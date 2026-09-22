"""手机步数上报接入（D-002：协议优先、客户端零开发）。

手机侧零代码：iOS 快捷指令 / Android HTTP Shortcuts → `POST /api/ingest/health`。
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from ..config import Config
from ..hub import Hub, now_ms


class PhoneIngest:
    def __init__(self, cfg: Config, hub: Hub) -> None:
        self.cfg = cfg
        self.hub = hub
        self.steps: int | None = None            # 当日累计
        self.updated_ts: int | None = None
        self.source: str | None = None
        self._last_by_device: dict[str, float] = {}   # device_id → 上次接收时刻

    def stale(self) -> bool:
        if self.updated_ts is None:
            return True
        return (now_ms() - self.updated_ts) / 1000.0 > self.cfg.stale_sec

    def snapshot(self) -> dict[str, Any]:
        return {
            "steps": self.steps,
            "updated_ts": self.updated_ts,
            "stale": self.stale(),
        }

    def accept(self, steps: int, ts: int | None, source: str | None,
               device_id: str | None, client_ip: str) -> dict:
        """返回协议规定的响应体。含幂等与「只前进不回退」两条规则。"""
        now = time.monotonic()
        key = device_id or client_ip or "unknown"

        # 1) 幂等：60 秒窗口内同设备重复上报直接丢弃
        last = self._last_by_device.get(key)
        if last is not None and (now - last) < self.cfg.dedup_window_sec:
            return {"ok": True, "deduped": True}
        self._last_by_device[key] = now

        # 2) 只前进不回退：新值更小视为跨零点/系统重置 → 开新记录
        if self.steps is not None and steps < self.steps:
            self.steps = steps
        else:
            self.steps = steps if self.steps is None else max(self.steps, steps)

        self.updated_ts = ts or now_ms()
        self.source = source
        snapshot = self.snapshot()
        self.hub.publish_threadsafe({"type": "state", "phone": snapshot})
        return {"ok": True, "deduped": False}


def build_router(cfg: Config, hub: Hub, ingest: PhoneIngest) -> APIRouter:
    router = APIRouter()

    @router.post("/api/ingest/health")
    async def ingest_health(request: Request,
                            x_xiaoqi_token: str | None = Header(default=None)):
        if x_xiaoqi_token != cfg.token:
            return JSONResponse(status_code=401,
                                 content={"ok": False, "error": "BAD_TOKEN"})
        body = await request.json()
        steps = body.get("steps")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
            return JSONResponse(status_code=400, content={
                "ok": False, "error": "INVALID_FIELD", "field": "steps"})
        ts = body.get("ts")
        if ts is not None and not isinstance(ts, int):
            return JSONResponse(status_code=400, content={
                "ok": False, "error": "INVALID_FIELD", "field": "ts"})
        return ingest.accept(
            steps=steps, ts=ts,
            source=body.get("source"), device_id=body.get("device_id"),
            client_ip=request.client.host if request.client else "",
        )

    return router
