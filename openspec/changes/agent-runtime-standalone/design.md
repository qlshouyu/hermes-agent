## Context

动机见 `proposal.md`，行为契约见 `specs/agent-runtime/standalone-runtime` 与 `specs/agent-runtime/standalone-packaging`。本变更依赖 `agent-runtime-hosted-ports` 的北向接口、交互挂起请求与 SymbolBinder。

### explore 阶段实测（基线 `fc71fb63e5`，Python 3.11，脚本位于会话 scratchpad `spike/`）

| 项 | 结果 |
|---|---|
| 隔离方式 | 复制 ③④ 闭包 608 个文件，未改一字节；`sys.path` 去掉仓库路径；从真实仓库加载的模块数为 0 |
| 替身 | 36 个文件，其中 9 个是上游原文件照搬（`hermes_cli` 的 middleware、lifecycle、_subprocess_compat、route_identity、timefmt、sizefmt、relay_plugin_cutover，以及 `gateway/session_context`、`acp_adapter/edit_approval`，均无外层依赖）；手写部分约 90 行 |
| 仍为自动桩的外层模块 | 16 个：`cron.jobs`、`gateway.status`、`plugins.browser/web/video_gen.*`、`hermes_cli.goals`、`hermes_cli.mem_trim` 等。导入阶段被触及，测试路径未调用 |
| 端到端 | 纯对话、`read_file`、`terminal`、`memory` 均完成；记忆文件写在隔离的 HERMES_HOME 内 |
| 静默失效 | 自动桩让工具返回空结果，同时 `completed=True`（`_dispatch_pre_tool_call_hooks`、`maybe_require_edit_approval`）；`is_actual_route` 替身语义写错导致路由失败 |
| 静态分析遗漏的依赖 | `acp_adapter.edit_approval`（`model_tools.py:774`、`:923`）；`gateway.hosted_room_execution_policy`（`tools/approval_context.py:231`） |
| 导入期副作用 | `run_agent.py:93-94` 在导入时读取 HERMES_HOME 下的 `.env`；`model_tools.py:147` 在导入时加载全部注册工具模块；导入期共加载 439 个模块，其中 76 个属于外层 |
| 端点探测 | 首个 chat 请求之前，先依次请求 `/api/v1/models`、`/api/tags`、`/v1/props`、`/props`、`/version`、`/v1/models`、`/models`、`/v1/models/<m>`、`/api/show` |
| 状态库 | 未传 `session_db` 时，状态目录中仍会出现 `state.db` |
| 审批 | 上游原版在无审批上下文时执行了 `rm -rf`；设置 `HERMES_EXEC_ASK=1` 但未注册 notify 时阻塞超过 400 秒，目录未被删除 |

## Goals / Non-Goals

**Goals:**
- 以最低维护成本得到满足 `standalone-runtime` 契约的产物。
- 保留一条经过验证、可以产出「不含外层代码」产物的后备路线，并从机制上杜绝替身的静默失效。

**Non-Goals:**
- 同进程多租户隔离（环境变量、HERMES_HOME、进程级全局状态都是进程级）。
- 支持 OAuth 类 provider（Nous、Codex、Copilot 等）。
- 修改上游以消除导入期副作用；如有需要，另行向上游提 PR（路线 D）。

## Decisions

### D1 默认路线 C：整包依赖 + 配置隔离

| 路线 | 上游零修改 | 产物不含外层代码 | 替身维护 | 静默错误风险 | 结论 |
|---|---|---|---|---|---|
| A 构建期抽取 + 替身 | ✅ | ✅ | 36 个起，随上游漂移 | 高 | 后备 |
| B fork 内源码改造 | ❌ | ✅ | 无 | 低 | 放弃，与上游持续冲突 |
| **C 整包依赖 + 配置隔离** | ✅ | ❌ | 无 | 低 | **默认** |
| D 向上游提交缝隙 PR | ✅ | 视采纳情况 | 递减 | 低 | 长期补充 |

- **理由**：
  - 目前没有明确消费方，没有「产物不得包含外层代码」的硬约束；
  - 路线 C 不引入任何替身，上游所有代码路径保持原语义；
  - 上游 `pyproject.toml` 已声明全部 packages，以及 sealed wheel 所需的 package-data。
- **切换到 A 的条件**：出现明确要求「产物不含 `hermes_cli`、`gateway` 等外层代码」（例如体积、合规或攻击面审查）。切换只影响 `standalone-packaging` 中抽取路线的相关要求，不影响 `standalone-runtime` 契约。

### D2 隔离实现（路线 C）
1. `bootstrap(mode="standalone", hermes_home=...)` 在导入任何上游模块之前设置 `HERMES_HOME`。原因是 `run_agent.py:93` 在导入时就读取 `.env`。若上游模块已被导入，抛出初始化顺序错误。
2. 在实例目录中生成 `config.yaml`，内容由 `RuntimeSpec` 与宿主的 ConfigPort 合成。`.env` 只由凭证接口写入，或不生成。
3. 确认产物安装目录（`run_agent.py` 同级）不存在 `.env`。上游会从 `Path(__file__).parent / ".env"` 读取，打包时必须排除该文件。
4. 生成的配置中 `plugins.enabled` 为空，关闭 entry-point 和用户插件。内置的 model-providers 依然可用，provider 档案依赖它。
5. 南向接口在路线 C 下以「写配置 + 绑定 ContextVar」实现。宿主需要以编程方式覆盖的，复用 hosted-ports 的 SymbolBinder。

### D3 会话存储与全局状态库
- **决定**：未提供会话存储时，开会话把 `session_search`、`react_to_message` 等会打开状态库的工具加入禁用列表，同时审计 `process_registry_results`、`async_delegation`、`bot_live_delivery` 中直接打开状态库的路径，按工具集门控。
- **待验证**：`state.db` 在构造阶段即被创建（spike 观测），需要定位创建方。只要不写入对话消息即满足规格；若仍有写入，再按调用方加门控。

### D4 端点探测
- **决定**：宿主提供 `context_length` 时，写入生成配置（`model.context_length`）。验证它能否抑制 spike 观测到的全部探测请求；若不能，按探测来源（`agent/model_metadata` 等）加配置开关。上游没有开关的探测，记为风险，进入路线 D 候选清单。

### D5 审批
- **决定**：直接沿用 hosted-ports D5 的审批上下文与挂起请求实现。Standalone 不另做分支。

### D6 路线 A（后备）的设计要点
- **分层**：
  - T0：原样复制闭包；
  - T1：外层随行，即无外层依赖的上游文件原样随行（见 Context 表）；
  - T2：语义替身，转发到南向接口；
  - T3：仅需可导入的模块，访问任何符号即抛出能力不可用错误。
- **替身来源**：由绑定清单生成骨架，语义函数手写。每个手写函数配一组契约输入，与上游原函数比对。
- **禁止自动占位**：spike 使用的自动桩只能用于探测清单，不得进入产物。
- **闭包锁**：记录 sha256，同步后发生漂移时构建失败。
- **清单校准**：以运行期导入审计为准，静态扫描作为补充。

### D7 测试资产
- **决定**：把 spike 的隔离运行器、路径感知的假模型端点、访问记录器迁入 `agent_runtime/tests/standalone/`。
- 用例覆盖：纯对话、文件、终端、记忆、危险命令（无交互实现 / 批准 / 超时）、端点探测计数、写入范围审计。

## Risks / Trade-offs

- **[R1] 路线 C 的可打包性未经验证**，上游声明「不发布受支持的 wheel」。
  → 首个任务就是在干净环境构建并安装 wheel 跑冒烟测试。失败时评估改为「带锁文件的 venv 目录分发」，或提前启用路线 A。
- **[R2] 产物体积与导入成本**：整包包含 gateway、tui_gateway 等约 34.7 万行代码（不加载）；导入期加载 439 个模块。
  → 记录冷启动耗时基准；超出预算时作为切换路线 A 的依据。
- **[R3] 上游在导入期新增读取用户目录的副作用**。
  → Standalone 冒烟用例在测试中把 `~/.hermes` 替换为只读哨兵目录，一旦发生访问即失败。
- **[R4] 状态库工具门控遗漏**。
  → 规格要求「未提供会话存储时不写会话数据库」，用多轮对话后检查数据库作为兜底测试。
- **[R5] 端点探测无法完全关闭**。
  → 规格限定在「预置元数据时」；无法关闭的探测列入构建报告，并提交路线 D 候选。
- **[R6] 路线 A 替身漂移导致静默失效**（spike 已复现）。
  → 显式失败、契约测试、闭包锁、运行期导入审计四项同时启用，缺一不可。
- **[R7] 进程级状态**：`HERMES_HOME`、`os.environ`、`_last_resolved_tool_names`。
  → 规格限定一个进程一个状态目录；文档要求多租户按进程部署。

## Migration Plan

1. 等待 `agent-runtime-hosted-ports` 完成 P1（北向接口、交互挂起请求）。
2. 验证 R1：构建 wheel，在干净环境安装并跑冒烟测试。
3. 实现 D2–D5，并迁入 D7 测试资产。
4. 在兼容层 revert 之后的新基线上跑完整 Standalone 端到端测试。
5. 仅在满足 D1 的切换条件时，实施 D6。

**回滚**：Standalone 是新增产物，不影响 Hosted 模式和上游。停止发布即可。

## Open Questions

- 内部制品仓库与发布流水线归属。不影响契约与任务拆分。
