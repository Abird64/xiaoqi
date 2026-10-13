/**
 * 家具与陈设 —— XQ-003「M3-1 房间骨架补齐」
 * owner: A（张鹏）
 *
 * ══════ 布局定稿（照 04-视觉参考/房间-建模基准.jpeg 数出来，不是猜的）══════
 *
 * 参考图构图：
 *   画面左 1/3 = 实体墙（椭圆镜 + 挂历）
 *   画面右 2/3 = 整面落地窗（两扇大窗 + 上部气窗）
 *   桌椅在中段、地板占下部、吊灯在桌面上方
 *
 * 相机站在 (+x, +z) 的墙角外侧时（房间唯一合理的机位）：
 *   x = -3 那面墙 → 落画面左
 *   z = -3 那面墙 → 落画面右
 *   ⇒ 实体墙开 x = -3，落地窗开 z = -3
 *
 * ── 坐标约定（1 单位 = 1 米，y 向上，地面 y = 0，房间 6×6×3）──
 *   **实体墙 x = -3**  椭圆镜 + 挂历           （画面左 1/3）
 *   **窗墙   z = -3**  整面落地窗 + 城市剪影   （画面右 2/3，光源）
 *   **敞口   z = +3 / x = +3**  留机位，不立任何东西
 *
 *   ⚠️ 这个归属与 XQ-008 旧约定**不同**（旧：后墙 z=-3 贴显示器 / 左墙 x=-3 挂日历）。
 *      显示器现在贴的是窗墙 z=-3。看旧代码时别照旧记忆。
 *
 * 五个坑（小栖 界面原型.md §六）：
 *   1. 实体墙只放镜子 + 日历两件
 *   2. 盆栽是唯一「能读数的植物」，窗外剪影不许同款
 *   3. 显示器朝房间内（+z），它是唯一 2D 容器
 *   4. away 不能设计成出门，窗前看风景就是去处
 *   5. 摄像头放显示器顶
 */
import * as THREE from 'three';
import { PALETTE, clay, glow, roundedBox, NAME } from './materials.js';

export const ROOM = { size: 6, wallHeight: 3 };

/** 桌高 0.75m；矮柜 0.62m；椅座 0.45m。改这几个数要同步 README。 */
const DESK_H = 0.75;
const CABINET_H = 0.62;
const SEAT_H = 0.45;
const DESK_L = 2.5;    // 桌长（沿 x）
const DESK_D = 0.68;   // 桌深（沿 z）
const WALL = -ROOM.size / 2;   // = -3

// ============================================================
// 地面 / 实体墙
// ============================================================

function buildFloor() {
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.size, ROOM.size),
    clay(PALETTE.floor, { roughness: 0.88 })
  );
  floor.name = NAME.floor;
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  return floor;
}

/** x = -3 → 实体墙：镜子 + 日历本挂这面 */
function buildSolidWall() {
  const wall = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.size, ROOM.wallHeight),
    clay(PALETTE.wall, { side: THREE.DoubleSide })
  );
  wall.name = NAME.wallLeft;
  wall.position.set(WALL, ROOM.wallHeight / 2, 0);
  wall.rotation.y = Math.PI / 2;
  wall.receiveShadow = true;
  return wall;
}

// ============================================================
// 落地窗（z = -3）—— 光源 + 景观
// ============================================================

function buildWindow() {
  const group = new THREE.Group();
  group.name = NAME.window;
  group.position.set(0, 0, WALL);

  const H = ROOM.wallHeight;
  // 窗铺 x ∈ [-3, 1.8]：+x 那侧是敞口，留空当机位。
  // 铺到 x=+3 时竖梃杵在镜头旁边，画面被黑柱穿一道（XQ-003 踩过）。
  const X_BACK = -ROOM.size / 2;
  const X_FRONT = 1.8;
  const W = X_FRONT - X_BACK;
  const X_MID = (X_FRONT + X_BACK) / 2;

  // 远景天色：雾化蓝灰，与 scene.background 同色
  const sky = new THREE.Mesh(
    new THREE.PlaneGeometry(W, H),
    new THREE.MeshBasicMaterial({ color: PALETTE.cityFar })
  );
  sky.name = 'window-sky';
  sky.position.set(X_MID, H / 2, -0.06);
  group.add(sky);

  // 远景剪影：纯色矩形，不带植物（坑 2）
  const silhouetteMat = new THREE.MeshBasicMaterial({ color: PALETTE.cityNear });
  const boxes = [
    [-1.6, 0.9, 1.0, 1.5], [-1.1, 1.25, 0.9, 2.0], [-0.4, 0.75, 1.1, 1.25],
    [0.4, 1.0, 1.3, 1.75], [1.2, 0.8, 1.1, 1.4], [1.9, 1.05, 1.0, 1.85],
  ];
  boxes.forEach(([dx, y, w, h], i) => {
    const b = new THREE.Mesh(new THREE.PlaneGeometry(w, h), silhouetteMat);
    b.name = `window-city-${i}`;
    b.position.set(X_MID + dx, y, -0.04);
    group.add(b);
  });

  // 窗框：上下横梁 + 上部气窗分隔 + 两根竖梃（参考图是两扇大窗 + 气窗）
  const frameMat = clay(PALETTE.windowFrame);
  const T = 0.07, BAR = 0.05;
  const addFrame = (name, len, h, y, x) => {
    const m = roundedBox(len, h, T, 0.02, frameMat);
    m.name = name;
    m.position.set(x, y, 0.02);
    m.castShadow = false;
    group.add(m);
  };
  addFrame(`${NAME.windowFrame}-beam-top`, W, BAR, H - BAR / 2, X_MID);
  addFrame(`${NAME.windowFrame}-beam-bottom`, W, BAR, BAR / 2, X_MID);
  addFrame(`${NAME.windowFrame}-beam-mid`, W, BAR * 0.8, H * 0.68, X_MID);
  addFrame(`${NAME.windowFrame}-post-l`, BAR, H, H / 2, X_BACK + BAR / 2);
  addFrame(`${NAME.windowFrame}-post-r`, BAR, H, H / 2, X_FRONT - BAR / 2);
  addFrame(`${NAME.windowFrame}-post-mid`, BAR * 0.8, H, H / 2, X_MID - 0.9);

  return group;
}

// ============================================================
// 桌子（贴窗墙 z = -3，L 型）
// ============================================================

function buildDesk() {
  const group = new THREE.Group();
  group.name = NAME.desk;
  const woodMat = clay(PALETTE.wood);

  // 长边：沿 x 延伸、贴着窗墙
  const longTop = roundedBox(DESK_L, 0.05, DESK_D, 0.02, woodMat);
  longTop.name = 'desk-top-long';
  longTop.position.set(WALL + DESK_L / 2, DESK_H, WALL + DESK_D / 2);
  longTop.castShadow = true;
  longTop.receiveShadow = true;
  group.add(longTop);

  const legR = roundedBox(0.06, DESK_H - 0.05, DESK_D - 0.08, 0.02, woodMat);
  legR.name = 'desk-leg-long';
  legR.position.set(WALL + DESK_L - 0.05, (DESK_H - 0.05) / 2, WALL + DESK_D / 2);
  legR.castShadow = true;
  group.add(legR);

  // 短边：沿 z 回靠实体墙 x=-3
  const SHORT_L = 1.1;
  const shortTop = roundedBox(DESK_D, 0.05, SHORT_L, 0.02, woodMat);
  shortTop.name = 'desk-top-short';
  shortTop.position.set(WALL + DESK_D / 2, DESK_H, WALL + SHORT_L / 2);
  shortTop.castShadow = true;
  shortTop.receiveShadow = true;
  group.add(shortTop);

  const legS = roundedBox(DESK_D - 0.08, DESK_H - 0.05, 0.06, 0.02, woodMat);
  legS.name = 'desk-leg-short';
  legS.position.set(WALL + DESK_D / 2, (DESK_H - 0.05) / 2, WALL + SHORT_L - 0.05);
  legS.castShadow = true;
  group.add(legS);

  const brace = roundedBox(DESK_L - 0.2, 0.05, 0.04, 0.015, woodMat);
  brace.name = 'desk-brace';
  brace.position.set(WALL + DESK_L / 2, DESK_H - 0.16, WALL + 0.06);
  group.add(brace);

  return group;
}

function buildDeskCabinet() {
  const group = new THREE.Group();
  group.name = NAME.deskCabinet;
  group.position.set(WALL + DESK_D / 2, 0, WALL + 1.5);

  const woodMat = clay(PALETTE.wood);
  const W = 0.6, H = CABINET_H, D = 0.6;

  const body = roundedBox(W, H, D, 0.02, woodMat);
  body.name = 'cabinet-body';
  body.position.set(0, H / 2, 0);
  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);

  for (let i = 0; i < 3; i++) {
    const drawer = roundedBox(W - 0.06, H / 3 - 0.02, 0.03, 0.015, clay(PALETTE.wood, { roughness: 0.85 }));
    drawer.name = `cabinet-drawer-${i}`;
    drawer.position.set(0, H / 6 + i * (H / 3), D / 2 + 0.005);
    drawer.castShadow = true;
    group.add(drawer);

    const handle = roundedBox(0.14, 0.02, 0.02, 0.008, clay(PALETTE.silver));
    handle.name = `cabinet-handle-${i}`;
    handle.position.set(0, H / 6 + i * (H / 3), D / 2 + 0.03);
    group.add(handle);
  }
  return group;
}

// ============================================================
// 椅子（桌前，面朝 -z 即朝桌子/窗）
// ============================================================

function buildChair() {
  const group = new THREE.Group();
  group.name = NAME.chair;
  group.position.set(WALL + 1.35, 0, WALL + DESK_D + 0.62);

  const seatMat = clay(PALETTE.chair);
  const metalMat = clay(0x7f8286, { roughness: 0.75 });

  const seat = roundedBox(0.46, 0.06, 0.44, 0.03, seatMat);
  seat.name = 'chair-seat';
  seat.position.set(0, SEAT_H, 0);
  seat.castShadow = true;
  group.add(seat);

  const backRest = roundedBox(0.44, 0.46, 0.06, 0.03, seatMat);
  backRest.name = 'chair-back';
  backRest.position.set(0, SEAT_H + 0.26, 0.2);
  backRest.rotation.x = -0.12;
  backRest.castShadow = true;
  group.add(backRest);

  const column = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.045, 0.34, 12), metalMat);
  column.name = 'chair-column';
  column.position.set(0, SEAT_H - 0.21, 0);
  column.castShadow = true;
  group.add(column);

  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2;
    const leg = roundedBox(0.24, 0.03, 0.04, 0.012, metalMat);
    leg.name = `chair-leg-${i}`;
    leg.position.set(Math.cos(a) * 0.12, 0.07, Math.sin(a) * 0.12);
    leg.rotation.y = -a;
    leg.castShadow = false;
    group.add(leg);

    const caster = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.028, 0.03, 10), clay(0x3a3a3c));
    caster.name = `chair-caster-${i}`;
    caster.rotation.z = Math.PI / 2;
    caster.position.set(Math.cos(a) * 0.23, 0.03, Math.sin(a) * 0.23);
    group.add(caster);
  }
  return group;
}

// ============================================================
// 显示器组（贴窗墙，面朝 +z 房间内）
// ============================================================

function buildMonitor() {
  const group = new THREE.Group();
  group.name = NAME.monitor;
  group.position.set(WALL + 1.35, DESK_H + 0.025, WALL + 0.3);

  const frameMat = clay(PALETTE.frameSilver, { roughness: 0.7, metalness: 0.35 });

  const base = roundedBox(0.28, 0.02, 0.2, 0.01, frameMat);
  base.name = 'monitor-base';
  base.position.set(0, 0.01, 0);
  base.castShadow = true;
  group.add(base);

  const stem = roundedBox(0.05, 0.16, 0.05, 0.015, frameMat);
  stem.name = 'monitor-stem';
  stem.position.set(0, 0.1, 0);
  stem.castShadow = true;
  group.add(stem);

  const body = roundedBox(0.6, 0.36, 0.03, 0.012, frameMat);
  body.name = 'monitor-body';
  body.position.set(0, 0.37, 0);
  body.castShadow = true;
  group.add(body);

  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.55, 0.3), glow(PALETTE.screen, 0.32));
  screen.name = NAME.screen;
  screen.position.set(0, 0.37, 0.017);
  group.add(screen);

  const anchor = new THREE.Object3D();
  anchor.name = NAME.screenAnchor;
  anchor.position.set(0, 0.37, 0.02);
  group.add(anchor);

  // 摄像头放显示器顶（坑 5）
  const camBody = roundedBox(0.1, 0.045, 0.05, 0.02, clay(0x40444a));
  camBody.name = NAME.webCamera;
  camBody.position.set(0, 0.575, 0);
  camBody.castShadow = true;
  group.add(camBody);

  const lens = new THREE.Mesh(
    new THREE.CylinderGeometry(0.013, 0.013, 0.02, 12),
    clay(0x1c1f24, { roughness: 0.4 })
  );
  lens.name = 'web-camera-lens';
  lens.rotation.x = Math.PI / 2;
  lens.position.set(0, 0.575, 0.033);
  group.add(lens);

  return group;
}

function buildKeyboard() {
  const group = new THREE.Group();
  group.name = NAME.keyboard;
  group.position.set(WALL + 1.35, DESK_H + 0.032, WALL + 0.66);
  const base = roundedBox(0.42, 0.02, 0.14, 0.008, clay(0x6f7378, { roughness: 0.75 }));
  base.name = 'keyboard-base';
  base.castShadow = true;
  base.receiveShadow = true;
  group.add(base);
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 10; c++) {
      const key = roundedBox(0.032, 0.008, 0.028, 0.003, clay(0xa8acb0, { roughness: 0.8 }));
      key.name = `key-${r}-${c}`;
      key.position.set(-0.185 + c * 0.041, 0.014, -0.045 + r * 0.042);
      group.add(key);
    }
  }
  return group;
}

function buildMouse() {
  const mouse = roundedBox(0.06, 0.035, 0.1, 0.026, clay(0x6f7378, { roughness: 0.7 }));
  mouse.name = NAME.mouse;
  mouse.position.set(WALL + 1.72, DESK_H + 0.043, WALL + 0.64);
  mouse.rotation.y = -0.2;
  mouse.castShadow = true;
  return mouse;
}

function buildClock() {
  const group = new THREE.Group();
  group.name = NAME.clock;
  group.position.set(WALL + 2.15, DESK_H + 0.025, WALL + 0.38);

  const silverMat = clay(PALETTE.silver, { roughness: 0.45, metalness: 0.55 });

  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.05, 22), silverMat);
  body.name = 'clock-body';
  body.position.y = 0.085;
  body.castShadow = true;
  group.add(body);

  const face = new THREE.Mesh(new THREE.CircleGeometry(0.066, 26), clay(0xf7f6f2));
  face.name = 'clock-face';
  face.position.set(0, 0.085, 0.026);
  group.add(face);

  const hour = roundedBox(0.008, 0.038, 0.004, 0.002, clay(0x2c2f33));
  hour.name = 'clock-hand-hour';
  hour.position.set(0.009, 0.097, 0.029);
  hour.rotation.z = -0.6;
  group.add(hour);

  const minute = roundedBox(0.006, 0.052, 0.004, 0.002, clay(0x2c2f33));
  minute.name = 'clock-hand-minute';
  minute.position.set(0.015, 0.097, 0.03);
  minute.rotation.z = 0.9;
  group.add(minute);

  // 双铃 + 提手（参考图是老式双铃闹钟）
  [-0.075, 0.075].forEach((x, i) => {
    const bell = new THREE.Mesh(
      new THREE.SphereGeometry(0.035, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2),
      silverMat
    );
    bell.name = `clock-bell-${i}`;
    bell.position.set(x, 0.115, 0);
    bell.rotation.z = i === 0 ? 0.5 : -0.5;
    bell.castShadow = true;
    group.add(bell);
  });
  const handle = new THREE.Mesh(new THREE.TorusGeometry(0.026, 0.006, 6, 12, Math.PI), silverMat);
  handle.name = 'clock-handle';
  handle.position.set(0, 0.145, 0);
  handle.castShadow = true;
  group.add(handle);

  [[-0.055, 'clock-foot-0'], [0.055, 'clock-foot-1']].forEach(([x, name]) => {
    const foot = roundedBox(0.03, 0.02, 0.04, 0.008, silverMat);
    foot.name = name;
    foot.position.set(x, 0.01, 0);
    group.add(foot);
  });

  return group;
}

// ============================================================
// 盆栽（显示器旁）
// ============================================================

function buildPlant() {
  const group = new THREE.Group();
  group.name = NAME.plant;
  group.position.set(WALL + 1.95, DESK_H + 0.025, WALL + 0.34);

  const pot = new THREE.Mesh(
    new THREE.CylinderGeometry(0.075, 0.06, 0.1, 14),
    clay(PALETTE.white, { roughness: 0.85 })
  );
  pot.name = NAME.plantPot;
  pot.position.y = 0.05;
  pot.castShadow = true;
  pot.receiveShadow = true;
  group.add(pot);

  const soil = new THREE.Mesh(new THREE.CircleGeometry(0.07, 14), clay(0x4a3d33));
  soil.name = 'plant-soil';
  soil.rotation.x = -Math.PI / 2;
  soil.position.y = 0.1;
  group.add(soil);

  const leafGeo = new THREE.ConeGeometry(0.03, 0.16, 4);
  const leafMat = new THREE.MeshStandardMaterial({
    color: PALETTE.leafLight, roughness: 0.85, metalness: 0, flatShading: true,
  });
  const leafMatDark = new THREE.MeshStandardMaterial({
    color: PALETTE.leafDark, roughness: 0.85, metalness: 0, flatShading: true,
  });
  for (let i = 0; i < 7; i++) {
    const a = (i / 7) * Math.PI * 2;
    const leaf = new THREE.Mesh(leafGeo, i % 2 === 0 ? leafMat : leafMatDark);
    leaf.name = `plant-leaf-${i}`;
    leaf.position.set(Math.cos(a) * 0.035, 0.185 + (i % 3) * 0.024, Math.sin(a) * 0.035);
    leaf.rotation.set(Math.sin(a) * 0.5, a, Math.cos(a) * -0.5);
    leaf.castShadow = false;
    group.add(leaf);
  }
  return group;
}

// ============================================================
// 水杯（在矮柜上）
// ============================================================

function buildMug() {
  const group = new THREE.Group();
  group.name = NAME.mug;
  group.position.set(WALL + DESK_D / 2, CABINET_H + 0.025, WALL + 1.5);

  const whiteMat = clay(PALETTE.white, { roughness: 0.55 });

  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(0.04, 0.035, 0.1, 18, 1, true),
    whiteMat
  );
  body.name = 'mug-body';
  body.position.y = 0.05;
  body.material.side = THREE.DoubleSide;
  body.castShadow = true;
  group.add(body);

  const bottom = new THREE.Mesh(new THREE.CircleGeometry(0.035, 18), whiteMat);
  bottom.name = 'mug-bottom';
  bottom.rotation.x = -Math.PI / 2;
  group.add(bottom);

  const water = new THREE.Mesh(
    new THREE.CylinderGeometry(0.034, 0.032, 0.058, 18),
    new THREE.MeshStandardMaterial({
      color: 0x9fc4d8, roughness: 0.15, metalness: 0, transparent: true, opacity: 0.75,
    })
  );
  water.name = 'mug-water';
  water.position.y = 0.034;
  group.add(water);

  const handle = new THREE.Mesh(new THREE.TorusGeometry(0.028, 0.007, 6, 12, Math.PI * 1.2), whiteMat);
  handle.name = 'mug-handle';
  handle.position.set(0.046, 0.053, 0);
  handle.rotation.set(0, Math.PI / 2, -0.3);
  handle.castShadow = true;
  group.add(handle);

  return group;
}

// ============================================================
// 实体墙件（x = -3）：镜子 + 日历
// ============================================================

function buildMirror() {
  const group = new THREE.Group();
  group.name = NAME.mirror;
  group.position.set(WALL + 0.04, 1.42, -0.55);
  group.rotation.y = Math.PI / 2;

  const frame = new THREE.Mesh(
    new THREE.TorusGeometry(0.4, 0.04, 8, 26),
    clay(PALETTE.mirrorFrame, { roughness: 0.65 })
  );
  frame.name = 'mirror-frame';
  frame.scale.set(1, 1.35, 1);
  frame.castShadow = true;
  group.add(frame);

  const glass = new THREE.Mesh(
    new THREE.CircleGeometry(0.385, 26),
    new THREE.MeshStandardMaterial({ color: 0xc8d4dc, roughness: 0.1, metalness: 0.6 })
  );
  glass.name = 'mirror-glass';
  glass.scale.set(1, 1.35, 1);
  glass.position.x = -0.014;
  group.add(glass);

  return group;
}

function buildCalendar() {
  const group = new THREE.Group();
  group.name = NAME.calendar;
  group.position.set(WALL + 0.03, 1.92, -1.85);
  group.rotation.y = Math.PI / 2;

  const paper = roundedBox(0.46, 0.6, 0.02, 0.008, clay(PALETTE.white));
  paper.name = 'calendar-paper';
  paper.castShadow = true;
  group.add(paper);

  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.028, 0.006, 6, 12), clay(PALETTE.silver));
  ring.name = 'calendar-ring';
  ring.position.set(0, 0.32, 0.012);
  group.add(ring);

  const gridMat = clay(0xd2ccc0, { roughness: 0.9 });
  for (let c = 0; c < 6; c++) {
    for (let r = 0; r < 5; r++) {
      const cell = new THREE.Mesh(new THREE.PlaneGeometry(0.056, 0.07), gridMat);
      cell.name = `calendar-cell-${c}-${r}`;
      cell.position.set(-0.16 + c * 0.064, 0.19 - r * 0.092, 0.013);
      group.add(cell);
    }
  }
  return group;
}

function buildSkirting() {
  const group = new THREE.Group();
  group.name = 'skirting';
  const mat = clay(0xe6dccb, { roughness: 0.9 });
  const H = 0.09, T = 0.035;
  const along = roundedBox(T, H, ROOM.size, 0.008, mat);
  along.name = 'skirting-solid-wall';
  along.position.set(WALL + T / 2, H / 2, 0);
  group.add(along);
  return group;
}

// ============================================================
// 照明：吊灯悬在桌面上方
// ============================================================

function buildLights() {
  const group = new THREE.Group();
  group.name = 'lights';

  const hemi = new THREE.HemisphereLight(PALETTE.skyCool, PALETTE.floor, 0.85);
  hemi.name = 'light-hemi';
  group.add(hemi);

  // 顶部柔光：不投影，只把地板从死黑里捞出来
  const fill = new THREE.DirectionalLight(0xfff2e2, 0.75);
  fill.name = 'light-fill-top';
  fill.position.set(1.5, 5.5, 2.5);
  group.add(fill);

  const ambient = new THREE.AmbientLight(0xdce6f0, 0.35);
  ambient.name = 'light-ambient';
  group.add(ambient);

  const lampPos = [-1.75, ROOM.wallHeight - 0.72, -2.2];
  const lampGroup = new THREE.Group();
  lampGroup.name = NAME.lamp;
  lampGroup.position.set(...lampPos);

  const cord = new THREE.Mesh(
    new THREE.CylinderGeometry(0.005, 0.005, 0.68, 6),
    clay(0x33333a)
  );
  cord.name = 'lamp-cord';
  cord.position.y = 0.34;
  lampGroup.add(cord);

  const shade = new THREE.Mesh(
    new THREE.ConeGeometry(0.24, 0.2, 24, 1, true),
    clay(PALETTE.white, { side: THREE.DoubleSide, roughness: 0.9 })
  );
  shade.name = 'lamp-shade';
  shade.castShadow = true;
  lampGroup.add(shade);

  const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.05, 14, 10), glow(PALETTE.lampWarm, 2.0));
  bulb.name = 'lamp-bulb';
  bulb.position.y = -0.06;
  lampGroup.add(bulb);

  group.add(lampGroup);

  const point = new THREE.PointLight(PALETTE.lampWarm, 20, 7.5, 2);
  point.name = 'light-lamp';
  point.position.set(...lampPos);
  point.castShadow = true;
  point.shadow.mapSize.set(512, 512);
  point.shadow.bias = -0.003;
  point.shadow.normalBias = 0.02;
  point.shadow.radius = 3;
  group.add(point);

  const spot = new THREE.SpotLight(PALETTE.lampWarm, 26, 6.5, Math.PI / 4, 0.8, 2);
  spot.name = 'light-spot';
  spot.position.set(...lampPos);
  spot.target.position.set(lampPos[0], 0, lampPos[2] + 0.5);
  spot.castShadow = true;
  spot.shadow.mapSize.set(1024, 1024);
  spot.shadow.radius = 4;
  spot.shadow.bias = -0.004;
  spot.shadow.normalBias = 0.02;
  group.add(spot);
  group.add(spot.target);

  // 窗外冷光：从窗墙（z = -3）打进来
  const sky = new THREE.DirectionalLight(PALETTE.skyCool, 1.0);
  sky.name = 'light-sky';
  sky.position.set(1.2, 3.4, -7.5);
  group.add(sky);

  return group;
}

// ============================================================
// 组装
// ============================================================

export function createRoom({ grid = true } = {}) {
  const room = new THREE.Group();
  room.name = 'room';

  room.add(buildFloor());
  room.add(buildSolidWall());   // x = -3：镜子 + 日历（画面左）
  room.add(buildWindow());       // z = -3：整面落地窗（画面右）
  room.add(buildSkirting());

  room.add(buildDesk());
  room.add(buildDeskCabinet());
  room.add(buildChair());
  room.add(buildMonitor());
  room.add(buildKeyboard());
  room.add(buildMouse());
  room.add(buildClock());
  room.add(buildPlant());
  room.add(buildMug());

  room.add(buildMirror());
  room.add(buildCalendar());

  room.add(buildLights());

  if (grid) {
    const gridHelper = new THREE.GridHelper(ROOM.size, ROOM.size, 0x8d8375, 0x8d8375);
    gridHelper.name = 'grid';
    gridHelper.position.y = 0.002;
    gridHelper.material.opacity = 0.28;
    gridHelper.material.transparent = true;
    room.add(gridHelper);
  }

  // 伙伴占位（XQ-004 建几何体）：坐在椅子上
  const partnerAnchor = new THREE.Object3D();
  partnerAnchor.name = NAME.partner;
  partnerAnchor.position.set(WALL + 1.35, SEAT_H, WALL + DESK_D + 0.62);
  room.add(partnerAnchor);

  return room;
}

export { DESK_H, DESK_L, DESK_D, CABINET_H, SEAT_H };
