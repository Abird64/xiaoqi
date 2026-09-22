"""个人化校准（M2-1）：启动时引导「坐直」采样基线。

为什么必须校准：每个人的头颈几何量本来就不同，绝对阈值必然误报/漏报（R1）。
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from ..hub import now_ms
from .posture_rules import PoseObservation, compute_metrics


@dataclass
class Calibration:
    required_samples: int = 30
    samples: list = field(default_factory=list)
    baseline_neck_deg: float | None = None
    calibrated_at_ms: int | None = None

    @property
    def done(self) -> bool:
        return self.baseline_neck_deg is not None

    @property
    def progress(self) -> float:
        return round(min(1.0, len(self.samples) / self.required_samples), 2)

    def feed(self, obs: PoseObservation) -> bool:
        """喂一帧「坐直」姿态。采满即出基线，返回是否刚完成。"""
        if self.done:
            return False
        if not obs.person_present or not obs.landmarks or obs.confidence <= 0:
            return False
        metrics = obs.metrics or compute_metrics(obs.landmarks)
        self.samples.append(metrics["neck_angle_deg"])
        if len(self.samples) < self.required_samples:
            return False
        trimmed = statistics.trim_mean(self.samples, 0.1) if len(self.samples) >= 10 \
            else statistics.fmean(self.samples)
        self.baseline_neck_deg = round(float(trimmed), 1)
        self.calibrated_at_ms = now_ms()
        return True

    def reset(self) -> None:
        self.samples.clear()
        self.baseline_neck_deg = None
        self.calibrated_at_ms = None
