/**
 * steps.js 单测 —— 三态判定的边界都在这里钉住（无数据不补 0、15 分钟老化、断连）
 * 跑法：cd frontend && node --test test/
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { describePhone, formatAge, formatSteps, toMs, STALE_MS } from '../src/steps.js';

test('formatSteps：千分位，非法值一律返回空串（不补 0）', () => {
  assert.equal(formatSteps(3210), '3,210');
  assert.equal(formatSteps(0), '0');
  assert.equal(formatSteps(999), '999');
  assert.equal(formatSteps(1234567), '1,234,567');
  assert.equal(formatSteps(null), '');
  assert.equal(formatSteps(undefined), '');
  assert.equal(formatSteps(''), '');
  assert.equal(formatSteps('abc'), '');
  assert.equal(formatSteps(-1), '');
});

test('toMs：毫秒原样、秒换算成毫秒、垃圾值 null', () => {
  assert.equal(toMs(1_700_000_000_000), 1_700_000_000_000);
  assert.equal(toMs(1_700_000_000), 1_700_000_000_000);
  assert.equal(toMs(null), null);
  assert.equal(toMs(0), null);
  assert.equal(toMs('2026-10-27'), null);
});

test('formatAge：只说人话', () => {
  assert.equal(formatAge(0), '刚刚');
  assert.equal(formatAge(59_000), '刚刚');
  assert.equal(formatAge(60_000), '1 分钟前');
  assert.equal(formatAge(90 * 60_000), '1 小时前');
  assert.equal(formatAge(3.5 * 3_600_000), '3 小时前');
  assert.equal(formatAge(30 * 3_600_000), '1 天前');
});

test('无 phone / steps 为 null → 无数据，绝不显示 0', () => {
  for (const phone of [null, undefined, {}, { steps: null }, { steps: 'x' }]) {
    const v = describePhone(phone, { now: 1_700_000_000_000 });
    assert.equal(v.state, 'none');
    assert.equal(v.value, '');
    assert.equal(v.note, '等待手机同步');
    assert.equal(v.tone, 'idle');
  }
});

test('刚上报过 → 已同步，带相对时间', () => {
  const now = 1_700_000_000_000;
  const v = describePhone({ steps: 3210, updated_ts: now - 60_000, stale: false }, { now });
  assert.equal(v.state, 'synced');
  assert.equal(v.value, '3,210');
  assert.equal(v.unit, '步');
  assert.equal(v.note, '1 分钟前同步');
  assert.equal(v.tone, 'ok');
});

test('后端标了 stale → 待同步', () => {
  const now = 1_700_000_000_000;
  const v = describePhone({ steps: 3210, updated_ts: now - 60_000, stale: true }, { now });
  assert.equal(v.state, 'pending');
  assert.equal(v.tone, 'warn');
  assert.match(v.note, /^待同步/);
});

test('后端没标 stale 但已超过 15 分钟 → 前端自己翻成待同步', () => {
  const now = 1_700_000_000_000;
  const v = describePhone({ steps: 3210, updated_ts: now - STALE_MS - 1000 }, { now });
  assert.equal(v.state, 'pending');
  assert.equal(v.note, '待同步 · 15 分钟前');
});

test('刚好 15 分钟不算 stale（边界不抖动）', () => {
  const now = 1_700_000_000_000;
  const v = describePhone({ steps: 3210, updated_ts: now - STALE_MS }, { now });
  assert.equal(v.state, 'synced');
});

test('没有 updated_ts 时只能信后端 stale 字段', () => {
  const v = describePhone({ steps: 88 }, { now: 1_700_000_000_000 });
  assert.equal(v.state, 'synced');
  assert.equal(v.note, '已同步');
});

test('连接断了：保留最后一次数值，但标成中断', () => {
  const now = 1_700_000_000_000;
  const v = describePhone({ steps: 3210, updated_ts: now - 60_000 }, { now, connected: false });
  assert.equal(v.state, 'offline');
  assert.equal(v.value, '3,210');
  assert.equal(v.note, '连接中断');
  assert.equal(v.tone, 'warn');
});

test('连接断了且从来没有数据 → 提示未连接数据源', () => {
  const v = describePhone(null, { now: 1, connected: false });
  assert.equal(v.state, 'none');
  assert.equal(v.note, '未连接数据源');
});
