/**
 * 程序化贴图 —— XQ-009「房间视觉精修」
 * owner: A（张鹏）
 *
 * 全部用 CanvasTexture 现场生成，**不引入任何外部图片文件**：
 *   - 纹样精度口径 = 「肉眼可辨、同型不同款」，不追求与参考图逐像素一致
 *   - 随机数走 mulberry32 种子 PRNG：每次加载生成结果一致（可复现、可回归对比）
 *
 * 已登记的 XQ-003 审核 MINOR ②（墙纸菱形暗纹 / 地板拼花）与
 * MINOR ①（窗外城市层次）在本文件落地。
 */
import * as THREE from 'three';

/** 确定性 PRNG（mulberry32）——贴图可复现，不允许 Math.random 漂移 */
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * canvas → CanvasTexture 通用包装。
 * draw(ctx, w, h) 里画完整内容；repeat 控制平铺（房间 6m 见各生成器的注释）。
 */
function toTexture(canvas, { repeat = [1, 1] } = {}) {
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(repeat[0], repeat[1]);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function makeCanvas(w, h) {
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  return [canvas, canvas.getContext('2d')];
}

// ============================================================
// G1 墙纸：暖米白底 + 菱形网格暗纹（参考图左墙同型）
// ============================================================

export function makeWallpaperTexture() {
  const [canvas, ctx] = makeCanvas(512, 512);
  const rand = mulberry32(20261013);

  ctx.fillStyle = '#f0e7d6';
  ctx.fillRect(0, 0, 512, 512);

  // 极淡的底色肌理（大块明暗扰动，避免纯色塑料感）
  for (let i = 0; i < 60; i++) {
    const x = rand() * 512;
    const y = rand() * 512;
    const r = 40 + rand() * 70;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    const light = rand() > 0.5;
    g.addColorStop(0, light ? 'rgba(255,252,244,0.10)' : 'rgba(214,198,170,0.08)');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }

  // 菱形网格：周期 128px（一贴 4 周期），repeat(3,3) → 6m 墙 12 周期 ≈ 0.5m/周期
  const STEP = 128;
  ctx.strokeStyle = 'rgba(214,196,164,0.85)';
  ctx.lineWidth = 2;
  for (let oy = -STEP; oy <= 512 + STEP; oy += STEP) {
    for (let ox = -STEP; ox <= 512 + STEP; ox += STEP) {
      // 相邻行错开半步，形成编织感菱形网格
      const cx = ox + ((oy / STEP) % 2 === 0 ? 0 : STEP / 2);
      const cy = oy;
      const hw = STEP / 2;
      const hh = STEP / 4;
      ctx.beginPath();
      ctx.moveTo(cx, cy - hh);
      ctx.lineTo(cx + hw, cy);
      ctx.lineTo(cx, cy + hh);
      ctx.lineTo(cx - hw, cy);
      ctx.closePath();
      ctx.stroke();
    }
  }

  // 菱形中心的小四瓣花（参考图纹样的「花心」）
  ctx.fillStyle = 'rgba(214,196,164,0.9)';
  for (let oy = 0; oy <= 512; oy += STEP) {
    for (let ox = -STEP; ox <= 512 + STEP; ox += STEP) {
      const cx = ox + ((oy / STEP) % 2 === 0 ? 0 : STEP / 2);
      const cy = oy;
      for (let p = 0; p < 4; p++) {
        const a = (p / 4) * Math.PI * 2 + Math.PI / 4;
        ctx.beginPath();
        ctx.ellipse(
          cx + Math.cos(a) * 5, cy + Math.sin(a) * 5,
          3.4, 2.0, a, 0, Math.PI * 2
        );
        ctx.fill();
      }
    }
  }

  // 封边做无缝：把左右/上下边缘 2px 互补贴回（菱形跨周期连续的关键）
  const edge = 2;
  ctx.drawImage(canvas, 0, 0, 512, edge, 512 - edge, 0, edge, edge); // 上→下
  ctx.drawImage(canvas, 0, 512 - edge, 512, edge, 0, 0, 512, edge);   // 下→上（反向覆盖由下一行）
  ctx.drawImage(canvas, 512 - edge, 0, edge, 512, 0, 0, edge, 512);   // 右→左
  ctx.drawImage(canvas, 0, 0, edge, 512, 512 - edge, 0, edge, 512);   // 左→右

  return toTexture(canvas, { repeat: [3, 3] });
}

// ============================================================
// G2 地板：长条木地板（板间分缝 + 每板色差 + 顺纹）
// ============================================================

export function makeFloorTexture() {
  const [canvas, ctx] = makeCanvas(1024, 1024);
  const rand = mulberry32(20261013);

  // PlaneGeometry(6,6) UV：u → 世界 +x，v → 世界 -z（room.js rotation.x=-PI/2 推导）
  // repeat(6,6) → 每贴 1m；一贴 4 板 → 板宽 0.25m，板长即贴宽 1m（长条沿 x）
  const PLANKS = 4;
  const band = 1024 / PLANKS;
  const base = [0xd9, 0xad, 0x72];

  for (let p = 0; p < PLANKS; p++) {
    const y0 = p * band;
    // 每板色相/明度扰动 ±5%（确定性）
    const j = (rand() - 0.5) * 0.1;
    const r = Math.round(base[0] * (1 + j));
    const g = Math.round(base[1] * (1 + j));
    const b = Math.round(base[2] * (1 + j));
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.fillRect(0, y0, 1024, band);

    // 顺纹浅色条纹（每板 8~14 条，长度略短于板长，错落排布）
    const streaks = 8 + Math.floor(rand() * 7);
    for (let s = 0; s < streaks; s++) {
      const sy = y0 + 6 + rand() * (band - 12);
      const sx = rand() * 1024;
      const len = 120 + rand() * 500;
      ctx.strokeStyle = `rgba(255,240,214,${0.05 + rand() * 0.07})`;
      ctx.lineWidth = 1 + rand() * 2;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.bezierCurveTo(sx + len * 0.3, sy + (rand() - 0.5) * 3, sx + len * 0.7, sy + (rand() - 0.5) * 3, sx + len, sy);
      ctx.stroke();
    }

    // 板端缝（每板 2~3 道横向断缝，错位排列，读作多块短板拼）
    const joints = 2 + Math.floor(rand() * 2);
    for (let jn = 0; jn < joints; jn++) {
      const jx = ((jn + 0.5) / joints) * 1024 + (rand() - 0.5) * 60;
      ctx.fillStyle = 'rgba(150,110,68,0.55)';
      ctx.fillRect(jx, y0, 2.5, band);
    }

    // 板间分缝（深色）
    ctx.fillStyle = '#a87f4e';
    ctx.fillRect(0, y0, 1024, 3);
    ctx.fillRect(0, y0 + band - 3, 1024, 3);
  }

  // 上下封边（分缝跨贴连续）
  const edge = 3;
  ctx.drawImage(canvas, 0, 0, 1024, edge, 0, 1024 - edge, 1024, edge);

  return toTexture(canvas, { repeat: [6, 6] });
}

// ============================================================
// G3 窗外城市：天空渐变 + ≥3 层楼房剪影（远浅近深大气透视）
// ============================================================

export function makeCityTexture() {
  const W = 1024;
  const H = 640; // 窗 4.8m×3m ≈ 1.6 aspect，与玻璃区匹配
  const [canvas, ctx] = makeCanvas(W, H);
  const rand = mulberry32(20261013);

  // ── 天空：上深蓝灰 → 地平线浅雾蓝（与 scene.background #8fa5bd 衔接）──
  const sky = ctx.createLinearGradient(0, 0, 0, H * 0.9);
  sky.addColorStop(0, '#5f7a9e');
  sky.addColorStop(0.55, '#7e9ab8');
  sky.addColorStop(1, '#aebfd2');
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, W, H);

  /** 一层楼群：base=楼群基线 y，color=楼体色，minH/maxH=楼高范围，win=是否画亮灯窗 */
  function layer({ base, color, minH, maxH, win, count, haze }) {
    let x = -40;
    while (x < W + 40) {
      const w = 50 + rand() * 110;
      const h = minH + rand() * (maxH - minH);
      const top = base - h;
      // 楼体
      ctx.fillStyle = color;
      ctx.fillRect(x, top, w, h);
      // 顶部细节：矮楼顶 / 天线 / 退台（确定性挑选）
      const detail = rand();
      if (detail > 0.72) {
        const aw = 8 + rand() * 14;
        ctx.fillRect(x + w / 2 - aw / 2, top - 8 - rand() * 18, aw, 10 + rand() * 18);
      } else if (detail > 0.55) {
        const sw = w * (0.3 + rand() * 0.3);
        ctx.fillRect(x + (w - sw) / 2, top - 10, sw, 10);
      }
      // 亮灯窗（仅近层）
      if (win) {
        const cols = Math.max(2, Math.floor(w / 16));
        const rows = Math.max(2, Math.floor(h / 18));
        for (let c = 0; c < cols; c++) {
          for (let r = 0; r < rows; r++) {
            if (rand() > 0.82) {
              ctx.fillStyle = 'rgba(255,217,160,0.55)';
              ctx.fillRect(x + 6 + c * 16, top + 8 + r * 18, 4, 6);
            }
          }
        }
      }
      x += w + 4 + rand() * 16;
    }
    // 层间雾带：在楼群基线下方铺一条半透明雾色，拉开层间距
    const fog = ctx.createLinearGradient(0, base - 6, 0, base + 40);
    fog.addColorStop(0, 'rgba(0,0,0,0)');
    fog.addColorStop(1, haze);
    ctx.fillStyle = fog;
    ctx.fillRect(0, base - 6, W, 46);
  }

  // 三层深度：远层浅而矮、近层深而高（大气透视方向不可反）
  layer({ base: H * 0.60, color: '#b4c6d6', minH: 40, maxH: 120, win: false, haze: 'rgba(180,198,214,0.35)' });
  layer({ base: H * 0.74, color: '#8ba3ba', minH: 70, maxH: 190, win: false, haze: 'rgba(139,163,186,0.45)' });
  layer({ base: H * 0.92, color: '#62809a', minH: 90, maxH: 240, win: true, haze: 'rgba(98,128,154,0.5)' });

  // 地平线以下：微深的地面影区，避免楼群「悬空」
  const ground = ctx.createLinearGradient(0, H * 0.92, 0, H);
  ground.addColorStop(0, 'rgba(74,93,116,0.0)');
  ground.addColorStop(1, 'rgba(88,110,136,0.5)');
  ctx.fillStyle = ground;
  ctx.fillRect(0, H * 0.92, W, H * 0.08);

  return toTexture(canvas, { repeat: [1, 1] });
}

// ============================================================
// G4 吊灯辉光：径向渐变 sprite 贴图（加色混合）
// ============================================================

export function makeGlowTexture() {
  const [canvas, ctx] = makeCanvas(256, 256);
  const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
  g.addColorStop(0, 'rgba(255,238,205,0.95)');
  g.addColorStop(0.25, 'rgba(255,217,160,0.42)');
  g.addColorStop(0.6, 'rgba(255,203,130,0.16)');
  g.addColorStop(1, 'rgba(255,203,130,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(canvas);
}
