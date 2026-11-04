/**
 * 小栖 3D 场景与资产工作室 (Studio)
 * 功能：
 *   1. 资产大纲树：小怪兽、书桌、椅子、显示器、键盘、鼠标、绿植、闹钟、水杯、矮柜、灯具等任意选中
 *   2. 3D 可视化交互：W 平移 / E 旋转 / R 缩放，实时吸附与调整
 *   3. 角色骨骼动作实时预览与调姿（6大姿态 + 骨骼滑块）
 *   4. 一键导出 / 应用场景布局配置文件 scene-layout.json
 */
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

export function setupStudio({ scene, viewer, partner, room, onSave }) {
  // 注入 Studio 专属样式
  const style = document.createElement('style');
  style.textContent = `
    .studio-panel {
      position: absolute;
      background: rgba(18, 24, 34, 0.92);
      backdrop-filter: blur(12px);
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 12px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 10px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      z-index: 10000;
      user-select: none;
      display: flex;
      flex-direction: column;
    }
    .studio-panel header {
      padding: 10px 14px;
      font-weight: 700;
      font-size: 13px;
      color: #60a5fa;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .studio-left {
      top: 60px;
      left: 14px;
      width: 220px;
      max-height: calc(100vh - 80px);
    }
    .studio-right {
      top: 60px;
      right: 14px;
      width: 280px;
      max-height: calc(100vh - 80px);
    }
    .studio-list {
      overflow-y: auto;
      padding: 6px;
      flex: 1;
    }
    .studio-item {
      padding: 6px 10px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 2px;
      color: #cbd5e1;
      transition: background 0.15s;
    }
    .studio-item:hover {
      background: rgba(255, 255, 255, 0.08);
      color: #fff;
    }
    .studio-item.active {
      background: #2563eb;
      color: #fff;
      font-weight: 600;
    }
    .studio-prop-group {
      padding: 10px 14px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .studio-prop-title {
      font-size: 11px;
      font-weight: 600;
      color: #94a3b8;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .studio-prop-row {
      display: flex;
      align-items: center;
      margin-bottom: 6px;
      gap: 6px;
    }
    .studio-prop-row label {
      width: 38px;
      color: #94a3b8;
      font-size: 11px;
    }
    .studio-input {
      flex: 1;
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: #38bdf8;
      padding: 4px 6px;
      border-radius: 4px;
      font-family: ui-monospace, monospace;
      font-size: 11px;
    }
    .studio-input:focus {
      outline: none;
      border-color: #38bdf8;
    }
    .studio-btn {
      background: #3b82f6;
      color: #fff;
      border: none;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
      transition: background 0.15s;
    }
    .studio-btn:hover { background: #2563eb; }
    .studio-btn.success { background: #10b981; }
    .studio-btn.success:hover { background: #059669; }
    .studio-btn.secondary { background: rgba(255,255,255,0.1); color: #cbd5e1; }
    .studio-btn.secondary:hover { background: rgba(255,255,255,0.18); color: #fff; }
    .studio-badge {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      background: rgba(0,0,0,0.3);
      color: #94a3b8;
    }
  `;
  document.head.appendChild(style);

  // 1. 初始化 3D TransformControls
  const transform = new TransformControls(viewer.camera, viewer.controls.domElement);
  transform.size = 0.8;
  scene.add(transform.getHelper());

  transform.addEventListener('dragging-changed', (e) => {
    viewer.controls.enabled = !e.value;
  });

  // 物件清单映射
  // 物件在中英文标识名与其在 Three.js 场景里的真实 name (NAME 字典) 之间的映射
  const OBJECT_CONFIG = [
    { key: 'partner', label: '👾 小怪兽 (角色)', find: () => partner?.group },
    { key: 'chair', label: '🪑 办公椅', names: ['chair'] },
    { key: 'desk', label: '🪵 办公桌', names: ['desk'] },
    { key: 'deskCabinet', label: '🗄️ 桌面矮柜', names: ['desk-cabinet', 'deskCabinet'] },
    { key: 'monitor', label: '🖥️ 显示器', names: ['monitor'] },
    { key: 'keyboard', label: '⌨️ 键盘', names: ['keyboard'] },
    { key: 'mouse', label: '🖱️ 鼠标', names: ['mouse'] },
    { key: 'plant', label: '🪴 绿植盆栽', names: ['plant'] },
    { key: 'clock', label: '⏰ 闹钟', names: ['clock'] },
    { key: 'mug', label: '☕ 水杯', names: ['mug'] },
    { key: 'lamp', label: '💡 吊灯', names: ['lamp'] },
    { key: 'mirror', label: '🪞 椭圆镜', names: ['mirror'] },
    { key: 'calendar', label: '📅 挂历', names: ['calendar'] },
  ];

  const OBJECT_LABELS = {};
  const managedObjects = {};

  OBJECT_CONFIG.forEach(cfg => {
    OBJECT_LABELS[cfg.key] = cfg.label;
    if (cfg.find) {
      const obj = cfg.find();
      if (obj) managedObjects[cfg.key] = obj;
    } else if (cfg.names) {
      for (const n of cfg.names) {
        const obj = scene.getObjectByName(n) || room?.getObjectByName?.(n);
        if (obj) {
          managedObjects[cfg.key] = obj;
          break;
        }
      }
    }
  });

  let selectedKey = 'partner';
  let selectedObj = managedObjects['partner'] || null;

  // 2. 创建左侧大纲面板
  const leftPanel = document.createElement('div');
  leftPanel.className = 'studio-panel studio-left';
  leftPanel.innerHTML = `
    <header>
      <span>场景物件大纲</span>
      <span class="studio-badge">${Object.keys(managedObjects).length} 个物件</span>
    </header>
    <div class="studio-list" id="studio-obj-list"></div>
    <div style="padding: 10px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; gap: 6px;">
      <button class="studio-btn secondary" id="studio-mode-t" style="flex:1;">平移 (W)</button>
      <button class="studio-btn secondary" id="studio-mode-r" style="flex:1;">旋转 (E)</button>
      <button class="studio-btn secondary" id="studio-mode-s" style="flex:1;">缩放 (R)</button>
    </div>
  `;
  document.body.appendChild(leftPanel);

  // 3. 创建右侧属性面板
  const rightPanel = document.createElement('div');
  rightPanel.className = 'studio-panel studio-right';
  rightPanel.innerHTML = `
    <header>
      <span id="studio-selected-name">物件属性</span>
      <button class="studio-btn secondary" id="studio-focus-btn" style="padding: 2px 8px; font-size: 11px;">聚焦视角</button>
    </header>
    <div style="overflow-y:auto; flex:1;">
      <!-- 位置 -->
      <div class="studio-prop-group">
        <div class="studio-prop-title">Position (位置)</div>
        <div class="studio-prop-row">
          <label>X (m)</label><input class="studio-input" id="prop-pos-x" type="number" step="0.02"/>
          <label style="margin-left:6px;">Y</label><input class="studio-input" id="prop-pos-y" type="number" step="0.02"/>
          <label style="margin-left:6px;">Z</label><input class="studio-input" id="prop-pos-z" type="number" step="0.02"/>
        </div>
      </div>

      <!-- 旋转 -->
      <div class="studio-prop-group">
        <div class="studio-prop-title">Rotation (旋转角度)</div>
        <div class="studio-prop-row">
          <label>Y (度)</label><input class="studio-input" id="prop-rot-y" type="number" step="5"/>
          <label style="margin-left:6px;">X</label><input class="studio-input" id="prop-rot-x" type="number" step="5"/>
          <label style="margin-left:6px;">Z</label><input class="studio-input" id="prop-rot-z" type="number" step="5"/>
        </div>
      </div>

      <!-- 缩放 -->
      <div class="studio-prop-group">
        <div class="studio-prop-title">Scale (尺寸缩放)</div>
        <div class="studio-prop-row">
          <label>Scale</label><input class="studio-input" id="prop-scale" type="number" step="0.05"/>
          <button class="studio-btn secondary" id="prop-scale-reset" style="padding: 2px 8px; font-size: 11px;">1.0</button>
        </div>
      </div>

      <!-- 角色动作控制 -->
      <div class="studio-prop-group" id="studio-partner-pose-group">
        <div class="studio-prop-title">角色动作切换</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px;">
          <button class="studio-btn secondary pose-btn" data-pose="upright">1. 坐直</button>
          <button class="studio-btn secondary pose-btn" data-pose="slouch">2. 驼背</button>
          <button class="studio-btn secondary pose-btn" data-pose="desk_hunch">3. 伏案</button>
          <button class="studio-btn secondary pose-btn" data-pose="away">4. 离开</button>
          <button class="studio-btn secondary pose-btn" data-pose="drinking">5. 喝水</button>
          <button class="studio-btn secondary pose-btn" data-pose="unknown">6. 检测中</button>
        </div>
      </div>
    </div>

    <!-- 底部保存与导出 -->
    <div style="padding: 12px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; flex-direction: column; gap: 6px;">
      <button class="studio-btn success" id="studio-btn-export" style="padding: 8px 0;">
        💾 导出完整场景布局配置 (JSON)
      </button>
      <button class="studio-btn secondary" id="studio-btn-copy-code" style="padding: 6px 0; font-size: 11px;">
        📋 复制当前选中物件的代码
      </button>
    </div>
  `;
  document.body.appendChild(rightPanel);

  // 渲染物件列表
  const listEl = document.getElementById('studio-obj-list');
  function renderList() {
    listEl.innerHTML = '';
    Object.keys(managedObjects).forEach((key) => {
      const item = document.createElement('div');
      item.className = `studio-item ${key === selectedKey ? 'active' : ''}`;
      item.innerHTML = `
        <span>${OBJECT_LABELS[key] || key}</span>
        <span style="opacity:0.6;font-size:10px;">${key}</span>
      `;
      item.onclick = () => selectObject(key);
      listEl.appendChild(item);
    });
  }

  function selectObject(key) {
    selectedKey = key;
    selectedObj = managedObjects[key];
    if (selectedObj) {
      transform.attach(selectedObj);
      transform.enabled = true;
      transform.getHelper().visible = true;
    } else {
      transform.detach();
      transform.enabled = false;
      transform.getHelper().visible = false;
    }
    renderList();
    updatePropsUI();

    const poseGroup = document.getElementById('studio-partner-pose-group');
    if (poseGroup) poseGroup.style.display = key === 'partner' ? 'block' : 'none';

    const nameEl = document.getElementById('studio-selected-name');
    if (nameEl) nameEl.innerText = OBJECT_LABELS[key] || key;
  }

  // 更新属性输入框数值
  function updatePropsUI() {
    if (!selectedObj) return;
    const p = selectedObj.position;
    const r = selectedObj.rotation;
    const s = selectedObj.scale.x;

    const posX = document.getElementById('prop-pos-x');
    const posY = document.getElementById('prop-pos-y');
    const posZ = document.getElementById('prop-pos-z');
    if (posX) posX.value = p.x.toFixed(2);
    if (posY) posY.value = p.y.toFixed(2);
    if (posZ) posZ.value = p.z.toFixed(2);

    const rotX = document.getElementById('prop-rot-x');
    const rotY = document.getElementById('prop-rot-y');
    const rotZ = document.getElementById('prop-rot-z');
    if (rotX) rotX.value = (THREE.MathUtils.radToDeg(r.x)).toFixed(0);
    if (rotY) rotY.value = (THREE.MathUtils.radToDeg(r.y)).toFixed(0);
    if (rotZ) rotZ.value = (THREE.MathUtils.radToDeg(r.z)).toFixed(0);

    const sc = document.getElementById('prop-scale');
    if (sc) sc.value = s.toFixed(2);
  }

  transform.addEventListener('change', updatePropsUI);

  // 输入框反向修改物体 Transform
  const setFromInput = () => {
    if (!selectedObj) return;
    const px = parseFloat(document.getElementById('prop-pos-x').value) || 0;
    const py = parseFloat(document.getElementById('prop-pos-y').value) || 0;
    const pz = parseFloat(document.getElementById('prop-pos-z').value) || 0;
    selectedObj.position.set(px, py, pz);

    const rx = THREE.MathUtils.degToRad(parseFloat(document.getElementById('prop-rot-x').value) || 0);
    const ry = THREE.MathUtils.degToRad(parseFloat(document.getElementById('prop-rot-y').value) || 0);
    const rz = THREE.MathUtils.degToRad(parseFloat(document.getElementById('prop-rot-z').value) || 0);
    selectedObj.rotation.set(rx, ry, rz);

    const sc = parseFloat(document.getElementById('prop-scale').value) || 1;
    selectedObj.scale.setScalar(sc);
  };

  ['prop-pos-x', 'prop-pos-y', 'prop-pos-z', 'prop-rot-x', 'prop-rot-y', 'prop-rot-z', 'prop-scale'].forEach((id) => {
    document.getElementById(id)?.addEventListener('input', setFromInput);
  });

  document.getElementById('prop-scale-reset')?.addEventListener('click', () => {
    if (selectedObj) {
      selectedObj.scale.setScalar(1);
      updatePropsUI();
    }
  });

  // W / E / R 模式切换
  const setMode = (mode) => {
    transform.setMode(mode);
    ['studio-mode-t', 'studio-mode-r', 'studio-mode-s'].forEach((id) => {
      document.getElementById(id)?.classList.remove('active');
    });
    if (mode === 'translate') document.getElementById('studio-mode-t')?.classList.add('active');
    if (mode === 'rotate') document.getElementById('studio-mode-r')?.classList.add('active');
    if (mode === 'scale') document.getElementById('studio-mode-s')?.classList.add('active');
  };

  document.getElementById('studio-mode-t').onclick = () => setMode('translate');
  document.getElementById('studio-mode-r').onclick = () => setMode('rotate');
  document.getElementById('studio-mode-s').onclick = () => setMode('scale');
  setMode('translate');

  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    const k = e.key.toLowerCase();
    if (k === 'w') setMode('translate');
    if (k === 'e') setMode('rotate');
    if (k === 'r') setMode('scale');
  });

  // 视角聚焦
  document.getElementById('studio-focus-btn')?.addEventListener('click', () => {
    if (!selectedObj) return;
    const box = new THREE.Box3().setFromObject(selectedObj);
    const center = box.getCenter(new THREE.Vector3());
    viewer.controls.target.copy(center);
    viewer.camera.position.set(center.x + 1.2, center.y + 0.8, center.z + 1.5);
    viewer.camera.lookAt(center);
    viewer.controls.update();
  });

  // 动作切换测试按钮
  document.querySelectorAll('.pose-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const pose = btn.getAttribute('data-pose');
      if (partner?.setState) partner.setState(pose);
    });
  });

  // 导出全部场景配置
  document.getElementById('studio-btn-export')?.addEventListener('click', () => {
    const config = {};
    Object.keys(managedObjects).forEach((k) => {
      const o = managedObjects[k];
      config[k] = {
        position: [parseFloat(o.position.x.toFixed(3)), parseFloat(o.position.y.toFixed(3)), parseFloat(o.position.z.toFixed(3))],
        rotation: [parseFloat(o.rotation.x.toFixed(3)), parseFloat(o.rotation.y.toFixed(3)), parseFloat(o.rotation.z.toFixed(3))],
        scale: [parseFloat(o.scale.x.toFixed(3)), parseFloat(o.scale.y.toFixed(3)), parseFloat(o.scale.z.toFixed(3))],
      };
    });
    const jsonStr = JSON.stringify(config, null, 2);
    console.log('=== SCENE CONFIG EXPORT ===\n', jsonStr);
    navigator.clipboard.writeText(jsonStr).then(() => {
      alert('✅ 全场景配置 JSON 已成功复制到剪贴板！');
    });
    if (onSave) onSave(config);
  });

  // 复制代码片段
  document.getElementById('studio-btn-copy-code')?.addEventListener('click', () => {
    if (!selectedObj) return;
    const p = selectedObj.position;
    const r = selectedObj.rotation;
    const s = selectedObj.scale.x;
    const code = `// ${OBJECT_LABELS[selectedKey] || selectedKey}\n${selectedKey}.position.set(${p.x.toFixed(2)}, ${p.y.toFixed(2)}, ${p.z.toFixed(2)});\n${selectedKey}.rotation.set(${r.x.toFixed(2)}, ${r.y.toFixed(2)}, ${r.z.toFixed(2)});\n${selectedKey}.scale.setScalar(${s.toFixed(2)});`;
    navigator.clipboard.writeText(code).then(() => {
      alert('✅ 已复制代码片段到剪贴板！');
    });
  });

  renderList();
  selectObject('partner');
}
