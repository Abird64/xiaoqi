"""独立联调后端的协议测试（标准库，不依赖小栖仓库）。

运行：
  python -B tools/test-dev-server.py
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "tools" / "dev_server.py"
DATA = ROOT / "build" / "demo-test-state.json"
TOKEN = "demo-test-token"
passed = 0
failed = 0

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    line = f"  {'PASS' if condition else 'FAIL'}  {name}"
    if detail and not condition:
        line += f"  ({detail})"
    print(line)
    if condition:
        passed += 1
    else:
        failed += 1


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def call(base: str, path: str, method: str = "GET", body: dict | None = None,
         token: str | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Xiaoqi-Token"] = token
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def main() -> int:
    DATA.parent.mkdir(parents=True, exist_ok=True)
    if DATA.exists():
        DATA.unlink()
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [sys.executable, "-B", str(SERVER), "--port", str(port),
         "--host", "127.0.0.1", "--token", TOKEN, "--data", str(DATA)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                code, body = call(base, "/api/health")
                if code == 200 and json.loads(body).get("ok"):
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError("dev_server 没有启动")

        code, body = call(base, "/")
        check("GET / 返回面板", code == 200 and "手机步数联调面板" in body)
        code, body = call(base, "/api/health")
        check("GET /api/health", code == 200 and json.loads(body)["ok"] is True)
        code, body = call(base, "/api/token")
        check("GET /api/token", code == 200 and json.loads(body)["token"] == TOKEN)

        payload = {"steps": 3210, "ts": int(time.time() * 1000),
                   "source": "android-app", "device_id": "demo-device-1"}
        code, body = call(base, "/api/ingest/health", "POST", payload, TOKEN)
        result = json.loads(body)
        check("首次上报 200", code == 200 and result["ok"] and not result["deduped"], body)
        state = json.loads(call(base, "/api/state")[1])
        check("state 记录 3210", state["phone"]["steps"] == 3210, body)
        check("state 保留来源 android-app", state["source"] == "android-app", body)

        payload["steps"] = 3300
        code, body = call(base, "/api/ingest/health", "POST", payload, TOKEN)
        result = json.loads(body)
        check("同设备 60 秒内上报被 deduped", result["ok"] and result["deduped"], body)
        state = json.loads(call(base, "/api/state")[1])
        check("幂等后仍为 3210", state["phone"]["steps"] == 3210, body)

        payload["device_id"] = "demo-device-2"
        code, body = call(base, "/api/ingest/health", "POST", payload, TOKEN)
        result = json.loads(body)
        check("换设备 3300 被接受", result["ok"] and not result["deduped"], body)
        state = json.loads(call(base, "/api/state")[1])
        check("state 前进到 3300", state["phone"]["steps"] == 3300, body)

        payload = {"steps": 100, "device_id": "demo-device-3", "source": "android-app"}
        call(base, "/api/ingest/health", "POST", payload, TOKEN)
        state = json.loads(call(base, "/api/state")[1])
        check("更小步数视为新的一天/重置", state["phone"]["steps"] == 100, body)

        code, body = call(base, "/api/state")
        state = json.loads(body)
        check("state 带 history", len(state.get("history", [])) >= 3, body)
        code, body = call(base, "/api/history")
        check("history 样本按接口返回", code == 200 and len(json.loads(body)["samples"]) >= 3, body)

        code, body = call(base, "/api/ingest/health", "POST",
                          {"steps": "x"}, TOKEN)
        check("steps 非整数 400", code == 400 and
              json.loads(body)["error"] == "INVALID_FIELD", body)
        code, body = call(base, "/api/ingest/health", "POST",
                          {"steps": 1}, "wrong-token")
        check("错误令牌 401", code == 401 and
              json.loads(body)["error"] == "BAD_TOKEN", body)

        code, body = call(base, "/api/reset", "POST", {}, TOKEN)
        check("reset 200", code == 200, body)
        state = json.loads(call(base, "/api/state")[1])
        check("reset 后 steps=null（无数据不补 0）", state["phone"]["steps"] is None, body)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        if DATA.exists():
            DATA.unlink()

    print()
    print("=" * 42)
    print(f"DevServerTest: {passed} passed, {failed} failed")
    print("=" * 42)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
