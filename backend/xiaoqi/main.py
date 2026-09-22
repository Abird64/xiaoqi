"""FastAPI 入口：WS Hub + 手机接入 + 历史查询 + 前端静态托管（D-007 单端口）。"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Config, load_config
from .hub import Hub, now_ms
from .ingest.phone import PhoneIngest, build_router
from .rules.calibration import Calibration
from .rules.posture_rules import PostureRules
from .state.machine import PoseStateMachine
from .store.db import Store
from .vision.camera import CaptureThread, SimThread

log = logging.getLogger("xiaoqi.main")


def create_app(cfg: Config | None = None, sim: bool = False) -> FastAPI:
    cfg = cfg or load_config()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()
        hub.bind_loop(loop)
        store = Store(cfg.db_path)
        hub.set_persist(store.write_event)
        app.state.store, app.state.cfg = store, cfg

        source = (SimThread(cfg, hub, rules, machine, calib) if sim
                  else CaptureThread(cfg, hub, rules, machine, calib))
        source.start()
        app.state.source = source
        log.info("数据源已启动：%s", "模拟(--sim)" if sim else "摄像头")

        async def heartbeat():
            while True:
                await asyncio.sleep(10)
                for ws in list(hub._clients):      # noqa: SLF001 心跳属 Hub 内部
                    try:
                        await ws.send_json({"v": 1, "type": "ping", "ts": now_ms()})
                    except Exception:
                        hub._clients.discard(ws)   # noqa: SLF001

        hb = asyncio.create_task(heartbeat())
        try:
            yield
        finally:
            hb.cancel()
            source.stop()
            source.join(timeout=3)
            store.close()
            log.info("已关闭")

    app = FastAPI(title="小栖 · 后端", version="0.1.0", lifespan=lifespan)

    hub = Hub()
    rules = PostureRules(cfg)
    machine = PoseStateMachine(cfg)
    calib = Calibration()
    phone = PhoneIngest(cfg, hub)
    app.state.hub, app.state.rules, app.state.machine = hub, rules, machine
    app.state.calib, app.state.phone = calib, phone

    app.include_router(build_router(cfg, hub, phone))

    # ---------- WebSocket ----------
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        await hub.add(ws)
        try:
            await ws.send_json(hub.hello())          # 首帧全量快照（协议 3.1）
            while True:
                await ws.receive_text()              # v0.1 前端不发消息，收到即忽略
        except WebSocketDisconnect:
            pass
        except Exception:
            log.debug("WS 异常断开", exc_info=True)
        finally:
            await hub.remove(ws)

    # ---------- 只读查询 ----------
    @app.get("/api/state")
    async def get_state():
        return {"v": 1, "type": "state", "ts": now_ms(), **hub.snapshot(),
                "capabilities_ready": {"calibrated": calib.done,
                                       "camera_error": getattr(
                                           app.state.source, "last_error", None)}}

    @app.get("/api/history")
    async def get_history(from_: int | None = None, to: int | None = None,
                          kind: str | None = None, limit: int = 5000):
        """人机课 M2 报告要用的历史查询（P7：是否随 v0.1 冻结待周会确认）。"""
        store: Store = app.state.store
        return {"v": 1, "ts": now_ms(),
                "items": store.query(from_, to, kind, limit)}

    @app.post("/api/calibration/reset")
    async def reset_calibration():
        calib.reset()
        rules.baseline_neck_deg = None
        return {"ok": True, "calibrated": False}

    @app.get("/api/health")
    async def health():
        return {"ok": True, "version": "0.1.0", "clients": hub.client_count,
                "calibrated": calib.done, "sim": sim}

    @app.get("/api/token")
    async def token():
        """配对令牌：打印在控制台 / 展示二维码给手机扫。"""
        return {"token": cfg.token,
                "endpoint": f"/api/ingest/health",
                "example_header": f"X-Xiaoqi-Token: {cfg.token}"}

    # ---------- 前端静态托管（交付形态：一条命令起全部）----------
    if cfg.frontend_dist:
        app.mount("/", StaticFiles(directory=str(cfg.frontend_dist), html=True),
                  name="frontend")

    @app.exception_handler(Exception)
    async def _on_error(request, exc):
        log.exception("未处理异常 %s", request.url.path)
        return JSONResponse(status_code=500,
                            content={"ok": False, "error": "INTERNAL",
                                     "message": str(exc)})

    return app


def run(sim: bool = False, host: str | None = None, port: int | None = None,
        config: str | None = None) -> None:
    import uvicorn

    cfg = load_config(config)
    app = create_app(cfg, sim=sim)
    banner = f"""
┌──────────────────────────────────────────────┐
│ 小栖 · 后端   {'[模拟链路 --sim]' if sim else '[摄像头链路]':<16}            │
│  前端/WS   ws://{host or cfg.host}:{cfg.port}/ws             │
│  手机上报  POST /api/ingest/health           │
│  配对令牌  {cfg.token:<38}│
│  历史查询  GET  /api/history                 │
└──────────────────────────────────────────────┘"""
    print(banner)
    uvicorn.run(app, host=host or cfg.host, port=port or cfg.port,
                log_level="info")
