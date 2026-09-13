## Context

动机见 `proposal.md`，接口契约见 `specs/agent-runtime/*`。原始方案见 `contract/agent-runtime-extraction-plan.md` 与 `contract/agent-runtime-integration-guide.md`。explore 阶段在基线 `fc71fb63e5` 上核实，以下事实会影响设计：

| 事实 | 位置 | 对设计的影响 |
|---|---|---|
| `AIAgent.__init__` 有 80 个参数、21 个回调；本类只有 6 个公开方法，其余来自 14 个 mixin | `run_agent.py` | G1 快照必须覆盖整条继承链 |
| 危险命令审批仅在 CLI / gateway / ask 上下文中阻塞，否则直接放行 | `tools/approval.py:1047-1054` | 运行时必须主动建立审批面 |
| 终端审批回调已是线程局部；gateway 使用按 session_key 的队列，并支持列出、确认、按 ID 解决 | `tools/terminal_tool.py:84`、`tools/approval.py:118-205` | 审批直接复用队列，不另造回调分发 |
| clarify 有队列，但没有列表接口 | `tools/clarify_gateway.py` | 运行时补一个索引 |
| sudo、secret、read_*、tour、setup_mcp 只有同步回调；secret 回调是模块全局变量 | `tools/skills_tool.py:104` | 运行时自建挂起注册表 |
| ACP 文件编辑审批通过 ContextVar 请求器实现 | `acp_adapter/edit_approval.py:165` | 新增交互类型 |
| 每轮复制传入的 history 再追加；系统提示缓存在实例上 | `agent/turn_context.py:918-951` | 宿主持有历史，且一会话一个实例 |
| 仅在有 `session_db` 时压缩才会轮换 session_id；无 DB 时 `_last_compaction_in_place` 恒为 False | `agent/conversation_compression.py:2949-3012`、`:3123` | 历史改写需要运行时自行判定 |
| `session_search` 在 `session_db=None` 时会打开全局状态库并开始写入 | `run_agent.py:282-296` | 自建宿主默认禁用该工具 |
| 中间件链读取插件管理器的私有字典；entry-point 插件默认不启用 | `hermes_cli/middleware.py:161-165`、`hermes_cli/plugins.py:1305` | L2 走插件方式，需要显式启用 |
| 兼容层（147 个闭包文件）计划 2026-09-14 移除 | `COMPAT_MANIFEST.md` | 冻结基线须等 revert 合入 |
| 闭包对外引用（去除兼容块后）：416 个符号 / 972 处，其中模块顶层 82 个 / 134 处 | AST 重算 | 作为绑定清单的初始输入 |

## Goals / Non-Goals

**Goals:**
- Hosted 模式下交付北向接口、挂起请求交互、三级扩展层与契约守卫，且上游零修改。
- 自建宿主在不设置任何进程级环境变量的情况下获得安全的审批行为。
- 同步上游时，漂移在守卫阶段被发现。

**Non-Goals:**
- Standalone 打包与独立南向实现（见变更 `agent-runtime-standalone`）。
- 修复上游进程级全局状态，例如 `model_tools._last_resolved_tool_names`；本变更只做文档标注。
- 让同进程多租户隔离环境变量级配置。
- 替代 `hermes serve`：前后端分离、只走 HTTP 的场景仍按 b-line 决策文档执行。

## Decisions

### D1 零修改上游 + 自有顶层目录
- **决定**：代码放在 `agent_runtime/`，包名 `hermes_agent_runtime`，分支 `local/agent-runtime`，通过 rebase 跟随 `main`。
- **备选**：源码迁移重构（每次同步大量冲突）；fork 内改造（违反「上游零修改」约束）。均放弃。

### D2 历史以宿主为准
- **决定**：`RunRequest.history` 必填，每轮原样传给上游的 `conversation_history`；运行时不保存历史。
- **理由**：
  - 这是上游宿主（gateway）的现行用法；
  - 断线重连、多实例部署时，历史的唯一真源在宿主；
  - 避免内存历史与会话 ID 轮换叠加导致错位。
- **备选**：运行时内存历史（进程重启即丢失）；SessionDB 为真源（强依赖状态库，Standalone 无法满足）。

### D3 一个会话对应一个 `AIAgent` 实例
- **决定**：`DefaultAgentSession` 持有唯一实例，轮次之间复用。
- **理由**：系统提示和工具数组的冻结状态保存在实例上；每轮新建实例会重建系统提示，时间戳行和记忆快照会变化，破坏提示缓存（`conversation_loop.py:753`）。

### D4 历史改写判定
- **决定**：满足下列任一条件即判定为历史已改写：
  - 返回的 `messages` 不再以传入的 history 为前缀（逐条比较 role、content、tool_calls、tool_call_id）；
  - `session_id` 发生变化；
  - 上游 `_last_compaction_in_place` 为真。
- **理由**：无 DB 时上游不给任何信号，前缀比较是唯一可靠的判定；另外两条用于在有 DB 时更早判定。
- **代价**：每轮做一次 O(n) 比较。与模型调用相比可以忽略。

### D5 交互：挂起请求模型，按类型复用上游机制
接口拆为两部分：
- `InteractionNotifier`：宿主实现，允许断线；
- `InteractionControl`：运行时实现，提供 `pending`、`resolve`、`ack`、`cancel_all`。

| 类型 | 实现 |
|---|---|
| 命令 / 代码 / 插件工具审批 | 复用 `tools.approval` gateway 队列：轮次线程内绑定 session key ContextVar，并按会话注册 notify。`resolve` 映射为 `resolve_gateway_approval(request_id=...)`，`pending` 映射为 `list_gateway_approvals` |
| clarify | 复用 `tools.clarify_gateway`，运行时维护 session → clarify_id 索引以支持列表 |
| sudo、secret、read_*、tour、setup_mcp | 运行时挂起注册表（参照 `tui_gateway/server.py:1262` 的 `_block`），补上载荷回放；secret 使用一次性注册的进程级回调，再按 ContextVar 中的会话路由 |
| 文件编辑审批 | 在轮次上下文中设置 ACP edit approval 请求器，转成挂起请求 |

- **审批上下文的建立方式**：优先通过 ContextVar 绑定会话平台，使 `_is_gateway_approval_context()` 为真；**不**设置进程级 `HERMES_EXEC_ASK`，因为它会影响同进程所有会话。
  - 绑定所用的平台值必须满足两点：不属于无人值守平台列表；不被 `session_is_messaging_surface()` 判为消息渠道，以免改变平台提示词。
  - 候选值需要在 P1 验证，见风险 R1。
- **备选**：保持同步 `InteractionPort` 回调。无法支持断线重连（Q4 已明确要求），放弃。

### D6 保留 L3 SymbolBinder（Q2 已决定）
- **用途**：Hosted 模式下，允许宿主以自定义南向实现覆盖上游外层函数，例如从配置中心读取配置。
- **作用域**：进程级。覆盖同样作用于同进程内的上游宿主，以及外层模块内部经 globals 的相互调用。初始化结果必须列出覆盖清单。
- **原实现的获取**：Hosted 适配器通过注册表中保存的原函数调用上游，避免递归。
- **默认行为**：不提供自定义实现时不安装任何绑定，避免热路径开销。只有在开启回归验证模式时，才安装恒等绑定，用来证明行为等价。
- **导入顺序**：
  - 顶层绑定必须在读取方首次导入前安装；
  - 安装绑定本身需要先导入外层模块，而外层模块可能反向导入闭包（例：`hermes_cli/auth.py:36` 导入 `agent.credential_persistence`）；
  - G3 扩展一项检查：安装绑定时，其导入图不得提前加载任何「读取被覆盖符号」的顶层读取方。

### D7 L2 中间件以插件方式交付
- **决定**：通过 `hermes_agent.plugins` entry point 注册，Hosted 模式需要 `hermes plugins enable agent-runtime`。
- **契约校验**：初始化时校验 `MIDDLEWARE_SCHEMA_VERSION == "hermes.middleware.v1"`。
- **请求守卫**：用函数装饰器实现，丢弃对 messages、input、tools、system 的改写。

### D8 回调到事件的映射
- **决定**：14 个通知类回调映射为 `RuntimeEvent`。交互类回调不走同步回调，统一转成 D5 的挂起请求。
- `emit` 抛出的异常被记录并吞掉。

### D9 冻结基线时机
- **决定**：P0 先完成守卫与扫描工具，但冻结动作以「闭包内不存在 PLUGIN-COMPAT 标记」为前置条件。
- **理由**：兼容层移除会一次性删掉 56 处外向引用和 3,613 行代码；在移除前冻结，同步一次就要全部重做。

## Risks / Trade-offs

- **[R1] 审批上下文的绑定方式可能带来副作用**：绑定的平台值可能影响平台提示词或默认工具集。
  → P1 第一个任务就是验证候选绑定方式：系统提示字节不变，且 `_presence()` 返回 `is_gateway=True`。若找不到无副作用的方案，退而使用 ContextVar 形式的 `_hermes_interactive_ctx` 配合线程局部回调转挂起请求。
- **[R2] SymbolBinder 的进程级覆盖影响同进程上游宿主**。
  → 初始化结果列出覆盖清单；文档标注「自定义南向实现与上游宿主同进程运行时共享覆盖」；提供恢复操作。
- **[R3] 绑定依赖上游私有符号**：`hermes_cli.auth` 有 21 个私有符号在顶层被导入，上游可以随时改名。
  → G2 重点监控；严格模式在初始化时失败。
- **[R4] 配置读取是热路径**（上游注释：约 265µs/次）。
  → 未覆盖时不安装绑定；覆盖时转发函数不做额外分配，并在 P2 做基准测试。
- **[R5] `session_search`、`react_to_message` 等工具会打开全局状态库**。
  → 宿主未提供会话存储时，开会话默认把这些工具加入禁用列表，并在能力表中声明。
- **[R6] 同进程并发会话读到 `_last_resolved_tool_names` 的旧值**。
  → 维持上游现状；文档建议高并发场景按进程隔离。
- **[R7] 前缀比较误判历史改写**，例如上游对 content 做了规范化。
  → 比较前按上游持久化规则规范化；差分测试覆盖正常、压缩、插话三种情形。
- **[R8] 静态扫描漏掉动态导入**。
  → 守卫加入运行期导入审计校准。explore 阶段已实测发现静态分析遗漏了 `acp_adapter.edit_approval` 和 `gateway.hosted_room_execution_policy`。

## Migration Plan

1. **P0**：开发环境（Python 3.11 + uv）、闭包扫描、绑定清单生成、G1–G6、边界检查、ADR。等兼容层 revert 合入后冻结基线。
2. **P1**：北向接口、宿主持有历史、交互挂起请求（先解决 R1）、Hosted 适配器、示例宿主、差分测试。
3. **P2**：L1 装饰器、L2 中间件插件、L3 SymbolBinder 与覆盖、可选启动器、上游回归测试、基准测试。
4. **文档回写**：更新 `contract/` 下的集成指南与清单。

**回滚**：卸载 `hermes-agent-runtime` 并禁用插件即可恢复原状，上游无任何改动。

## Open Questions

- 发行名 `hermes-agent-runtime` 是否可用，是否发布到内部 PyPI。不影响接口与任务拆分。
- 追踪与指标后端的具体选型。接口已抽象为 `Tracer` / `MetricsSink`。
