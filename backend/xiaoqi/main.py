"""FastAPI 入口：WS Hub + 手机接入 + 历史查询 + 前端静态托管（D-007 单端口）。"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from fastapi import (FastAPI, HTTPException, Query, WebSocket,
                     WebSocketDisconnect)
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Config, load_config
from .hub import Hub, now_ms
from .ingest.phone import PhoneIngest, build_router
from .rules.calibration import Calibration
from .rules.posture_rules import PostureRules
from .state.machine import PoseStateMachine
from .store.db import Store
from .vision.camera import SimThread
from .vision.spot_check import SpotCheckThread

log = logging.getLogger("xiaoqi.main")

# 协议 §4.1：GET /api/history 单次查询范围上限
HISTORY_MAX_RANGE_MS = 7 * 24 * 3600 * 1000


def create_app(cfg: Config | None = None, sim: bool = False) -> FastAPI:
    cfg = cfg or load_config()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()
        hub.bind_loop(loop)
        store = Store(cfg.db_path)
        hub.set_persist(store.write_event)
        app.state.store, app.state.cfg = store, cfg

        # ---- 姿态源（D-016：抽检是唯一真实姿态源，没有 MediaPipe 实时链可退）----
        # `--sim` 只吐合成数据、不碰摄像头；真机模式要么抽检能跑，要么就没有姿态数据，
        # 必须把原因喊出来（前端 POSE_UNAVAILABLE），不能假装画面里没人。
        spot = None
        if sim:
            log.info("--sim：坐姿抽检不启用（演示用合成数据，不占真摄像头）")
        elif getattr(cfg, "sitting_enabled", False):
            # 模型加载是同步的（torch import + 88MB 权重），放在这里会阻塞启动数秒
            spot = SpotCheckThread(cfg, store=store, hub=hub)
            app.state.spot = spot
        else:
            log.info("坐姿抽检未启用（config.yaml 的 sitting.enabled=false）")

        source = None
        if sim:
            source = SimThread(cfg, hub, rules, machine, calib)
            source.start()
            log.info("数据源已启动：模拟(--sim)")
        elif spot is not None and spot.estimator.ok:
            spot.start()
            log.info("坐姿抽检已启动：每 %ss 一次，摄像头 #%s",
                     spot.interval, spot.camera_index)
        else:
            reason = (spot.last_error if spot is not None
                      else "坐姿抽检未启用（sitting.enabled=false）")
            log.error("没有可用的姿态源：%s", reason)
            hub.publish_threadsafe({
                "type": "error", "code": "POSE_UNAVAILABLE", "message": reason})
        app.state.source = source

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
            # 只有真正 start() 过的线程才 join：模型缺失时抽检线程从未启动，
            # 无条件 join 会抛 RuntimeError 把整个关闭流程带崩（TestClient 直接报错）。
            if spot is not None:
                spot.stop()
                if spot.is_alive():
                    spot.join(timeout=3)
            if source is not None:
                source.stop()
                if source.is_alive():
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
        spot = getattr(app.state, "spot", None)
        return {"v": 1, "type": "state", "ts": now_ms(), **hub.snapshot(),
                "capabilities_ready": {
                    "calibrated": calib.done,
                    "camera_error": (getattr(app.state.source, "last_error", None)
                                     or (spot.last_error if spot else None))}}

    @app.get("/api/history")
    async def get_history(
        from_: int | None = Query(None, alias="from"),
        to: int | None = Query(None, alias="to"),
        kind: str | None = None,           # 本站扩展，协议未定义
        limit: int = 5000,                 # 本站扩展，安全阀
    ):
        """历史查询（`接口协议.md` §4.1，随 v0.1 冻结）。

        ⚠️ `from` 是 Python 保留字，参数只能写作 `from_`。**必须**用
        `Query(alias="from")` 把它对外暴露成 `from` —— FastAPI 按参数名匹配
        查询串，不写 alias 的话协议要求的 `?from=` 会被静默忽略、退回查全量。
        """
        store: Store = app.state.store
        t = to or now_ms()
        f = from_ if from_ is not None else t - HISTORY_MAX_RANGE_MS
        if t - f > HISTORY_MAX_RANGE_MS:
            raise HTTPException(status_code=400, detail="RANGE_TOO_WIDE")
        return {"v": 1, "from": f, "to": t,
                "samples": store.query_snapshots(f, t, kind, limit)}

    @app.post("/api/calibration/reset")
    async def reset_calibration():
        calib.reset()
        rules.baseline_neck_deg = None
        return {"ok": True, "calibrated": False}

    # ---------- 坐姿抽检（2026-11-16 新增，协议未定义 → 属「只增不改」的增）----------
    @app.get("/api/sitting/latest")
    async def sitting_latest():
        """最近一次抽检的结果快照（只读，不触发新抽检）。"""
        spot = getattr(app.state, "spot", None)
        if spot is None:
            return {"v": 1, "enabled": False, "model_ready": False,
                    "camera_ready": False, "result": None,
                    "last_error": "坐姿抽检未启用（config.yaml → sitting.enabled）"}
        return {"v": 1, "enabled": True, **spot.snapshot()}

    @app.get("/api/sitting/history")
    async def sitting_history(
        from_: int | None = Query(None, alias="from"),
        to: int | None = Query(None, alias="to"),
        # 60s 一条 → 一天 1440 条。默认值必须覆盖一天，否则出日报时会被静默截断
        # 成最近 200 条（约 3.3 小时）而调用方看不出少了。
        limit: int = 2000,
    ):
        """按 ts 升序返回历史抽检记录（人机课 M2 报告的数据来源）。

        `truncated=true` 表示被 limit 截断了，报告里必须说明统计窗口。
        """
        store: Store = app.state.store
        t = to or now_ms()
        f = from_ if from_ is not None else t - HISTORY_MAX_RANGE_MS
        if t - f > HISTORY_MAX_RANGE_MS:
            raise HTTPException(status_code=400, detail="RANGE_TOO_WIDE")
        rows = store.query(f, t, "sitting", limit)
        rows.reverse()                      # store 返回倒序，对外统一升序
        return {"v": 1, "from": f, "to": t, "count": len(rows),
                "truncated": len(rows) >= limit, "items": rows}

    @app.post("/api/sitting/check")
    async def sitting_check():
        """手动触发一次抽检（调试/补拍用）。真正的结果稍后从 latest 取。"""
        spot = getattr(app.state, "spot", None)
        if spot is None:
            raise HTTPException(status_code=409, detail="SITTING_DISABLED")
        if not spot.estimator.ok:
            raise HTTPException(status_code=503, detail="MODEL_UNAVAILABLE")
        spot.trigger()
        return {"ok": True, "interval_sec": spot.interval,
                "message": "已触发一次抽检，约 1 秒后查 GET /api/sitting/latest"}

    @app.get("/api/health")
    async def health():
        spot = getattr(app.state, "spot", None)
        return {"ok": True, "version": "0.1.0", "clients": hub.client_count,
                "calibrated": calib.done, "sim": sim,
                # D-016：真实姿态只来自抽检；"sim" 是 --sim 合成数据，None = 没有姿态源
                "pose_source": ("sim" if sim else
                                ("spot_check" if spot is not None and spot.estimator.ok
                                 else None)),
                "sitting": {
                    "enabled": spot is not None,
                    "model_ready": bool(spot and spot.estimator.ok),
                    "rounds": spot.rounds if spot else 0,
                    "interval_sec": spot.interval if spot else None,
                    "last_error": spot.last_error if spot else None,
                }}

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
│  坐姿抽检  GET  /api/sitting/latest          │
│            周期 {getattr(cfg, 'sitting_interval_sec', 60):>3}s（{('启用' if getattr(cfg, 'sitting_enabled', False) else '关闭'):<4}）           │
└──────────────────────────────────────────────┘"""
    print(banner)
    uvicorn.run(app, host=host or cfg.host, port=port or cfg.port,
                log_level="info")
