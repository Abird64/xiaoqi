/**
 * 场景通用件 —— 材质工厂 + 圆角几何体 + 物件命名常量
 * owner: A（张鹏）｜XQ-003 M3-1
 *
 * 抽出这一层的原因：room.js 里 13 件家具若各写各的 MeshStandardMaterial，
 * roughness/metalness 会漂成十几种值，M3-7「展示效果达标」根本没法定标准。
 * 材质参数集中在这里，改一处全体生效。
 *
 * ── 美术规格（XQ-003 定档，来自 04-视觉参考/房间-建模基准.jpeg 反推）──
 *   风格：粘土风 —— 所有边缘倒圆角、亚光、无高光、无复杂 PBR 贴图
 *   材质：MeshStandardMaterial，roughness ≈ 0.9，metalness = 0
 *   唯一硬边 low-poly 是植物叶片（见 buildPlant）
 *
 * 坐标约定（沿用 XQ-008，不得改动）：
 *   1 单位 = 1 米；y 轴朝上；地面 y = 0
 *   房间 6m × 6m；墙高 3m；后墙 z = -3；左墙 x = -3
 */
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

/**
 * 配色表 —— 直接取自基准图，可当 three.js Color 十六进制用。
 * 与 小栖 界面原型.md §8.2 一致，勿单处改动。
 */
export const PALETTE = {
  wall: 0xf0e7d6,       // 墙纸 暖米白带浅纹样
  floor: 0xd9ad72,      // 地板 浅橡木
  wood: 0xc9915e,       // 桌面 / 矮柜 中橡木
  chair: 0xd9d9dd,      // 椅子 灰白
  frameSilver: 0xb8bcc0, // 显示器边框 银灰
  screen: 0x3a3f44,     // 显示器屏 深灰
  white: 0xf2f1ec,      // 花盆 / 灯罩 / 日历纸 白
  leafLight: 0x6fbf5a,  // 植物叶 亮面
  leafDark: 0x4f9e42,   // 植物叶 暗面
  silver: 0xc8ccd0,     // 闹钟 / 键鼠 银
  mirrorFrame: 0xb07d4f, // 镜框 木色
  windowFrame: 0x5a6068, // 落地窗框 深灰
  cityFar: 0x8fa5bd,    // 窗外城市 蓝灰雾
  cityNear: 0x6b8299,
  lampWarm: 0xffd9a0,   // 吊灯暖主光 2700K
  skyCool: 0x7f9cc4,    // 窗外蓝调天光（黄昏）
};

/** 粘土风材质：亚光、无高光。家具/墙面/地板统一走这里。 */
export function clay(color, extra = {}) {
  return new THREE.MeshStandardMaterial({
    color,
    roughness: 0.9,   // 亚光粘土感 —— 别用 MeshPhongMaterial，高光太硬不像基准图
    metalness: 0,     // 非金属
    ...extra,
  });
}

/** 自发光材质：只给屏幕/灯罩这类「自己在发光」的件。 */
export function glow(color, intensity = 0.8) {
  return new THREE.MeshStandardMaterial({
    color,
    emissive: color,
    emissiveIntensity: intensity,
    roughness: 0.7,
    metalness: 0,
  });
}

/**
 * 圆角盒 —— 家具统一用它，不要用裸 BoxGeometry。
 * 基准图里所有家具边缘都是倒圆角的，这是「粘土风」最直观的识别特征。
 * 半径约束在 min(半径, 最短边/2) 以内，避免几何体自交。
 */
export function roundedBox(w, h, d, radius = 0.03, material) {
  const r = Math.min(radius, Math.min(w, h, d) / 2 - 1e-4);
  const geo = new RoundedBoxGeometry(w, h, d, 2, Math.max(r, 1e-4));
  return new THREE.Mesh(geo, material);
}

/**
 * 物件名常量 —— 与 M3-1 验收清单一一对应。
 * 独立成对象而非散落的字符串字面量：XQ-004 之后要按名字取伙伴、屏幕覆盖层对齐，
 * 拼错字会静默变成 undefined，查起来很痛。
 */
export const NAME = {
  floor: 'floor',
  wallBack: 'wall-back',
  wallLeft: 'wall-left',
  window: 'window',
  windowFrame: 'window-frame',
  desk: 'desk',
  deskCabinet: 'desk-cabinet',
  chair: 'chair',
  monitor: 'monitor',
  screen: 'screen',
  keyboard: 'keyboard',
  mouse: 'mouse',
  webCamera: 'web-camera',
  mug: 'mug',
  clock: 'clock',
  plant: 'plant',
  plantPot: 'plant-pot',
  mirror: 'mirror',
  calendar: 'calendar',
  lamp: 'lamp',
  // 伙伴位：XQ-004 才建几何体，这里只留名字占位
  partner: 'partner',
  // 屏幕 HTML 覆盖层对齐用的锚点（XQ-004/005 用）
  screenAnchor: 'screen-anchor',
};
