# contract/

本目录存放**我们自己的**文档与契约基线。它与上游 `NousResearch/hermes-agent` 无关，
且该目录名在 `origin/main` 中**不存在**——因此上游永远不会与它产生同名碰撞。

采纳的架构是「方案 1 + 方案 3B」：把 `hermes serve` 当黑盒后端，前端在本仓库之外自建；
本目录是留在仓库内的那一层契约守卫。详见 `b-line-extraction-options.html`。

## 为什么不放在 docs/

`docs/` 是上游在积极维护的目录（23 个文件、239 次提交/年）。自有文件放进去不会立刻出问题，
但同名碰撞的概率长期不为零，而且会让「哪些文件是我们的」变得模糊。

## 保证能跟随主线的四条规则

1. **`main` 永远是 `origin/main` 的纯镜像，绝不提交** —— 不分叉，`git pull` 才能永远是快进。
2. **自有文件只放上游未占用的顶层目录** —— 即本目录。
3. **自有提交放独立分支（如 `local/contract`），用 `git rebase main` 跟随** —— 文件集不相交，rebase 永不冲突。
4. **只依赖 HTTP/WS 契约，绝不 import 上游内部路径** —— 上游明确声明
   *"Internal import paths are not a stable API"*（见 `COMPAT_MANIFEST.md`）。

### 日常跟随上游

```sh
git checkout main
git pull                 # 永远快进：main 无自有提交
git checkout local/contract
git rebase main          # 永不冲突：文件集不相交
```

### 验收检查

```sh
# 1. main 是否仍是上游纯镜像（期望 0　0）
git rev-list --left-right --count origin/main...main

# 2. 自有分支是否只新增、未修改上游文件（期望只有 A 开头的行）
git diff --name-status main...local/contract

# 3. 是否误 import 了上游内部路径（期望无输出）
#    只扫源文件里行首的 import 语句——否则会命中本文件里描述该检查的这几行。
#    zsh 下 --include 的通配符必须加引号。
grep -rnE "^[[:space:]]*(from|import)[[:space:]]+(hermes_cli|tui_gateway|agent|gateway|tools)\b" \
  --include='*.py' --include='*.ts' --include='*.tsx' --include='*.js' contract/
```

## 目录内容

| 文件 | 说明 |
|---|---|
| `b-line-extraction-options.html` | 架构决策：采纳方案 1 + 3B，方案 2 / 3A 的弃用留档 |
| `hermes-serve-integration.html` | 方案 1 落地方案：启动参数、鉴权矩阵、REST 与 JSON-RPC 契约、MVP 切片、分阶段计划 |
| `desktop-backend-api.html` | 桌面端 → `hermes serve` 接口手册 |
| `web-server-api.html` | `web_server` 接口手册 |
| `desktop-integration.html` | 桌面端接口对接 |
| `hermes-process-map.html` | 进程与模块依赖 |
| `diagrams/` | 端到端架构图的导出（SVG / PNG，四页） |

架构图源文件 `docs/hermes-architecture.drawio` 仍在 `docs/` 下（draw.io 占用中），
编辑器关闭后应一并迁入本目录。
