/**
 * 前端入口 —— XQ-003「M3-1 房间骨架补齐（13 件物件 + 粘土风 + 双光）」
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
// 与窗外 cityFar (#8fa5bd) 同色：房间外不再是突兀的深灰，镜头推近时衔接自然
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
const hud = createHud();

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
