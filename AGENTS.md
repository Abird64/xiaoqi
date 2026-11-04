# 小栖（xiaoqi）项目开发规范与纪律

本文件是小栖项目（`D:\code\xiaoqi`）在 Windows 开发环境下的代码级规则基准。

## 1. 核心红线

1. **统一开发端**：小栖正式开发环境已统一收拢至 **Windows 本地（`D:\code\xiaoqi`）**，具备摄像头驱动、音视频采集与真机演示依赖，不再以 WSL 为主开发端。
2. **禁止擅自暂存**：严禁未经显式授权执行 `git add`，避免触发上游自动同步机制。只读检查优先使用 `git status -s` 与 `git diff`。
3. **不可逆操作举手**：禁止擅自执行 `git commit`、`git push`、`git checkout`、`git reset` 或删除未提交文件。
4. **禁止私自合并与关闭 PR**：不 approve / 不 merge 自己的 PR（项目通用红线）。

## 2. 工程常用命令与构建基准

- **前端路径**：`D:\code\xiaoqi\frontend`
  - 安装依赖：`npm install`
  - 开发热更：`npm run dev`（默认端口 5173，支持 URL 参数 `?ws=ws://127.0.0.1:8000/ws`）
  - 生产构建：`npm run build`（构建输出 `dist/`，要求退出码 0）
- **后端路径**：`D:\code\xiaoqi\backend`
  - 依赖安装：`pip install -r requirements.txt`
  - 模拟运行：`python -m xiaoqi --sim --port 8000`
  - 真机运行：`python -m xiaoqi --port 8000`

## 3. 架构真相源与审核指针

- **审核判据**：见项目根目录 `review.md`（包含各模块验收标准与红线指标）。
- **空间口径**：见 `frontend/README.md` 与 `docs/02-需求与设计/系统架构.md`（1 单位 = 1 米，地面 y = 0，房间 6×6×3）。
- **接口协议**：见 `docs/02-需求与设计/接口协议.md`（WS 6 姿态枚举：`unknown` / `upright` / `slouch` / `desk_hunch` / `away` / `drinking`）。
- **场景配置**：见 `frontend/src/scene/scene-layout.json`（由内置 Studio 工具一键导出和维护）。
