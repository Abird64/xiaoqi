"""MediaPipe Tasks API 姿态估计（CPU，无需 GPU）。

**决策**：2026-09-23 团队定「使用最新版 mediapipe」，而 1.0 已移除旧的
`mp.solutions.pose`，故本模块整体重写为 Tasks API（`PoseLandmarker`）。
**对外接口 `infer(frame_bgr) -> PoseObservation` 保持不变，上层零改动。**

铁律：**不允许静默降级**。依赖缺失 / 模型缺失 / 路径错误一律置 `ok=False`
并写清 `last_error`，由采集线程上报 error 帧（M1-6 精神）。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from ..config import BACKEND_DIR, Config, load_config
from ..rules.posture_rules import PoseObservation, compute_metrics

log = logging.getLogger("xiaoqi.pose")

# lite 模型：对应旧实现的 model_complexity=0（最快、CPU 友好）
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_lite/float16/1/pose_landmarker_lite.task")

# 官方骨架连线（35 条），给 scripts/debug_view.py 用；旧实现是手写 10 条
SKELETON: list[tuple[int, int]] = []

try:  # pragma: no cover - 取决于本机是否安装
    import cv2
    import numpy as np
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    _HAS_MP = True
    _IMPORT_ERR = ""
    SKELETON = [(c.start, c.end)
                for c in vision.PoseLandmarksConnections.POSE_LANDMARKS]
except Exception as _e:  # ImportError 或平台不支持
    cv2 = np = mp = BaseOptions = vision = None
    _HAS_MP = False
    _IMPORT_ERR = f"{type(_e).__name__}: {_e}"


class PoseEstimator:
    """一帧 BGR → 33 点关键点。失败时 ok=False，**绝不假装"无人"**。"""

    def __init__(self, cfg: Config | None = None) -> None:
        self.cfg = cfg or load_config()
        self.ok = False
        self.last_error: str | None = None
        self.infer_ms: float = 0.0          # 最近一次推理耗时（NFR-P-02 实测用）
        self._landmarker = None
        self._last_ts_ms = 0

        if not _HAS_MP:
            self.last_error = (
                f"mediapipe 不可用（{_IMPORT_ERR}）。"
                "请 `pip install -r requirements.txt`（需 mediapipe>=1.0）")
            log.error(self.last_error)
            return

        path = Path(self.cfg.vision_model_path)
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        if not path.exists():
            self.last_error = (
                f"姿态模型不存在：{path}\n"
                f"    获取（约 5.5 MB）：curl -L -o \"{path}\" {MODEL_URL}\n"
                f"    或浏览器打开该 URL 另存到上述路径。")
            log.error("姿态模型缺失，姿态链不可用：%s", path)
            return

        try:
            opts = vision.PoseLandmarkerOptions(
                # 用字节而不是路径：mediapipe 的 C++ 层对非 ASCII 路径
                # （本项目就在 G:\中级实训\… 下）会报 "Unable to open file"，
                # 传 model_asset_buffer 可完全绕过这个限制；5.5 MB 常驻内存可接受。
                base_options=BaseOptions(model_asset_buffer=path.read_bytes()),
                running_mode=vision.RunningMode.VIDEO,   # 需要帧间跟踪
                num_poses=int(self.cfg.vision_num_poses),
                min_pose_detection_confidence=float(
                    self.cfg.vision_min_detection_confidence),
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=float(
                    self.cfg.vision_min_tracking_confidence),
                output_segmentation_masks=False,
            )
            self._landmarker = vision.PoseLandmarker.create_from_options(opts)
            self.ok = True
            log.info("姿态模型已加载：%s（CPU / VIDEO 模式）", path.name)
        except Exception as e:
            self.last_error = f"姿态模型加载失败：{type(e).__name__}: {e}"
            log.exception("姿态模型加载失败")

    # ------------------------------------------------------------------
    def infer(self, frame_bgr) -> PoseObservation:
        """BGR 帧 → PoseObservation。单帧异常按"无人"处理，不抛出。"""
        if not self.ok or self._landmarker is None:
            return PoseObservation(confidence=0.0, person_present=False)
        try:
            t0 = time.perf_counter()
            rgb = np.ascontiguousarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            ts = int(time.monotonic() * 1000)          # VIDEO 模式必须严格递增
            if ts <= self._last_ts_ms:
                ts = self._last_ts_ms + 1
            self._last_ts_ms = ts

            res = self._landmarker.detect_for_video(mp_image, ts)
            self.infer_ms = round((time.perf_counter() - t0) * 1000, 1)

            if not res.pose_landmarks:                 # 画面中没人
                return PoseObservation(confidence=0.0, person_present=False)

            lms = res.pose_landmarks[0]                # num_poses=1，仍要多取一层
            points = [(p.x, p.y, p.z, getattr(p, "visibility", 0.0) or 0.0)
                      for p in lms]
            if len(points) < 25:                       # 点数不足 → 按无人，避免上层 IndexError
                return PoseObservation(confidence=0.0, person_present=False)

            conf = float(min(p[3] for p in points[11:25]))   # 与旧实现同口径
            return PoseObservation(landmarks=points, confidence=conf,
                                   metrics=compute_metrics(points), person_present=True)
        except Exception:
            log.exception("推理失败，本帧按无人处理")
            return PoseObservation(confidence=0.0, person_present=False)

    def close(self) -> None:
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass
            self._landmarker = None
        self.ok = False
