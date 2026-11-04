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
import { createPartner, PARTNER_STATES } from './scene/partner.js';
import { createViewer } from './viewer.js';
import { createHud } from './hud.js';
import { setupStudio } from './studio.js';

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

// ---- 健康伙伴（XQ-004）----
// 站在椅子左前方、面向房间内（≈ 相机方向），这样从默认机位看得到正脸：
// 房间的椅子朝 -z（对着桌子），若让它坐进椅子，默认机位看到的会是后脑勺。
// 身高 1.2 m：坐在桌上会挡住显示器，站在地上放 1.0 m 又太不起眼（默认机位下只有 6% 画面高）。
// 位置按默认机位 (3.0, 1.8, 1.8) → (-2.2, 1.0, -1.6) 的视锥调过，见 frontend/README。
const partner = createPartner({ height: 1.15 });
// 应用 Studio 精调坐姿与位置
partner.group.position.set(-2.024, 0.25, -1.45);
partner.group.rotation.set(0, 1.571, 0);
room.add(partner.group);



// ---- HUD ----
const initialState = params.get('state') || 'upright';
const hud = createHud({
  onTool: handleTool,
  initialState,
  showToolbar: params.get('hud') !== '0',
});
hud.setState(initialState);
partner.setState(initialState);

// 演示用：数字键 1–6 直接切伙伴状态（1 坐直 2 驼背 3 伏案 4 离开 5 喝水 6 检测中）。
// 只改姿态与状态卡，不碰镜头；HUD 工具条是业务入口，这里是录屏/答辩的快捷方式。
window.addEventListener('keydown', (e) => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const idx = Number(e.key) - 1;
  if (!Number.isInteger(idx) || idx < 0 || idx >= PARTNER_STATES.length) return;
  const next = PARTNER_STATES[idx];
  partner.setState(next);
  hud.setState(next);
});

// ============================================================
// XQ-009 演示工具条：镜头快捷跳转 + 物件高亮
// ============================================================

/**
 * 工具条是**演示辅助层**（可逆假设 A-2）：帮演示人快速到达某个物件，
 * 功能入口本身仍是「点物件」（界面原型原则二）。各机位按 room.js 布局估算。
 */
const VIEWS = {
  default:  { pos: [3.0, 1.8, 1.8],   tgt: [-1.8, 0.95, -1.45] },   // 房间总览
  desk:     { pos: [0.6, 1.45, -0.6], tgt: [-1.5, 0.85, -1.45] }, // 桌面近景
  chair:    { pos: [0.1, 1.35, -0.5], tgt: [-2.06, 0.8, -1.45] }, // 椅位小怪兽特写
  monitor:  { pos: [-0.3, 1.25, -1.45], tgt: [-1.30, 1.12, -1.45] }, // 显示器（屏面朝 -x）
  mirror:   { pos: [0.3, 1.5, 0.3],   tgt: [-2.85, 1.42, -0.55] }, // 椭圆镜
  calendar: { pos: [0.3, 1.95, -0.75],tgt: [-2.85, 1.92, -1.85] }, // 挂历
  mug:      { pos: [-0.8, 1.35, -1.2], tgt: [-2.45, 0.78, -2.55] }, // 水杯（矮柜上）
  camera:   { pos: [-0.4, 1.55, -1.45], tgt: [-1.30, 1.32, -1.45] }, // 小相机（显示器顶）
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
// r186 起 THREE.Clock 已标记废弃，改用 THREE.Timer（同样是「上一帧到这一帧」的秒数）
const timer = new THREE.Timer();
renderer.setAnimationLoop((timestamp) => {
  timer.update(timestamp);
  const dt = Math.min(timer.getDelta(), 0.1); // 切标签页回来时 dt 会很大，钳一下防止姿态瞬间跳到位
  partner.update(dt);
  viewer.update();
  hud.tick();
  renderer.render(scene, viewer.camera);
});

// 调试入口：开发期在控制台可直接改场景
// （F12 → __xiaoqi.scene.getObjectByName('room')）
// 只在开发期挂载 —— 生产构建带上它等于把内部对象对外暴露。
if (import.meta.env.DEV) {
  window.__xiaoqi = { THREE, scene, renderer, viewer, hud, partner };
}


// ---- 挂载小栖 3D 资产与场景工作室 (Studio) ----
// 默认开启，支持多物件变换、缩放、旋转、动作测试与一键导出
setupStudio({
  scene,
  viewer,
  partner,
  room,
  onSave: (config) => {
    console.log('[Studio] 保存最新场景配置:', config);
  }
});


// ============================================================
// 后端 WebSocket 实时姿态驱动（XQ-004 闭环链路）
// ============================================================
const wsUrl = params.get('ws') || 'ws://127.0.0.1:8000/ws';
let ws = null;
let reconnectTimer = null;

function connectWs() {
  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`[xiaoqi:ws] 已连接后端姿态链路: ${wsUrl}`);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        // 兼容全量快照 (hello) 与实时事件 (state)
        let poseState = null;
        if (msg.type === 'state' && msg.pose?.state) {
          poseState = msg.pose.state;
        } else if (msg.type === 'hello' && msg.pose?.state) {
          poseState = msg.pose.state;
        } else if (msg.pose_state) {
          poseState = msg.pose_state;
        }

        if (poseState) {
          console.log(`[xiaoqi:ws] 收到姿态变更: ${poseState}`);
          partner.setState(poseState);
          hud.setState(poseState);
        }
      } catch (err) {
        console.warn('[xiaoqi:ws] 解析消息失败:', err);
      }
    };

    ws.onclose = () => {
      // 断流兜底：角色保持当前姿态，不弹窗、不报错，静默尝试重连
      scheduleReconnect();
    };

    ws.onerror = () => {
      // 静默处理，避免打断界面
    };
  } catch (e) {
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWs();
  }, 3000);
}

// 启动 WebSocket 监听
connectWs();
