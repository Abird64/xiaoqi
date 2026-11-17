# review.md — 小栖（xiaoqi）审查判据

> 给**独立审核 Agent**。跨仓通用纪律见 vault `01-Projects/AI任务系统/治理/模板/review模板.md`。
> 本仓**无 AGENTS.md、无任何测试文件**（实测 `test_*.py` / `*_test.py` = 0，`frontend` 亦无测试）。所以"没有测试可跑"是本仓的常态，不是免检理由——见第三节。

## 一、本仓形态（三路取证，互不冒充）

| 层 | 形态 | 首取证 |
|---|---|---|
| `backend/xiaoqi` | Python + FastAPI + WebSocket（`ingest/behavior·phone` → `vision/spot_check` + `rules/sitting_rules` → `hub` → `store/db`；`--sim` 走 `posture_rules·calibration` → `state/machine`） | CLI/服务端端到端实跑：真实输入 → 抽检输出 → 落盘 |
| `frontend` | Three.js + Vite 的浏览器 3D 场景（`scene`/`hud`/`viewer`/`main`） | 真浏览器（Playwright）打开 `dev`/`preview`，看角色状态与 console 报错，截图 |
| 感知端 | 外置 USB 摄像头 + Lightweight OpenPose（torch CPU，60s 抽检）、前台应用采集（Windows=pywin32，Linux X11=XGetInputFocus，Wayland 见 P10） | **真机联调**（mock 绿 ≠ 真机绿） |

## 二、失败长什么样

| 类别 | 具体形态 |
|---|---|
| **用 mock 冒充真链路**（本仓头号风险） | `scripts/mock_server.py` / `scripts/detect_image.py` 跑通只能证明后端与前端契约通、LW 单图诊断能出数，**不能证明**真机抽检（摄像头取流 → 60s 周期推理）、前台采集工作。证据里把 mock 写成"已验证"必须报 important。真机不可达时记入 RUN「未执行 + 原因」，**不得推断为通过** |
| **姿态状态口径** | 五态（坐直 / 驼背 / 伏案 / 起身 / 喝水）的阈值与滞回、校准（`calibration.py`）改动，会静默改变所有下游统计。抽检结果走独立的 `type:"sitting"` 通路，**不进状态机**，不得与 `pose_state` 合并统计（D-014/D-016）。任何"占比/时长/次数"结论必须写明**口径**（含不含起身、跨天怎么切、暂停时段算不算）——同一指标能算出多个数时，"恰好算出一个数"最危险 |
| **状态机与实时推送** | WebSocket 断线重连后的状态补齐、重复推送、时序错乱（HTTP 上报与 WS 推送竞争同一状态）；状态跳变（未校准直接判驼背）；`hub` 单点故障导致前端停在旧状态而不报错 |
| **前后端口径二次加工** | 前端不得自己判姿态、不得二次排序/换算（渲染以后端下发为准，先例：wild-work R130「排序完全由后端决定」）。HUD 显示"0"表示"上游没给"还是"真的是 0"必须区分——**缺数据显示「—/待同步」，显示 0 就是编造** |
| **行为采集侧（Linux / Wayland）** | `behavior.py`（W10 至今未实现）在本机 **Wayland** 下拿不到全局前台窗口：`XGetInputFocus` / `xprop` / `xdotool getactivewindow` 只对 X11 有效，Wayland 下要么返回无效值要么直接连不上 display。可行路径只有 `xdg-desktop-portal`（需用户授权、逐次弹窗、能力受限）或退化成进程活跃度估算。任何"前台应用已能采集"的表述必须报 important；用 `Xlib` 在 XWayland 下读到的是 XWayland 客户端而不是全桌面，别当成成功。隐私面：前台应用采集属个人数据，落盘内容与保留期必须与需求一致，不得悄悄多采 |
| **持久化** | `store/db.py` 写入路径与 `backend/data/` 是否入库/入 `.gitignore`；时间戳时区（须固定 UTC+8 墙钟口径，用 `time.Local` 会跨机算错一天）；清理/覆盖策略；写失败必须报错而非静默 |
| **分层纪律** | 编排层（`collect_flow` 式模块）**零 Qt/宿主依赖**，好让命令行复用；CLI 是**唯一**允许编排多个业务模块的地方——GUI 里偷偷编排第二套流程 = 双真相源 |
| **产品定位红线** | README 明确它**不是**「医疗级姿态检测仪器」、不是弹窗提醒软件、不是「AI 健康管理平台」。出现医疗/诊断/精度承诺，或用弹窗替代角色行动，属越界，按 important 报 |
| **交付物可复现** | `XD-002`（端到端联调与真机演示）、`XE-001`（演示视频）、`XE-002`（答辩问答）是**交付类包**：证据须是可重放的现场步骤（启动命令 → 输入 → 期望现象 → 录屏/截图帧号），不能只有"演示通过"一句结论 |

## 三、验证方式（当场实测，本文件不写基线数字）

```bash
# 后端（Linux 开发机用 backend/.venv；Windows 组员机用 .venv\Scripts\python，命令其余相同）
cd backend && python -m xiaoqi --sim --port 8000   # 无摄像头验证接口与 WS
python -m xiaoqi --port 8000                       # 真摄像头 + 60s 抽检（需 torch + LW 权重）
curl -s http://127.0.0.1:8000/api/health | jq '.sitting, .pose_source'   # model_ready / last_error / 姿态源
python -c "import torch, fastapi, uvicorn; print('deps ok')"   # 少 torch 就没有姿态数据
# 摄像头诊断：Linux `v4l2-ctl --list-devices`；Windows 设备管理器 + 设置→隐私→相机

# 前端（真浏览器取证）
cd frontend && npm run build && npm run preview     # 构建 + 起预览
# Playwright 打开预览：查 console 零报错、切三种状态看角色是否响应、截图

# 行为采集侧（Linux · Wayland 下不可行，见 D-015 / P10；Windows 用 pywin32）
# 不要在本机用 mock 假装前台窗口采集已通；Wayland 拿不到全局焦点就是拿不到
```

**证据包**：后端端到端命令与输出 + 前端 3D 场景真截图（至少含一个状态切换前后各一张）+ console 零报错 + 涉及真机感知的实测记录或「未执行」声明。
**建议（非阻塞）**：本仓零回归资产——任何改动都至少落一条可重跑断言（`backend/tests/` + `pytest`），否则下一轮无法证明上一轮没退化。

## 四、不报

Three.js 代码风格与着色器口味 · 3D 美术观感（属设计层，除非与需求决策冲突）· `frontend/node_modules`、`dist`、`__pycache__` · 未在本包 `allowed_paths` 内的文件 · 已有 mock 本身（mock 是正当工具，问题只在**拿它冒充真机**）

## 五、待仓库负责人校正

1. **哪些状态属"绝不能算错"的**：久坐时长？喝水次数？步数？——口径错了会直接影响你的健康判断，这类要设成审核高风险区。
2. 摄像头/前台应用采集的数据**保留多久、放哪儿、可不可导出**？（隐私红线得由你定，我不替你裁决）
3. 答辩演示的最短成功链路是哪几步？我照它写"可重放步骤"作为验收证据格式。
