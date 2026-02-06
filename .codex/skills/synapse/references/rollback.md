# `synapse rollback`

安全回滚工具：默认 **dry-run**，展示将执行的 git 命令，需二次确认（或 `--yes`）才会真正回滚。

## 用法

```bash
synapse rollback --target <rev> [--mode reset|revert] [--branch <name>] [--dry-run] [--yes]
```

## 行为说明

- `reset`：本地 `git reset --hard <target>`（改变历史；不自动强推）
- `revert`：`git revert <target>..HEAD`（生成反向提交；不自动 push）

## 失败与恢复

- 若误操作：可用 `git reflog` 找回（脚本应在执行前打印当前 HEAD）
- merge/rebase 中：拒绝执行，要求先处理冲突

