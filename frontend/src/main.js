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
 *
 * XQ-006 改动（手机步数同步的电脑端呈现）：
 *   7. 接后端 WS /ws：hello/state 里的 pose → 伙伴状态卡，phone → 今日步数卡
 *   8. 挂历正面叠一张 CanvasTexture 卡面，房间视角下也能看到当日步数
 *   9. URL 参数：?live=0 关掉 WS（纯离线演示）、?ws=<host|url> 换后端
 */
import * as THREE from 'three';
import './style.css';
import { createRoom } from './scene/room.js';
import { NAME } from './scene/materials.js';
import { createCalendarFace } from './scene/calendarFace.js';
import { createViewer } from './viewer.js';
import { createHud } from './hud.js';
import { createLive } from './live.js';
import { describePhone } from './steps.js';

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
const room = createRoom({ grid: params.get('grid') !== '0' });
scene.add(room);

// ---- 挂历正面：当日步数卡面（XQ-006） ----
// 日历是「当日健康概览」的物件位（UC-04），文字只能走贴图 —— 相机一动 HTML 覆盖层就穿帮。
const calendarFace = createCalendarFace();
const calendarGroup = room.getObjectByName(NAME.calendar);
if (calendarGroup) calendarGroup.add(calendarFace.mesh);

// ---- HUD ----
const hud = createHud({
  onTool: handleTool,
  initialState: params.get('state') || 'upright',
  showToolbar: params.get('hud') !== '0',
});
hud.setState(params.get('state') || 'upright');

// ============================================================
// XQ-006 数据链：WS /ws → 伙伴状态 / 今日步数
// ============================================================

/** WS 上的 phone 快照（hello 全量 / state 增量）；null = 还没收到过手机数据 */
let phone = null;
/** ?live=0 → 纯离线演示：不连 WS，步数卡停在「无数据」 */
const liveEnabled = params.get('live') !== '0';
let liveConnected = false;
let everOpened = false;

/**
 * 展示层用的「是否连着数据源」：首帧还在握手时别急着写「未连接」，
 * 否则页面刚打开的一瞬间卡片会闪一下「未连接数据源」再变回「等待手机同步」。
 */
function connectedForDisplay() {
  if (!liveEnabled) return true;
  return liveConnected || !everOpened;
}

/** phone 快照 → 三态文案；同一次刷新里 HUD 卡片与挂历卡面用同一份判定 */
function renderPhone() {
  const view = describePhone(phone, { now: Date.now(), connected: connectedForDisplay() });
  hud.setSteps(view);
  calendarFace.update(view);
  return view;
}

function applyPose(pose) {
  if (pose && typeof pose === 'object' && pose.state) hud.setState(pose.state);
}

function applyHello(msg) {
  if ('phone' in msg) phone = msg.phone ?? null; // 全量快照：没有 phone 就是没有手机数据
  applyPose(msg.pose);
  renderPhone();
}

function applyState(msg) {
  if (msg.phone) phone = msg.phone; // 增量帧只带变化字段
  applyPose(msg.pose);
  renderPhone();
}

const REMINDER_TEXT = { water: '该喝水了', standup: '该起身活动一下', focus: '专注时段结束' };

function handleReminder(msg) {
  hud.showToast(msg.text || REMINDER_TEXT[msg.kind] || '伙伴有提醒');
}

function handleStatus(status) {
  const was = liveConnected;
  liveConnected = status === 'open';
  if (liveConnected) everOpened = true;
  hud.setConnected(liveConnected);
  if (was !== liveConnected) {
    hud.showToast(liveConnected ? '已连上数据源' : '数据连接中断 · 重试中');
  }
  renderPhone();
}

/** ?ws= 可写完整 ws:// 地址、路径，或只写 host:port（vite dev 代理时最省事） */
function resolveWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const override = params.get('ws');
  if (override) {
    if (/^wss?:\/\//i.test(override)) return override;
    if (override.startsWith('/')) return `${proto}//${location.host}${override}`;
    return `${proto}//${override.replace(/^\/+/, '')}/ws`;
  }
  return `${proto}//${location.host}/ws`;
}

renderPhone(); // 首帧先按「无数据」渲染，WS 连上之前卡片也不空着
// 相对时间与 15 分钟 stale 判定会随时间漂移，光等 WS 帧不会自己更新
setInterval(renderPhone, 10_000);

const live = liveEnabled
  ? createLive({
      url: resolveWsUrl(),
      onStatus: handleStatus,
      onHello: applyHello,
      onState: applyState,
      onReminder: handleReminder,
    })
  : null;

// 关标签页时主动断开，别让服务端留一堆死连接
window.addEventListener('pagehide', () => live?.close());

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
  // 日历的 toast 不再写死：点它时读当前步数快照（见 calendarToast）
  calendar: { view: 'calendar', target: 'calendar',   toast: null },
  mug:      { view: 'mug',      target: 'mug',        toast: '演示占位 · 水杯 = 标记喝水（UC-03）' },
  camera:   { view: 'camera',   target: 'web-camera', toast: '演示占位 · 小相机 = 隐私状态快捷入口（UC-10）' },
};

// 直达机位：?view=calendar / desk / ... —— 截图取证与演示脚本用（工具条之外的第二个入口）
const startView = params.get('view');
if (startView && VIEWS[startView]) {
  viewer.flyTo(VIEWS[startView].pos, VIEWS[startView].tgt, 1);
}

/** 物件高亮脉冲：把组内所有带 emissive 的材质临时点暖，1100ms 后原样还原 */function pulse(name, ms = 1100) {
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

/** 点「日历」时把当日步数念出来 —— 让演示现场不必凑近墙上的卡面 */
function calendarToast() {
  const v = renderPhone();
  const head = v.state === 'none' ? '今日步数：无数据' : `今日 ${v.value} 步`;
  return `日历本 · ${head} · ${v.note}`;
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
  hud.showToast(tool === 'calendar' ? calendarToast() : m.toast);
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
  window.__xiaoqi = { THREE, scene, renderer, viewer, hud, live, phone: () => phone, calendarFace };
}
