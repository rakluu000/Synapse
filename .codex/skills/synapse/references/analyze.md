# `synapse analyze`

技术分析/方案对比：生成结构化分析报告，默认不改代码。

## 用法

```bash
synapse analyze <问题或目标...>
```

## 主要产物

- `<project>/.synapse/context/<slug>-analyze.md`：上下文包
- `<project>/.synapse/patches/<slug>-analyze-claude.md`：分析报告（Claude）
- `<project>/.synapse/logs/*`：Claude stream-json 原始输出

## 输出期望

报告建议包含：

- 目标与非目标
- 现状推断（基于 context pack）
- 候选方案 ≥2（优缺点、风险、成本）
- 推荐方案与迁移步骤

## 失败与恢复

Claude 调用失败不会影响仓库；重跑即可。

