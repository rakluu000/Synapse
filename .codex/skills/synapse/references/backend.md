# `synapse backend`

后端/逻辑专项：默认由 **Codex 主控侧**完成实现（不强制调用外部模型），脚本负责落盘上下文包与任务记录，便于可重复执行与审计。

## 用法

```bash
synapse backend <需求文本...>
```

## 主要产物

- `<project>/.synapse/context/<slug>-backend.md`：上下文包（git/rg 摘要 + 关键文件片段）
- `<project>/.synapse/patches/<slug>-backend-task.md`：结构化任务描述（给 Codex 主控侧直接执行）
- `<project>/.synapse/state.json`：记录最近一次 backend 任务

## 失败与恢复

- 任何失败都不会修改产品代码；修复环境后重跑即可
- 若需要外部模型辅助，可改用 `synapse plan/execute` 或在 backend 任务中显式要求生成 patch 并落盘

