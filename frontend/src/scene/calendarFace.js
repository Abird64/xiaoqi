/**
 * 挂历正面的动态卡面 —— 「当日步数」在房间里的可见位（XQ-006，UC-04 当日健康概览）。
 * owner: A（张鹏）
 *
 * 为什么不改 room.js：日历几何是 M3-1 的验收对象（XQ-018 定稿过尺寸与配色），
 * 这层只往 group 里加一块贴纸大小的面片，room.js 一行不动，回头 A 改家具也不会撞车。
 *
 * 层级：日历纸 z≈0.01、格子 z=0.013、月份带 z=0.0135，
 * 卡面取 z=0.0144 压在格子上方（格子被卡面遮住，露出纸边与月份带，仍是「挂历」）。
 *
 * 文字用 CanvasTexture 画，不用 HTML —— 这块面片要参与光照与透视，HTML 覆盖层
 * 只能贴屏幕坐标，镜头一动就穿帮。
 */
import * as THREE from 'three';

const PX_PER_M = 1280; // 0.40m 宽 → 512px，房间尺度下够清晰
// 卡面要扛住房间里的暖光：纸是亮的，墨色得压深一档，否则远看只剩一团白。
const INK = '#332f28';
const DIM = '#6c6454';
const TONE_COLOR = { ok: '#3f6b34', warn: '#a8641a', idle: '#8e8676' };

/** 圆角矩形路径（canvas 没有原生圆角填充） */
function roundRect(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.lineTo(x + w - rr, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
  ctx.lineTo(x + w, y + h - rr);
  ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
  ctx.lineTo(x + rr, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - rr);
  ctx.lineTo(x, y + rr);
  ctx.quadraticCurveTo(x, y, x + rr, y);
  ctx.closePath();
}

/** 缩到不超过 maxWidth 再写，宁可小一点也不出界 */
function fitText(ctx, text, maxWidth) {
  const w = ctx.measureText(text).width;
  return w <= maxWidth ? 1 : maxWidth / w;
}

/**
 * 把展示态画到 2D 画布上。
 * @param {CanvasRenderingContext2D} ctx
 * @param {{value: string, unit: string, note: string, tone: 'ok'|'warn'|'idle', state: string}} view
 */
export function paintFace(ctx, view) {
  const { width: W, height: H } = ctx.canvas;
  const { value, unit, note, tone, state } = view;
  ctx.clearRect(0, 0, W, H);

  // 纸面：留 6px 边，让底下日历纸的暖白露出一圈，像贴上去的一张卡
  ctx.fillStyle = '#f8f3e7';
  roundRect(ctx, 6, 6, W - 12, H - 12, 26);
  ctx.fill();

  const font = (size, weight = '400') =>
    `${weight} ${size}px "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';

  // 标题
  ctx.fillStyle = DIM;
  ctx.font = font(Math.round(H * 0.078), '600');
  ctx.fillText('今日步数', W / 2, H * 0.2);

  // 主体：有数就写数，没数就写「无数据」（A-04：不补 0）
  const hasValue = Boolean(value);
  const numSize = hasValue ? Math.round(H * 0.3) : Math.round(H * 0.15);
  ctx.fillStyle = hasValue ? TONE_COLOR[tone] || INK : TONE_COLOR.idle;
  ctx.font = font(numSize, '700');

  const gap = hasValue ? Math.round(H * 0.012) : 0;
  const unitFontSize = Math.round(H * 0.085);
  ctx.font = font(unitFontSize);
  const unitWidth = hasValue && unit ? ctx.measureText(unit).width : 0;

  ctx.font = font(numSize, '700');
  const text = hasValue ? value : '无数据';
  const scale = fitText(ctx, text, W * 0.78 - unitWidth - gap);
  if (scale < 1) ctx.font = font(Math.round(numSize * scale), '700');
  const valueWidth = ctx.measureText(text).width;
  const totalWidth = valueWidth + gap + unitWidth;
  const startX = W / 2 - totalWidth / 2;
  const baseline = H * 0.56;
  ctx.textAlign = 'left';
  ctx.fillText(text, startX, baseline);

  if (hasValue && unit) {
    ctx.font = font(unitFontSize);
    ctx.fillStyle = DIM;
    ctx.fillText(unit, startX + valueWidth + gap, baseline);
  }

  // 分隔线 + 状态行
  ctx.strokeStyle = '#dfd6c2';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(W * 0.16, H * 0.7);
  ctx.lineTo(W * 0.84, H * 0.7);
  ctx.stroke();

  ctx.textAlign = 'center';
  ctx.fillStyle = state === 'synced' ? DIM : TONE_COLOR[tone] || DIM;
  const noteSize = Math.round(H * 0.068);
  ctx.font = font(noteSize, '500');
  const noteScale = fitText(ctx, note || '', W * 0.84);
  if (noteScale < 1) ctx.font = font(Math.round(noteSize * noteScale));
  ctx.fillText(note || '', W / 2, H * 0.82);

  // 落款：让卡面看起来像屋里的一件东西，而不是调试浮层
  ctx.font = font(Math.round(H * 0.052), '500');
  ctx.fillStyle = '#a49b88';
  ctx.fillText('小栖 · 手机同步', W / 2, H * 0.93);
}

/**
 * @param {{width?: number, height?: number, name?: string}} [opts]
 * @returns {{mesh: THREE.Mesh, update: (view: any) => void}}
 */
export function createCalendarFace({ width = 0.4, height = 0.46, name = 'calendar-face' } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width * PX_PER_M);
  canvas.height = Math.round(height * PX_PER_M);
  const ctx = canvas.getContext('2d');

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;

  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(width, height),
    new THREE.MeshStandardMaterial({ map: texture, roughness: 0.95, metalness: 0, transparent: true })
  );
  mesh.name = name;
  // 贴在日历纸上：高度占满日期格区域（上让月份带、下留一圈纸边），z 压在 6×5 格子之上
  mesh.position.set(0, -0.05, 0.0144);

  let signature = '';

  function update(view) {
    const sig = [view?.value, view?.unit, view?.note, view?.tone, view?.state].join('|');
    if (sig === signature) return; // 每 10s 的刷新里，绝大多数帧什么都没变
    signature = sig;
    paintFace(ctx, view || { value: '', note: '', unit: '', tone: 'idle', state: 'none' });
    texture.needsUpdate = true;
  }

  update({
    value: '',
    unit: '',
    note: '等待手机同步',
    tone: 'idle',
    state: 'none',
  });

  return { mesh, update };
}
