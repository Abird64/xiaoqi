"""摄像头采集线程 + `--sim` 模拟线程（两者对外接口一致）。

铁律：本线程**只算不发**，事件一律 `hub.publish_threadsafe`。
"""
from __future__ import annotations

import logging
import threading
import time

from ..config import Config
from ..hub import Hub
from ..rules.calibration import Calibration
from ..rules.posture_rules import PoseObservation, PostureRules, compute_metrics
from ..state.machine import PoseStateMachine
from .pose_estimator import PoseEstimator

log = logging.getLogger("xiaoqi.camera")

# --sim 剧本：给没有摄像头 / 给前端 B 做 mock 消费（XQ-011）
SIM_SCRIPT = [
    ("upright", 8.0),
    ("slouch", 8.0),
    ("desk_hunch", 8.0),
    ("upright", 6.0),
    ("away", 5.0),
]


class _BaseThread(threading.Thread):
    def __init__(self, cfg: Config, hub: Hub, rules: PostureRules,
                 machine: PoseStateMachine, calib: Calibration) -> None:
        super().__init__(daemon=True, name="xiaoqi-source")
        self.cfg, self.hub = cfg, hub
        self.rules, self.machine, self.calib = rules, machine, calib
        self._stop_event = threading.Event()   # 注意：不能叫 _stop，会覆盖 Thread 内部的 _stop() 方法
        self._last_refresh = 0.0
        self.last_error: str | None = None

    def stop(self) -> None:
        self._stop_event.set()

    def _handle(self, obs: PoseObservation) -> None:
        if not self.calib.done:
            if self.calib.feed(obs):                 # 校准刚完成
                self.rules.baseline_neck_deg = self.calib.baseline_neck_deg
                self.hub.publish_threadsafe({
                    "type": "state", "source": "calibration",
                    "baseline_neck_deg": self.calib.baseline_neck_deg,
                })
            return                                   # 校准期间不判定

        state, conf, metrics = self.rules.classify(obs)
        event = self.machine.feed(state, conf, metrics)
        if event:
            self.hub.publish_threadsafe(event)
        elif time.monotonic() - self._last_refresh >= self.cfg.refresh_sec:
            self._last_refresh = time.monotonic()
            ref = self.machine.refresh_event()
            if ref:
                self.hub.publish_threadsafe(ref)

    def _sleep(self) -> None:
        self._stop_event.wait(1.0 / self.cfg.sample_hz)


class CaptureThread(_BaseThread):
    """真实链路：USB 摄像头 → MediaPipe → 判定 → 状态机 → Hub（M1-1/1-2/1-3）。"""

    def __init__(self, *a, estimator: PoseEstimator | None = None, **kw) -> None:
        super().__init__(*a, **kw)
        self.estimator = estimator or PoseEstimator()

    def run(self) -> None:
        cap = None
        while not self._stop_event.is_set():
            try:
                if cap is None:
                    import cv2
                    cap = cv2.VideoCapture(self.cfg.camera_index)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.camera_width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.camera_height)
                    if not cap.isOpened():
                        raise RuntimeError(f"摄像头 {self.cfg.camera_index} 打不开")
                    log.info("摄像头已打开 #%s", self.cfg.camera_index)

                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("摄像头断流")   # → M1-6：报错但不崩
                # 降采样靠 _sleep() 控制在 sample_hz（默认 10Hz），
                # 摄像头 30fps 多出的帧由驱动缓冲丢弃，CPU 不空转。
                self._handle(self.estimator.infer(frame))
                self.last_error = None
                self._sleep()
            except Exception as e:                       # 断流 / 拔线 → 报错 + 重连
                self.last_error = str(e)
                log.warning("采集异常，3 秒后重试：%s", e)
                self.hub.publish_threadsafe(
                    {"type": "error", "code": "POSE_LOST", "message": str(e)})
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                self._stop_event.wait(3.0)
        if cap is not None:
            cap.release()
        self.estimator.close()
        log.info("采集线程已停止")


class SimThread(_BaseThread):
    """模拟链路：按剧本吐合成关键点。无摄像头也能演示 M1-4/1-5，B 联调也用它。"""

    def run(self) -> None:
        idx, elapsed = 0, 0.0
        self.rules.baseline_neck_deg = 12.0          # 伪基线，跳过校准
        self.calib.baseline_neck_deg = 12.0
        log.info("模拟链路启动（--sim）")
        while not self._stop_event.is_set():
            target, duration = SIM_SCRIPT[idx % len(SIM_SCRIPT)]
            obs = self._synthetic(target)
            self._handle(obs)
            elapsed += 1.0 / self.cfg.sample_hz
            if elapsed >= duration:
                elapsed, idx = 0.0, idx + 1
            self._sleep()
        log.info("模拟链程已停止")

    @staticmethod
    def _synthetic(target: str) -> PoseObservation:
        if target == "away":
            return PoseObservation(confidence=0.0, person_present=False)
        # 伪 33 点：只要肩/髋/耳能构成几何关系即可
        pts = [(0.5, 0.5, 0.0, 0.99)] * 33
        # forward = 耳朵相对肩的前移量。必须先算过：三个档位代入 compute_metrics
        # 得到的 delta(neck-基线 12°) 要分别落在 [0,15) / [15,28) / [28,∞) 区间，
        # 否则剧本会跳过 slouch 直接判成 desk_hunch（首次实现就踩了这个坑）。
        #   forward=0  → 0.0° (delta 0)      upright
        #   forward=26 → 34.7° (delta 22.7)  slouch
        #   forward=40 → 46.8° (delta 34.8)  desk_hunch
        forward = {"upright": 0.0, "slouch": 26.0, "desk_hunch": 40.0}[target]
        pts[7] = (0.5 + forward * 0.004, 0.30, 0.0, 0.95)    # 左耳
        pts[8] = (0.5 + forward * 0.004, 0.30, 0.0, 0.95)    # 右耳
        pts[11] = (0.40, 0.45, 0.0, 0.98)                    # 左肩
        pts[12] = (0.60, 0.45, 0.0, 0.98)                    # 右肩
        pts[23] = (0.43, 0.70, 0.0, 0.98)                    # 左髋
        pts[24] = (0.57, 0.70, 0.0, 0.98)                    # 右髋
        return PoseObservation(landmarks=pts, confidence=0.9,
                               metrics=compute_metrics(pts), person_present=True)
