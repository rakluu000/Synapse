# `synapse commit`

安全的 Git 提交辅助：

- 读取当前改动，生成 Conventional Commit 风格的提交信息（可选 emoji）
- 默认 **dry-run**（只生成提交信息与建议，不执行 `git commit`）

## 用法

```bash
synapse commit [--all] [--amend] [--no-verify] [--signoff] [--emoji] [--type <type>] [--scope <scope>] [--yes]
```

## 写入哪些文件

- `<project>/.synapse/patches/<slug>-commit-message.txt`：生成的提交信息
- `<project>/.synapse/state.json`：记录最近一次 commit 建议

> 若 `--yes` 且实现允许执行提交：也会修改 git 元数据（`.git/**`）。默认不执行。

## 失败与恢复

- 无改动：输出提示并退出
- 生成信息失败：可手工填写提交信息或重跑

