# `synapse backend`

后端/逻辑专项：用 **Claude** 产出后端 diff 草稿（Unified Diff），落盘到 `./.synapse/**`，再由 Codex（主控）重写为最终实现。

## 用法

```bash
synapse backend <需求文本...>
```

## 主要产物

- `<project>/.synapse/context/<slug>-backend.md`：上下文包（git/rg 摘要 + 关键文件片段）
- `<project>/.synapse/patches/<slug>-backend-claude.md`：Claude 原始文本
- `<project>/.synapse/patches/<slug>-backend-claude.diff`：提取出的 unified diff（如可提取）
- `<project>/.synapse/logs/*`：Claude stream-json 原始输出
- `<project>/.synapse/state.json`：记录最近一次 backend 任务（含 session_id 与产物路径）

## 失败与恢复

- patch 提取失败：保留 `*.md` 原文；可手动复制 diff 或重跑
- 会话丢失：重跑不影响既有产物；会生成新日志与新 patch 文件
