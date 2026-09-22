"""MediaPipe BlazePose 推理（CPU，无需 GPU）。

装不上 mediapipe 时 `self.ok=False`，上层自动切 `--sim` —— 不允许崩（M1-6）。
"""
from __future__ import annotations

import logging

from ..rules.posture_rules import PoseObservation, compute_metrics

log = logging.getLogger("xiaoqi.pose")

try:  # pragma: no cover - 取决于本机是否安装
    import mediapipe as mp

    _SOLUTION = mp.solutions.pose
    _HAS_MEDIAPIPE = True
except Exception as _e:  # ImportError 或平台不支持
    mp = None
    _SOLUTION = None
    _HAS_MEDIAPIPE = False
    log.warning("MediaPipe 不可用（%s），请用 --sim 模式", _e)


class PoseEstimator:
    def __init__(self, model_complexity: int = 0) -> None:
        self.ok = _HAS_MEDIAPIPE
        self._pose = None
        if self.ok:
            self._pose = _SOLUTION.Pose(
                model_complexity=model_complexity,      # 0 = 最快，CPU 够用
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

    def infer(self, frame_bgr) -> PoseObservation:
        """BGR 帧 → PoseObservation。任何异常都降级为 unknown，不抛出。"""
        if not self.ok or self._pose is None:
            return PoseObservation(confidence=0.0, person_present=False)
        try:
            import cv2

            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            result = self._pose.process(rgb)
            if not result.pose_landmarks:
                return PoseObservation(confidence=0.0, person_present=False)
            lms = result.pose_landmarks.landmark
            points = [(p.x, p.y, p.z, p.visibility) for p in lms]
            conf = float(min(p.visibility for p in lms[11:25])) if len(lms) >= 25 else 0.5
            return PoseObservation(
                landmarks=points,
                confidence=conf,
                metrics=compute_metrics(points),
                person_present=True,
            )
        except Exception:
            log.exception("推理失败，本帧按无人处理")
            return PoseObservation(confidence=0.0, person_present=False)

    def close(self) -> None:
        if self._pose is not None:
            self._pose.close()
            self._pose = None
