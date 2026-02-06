# `synapse execute`

读取计划文件，并按 plan meta 的 `task_type` 生成 **diff 草稿**（不会自动修改产品代码）：

- `frontend`：调用 **Gemini** 产出前端/UI diff 草稿
- `backend`：调用 **Claude** 产出后端/逻辑 diff 草稿
- `fullstack`：两者并行，各自产出一份 diff 草稿

> Codex（主控）把这些 diff 当“草稿”，重写成最终生产级实现，然后再跑 `synapse verify` + `synapse review`。

## 用法

```bash
synapse execute <plan_path>
```

## 读取内容

- `<plan_path>`：提取 `request`、`task_type`、关键步骤、以及外部模型 `session_id`（如有）

## 写入哪些文件

- `<project>/.synapse/context/<slug>-execute.md`：执行上下文包（含 git diff/status 摘要等）
- `<project>/.synapse/logs/*`：外部模型 `stream-json` 原始输出
- `<project>/.synapse/patches/*`：
  - `*-execute-draft-gemini.md/.diff`（仅 frontend/fullstack）
  - `*-execute-draft-claude.md/.diff`（仅 backend/fullstack）
- `<project>/.synapse/state.json`：更新最近一次执行信息（包含草稿路径、会话信息）

## 交互确认点（默认要求）

- 进入 execute 前：确认 plan 已被接受
- 落地改代码前：Codex 主控侧需展示“将改哪些文件 + verify 计划”，再次确认

## 失败与恢复（关键）

- diff 提取失败：会保留对应 `*.md` 原文；可手动从中复制 diff，或重跑 `execute`
- 续跑/断点恢复：依靠 plan 文件里的 `sessions` + `.synapse/state.json` 继续（必要时用 CLI `--resume*` 强制覆盖）
