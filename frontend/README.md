# 小栖 · 前端（呈现层）

owner：**A（张鹏）** ｜ 模块：W6 场景 · W7 健康伙伴 · W8 信息可视化
当前进度：**XQ-009 视觉精修**（XQ-003 房间骨架 + 程序化贴图 / 窗外城市景观 / 吊灯光晕 / 闹钟绿植重做 / HUD 演示工具条）+ **XQ-006 手机步数数据链**（WS 接线 / 左下步数卡 / 挂历卡面）。M1 阶段**不做美术、不做动画补间**。

## 跑起来

```bash
cd frontend
npm ci            # 锁文件可复现，18 个包约 4 秒
npm run dev       # http://localhost:5173
```

开发期 `/api` 与 `/ws` 由 Vite 代理转发到后端 `http://127.0.0.1:8000`（免 CORS）。
后端地址可用环境变量覆盖：`XIAOQI_BACKEND=http://192.168.1.5:8000 npm run dev`。

### 手机端上报页（`/phone.html`）

浏览器地址栏只能发 `GET`，而协议要求 `POST /api/ingest/health` + JSON + `X-Xiaoqi-Token`，
所以在 `public/phone.html` 放了一张手机可用的上报页，构建后随 dist 一起托管：

```
http://<电脑局域网IP>:8000/phone.html      # 后端单端口托管时
```

页面会显示服务端已记录的步数与连接状态，手填步数后点按钮即可上报（也可用
`?steps=8123` 预填）。**它读不到系统步数**——浏览器没有 Health Connect / 健康 App 的权限，
自动同步要靠 D-009 的自研 Android App，目前仓库里还没有。

URL 参数：

| 参数 | 作用 |
|---|---|
| `?grid=0` | 关掉地面网格（演示/录像时用） |
| `?az=42` | 初始机位方位角（度）。0 = 从 +z 方向看，90 = 从 +x 方向看 |
| `?el=15` | 初始机位仰角（度）。0 = 与目标同高，90 = 正上方俯视 |
| `?dist=7.9` | 初始机位与目标的距离（米） |
| `?state=slouch` | 伙伴状态卡初始值（`upright`/`slouch`/`desk_hunch`/`away`/`drinking`/`unknown`，默认 `upright`）。连上 WS 后以服务端 `pose.state` 为准 |
| `?hud=0` | 隐藏顶部演示工具条（左下伙伴状态卡仍保留） |
| `?live=0` | 不连 WS，纯离线看画面：步数卡停在「无数据 / 等待手机同步」，伙伴状态用 `?state=` 的初值 |
| `?ws=...` | 覆盖 WS 地址。可写完整 `ws://host:port/ws`、路径 `/ws`，或只写 `host:port`（默认同源 `/ws`） |
| `?view=calendar` | 启动即飞到某个机位（`default`/`desk`/`chair`/`monitor`/`mirror`/`calendar`/`mug`/`camera`），录像取证用 |

例：`http://localhost:5173/?az=110&el=25&dist=9` —— 验收或录像时固定机位用；
`http://localhost:5173/?live=0` —— 没有后端时也能看完整画面。

## 交付形态（D-007）

```bash
npm run build      # 产物 → frontend/dist
cd ../backend && python -m xiaoqi    # 后端一条命令托管前端，单端口 8000
```

`backend/config.yaml` 的 `frontend.dist` 已指向 `../frontend/dist`，两边不用手工对齐。

## 目录

```
src/
├── main.js          装配：渲染器 → 场景 → 相机 → 房间 → HUD → 数据链 → 循环
├── viewer.js        相机 + OrbitControls（不许钻到地板下）；XQ-009 增加 flyTo 平滑飞行
├── hud.js           信息层：伙伴状态卡 + 步数卡 + 演示工具条（10 钮）+ FPS
├── live.js          XQ-006：WS 客户端（15s 看门狗 / 2s→30s 退避重连 / 帧分发）
├── steps.js         XQ-006：phone 快照 → 三态文案（纯函数，无 DOM 依赖，可单测）
└── scene/
    ├── room.js      房间组装 + 13 件家具构建函数（XQ-009：窗外景观/光晕/闹钟/绿植重做）
    ├── calendarFace.js XQ-006：挂历正面当日步数卡面（CanvasTexture）
    ├── textures.js  XQ-009 新增：CanvasTexture 程序化贴图（墙纸暗纹 / 木地板 / 城市景观 / 光晕）
    └── materials.js 粘土风材质工厂 + 配色表 + 物件名常量（XQ-003 新增）
public/assets/       W9 素材：glTF 模型与贴图（Vite 原样拷进 dist/assets/）
test/                steps / live 的 node 逻辑测试（不依赖浏览器）
```

## 贴图与视觉效果（XQ-009）

- **墙纸暗纹**：`textures.js` 的 `makeWallpaperTexture()` 用 Canvas 画菱形网格暗纹（底色 `#f0e7d6`、纹样 `#e2d5bc`），贴到实体墙 x=-3
- **木地板**：`makeFloorTexture()` 画长条木地板（板宽 0.2~0.3 m、深色分缝、每板色相微扰）
- **窗外城市**：`makeCityTexture()` 一张 1024×640 城市景观贴图替代原 6 块剪影矩形（窗 4.8m×3m ≈ 1.6 宽高比）——天空纵向渐变 + 远/中/近三层楼群（远浅近深的大气透视，近层带亮灯窗点）
- **吊灯光晕**：灯泡外加 `THREE.Sprite` 径向渐变辉光（`AdditiveBlending`、暖色 `#ffd9a0`），光源结构与投影配置未动
- **闹钟/绿植重做**：闹钟为双铃圆形闹钟（铃铛 + 倾斜柄 + 刻度表盘），绿植为梯形盆 + 扇形张开的桨形叶
- **全部程序化生成，零外部图片文件、零新增 npm 依赖**

## HUD 结构（XQ-009）

- **左下伙伴状态卡**：深色半透明圆角卡，「伙伴状态」标签 + 状态值 + 状态点。映射：`upright→正直（健康）` 绿 / `slouch→驼背（注意）` 橙 / `desk_hunch→伏案（提醒）` 橙 / `away→离开（待机）` 灰 / `drinking→喝水（计数）` 蓝 / `unknown→检测中` 灰。XQ-006 接 WS 后替换数据源，`setState(key)`（枚举键优先，非枚举键按原文显示）/ `setConnected(connected)` 接口形式不变
- **左上演示工具条 10 钮**（`?hud=0` 可隐藏）：`视角方式`（循环机位预设）/ `电脑设置` `配置` `导入` `隐形`（HUD 显隐）/ `镜子` `日历` `水杯` `监视` `相机`（相机 `flyTo` 飞向对应物件 + 高亮脉冲）。**演示辅助层，不承载功能入口**（入口仍是点物件）
- **右上 FPS**：小、半透明，M3-6 取证用
- 文案一律 `textContent` 写入，禁止 `innerHTML` 拼动态内容

## 手机步数数据链（XQ-006）

数据从手机到房间只有一条线：**Android App → `POST /api/ingest/health` → 后端幂等/聚合 → WS 广播 → 前端**。
前端**只消费 WS、不轮询 HTTP**，`?live=0` 可整条关掉。

- **帧**：`hello`（连上首帧，带全量 `phone: {steps, updated_ts, stale}`）→ `state`（增量，只带变化字段）→ `ping`（10s 心跳，喂看门狗）。
  协议字段见 `docs/02-需求与设计/接口协议.md` §3；前端不认识业务语义中的其它字段，只取 `pose.state` 与 `phone`。
- **连接**：15s 收不到任何帧视为断线（后端心跳就是一拍 10s），主动断开后按 **2s → 4s → 8s … 封顶 30s** 重连，连上即归零。
- **三态**（`steps.js` 的 `describePhone`，HUD 卡与挂历卡面共用同一份判定）：
  | 态 | 触发 | 卡片 |
  |---|---|---|
  | `none` | 还没收到过 phone，或 `steps` 非数字 | 「无数据」+「等待手机同步」——**不补 0**（A-04） |
  | `synced` | 有数值且 `updated_ts` 在 15 分钟内、后端 `stale=false` | `6,842 步` + 「刚刚 / N 分钟前同步」 |
  | `pending` | 后端 `stale=true`，或本地算出来超过 15 分钟 | 数值照显，note 变「待同步 · N 分钟前」 |
  | `offline` | WS 断开 | 保留最后数值，note 变「连接中断」 |
- **两个呈现位**：左下 HUD 步数卡（伙伴状态卡上方，`隐形` 模式下一起隐藏）；挂历正面的卡面（`scene/calendarFace.js`，CanvasTexture 贴在 z=0.0144，压在日历格子之上、让开月份带）。文字走贴图而不是 HTML 覆盖层——后者只能贴屏幕坐标，镜头一动就穿帮。
- **刷新节奏**：收到帧渲染一次，另外每 10s 兜底重渲染——「N 分钟前」和 15 分钟老化不会因为没新帧就不动。
- **测试**：`npm test`（`node --test`）。若环境不允许 `node --test` 起子进程，逐文件跑 `node test/steps.test.mjs`、`node test/live.test.mjs` 即可，两套都不碰浏览器与真实网络。

## 坐标约定（加任何东西都按这个来）

单位 1 = 1 米，y 轴朝上，地面 y = 0，房间 **6×6 m**、墙高 **3 m**。

> ⚠️ **XQ-003 重排过墙面归属**（照 `04-视觉参考/房间-建模基准.jpeg` 数出来的）。
> XQ-008 的旧约定是「后墙 z=-3 贴显示器 / 左墙 x=-3 挂日历」，**已作废**。

| 面 | 位置 | 说明 |
|---|---|---|
| **实体墙** | **x = -3** | 椭圆镜 + 挂历两件（别再往上堆）。落**画面左 1/3** |
| **窗墙** | **z = -3** | 整面落地窗（顶到底，无窗台）+ 城市景观贴图，同时是冷环境光来源。落**画面右 2/3** |
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

另：`three@0.186` 已移除 `PCFSoftShadowMap`，`main.js` 里那行会在控制台留一条
`THREE.WebGLShadowMap: PCFSoftShadowMap has been removed. Using PCFShadowMap instead.`
（阴影实际走 PCF）。是本仓库既有代码的版本噪声，与步数数据链无关，改不改都不影响画面。

## 素材约定（W9 · owner: B）

- 命名：`room-*.glb` / `partner-*.glb` / `tex-*.png`
- 每个素材登记来源与许可（对应 XQ-010 美术风格参考收集）
- 单文件 >20MB 走网盘或 Git LFS，不进仓库
