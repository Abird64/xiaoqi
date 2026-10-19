/**
 * 家具与陈设 —— XQ-003「M3-1 房间骨架补齐」+ XQ-009「视觉精修」
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
 *   **窗墙   z = -3**  整面落地窗 + 城市景观     （画面右 2/3，光源）
 *   **敞口   z = +3 / x = +3**  留机位，不立任何东西
 *
 * ⚠️ XQ-009 只改视觉层（贴图 / 窗外景观 / 光晕 / 闹钟造型 / 绿植造型），
 *    几何布局、坐标、机位、6 光源结构一律不动（XQ-003 定稿）。
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
import { makeWallpaperTexture, makeFloorTexture, makeCityTexture, makeGlowTexture } from './textures.js';

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
  // G2：长条木地板程序化贴图（textures.js，repeat 6×6 → 板宽 0.25m）。
  // color 用白色 tint：贴图本身已含基色，再乘 PALETTE.floor 会双重变暗。
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.size, ROOM.size),
    clay(0xffffff, { roughness: 0.88, map: makeFloorTexture() })
  );
  floor.name = NAME.floor;
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  return floor;
}

/** x = -3 → 实体墙：镜子 + 日历本挂这面 */
function buildSolidWall() {
  // G1：暖米白底 + 菱形网格暗纹（textures.js，repeat 3×3 → 12 纹样周期/墙）
  const wall = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.size, ROOM.wallHeight),
    clay(0xffffff, { roughness: 0.9, map: makeWallpaperTexture(), side: THREE.DoubleSide })
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

  // G3：城市景观贴图（天空渐变 + 3 层楼群，远浅近深大气透视）。
  // 一张大 plane 取代 XQ-003 的「单色天 + 6 块纯色矩形」；
  // MeshBasicMaterial（自表现，不受房间灯光影响——窗外是另一个光源世界）。
  // 1024×640 ≈ 窗 4.8m×3m 的 1.6 宽高比，不变形。
  const city = new THREE.Mesh(
    new THREE.PlaneGeometry(W, H),
    new THREE.MeshBasicMaterial({ map: makeCityTexture() })
  );
  city.name = 'window-city';
  city.position.set(X_MID, H / 2, -0.05);
  group.add(city);

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

// ============================================================
// G6 桌面闹钟（双铃）—— XQ-009 整体重做
// ============================================================

/**
 * XQ-003 旧版被组长判「建的很失败」（银色圆柱 + 两片半球铃直愣愣插在顶上、表盘无刻度）；
 * XQ-009 重做为「双铃 + 刻度表盘」后，组长仍判「不像」（2026-10-14，XQ-010）：
 * 金属银 + 0.55 metalness 在暖环境光下发冷发暗、铃小、主体扁。
 * 本版照参考图收敛：
 *   - 粘土奶油白主体与铃（metalness 0、roughness 0.9，对齐美术规格「亚光无高光」）
 *   - 双铃放大外张（双铃闹钟第一识别特征）、主体加厚圆鼓、提手加粗
 *   - 刻度/指针深棕，白盘柔和对比
 *   - 读法结构保留：白表盘 + 12 刻度 + 时针分针 + 铃锤 + 拱形提手 + 双脚
 */
function buildClock() {
  const group = new THREE.Group();
  group.name = NAME.clock;
  group.position.set(WALL + 2.15, DESK_H + 0.025, WALL + 0.38);
  // XQ-014：表盘朝向 65°→0°，法线 (0,0,1) 纯 +z，与显示器屏幕同向、正对椅子。
  // 65° 是 XQ-011 为消「默认机位饼读感」设的斜角；XQ-013 盘体竖正后结构已成立，
  // 组长要求朝向对齐场景逻辑（闹钟/显示器都面朝使用者），故归零同向。
  group.rotation.y = 0;

  // 粘土奶油白（亚光无高光，对齐 materials.js 美术规格）
  const creamMat = clay(0xf2ead8, { roughness: 0.9 });
  const darkMat = clay(0x6b543a, { roughness: 0.8 });  // 深棕：刻度/指针/轴帽/铃锤
  const faceMat = clay(0xfefdfa, { roughness: 0.7 }); // 表盘白（提亮，与奶油白主体拉开色差）

  // 脚（先落地，后盖上头）
  [[-0.055, 'clock-foot-0'], [0.055, 'clock-foot-1']].forEach(([x, name]) => {
    const foot = roundedBox(0.038, 0.024, 0.055, 0.008, creamMat);
    foot.name = name;
    foot.position.set(x, 0.012, 0);
    group.add(foot);
  });

  // XQ-012 A1：主体改「盘式」——圆盘厚 0.05（直径 0.185，直径:厚度 ≈ 3.7:1）
  // 参考图为「圆盘即表盘」结构；XQ-011 的桶式（厚 0.075 + 小盘贴桶面）在斜俯视角
  // 下贴盘边缘与刻度圈层层投影成环纹，读作「贴表的桶」。
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.0925, 0.0925, 0.05, 24), creamMat);
  body.name = 'clock-body';
  // XQ-013 A1：盘体竖正——CylinderGeometry 默认轴向 Y（圆面朝上下），表盘置局部 z 即埋主体内。
  // rotation.x = π/2 把轴向扳到 Z：圆面朝 +z（观众），表盘部件贴盘面。
  body.rotation.x = Math.PI / 2;
  // 盘中心 = 脚顶 0.024 + 盘半径 0.0925，盘底缘坐两脚顶
  body.position.y = 0.1165;
  body.castShadow = true;
  group.add(body);

  // XQ-012 A2：表盘覆盖全盘面（半径 0.090，贴主体 0.0925 内侧 2.5mm）
  // 盘面即表盘面，刻度/指针直接读在盘面上，对齐参考图结构
  const face = new THREE.Mesh(new THREE.CircleGeometry(0.090, 28), faceMat);
  face.name = 'clock-face';
  face.position.set(0, 0.1165, 0.027);
  group.add(face);

  // 表盘外圈深棕环（贴盘缘勾边）
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.090, 0.005, 8, 28), darkMat);
  ring.name = 'clock-face-ring';
  ring.position.set(0, 0.1165, 0.027);
  group.add(ring);

  // 12 刻度：3/6/9/12 位加长
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    const tick = roundedBox(0.007, i % 3 === 0 ? 0.016 : 0.009, 0.003, 0.001, darkMat);
    tick.name = `clock-tick-${i}`;
    tick.position.set(Math.sin(a) * 0.056, 0.1165 + Math.cos(a) * 0.056, 0.030);
    tick.rotation.z = -a;
    group.add(tick);
  }

  // 时针 / 分针 / 轴帽
  const hour = roundedBox(0.008, 0.032, 0.003, 0.001, darkMat);
  hour.name = 'clock-hand-hour';
  hour.position.set(-0.009, 0.130, 0.031);
  hour.rotation.z = -0.5;
  group.add(hour);

  const minute = roundedBox(0.006, 0.045, 0.003, 0.001, darkMat);
  minute.name = 'clock-hand-minute';
  minute.position.set(0.004, 0.135, 0.032);
  minute.rotation.z = 1.1;
  group.add(minute);

  const cap = new THREE.Mesh(new THREE.SphereGeometry(0.0065, 8, 6), darkMat);
  cap.name = 'clock-hand-cap';
  cap.position.set(0, 0.1165, 0.033);
  group.add(cap);

  // 双铃：短柄外倾 0.42rad → 大半球铃 → 铃下铃锤
  [-1, 1].forEach((s, i) => {
    const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.009, 0.011, 0.04, 10), creamMat);
    stem.name = `clock-bell-stem-${i}`;
    // XQ-013 回修（审核非阻塞项）：柄长 0.03→0.04、心上移 0.150→0.185，
    // 柄 [0.165,0.205] 底埋盘面（x=0.058 处盘面上缘 0.1886）、顶贴铃赤道 0.205，恢复柄-铃连接
    stem.position.set(s * 0.058, 0.185, 0);
    stem.rotation.z = -s * 0.42;
    stem.castShadow = true;
    group.add(stem);

    const bell = new THREE.Mesh(
      new THREE.SphereGeometry(0.046, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2),
      creamMat
    );
    bell.name = `clock-bell-${i}`;
    bell.position.set(s * 0.082, 0.205, 0);
    bell.rotation.z = -s * 0.42;
    bell.castShadow = true;
    group.add(bell);

    const hammer = new THREE.Mesh(new THREE.SphereGeometry(0.011, 8, 6), darkMat);
    hammer.name = `clock-hammer-${i}`;
    hammer.position.set(s * 0.066, 0.185, 0);
    group.add(hammer);
  });

  // 提手：两铃之间的半拱（加粗，与放大后的铃匹配）
  const handle = new THREE.Mesh(new THREE.TorusGeometry(0.082, 0.01, 8, 18, Math.PI), creamMat);
  handle.name = 'clock-handle';
  handle.position.set(0, 0.205, 0);
  handle.castShadow = true;
  group.add(handle);

  return group;
}

// ============================================================
// G7 盆栽（显示器旁）—— XQ-009 整体重做
// ============================================================

/**
 * XQ-003 旧版被组长判「建的很失败」：白圆柱盆 + 7 根圆锥呈刺球，读不出是植物。
 * 本版照参考图重做：
 *   - 梯形盆（上口 0.164、底 0.116、高 0.1）+ 盆沿 + 土面
 *   - 桨形叶 7 片：球形缩成扁长透镜；内 3 片高而直、外 4 片矮而张，扇形排布
 *   - 两色绿交替 + flatShading，保留「硬边 low-poly」的美术规格（原型 §8.2）
 */
function buildPlant() {
  const group = new THREE.Group();
  group.name = NAME.plant;
  group.position.set(WALL + 1.95, DESK_H + 0.025, WALL + 0.34);

  // 梯形盆 + 盆沿
  const potMat = clay(0xe8e6e0, { roughness: 0.85 });
  const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.082, 0.058, 0.1, 16), potMat);
  pot.name = NAME.plantPot;
  pot.position.y = 0.05;
  pot.castShadow = true;
  pot.receiveShadow = true;
  group.add(pot);

  const rim = new THREE.Mesh(new THREE.CylinderGeometry(0.089, 0.083, 0.02, 16), potMat);
  rim.name = 'plant-pot-rim';
  rim.position.y = 0.1;
  rim.castShadow = true;
  group.add(rim);

  const soil = new THREE.Mesh(new THREE.CircleGeometry(0.08, 16), clay(0x4a3d33));
  soil.name = 'plant-soil';
  soil.rotation.x = -Math.PI / 2;
  soil.position.y = 0.101;
  group.add(soil);

  // 桨形叶：单位球缩成 (宽 0.034, 长 h, 厚 0.018) 的圆透镜，长轴对齐生长方向
  const leafGeo = new THREE.SphereGeometry(1, 12, 8);
  const leafMat = new THREE.MeshStandardMaterial({
    color: PALETTE.leafLight, roughness: 0.85, metalness: 0, flatShading: true,
  });
  const leafMatDark = new THREE.MeshStandardMaterial({
    color: PALETTE.leafDark, roughness: 0.85, metalness: 0, flatShading: true,
  });

  // [方位角°, 叶长 m, 外张角°, 基部半径 m] —— 非等差错开、内高外垂、基部散开
  // XQ-015：原 7 片等差 52° 全竖直同点出发读作「放射绿刺」；
  // 改 8 片非等差，外叶 42~62° 下垂，基部沿盆内 0.02~0.05 圆周错开
  const leaves = [
    [0, 0.165, 12, 0.020], [38, 0.150, 24, 0.030], [91, 0.158, 15, 0.020],
    [133, 0.128, 48, 0.045], [180, 0.145, 20, 0.025], [227, 0.118, 62, 0.050],
    [281, 0.122, 55, 0.045], [330, 0.135, 30, 0.035],
  ];
  const UP = new THREE.Vector3(0, 1, 0);
  leaves.forEach(([deg, len, tilt, base], i) => {
    const a = (deg / 180) * Math.PI;
    const t = (tilt * Math.PI) / 180;
    // 生长方向：竖直方向绕方位角外张 tilt
    const dir = new THREE.Vector3(
      Math.cos(a) * Math.sin(t), Math.cos(t), Math.sin(a) * Math.sin(t)
    ).normalize();

    const leaf = new THREE.Mesh(leafGeo, i % 2 === 0 ? leafMat : leafMatDark);
    leaf.name = `plant-leaf-${i}`;
    leaf.scale.set(0.034, len, 0.018);
    leaf.quaternion.setFromUnitVectors(UP, dir);
    leaf.position
      .set(Math.cos(a) * base, 0.101, Math.sin(a) * base)
      .addScaledVector(dir, len * 0.42);
    leaf.castShadow = true;
    group.add(leaf);
  });

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

  // G4：辉光 sprite —— 径向渐变 + 加色混合，包在灯泡外。
  // 不动 6 光源结构（这是「看得见的暖」，不是新光源）；depthWrite 关掉避免挡家具。
  const glowSprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: makeGlowTexture(),
      color: PALETTE.lampWarm,
      transparent: true,
      opacity: 0.78,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  glowSprite.name = 'lamp-glow';
  glowSprite.scale.set(0.78, 0.78, 1);
  glowSprite.position.y = -0.06;
  lampGroup.add(glowSprite);

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
