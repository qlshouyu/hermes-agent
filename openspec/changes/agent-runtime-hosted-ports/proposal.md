## Why

自建宿主（外部前端 / 服务）目前只能直接构造上游 `run_agent.AIAgent`：80 个构造参数、21 个回调、宿主侧 110 处私有属性访问，且上游 `agent/` 年提交 4,692 次，任何源码级改造都会持续冲突。需要一层**零修改上游**的稳定接口，把宿主与上游内部实现隔开，并让上游升级只影响本层。

探索阶段在基线 `fc71fb63e5` 上实测发现两个必须在首个交付里解决的问题：

- 以库方式使用时，若不存在 CLI / gateway / ask 审批上下文，危险命令**直接执行、不经审批**（`tools/approval.py:1047-1054`，已实测 `rm -rf` 被执行）。
- 上游宿主各自处理历史、压缩与会话轮换，没有统一契约；自建 Web 宿主还需要**断线重连后恢复挂起的审批 / 澄清请求**。

依据：`contract/agent-runtime-extraction-plan.md`、`contract/agent-runtime-integration-guide.md`，以及本次 explore 的核实结论。

## What Changes

- 新增自有顶层目录 `agent_runtime/`（独立发行包 `hermes_agent_runtime`），**不修改任何上游文件**，自有提交只落在 `agent_runtime/`、`contract/`、`openspec/`。
- 新增北向 Port：`AgentRuntimePort`、`AgentSessionPort`、`SessionMaintenancePort`、`EventSinkPort`，以及替代同步 `InteractionPort` 的 **`InteractionNotifier` + `InteractionControl`（挂起请求模型）**。
- **历史以宿主为准**：`RunRequest.history` 必填；每轮以返回的 `messages` 整体替换；运行时判定 `history_rewritten`，并透出会话 ID 变化。
- **审批面强制建立**：每个会话在执行轮次前绑定审批上下文并注册通知；未提供交互实现时审批一律拒绝，而非上游库模式的默认放行。
- 三级装饰器：L1 会话装饰器；L2 执行中间件（`hermes.middleware.v1` 插件）；**L3 `SymbolBinder` 保留**，用于 Hosted 模式下以自定义南向 Port 覆盖上游外层函数。
- 南向 Port 的 Hosted 适配器（委托上游原函数）。
- 契约守卫 G1–G6 与同步流程；**基线冻结在上游兼容层（PLUGIN-COMPAT）revert 合入之后**。
- 对集成指南中与代码不符的描述做修正（审批回调已是线程局部、压缩仅在有 `session_db` 时换 ID、会话自动维护历史改为宿主持有等）。

## Capabilities

### New Capabilities

- `agent-runtime/session-api`: 北向会话接口——开会话、执行轮次、中断 / 插话、状态查询、关闭；宿主持有历史的契约与 `TurnResult` 映射；同会话串行。
- `agent-runtime/interaction`: 人机交互的挂起请求模型——通知、列出挂起、按 ID 解决、确认、取消；断线不取消；审批面强制建立。
- `agent-runtime/extension-layers`: 三级装饰器——L1 会话装饰器链、L2 执行中间件插件（含请求改写守卫）、L3 `SymbolBinder` 依赖转发与南向 Port 覆盖。
- `agent-runtime/upstream-sync`: 零修改上游的边界约束、契约守卫 G1–G6、基线冻结与同步流程。

### Modified Capabilities

（无：`openspec/specs/` 目前为空）

## Impact

- **新增代码**：`agent_runtime/`（`src/hermes_agent_runtime/{ports,domain,application,decorators,bindings,adapters/hosted}`、`guard/`、`tests/`）。
- **上游代码**：0 修改；运行期依赖 `run_agent`、`agent.*`、`tools.approval`、`tools.clarify_gateway`、`hermes_cli.plugins` / `middleware` 的现有公开或约定接口。
- **文档**：`contract/agent-runtime-integration-guide.md`、`contract/agent-runtime-ports-decorators.html` 需按本变更回写；`contract/b-line-extraction-options.html` 追加 ADR「方案 2′」。
- **环境**：Python 3.11–3.13（本机已有 `/opt/homebrew/bin/python3.11` 与 `uv`）。
- **时间依赖**：上游兼容层计划 2026-09-14 移除，P0 基线冻结需等待该 revert 合入 `main`。
- **下游变更**：`agent-runtime-standalone` 复用本变更的 Port 与适配器接口。
