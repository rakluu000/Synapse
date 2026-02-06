# `synapse execute`

读取计划文件并执行实现闭环：

- 优先 **resume** 计划中记录的外部会话
- 调用 **Gemini** 产出“原型补丁”（Unified Diff）
- 调用 **Claude** 给出审计意见（可附修复补丁）
- 产物全部落盘到 `./.synapse/**`，由 Codex 主控侧决定是否应用补丁

## 用法

```bash
synapse execute <plan_path>
```

## 读取内容

- `<plan_path>`：从中提取需求、关键步骤、以及 `gemini_session_id`（如有）

## 写入哪些文件

- `<project>/.synapse/context/<slug>-execute.md`：执行上下文包（含 git diff/status 摘要等）
- `<project>/.synapse/logs/*`：两模型 `stream-json` 原始输出
- `<project>/.synapse/patches/*`：
  - `*-gemini.md`：Gemini 最终文本
  - `*-gemini.diff`：从最终文本中提取的 Unified Diff（如可提取）
  - `*-claude.md`：Claude 审计结果（可包含建议补丁）
- `<project>/.synapse/state.json`：更新最近一次执行信息

## 交互确认点（默认要求）

- 进入 execute 前应确认 plan 已被接受（除非用户显式 `--yes` 或已确认继续）
- 若 plan 缺失 `gemini_session_id`：允许新建会话执行，但应告知无法复用上下文

## 失败与恢复（关键）

- **Gemini patch 提取失败**：会保留 `*-gemini.md` 原文；可手动从中复制 diff，或重跑 execute
- **Claude 审计失败**：不阻断 Gemini patch 落盘；可单独重跑审计（再次 execute 或未来提供的专用审计参数）
- **续跑/断点恢复**：
  - 通过 `plan` 文件里的 `gemini_session_id` + `.synapse/state.json`，可以在清空 Codex 对话后继续
  - 后续可使用 `--resume <SESSION_ID>`（如脚本提供该参数）强制续跑同一会话

