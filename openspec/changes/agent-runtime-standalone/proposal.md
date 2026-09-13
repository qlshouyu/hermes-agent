## Why

需要一种不依赖本机 Hermes 安装（不读写 `~/.hermes`、不加载第三方插件、配置由宿主下发）的 AgentRuntime 形态，用于嵌入业务服务或独立部署。目前没有明确消费方，但探索阶段已在隔离环境中验证可行：仅复制 ③④ 闭包 608 个文件（未改一字节）+ 36 个替身模块，即完成多轮对话以及 `read_file`、`terminal`、`memory` 工具的真实执行，且从真实仓库加载的模块数为 0。

同一次验证也暴露了风险：替身语义错误不会报错，而是**静默失效**（工具返回空结果且 `completed=True`）；若干外层依赖（`acp_adapter.edit_approval`、`gateway.hosted_room_execution_policy`）在静态分析与原方案 Port 清单中均缺失。因此需要先把 Standalone 的行为契约与打包路线定下来，再决定投入。

## What Changes

- 定义 Standalone 运行时的行为契约：状态目录隔离、不触碰全局 `~/.hermes`、配置由宿主下发、第三方插件默认不加载、能力缺席时在开会话前禁用对应工具集。
- 采用**路线 C「整包依赖 + 配置隔离」**作为默认打包形态：wheel 携带完整上游包与 `hermes_agent_runtime`，通过独立 `HERMES_HOME` 与运行时生成的配置实现隔离，南向 Port 以「写配置 / 绑定上下文」实现，不引入替身模块。
- 保留**路线 A「构建期抽取 + 替身模块」**作为后备：仅当确认「产物不得包含 `hermes_cli` / `gateway` 等外层代码」时启用；启用时替身必须对未知符号显式失败，并对照上游原函数做契约测试。
- 拦截或禁用会绕过 `session_db=None` 直接打开全局状态库的工具（`session_search`、`react_to_message` 等）。
- 支持离线 / 内网模型端点：可关闭或预置上下文长度探测，避免首轮前对端点的多次探测请求。
- 把探索阶段的验证脚本沉淀为可重复运行的 Standalone 冒烟与 E2E 套件，在上游兼容层 revert 后的新基线上重跑。

## Capabilities

### New Capabilities

- `agent-runtime/standalone-runtime`: Standalone 模式的行为契约——状态隔离、配置下发、插件策略、能力门控、全局状态库访问拦截、端点探测控制、审批面要求。
- `agent-runtime/standalone-packaging`: 打包与分发——默认路线 C 的 wheel 组成与安装验收；路线 A 启用条件及其替身契约（未知符号显式失败、逐函数契约测试、闭包锁定）。

### Modified Capabilities

（无：`openspec/specs/` 目前为空）

## Impact

- **依赖**：本变更依赖 `agent-runtime-hosted-ports` 提供的北向 Port、`InteractionControl` 与南向 Port 接口。
- **新增代码**：`agent_runtime/src/hermes_agent_runtime/adapters/standalone/`、`agent_runtime/build/`（打包；路线 A 时含闭包扫描与替身生成）、Standalone 测试套件。
- **上游代码**：0 修改。
- **打包风险**：上游文档声明「不发布受支持的 wheel」，但 `pyproject.toml` 已声明全部 packages 与 sealed-wheel 所需的 package-data；路线 C 的可打包性需要在本变更中首先验证。
- **运维**：多租户需按进程隔离（`os.environ`、进程级全局状态与 `HERMES_HOME` 均为进程级）。
- **探索产物**：验证脚本位于会话 scratchpad 的 `spike/` 目录，需迁入 `agent_runtime/tests/standalone/` 后方可复用。
