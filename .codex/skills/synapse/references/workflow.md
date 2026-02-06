# `synapse workflow`

Codex 主导的“一条龙”研发工作流（推荐入口）：

`init → plan → execute(草稿) → (Codex 落地改代码) → verify → review`

## 用法

```bash
synapse workflow [--task-type <frontend|backend|fullstack>] [--yes] <需求文本...>
```

## 默认行为（重要）

- `plan`/`execute` 阶段会调用外部模型产出**草稿**与审计材料，但**不会自动改产品代码**
- 产品代码的最终修改由 **Codex（主控）**在对话中完成（把 diff 当草稿重写）
- `verify` 可能会触发项目级依赖安装/锁文件生成（由用户已授权；详见 `references/verify.md`）
- 若传 `--yes`：脚本会自动跑到 `execute` 结束（跳过“plan 后确认”停顿）

## 写入哪些文件

- 会调用 `init/plan/execute`，因此会写入：
  - `<project>/AGENTS.md`
  - `<project>/.gitignore`
  - `<project>/.synapse/**`（plan/context/logs/patches/state/index）
- 后续 `verify`/`review` 还会写入：
  - `<project>/.synapse/**`（更多日志/审计报告）
  - 以及**项目级**副产物（如 lockfile、`.venv/`、`node_modules/`、build 输出）——取决于项目工具链

## 失败与恢复（关键）

- 任一阶段失败：
  - 已完成阶段的产物会保留在 `./.synapse/**`
  - 修复问题后从失败阶段重跑即可（通常不需要重跑 init）
- 清空 Codex 对话仍可续跑：
  - 依赖 `.synapse/state.json`（最近 plan/execute 信息）
  - 以及 plan 文件里的 `sessions` 继续执行
