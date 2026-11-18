"""端到端联调测试：

  App 的 SyncClient（Java，真源码）
        → 小栖真实的 PhoneIngest / Hub（只读 import）
        → WebSocket 广播 phone 快照

不使用 mock 协议：HTTP 路由、令牌校验、60 秒幂等、只前进不回退都走
仓库内 `backend/xiaoqi/ingest/phone.py` 的真实实现（可用 `XIAOQI_BACKEND` 覆盖）。

运行：
  python -B android/tools/test-integration.py
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                    # android/
REPO_ROOT = ROOT.parent               # 仓库根目录
BUILD = ROOT / "build" / "integration"
CLASSES = BUILD / "classes"
SERVER = HERE / "real-ingest-server.py"
TOKEN = "xiaoqi-test-token"


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _find_python() -> Path:
    from_env = os.environ.get("XIAOQI_PY")
    if from_env and Path(from_env).exists():
        return Path(from_env)
    found = _first_existing([
        REPO_ROOT / "backend" / ".venv" / "Scripts" / "python.exe",
        REPO_ROOT / "backend" / ".venv" / "bin" / "python",
    ])
    if found:
        return found
    for name in ("python", "python3"):
        exe = shutil.which(name)
        if exe:
            return Path(exe)
    return Path(sys.executable)


def _find_java_home() -> Path:
    from_env = os.environ.get("JAVA_HOME")
    candidates: list[Path] = []
    if from_env:
        candidates.append(Path(from_env))
    candidates.extend([
        Path(r"C:\Program Files\Java\jdk-17"),
        Path(r"C:\Program Files\Java\jdk-21"),
        Path(r"C:\Program Files\Android\Android Studio\jbr"),
    ])
    for candidate in candidates:
        javac_exe = candidate / "bin" / "javac.exe"
        javac_bin = candidate / "bin" / "javac"
        if (candidate / "release").exists() and (javac_exe.exists() or javac_bin.exists()):
            return candidate
    javac = shutil.which("javac")
    if javac:
        # 解析 symlink/包装脚本；Windows 的 javapath 包装器不是 JDK home。
        home = Path(javac).resolve().parent.parent
        if (home / "release").exists():
            return home
    return Path(r"C:\Program Files\Java\jdk-17")


XIAOQI_BACKEND = Path(
    os.environ.get("XIAOQI_BACKEND")
    or _first_existing([REPO_ROOT / "backend"])
    or (REPO_ROOT / "backend")
)
PY = _find_python()
JAVA_HOME = _find_java_home()
JAVA_NAME = "java.exe" if os.name == "nt" else "java"
JAVAC_NAME = "javac.exe" if os.name == "nt" else "javac"
JAVA = JAVA_HOME / "bin" / JAVA_NAME
JAVAC = JAVA_HOME / "bin" / JAVAC_NAME

passed = 0
failed = 0
log_lines: list[str] = []

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    line = f"  {'PASS' if condition else 'FAIL'}  {name}"
    if detail and not condition:
        line += f"  ({detail})"
    print(line)
    log_lines.append(line)
    if condition:
        passed += 1
    else:
        failed += 1


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(base: str, path: str, method: str = "GET",
              body: dict | None = None, token: str | None = None,
              timeout: float = 5.0) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Xiaoqi-Token"] = token
    request = urllib.request.Request(base + path, data=data,
                                     headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, {"raw": raw}


def wait_health(base: str, timeout: float = 25.0) -> dict:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            code, body = http_json(base, "/api/health", timeout=2)
            if code == 200 and body.get("ok"):
                return body
            last = f"HTTP {code}: {body}"
        except Exception as error:  # noqa: BLE001
            last = f"{type(error).__name__}: {error}"
        time.sleep(0.25)
    raise RuntimeError(f"后端没有起来：{last}")


def compile_harness() -> None:
    CLASSES.mkdir(parents=True, exist_ok=True)
    sources = sorted((ROOT / "app/src/main/java/com/xiaoqi/steps/core").glob("*.java"))
    sources.append(ROOT / "app/src/test/java/com/xiaoqi/steps/core/SyncHarness.java")
    command = [str(JAVAC), "--release", "11", "-encoding", "UTF-8",
               "-d", str(CLASSES)] + [str(source) for source in sources]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit("SyncHarness 编译失败")


def java_harness(*args: str, timeout: float = 20.0) -> tuple[int, str]:
    command = [str(JAVA), "-cp", str(CLASSES),
               "com.xiaoqi.steps.core.SyncHarness", *args]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    output = (result.stdout + result.stderr).strip()
    print(f"    java> {output}")
    log_lines.append(f"    java> {output}")
    return result.returncode, output


def push(base: str, steps: int, device: str,
         token: str = TOKEN) -> tuple[int, str]:
    return java_harness("push", base, token, str(steps), device)


async def websocket_scenario(base: str) -> None:
    import websockets

    ws_url = base.replace("http://", "ws://") + "/ws"
    async with websockets.connect(ws_url, open_timeout=8) as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        check("WS 首帧 type=hello", hello.get("type") == "hello", str(hello)[:200])
        check("WS hello 声明 phone 能力",
              "phone" in hello.get("server", {}).get("capabilities", []),
              str(hello.get("server")))

        code, output = await asyncio.to_thread(push, base, 1234, "android-int-ws")
        check("SyncClient 上报 1234 成功", code == 0, output)

        phone = None
        deadline = time.time() + 6
        while time.time() < deadline:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if message.get("type") == "state" and "phone" in message:
                phone = message["phone"]
                break
        check("WS 收到 phone 增帧", phone is not None, "6 秒内没有 state.phone")
        if phone is not None:
            check("WS phone.steps=1234", phone.get("steps") == 1234, str(phone))
            check("WS phone.stale=false", phone.get("stale") is False, str(phone))
            check("WS phone.updated_ts 是毫秒",
                  isinstance(phone.get("updated_ts"), int)
                  and phone["updated_ts"] > 1_700_000_000_000, str(phone))


def main() -> int:
    if not (XIAOQI_BACKEND / "xiaoqi" / "ingest" / "phone.py").exists():
        print(f"找不到小栖后端：{XIAOQI_BACKEND}")
        print("可设置 XIAOQI_BACKEND 指向仓库的 backend/ 目录。")
        return 2
    if not PY.exists():
        print(f"找不到可用的 Python：{PY}")
        print("可设置 XIAOQI_PY 指向 backend/.venv 的 python。")
        return 2
    if not JAVA.exists() or not JAVAC.exists():
        print(f"找不到 JDK：{JAVA_HOME}")
        print("可设置 JAVA_HOME 指向 JDK 17+。")
        return 2
    compile_harness()

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    BUILD.mkdir(parents=True, exist_ok=True)
    server_log = BUILD / "server.log"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["XIAOQI_BACKEND"] = str(XIAOQI_BACKEND)
    handle = server_log.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [str(PY), "-B", str(SERVER), "--port", str(port), "--token", TOKEN],
        stdout=handle, stderr=subprocess.STDOUT, env=env)
    try:
        wait_health(base)
        print(f"真实 PhoneIngest 后端已启动：{base}")
        log_lines.append(f"后端：{base}")

        code, body = http_json(base, "/api/health")
        check("GET /api/health", code == 200 and body.get("ok") is True, str(body))
        code, body = http_json(base, "/api/token")
        check("GET /api/token", code == 200 and body.get("token") == TOKEN, str(body))

        asyncio.run(websocket_scenario(base))

        # 同一 device 60 秒内重复上报 → 真实 PhoneIngest 幂等
        code, output = push(base, 1300, "android-int-ws")
        check("60 秒内同设备重复上报返回 ok", code == 0, output)
        check("重复上报被标记 deduped=true", "DEDUPED=true" in output, output)
        code, state = http_json(base, "/api/state")
        check("幂等丢弃后服务端仍为 1234",
              state.get("phone", {}).get("steps") == 1234, str(state.get("phone")))

        # 换设备立刻上报 → 接受，验证只前进/取最大值
        code, output = push(base, 1500, "android-int-second")
        check("不同设备上报 1500 成功", code == 0 and "DEDUPED=false" in output, output)
        code, state = http_json(base, "/api/state")
        check("服务端 steps=1500", state.get("phone", {}).get("steps") == 1500,
              str(state.get("phone")))

        code, debug = http_json(base, "/api/debug")
        check("真实后端的 source=android-app", debug.get("source") == "android-app",
              str(debug))
        check("device_id 进入真实后端去重表",
              "android-int-second" in debug.get("dedup_keys", []), str(debug))

        # 错误令牌
        code, output = push(base, 1600, "android-int-bad", token="wrong-token")
        check("错误令牌 exit=1", code == 1, output)
        check("错误令牌 HTTP=401 BAD_TOKEN",
              "HTTP=401" in output and "BAD_TOKEN" in output, output)

        # 字段校验（只验证后端契约，不是 App 行为）
        code, body = http_json(base, "/api/ingest/health", method="POST",
                               body={"steps": "not-a-number"}, token=TOKEN)
        check("steps 非整数 → 400 INVALID_FIELD",
              code == 400 and body.get("error") == "INVALID_FIELD", str(body))

        # 只前进不回退：更小值被视为跨零点/系统重置，开新记录
        code, output = push(base, 50, "android-int-newday")
        check("更小步数被视为新的一天并接受", code == 0, output)
        code, state = http_json(base, "/api/state")
        check("服务端 steps=50", state.get("phone", {}).get("steps") == 50,
              str(state.get("phone")))

        # App 侧的探测函数也过一遍
        code, output = java_harness("token", base)
        check("SyncClient.fetchToken", code == 0 and f"TOKEN={TOKEN}" in output, output)
        code, output = java_harness("health", base)
        check("SyncClient.health", code == 0 and "VERSION=test" in output, output)
        code, output = java_harness("state", base)
        check("SyncClient.fetchState", code == 0 and "STEPS=50" in output, output)
    finally:
        handle.close()
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
        print()
        print("后端日志：", server_log)
        try:
            tail = server_log.read_text(encoding="utf-8", errors="replace").strip()
            if tail:
                print(tail[-2000:])
        except OSError:
            pass

    print()
    print("=" * 46)
    print(f"IntegrationTest: {passed} passed, {failed} failed")
    print("=" * 46)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
