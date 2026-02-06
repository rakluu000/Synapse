# `synapse optimize`

性能/质量优化：输出优化建议，必要时可让模型给出可落盘的 Unified Diff Patch（但默认只生成建议与补丁文件，不直接修改产品代码）。

## 用法

```bash
synapse optimize <目标描述...>
```

## 主要产物

- `<project>/.synapse/context/<slug>-optimize.md`
- `<project>/.synapse/patches/<slug>-optimize-claude.md`
- `<project>/.synapse/patches/<slug>-optimize-claude.diff`（若能提取）
- `<project>/.synapse/logs/*`

## 失败与恢复

同 `analyze/debug`：失败不改代码，重跑即可。

