# review.md — 小栖（xiaoqi）审查判据

> 给**独立审核 Agent**。跨仓通用纪律见 vault `01-Projects/AI任务系统/治理/模板/review模板.md`。
> 本仓**无 AGENTS.md、无任何测试文件**（实测 `test_*.py` / `*_test.py` = 0，`frontend` 亦无测试）。所以"没有测试可跑"是本仓的常态，不是免检理由——见第三节。

## 一、本仓形态（三路取证，互不冒充）

| 层 | 形态 | 首取证 |
|---|---|---|
| `backend/xiaoqi` | Python + FastAPI + WebSocket（`ingest/behavior·phone` → `rules/posture_rules·calibration` → `state/machine` → `hub` → `store/db`） | CLI/服务端端到端实跑：真实输入 → 状态输出 → 落盘 |
| `frontend` | Three.js + Vite 的浏览器 3D 场景（`scene`/`hud`/`viewer`/`main`） | 真浏览器（Playwright）打开 `dev`/`preview`，看角色状态与 console 报错，截图 |
| 感知端 | 外置 USB 摄像头 + MediaPipe、Windows 前台应用采集 | **真机联调**（mock 绿 ≠ 真机绿） |

## 二、失败长什么样

| 类别 | 具体形态 |
|---|---|
| **用 mock 冒充真链路**（本仓头号风险） | `scripts/mock_server.py` / `debug_view.py` 跑通只能证明后端与前端契约通，**不能证明**姿态判定、摄像头取流、Windows 前台采集工作。证据里把 mock 写成"已验证"必须报 important。真机不可达时记入 RUN「未执行 + 原因」，**不得推断为通过** |
| **姿态状态口径** | 五态（坐直 / 驼背 / 伏案 / 起身 / 喝水）的阈值与滞回、校准（`calibration.py`）改动，会静默改变所有下游统计。任何"占比/时长/次数"结论必须写明**口径**（含不含起身、跨天怎么切、暂停时段算不算）——同一指标能算出多个数时，"恰好算出一个数"最危险 |
| **状态机与实时推送** | WebSocket 断线重连后的状态补齐、重复推送、时序错乱（HTTP 上报与 WS 推送竞争同一状态）；状态跳变（未校准直接判驼背）；`hub` 单点故障导致前端停在旧状态而不报错 |
| **前后端口径二次加工** | 前端不得自己判姿态、不得二次排序/换算（渲染以后端下发为准，先例：wild-work R130「排序完全由后端决定」）。HUD 显示"0"表示"上游没给"还是"真的是 0"必须区分——**缺数据显示「—/待同步」，显示 0 就是编造** |
| **Windows 采集侧** | `behavior.py` 走 PowerShell 时有三个已在本机其他仓实测过的坑：① 输出编码（PS 默认 GBK 会把中文路径读成乱码，须显式 UTF-8）；② `-NonInteractive` 下 **CLIXML 混在载荷之前进 stdout**（须整段切除，且不能用 `CombinedOutput`）；③ 用 `Start-Process` 拉 GUI 可能返回 `0xc0000142`（须直接 `Start()` + `DETACHED_PROCESS`）。隐私面：前台应用采集属个人数据，落盘内容与保留期必须与需求一致，不得悄悄多采 |
| **持久化** | `store/db.py` 写入路径与 `backend/data/` 是否入库/入 `.gitignore`；时间戳时区（须固定 UTC+8 墙钟口径，用 `time.Local` 会跨机算错一天）；清理/覆盖策略；写失败必须报错而非静默 |
| **分层纪律** | 编排层（`collect_flow` 式模块）**零 Qt/宿主依赖**，好让命令行复用；CLI 是**唯一**允许编排多个业务模块的地方——GUI 里偷偷编排第二套流程 = 双真相源 |
| **产品定位红线** | README 明确它**不是**「医疗级姿态检测仪器」、不是弹窗提醒软件、不是「AI 健康管理平台」。出现医疗/诊断/精度承诺，或用弹窗替代角色行动，属越界，按 important 报 |
| **交付物可复现** | `XD-002`（端到端联调与真机演示）、`XE-001`（演示视频）、`XE-002`（答辩问答）是**交付类包**：证据须是可重放的现场步骤（启动命令 → 输入 → 期望现象 → 录屏/截图帧号），不能只有"演示通过"一句结论 |

## 三、验证方式（当场实测，本文件不写基线数字）

```bash
# 后端（Windows 侧或 WSL 均可，但必须记录实际用的哪一侧）
cd backend && python -m xiaoqi.main                 # 起服务，记录端口
curl -s http://127.0.0.1:<port>/... | head -c 300   # 接口形状；状态端点须含口径字段
python -c "import fastapi, uvicorn; print('deps ok')"

# 前端（真浏览器取证）
cd frontend && npm run build && npm run preview     # 构建 + 起预览
# Playwright 打开预览：查 console 零报错、切三种状态看角色是否响应、截图

# Windows 采集侧
# behavior.py 的采集函数单独跑一次，确认输出解析正确（编码 / CLIXML / 退出码三处都要看）
```

**证据包**：后端端到端命令与输出 + 前端 3D 场景真截图（至少含一个状态切换前后各一张）+ console 零报错 + 涉及真机感知的实测记录或「未执行」声明。
**建议（非阻塞）**：本仓零回归资产——任何改动都至少落一条可重跑断言（`backend/tests/` + `pytest`），否则下一轮无法证明上一轮没退化。

## 四、不报

Three.js 代码风格与着色器口味 · 3D 美术观感（属设计层，除非与需求决策冲突）· `frontend/node_modules`、`dist`、`__pycache__` · 未在本包 `allowed_paths` 内的文件 · 已有 mock 本身（mock 是正当工具，问题只在**拿它冒充真机**）

## 五、待仓库负责人校正

1. **哪些状态属"绝不能算错"的**：久坐时长？喝水次数？步数？——口径错了会直接影响你的健康判断，这类要设成审核高风险区。
2. 摄像头/前台应用采集的数据**保留多久、放哪儿、可不可导出**？（隐私红线得由你定，我不替你裁决）
3. 答辩演示的最短成功链路是哪几步？我照它写"可重放步骤"作为验收证据格式。
