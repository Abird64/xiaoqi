/**
 * W6 · 3D 房间场景 —— XQ-008「Three.js 空房间骨架跑通（能转相机）」
 * owner: A（张鹏）｜备份: B
 *
 * ── 尺寸与坐标约定（后续任何人加家具都按这个来，别各写各的）──
 *   单位：1 = 1 米；y 轴朝上（Three.js 默认）
 *   地面 y = 0；房间 6m × 6m；墙高 3m
 *   墙角在一侧：后墙 z = -3、左墙 x = -3，其余两面敞开（给相机留机位）
 *
 * 配色是占位值，M3 美术由 B 定（XQ-010 美术风格参考收集）
 */
import * as THREE from 'three';

export const ROOM = { size: 6, wallHeight: 3 };

// 占位配色（M3 会换成 low-poly / 粘土风，见 XQ-010）
const COLOR = {
  floor: 0xc9b8a2,
  wall: 0xe9e3da,
  grid: 0x8d8375,
};

export function createRoom({ grid = true } = {}) {
  const room = new THREE.Group();
  room.name = 'room';

  const { size, wallHeight } = ROOM;

  // ---- 地面 ----
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(size, size),
    new THREE.MeshStandardMaterial({ color: COLOR.floor, roughness: 0.95 })
  );
  floor.name = 'floor';
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  room.add(floor);

  // ---- 两面墙（成直角，做出墙角）----
  // side: DoubleSide —— 房间只做了两面墙，相机绕到墙背后时单面材质会被背面剔除、
  // 整面墙凭空消失；双面渲染让任意机位都有画面（M3 录视频要绕机位）。
  const backWall = new THREE.Mesh(
    new THREE.PlaneGeometry(size, wallHeight),
    new THREE.MeshStandardMaterial({ color: COLOR.wall, roughness: 1, side: THREE.DoubleSide })
  );
  backWall.name = 'wall-back';
  backWall.position.set(0, wallHeight / 2, -size / 2);
  backWall.receiveShadow = true;
  room.add(backWall);

  const leftWall = new THREE.Mesh(
    new THREE.PlaneGeometry(size, wallHeight),
    new THREE.MeshStandardMaterial({ color: COLOR.wall, roughness: 1, side: THREE.DoubleSide })
  );
  leftWall.name = 'wall-left';
  leftWall.position.set(-size / 2, wallHeight / 2, 0);
  leftWall.rotation.y = Math.PI / 2;
  leftWall.receiveShadow = true;
  room.add(leftWall);

  // ---- 尺度参照（开发期用，验收时可用 ?grid=0 关掉）----
  if (grid) {
    const gridHelper = new THREE.GridHelper(size, size, COLOR.grid, COLOR.grid);
    gridHelper.name = 'grid';
    gridHelper.position.y = 0.002; // 抬一点，避免与地面 z-fighting
    gridHelper.material.opacity = 0.35;
    gridHelper.material.transparent = true;
    room.add(gridHelper);
  }

  // ---- 整体光照（M3-1「有整体光照」的地基；家具进来后再开阴影）----
  const hemi = new THREE.HemisphereLight(0xffffff, COLOR.floor, 1.1);
  hemi.name = 'light-hemi';
  room.add(hemi);

  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.name = 'light-key';
  key.position.set(3.5, 5.5, 2.5);
  room.add(key);

  const fill = new THREE.DirectionalLight(0xdfe8ff, 0.5);
  fill.name = 'light-fill';
  fill.position.set(-4, 2.5, -3);
  room.add(fill);

  // TODO(M3-1)：墙角 + 桌椅 + 电脑（低多边形），随 W6 的 M3 验收一并补
  return room;
}
