# `synapse review`

默认审查当前仓库的 `git diff`（以及 staged/unstaged 状态），并在 **Codex 主控侧**执行一次“独立二审”（review-only）。

## 用法

```bash
synapse review
```

## 主要产物

- `<project>/.synapse/context/<slug>-review.md`：包含 diff 摘要与关键片段（用于 Codex 主控侧审查）
- `<project>/.synapse/state.json`：记录最近一次 review 的输入范围

## 审查范围（默认）

- `git status --porcelain -b`
- `git diff`（必要时截断）

## 失败与恢复

- 非 git 仓库：退化为仅生成文件扫描/rg 摘要（不会崩溃）
- diff 过大：context pack 会截断；建议缩小范围或先拆分改动再 review

