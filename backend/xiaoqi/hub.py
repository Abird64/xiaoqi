"""事件总线 + WebSocket Hub。

D-007 进程模型：三路采集各自为**线程**，只把结果投进来；
**绝不允许**在采集线程里碰事件循环 → 一律走 `publish_threadsafe`。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from . import __version__

log = logging.getLogger("xiaoqi.hub")

PROTOCOL_VERSION = 1
CAPABILITIES = ["pose", "phone"]  # behavior 上线后加入


def now_ms() -> int:
    return int(time.time() * 1000)


class Hub:
    def __init__(self) -> None:
        self._clients: set = set()
        self._snapshot: dict[str, Any] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._on_event: Callable[[dict], Awaitable[None] | None] | None = None

    # ---------- 生命周期 ----------
    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def set_persist(self, fn: Callable[[dict], Awaitable[None] | None]) -> None:
        """落库回调（store.db）。只在事件循环内被调用。"""
        self._on_event = fn

    # ---------- 订阅 ----------
    async def add(self, ws) -> None:
        self._clients.add(ws)

    async def remove(self, ws) -> None:
        self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ---------- 发布 ----------
    def publish_threadsafe(self, event: dict) -> None:
        """线程侧入口（采集线程 / 行为线程用）。事件循环没绑好就丢弃。"""
        if self._loop is None or self._loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.publish(event), self._loop)
        except RuntimeError:  # 循环正在关闭
            log.debug("事件循环已关闭，丢弃事件 %s", event.get("type"))

    async def publish(self, event: dict) -> None:
        event.setdefault("v", PROTOCOL_VERSION)
        event.setdefault("ts", now_ms())
        self._merge_snapshot(event)
        if self._on_event:
            try:
                res = self._on_event(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:  # 落库失败不能打断广播
                log.exception("落库失败")
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    def _merge_snapshot(self, event: dict) -> None:
        """hello 要全量快照 → 持续合并 pose / behavior / phone / reminder 摘要。"""
        for key in ("pose", "behavior", "phone", "reminder"):
            if key in event:
                self._snapshot[key] = event[key]

    # ---------- 构造消息 ----------
    def hello(self) -> dict:
        msg: dict[str, Any] = {
            "v": PROTOCOL_VERSION,
            "type": "hello",
            "ts": now_ms(),
            "server": {"version": __version__, "capabilities": list(CAPABILITIES)},
        }
        msg.update(self._snapshot)
        msg.setdefault("pose", {"state": "unknown", "confidence": 0.0, "since_ts": None})
        return msg

    def snapshot(self) -> dict:
        return dict(self._snapshot)
