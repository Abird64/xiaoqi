"""周期性坐姿抽检线程（2026-11-16 方案：定时抓拍，不实时监测）。

为什么改成抽检：
  任课老师提醒实时监测会持续占用大量算力；团队因此改为「定期拍摄抽检」。
  副作用是技术约束大幅放宽 —— 不再关心帧率，可以换用精度更高的 bottom-up 模型。

线程行为：
  每 `sitting.interval_sec`（默认 60s）抓一帧摄像头画面 → Lightweight OpenPose
  推理 → 算指标 → 粗判 → 存库 + 推 WS + 更新 `latest`。

摄像头「权限」在 Windows 上是系统级开关，程序侧能做的是**打开并分类报错**：
  设备不存在 / 被其它程序占用 / 隐私设置禁止 / 直接打不开，分别给不同提示，
  且失败后不退出线程，下一轮继续重试（M1-6 精神：不崩）。

线程安全：`latest` / `last_error` 由本线程写、接口线程读，读的是不可变 dict 引用，
          CPython 下赋值是原子的，足够用；不做锁以免拖慢抽检。
"""
from __future__ import annotations

import logging
import threading
import time

from ..hub import now_ms
from ..rules import sitting_rules
from .pose_lw import LWPoseEstimator

log = logging.getLogger("xiaoqi.spot")


class SpotCheckThread(threading.Thread):
    """周期性抓拍 + 姿态判定。"""

    def __init__(self, cfg, store=None, hub=None) -> None:
        super().__init__(daemon=True, name="xiaoqi-spot")
        self.cfg = cfg
        self.store = store
        self.hub = hub
        self.interval = max(5, int(getattr(cfg, "sitting_interval_sec", 60)))
        self.camera_index = int(getattr(cfg, "sitting_camera_index",
                                        cfg.camera_index))

        self.latest: dict | None = None
        self.last_error: str | None = None
        self.rounds = 0

        self._stop_event = threading.Event()
        self._wake = threading.Event()
        self._cap = None
        self._next_ts: int | None = None
        # 连续"画面里没有人"的轮数：单轮记 unknown，连续两轮才算真的离开
        self._no_person_rounds = 0

        self.estimator = LWPoseEstimator(
            repo_dir=getattr(cfg, "sitting_lw_repo", ""),
            checkpoint=getattr(cfg, "sitting_lw_checkpoint", ""),
            height_size=int(getattr(cfg, "sitting_height_size", 256)),
            num_threads=int(getattr(cfg, "sitting_torch_threads", 1)),
        )
        if not self.estimator.ok:
            self.last_error = self.estimator.last_error

    # ------------------------------------------------------------------ 控制
    def stop(self) -> None:
        self._stop_event.set()
        self._wake.set()

    def trigger(self) -> None:
        """手动立即抽检一次（接口 /api/sitting/check 用）。"""
        self._wake.set()

    # ------------------------------------------------------------------ 摄像头
    def _open_camera(self):
        """打开摄像头；失败返回 (None, 可读原因)。"""
        import cv2

        for backend, tag in ((cv2.CAP_DSHOW, "DSHOW"), (cv2.CAP_ANY, "ANY")):
            try:
                cap = cv2.VideoCapture(self.camera_index, backend)
            except Exception as e:                       # 极少见，兜底
                log.warning("摄像头打开异常（%s）：%s", tag, e)
                continue
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.camera_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.camera_height)
                log.info("抽检摄像头已打开 #%s（%s）", self.camera_index, tag)
                return cap, None
            cap.release()

        return None, (
            f"摄像头 #{self.camera_index} 打不开。常见原因：\n"
            "    1) 设备未连接或被禁用（设备管理器里看不到）；\n"
            "    2) 已被其它程序占用（相机 App / 会议软件 / 其它调试进程）；\n"
            "    3) Windows 设置 → 隐私 → 相机，未允许桌面应用访问。")

    def _grab_frame(self):
        """抓一帧。前几帧丢弃，等自动曝光稳定。"""
        if self._cap is None:
            self._cap, err = self._open_camera()
            if self._cap is None:
                return None, err
            for _ in range(5):
                self._cap.read()
        ok, frame = self._cap.read()
        if not ok or frame is None:
            # 设备被拔掉/占用：释放，下一轮重新打开
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
            return None, "取帧失败（设备可能被拔出或被占用），下一轮重试"
        return frame, None

    # ------------------------------------------------------------------ 单轮
    def _run_once(self) -> dict:
        ts = now_ms()
        result: dict = {
            "v": 1, "ts": ts, "ok": False,
            "state": "unknown", "confidence": 0.0, "reason": "",
            "metrics": {}, "infer_ms": None, "error": None,
        }

        if not self.estimator.ok:
            result["error"] = self.estimator.last_error or "姿态模型不可用"
            return result

        frame, err = self._grab_frame()
        if frame is None:
            result["error"] = err
            return result

        h, w = frame.shape[:2]
        result["frame_size"] = [w, h]
        people = self.estimator.infer(frame)
        result["infer_ms"] = self.estimator.infer_ms
        result["people"] = len(people)

        if not people:
            # 一张 60 秒的抽检帧没检出人，多半是构图/逆光/只露半身，不能直接写
            # "人离开了"（会污染 away 时长统计）。连续两轮才记 away。
            self._no_person_rounds += 1
            away = self._no_person_rounds >= 2
            result.update(state="away" if away else "unknown", confidence=0.0,
                          reason="no_person_away" if away else "no_person",
                          reason_text=sitting_rules.reason_text(
                              "no_person_away" if away else "no_person"),
                          ok=True, no_person_rounds=self._no_person_rounds)
            return result

        self._no_person_rounds = 0
        # 取组内得分最高的人
        pts = people[0]["pts"]
        metrics = sitting_rules.compute_metrics(
            pts, w, h, float(getattr(self.cfg, "sitting_margin_ratio", 0.03)))
        state, conf, reason = sitting_rules.classify(metrics, self.cfg)
        result.update(
            ok=True, state=state, confidence=conf, reason=reason,
            reason_text=sitting_rules.reason_text(reason),
            metrics=metrics, pose_score=round(float(people[0]["score"]), 3),
        )
        return result

    # ------------------------------------------------------------------ 主循环
    def run(self) -> None:
        if not self.estimator.ok:
            log.error("坐姿抽检未启动：%s", self.last_error)
            return

        log.info("坐姿抽检已启动：每 %s 秒一次（摄像头 #%s）",
                 self.interval, self.camera_index)
        while not self._stop_event.is_set():
            try:
                result = self._run_once()
                self.rounds += 1
                self.latest = result

                if result["error"]:
                    self.last_error = result["error"]
                    log.warning("抽检失败：%s", result["error"])
                else:
                    self.last_error = None
                    self._publish(result)
            except Exception:
                log.exception("抽检线程异常（继续下一轮）")
                self.last_error = "抽检线程异常，详见日志"
                self._drop_camera()

            # 等 interval，或被 trigger() 提前唤醒；next_ts 这里算才准确
            self._next_ts = now_ms() + self.interval * 1000
            self._wake.wait(timeout=self.interval)
            self._wake.clear()

        self._drop_camera()
        self.estimator.close()
        log.info("坐姿抽检已停止")

    def _publish(self, result: dict) -> None:
        """推一条 `type:"sitting"` 事件；落库由 Hub 统一完成（单次写入）。

        以前既手工 `store.write_event` 又 `hub.publish_threadsafe`，等于一次抽检
        落两行，其中一行是伪装成 `state` 的伪样本，会混进 `/api/history` 的
        实时统计。现在只发一条、只落一次库，`kind="sitting"` 独立存在。
        """
        state = result.get("state")
        log.info("抽检 #%s：%s（%s）", self.rounds, state, result.get("reason"))
        event = {
            "v": 1, "type": "sitting", "ts": result["ts"],
            # 复用 events 表的 state/confidence/metrics 列，便于 SQL 直接查
            "pose": {"state": state,
                     "confidence": result.get("confidence"),
                     "metrics": result.get("metrics") or {}},
            "sitting": result,
        }
        if self.hub is not None:
            try:
                self.hub.publish_threadsafe(event)   # 落库 + 广播一次
            except Exception:
                log.debug("抽检推送失败", exc_info=True)
        elif self.store is not None:                 # 无 Hub 时（脚本/测试）直接落库
            try:
                self.store.write_event(event)
            except Exception:
                log.exception("坐姿抽检落库失败")

    def _drop_camera(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    # ------------------------------------------------------------------ 只读
    def snapshot(self) -> dict:
        """给 /api/sitting/latest 用的快照（不触发新抽检）。"""
        return {
            "v": 1,
            # ts = 最近一次抽检的抓拍时刻（没有结果时为 None）；"现在"另给 server_ts
            "ts": self.latest["ts"] if self.latest else None,
            "server_ts": now_ms(),
            "interval_sec": self.interval,
            "next_ts": self._next_ts,
            "rounds": self.rounds,
            "model_ready": self.estimator.ok,
            "camera_ready": self._cap is not None,
            "last_error": self.last_error,
            "result": self.latest,
        }
