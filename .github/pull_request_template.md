<!--
PR 标题格式：<type>(<scope>): <中文简述>，例：feat(pose): 接入 Lightweight OpenPose 抽检
标题请删掉本行注释。
-->

## 做了什么

<!-- 一句话说清产出，列出涉及的模块（W1–W13，见 docs/02-需求与设计/系统架构.md） -->

- 模块：
- 关联卡片：XQ-0NN（带任务名，例：XQ-010 美术风格参考收集）

## 怎么验证的

<!-- ⚠️ 没有验证方法的 PR 不合并。写清命令 / 步骤 / 预期现象 -->

```bash
# 例：起服务 + 手动触发一次抽检（需 torch + LW 权重，见 backend/models/README.md）
cd backend && python -m xiaoqi --port 8000

curl -s http://127.0.0.1:8000/api/health | jq '.sitting'
curl -s -X POST http://127.0.0.1:8000/api/sitting/check | jq
curl -s http://127.0.0.1:8000/api/sitting/latest | jq
```

预期：`sitting.model_ready=true`；`latest` 返回 `head_pitch_deg` / `torso_lean_deg` / `state`（抽检结果走 `type:"sitting"`，不进状态机）。

## 影响范围

- [ ] 改了接口协议（`docs/02-需求与设计/接口协议.md`）—— 已附 diff 并知会 A / C / D
- [ ] 改动了别人的文件（已在群里说过，并 @ 了模块 owner）
- [ ] 新增依赖（列在下面）
- [ ] 只改文档

新增依赖：

## 自检清单

- [ ] 本地跑通，且没有破坏别人已完成的功能
- [ ] 若动了姿态链路：本机已装 `torch` + LW 权重（`/api/health` 的 `sitting.model_ready=true`）
- [ ] 没有提交密钥 / 大文件 / 虚拟环境（含 LW 权重 `*.pth` 与 LW 仓库）
- [ ] 提交信息符合规范
- [ ] 相关文档已同步更新（代码改了文档没改 = bug）

## 评审人请注意看

<!-- 指出你自己最没把握的地方，节省评审时间 -->
