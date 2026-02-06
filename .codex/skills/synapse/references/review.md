# `synapse review`

对当前仓库的 `git diff` 做一次**外部审计**（audit），把审计报告落盘到 `./.synapse/**`，供 Codex 主控侧修正与复跑验证。

## 用法

```bash
synapse review [--plan-path <plan_path>] [--task-type <frontend|backend|fullstack>]
```

> 如果不传 `--plan-path/--task-type`：脚本会尽量从 `.synapse/state.json` 的最近一次 plan/execute 推断；仍无法推断则默认按 `fullstack` 审计（可能更费钱）。

## 模型分工（本阶段）

- **Claude**：总体代码审计（正确性/安全/边界/可维护性/测试覆盖）
- **Gemini**：仅当 `task_type` 包含 `frontend` 时，做 UI/UX/可访问性/一致性审计
- **Codex（主控）**：根据审计修正代码，并复跑 `synapse verify`

## 写入哪些文件

- `<project>/.synapse/context/<slug>-review.md`：审计上下文包（git status/diff + snippets/rg）
- `<project>/.synapse/logs/*`：外部模型 `stream-json` 原始输出
- `<project>/.synapse/patches/*`：
  - `*-review-audit-claude.md`
  - `*-review-audit-gemini.md`（仅 frontend/fullstack）
- `<project>/.synapse/state.json`：记录最近一次 review 的输入范围与产物路径

## 失败与恢复

- 非 git 仓库：退化为仅生成 context pack 并输出“需手动审计”提示（不会崩溃）
- diff 过大：context pack 会截断；建议拆分改动后再 review
