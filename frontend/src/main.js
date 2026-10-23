/**
 * 前端入口 —— XQ-003「M3-1 房间骨架补齐」+ XQ-009「视觉精修 + HUD 重设计」
 * owner: A（张鹏）
 *
 * 装配顺序：渲染器 → 场景 → 相机/控制器 → 房间 → HUD → 渲染循环。
 * 渲染循环用 setAnimationLoop（而不是 rAF 裸调用），方便以后接 XR / 统一暂停。
 *
 * M3-1 本轮改动：
 *   1. 开 shadowMap（PCFSoftShadowMap）—— XQ-008 时只铺了 receiveShadow，没开阴影，
 *      家具进来后没有影子，房间「飘」着不像基准图
 *   2. toneMapping 换成 ACESFilmic —— 暖主光 + 冷天光两种强光直接相加会过曝
 *   3. 机位从 (4.4, 3.2, 4.8) 调到与基准图一致的角落透视
 *   4. 背景色改成雾化的蓝灰，与落地窗外的城市天色衔接（原来深灰 #171a20 与窗景脱节）
 *
 * XQ-009 改动：
 *   5. HUD 重设计（伙伴状态卡 + 演示工具条），URL 参数 ?state= / ?hud=0
 *   6. 工具条 → viewer.flyTo 镜头跳转 + 物件高亮脉冲（演示辅助层，入口仍是点物件）
 */
import * as THREE from 'three';
import './style.css';
import { createRoom } from './scene/room.js';
import { createViewer } from './viewer.js';
import { createHud } from './hud.js';

const params = new URLSearchParams(location.search);
// 数值型 URL 参数：缺省 / 非数字 → undefined（沿用默认机位）
const num = (key) => {
  const raw = params.get(key);
  if (raw === null || raw.trim() === '') return undefined;
  const value = Number(raw);
  return Number.isFinite(value) ? value : undefined;
};

// ---- 渲染器 ----
const canvas = document.querySelector('#scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });

// M3-1：开阴影。PCFSoftShadowMap —— 基准图阴影柔和无强反射（渲染图反推）。
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
// 暖主光 + 冷天光同场，两盏强光直接相加会过曝，基准图的高光已被压住。
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15; // 实测 1.0 偏暗，基准图整体亮一档

// ---- 场景 ----
const scene = new THREE.Scene();
// 与窗外天色衔接：镜头推近时窗景与背景不脱节
scene.background = new THREE.Color(0x8fa5bd);

// ---- 相机 / 控制器 ----
const viewer = createViewer(canvas, {
  azimuth: num('az'),
  elevation: num('el'),
  distance: num('dist'),
});

// ---- 房间 ----
scene.add(createRoom({ grid: params.get('grid') !== '0' }));

// ---- HUD ----
const hud = createHud({
  onTool: handleTool,
  initialState: params.get('state') || 'upright',
  showToolbar: params.get('hud') !== '0',
});
hud.setState(params.get('state') || 'upright');

// ============================================================
// XQ-009 演示工具条：镜头快捷跳转 + 物件高亮
// ============================================================

/**
 * 工具条是**演示辅助层**（可逆假设 A-2）：帮演示人快速到达某个物件，
 * 功能入口本身仍是「点物件」（界面原型原则二）。各机位按 room.js 布局估算。
 */
const VIEWS = {
  default:  { pos: [3.0, 1.8, 1.8],   tgt: [-2.2, 1.0, -1.6] },   // 房间总览（XQ-003 定稿机位）
  desk:     { pos: [1.9, 1.45, 0.1],  tgt: [-1.8, 0.95, -2.5] },  // 桌面近景
  chair:    { pos: [1.1, 1.25, 0.8],  tgt: [-1.65, 0.6, -2.35] }, // 椅位视角
  monitor:  { pos: [1.35, 1.5, 0.35], tgt: [-1.65, 1.12, -2.68] },// 显示器（屏面朝 +z）
  mirror:   { pos: [0.3, 1.5, 0.3],   tgt: [-2.85, 1.42, -0.55] },// 椭圆镜
  calendar: { pos: [0.3, 1.95, -0.75],tgt: [-2.85, 1.92, -1.85] },// 挂历
  mug:      { pos: [0.7, 1.35, 0.1],  tgt: [-2.66, 0.78, -1.5] }, // 水杯（矮柜上）
  camera:   { pos: [1.15, 1.62, 0.15],tgt: [-1.65, 1.32, -2.7] }, // 小相机（显示器顶）
};
const VIEW_CYCLE = ['default', 'desk', 'chair']; // 「视角方式」循环序
let viewIdx = 0;

/** 工具 → 机位 / 高亮对象名 / toast 文案（语义对齐界面原型第二节物件×功能表） */
const TOOL_MAP = {
  pc:       { view: 'monitor',  target: 'monitor',    toast: '演示占位 · 电脑屏 = 设置/配对/导入/隐私容器（内容 XQ-006 填）' },
  config:   { view: 'monitor',  target: 'monitor',    toast: '演示占位 · 提醒阈值/静默时段在电脑屏「设置」窗' },
  import:   { view: 'monitor',  target: 'monitor',    toast: '演示占位 · 手动导入健康数据在电脑屏「导入」窗' },
  monitor:  { view: 'monitor',  target: 'monitor',    toast: '演示占位 · 显示器 = 前台应用时长可视化位（XQ-006）' },
  mirror:   { view: 'mirror',   target: 'mirror',     toast: '演示占位 · 镜子 = 坐姿校准入口（UC-01/07）' },
  calendar: { view: 'calendar', target: 'calendar',   toast: '演示占位 · 日历本 = 当日健康概览（UC-04）' },
  mug:      { view: 'mug',      target: 'mug',        toast: '演示占位 · 水杯 = 标记喝水（UC-03）' },
  camera:   { view: 'camera',   target: 'web-camera', toast: '演示占位 · 小相机 = 隐私状态快捷入口（UC-10）' },
};

/** 物件高亮脉冲：把组内所有带 emissive 的材质临时点暖，1100ms 后原样还原 */
function pulse(name, ms = 1100) {
  const obj = scene.getObjectByName(name);
  if (!obj) return;
  const mats = new Set();
  obj.traverse((o) => {
    if (o.isMesh && o.material && o.material.emissive) mats.add(o.material);
  });
  const list = [...mats];
  const prev = list.map((m) => m.emissive.getHex());
  list.forEach((m) => m.emissive.setHex(0xffd9a0));
  setTimeout(() => list.forEach((m, i) => m.emissive.setHex(prev[i])), ms);
}

function handleTool(tool) {
  if (tool === 'stealth') {
    hud.setStealth(true);
    return;
  }
  if (tool === 'view') {
    viewIdx = (viewIdx + 1) % VIEW_CYCLE.length;
    const v = VIEWS[VIEW_CYCLE[viewIdx]];
    viewer.flyTo(v.pos, v.tgt);
    hud.showToast(`视角方式 → ${VIEW_CYCLE[viewIdx]}`);
    return;
  }
  const m = TOOL_MAP[tool];
  if (!m) return;
  const v = VIEWS[m.view];
  viewer.flyTo(v.pos, v.tgt);
  // 飞行约 850ms 后镜头到位，此时点亮目标物件
  setTimeout(() => pulse(m.target), 850);
  hud.showToast(m.toast);
}

// ---- 自适应窗口 ----
// devicePixelRatio 在 resize 里重读：跨屏拖动（普通屏 ↔ 高分屏）时 dpr 会变，
// 只在启动读一次会让高分屏上的画面糊、或在低分屏上白白多渲染数倍像素。
function resize() {
  const width = window.innerWidth;
  const height = window.innerHeight;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(width, height, false);
  viewer.resize(width, height);
}
window.addEventListener('resize', resize);
resize();

// ---- 渲染循环 ----
renderer.setAnimationLoop(() => {
  viewer.update();
  hud.tick();
  renderer.render(scene, viewer.camera);
});

// 调试入口：开发期在控制台可直接改场景
// （F12 → __xiaoqi.scene.getObjectByName('room')）
// 只在开发期挂载 —— 生产构建带上它等于把内部对象对外暴露。
if (import.meta.env.DEV) {
  window.__xiaoqi = { THREE, scene, renderer, viewer, hud };
}
