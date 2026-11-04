/**
 * live.js 单测 —— 用假 WebSocket + 假时钟验重连曲线、心跳看门狗与帧分发。
 * 跑法：cd frontend && node --test test/
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { createLive } from '../src/live.js';

/** 最小 WebSocket 替身：手动触发 open/message/close */
class FakeWS {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.closed = false;
    this.readyState = 0;
    FakeWS.instances.push(this);
  }

  open() {
    this.readyState = 1;
    this.onopen?.({});
  }

  send(frame) {
    this.onmessage?.({ data: typeof frame === 'string' ? frame : JSON.stringify(frame) });
  }

  close() {
    this.readyState = 3;
    this.closed = true;
    this.onclose?.({ code: 1000 });
  }

  /** 服务端/网络侧意外断开 */
  drop(code = 1006) {
    this.readyState = 3;
    this.closed = true;
    this.onclose?.({ code });
  }
}

/** 假时钟：advance 会按时间顺序执行到期的定时器 */
function makeClock() {
  let t = 0;
  let seq = 0;
  let timers = [];
  return {
    now: () => t,
    setTimeout: (fn, ms) => {
      seq += 1;
      timers.push({ id: seq, at: t + ms, fn });
      return seq;
    },
    clearTimeout: (id) => {
      timers = timers.filter((x) => x.id !== id);
    },
    advance(ms) {
      const target = t + ms;
      for (;;) {
        timers.sort((a, b) => a.at - b.at || a.id - b.id);
        const next = timers[0];
        if (!next || next.at > target) break;
        timers.shift();
        t = next.at;
        next.fn();
      }
      t = target;
    },
    get pending() {
      return timers.length;
    },
  };
}

function setup(overrides = {}) {
  FakeWS.instances = [];
  const clock = makeClock();
  const events = [];
  const live = createLive({
    url: 'ws://test/ws',
    WebSocketImpl: FakeWS,
    now: clock.now,
    setTimeoutImpl: clock.setTimeout,
    clearTimeoutImpl: clock.clearTimeout,
    onStatus: (status, detail) => events.push(['status', status, detail?.reason]),
    onHello: (msg) => events.push(['hello', msg]),
    onState: (msg) => events.push(['state', msg]),
    onReminder: (msg) => events.push(['reminder', msg]),
    onError: (err) => events.push(['error', String(err?.message || err)]),
    ...overrides,
  });
  return { live, clock, events, sockets: FakeWS.instances };
}

test('连上后状态是 open，hello 帧分发', () => {
  const { live, events, sockets } = setup();
  assert.equal(sockets.length, 1);
  assert.equal(live.connected, false);

  sockets[0].open();
  assert.equal(live.connected, true);
  sockets[0].send({ v: 1, type: 'hello', phone: { steps: 1 } });

  assert.deepEqual(events[0], ['status', 'open', undefined]);
  assert.deepEqual(events[1], ['hello', { v: 1, type: 'hello', phone: { steps: 1 } }]);
});

test('state 与 reminder 分发；ping 不打扰上层；未知类型忽略', () => {
  const { events, sockets } = setup();
  sockets[0].open();
  sockets[0].send({ type: 'state', phone: { steps: 2 } });
  sockets[0].send({ type: 'ping', ts: 1 });
  sockets[0].send({ type: 'reminder', kind: 'water' });
  sockets[0].send({ type: 'future-thing' });

  assert.deepEqual(
    events.slice(1).map((e) => e[0]),
    ['state', 'reminder']
  );
});

test('非法 JSON 只报错，不断连接', () => {
  const { events, sockets, live } = setup();
  sockets[0].open();
  sockets[0].onmessage({ data: '{not json' });
  assert.equal(live.connected, true);
  assert.equal(events.at(-1)[0], 'error');
});

test('意外断开后按 2s→4s→8s 递增重连，连上后回到 2s', () => {
  const { clock, sockets } = setup();
  sockets[0].open();
  sockets[0].drop();
  assert.equal(FakeWS.instances.length, 1);

  clock.advance(1999);
  assert.equal(FakeWS.instances.length, 1, '未到 2s 不该重连');
  clock.advance(1);
  assert.equal(FakeWS.instances.length, 2, '2s 后重连');

  // 第二次也失败 → 4s
  FakeWS.instances[1].drop();
  clock.advance(3999);
  assert.equal(FakeWS.instances.length, 2);
  clock.advance(1);
  assert.equal(FakeWS.instances.length, 3);

  // 第三次成功连上 → 退避重置
  FakeWS.instances[2].open();
  FakeWS.instances[2].drop();
  clock.advance(2000);
  assert.equal(FakeWS.instances.length, 4, '连上再断应回到 2s');
});

test('重连间隔封顶 30s', () => {
  const { clock, sockets } = setup();
  sockets[0].open();
  sockets[0].drop();
  let last = FakeWS.instances.length;
  for (let i = 0; i < 6; i++) {
    clock.advance(30_000);
    if (FakeWS.instances.length === last) break;
    last = FakeWS.instances.length;
    FakeWS.instances.at(-1).drop();
  }
  // 2,4,8,16,30,30 —— 第 6 次失败后等 30s
  const before = FakeWS.instances.length;
  clock.advance(29_999);
  assert.equal(FakeWS.instances.length, before, '30s 封顶：29.999s 还不该连');
  clock.advance(1);
  assert.equal(FakeWS.instances.length, before + 1);
});

test('心跳看门狗：15s 无消息主动断开并重连', () => {
  const { clock, sockets, events } = setup();
  sockets[0].open();
  clock.advance(14_999);
  assert.equal(sockets[0].closed, false);

  clock.advance(1);
  assert.equal(sockets[0].closed, true, '静默 15s 应主动断开');
  assert.equal(
    events.some((e) => e[0] === 'status' && e[1] === 'closed'),
    true
  );

  clock.advance(2000);
  assert.equal(FakeWS.instances.length, 2, '断开后 2s 重连');
});

test('服务端的 10s ping 足以喂活看门狗', () => {
  const { clock, sockets } = setup();
  sockets[0].open();
  for (let i = 0; i < 5; i++) {
    clock.advance(10_000);
    sockets[0].send({ type: 'ping', ts: i });
  }
  assert.equal(sockets[0].closed, false);
  assert.equal(FakeWS.instances.length, 1);
});

test('close() 之后不再重连', () => {
  const { clock, sockets, live } = setup();
  sockets[0].open();
  live.close();
  assert.equal(live.connected, false);
  assert.equal(sockets[0].closed, true);

  clock.advance(120_000);
  assert.equal(FakeWS.instances.length, 1, '主动关闭后不应再建连');
});

test('环境里没有 WebSocket 时只报错，不抛异常', () => {
  const events = [];
  const live = createLive({
    url: 'ws://test/ws',
    WebSocketImpl: null,
    onError: (err) => events.push(String(err?.message || err)),
  });
  assert.equal(live.connected, false);
  assert.equal(events.length, 1);
});
