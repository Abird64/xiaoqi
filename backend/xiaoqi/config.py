"""配置加载：config.yaml → 对象。M2-2「改配置不改代码」的载体。"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 8000
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    neck_delta_deg: float = 15.0
    hunch_delta_deg: float = 28.0
    min_confidence: float = 0.55
    absent_sec: float = 1.5
    sample_hz: int = 10
    debounce_default: float = 2.0
    debounce: dict[str, float] = field(default_factory=dict)
    refresh_sec: float = 10.0
    water_sec: int = 1800
    standup_sec: int = 1800
    token: str = ""
    dedup_window_sec: int = 60
    stale_sec: int = 900
    db_path: Path = BACKEND_DIR / "data" / "xiaoqi.db"
    frontend_dist: Path | None = None

    def debounce_for(self, state: str) -> float:
        return self.debounce.get(state, self.debounce_default)


def _dig(d: dict, *keys: str, default: Any = None) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def load_config(path: str | Path | None = None) -> Config:
    cfg_file = Path(path) if path else BACKEND_DIR / "config.yaml"
    raw: dict = {}
    if cfg_file.exists():
        raw = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}

    c = Config()
    c.host = _dig(raw, "server", "host", default=c.host)
    c.port = int(_dig(raw, "server", "port", default=c.port))
    c.camera_index = int(_dig(raw, "camera", "index", default=c.camera_index))
    c.camera_width = int(_dig(raw, "camera", "width", default=c.camera_width))
    c.camera_height = int(_dig(raw, "camera", "height", default=c.camera_height))
    c.camera_fps = int(_dig(raw, "camera", "fps", default=c.camera_fps))

    c.neck_delta_deg = float(_dig(raw, "posture", "neck_delta_deg", default=c.neck_delta_deg))
    c.hunch_delta_deg = float(_dig(raw, "posture", "hunch_delta_deg", default=c.hunch_delta_deg))
    c.min_confidence = float(_dig(raw, "posture", "min_confidence", default=c.min_confidence))
    c.absent_sec = float(_dig(raw, "posture", "absent_sec", default=c.absent_sec))
    c.sample_hz = int(_dig(raw, "posture", "sample_hz", default=c.sample_hz))

    c.debounce_default = float(_dig(raw, "debounce", "default_sec", default=c.debounce_default))
    db_raw = _dig(raw, "debounce", default={}) or {}
    c.debounce = {k: float(v) for k, v in db_raw.items() if k != "default_sec"}

    c.refresh_sec = float(_dig(raw, "refresh_sec", default=c.refresh_sec))
    c.water_sec = int(_dig(raw, "reminder", "water_sec", default=c.water_sec))
    c.standup_sec = int(_dig(raw, "reminder", "standup_sec", default=c.standup_sec))
    c.dedup_window_sec = int(_dig(raw, "phone", "dedup_window_sec", default=c.dedup_window_sec))
    c.stale_sec = int(_dig(raw, "phone", "stale_sec", default=c.stale_sec))

    token = _dig(raw, "phone", "token", default="") or ""
    c.token = token or secrets.token_urlsafe(16)

    dbp = _dig(raw, "storage", "path", default=None)
    c.db_path = (BACKEND_DIR / dbp) if dbp else c.db_path

    dist = _dig(raw, "frontend", "dist", default=None)
    if dist:
        p = (BACKEND_DIR / dist).resolve()
        c.frontend_dist = p if p.exists() else None
    return c
