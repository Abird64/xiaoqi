"""姿态状态机：防抖 / 持续时长 / 状态事件（M2-5「不是一闪一闪」的实现处）。"""
from __future__ import annotations

import time
from typing import Optional

from ..config import Config
from ..hub import now_ms

# 协议冻结的姿态状态枚举（接口协议 v0.1）
POSE_STATES = ("unknown", "upright", "slouch", "desk_hunch", "away", "drinking")


class PoseStateMachine:
    def __init__(self, cfg: Config, clock=time.time) -> None:
        self.cfg = cfg
        self.clock = clock
        self.state: str = "unknown"
        self.since_ts: int = now_ms()
        self._since_mono: float = clock()
        self._candidate: Optional[str] = None
        self._cand_since: float = 0.0
        self._last_metrics: dict = {}
        self._state_metrics: dict = {}      # 当前状态**切换时刻**的指标（refresh 用，避免与 state 不一致）
        self._last_confidence: float = 0.0

    def sustained_sec(self) -> float:
        return round(self.clock() - self._since_mono, 1)

    def feed(
        self,
        candidate: str,
        confidence: float,
        metrics: dict | None = None,
    ) -> Optional[dict]:
        """喂一帧判定结果。返回状态事件（仅在真正切换时），否则 None。"""
        if candidate not in POSE_STATES:
            candidate = "unknown"
        self._last_confidence = confidence
        self._last_metrics = metrics or {}

        if candidate == self.state:
            self._candidate = None          # 回到当前状态 → 取消待切换
            return None

        now = self.clock()
        if candidate != self._candidate:
            self._candidate = candidate
            self._cand_since = now

        hold = self.cfg.debounce_for(candidate)
        if now - self._cand_since < hold:
            return None                     # 还没持续够 → 不切（防抖）

        self.state = candidate
        self.since_ts = now_ms()
        self._since_mono = now
        self._candidate = None
        self._state_metrics = dict(self._last_metrics)
        return {
            "v": 1,
            "type": "state",
            "ts": self.since_ts,
            "pose": {
                "state": self.state,
                "confidence": round(confidence, 3),
                "since_ts": self.since_ts,
                "sustained_sec": 0.0,
                "metrics": dict(self._state_metrics),
            },
        }

    def refresh_event(self) -> Optional[dict]:
        """周期性同状态推送（带真实 sustained_sec），满足 ≤1 条/秒。"""
        if self.state == "unknown" and not self._state_metrics:
            return None
        return {
            "v": 1,
            "type": "state",
            "ts": now_ms(),
            "pose": {
                "state": self.state,
                "confidence": round(self._last_confidence, 3),
                "since_ts": self.since_ts,
                "sustained_sec": self.sustained_sec(),
                "metrics": dict(self._state_metrics),
            },
        }
