# 小栖 · 前端（呈现层）

owner：**A（张鹏）** ｜ 备份：B ｜ 模块：W6 场景 · W7 健康伙伴 · W8 信息可视化
当前进度：XQ-008 空房间骨架（地面 + 墙角 + 光照 + 相机可旋转）。M1 阶段**不做美术、不做动画补间**。

## 跑起来

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
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
└── scene/room.js    W6 房间场景
public/assets/       W9 素材：glTF 模型与贴图（Vite 原样拷进 dist/assets/）
```

**坐标约定**（加任何东西都按这个来）：单位 1 = 1 米，y 轴朝上，地面 y = 0，
房间 6×6 m、墙高 3 m，后墙 z = -3、左墙 x = -3。

## 素材约定（W9 · owner: B）

- 命名：`room-*.glb` / `partner-*.glb` / `tex-*.png`
- 每个素材登记来源与许可（对应 XQ-010 美术风格参考收集）
- 单文件 >20MB 走网盘或 Git LFS，不进仓库
