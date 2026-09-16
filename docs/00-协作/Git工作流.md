# Git 工作流

> 目标：3 个人同时写代码**不互相踩**，而且 main 分支**任何时候都能演示**。

---

## 一、分支模型（够用就好）

```
main                 ← 随时可演示，只接受 PR 合并，禁止直接 push
├── feat/vision-baseline     功能分支：feat/模块名-简述
├── fix/ws-reconnect         修复分支：fix/问题简述
└── docs/interface-v0.2      文档分支：docs/改了什么
```

| 规则 | 说明 |
|---|---|
| 每个任务开一个分支 | 分支名带上任务号更好：`feat/xq-003-pose-baseline` |
| 分支存活 ≤ 3 天 | 超过 3 天说明拆得不够小，拆开或先合一个能跑的版本 |
| 至少每天 push 一次 | 哪怕没写完，push 到自己的分支（就是备份） |
| 合并前先 `git pull --rebase origin main` | 避免制造无意义的合并提交 |
| 合并方式用 **Squash merge** | main 的历史 = 一条任务一条提交，干净可读 |

---

## 二、提交信息规范

格式：`<type>(<scope>): <中文简述>`

| type | 用于 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 只改文档 |
| `refactor` | 重构（行为不变） |
| `test` | 测试 |
| `chore` | 构建 / 依赖 / 脚本 |

```
feat(pose): 接入 MediaPipe 关键点并输出头前倾角
fix(ws): 修复断线后不重连的问题
docs(interface): 补充手机上报的幂等去重规则
```

> 禁止：`update`、`修改`、`111`、`fix bug`。**看提交信息要能知道改了什么。**

---

## 三、Pull Request 规范

### 什么时候开 PR

- 写完了 → 开 PR（用 [PR 模板](../../.github/pull_request_template.md)）
- 还没写完但要别人看 → 开 **Draft PR**

### PR 必须包含三件事

1. **做了什么**（一句话 + 涉及哪些模块）
2. **怎么验证的**（跑了什么命令 / 看到什么现象，**没有验证方法的 PR 不合并**）
3. **影响谁**（是否动了接口、动了别人的文件；动了接口必须附接口协议 diff）

### 评审规则

| 项 | 规则 |
|---|---|
| 谁评审 | 至少 1 人，且**不能是自己**；动了某模块优先找该模块主责 |
| 响应时限 | 24 小时内给回应（哪怕只是"我看过了，明天细看"） |
| 什么算通过 | 能跑通 + 不破坏别人的功能 + 评审人已看过 diff |
| 大改动 | 超过 400 行 diff 先别开 PR，先约 15 分钟口头讲一遍 |

---

## 四、main 分支保护（建议开启，只需一次）

仓库 Settings → Branches → Add branch protection rule：

- Branch name pattern: `main`
- ✅ Require a pull request before merging
- ✅ Require approvals: 1
- ✅ Dismiss stale approvals when new commits are pushed
- ❌ 不勾 "Include administrators"（3 人团队别把自己锁死）

> 没开保护也要**自觉遵守**：main 只通过 PR 合入。

---

## 五、冲突纪律（3 人最容易伤感情的地方）

1. **同一文件同一时间只允许一个人改**。要改别人的文件，先群里说一句。
2. **接口协议文件（`docs/02-需求与设计/接口协议.md`）只增不改**：废弃字段标 `deprecated`，不删、不改名，版本号 +1。
3. 冲突了怎么办：**谁的分支后合并谁解冲突**，但**冲突涉及别人逻辑时必须叫上他**，不许靠猜。
4. 解完冲突必须**本地跑一遍**再 push，不能只相信 git 说"合并成功"。

---

## 六、不要提交的东西

| 类型 | 处理 |
|---|---|
| 虚拟环境 / `node_modules` | 进 `.gitignore` |
| 模型权重、大贴图、视频（> 5 MB） | 放 Git LFS 或外部网盘，仓库只留路径说明 |
| 密钥 / 令牌 / 摄像头隐私配置 | **永不提交**，放 `.env`（同样进 `.gitignore`） |
| 个人截图、临时 debug 文件 | 不要提交 |

---

## 七、救命命令（新手区）

| 场景 | 命令 |
|---|---|
| 现在什么状态 | `git status` |
| 拉最新（我的改动还没提交） | `git stash && git pull --rebase && git stash pop` |
| 提交写错了想改 | `git commit --amend`（**只在没 push 时用**） |
| 改乱了想扔掉本地改动 | `git checkout -- <文件>`（**确认不需要了再执行**） |
| 看看我这条分支和 main 差多少 | `git log --oneline main..HEAD` |
| 提交粒度太大 | 别慌，合并时用 Squash，历史自动变干净 |

> ⚠️ 除了自己的功能分支，**任何情况下不要 `git push --force`**。
