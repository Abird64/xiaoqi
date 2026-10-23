/**
 * 相机与轨道控制 —— XQ-003 机位对齐基准图 + XQ-009 flyTo
 * owner: A（张鹏）
 *
 * 交互：OrbitControls 拖拽旋转 / 滚轮缩放 / 右键平移。
 * 约束：不许钻到地板下（maxPolarAngle）、距离有上下限，免得演示时一滚轮钻进墙里出不来。
 *
 * M3-1 机位调整（依据 04-视觉参考/房间-建模基准.jpeg）：
 *   原 (4.4, 3.2, 4.8) fov 50 → 视点过高、房间在画面里偏小，桌面看不到物件细节。
 *   新机位视点约 1.55m（略高于桌面 0.75m 与椅子座面 0.45m），fov 42。
 *
 * ── 朝向要点（踩过一次坑才写对）──
 *   房间只有**左墙 x=-3** 与**窗墙 z=-3**（落地窗整面）。
 *   基准图是「站在敞口侧往房间里看」：**左墙占画面左 1/3、落地窗占右 2/3**。
 *   所以机位必须在 **+x 一侧**、镜头朝 **-x** 方向。
 *   第一版把相机放在 (3.1, 1.55, 3.2) 却沿用旧朝向，镜头朝 -x-z 看左后角，
 *   结果落地窗整个在画面外，右侧全是空背景色 —— 窗景消失。
 *   现用 spherical 直接给出「方位角 + 距离」，不再靠 position 试。
 *
 * 初始机位可用 URL 参数覆盖（验收与录像要固定机位，见 README）：
 *   ?az=42&el=15&dist=7.9
 *
 * XQ-009 新增 flyTo：HUD 演示工具条的镜头快捷跳转（easeInOutQuad，
 * 飞行期间临时禁用 controls，避免 damping 与直接写 position 相互打架）。
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export function createViewer(canvas, { azimuth, elevation, distance } = {}) {
  // fov 42：基准图的构图是「近一点、广一点」，50 会把房间压小、边缘拉出畸变
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 1.2;
  controls.maxDistance = 14;
  controls.maxPolarAngle = Math.PI / 2 - 0.05; // 视线不低于地平线

  // ── 机位：站在 (+x,+z) 墙角外侧，日历墙在左、窗墙在右 ──
  //   几何依据（验算）：机位在 (+x,+z) 时，x=-3 那面墙必然落画面左、z=-3 那面墙必然落画面右。
  //   所以实体墙开 x=-3、窗墙开 z=-3（见 room.js「布局定稿」）。
  //   参考图构图：实体墙占左 1/3（椭圆镜+挂历）、整面窗占右 2/3、桌椅在中段、地板占下部、吊灯在桌面上方。
  //   从 6 组候选里选定这一组（关键点 6/6 入画 + 镜子与桌面占比最接近参考图）。
  const DEFAULT_CAM = {
    position: [3.0, 1.8, 1.8],
    target: [-2.2, 1.0, -1.6],
  };
  controls.target.set(...DEFAULT_CAM.target);
  camera.position.set(...DEFAULT_CAM.position);
  camera.lookAt(...DEFAULT_CAM.target);
  if (azimuth !== undefined || elevation !== undefined || distance !== undefined) {
    applyOrbit(camera, controls.target, { azimuth, elevation, distance });
  }
  controls.update();

  // ── 相机飞行（XQ-009 HUD 工具条用）──
  let flight = null;

  /**
   * 平滑飞向指定机位。durationMs 默认 900ms，easeInOutQuad。
   * 飞行期间禁用 controls（用户输入在飞行结束后恢复生效），
   * 结束后交还 controls 并 update 一次，让 damping 状态连续。
   */
  function flyTo(position, target, durationMs = 900) {
    flight = {
      t0: performance.now(),
      dur: Math.max(1, durationMs),
      fromPos: camera.position.clone(),
      toPos: new THREE.Vector3(position[0], position[1], position[2]),
      fromTgt: controls.target.clone(),
      toTgt: new THREE.Vector3(target[0], target[1], target[2]),
    };
    controls.enabled = false;
  }

  function update() {
    if (flight) {
      const k = Math.min(1, (performance.now() - flight.t0) / flight.dur);
      const e = k < 0.5 ? 2 * k * k : 1 - ((-2 * k + 2) ** 2) / 2;
      camera.position.lerpVectors(flight.fromPos, flight.toPos, e);
      controls.target.lerpVectors(flight.fromTgt, flight.toTgt, e);
      camera.lookAt(controls.target);
      if (k >= 1) {
        flight = null;
        controls.enabled = true;
      }
    }
    controls.update();
  }

  return {
    camera,
    controls,
    flyTo,
    resize(width, height) {
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    },
    update,
  };
}

/**
 * 把相机摆到指定球面机位。走的是与 OrbitControls 同一套球面坐标，
 * 所以这里转得对，拖拽就一定转得对。
 * azimuth：绕 y 轴方位角，度；0 = 从 +z 方向看，90 = 从 +x 方向看
 * elevation：仰角，度；0 = 与目标同高，90 = 正上方俯视
 * distance：与目标的距离，米
 */
export function applyOrbit(camera, target, { azimuth, elevation, distance }) {
  if (azimuth === undefined && elevation === undefined && distance === undefined) return;

  const spherical = new THREE.Spherical().setFromVector3(
    camera.position.clone().sub(target)
  );
  if (Number.isFinite(azimuth)) spherical.theta = THREE.MathUtils.degToRad(azimuth);
  if (Number.isFinite(elevation)) spherical.phi = THREE.MathUtils.degToRad(90 - elevation);
  if (Number.isFinite(distance)) spherical.radius = distance;
  spherical.makeSafe();

  camera.position.copy(target).add(new THREE.Vector3().setFromSpherical(spherical));
}
