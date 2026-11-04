/**
 * 健康伙伴 —— 骨骼驱动粘土风小怪（XQ-004 · M3 状态驱动角色）
 *
 * 采用 Blender 绑骨蒙皮建模资产：public/assets/monster.glb
 *   - 几何分件完成：腿部独立壳体，不再与下腹布尔粘连。
 *   - 骨骼 Rest Pose 规范化：插入 Pelvis 吸收父子反向，Thigh/Shin 的 Rest 四元数无 180° 翻转。
 *   - 尾巴根部收紧并侧弯：坐姿下自然顺垂，不再硬捅椅背。
 *
 * 姿态规约：
 *   - 支持 5 大核心姿态：unknown（静止/中性）、upright（端坐精神）、slouch（驼背弯腰）、desk_hunch（伏案敲键盘）、away（离开看风景）
 *   - drinking（喝水）：协议 §4.1 明确保留枚举但不做独立动画，平滑降级为 upright 端坐，不抛异常。
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export const PARTNER_PALETTE = {
  skin: 0x2f5b96,
  horn: 0x2a5290,
  sclera: 0xf2eee4,
  iris: 0x223144,
  pupil: 0x0c1015,
  mouth: 0x101821,
  fang: 0xf7f4ec,
};

/**
 * 姿态目标配置
 */
const POSES = {
  // 1. 坐直（upright）：端坐、腰背挺直、小手自然搭在桌面上敲键盘、小腿垂直垂在椅前
  upright: {
    sink: 0,
    hipsPitch: 0.02, hipsYaw: 0, hipsRoll: 0,
    spinePitch: 0.02, chestPitch: -0.02,
    headPitch: -0.04, headYaw: 0.02, headRoll: 0,
    armReachL: 0.85, armReachR: 0.85,
    armSpreadL: 0.20, armSpreadR: 0.20,
    forearmBendL: 0.40, forearmBendR: 0.40,
    thighAngle: -1.36, shinAngle: 1.48, footAngle: -0.24,
    awayOffsetZ: 0, awayOffsetX: 0, awayRotationY: 0,
    breath: 1,
  },
  // 2. 驼背（slouch）：身子后瘫窝进椅背、骨盆微滑、头向前探、小手耷拉在桌沿
  slouch: {
    sink: -0.04,
    hipsPitch: -0.12, hipsYaw: 0, hipsRoll: 0.02,
    spinePitch: 0.24, chestPitch: 0.18,
    headPitch: 0.18, headYaw: 0.06, headRoll: 0.05,
    armReachL: 0.60, armReachR: 0.60,
    armSpreadL: 0.10, armSpreadR: 0.10,
    forearmBendL: 0.20, forearmBendR: 0.20,
    thighAngle: -1.25, shinAngle: 1.35, footAngle: -0.20,
    awayOffsetZ: 0, awayOffsetX: 0, awayRotationY: 0,
    breath: 0.65,
  },
  // 3. 伏案（desk_hunch）：整个身体向前扑在桌面上、双手撑在键盘两侧敲击、低头注视屏幕
  desk_hunch: {
    sink: 0.02,
    hipsPitch: 0.22, hipsYaw: 0, hipsRoll: 0,
    spinePitch: 0.32, chestPitch: 0.25,
    headPitch: 0.25, headYaw: 0, headRoll: 0,
    armReachL: 1.25, armReachR: 1.25,
    armSpreadL: 0.28, armSpreadR: 0.28,
    forearmBendL: 0.65, forearmBendR: 0.65,
    thighAngle: -1.40, shinAngle: 1.50, footAngle: -0.24,
    awayOffsetZ: 0, awayOffsetX: 0, awayRotationY: 0,
    breath: 0.5,
  },
  // 4. 离开（away）：从小椅子上站起走开到窗边，身体站立放松，望向窗外或等待
  away: {
    sink: -0.48, // 站起后脚落回地面
    hipsPitch: 0, hipsYaw: 0.45, hipsRoll: 0,
    spinePitch: -0.02, chestPitch: -0.02,
    headPitch: -0.02, headYaw: 0.75, headRoll: -0.08,
    armReachL: 0.05, armReachR: 0.05,
    armSpreadL: 0.05, armSpreadR: 0.05,
    forearmBendL: 0.05, forearmBendR: 0.05,
    thighAngle: 0, shinAngle: 0, footAngle: 0,
    awayOffsetZ: -0.90, awayOffsetX: 0.20, awayRotationY: -0.85,
    breath: 0.7,
  },
  // 5. 喝水（drinking）：协议 §4.1 约定枚举保留但不做独立动画，平滑降级为 upright 端坐
  drinking: {
    sink: 0,
    hipsPitch: 0.02, hipsYaw: 0, hipsRoll: 0,
    spinePitch: 0.02, chestPitch: -0.02,
    headPitch: -0.04, headYaw: 0.02, headRoll: 0,
    armReachL: 0.85, armReachR: 0.85,
    armSpreadL: 0.20, armSpreadR: 0.20,
    forearmBendL: 0.40, forearmBendR: 0.40,
    thighAngle: -1.36, shinAngle: 1.48, footAngle: -0.24,
    awayOffsetZ: 0, awayOffsetX: 0, awayRotationY: 0,
    breath: 1,
  },
  // 6. 检测中（unknown）：坐在椅子上，小脑袋微偏，双手搭在桌前好奇打量
  unknown: {
    sink: 0,
    hipsPitch: 0.02, hipsYaw: -0.05, hipsRoll: 0.02,
    spinePitch: 0.02, chestPitch: 0.02,
    headPitch: -0.12, headYaw: -0.22, headRoll: 0.08,
    armReachL: 0.75, armReachR: 0.75,
    armSpreadL: 0.15, armSpreadR: 0.15,
    forearmBendL: 0.45, forearmBendR: 0.45,
    thighAngle: -1.36, shinAngle: 1.48, footAngle: -0.24,
    awayOffsetZ: 0, awayOffsetX: 0, awayRotationY: 0,
    breath: 1,
  },
};

export const PARTNER_STATES = Object.keys(POSES);

export function createPartner({ height = 1.0, modelUrl = './assets/monster.glb' } = {}) {
  const root = new THREE.Group();
  root.name = 'partner';
  root.scale.setScalar(height);

  const offsetContainer = new THREE.Group();
  root.add(offsetContainer);

  const bones = {};
  const restQuats = {};
  const restPositions = {};
  let isLoaded = false;

  // 异步加载 GLB 模型
  const loader = new GLTFLoader();
  loader.load(
    modelUrl,
    (gltf) => {
      const model = gltf.scene;
      model.name = 'partner-monster-mesh';

      model.traverse((child) => {
        if (child.isMesh) {
          child.castShadow = true;
          child.receiveShadow = true;
          child.frustumCulled = false;
          if (child.material) {
            child.material.roughness = Math.max(child.material.roughness || 0.6, 0.55);
            child.material.needsUpdate = true;
          }
        }
        if (child.isBone) {
          bones[child.name] = child;
          restQuats[child.name] = child.quaternion.clone();
          restPositions[child.name] = child.position.clone();

          // 别名支持
          const altName = child.name.includes('.')
            ? child.name.replace('.', '')
            : child.name.replace(/([LR])$/, '.$1');
          bones[altName] = child;
          restQuats[altName] = child.quaternion.clone();
          restPositions[altName] = child.position.clone();
        }
      });

      offsetContainer.add(model);
      isLoaded = true;
    },
    undefined,
    (err) => {
      console.error('[partner] 加载怪物模型失败:', err);
    }
  );

  // ============================================================
  // 姿态系统状态
  // ============================================================
  const current = { ...POSES.upright };
  const target = { ...POSES.upright };
  let stateName = 'upright';
  let elapsed = 0;

  const POSE_KEYS = Object.keys(POSES.upright);

  function setState(next) {
    if (!POSES[next]) return false;
    stateName = next;
    for (const k of POSE_KEYS) target[k] = POSES[next][k] ?? 0;
    return true;
  }

  function getBone(...names) {
    for (const n of names) {
      if (bones[n]) return bones[n];
    }
    return null;
  }

  // 沿指定局部轴叠加旋转
  function rotateBoneAxis(boneName, axisX, axisY, axisZ, angle) {
    const bone = getBone(boneName);
    const rest = restQuats[boneName];
    if (!bone || !rest) return;
    bone.quaternion.copy(rest);
    if (Math.abs(angle) > 1e-4) {
      bone.rotateOnAxis(new THREE.Vector3(axisX, axisY, axisZ).normalize(), angle);
    }
  }

  const deltaEuler = new THREE.Euler();
  const deltaQuat = new THREE.Quaternion();
  function applyDeltaEuler(boneName, x = 0, y = 0, z = 0) {
    const bone = getBone(boneName);
    const rest = restQuats[boneName];
    if (!bone || !rest) return;
    deltaEuler.set(x, y, z);
    deltaQuat.setFromEuler(deltaEuler);
    bone.quaternion.copy(rest).multiply(deltaQuat);
  }

  function update(dt = 0.016) {
    elapsed += dt;
    const k = 1 - Math.exp(-dt * 6.0);
    for (const key of POSE_KEYS) current[key] += (target[key] - current[key]) * k;

    // 呼吸微动与尾巴晃动
    const breath = current.breath * Math.sin(elapsed * 2.2) * 0.008;
    const tailWiggleX = Math.sin(elapsed * 1.6) * 0.14;
    const tailWiggleY = Math.cos(elapsed * 1.3) * 0.06;

    // 身体整体位移（离开时平滑走到窗边）
    offsetContainer.position.set(current.awayOffsetX, current.sink, current.awayOffsetZ);
    offsetContainer.rotation.y = current.awayRotationY;

    if (isLoaded) {
      // 1. 骨盆（Hips）
      const hips = getBone('Hips');
      const hipsRestPos = restPositions['Hips'];
      if (hips && hipsRestPos) {
        hips.position.y = hipsRestPos.y + breath * 0.4;
      }
      applyDeltaEuler('Hips', current.hipsPitch, current.hipsYaw, current.hipsRoll);

      // 2. 脊椎与胸腔
      applyDeltaEuler('Spine', current.spinePitch + breath * 0.25, 0, 0);
      applyDeltaEuler('Chest', current.chestPitch + breath * 0.25, 0, 0);

      // 3. 头部
      applyDeltaEuler('Head', current.headPitch, current.headYaw, current.headRoll);

      // 4. 手臂：向前平伸搭在桌面上
      rotateBoneAxis('UpperArm.L', -1, 0, -0.6, current.armReachL);
      rotateBoneAxis('LowerArm.L', -1, 0, 0, current.forearmBendL);

      rotateBoneAxis('UpperArm.R', -1, 0, 0.6, current.armReachR);
      rotateBoneAxis('LowerArm.R', -1, 0, 0, current.forearmBendR);

      // 5. 腿部坐姿（大腿前抬 -78°，小腿下折 +85°，脚掌平踩 -14°）
      rotateBoneAxis('Thigh.L', 1, 0, 0, current.thighAngle);
      rotateBoneAxis('Shin.L', 1, 0, 0, current.shinAngle);
      rotateBoneAxis('Foot.L', 1, 0, 0, current.footAngle);

      rotateBoneAxis('Thigh.R', 1, 0, 0, current.thighAngle);
      rotateBoneAxis('Shin.R', 1, 0, 0, current.shinAngle);
      rotateBoneAxis('Foot.R', 1, 0, 0, current.footAngle);

      // 6. 尾巴：轻微摇摆
      rotateBoneAxis('Tail1', 0, 1, 0, tailWiggleX);
      rotateBoneAxis('Tail2', 0, 1, 0, tailWiggleX * 0.8);
      rotateBoneAxis('Tail3', 1, 0, 0, tailWiggleY);
    }
  }

  update(0);

  return {
    group: root,
    setState,
    update,
    getState: () => stateName,
    getPose: () => ({ ...current }),
    bones,
  };
}
