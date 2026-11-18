# 小栖步数 · Android 手机端

> 统计**当日步数**，按小栖接口协议 `POST /api/ingest/health` 同步到电脑端；
> 小栖网页（3D 房间 / 挂历 / 左下步数卡）通过现有 WebSocket 自动刷新，手机端零改动接入。

<p>
<img alt="android" src="https://img.shields.io/badge/platform-Android%208.0%2B-3ddc84">
<img alt="target" src="https://img.shields.io/badge/targetSdk-34-blue">
<img alt="apk" src="https://img.shields.io/badge/APK-190%20KB-brightgreen">
<img alt="tests" src="https://img.shields.io/badge/tests-98%20passed-success">
</p>

---

## 交付物

| 文件 | 说明 |
|---|---|
| **[`release/xiaoqi-steps-1.0.0.apk`](release/xiaoqi-steps-1.0.0.apk)** | 已签名、可直接侧载的 APK（Android 8.0+，targetSdk 34，约 190 KB） |
| [`app/`](app/) | 完整 Android 工程源码（Java，无第三方依赖，Android Studio 可直接打开） |
| [`tools/build-apk.ps1`](tools/build-apk.ps1) | **无需 Gradle / 无需联网**的 APK 构建脚本（aapt2 + javac + d8 + zipalign + apksigner） |
| [`tools/dev_server.py`](tools/dev_server.py) | 零依赖联调后端 + 网页面板，不装摄像头依赖也能验证整条链路 |
| [`tools/test-integration.py`](tools/test-integration.py) | 对**小栖真实 `PhoneIngest`** 的端到端测试（HTTP + WebSocket） |
| [`docs/`](docs/) | 设计、集成、测试报告、真机验收清单 |

> 本目录是仓库的 W11 Android 工程，可独立构建；后端在 `../backend`，前端在 `../frontend`。
> 它只消费后端已有的 `POST /api/ingest/health` 与 WebSocket `phone` 快照，不修改后端/前端代码。

---

## 30 秒上手

### 方式 A：只验证「手机 → 网页」链路（最快，零依赖）

```powershell
# 在仓库根目录执行
cd android
python tools\dev_server.py --port 8765 --token xiaoqi-demo
```

浏览器打开 `http://127.0.0.1:8765/`，把 APK 装到手机：

```powershell
adb install -r release\xiaoqi-steps-1.0.0.apk
```

手机 App → **设置**：

- 电脑地址：`http://<电脑局域网 IP>:8765`（例如 `http://192.168.1.5:8765`）
- 配对令牌：`xiaoqi-demo`
- 点「测试连接」→「保存并启动」→ 授予「身体活动」权限

走几步，面板上的数字会随着自动同步更新。这个面板是**联调面板**，不是 3D 房间；
它和真实前端消费的是同一份 `phone` 快照。

### 方式 B：接真实小栖后端

1. 按小栖原项目文档启动后端（需要其 `requirements.txt` 完整安装，摄像头链路或 `--sim` 均可）。
2. 在电脑上取地址与令牌：
   - 地址：`http://<电脑局域网 IP>:8000`（后端默认监听 `0.0.0.0:8000`）
   - 令牌：后端控制台打印的配对令牌，或浏览器打开 `http://127.0.0.1:8000/api/token`
3. 手机 App 设置里填地址 + 令牌，保存并启动。
4. 电脑端打开小栖房间。手机步数会经
   `POST /api/ingest/health → 后端幂等/聚合 → WebSocket → 前端 steps.js` 自动出现；
   超过 15 分钟没上报会显示「待同步」，而不是旧数字一直挂着。

> **令牌注意**：小栖 `backend/config.yaml` 的 `phone.token` 默认为空，此时后端每次启动
> 会随机生成令牌。想少填几次，可以在你自己的后端配置里固定一个 `phone.token`
> （这是后端配置改动，本 App 目录不改）；App 也提供「自动获取令牌」按钮。

---

## 它做了什么

### 1. 当日步数（核心）

Android 的 `TYPE_STEP_COUNTER` 给的是「**开机以来**累计步数」，不是自然日步数。
App 在前台服务里持续接收传感器事件，维护：

```
今日步数 = 当日零点基线之后的增量
```

并处理四种真实世界的坑：

| 场景 | 处理 |
|---|---|
| **跨零点** | 本地日期变化时今日归零；保留上次读数，让跨零点的少量步数仍能计入新一天 |
| **重启 / 传感器归零** | 新读数 < 旧读数时，把新读数当作「重启后的步数」累加，不丢步 |
| **长时间断流** | 跨天且距上次采样 > 2 小时，整段无法拆分归属 → 不把几天的步数算到今天 |
| **异常跳变** | 同一自然日内按「每秒最多 5 步」做物理上限校验，明显异常不计数 |

没有计步器硬件时自动降级到 `TYPE_STEP_DETECTOR`（每事件 +1）；两者都没有时 UI 会
明确显示「无传感器」，不会假装在计步。

### 2. 后台持续计步

- **前台服务**（`foregroundServiceType="health"`）+ 常驻通知，锁屏不被冻结；
- **开机自启**（`BOOT_COMPLETED`）恢复服务；
- **JobScheduler 15 分钟兜底同步**，前台服务被厂商清理后仍会补报；
- 引导用户把 App 加入**电池优化白名单**（国产 ROM 还需允许自启动/后台运行）。

### 3. 按协议同步

请求体严格遵循小栖接口协议 §4：

```http
POST /api/ingest/health
Content-Type: application/json
X-Xiaoqi-Token: <配对令牌>

{"steps":3210,"ts":1789526000000,"source":"android-app","device_id":"android-xxxx"}
```

- `source` 使用协议 D-009 新增的 **`android-app`**；
- `device_id` 由 `ANDROID_ID` 生成并持久化，用于后端 60 秒幂等去重；
- 默认每 **5 分钟**同步一次；步数每增加 **300 步**且距上次尝试 ≥ **75 秒**时提前同步
  （协议规定 60 秒内重复上报会被丢弃，75 秒是安全下限）；
- 手动「立即同步」；打开 App 时若距上次尝试 ≥75 秒也会顺手补一次；
- 失败保留错误信息并显示在卡片/通知里，不静默吞掉；
- 后端的 `deduped: true` 视为成功（只是被幂等窗口去重）。

### 4. 配对与状态

- 设置页可填地址/令牌、自动获取令牌、测试连接（只读 `/api/health` 与 `/api/state`，不写步数）；
- 「测试连接」会显示后端版本、在线前端数量、服务端已有步数；
- 支持深链导入：
  `xiaoqi://pair?base=http://192.168.1.5:8000&token=xxx`
- 首页展示今日步数圆环、目标进度、同步三态（已同步 / 待同步 / 同步失败）、
  计步方式、服务状态、权限与电池优化状态；
- 设置页提供「+1000 步 / 今日清零」演示工具，便于没有真机传感器时联调。

---

## 数据链

```
TYPE_STEP_COUNTER / TYPE_STEP_DETECTOR
        │  （前台服务，锁屏持续）
        ▼
StepTracker（纯 Java：日切 / 重启 / 断流 / 防跳变）
        │  SharedPreferences
        ▼
SyncClient（HttpURLConnection，无第三方库）
        │  POST /api/ingest/health   X-Xiaoqi-Token
        ▼
小栖后端 PhoneIngest（令牌 / 60s 幂等 / 只前进不回退）
        │  Hub.publish
        ▼
WebSocket /ws  →  frontend/src/live.js  →  steps.js 三态  →  房间 HUD / 挂历
```

本项目的 `tools/test-integration.py` 会直接 `import` 小栖真实的
`xiaoqi.ingest.phone.PhoneIngest` 与 `Hub`，在**不改参考仓库**的前提下验证上面这条链，
包括 WebSocket 广播帧。

---

## 协议对齐表

| 协议项 | 本 App 行为 |
|---|---|
| 路径 | `POST /api/ingest/health` |
| 鉴权 | `X-Xiaoqi-Token`，401 → 显示「令牌错误」 |
| `steps` | 当日累计、非负整数（`0` 合法） |
| `ts` | Unix 毫秒，取上报时刻 |
| `source` | `android-app` |
| `device_id` | `android-<ANDROID_ID>`，稳定、用于幂等 |
| 400 | `INVALID_FIELD` 原样展示 |
| 200 `deduped` | 视为成功，不重试 |
| 60 秒幂等 | 自动同步最小间隔 75 秒；手动连点可能被去重，会明确提示 |
| 只前进不回退 | 服务端行为；App 跨零点上报更小值即触发「新的一天」 |
| 15 分钟 stale | 由后端/前端判断；App 首页也会按 `lastSyncAt` 自行显示「待同步」 |
| `screen_minutes` / `top_apps` | **本版未实现**（D-009 可选扩展；当前后端也未消费） |

---

## 构建 APK

### 已验证的离线构建（推荐）

前置：**JDK 17**（或 21）+ **Android SDK platform 34 + build-tools 34.x**。
不需要 Gradle、不需要联网。

```powershell
# 在仓库根目录执行
cd android
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build-apk.ps1
```

产物：

```
release/xiaoqi-steps-1.0.0.apk
release/BUILD-INFO.txt          # 版本、SHA256、证书指纹、工具链
```

脚本会依次执行 `aapt2 compile/link → javac → d8 → zip classes.dex → zipalign →
apksigner sign → verify → aapt2 dump badging`，并打印 APK 的 SHA256。

### Android Studio / Gradle

`app/` 是标准 Gradle 工程（`namespace com.xiaoqi.steps`，无依赖），用 Android Studio
打开根目录即可。仓库没有附带 Gradle Wrapper 的 jar（本机离线），所以命令行构建以
`tools/build-apk.ps1` 为准。

### 签名说明

`tools/build-apk.ps1` 会在 `build/xiaoqi-debug.keystore` 生成一张**调试证书**并签名
（口令 `xiaoqi2026`，仅用于课程演示/侧载，**不要用于发布**）。证书指纹见
[`release/BUILD-INFO.txt`](release/BUILD-INFO.txt)。

---

## 测试

> 联调脚本只用 Python 标准库，需要 **Python 3.10+**（本环境为 3.13.7）。

```powershell
# 1) 纯 Java 核心：57 项
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\test-core.ps1

# 2) 独立联调后端：17 项（标准库）
python -B .\tools\test-dev-server.py

# 3) 真实 PhoneIngest + WebSocket：24 项
..\backend\.venv\Scripts\python.exe -B .\tools\test-integration.py

# 4) 一键全跑（最后会重新构建 APK）
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\test-all.ps1
```

本次环境的结果：

| 套件 | 结果 | 覆盖 |
|---|---|---|
| `CoreSelfTest` | **57 passed / 0 failed** | 日切、重启、断流、防跳变、降级计步器、URL 归一化、JSON、HTTP 200/400/401、探测接口 |
| `DevServerTest` | **17 passed / 0 failed** | 令牌、幂等、只前进不回退、history、reset、面板 |
| `IntegrationTest` | **24 passed / 0 failed** | 真实 `PhoneIngest`、`source=android-app`、`device_id`、WS 广播、400/401、日期重置 |
| APK 构建 | **OK** | v2/v3 签名校验、manifest 权限/服务类型、dex 类、R.java |

**没有做真机运行测试**：本环境没有连接 Android 设备，SDK 也没有系统镜像，无法
启动模拟器。APK 已通过编译、打包、签名与静态检查；真机验收清单见
[`docs/04-真机验收清单.md`](docs/04-真机验收清单.md)。这是本交付最需要补的一步。

---

## 目录

```
android/
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/xiaoqi/steps/
│       │   ├── core/                 # 纯 Java，可脱离 Android 测试
│       │   │   ├── StepTracker.java  # 今日步数算法
│       │   │   ├── SyncClient.java   # 协议客户端
│       │   │   ├── SyncConfig.java
│       │   │   ├── SyncResult.java
│       │   │   └── MiniJson.java
│       │   ├── MainActivity.java
│       │   ├── SettingsActivity.java
│       │   ├── StepService.java      # 前台计步 + 自动同步
│       │   ├── SyncJobService.java   # 15 分钟兜底
│       │   ├── BootReceiver.java
│       │   ├── AppConfig.java
│       │   ├── StepRepository.java
│       │   ├── Notifications.java
│       │   ├── Permissions.java
│       │   ├── RingView.java
│       │   ├── Ui.java
│       │   └── Format.java
│       └── res/                      # 图标、通知小图标、主题
├── app/src/test/java/...             # CoreSelfTest / SyncHarness
├── tools/                            # 构建、联调、测试脚本
├── docs/                             # 设计 / 集成 / 测试 / 验收
└── release/                             # APK 与构建信息
```

---

## 已知限制

1. **真机未跑**：见上；算法与网络链路已测，Android UI/传感器/厂商后台策略需要真机确认。
2. **首次安装从 0 开始**：不会把安装前的「开机以来」步数算进今天；这是有意为之，避免虚高。
3. **只支持 Android**：与小栖 D-009 一致，不做 iOS；iOS 的 Screen Time entitlement 不可行。
4. **只做步数**：`screen_minutes` / `top_apps` 未实现（需要 `UsageStatsManager` 特殊权限，
   且当前参考后端 `PhoneIngest` 尚未消费这两个字段）。协议已预留，后续可加。
5. **国产 ROM 可能杀后台**：已做前台服务 + 开机自启 + JobScheduler + 电池白名单引导，
   但 MIUI/EMUI/ColorOS 仍需手动允许「自启动 / 后台运行」。
6. **明文 HTTP**：局域网演示用 `usesCleartextTraffic=true`；令牌以明文存应用私有
   SharedPreferences（`allowBackup=false`）。生产场景应上 HTTPS 与系统密钥库。
7. **调试签名**：APK 用调试证书，不适合上架/长期分发。
8. **深链可被同机应用触发**：`xiaoqi://pair` 会写入地址/令牌；演示方便，安全性要求高时
   应加签名校验或改为扫码配对。
9. **时区**：日切用手机本地时区；后端 `steps` 表按电脑本地日期落库。跨时区场景需注意。

---

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/01-设计与实现.md`](docs/01-设计与实现.md) | 架构、步数算法、服务生命周期、同步状态机、安全取舍 |
| [`docs/02-集成指南.md`](docs/02-集成指南.md) | 从零接到真实小栖 / 联调后端，排障表 |
| [`docs/03-测试报告.md`](docs/03-测试报告.md) | 环境、用例、证据、APK 信息、未覆盖项 |
| [`docs/04-真机验收清单.md`](docs/04-真机验收清单.md) | 真机上要逐条勾的验收项 |
| [`release/BUILD-INFO.txt`](release/BUILD-INFO.txt) | 本次 APK 的版本、SHA256、证书指纹、工具链 |

---

## 参考项目

- 小栖 README / 接口协议 v0.1-frz + v0.2-draft（D-009：Android 原生 App、`android-app` 来源）
- 前端 `frontend/src/live.js` / `steps.js`：WebSocket 消费与「无数据不补 0 / 15 分钟待同步」语义
- 后端 `backend/xiaoqi/ingest/phone.py`：令牌、60 秒幂等、只前进不回退

本目录只消费这些文件作为协议依据，不修改 `backend/` 与 `frontend/`。
