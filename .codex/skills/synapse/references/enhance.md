# `synapse enhance`

Prompt 增强：把原始需求整理成更清晰、可执行、可验收的任务描述（默认不改代码）。

## 用法

```bash
synapse enhance <原始需求文本...>
```

## 主要产物

- `<project>/.synapse/patches/<slug>-enhance-claude.md`：增强后的需求（可直接喂给 plan/workflow）
- `<project>/.synapse/logs/*`：Claude stream-json 原始输出

## 失败与恢复

增强失败则保留原始输入；可重跑或直接进入 `synapse plan`。

