# `synapse feat`

“功能开发”快捷入口：按需生成计划、补丁与审计产物，落盘到 `./.synapse/**`，便于 Codex 主控侧按计划实施。

## 用法

```bash
synapse feat <需求文本...>
```

## 行为约定

- 默认等价于 `synapse workflow <需求>`（分阶段、可确认、可 `--yes` 一路跑）
- 产物路径与 `workflow` 一致：`.synapse/plan`、`.synapse/context`、`.synapse/patches`、`.synapse/logs`

## 失败与恢复

同 `references/workflow.md`。

