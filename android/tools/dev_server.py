"""小栖步数 · 独立联调后端 + 网页面板（仅用 Python 标准库）。

真实小栖后端带摄像头/MediaPipe 依赖；如果只想验证“手机 App → HTTP → 网页端”
这条链路，可以先用本脚本起一个零依赖的替身：

    python tools/dev_server.py --port 8765 --token xiaoqi-demo

然后手机 App 设置里填：
    电脑地址  http://<电脑局域网 IP>:8765
    配对令牌  xiaoqi-demo

它严格复刻协议 §4 的响应码/幂等/只前进不回退，并提供：
    GET  /                  联调面板（步数、同步时间、来源、历史）
    GET  /api/state         当前 phone 快照
    GET  /api/token         令牌
    GET  /api/health        健康检查
    POST /api/ingest/health 手机上报
    GET  /api/history       历史样本
    POST /api/reset         清空演示数据（需要令牌）

注意：这是开发联调面板，不是小栖的 3D 房间前端；真实前端消费的是同一个
后端的 WebSocket phone 帧，字段与本面板完全一致。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "build" / "demo-state.json"


def now_ms() -> int:
    return int(time.time() * 1000)


class DemoState:
    def __init__(self, token: str, data_file: Path) -> None:
        self.token = token
        self.data_file = data_file
        self.steps: int | None = None
        self.updated_ts: int | None = None
        self.source: str | None = None
        self.device_id: str | None = None
        self.day: str | None = None
        self.history: list[dict] = []
        self._last_by_device: dict[str, float] = {}
        self._load()

    # ---------- 持久化 ----------
    def _load(self) -> None:
        if not self.data_file.exists():
            return
        try:
            raw = json.loads(self.data_file.read_text(encoding="utf-8"))
            self.steps = raw.get("steps")
            self.updated_ts = raw.get("updated_ts")
            self.source = raw.get("source")
            self.device_id = raw.get("device_id")
            self.day = raw.get("day")
            self.history = list(raw.get("history") or [])[-200:]
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "steps": self.steps,
            "updated_ts": self.updated_ts,
            "source": self.source,
            "device_id": self.device_id,
            "day": self.day,
            "history": self.history[-200:],
        }
        tmp = self.data_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.data_file)

    # ---------- 协议 ----------
    def stale(self) -> bool:
        if self.updated_ts is None:
            return True
        return (now_ms() - self.updated_ts) / 1000.0 > 900

    def snapshot(self) -> dict:
        return {
            "steps": self.steps,
            "updated_ts": self.updated_ts,
            "stale": self.stale(),
        }

    def accept(self, steps: int, ts: int | None, source: str | None,
               device_id: str | None, client_ip: str) -> dict:
        # 1) 60 秒幂等
        key = device_id or client_ip or "unknown"
        mono = time.monotonic()
        last = self._last_by_device.get(key)
        if last is not None and (mono - last) < 60:
            return {"ok": True, "deduped": True}
        self._last_by_device[key] = mono

        effective_ts = ts or now_ms()
        day = date.fromtimestamp(effective_ts / 1000).isoformat()
        # 2) 只前进不回退：跨零点/系统重置 → 开新记录
        if self.steps is None or self.day != day or steps < self.steps:
            self.steps = steps
        else:
            self.steps = max(self.steps, steps)
        self.day = day
        self.updated_ts = effective_ts
        self.source = source
        self.device_id = device_id
        self.history.append({
            "ts": effective_ts,
            "steps": self.steps,
            "source": source,
            "device_id": device_id,
        })
        self.history = self.history[-200:]
        self._save()
        return {"ok": True, "deduped": False}

    def reset(self) -> None:
        self.steps = None
        self.updated_ts = None
        self.source = None
        self.device_id = None
        self.day = None
        self.history = []
        self._last_by_device = {}
        self._save()


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f1318">
<title>小栖 · 手机同步联调面板</title>
<style>
  :root {
    --bg:#0f1318; --card:#1a212a; --card2:#202a35; --line:#2a3542;
    --text:#f1f5f7; --dim:#93a0ae; --dim2:#6c7987;
    --green:#8bd97b; --green2:#5fa85a; --amber:#e0a458; --red:#e2726a;
    --radius:24px;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; padding:26px 18px 48px; background:
      radial-gradient(900px 500px at 85% -10%, rgba(139,217,123,.10), transparent 60%),
      radial-gradient(700px 400px at 0% 0%, rgba(127,178,229,.08), transparent 55%),
      var(--bg);
    color:var(--text); min-height:100vh;
    font:15px/1.6 -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
  }
  .wrap { max-width:980px; margin:0 auto; }
  header { display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin-bottom:22px; }
  .brand { font-size:13px; letter-spacing:.28em; color:var(--dim); text-transform:uppercase; }
  h1 { margin:6px 0 4px; font-size:30px; letter-spacing:.01em; font-weight:700; }
  .sub { margin:0; color:var(--dim); font-size:13px; }
  .live { display:inline-flex; align-items:center; gap:8px; padding:8px 14px; border-radius:999px;
    background:rgba(139,217,123,.10); color:var(--green); font-size:13px; font-weight:600;
    border:1px solid rgba(139,217,123,.22); white-space:nowrap; }
  .live.off { background:rgba(226,114,106,.10); color:var(--red); border-color:rgba(226,114,106,.25); }
  .dot { width:8px; height:8px; border-radius:50%; background:currentColor; box-shadow:0 0 12px currentColor; }
  .grid { display:grid; grid-template-columns: minmax(0,1.15fr) minmax(0,.85fr); gap:16px; }
  @media (max-width: 760px) { .grid { grid-template-columns:1fr; } header { align-items:flex-start; flex-direction:column; } }
  .card { background:linear-gradient(160deg, rgba(32,42,53,.92), rgba(23,30,38,.96));
    border:1px solid var(--line); border-radius:var(--radius); padding:22px; }
  .hero { display:flex; flex-direction:column; align-items:center; padding:26px 22px 22px; }
  .ring { --p:0; width:236px; height:236px; border-radius:50%; position:relative;
    background:conic-gradient(from 135deg, var(--green) 0 calc(var(--p) * 1%), #27313d 0 75%, transparent 75%);
    filter:drop-shadow(0 0 22px rgba(139,217,123,.18)); }
  .ring::after { content:""; position:absolute; inset:14px; border-radius:50%; background:var(--card); }
  .ring .center { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center;
    justify-content:center; z-index:2; }
  .ring .label { font-size:12px; letter-spacing:.22em; color:var(--dim); }
  .ring .num { font-size:56px; line-height:1.05; font-weight:300; letter-spacing:-.02em;
    font-variant-numeric:tabular-nums; margin-top:4px; }
  .ring .num.empty { color:var(--dim2); font-size:24px; font-weight:500; }
  .ring .unit { font-size:12px; color:var(--dim); margin-top:2px; }
  .goal { margin-top:14px; color:var(--dim); font-size:13px; }
  .goal b { color:var(--text); }
  .status { margin-top:12px; }
  .pill { display:inline-flex; align-items:center; gap:7px; padding:6px 12px; border-radius:999px;
    font-size:12px; font-weight:600; }
  .pill.ok { background:rgba(139,217,123,.12); color:var(--green); }
  .pill.warn { background:rgba(224,164,88,.12); color:var(--amber); }
  .pill.bad { background:rgba(226,114,106,.12); color:var(--red); }
  .pill.idle { background:rgba(147,160,174,.10); color:var(--dim); }
  h2 { margin:0 0 14px; font-size:12px; letter-spacing:.16em; color:var(--dim); font-weight:700; }
  .rows { display:flex; flex-direction:column; gap:10px; }
  .row { display:flex; justify-content:space-between; gap:14px; font-size:13px; }
  .row .k { color:var(--dim); flex:0 0 auto; }
  .row .v { text-align:right; overflow-wrap:anywhere; font-variant-numeric:tabular-nums; }
  .mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size:12px; }
  .ok { color:var(--green); } .warn { color:var(--amber); } .bad { color:var(--red); } .dim { color:var(--dim2); }
  .chart { display:flex; align-items:flex-end; gap:4px; height:86px; margin-top:6px;
    padding-top:8px; border-top:1px dashed var(--line); }
  .bar { flex:1; min-width:3px; border-radius:4px 4px 2px 2px;
    background:linear-gradient(180deg, var(--green), var(--green2)); opacity:.85; }
  .bar.wait { background:var(--line); opacity:.5; }
  .chart-empty { color:var(--dim2); font-size:12px; margin-top:10px; }
  .help { margin-top:16px; font-size:12px; color:var(--dim); line-height:1.75; }
  .help code { background:#11161c; border:1px solid var(--line); border-radius:7px;
    padding:2px 6px; color:var(--green); font-family:ui-monospace, Consolas, monospace; }
  .actions { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; }
  button { border:1px solid var(--line); background:var(--card2); color:var(--text);
    border-radius:12px; padding:10px 14px; font-size:13px; cursor:pointer; }
  button:hover { border-color:#3b4a5a; }
  button.primary { background:var(--green); border-color:var(--green); color:#0e1a10; font-weight:700; }
  footer { margin-top:26px; color:var(--dim2); font-size:11px; text-align:center; line-height:1.9; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <div class="brand">XIAOQI · PHONE SYNC</div>
      <h1>手机步数联调面板</h1>
      <p class="sub">手机 App → <code>POST /api/ingest/health</code> → 当前快照。真实房间前端消费的是同一份 WebSocket phone 帧。</p>
    </div>
    <div class="live" id="live"><span class="dot"></span><span id="liveText">连接中</span></div>
  </header>

  <div class="grid">
    <section class="card hero">
      <div class="ring" id="ring">
        <div class="center">
          <div class="label">今日步数</div>
          <div class="num empty" id="steps">无数据</div>
          <div class="unit" id="unit">等待手机同步</div>
        </div>
      </div>
      <div class="goal" id="goal">目标 8,000 步 · 0%</div>
      <div class="status"><span class="pill idle" id="syncPill">● 等待首次上报</span></div>
    </section>

    <section class="card">
      <h2>同步状态</h2>
      <div class="rows">
        <div class="row"><span class="k">最后更新</span><span class="v" id="age">—</span></div>
        <div class="row"><span class="k">服务端记录</span><span class="v" id="serverSteps">—</span></div>
        <div class="row"><span class="k">来源</span><span class="v mono" id="source">—</span></div>
        <div class="row"><span class="k">设备</span><span class="v mono" id="device">—</span></div>
        <div class="row"><span class="k">数据新鲜度</span><span class="v" id="fresh">—</span></div>
      </div>
      <div class="chart" id="chart"></div>
      <div class="chart-empty" id="chartEmpty">还没有收到上报。配置好手机 App 后，这里会出现每次同步的步数。</div>
      <div class="actions">
        <button class="primary" onclick="refresh()">立即刷新</button>
        <button onclick="copyToken()">复制令牌</button>
        <button onclick="resetData()">清空演示数据</button>
      </div>
      <div class="help">
        手机地址：<code id="baseUrl">__BASE__</code><br>
        配对令牌：<code id="token">__TOKEN__</code><br>
        电脑与手机需同一 Wi-Fi；Windows 防火墙需放行端口 <code>__PORT__</code>。
      </div>
    </section>
  </div>

  <footer>
    小栖 · 手机同步联调面板 · 仅局域网使用<br>
    这不是 3D 房间前端；它用于在没有摄像头/MediaPipe 环境时验证手机上报链路。
  </footer>
</div>
<script>
const TOKEN = "__TOKEN__";
let last = null;

function fmt(n) { return n === null || n === undefined ? "—" : Number(n).toLocaleString("zh-CN"); }
function age(ms) {
  if (ms === null || ms === undefined) return "—";
  const s = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (s < 60) return "刚刚";
  if (s < 3600) return Math.round(s / 60) + " 分钟前";
  if (s < 86400) return Math.round(s / 3600) + " 小时前";
  return Math.round(s / 86400) + " 天前";
}
function setPill(text, cls) {
  const el = document.getElementById("syncPill");
  el.textContent = text;
  el.className = "pill " + cls;
}
async function refresh() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const p = data.phone || {};
    last = p;
    const has = typeof p.steps === "number";
    const steps = document.getElementById("steps");
    if (has) {
      steps.textContent = fmt(p.steps);
      steps.classList.remove("empty");
      document.getElementById("unit").textContent = "步 · 今日累计";
      const pct = Math.min(100, Math.round(p.steps * 100 / 8000));
      document.getElementById("ring").style.setProperty("--p", pct);
      document.getElementById("goal").innerHTML = "目标 <b>8,000</b> 步 · " + pct + "%";
    } else {
      steps.textContent = "无数据";
      steps.classList.add("empty");
      document.getElementById("unit").textContent = "等待手机同步";
      document.getElementById("ring").style.setProperty("--p", 0);
      document.getElementById("goal").textContent = "目标 8,000 步 · 0%";
    }
    document.getElementById("serverSteps").textContent = has ? fmt(p.steps) + " 步" : "—";
    document.getElementById("source").textContent = data.source || "—";
    document.getElementById("device").textContent = data.device_id || "—";
    document.getElementById("age").textContent = age(p.updated_ts);
    const fresh = document.getElementById("fresh");
    if (!has) {
      fresh.textContent = "等待数据"; fresh.className = "v dim";
      setPill("● 等待首次上报", "idle");
    } else if (p.stale) {
      fresh.textContent = "超过 15 分钟未更新"; fresh.className = "v warn";
      setPill("● 待同步 · " + age(p.updated_ts), "warn");
    } else {
      fresh.textContent = "新鲜"; fresh.className = "v ok";
      setPill("● 已同步 · " + age(p.updated_ts), "ok");
    }
    document.getElementById("live").classList.remove("off");
    document.getElementById("liveText").textContent = "后端在线";
    drawChart(data.history || []);
  } catch (e) {
    document.getElementById("live").classList.add("off");
    document.getElementById("liveText").textContent = "后端断开";
    setPill("● 连接中断", "bad");
  }
}
function drawChart(history) {
  const chart = document.getElementById("chart");
  const empty = document.getElementById("chartEmpty");
  if (!history.length) { chart.innerHTML = ""; empty.style.display = "block"; return; }
  empty.style.display = "none";
  const recent = history.slice(-32);
  const max = Math.max(1, ...recent.map(x => x.steps || 0));
  chart.innerHTML = recent.map(x => {
    const h = Math.max(4, Math.round((x.steps || 0) * 80 / max));
    return '<div class="bar" style="height:' + h + 'px" title="' + fmt(x.steps) + ' 步 · ' + new Date(x.ts).toLocaleTimeString() + '"></div>';
  }).join("");
}
function copyToken() {
  navigator.clipboard?.writeText(TOKEN).then(
    () => alert("令牌已复制"),
    () => prompt("复制令牌", TOKEN)
  );
}
async function resetData() {
  if (!confirm("清空演示数据？手机端配置不会被修改。")) return;
  await fetch("/api/reset", { method: "POST", headers: { "X-Xiaoqi-Token": TOKEN } });
  refresh();
}
refresh();
setInterval(refresh, 3000);
setInterval(() => {
  if (last && typeof last.steps === "number") {
    document.getElementById("age").textContent = age(last.updated_ts);
  }
}, 1000);
</script>
</body>
</html>
"""


def make_handler(state: DemoState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "XiaoqiDemo/1.0"

        def log_message(self, fmt: str, *args) -> None:
            print(f"[{self.log_date_time_string()}] {fmt % args}")

        # ---------- 工具 ----------
        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict) -> None:
            self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def _authorized(self) -> bool:
            return self.headers.get("X-Xiaoqi-Token") == state.token

        # ---------- 路由 ----------
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                html = (HTML.replace("__TOKEN__", state.token)
                        .replace("__BASE__", f"http://{self.headers.get('Host', '127.0.0.1')}")
                        .replace("__PORT__", str(self.server.server_address[1])))
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/health":
                self._json(200, {"ok": True, "version": "1.0.0-demo", "clients": 0, "sim": True})
                return
            if parsed.path == "/api/token":
                self._json(200, {"token": state.token, "endpoint": "/api/ingest/health",
                                 "example_header": f"X-Xiaoqi-Token: {state.token}"})
                return
            if parsed.path == "/api/state":
                self._json(200, {
                    "v": 1, "type": "state", "ts": now_ms(),
                    "phone": state.snapshot(),
                    "source": state.source,
                    "device_id": state.device_id,
                    "day": state.day,
                    "history": state.history[-64:],
                })
                return
            if parsed.path == "/api/history":
                query = parse_qs(parsed.query)
                try:
                    end = int(query.get("to", [str(now_ms())])[0])
                    start = int(query.get(
                        "from", [str(end - 7 * 24 * 3600 * 1000)])[0])
                except ValueError:
                    self._json(400, {"ok": False, "error": "INVALID_FIELD", "field": "from"})
                    return
                if end - start > 7 * 24 * 3600 * 1000:
                    self._json(400, {"ok": False, "error": "RANGE_TOO_WIDE"})
                    return
                samples = [x for x in state.history if start <= x["ts"] <= end]
                self._json(200, {"v": 1, "from": start, "to": end, "samples": samples})
                return
            self._json(404, {"ok": False, "error": "NOT_FOUND"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in ("/api/reset", "/api/ingest/health"):
                self._json(404, {"ok": False, "error": "NOT_FOUND"})
                return

            # 先把请求体读完，再判令牌：否则 401 时未读的 body 会污染 keep-alive 连接。
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b""
            if not self._authorized():
                self._json(401, {"ok": False, "error": "BAD_TOKEN"})
                return

            if parsed.path == "/api/reset":
                state.reset()
                self._json(200, {"ok": True})
                return

            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"ok": False, "error": "INVALID_FIELD", "field": "body"})
                return
            steps = body.get("steps")
            if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
                self._json(400, {"ok": False, "error": "INVALID_FIELD", "field": "steps"})
                return
            ts = body.get("ts")
            if ts is not None and not isinstance(ts, int):
                self._json(400, {"ok": False, "error": "INVALID_FIELD", "field": "ts"})
                return
            client_ip = self.client_address[0] if self.client_address else ""
            result = state.accept(steps, ts, body.get("source"),
                                  body.get("device_id"), client_ip)
            self._json(200, result)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Xiaoqi-Token")
            self.end_headers()

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="小栖步数 · 独立联调后端")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="xiaoqi-demo")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    state = DemoState(args.token, Path(args.data))
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print("小栖步数 · 联调后端已启动")
    print(f"  面板    http://127.0.0.1:{args.port}/")
    print(f"  局域网  http://<本机 IP>:{args.port}/")
    print(f"  令牌    {args.token}")
    print(f"  数据    {args.data}")
    print("  Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
