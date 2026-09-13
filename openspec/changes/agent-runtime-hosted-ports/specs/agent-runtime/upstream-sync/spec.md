## Purpose

保证 AgentRuntime 在持续跟随上游主线的同时不修改任何上游文件，并在同步上游时把接口漂移提前暴露为可操作的守卫报告，而不是运行时故障。

## ADDED Requirements

### Requirement: 上游文件零修改
自有分支相对 `main` 的差异 MUST 只包含新增文件，且新增文件 MUST 位于 `agent_runtime/`、`contract/`、`openspec/` 之下。

#### Scenario: 差异检查
- **WHEN** 对自有分支执行 `git diff --name-status main...<自有分支>`
- **THEN** 每一行都是新增，且路径以允许的目录开头

#### Scenario: 误改上游文件
- **WHEN** 某次提交修改了上游已有文件
- **THEN** 边界检查失败，并列出被修改的上游文件

### Requirement: main 保持上游纯镜像
`main` MUST 与上游主线保持一致，不包含任何自有提交。

#### Scenario: 镜像检查
- **WHEN** 执行 `git rev-list --left-right --count origin/main...main`
- **THEN** 输出为 `0 0`

### Requirement: 基线在兼容层移除后冻结
闭包锁、绑定清单与构造签名快照 MUST 只在上游闭包内不存在临时兼容层标记（PLUGIN-COMPAT 块）时生成。存在标记时，基线冻结 MUST 拒绝执行。

#### Scenario: 兼容层仍存在
- **WHEN** 上游闭包内仍有文件包含 PLUGIN-COMPAT 块，维护者执行基线冻结
- **THEN** 冻结失败，并列出仍包含该标记的文件数量与示例路径

#### Scenario: 兼容层已移除
- **WHEN** 上游兼容层 revert 已合入 `main`，维护者执行基线冻结
- **THEN** 生成闭包锁、绑定清单与签名快照，并记录基线提交号

### Requirement: 契约守卫覆盖六类漂移
同步上游后，契约守卫 SHALL 检查六类漂移，每类失败 MUST 给出指明具体漂移项的可操作报告：
- G1：上游 Agent 构造参数与公开方法签名，含全部 mixin 的继承链；
- G2：绑定清单中的符号是否存在且可调用；
- G3：闭包内新增的模块顶层外向导入；
- G4：中间件与钩子契约常量；
- G5：闭包文件增删与内容变化；
- G6：已公告的定时移除项。

#### Scenario: 上游新增构造参数
- **WHEN** 同步后上游 Agent 构造签名新增一个参数
- **THEN** G1 失败，报告中给出新增参数名，并提示先经透传使用、再并入规格值对象

#### Scenario: 新增顶层外向导入
- **WHEN** 同步后闭包内某文件在模块顶层新增了对外层包的导入
- **THEN** G3 失败，报告中给出文件、行号与被导入的符号

#### Scenario: mixin 方法签名变化
- **WHEN** 同步后某个 mixin 提供的公开方法签名发生变化
- **THEN** G1 失败，报告中给出方法名与签名差异

### Requirement: 静态扫描需经运行期校准
守卫 SHALL 包含一次运行期导入审计：在真实运行一轮会话时记录实际导入的外层模块，并与静态扫描结果比对。差异 MUST 在报告中列出。

#### Scenario: 动态导入未被静态发现
- **WHEN** 运行期审计记录到一个静态扫描未发现的外层模块导入
- **THEN** 守卫报告列出该模块及其触发位置

### Requirement: 运行时内部导入边界
运行时内部只有 Hosted 适配器层与依赖转发层 MAY 导入上游外层包（`hermes_cli`、`gateway`、`cron`、`tui_gateway`、`plugins`、`acp_adapter`）。其他层导入这些包时 MUST 使边界检查失败。

#### Scenario: 领域层误导入上游
- **WHEN** 运行时领域层或接口层的某个模块导入了 `hermes_cli`
- **THEN** 边界检查失败，并指明违规模块与导入语句
