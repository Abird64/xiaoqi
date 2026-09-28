/**
 * 前端入口 —— XQ-008「Three.js 空房间骨架跑通（能转相机）」
 * owner: A（张鹏）
 *
 * 装配顺序：渲染器 → 场景 → 相机/控制器 → 房间 → HUD → 渲染循环。
 * 渲染循环用 setAnimationLoop（而不是 rAF 裸调用），方便以后接 XR / 统一暂停。
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
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

// ---- 场景 ----
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x171a20); // 房间外的底色

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
function resize() {
  const width = window.innerWidth;
  const height = window.innerHeight;
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

// 调试入口：控制台里可直接改场景（F12 → __xiaoqi.scene.getObjectByName('room')）
window.__xiaoqi = { THREE, scene, renderer, viewer, hud };
