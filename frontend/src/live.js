/**
 * 数据链客户端 —— 后端 WS `/ws` 的浏览器端接入（XQ-006）。
 * owner: A（张鹏）｜XQ-006 手机步数同步（电脑端呈现）
 *
 * 为什么要单独一层：main.js 只关心「快照/增量/提醒」三件事，重连、心跳看门狗、
 * 帧解析这些线缆逻辑塞进入口文件会和镜头/HUD 的装配代码搅在一起。
 *
 * 协议（docs/02-需求与设计/接口协议.md §3）：
 *   - 连上后首帧必然是 hello（全量快照，含 phone）；之后 state 只带变化字段
 *   - 服务端每 10s 发 {"type":"ping"}；客户端连续无消息视为断线，需自动重连
 *   - 重连间隔 2s 起、逐次翻倍、最长 30s
 *
 * 与协议的偏差（有意）：看门狗取 15s 而不是 10s。后端心跳就是 10s 一拍，
 * 卡在 10s 会因网络抖动刚好错拍而把健康连接判死，屏幕上表现为步数卡反复「连接中断」。
 * 15s = 1.5 个心跳周期：真断线最多晚 5s 发现，误判概率降到可忽略。
 *
 * 可测性：WebSocket 与定时器都可注入，node --test 里用假 WS + 假时钟跑重连/看门狗。
 */

/** 一次连接都没建立时，多久后判定失败（浏览器 WS 握手本身有 30s 超时，这里只兜 onerror 不回调） */
export const DEFAULT_SILENCE_MS = 15_000;
export const DEFAULT_RECONNECT_MIN_MS = 2_000;
export const DEFAULT_RECONNECT_MAX_MS = 30_000;

/**
 * @param {object} opts
 * @param {string} opts.url                     ws:// 或 wss:// 地址
 * @param {any}    [opts.WebSocketImpl]         注入用；默认 globalThis.WebSocket
 * @param {() => number} [opts.now]             注入用假时钟
 * @param {(fn: Function, ms: number) => any} [opts.setTimeoutImpl]
 * @param {(id: any) => void} [opts.clearTimeoutImpl]
 * @param {number} [opts.silenceMs]
 * @param {number} [opts.reconnectMinMs]
 * @param {number} [opts.reconnectMaxMs]
 * @param {(status: 'connecting'|'open'|'closed', detail?: object) => void} [opts.onStatus]
 * @param {(msg: any) => void} [opts.onHello]
 * @param {(msg: any) => void} [opts.onState]
 * @param {(msg: any) => void} [opts.onReminder]
 * @param {(err: any) => void} [opts.onError]
 */
export function createLive({
  url,
  WebSocketImpl = globalThis.WebSocket,
  now = () => Date.now(),
  setTimeoutImpl,
  clearTimeoutImpl,
  silenceMs = DEFAULT_SILENCE_MS,
  reconnectMinMs = DEFAULT_RECONNECT_MIN_MS,
  reconnectMaxMs = DEFAULT_RECONNECT_MAX_MS,
  onStatus = () => {},
  onHello = () => {},
  onState = () => {},
  onReminder = () => {},
  onError = () => {},
} = {}) {
  const later = setTimeoutImpl || ((fn, ms) => setTimeout(fn, ms));
  const cancel = clearTimeoutImpl || ((id) => clearTimeout(id));

  let socket = null;
  let stopped = false;
  let live = false; // 当前这条连接是否已 open
  let lastMsgAt = 0;
  let attempt = 0;
  let retryTimer = 0;
  let watchTimer = 0;

  function setStatus(status, detail) {
    onStatus(status, detail);
  }

  function clearWatch() {
    if (watchTimer) {
      cancel(watchTimer);
      watchTimer = 0;
    }
  }

  /**
   * 看门狗：不按固定周期轮询，而是「睡到 silenceMs - 已静默时长」再醒，
   * 每次收帧只会重置一个时间戳，不会额外排定时器。
   */
  function armWatch() {
    clearWatch();
    if (stopped || !socket) return;
    const idle = now() - lastMsgAt;
    const rest = silenceMs - idle;
    if (rest <= 0) {
      // 连续无消息 → 主动断，交给 close 分支重连
      drop('silence');
      return;
    }
    watchTimer = later(() => {
      watchTimer = 0;
      armWatch();
    }, Math.max(50, rest));
  }

  /** 拆掉当前连接并排下一次重连；reason 只进 onStatus 便于排查 */
  function drop(reason) {
    clearWatch();
    const ws = socket;
    socket = null;
    live = false;
    if (ws) {
      // 先摘回调：close() 触发的 onclose 不应再走一遍 teardown
      ws.onopen = null;
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
      try {
        ws.close();
      } catch {
        /* 已关闭 */
      }
    }
    setStatus('closed', { reason });
    scheduleRetry();
  }

  function scheduleRetry() {
    if (stopped || retryTimer) return;
    const delay = Math.min(reconnectMaxMs, reconnectMinMs * 2 ** attempt);
    attempt += 1;
    setStatus('connecting', { retryInMs: delay, attempt });
    retryTimer = later(() => {
      retryTimer = 0;
      connect();
    }, delay);
  }

  function handleFrame(raw) {
    lastMsgAt = now();
    let msg;
    try {
      msg = JSON.parse(typeof raw === 'string' ? raw : raw?.data);
    } catch {
      onError(new Error('WS 帧不是合法 JSON'));
      return;
    }
    if (!msg || typeof msg !== 'object') {
      onError(new Error('WS 帧不是对象'));
      return;
    }
    switch (msg.type) {
      case 'hello':
        onHello(msg);
        break;
      case 'state':
        onState(msg);
        break;
      case 'reminder':
        onReminder(msg);
        break;
      case 'error':
        onError(msg);
        break;
      case 'ping':
        break; // 心跳只用来刷新 lastMsgAt
      default:
        break; // 未知类型（协议向后兼容）：忽略，不打断连接
    }
  }

  function connect() {
    if (stopped) return;
    if (!WebSocketImpl) {
      onError(new Error('当前环境没有 WebSocket'));
      return;
    }
    let ws;
    try {
      ws = new WebSocketImpl(url);
    } catch (err) {
      onError(err);
      setStatus('closed', { reason: 'construct' });
      scheduleRetry();
      return;
    }
    socket = ws;
    lastMsgAt = now();

    ws.onopen = () => {
      if (socket !== ws) return;
      live = true;
      attempt = 0; // 连上就回到 2s 起步
      setStatus('open');
      armWatch();
    };
    ws.onmessage = (ev) => {
      if (socket !== ws) return;
      handleFrame(ev);
      armWatch();
    };
    ws.onerror = (err) => {
      if (socket !== ws) return;
      onError(err);
    };
    ws.onclose = (ev) => {
      if (socket !== ws) return;
      drop(ev?.code === 1000 ? 'closed' : 'remote');
    };
  }

  connect();

  return {
    get url() {
      return url;
    },
    get connected() {
      return live;
    },
    /** 页面卸载 / 关倍率时停掉：清掉重连与看门狗，避免后台无限重连 */
    close() {
      stopped = true;
      if (retryTimer) {
        cancel(retryTimer);
        retryTimer = 0;
      }
      clearWatch();
      const ws = socket;
      socket = null;
      live = false;
      if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onclose = null;
        ws.onerror = null;
        try {
          ws.close();
        } catch {
          /* 已关闭 */
        }
      }
      setStatus('closed', { reason: 'client' });
    },
  };
}
