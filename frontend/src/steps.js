/**
 * 手机步数的展示语义 —— 纯函数，不碰 DOM、不碰 three.js，可直接 `node --test` 单测。
 * owner: A（张鹏）｜XQ-006 手机步数同步（电脑端呈现）
 *
 * 依据：
 *   - 需求规格说明书 UC-06 主流程 4/5：WS 推送 phone → 前端刷新步数可视化；15 分钟未更新标 stale；
 *     A3：stale 时前端显示「待同步」；A-04：无数据不得补 0（显示「无数据」而不是 0 步）
 *   - 接口协议 §4 规则 4：`stale_sec` 默认 900s（15 分钟）未更新 → stale=true
 *   - 接口协议 §3.1：hello 首帧 phone = { steps, updated_ts, stale }（steps 可为 null）
 *
 * 为什么把「15 分钟」在前端再判一次：后端的 stale 只在下次上报时重算，手机不再上报时
 * 后端不会主动推一条 stale=true。前端按 updated_ts 自行老化，才能到点就把「已同步」翻成
 * 「待同步」，否则屏幕上会一直挂着一个永不过期的旧数字。
 */

/** 协议 §4 规则 4：15 分钟未更新视为待同步 */
export const STALE_MS = 15 * 60 * 1000;

/** 后端时间戳是毫秒；容错成秒/字符串也认 */
export function toMs(raw) {
  if (raw === null || raw === undefined || raw === '') return null;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return null;
  return n < 1e11 ? Math.round(n * 1000) : Math.round(n);
}

/** 3210 → '3,210'；非法/负数/空 → ''（调用方据此显示「无数据」，绝不补 0） */
export function formatSteps(steps) {
  if (steps === null || steps === undefined || steps === '') return '';
  const n = Number(steps);
  if (!Number.isFinite(n) || n < 0) return '';
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/** 相对时间：只说人话，不做时钟格式（跨天/时区一改就错） */
export function formatAge(ms) {
  if (!Number.isFinite(ms) || ms < 60_000) return '刚刚';
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

/**
 * phone 快照 → 展示三态。
 * @param {{steps?: any, updated_ts?: any, stale?: any}|null} phone  WS hello/state 里的 phone 字段
 * @param {{now?: number, connected?: boolean, staleMs?: number}} [opts]
 * @returns {{state: 'none'|'synced'|'pending'|'offline', value: string, unit: string,
 *            note: string, tone: 'idle'|'ok'|'warn', steps: number|null, updatedTs: number|null}}
 */
export function describePhone(phone, { now = Date.now(), connected = true, staleMs = STALE_MS } = {}) {
  // 空值判定必须走 formatSteps：`Number(null)` 是 0，直接 Number() 会把「没数据」变成「0 步」
  const value = formatSteps(phone ? phone.steps : null);
  const steps = value === '' ? null : Number(phone.steps);
  const updatedTs = toMs(phone && phone.updated_ts);
  const age = steps !== null && updatedTs !== null ? Math.max(0, now - updatedTs) : null;

  if (steps === null) {
    return {
      state: 'none',
      value: '',
      unit: '',
      note: connected ? '等待手机同步' : '未连接数据源',
      tone: 'idle',
      steps: null,
      updatedTs: null,
    };
  }

  // 后端说 stale，或按 updated_ts 自己老化超时 —— 两者任一成立就是「待同步」
  const stale = Boolean(phone && phone.stale) || (age !== null && age > staleMs);

  if (!connected) {
    return { state: 'offline', value, unit: '步', note: '连接中断', tone: 'warn', steps, updatedTs };
  }
  if (stale) {
    return {
      state: 'pending',
      value,
      unit: '步',
      note: age === null ? '待同步' : `待同步 · ${formatAge(age)}`,
      tone: 'warn',
      steps,
      updatedTs,
    };
  }
  return {
    state: 'synced',
    value,
    unit: '步',
    note: age === null ? '已同步' : `${formatAge(age)}同步`,
    tone: 'ok',
    steps,
    updatedTs,
  };
}
