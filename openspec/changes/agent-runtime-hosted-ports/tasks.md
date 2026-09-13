## 1. P0 · 环境、边界与守卫工具

- [ ] 1.1 创建分支 `local/agent-runtime`；用 `uv` + Python 3.11 建开发环境，确认上游 `tests/agent` 可运行
- [ ] 1.2 新建 `agent_runtime/` 骨架：`pyproject.toml`（发行名 `hermes-agent-runtime`，不改上游 pyproject）、`src/hermes_agent_runtime/{ports,domain,application,decorators,bindings,adapters/hosted}`、`guard/`、`tests/`
- [ ] 1.3 配置 import-linter 边界：只有 `adapters.hosted` 与 `bindings` 可以导入上游外层包；增加「导入公开包不加载 `run_agent` / `agent` / `tools`」测试
- [ ] 1.4 实现差异边界检查：`git diff --name-status main...local/agent-runtime` 只允许 `A`，且路径限定在 `agent_runtime/`、`contract/`、`openspec/`
- [ ] 1.5 实现闭包扫描：按模块顶层 / 函数体内 / TYPE_CHECKING 分类外向引用，排除 PLUGIN-COMPAT 块，输出绑定清单候选
- [ ] 1.6 实现运行期导入审计（`sys.addaudithook`），跑一轮假模型会话，与静态结果比对并输出差异
- [ ] 1.7 实现守卫 G1（构造签名 + 全部 mixin 的公开方法签名快照）
- [ ] 1.8 实现守卫 G2（绑定符号存在且可调用）与 G3（新增顶层外向导入，以及绑定安装导入图检查）
- [ ] 1.9 实现守卫 G4（`MIDDLEWARE_SCHEMA_VERSION`、`VALID_HOOKS`、entry point 分组名）、G5（闭包锁比对）、G6（定时移除项）
- [ ] 1.10 实现基线冻结命令：闭包内存在 PLUGIN-COMPAT 标记时拒绝执行；否则生成闭包锁、绑定清单与签名快照，并记录基线提交号
- [ ] 1.11 等上游兼容层 revert 合入 `main` 后执行基线冻结，守卫全绿
- [ ] 1.12 在 `contract/b-line-extraction-options.html` 追加 ADR「方案 2′」，说明它与方案 1（`hermes serve`）的分工

## 2. P1 · 领域模型与会话接口

- [ ] 2.1 定义值对象：`RuntimeSpec`（ModelRoute / ToolPolicy / SessionBinding / PromptOptions / output / passthrough）、`RunRequest`（`history` 必填）、`TurnResult`（含 `history_rewritten`、会话 ID 变化、`compression_deferred` / `compression_exhausted`、`interrupted`、`pending_steer`、usage）、`RuntimeEvent`、错误类型
- [ ] 2.2 实现 `SpecMapper`：规格摊平为 `AIAgent` 参数；透传参数按 `inspect.signature` 校验，未知键报错；补上契约测试「输出键 ⊆ 构造参数集」
- [ ] 2.3 实现 `DefaultAgentSession`：一个会话持有一个 `AIAgent`；`run_turn` 原样传入宿主历史；以副本方式调用，确保不修改宿主列表
- [ ] 2.4 实现结果映射与历史改写判定（前缀比较 + 会话 ID 变化 + `_last_compaction_in_place`），覆盖正常、压缩、插话三种用例
- [ ] 2.5 实现轮次串行（排队 / 拒绝两种策略）、跨线程 `interrupt` / `steer` / `redirect` / `activity`，以及可重复调用的 `close`
- [ ] 2.6 实现 `EventBridge` 的通知类回调到 `RuntimeEvent` 的映射；接收方异常只记录不中断；各类型填充标准化字段
- [ ] 2.7 实现 `DefaultAgentRuntime.open_session` / `capabilities`；未提供会话存储时，默认禁用 `session_search`、`react_to_message` 等会打开全局状态库的工具
- [ ] 2.8 实现 `SessionMaintenancePort`（按附录 D 访问次数 ≥ 2 的项），受 `allow_maintenance` 控制

## 3. P1 · 交互挂起请求与审批面

- [ ] 3.1 【先行验证 R1】找到仅靠 ContextVar 让 `_presence()` 返回 `is_gateway=True` 的绑定方式，并验证系统提示字节不变、不被判为消息渠道；输出结论并回写 design D5
- [ ] 3.2 定义 `InteractionNotifier`、`InteractionControl`、`PendingInteraction`、`ResolveOutcome`（resolved / expired / not_found）
- [ ] 3.3 审批：轮次线程内绑定 session key 与审批上下文，按会话注册 notify；`pending` / `resolve` / `ack` 映射到 `tools.approval` 的队列接口
- [ ] 3.4 clarify：接入 `tools.clarify_gateway`，维护 session → clarify_id 索引，支持列出挂起与超时反馈
- [ ] 3.5 实现运行时挂起注册表，覆盖 sudo、secret、read_terminal / preview / window_below、tour、setup_mcp，支持载荷回放与按类型超时；secret 回调进程级注册一次，再按 ContextVar 路由到会话
- [ ] 3.6 文件编辑审批：在轮次上下文设置 ACP edit approval 请求器，转成挂起请求
- [ ] 3.7 实现断线不取消、先写者生效、跨会话隔离；中断或关闭时 `cancel_all`（审批按拒绝处理）
- [ ] 3.8 敏感输入不外泄：检查事件、日志、结果消息中不出现 sudo 密码和密钥
- [ ] 3.9 安全测试：未提供通知方时危险命令不执行；批准后执行；超时后不执行；中断时取消

## 4. P1 · 验证与示例

- [ ] 4.1 迁入路径感知的假模型端点（兼容 OpenAI 协议，支持流式和工具调用）作为测试夹具
- [ ] 4.2 差分测试：同一脚本化对话分别直接调用 `AIAgent` 和经过 Port，断言角色序列、工具调用序列、系统提示字节一致
- [ ] 4.3 示例宿主：命令行多轮对话，以及 FastAPI + WebSocket（含断线重连后 `pending` / `resolve` 审批）

## 5. P2 · 装饰器与扩展层

- [ ] 5.1 L1：`SessionDecorator` 基类，以及 ErrorMapping、ConcurrencyGuard、Tracing、Metrics、CacheInvariant、CapabilityGate 装饰器；可配置叠加顺序
- [ ] 5.2 L2：中间件插件（entry point），`register(ctx)` 注册四类中间件与 `post_tool_call` 钩子；初始化时校验契约版本
- [ ] 5.3 L2：`guarded_request_middleware` 丢弃对 messages / input / tools / system 的改写并告警；测试中间件抛异常时审批仍然生效
- [ ] 5.4 L3：`SymbolBinder` 与 `original_of` 注册表；Hosted 适配器调用原实现，不产生递归
- [ ] 5.5 L3：`bootstrap(ports=...)` 覆盖流程：只安装被覆盖的绑定；初始化结果列出覆盖清单；提供 `uninstall`
- [ ] 5.6 L3：顶层读取方已被导入时报初始化顺序错误；严格模式下绑定漂移报 `BindingDrift`，可选绑定跳过并告警
- [ ] 5.7 L3：回归验证模式——安装恒等绑定后运行上游 `tests/agent`、`tests/tools`，结果与未安装时一致
- [ ] 5.8 基准测试：覆盖配置读取后，热路径开销低于 5%
- [ ] 5.9 可选启动器 `hermes-rt`：安装绑定后进入上游 main；`DecoratedAIAgent` 子类带重入保护，避免派生子 Agent 被重复装饰

## 6. 文档回写与收尾

- [ ] 6.1 回写 `contract/agent-runtime-integration-guide.md`：历史由宿主持有、交互挂起请求、审批面、压缩与会话 ID 语义、SymbolBinder 的作用域
- [ ] 6.2 回写 `contract/agent-runtime-ports-decorators.html` 与 `agent-runtime-extraction-plan.md`，纳入 explore 阶段修正的数据与新增依赖
- [ ] 6.3 编写同步处置手册，逐条对应守卫 G1–G6 失败时的处理步骤
