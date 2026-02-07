# Synapse（Codex Skill）

Synapse 是一个 **Codex 主导**的多模型研发工作流模板（Codex + Claude + Gemini）：

- **外部模型（Claude/Gemini）只产“草稿”（diff/审计）**，不做真实文件读写
- **Codex 负责最终落地改代码 + 运行验证 + 交付**
- 所有流程产物统一落盘到目标项目的 `./.synapse/**`，便于断点续跑与审计

> 目标体验：接近 `ccg-workflow` 的“一条龙研发流程”，但把主控从 Claude 迁移到 Codex。

---

## 文档分工（重要）

为节省上下文与降低模型成本，文档按用途拆分：

1) `README.md`（本文件）  
给**人**看的总说明：理念、全流程、目录结构、verify 探测策略、维护与扩展指南。

2) `.codex/skills/synapse/SKILL.md`  
给 **Codex** 的“执行协议”：触发条件、路由规则、必须读取 `references/<cmd>.md`、安全边界与确认点。

3) `.codex/skills/synapse/references/*.md`  
给 **每个命令**的“短规格说明”：用法、输入/输出、写入范围、确认点、失败恢复、模型分工（尽量短）。

---

## 目录结构

本仓库中，Skill 本体位于：

- `.codex/skills/synapse/`
  - `scripts/`：CLI 入口与实现（Python）
  - `references/`：命令文档（被 SKILL.md 要求“按需读取”）
  - `assets/defaults.json`：超时/重试/stream-json 保护/上下文包/写入安全等配置

目标项目中，Synapse 运行后会生成：

- `./.synapse/plan/`：plan 文件（含 meta JSON：`task_type`、sessions 等）
- `./.synapse/context/`：context pack（git diff/status + rg 摘要 + snippets）
- `./.synapse/logs/`：外部模型 stream-json 日志、verify 命令日志
- `./.synapse/patches/`：草稿 diff、审计报告等
- `./.synapse/prompts/`：Codex 生成并渲染后的 prompts（可审计/可复现）
- `./.synapse/state.json`：最近一次命令/产物/会话信息（用于续跑）
- `./.synapse/index.json`：plan 索引

你可以用 `synapse ui` 打开本地只读 Web Viewer，默认按 `slug → phase → model` 分组显示时间线，并可切换到 Browse 视图浏览原始目录列表。

---

## 模型分工（全阶段，一览）

### 路由规则（方案 A）

在 `synapse plan` 时显式指定（并写入 plan meta）：

- `task_type=frontend`：只走前端链路
- `task_type=backend`：只走后端链路
- `task_type=fullstack`：前后端都走（成本最高，但最稳）

### 分工矩阵

| 阶段 | Codex（主控） | Claude | Gemini |
|---|---|---|---|
| `init` | 写入约束文件与布局 | 不调用 | 不调用 |
| `plan` | 生成 prompts + 合并为最终可执行计划（对话中完成） | 主计划：架构/边界/风险/测试 | 仅 `frontend/fullstack`：UI/UX/可访问性计划 |
| `run (draft diff)` | 把 diff 当草稿，重写成最终代码（对话中完成） | 仅 `backend/fullstack`：产后端 diff 草稿 | 仅 `frontend/fullstack`：产前端 diff 草稿 |
| `verify` | 运行并解读验证结果 | 不调用 | 不调用 |
| `run (audit)` | 根据审计修正代码并复跑验证 | 总体审计：正确性/安全/边界/可维护性 | 仅 `frontend/fullstack`：UI/UX/可访问性审计 |
| `workflow/feat` | 一条龙编排（在 **Codex 对话**中完成；脚本提供 `init/pack/plan/run/verify/ui` 原语） | 见各阶段 | 见各阶段 |

---

## 快速开始（在任意目标项目中运行）

前置依赖（建议）：

- `git`、`rg`（ripgrep）
- `uv`（Python 运行/依赖：本项目强制 Python 相关使用 `uv`）
- 本机 `claude` CLI、`gemini` CLI（外部模型调用）

PowerShell 示例：

```powershell
$SkillDir = "H:\Project-C\Synapse\.codex\skills\synapse"
$Project  = "D:\your-project"

# 1) 初始化（幂等）
uv run --no-project python "$SkillDir\scripts\synapse.py" --project-dir "$Project" init

# 2) 生成计划（写 task_type 到 plan meta）
uv run --no-project python "$SkillDir\scripts\synapse.py" --project-dir "$Project" plan --task-type fullstack "Your request here"

# 3) 生成草稿（外部模型）：由 Codex 写 prompts 后，用 `run` 调用 Claude/Gemini
#    （示例中 `prompt-file`/`var-file` 仅展示形态；实际由 Codex 决定内容与注入变量）
uv run --no-project python "$SkillDir\scripts\synapse.py" --project-dir "$Project" run --model claude --phase plan --slug "<slug>" --prompt-file ".synapse/prompts/plan-claude.template.md" --plan-path "<plan_path>"
uv run --no-project python "$SkillDir\scripts\synapse.py" --project-dir "$Project" run --model gemini --phase plan --slug "<slug>" --prompt-file ".synapse/prompts/plan-gemini.template.md" --plan-path "<plan_path>"

# 4) 由 Codex（主控）把草稿重写成最终代码后，跑验证与审计
uv run --no-project python "$SkillDir\scripts\synapse.py" --project-dir "$Project" verify
uv run --no-project python "$SkillDir\scripts\synapse.py" --project-dir "$Project" pack --phase review --slug "<slug>" --query "git diff review"
uv run --no-project python "$SkillDir\scripts\synapse.py" --project-dir "$Project" run --model claude --phase review --slug "<slug>" --prompt-file ".synapse/prompts/review-claude.template.md" --plan-path "<plan_path>"
uv run --no-project python "$SkillDir\scripts\synapse.py" --project-dir "$Project" run --model gemini --phase review --slug "<slug>" --prompt-file ".synapse/prompts/review-gemini.template.md" --plan-path "<plan_path>"

# 5) 打开本地只读 Web Viewer（浏览 `.synapse/**`）
uv run --no-project python "$SkillDir\scripts\synapse.py" --project-dir "$Project" ui
```

---

## “diff 当草稿”的落地方式（你关心的点）

Synapse 的 `run` 产物可以是 **draft diff**（例如 `--phase execute`），建议的落地顺序是：

1) Codex 阅读 plan + 两份 draft diff（frontend/backed）+ 审计（如有）
2) Codex 以项目真实代码为准，**重写**成生产级实现（而不是机械套用 diff）
3) Codex 跑 `synapse verify`（自动探测）并修到绿
4) Codex 通过 `synapse run --phase review ...` 获取审计，根据审计再修、再 verify

这么做的好处：

- draft diff 负责“探索/铺路”，Codex 负责“最终质量”
- 避免外部模型 patch 直接落地导致的风格不一致、测试缺失、边界问题

---

## Verify 自动探测策略（当前实现）

`synapse verify` 会按项目根目录的标志文件探测可运行步骤，并把完整输出写入 `.synapse/logs/**`。

当前支持：

- Node：检测 `package.json`，优先使用锁文件选择 `pnpm/yarn/npm`，再按是否存在脚本决定跑 `lint/typecheck/test`
- Python（uv only）：检测 `pyproject.toml` 或 `requirements.txt`  
  - `pyproject.toml`：`uv sync` → `uv run python -m pytest`（若看起来像 pytest 项目）或 `unittest discover`
  - `requirements.txt`：`uv venv` + `uv pip install -r requirements.txt` → 运行测试
- Rust：`Cargo.toml` → `cargo test`
- Go：`go.mod` → `go test ./...`
- .NET：存在 `*.sln/*.csproj/*.fsproj` → `dotnet test`

参数：

- `--dry-run`：只打印计划命令
- `--no-install`：跳过安装/同步依赖步骤
- `--keep-going`：失败也继续跑后续步骤

注意：

- `verify` 允许产生项目级副产物（lockfile、`.venv/`、`node_modules/`、build 输出等）
- 探测不到入口时不会崩溃，会记录为“nothing to run”

---

## Session / Resume

- plan 文件 meta（JSON）里有 `sessions` 字段（如 `claude`、`gemini` 的 `session_id`）
- `synapse run` 会捕获 `session_id`（写入 `.synapse/state.json`），并可在提供 `--plan-path` 时回写到 plan meta `sessions.<model>`
- CLI 支持：
  - `--resume-gemini <SESSION_ID>`
  - `--resume-claude <SESSION_ID>`
  - `--resume <SESSION_ID>`（兼容别名：等价于 `--resume-gemini`）

---

## 维护与扩展（给脚本维护者）

关键入口：

- `.codex/skills/synapse/scripts/synapse.py`：CLI 子命令定义
- `.codex/skills/synapse/scripts/_synapse/cmd_init.py`：init
- `.codex/skills/synapse/scripts/_synapse/cmd_pack.py`：pack（context pack）
- `.codex/skills/synapse/scripts/_synapse/cmd_plan.py`：plan（plan stub + Gate）
- `.codex/skills/synapse/scripts/_synapse/cmd_run.py`：run（外部模型运行器：prompt 由 Codex 提供）
- `.codex/skills/synapse/scripts/_synapse/cmd_ui.py`：ui（本地 web viewer）
- `.codex/skills/synapse/scripts/_synapse/cmd_verify.py`：verify 自动探测与执行
- `.codex/skills/synapse/scripts/_synapse/context_pack.py`：context pack（git/rg/snippets）
- `.codex/skills/synapse/scripts/_synapse/llm.py`：外部模型调用（stream-json 捕获 session）

建议的扩展方式：

- 新增生态探测：优先只加“明确且低风险”的命令（比如官方 test 命令），避免盲目猜测
- 为 verify 增加 “按文件变更范围缩小测试集” 的策略：先跑最窄，再跑全量
