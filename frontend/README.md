# 小栖 · 前端（呈现层）

owner：**A（张鹏）** ｜ 模块：W6 场景 · W7 健康伙伴 · W8 信息可视化
当前进度：**XQ-003 房间骨架**（13 件物件 + 粘土风材质 + 双光 + 阴影）。M1 阶段**不做美术、不做动画补间**。

## 跑起来

```bash
cd frontend
npm ci            # 锁文件可复现，18 个包约 4 秒
npm run dev       # http://localhost:5173
```

开发期 `/api` 与 `/ws` 由 Vite 代理转发到后端 `http://127.0.0.1:8000`（免 CORS）。
后端地址可用环境变量覆盖：`XIAOQI_BACKEND=http://192.168.1.5:8000 npm run dev`。

URL 参数：

| 参数 | 作用 |
|---|---|
| `?grid=0` | 关掉地面网格（演示/录像时用） |
| `?az=42` | 初始机位方位角（度）。0 = 从 +z 方向看，90 = 从 +x 方向看 |
| `?el=15` | 初始机位仰角（度）。0 = 与目标同高，90 = 正上方俯视 |
| `?dist=7.9` | 初始机位与目标的距离（米） |

例：`http://localhost:5173/?az=110&el=25&dist=9` —— 验收或录像时固定机位用。

## 交付形态（D-007）

```bash
npm run build      # 产物 → frontend/dist
cd ../backend && python -m xiaoqi    # 后端一条命令托管前端，单端口 8000
```

`backend/config.yaml` 的 `frontend.dist` 已指向 `../frontend/dist`，两边不用手工对齐。

## 目录

```
src/
├── main.js          装配：渲染器 → 场景 → 相机 → 房间 → HUD → 循环
├── viewer.js        相机 + OrbitControls（不许钻到地板下）
├── hud.js           信息层：状态文字（M1-4 显示位）+ FPS
└── scene/
    ├── room.js      房间组装 + 13 件家具构建函数
    └── materials.js 粘土风材质工厂 + 配色表 + 物件名常量（XQ-003 新增）
public/assets/       W9 素材：glTF 模型与贴图（Vite 原样拷进 dist/assets/）
```

## 坐标约定（加任何东西都按这个来）

单位 1 = 1 米，y 轴朝上，地面 y = 0，房间 **6×6 m**、墙高 **3 m**。

> ⚠️ **XQ-003 重排过墙面归属**（照 `04-视觉参考/房间-建模基准.jpeg` 数出来的）。
> XQ-008 的旧约定是「后墙 z=-3 贴显示器 / 左墙 x=-3 挂日历」，**已作废**。

| 面 | 位置 | 说明 |
|---|---|---|
| **实体墙** | **x = -3** | 椭圆镜 + 挂历两件（别再往上堆）。落**画面左 1/3** |
| **窗墙** | **z = -3** | 整面落地窗（顶到底，无窗台）+ 城市剪影，同时是冷环境光来源。落**画面右 2/3** |
| 敞口 | z = +3 / x = +3 | 不立任何东西，留给相机 |

**为什么是这个归属**：相机站在 (+x, +z) 墙角外侧时，几何上必然是 `x=-3` 那面墙落画面左、`z=-3` 那面墙落画面右。参考图正是「实体墙左、落地窗右」。

**桌子贴窗墙**（z = -3），L 型：长边沿 x 延伸（与窗平行），短边回靠实体墙。

家具关键尺寸：桌高 **0.75 m**（长 2.5 × 深 0.68）· 矮柜高 **0.62 m** · 椅座高 **0.45 m**。

> **窗只铺 x ∈ [-3, 1.8]**。铺到 x = +3 时竖梃会杵在镜头旁边，画面被黑柱穿一道 —— XQ-003 踩过。

## M3-1 物件清单（XQ-003，13 件 + 照明）

| 区 | 物件 | `getObjectByName` |
|---|---|---|
| 结构 | 地板 / 实体墙(x=-3) / 落地窗(z=-3) | `floor` `wall-left` `window` |
| 桌区 | 桌子 / 矮柜 / 椅子 / 显示器 / 键盘 / 鼠标 / 摄像头 / 闹钟 | `desk` `desk-cabinet` `chair` `monitor` `keyboard` `mouse` `web-camera` `clock` |
| 桌面 | 水杯 / 盆栽 | `mug` `plant` |
| 墙面 | 镜子 / 日历本 | `mirror` `calendar` |
| 照明 | 吊灯 + 4 光源 | `lamp` `light-hemi` `light-lamp` `light-spot` `light-sky` |
| 占位 | 健康伙伴（XQ-004 建几何体） | `partner` |

屏幕 HTML 覆盖层用 `screen-anchor` 对齐（XQ-004/005 用）。

## 美术规格（粘土风）

- `MeshStandardMaterial`，`roughness ≈ 0.9`、`metalness = 0` —— 亚光、无高光
- 家具统一用 `RoundedBoxGeometry`（`materials.js` 的 `roundedBox`），**不要裸 `BoxGeometry`**
- 暖主光吊灯 `#ffd9a0` + 冷环境光窗外 `#7f9cc4`，构成冷暖对比
- `renderer.toneMapping = ACESFilmicToneMapping`，`exposure = 1.15`
- 阴影 `PCFSoftShadowMap`，`PointLight` 与 `SpotLight` 双投影（mapSize 512 / 1024）
- **补光两盏不投影**：`light-fill-top`（顶部柔光）+ `light-ambient` —— 只投影的话，桌面背光侧的地板会掉到近黑

配色表集中在 `materials.js` 的 `PALETTE`，与 `小栖 界面原型.md` §8.2 一致，**勿单处改动**。

## 机位

默认机位 `(3.0, 1.8, 1.8)` → 看向 `(-2.2, 1.0, -1.6)`，**从 6 组候选里选定**（关键点 6/6 入画 + 镜子与桌面占比最接近参考图）。

改机位用 URL 参数：`?az=42&el=15&dist=7.9`。

> 求解机位别靠手感试：先定「哪些面墙落画面左/右」这个硬约束，再用 `camera.project()` 或
> `Object3D.project()` 判候选点是否入画，最后看截图定构图。XQ-003 试了五轮才对。

## 已知限制（XQ-007 之前不得当作缺陷报）

**WSL 无 GPU 直通（无 `/dev/dri`）**，无头 Chromium 走 SwiftShader 软渲染，1440×900 下只有 **6–11 FPS**。
受控实验已证实这是**软渲染填充率**问题，不是场景复杂度：

| 实验 | FPS |
|---|---|
| 现状 | 8 |
| 关阴影 | 7（不升反降） |
| 分辨率减半 | 23 |
| 隐藏全部家具 | 27 |

⇒ **M3-6 的帧率判据必须在 Windows 真机 GPU 上跑**，不要用本环境的数字下结论。

## 素材约定（W9 · owner: B）

- 命名：`room-*.glb` / `partner-*.glb` / `tex-*.png`
- 每个素材登记来源与许可（对应 XQ-010 美术风格参考收集）
- 单文件 >20MB 走网盘或 Git LFS，不进仓库