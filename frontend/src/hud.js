/**
 * 平视信息层（HUD）—— XQ-009 重设计，对齐组长参考图截图
 * owner: A（张鹏）
 *
 * 结构（照参考图截图）：
 *   - 左上：演示工具条 10 钮（视角方式/电脑设置/配置/导入/隐形/镜子/日历/水杯/监视/相机）
 *   - 左下：今日步数卡（XQ-006 手机同步）+ 伙伴状态卡（正直（健康）式样 + 状态点）
 *   - 右上：FPS（M3-6 取证用，小且淡）
 *   - 底部中间：toast（演示占位提示，1.6s 自灭）
 *
 * 数据契约：来自后端的文案一律 textContent 写入，不用 innerHTML（防注入）。
 * 伙伴状态与步数由 main.js 接 WS 后驱动（XQ-006）；setState / setSteps / setConnected
 * 只接收「已经算好的展示文案」，三态判定在 steps.js 里，HUD 不认识协议字段。
 */

/** 伙伴状态枚举 → 展示文案 + 状态点色调（与后端 machine.py 6 值枚举对齐） */
const STATE_MAP = {
  upright:    { text: '正直（健康）', tone: 'ok' },
  slouch:     { text: '驼背（注意）', tone: 'warn' },
  desk_hunch: { text: '伏案（提醒）', tone: 'warn' },
  away:       { text: '离开（待机）', tone: 'idle' },
  drinking:   { text: '喝水（计数）', tone: 'info' },
  unknown:    { text: '检测中', tone: 'idle' },
};

/** 演示工具条（文案与参考图截图逐字一致） */
const TOOLS = [
  ['view', '视角方式'], ['pc', '电脑设置'], ['config', '配置'], ['import', '导入'],
  ['stealth', '隐形'], ['mirror', '镜子'], ['calendar', '日历'], ['mug', '水杯'],
  ['monitor', '监视'], ['camera', '相机'],
];

export function createHud({ onTool, initialState = 'upright', showToolbar = true } = {}) {
  const root = document.createElement('div');
  root.className = 'hud';

  // 骨架：静态文案走 innerHTML（与 XQ-008 同一约定）；动态文案一律 textContent
  root.innerHTML = `
    <div class="hud-toolbar" data-hud="toolbar">
      ${TOOLS.map(([id, label]) => `<button class="hud-tool" type="button" data-tool="${id}">${label}</button>`).join('')}
    </div>
    <div class="hud-steps" data-hud="steps" data-tone="idle">
      <span class="hud-steps-label">今日步数</span>
      <span class="hud-steps-row">
        <span class="hud-steps-value" data-hud="steps-value">无数据</span>
        <span class="hud-steps-unit" data-hud="steps-unit"></span>
      </span>
      <span class="hud-steps-note" data-hud="steps-note">等待手机同步</span>
    </div>
    <div class="hud-partner" data-hud="partner">
      <span class="hud-dot is-idle" data-hud="dot"></span>
      <span class="hud-partner-body">
        <span class="hud-partner-label">伙伴状态</span>
        <span class="hud-partner-value" data-hud="state">—</span>
      </span>
    </div>
    <div class="hud-fps" data-hud="fps">-- FPS</div>
    <div class="hud-toast" data-hud="toast" role="status"></div>
    <button class="hud-restore" type="button" data-hud="restore" hidden>显示界面</button>
  `;
  document.body.appendChild(root);

  const toolbarEl = root.querySelector('[data-hud="toolbar"]');
  const stepsEl = root.querySelector('[data-hud="steps"]');
  const stepsValueEl = root.querySelector('[data-hud="steps-value"]');
  const stepsUnitEl = root.querySelector('[data-hud="steps-unit"]');
  const stepsNoteEl = root.querySelector('[data-hud="steps-note"]');
  const partnerEl = root.querySelector('[data-hud="partner"]');
  const dotEl = root.querySelector('[data-hud="dot"]');
  const stateEl = root.querySelector('[data-hud="state"]');
  const fpsEl = root.querySelector('[data-hud="fps"]');
  const toastEl = root.querySelector('[data-hud="toast"]');
  const restoreEl = root.querySelector('[data-hud="restore"]');

  if (!showToolbar) toolbarEl.hidden = true;

  // 步数卡的上次渲染签名：rel time 每 10s 重算，签名不变就别碰 DOM
  let stepsSignature = '';

  // ---- 工具条：点击 → onTool(id)。按钮只做镜头快捷跳转，不承载业务入口 ----
  toolbarEl.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-tool]');
    if (!btn) return;
    if (typeof onTool === 'function') onTool(btn.dataset.tool, btn);
  });

  // ---- 隐形：整层隐显；留一个常驻恢复钮 + Esc 快捷键 ----
  function setStealth(on) {
    root.classList.toggle('is-stealth', on);
    restoreEl.hidden = !on;
  }
  restoreEl.addEventListener('click', () => setStealth(false));
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') setStealth(false);
  });

  // ---- toast：1.6s 自灭 ----
  let toastTimer = 0;
  function showToast(text) {
    toastEl.textContent = text || '';
    toastEl.classList.toggle('is-on', Boolean(text));
    clearTimeout(toastTimer);
    if (text) {
      toastTimer = setTimeout(() => toastEl.classList.remove('is-on'), 1600);
    }
  }

  const FPS_WINDOW_MS = 500;
  let frames = 0;
  let windowStart = performance.now();
  let firstWindow = true; // 首个窗口必然含着色器编译，不采信

  return {
    /** 更新伙伴状态：传枚举键（upright/slouch/...）；非枚举键时按原文显示 */
    setState(key) {
      const s = STATE_MAP[key];
      if (s) {
        stateEl.textContent = s.text;
        dotEl.className = `hud-dot is-${s.tone}`;
      } else {
        stateEl.textContent = key || '—';
        dotEl.className = 'hud-dot is-idle';
      }
    },
    /** 是否已连上数据源（XQ-006 接 WS 后调用；当前只切样式类） */
    setConnected(connected) {
      partnerEl.classList.toggle('is-live', Boolean(connected));
    },
    /**
     * 今日步数三态（XQ-006）。只吃 steps.js 算好的展示字段：
     *   { value: '3,210' | '', unit: '步', note: '3 分钟前同步', tone: 'ok'|'warn'|'idle' }
     * value 为空表示「无数据」——A-04 要求此时写「无数据」，不能补 0。
     * 每 10s 会重算一次相对时间，签名没变就不动 DOM（避免读数闪烁）。
     */
    setSteps(view) {
      const v = view || {};
      const signature = [v.value, v.unit, v.note, v.tone].join('|');
      if (signature === stepsSignature) return;
      stepsSignature = signature;
      stepsEl.dataset.tone = v.tone || 'idle';
      stepsValueEl.textContent = v.value || '无数据';
      stepsUnitEl.textContent = v.value ? v.unit || '' : '';
      stepsNoteEl.textContent = v.note || '';
    },
    showToast,
    setStealth,
    /**
     * 帧率统计。用 performance.now() 自己计时，不用渲染循环传进来的 delta ——
     * 后台标签页恢复、调试器断点、无头浏览器的虚拟时间都会让 delta 突变，
     * 那样算出来的帧率是假的。
     *
     * 有两类窗口不采信（否则会显示一个假低值）：
     *   1) 首个窗口 —— 含 WebGL 初始化与着色器编译，读数必然偏低；
     *   2) 跨度超过 4 个窗口长度 —— 标签页切回、断点后的第一个窗口。
     */
    tick() {
      frames += 1;
      const now = performance.now();
      const span = now - windowStart;
      if (span < FPS_WINDOW_MS) return;

      const trustworthy = !firstWindow && span < FPS_WINDOW_MS * 4;
      firstWindow = false;
      if (trustworthy) {
        fpsEl.textContent = `${Math.round((frames * 1000) / span)} FPS`;
      }
      frames = 0;
      windowStart = now;
    },
    get stateText() {
      return stateEl.textContent;
    },
  };
}
