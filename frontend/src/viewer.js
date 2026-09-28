/**
 * 相机与轨道控制 —— XQ-008 的「能转相机」
 * owner: A（张鹏）
 *
 * 交互：OrbitControls 拖拽旋转 / 滚轮缩放 / 右键平移。
 * 约束：不许钻到地板下（maxPolarAngle）、距离有上下限，免得演示时一滚轮钻进墙里出不来。
 *
 * 初始机位可用 URL 参数覆盖（验收与录像要固定机位，见 README）：
 *   ?az=42&el=15&dist=7.9
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export function createViewer(canvas, { azimuth, elevation, distance } = {}) {
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.set(4.4, 3.2, 4.8);

  const controls = new OrbitControls(camera, canvas);
  controls.target.set(-0.7, 1.1, -0.9); // 看向墙角
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 2;
  controls.maxDistance = 14;
  controls.maxPolarAngle = Math.PI / 2 - 0.05; // 视线不低于地平线

  applyOrbit(camera, controls.target, { azimuth, elevation, distance });
  controls.update();

  return {
    camera,
    controls,
    resize(width, height) {
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    },
    update() {
      controls.update();
    },
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
