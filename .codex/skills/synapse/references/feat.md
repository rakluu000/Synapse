# `synapse feat`

“功能开发”快捷入口（同 `workflow`）：生成 plan + 草稿 diff + 审计材料，便于 Codex 主控侧落地实现。

## 用法

```bash
synapse feat [--task-type <frontend|backend|fullstack>] <需求文本...>
```

## 行为约定

- 默认等价于 `synapse workflow <需求>`（分阶段、可确认）
- 产物路径与 `workflow` 一致：`.synapse/plan`、`.synapse/context`、`.synapse/patches`、`.synapse/logs`

## 失败与恢复

同 `references/workflow.md`。
