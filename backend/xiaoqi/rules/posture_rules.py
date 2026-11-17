"""姿态判定：关键点 → 客观几何量 → 状态候选。

⚠️ 唯一硬骨头是阈值（风险 R1）。这里只做**几何计算与相对基线比较**，
   基线由 calibration 采样得到，阈值全部来自 config.yaml（M2-2）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..config import Config

# 33 点索引约定（沿用 BlazePose 编号；--sim 合成点与校准链路按这套编号）
NOSE, LEFT_EAR, RIGHT_EAR = 0, 7, 8
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_HIP, RIGHT_HIP = 23, 24


@dataclass
class PoseObservation:
    """一帧推理结果。landmarks 为 (x, y, z, visibility) 列表。"""

    landmarks: list | None = None
    confidence: float = 0.0
    metrics: dict = field(default_factory=dict)
    person_present: bool = True


def _mid(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0)


def _angle_deg(u, v) -> float:
    """两个向量夹角（度）。"""
    dot = u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
    nu = math.sqrt(sum(c * c for c in u))
    nv = math.sqrt(sum(c * c for c in v))
    if nu < 1e-9 or nv < 1e-9:
        return 0.0
    cos = max(-1.0, min(1.0, dot / (nu * nv)))
    return math.degrees(math.acos(cos))


def compute_metrics(landmarks: list) -> dict:
    """算出客观指标。

    三个角度各有含义，别混用（接口协议 §3.2：metrics 仅供调试/可视化）：
      neck_angle_deg  头相对**躯干轴**的前屈 —— 正面/侧面都能用，但驼背时躯干也弯，会低估
      head_pitch_deg  头相对**竖直方向**的绝对前倾 —— 侧面视角最直观，和"看起来驼不驼"最接近
      shoulder_tilt_deg 肩线歪斜 —— **只在正面/斜前可用**；侧面两肩重叠时数学上无解，返回 None
    view 标明当前视角，view=="side" 时 shoulder_tilt_deg 一定是 None。
    """
    ear = _mid(landmarks[LEFT_EAR], landmarks[RIGHT_EAR])
    shoulder = _mid(landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER])
    hip = _mid(landmarks[LEFT_HIP], landmarks[RIGHT_HIP])

    up = (shoulder[0] - hip[0], shoulder[1] - hip[1], shoulder[2] - hip[2])
    neck = (ear[0] - shoulder[0], ear[1] - shoulder[1], ear[2] - shoulder[2])
    neck_angle = _angle_deg(up, neck)                     # 头相对躯干的前倾角

    # 头相对竖直方向：只取图像平面内的 x/y，避开 MediaPipe 深度 z 的噪声
    head_pitch = _angle_deg((0.0, -1.0, 0.0), (neck[0], neck[1], 0.0))

    ls, rs = landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER]
    dx, dy = rs[0] - ls[0], rs[1] - ls[1]
    torso_len = math.hypot(shoulder[0] - hip[0], shoulder[1] - hip[1])

    # 两肩在图像上的跨度 / 躯干长度：太窄说明人基本侧对镜头，
    # 此时 atan2(dy, dx) 的 dx→0，肩线角必然飙到 60°~130°，指标失去意义。
    span = math.hypot(dx, dy)
    ratio = (span / torso_len) if torso_len > 1e-6 else 0.0
    if ratio < 0.35:
        shoulder_tilt = None
        view = "side"
    else:
        ang = abs(math.degrees(math.atan2(dy, dx)))
        shoulder_tilt = round(min(ang, 180.0 - ang), 1)   # 折回 0~90°，别让左右方向翻出 180°
        view = "frontal"

    # 近似距离：躯干像素长度 → cm（标定常数，实测再调）
    distance_cm = round(torso_len * 140.0, 1) if torso_len > 0 else 0.0

    return {
        "neck_angle_deg": round(neck_angle, 1),
        "head_pitch_deg": round(head_pitch, 1),
        "shoulder_tilt_deg": shoulder_tilt,
        "view": view,
        "distance_cm": distance_cm,
    }


class PostureRules:
    """把几何量映射成 pose_state 候选。基线未校准时全部返回 unknown。"""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.baseline_neck_deg: float | None = None   # 由校准写入
        self._absent_frames = 0

    @property
    def calibrated(self) -> bool:
        return self.baseline_neck_deg is not None

    def classify(self, obs: PoseObservation) -> tuple[str, float, dict]:
        """返回 (state 候选, confidence, metrics)。"""
        if not obs.person_present or obs.confidence < self.cfg.min_confidence:
            self._absent_frames += 1
            if self._absent_frames * (1.0 / self.cfg.sample_hz) >= self.cfg.absent_sec:
                return "away", obs.confidence, {}
            return "unknown", obs.confidence, {}

        self._absent_frames = 0
        if not obs.landmarks or not self.calibrated:
            return "unknown", obs.confidence, obs.metrics

        metrics = obs.metrics or compute_metrics(obs.landmarks)
        delta = metrics["neck_angle_deg"] - float(self.baseline_neck_deg)

        if delta >= self.cfg.hunch_delta_deg:
            state = "desk_hunch"
        elif delta >= self.cfg.neck_delta_deg:
            state = "slouch"
        else:
            state = "upright"

        # drinking 为可选态：M1 不识别，协议枚举保留（P7 决议）
        return state, obs.confidence, metrics
