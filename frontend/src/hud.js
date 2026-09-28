/**
 * 平视信息层（HUD）
 * owner: A（张鹏）
 *
 * XQ-008 只放**显示位**，不接任何数据源 ——
 * 「当前状态」文字是 M1-4 的验收点，数据在 XQ-013（前端消费 WS mock）接。
 * FPS 是性能底线的现场判据（前端 ≥ 30 FPS @1080p，见系统架构 §四）。
 *
 * 来自后端的文案一律用 textContent 写入，不用 innerHTML（防注入）。
 */
export function createHud() {
  const root = document.createElement('div');
  root.className = 'hud';
  root.innerHTML = `
    <div class="hud-card hud-status">
      <div class="hud-label">当前状态</div>
      <div class="hud-value" data-hud="state">—</div>
      <div class="hud-note">未接入数据源 · 待 XQ-013</div>
    </div>
    <div class="hud-card hud-fps" data-hud="fps">-- FPS</div>
    <div class="hud-card hud-hint">拖拽旋转 · 滚轮缩放 · 右键平移</div>
  `;
  document.body.appendChild(root);

  const stateEl = root.querySelector('[data-hud="state"]');
  const fpsEl = root.querySelector('[data-hud="fps"]');
  const noteEl = root.querySelector('.hud-note');

  const FPS_WINDOW_MS = 500;
  let frames = 0;
  let windowStart = performance.now();
  let firstWindow = true; // 首个窗口必然含着色器编译，不采信

  return {
    /** 更新状态文字；传 null/'' 显示占位 */
    setState(text) {
      stateEl.textContent = text || '—';
    },
    /** 是否已连上数据源（用于灰掉那行说明） */
    setConnected(connected) {
      noteEl.textContent = connected ? '已连接' : '未接入数据源 · 待 XQ-013';
      noteEl.classList.toggle('is-on', Boolean(connected));
    },
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
