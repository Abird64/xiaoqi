# 小栖（xiaoqi）项目开发规范与纪律

本文件是小栖项目的代码级规则基准。**开发机是 Linux**（组长：`/home/abird/Workspace/Projects/xiaoqi`，Ubuntu / Wayland），**组员的机器是 Windows**，因此同一份代码必须两边都能跑。

## 1. 核心红线

1. **一套实现，两套平台**：代码只有一份，**不允许** `if sys.platform` 分叉出两个功能实现，也**不允许**"Linux 上能跑、Windows 上注释掉一半"。平台差异只允许出现在一处：`backend/xiaoqi/vision/camera_util.py`（选摄像头后端）与错误提示文案。别处要开摄像头，一律调 `open_capture()`。
2. **禁止擅自暂存**：严禁未经显式授权执行 `git add`，避免触发上游自动同步机制。只读检查优先使用 `git status -s` 与 `git diff`。
3. **不可逆操作举手**：禁止擅自执行 `git commit`、`git push`、`git checkout`、`git reset` 或删除未提交文件。
4. **禁止私自合并与关闭 PR**：不 approve / 不 merge 自己的 PR（项目通用红线）。

## 2. 工程常用命令与构建基准

- **前端路径**：`frontend/`
  - 安装依赖：`npm install`
  - 开发热更：`npm run dev`（默认端口 5173，支持 URL 参数 `?ws=ws://127.0.0.1:8000/ws`）
  - 生产构建：`npm run build`（构建输出 `dist/`，要求退出码 0）
  - 单测：`npm test`（= `node --test`）；**不要**写 `node --test test/`，Node 22 会把目录当文件跑，必定 `# fail 1`。
- **后端路径**：`backend/`
  - Linux（本机）：依赖装进 `backend/.venv`（Python 3.14，`.venv/` 已忽略）
    - `backend/.venv/bin/pip install -r requirements.txt`
    - 模拟运行：`backend/.venv/bin/python -m xiaoqi --sim --port 8000`
    - 真机运行：`backend/.venv/bin/python -m xiaoqi --port 8000`（`sitting_camera_index=0` → `/dev/video0`）
  - Windows（组员）：`py -3 -m venv .venv` → `.venv\Scripts\pip install -r requirements.txt` → `.venv\Scripts\python -m xiaoqi --port 8000`（摄像头 `sitting_camera_index=0` 是 DSHOW 编号 0）
- **摄像头**：后端选择集中在 `camera_util.py` —— Windows 先 DSHOW 再 MSMF 再 ANY，Linux 先 V4L2 再 ANY。诊断命令：Linux `v4l2-ctl --list-devices`；Windows 设备管理器 + 隐私 → 相机。

## 3. 平台约束（别踩）

- **Wayland 拿不到全局前台窗口**：W10 行为采集（`ingest/behavior.py`）在 Linux 下需 `xdg-desktop-portal` 或 X11 会话（`XGetInputFocus` / `xdotool getactivewindow`）；Windows 下是 `pywin32` 前台窗口。本机是 `XDG_SESSION_TYPE=wayland`，该链路待定（D-015 / P10），**不要**在本机用 mock 声称已通。
- **性能与验收数字按平台分开记**：帧率、单次推理耗时、模型可用性两边不同，报告里必须标明取自哪台机器，不得混算。
- **姿态源只有一条**：真实姿态由坐姿抽检（Lightweight OpenPose）在 `vision/spot_check.py` 产出，结果走独立 `type:"sitting"`，不进状态机；MediaPipe 实时链已整条删除（D-016），不要再加回来。`--sim` 用合成数据，不碰摄像头。

## 4. 架构真相源与审核指针

- **审核判据**：见项目根目录 `review.md`（包含各模块验收标准与红线指标）。
- **空间口径**：见 `frontend/README.md` 与 `docs/02-需求与设计/系统架构.md`（1 单位 = 1 米，地面 y = 0，房间 6×6×3）。
- **接口协议**：见 `docs/02-需求与设计/接口协议.md`（WS 6 姿态枚举：`unknown` / `upright` / `slouch` / `desk_hunch` / `away` / `drinking`；抽检结果走独立 `type:"sitting"`，不进状态机）。
- **场景配置**：见 `frontend/src/scene/scene-layout.json`（由内置 Studio 工具一键导出和维护）。
