"""用小栖仓库里**真实的** PhoneIngest / Hub 起一个最小后端，用于联调与验收。

只读引用仓库内 `backend/xiaoqi`（不会修改它）；没有摄像头依赖，
因为只装配手机接入链路。测试脚本 tools/test-integration.py 会拉起本服务、连接 /ws，
再用 App 同一份 SyncClient 上报步数，验证：
  1. 令牌校验、幂等、只前进不回退（真实 PhoneIngest 行为）；
  2. WebSocket 广播 phone 快照（前端 live.js 消费的正是这类帧）；
  3. 请求体 source=android-app、device_id 被真实后端接收。

用法（建议由测试脚本启动）：
  python -B android/tools/real-ingest-server.py --port 8765 --token xiaoqi-test-token
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
REPO_BACKEND = REPO_ROOT / "backend"
XIAOQI_BACKEND = Path(os.environ.get("XIAOQI_BACKEND") or REPO_BACKEND)
if not (XIAOQI_BACKEND / "xiaoqi" / "ingest" / "phone.py").exists():
    raise SystemExit(f"找不到小栖后端：{XIAOQI_BACKEND}")
sys.path.insert(0, str(XIAOQI_BACKEND))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # noqa: E402
import uvicorn  # noqa: E402

from xiaoqi.config import Config  # noqa: E402
from xiaoqi.hub import Hub, now_ms  # noqa: E402
from xiaoqi.ingest.phone import PhoneIngest, build_router  # noqa: E402


def create_app(token: str) -> FastAPI:
    cfg = Config()
    cfg.host = "127.0.0.1"
    cfg.port = 8765
    cfg.token = token
    cfg.dedup_window_sec = 60
    cfg.stale_sec = 900

    hub = Hub()
    phone = PhoneIngest(cfg, hub)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        hub.bind_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(title="小栖 · 手机接入联调后端", version="test",
                  lifespan=lifespan)

    app.include_router(build_router(cfg, hub, phone))

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "version": "test", "clients": hub.client_count}

    @app.get("/api/token")
    async def token_info() -> dict:
        return {"token": cfg.token, "endpoint": "/api/ingest/health",
                "example_header": f"X-Xiaoqi-Token: {cfg.token}"}

    @app.get("/api/state")
    async def state() -> dict:
        return {"v": 1, "type": "state", "ts": now_ms(),
                "phone": phone.snapshot()}

    @app.get("/api/debug")
    async def debug() -> dict:
        """测试专用：暴露 PhoneIngest 内部值，确认 source/device 真的到了。"""
        return {
            "steps": phone.steps,
            "updated_ts": phone.updated_ts,
            "source": phone.source,
            "dedup_keys": list(getattr(phone, "_last_by_device", {}).keys()),
        }

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        await hub.add(ws)
        try:
            await ws.send_json(hub.hello())
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await hub.remove(ws)

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="xiaoqi-test-token")
    args = parser.parse_args()
    app = create_app(args.token)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
