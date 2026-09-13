"""生成 Hermes-Agent 业务逻辑架构图（带代码路径 + AgentRuntime 抽取边界）。

用法: python3 gen_biz.py <out.drawio> <repo_root>
每个功能块写成 "功能|路径"，路径相对卡片 base；多个路径用 " · " 分隔，支持 glob。
生成前会校验所有路径真实存在，任一缺失即退出。
"""
import glob
import html
import os
import re
import sys
from xml.sax.saxutils import escape

OUT, REPO = sys.argv[1], sys.argv[2]
FONT = "fontFamily=PingFang SC;"

PAL = {
    "grey":   ("#f5f5f5", "#666666"),
    "blue":   ("#dae8fc", "#6c8ebf"),
    "green":  ("#d5e8d4", "#82b366"),
    "yellow": ("#fff2cc", "#d6b656"),
    "purple": ("#e1d5e7", "#9673a6"),
    "orange": ("#ffe6cc", "#d79b00"),
    "red":    ("#f8cecc", "#b85450"),
}
TINT = {"grey": "#fafafa", "blue": "#f3f7fd", "green": "#f3f9f2", "yellow": "#fffbef",
        "purple": "#f8f4fa", "orange": "#fff8f0", "red": "#fdf3f3"}

# AgentRuntime 依赖闭包：命中这些模式的路径在 ③④ 以外的层会打 ◆ 标记
CLOSURE = [r"^run_agent\.py$", r"^model_tools\.py$", r"^toolsets\.py$", r"^toolset_distributions\.py$",
           r"^agent/", r"^tools/", r"^hermes_state", r"^hermes_constants\.py$", r"^hermes_logging\.py$",
           r"^hermes_time\.py$", r"^utils\.py$"]

cells, missing, too_long = [], [], []
_id = [0]


def nid(p):
    _id[0] += 1
    return f"{p}{_id[0]}"


def xa(s):
    return escape(s, {'"': "&quot;"}).replace("\n", "&#xa;")


def v(cid, value, style, x, y, w, h, parent="1"):
    cells.append(f'<mxCell id="{cid}" value="{xa(value)}" style="{style}" vertex="1" parent="{parent}">'
                 f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" as="geometry" /></mxCell>')


def e(value, src, tgt, extra=""):
    cells.append(
        f'<mxCell id="{nid("e")}" value="{xa(value)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;'
        f'jettySize=auto;html=1;{FONT}fontSize=12;fontColor=#444444;labelBackgroundColor=#ffffff;strokeWidth=1.5;'
        f'strokeColor=#888888;endArrow=block;endFill=1;{extra}" edge="1" parent="1" source="{src}" target="{tgt}">'
        f'<mxGeometry relative="1" as="geometry" /></mxCell>')


# ---------------- 尺寸 ----------------
X0, MAIN_W = 40, 3000
RIGHT_W = 500
RIGHT_X = X0 + MAIN_W + 30
LABEL_W = 50
PAD = 14
MOD_GAP = 14
TITLE_H = 30
BASE_H = 20
CHIP_H = 40
GAP_Y = 6
GAP_X = 8
CHIP_MIN_W = 195
LAYER_GAP = 64
CHAR_W = 5.4  # Menlo 9px 近似字宽


def cols_for(w, n):
    c = max(1, int((w - 20 + GAP_X) // (CHIP_MIN_W + GAP_X)))
    return min(c, 2, n)


def card_h(w, chips):
    c = cols_for(w, len(chips))
    return TITLE_H + BASE_H + 4 + -(-len(chips) // c) * (CHIP_H + GAP_Y) + 8


def resolve(base, path):
    """返回仓库相对路径列表，并校验存在。"""
    out = []
    for part in path.split(" · "):
        rel = os.path.normpath(os.path.join(base, part))
        if not glob.glob(os.path.join(REPO, rel)):
            missing.append(rel)
        out.append(rel)
    return out


def in_closure(rels):
    return any(re.match(p, r) for r in rels for p in CLOSURE)


def draw_card(parent, x, y, w, h, color, title, base, chips, mark_closure):
    fill, stroke = PAL[color]
    cid = nid("m")
    v(cid, title, f"swimlane;startSize={TITLE_H};html=1;{FONT}fontSize=13;fontStyle=1;fillColor={fill};"
                  f"strokeColor={stroke};swimlaneFillColor=#ffffff;rounded=1;arcSize=2;", x, y, w, h, parent)
    sub = f"📁 {base}" if base else "路径相对仓库根目录"
    v(nid("b"), sub, f"text;html=1;fontFamily=Menlo;fontSize=10;fontColor={'#555555' if base else '#aaaaaa'};"
                     f"align=center;verticalAlign=middle;fontStyle={1 if base else 0};", 6, TITLE_H + 1, w - 12, BASE_H, cid)
    c = cols_for(w, len(chips))
    cw = (w - 20 - (c - 1) * GAP_X) / c
    for i, raw in enumerate(chips):
        r, k = divmod(i, c)
        label, _, path = raw.partition("|")
        bold = label.startswith("*")
        label = label.lstrip("*")
        rels = resolve(base, path) if path else []
        mark = bool(mark_closure and rels and in_closure(rels))
        shown = (" · ".join(rels) if path.startswith("../") else path) if path else "外部系统"
        if len(shown) * CHAR_W + 14 > cw:
            too_long.append((shown, int(cw)))
        lab = html.escape(label)
        if bold:
            lab = f"<b>{lab}</b>"
        if mark:
            lab = f'<font color="#c0392b">◆</font> {lab}'
        pcolor = "#7a7a7a" if path else "#b0b0b0"
        val = f'{lab}<br><font face="Menlo" style="font-size:9px" color="{pcolor}">{html.escape(shown)}</font>'
        v(nid("c"), val, f"rounded=1;arcSize=14;whiteSpace=wrap;html=1;{FONT}fontSize=11;fillColor={fill};"
                         f"strokeColor={'#c0392b' if mark else stroke};strokeWidth={2 if mark else 1};fontColor=#333333;spacing=2;",
          10 + k * (cw + GAP_X), TITLE_H + BASE_H + 4 + r * (CHIP_H + GAP_Y), cw, CHIP_H, cid)
    return cid


def draw_layer(y, color, name, modules, mark_closure=True):
    inner = MAIN_W - LABEL_W - 2 * PAD
    tw = sum(m[0] for m in modules)
    avail = inner - (len(modules) - 1) * MOD_GAP
    widths = [avail * m[0] / tw for m in modules]
    ch = max(card_h(wd, m[3]) for wd, m in zip(widths, modules))
    h = ch + 2 * PAD
    fill, stroke = PAL[color]
    lid = nid("L")
    v(lid, name, f"swimlane;horizontal=0;startSize={LABEL_W};html=1;{FONT}fontSize=16;fontStyle=1;fillColor={fill};"
                 f"strokeColor={stroke};swimlaneFillColor={TINT[color]};", X0, y, MAIN_W, h)
    x = LABEL_W + PAD
    for wd, m in zip(widths, modules):
        draw_card(lid, x, PAD, wd, ch, color, m[1], m[2], m[3], mark_closure)
        x += wd + MOD_GAP
    return lid, h


# ================= 内容：(权重, 标题, base, ["功能|路径"]) =================
LAYERS = [
    ("grey", "① 接入渠道层", [
        (1, "终端", "", ["*经典 REPL 命令行|cli.py", "Ink 终端 UI|ui-tui/src/", "TUI 启动器|hermes_cli/main_tui_launch.py",
                       "CLI 总入口|hermes_cli/main.py"]),
        (1, "桌面 App", "apps/desktop/electron/", ["*Electron 主进程|main.ts", "本地派生后端|local-backend-lifecycle.ts",
                                                 "SSH 隧道远程后端|ssh-connection.ts", "远程连接注册表|connection-registry.ts"]),
        (1, "Web Dashboard", "", ["*浏览器 /chat 对话|web/src/pages/ChatPage.tsx", "管理控制台页面|web/src/pages/",
                                  "Dashboard 认证插件|plugins/dashboard_auth/"]),
        (1, "消息平台 22+", "", ["*适配器基类|gateway/platforms/base.py", "Telegram · Slack · 飞书 …|plugins/platforms/",
                              "微信 · QQ · 元宝 · Signal|gateway/platforms/", "平台注册表|gateway/platform_registry.py"]),
        (1, "编辑器 (ACP)", "acp_adapter/", ["*进程入口|entry.py", "ACP 服务端|server.py", "Zed · VS Code · JetBrains|"]),
        (1, "MCP 客户端", "", ["*stdio MCP 服务入口|mcp_serve.py", "Claude Code · Cursor · Codex|"]),
        (1, "开放接口", "", ["*OpenAI 兼容 API|gateway/platforms/api_server*.py", "Webhook 入站|gateway/platforms/webhook.py",
                         "MS Graph 订阅|gateway/platforms/msgraph_webhook.py", "A2A 代理互通|plugins/platforms/a2a/"]),
        (1, "定时 & 事件", "", ["*cron 到点触发|cron/scheduler.py", "Kanban 派单监听|gateway/kanban_watchers*.py",
                            "唤醒|gateway/wake.py", "心跳恢复|gateway/run_heartbeat_*.py"]),
    ]),
    ("blue", "② 交互服务层", [
        (1.1, "终端交互", "", [
            "*102 个斜杠命令注册|hermes_cli/commands.py", "斜杠命令处理|hermes_cli/cli_commands_mixin.py",
            "流式输出 · 工具进度|hermes_cli/cli_stream_mixin.py", "steer · queue · retry|hermes_cli/cli_loops_mixin.py",
            "会话 · 撤销 · 重试|hermes_cli/cli_session_mixin.py", "皮肤 · 主题|hermes_cli/skin_engine.py",
            "语音模式|hermes_cli/cli_voice_mixin.py", "*TUI JSON-RPC 后端|tui_gateway/server.py",
            "TUI RPC 方法族|tui_gateway/methods_*.py", "附件 · 图片粘贴|tui_gateway/prompt_attachments.py"]),
        (1, "桌面前端", "apps/desktop/src/app/", [
            "*聊天工作台|chat/", "Artifacts 预览|artifacts/", "会话视图|session/", "会话导入|session-import/",
            "设置 · 模型配置|settings/", "技能管理|skills/", "定时任务面板|cron/", "消息渠道|messaging/",
            "命令面板|command-palette/", "Quick Entry|quick-entry/", "桌宠|pet-overlay/", "Profile 管理|profiles/"]),
        (1, "Dashboard 后端", "hermes_cli/", [
            "*FastAPI 应用门面|web_server.py", "23 个路由模块|web_routers/", "WebSocket 对话|web_routers/chat_ws.py",
            "会话 API|web_routers/sessions.py", "配置 · 环境变量|web_routers/config_env.py", "模型管理|web_routers/models.py",
            "技能 API|web_routers/skills.py", "MCP API|web_routers/mcp.py", "消息渠道 API|web_routers/messaging.py",
            "定时任务 API|web_routers/cron.py"]),
        (1.15, "消息网关", "gateway/", [
            "*网关门面 · 主循环|run.py", "启动阶段|run_startup.py", "适配器装配|run_adapters.py", "入站消息|run_inbound.py",
            "鉴权 mixin|authz_mixin.py", "DM 配对|pairing.py", "会话路由 · 多 Profile|profile_routing.py",
            "忙时队列 · 控制命令|run_busy.py", "斜杠命令处理|slash_commands_*.py", "流式投递|stream_consumer*.py",
            "流式 TTS|streaming_tts_consumer.py", "媒体拉取|media_fetch.py", "Bot Mode 托管房间|hosted_room*.py",
            "Relay 中继|relay/", "投递|delivery.py", "重启 · 看门狗|restart.py · startup_watchdog.py"]),
        (0.8, "编辑器协议", "acp_adapter/", [
            "*ACP 会话管理|session.py", "协议事件|events.py", "编辑审批|edit_approval.py", "权限|permissions.py",
            "模型目录|model_catalog.py", "溯源|provenance.py"]),
        (0.75, "MCP 只读服务", "", [
            "*会话 / 消息查询|mcp_serve.py", "跨平台发送|tools/send_message_tool.py", "只读连接注册|hermes_state_registry.py"]),
        (1.05, "自动化编排", "", [
            "*定时作业 CRUD|cron/jobs.py", "调度 tick · 预检|cron/scheduler*.py", "投递队列|cron/delivery_queue.py",
            "执行记录|cron/executions.py", "事故|cron/incidents.py", "Blueprint 目录|cron/blueprint_catalog.py",
            "*Kanban 看板|hermes_cli/kanban*.py", "Swarm 派单|hermes_cli/kanban_swarm.py",
            "任务拆解|hermes_cli/kanban_decompose.py", "Goals 持久目标|hermes_cli/goals.py"]),
    ]),
    ("green", "③ Agent 核心层", [
        (1.15, "对话轮次引擎", "agent/", [
            "*AIAgent 门面|../run_agent.py", "初始化|agent_init.py", "*对话主循环|conversation_loop.py",
            "运行时助手|agent_runtime_helpers.py", "预检 · 门控|turn_preflight*.py", "请求装配|turn_request_assembly.py",
            "模型调用 · 重试|turn_api_*.py", "工具轮次 · 校验|turn_tool_*.py", "工具执行器|tool_executor.py",
            "异常恢复|turn_recovery.py", "上下文溢出|turn_overflow.py", "停止门|turn_stop_gates.py",
            "迭代预算|iteration_budget.py", "中断 · 急停|interrupt_control.py · estop.py",
            "最终响应|turn_final_response.py", "会话持久化|session_persistence.py"]),
        (1, "提示 & 上下文", "agent/", [
            "*系统提示|system_prompt.py", "提示构建器|prompt_builder.py", "提示缓存|prompt_caching.py",
            "缓存边界|prompt_cache_boundary.py", "目录 hints|subdirectory_hints.py", "@ 引用解析|context_references.py",
            "*上下文压缩|context_compressor.py", "微压缩|micro_compaction.py", "上下文引擎接口|context_engine.py",
            "标题生成|title_generator.py"]),
        (1, "模型接入", "agent/", [
            "*Provider 注册表|provider_registry.py", "传输层|transports/", "Anthropic 适配|anthropic_adapter.py",
            "Gemini 原生适配|gemini_native_adapter.py", "Bedrock 适配|bedrock_adapter.py",
            "Codex Responses|codex_responses_adapter.py", "凭证池 · 轮换|credential_pool.py",
            "限流跟踪|rate_limit_tracker.py", "推理强度|reasoning_effort.py", "Fallback 冷却|fallback_cooldown.py",
            "用量计价|usage_pricing.py", "辅助模型客户端|auxiliary_client.py"]),
        (1, "学习闭环", "agent/", [
            "*记忆管理|memory_manager.py", "记忆 Provider 接口|memory_provider.py", "*后台复盘 · 建技能|background_review.py",
            "/learn 学习|learn_prompt.py", "技能命令|skill_commands.py", "技能预处理|skill_preprocessing.py",
            "Curator 整理|curator.py", "学习图谱|learning_graph.py", "Insights 分析|insights.py", "学习变更|learning_mutations.py"]),
        (0.95, "委派与协同", "", [
            "*子代理委派工具|tools/delegate_tool.py", "子代理生命周期|agent/subagent_lifecycle.py",
            "委派上下文|agent/delegation_context.py", "MoA 多模型混合|agent/moa_loop.py", "/btw 旁路提问|agent/side_question.py",
            "/plan 计划|agent/plan_prompt.py", "/review 评审|agent/review_engine.py", "一次性调用|agent/oneshot.py"]),
        (0.95, "能力提供者注册", "agent/", [
            "*Web 搜索|web_search_registry.py", "图像生成|image_gen_registry.py", "视频生成|video_gen_registry.py",
            "TTS|tts_registry.py", "语音转写|transcription_registry.py", "浏览器|browser_registry.py",
            "终端环境|terminal_env_registry.py", "插件 LLM|plugin_llm.py"]),
    ]),
    ("yellow", "④ 工具能力层", [
        (1, "工具编排", "", [
            "*工具发现 · 调用|model_tools.py", "*工具集定义|toolsets.py", "*注册中心|tools/registry.py",
            "工具集分发|toolset_distributions.py", "按需检索|tools/tool_search.py", "结果落盘|tools/tool_result_storage.py",
            "输出限流|tools/tool_output_limits.py", "参数纠正|tools/arg_coercion.py", "Schema 清洗|tools/schema_sanitizer.py"]),
        (1, "终端 & 代码执行", "tools/", [
            "*terminal 命令|terminal_tool.py", "终端后端选择|terminal_tool_backends.py", "后台进程表|process_registry.py",
            "sudo 守卫|terminal_tool_sudo.py", "*execute_code|code_execution_tool.py", "持久 REPL 内核|code_kernel.py",
            "执行环境基类|environments/base.py", "local · docker · ssh …|environments/"]),
        (1, "文件 & 项目", "tools/", [
            "*读写 · 搜索|file_tools.py", "文件操作|file_operations.py", "patch 解析|patch_parser.py",
            "模糊匹配|fuzzy_match.py", "checkpoint 回滚|checkpoint_manager.py", "working_diff|working_diff.py",
            "子代理 worktree|subagent_worktree.py", "项目工具|project_tools.py"]),
        (1, "浏览器 & 电脑", "tools/", [
            "*浏览器门面|browser_tool.py", "页面快照|browser_tool_snapshot.py", "CDP 调用|browser_cdp_tool.py",
            "对话框|browser_dialog_tool.py", "保险库登录|browser_vault_tool.py", "Camofox|browser_camofox.py",
            "Lightpanda|browser_lightpanda.py", "云浏览器|browser_tool_cloud.py", "computer_use|computer_use_tool.py"]),
        (1, "Web & 多模态", "tools/", [
            "*web_search / extract|web_tools.py", "vision 看图|vision_tools.py", "图像生成|image_generation_tool.py",
            "视频生成|video_generation_tool.py", "TTS|tts_tool.py", "语音转写|transcription_tools.py",
            "实时语音|voice_live.py", "X 搜索|x_search_tool.py"]),
        (1, "知识 & 协作", "tools/", [
            "*memory|memory_tool.py", "session_search|session_search_tool.py", "技能查看|skills_tool.py",
            "技能管理|skill_manager_tool.py", "Skills Hub|skills_hub*.py", "todo|todo_tool.py",
            "clarify|clarify_tool.py", "异步委派|async_delegation.py"]),
        (1, "调度 & 消息", "tools/", [
            "*cronjob|cronjob_tools.py", "kanban|kanban_tools.py", "send_message|send_message_tool.py",
            "表情反应|react_to_message_tool.py", "桌面 UI 工具|desktop_ui.py", "预览|preview_tool.py",
            "连接管理|connections_tool.py"]),
        (1, "外部集成", "tools/", [
            "*MCP 客户端|mcp_tool.py", "MCP 族（15 个）|mcp_tool_*.py", "MCP OAuth|mcp_oauth*.py",
            "Home Assistant|homeassistant_tool.py", "飞书文档|feishu_doc_tool.py", "元宝|yuanbao_tools.py",
            "Discord|discord_tool.py", "Tool Gateway|tool_gateway/"]),
    ]),
    ("purple", "⑤ 扩展生态层", [
        (1, "平台适配插件", "plugins/", [
            "*22 个平台插件|platforms/", "Telegram|platforms/telegram/", "飞书|platforms/feishu/",
            "企业微信|platforms/wecom/", "插件加载器|plugin_loader.py", "插件存储|plugin_storage.py"]),
        (1, "模型 Provider 插件", "plugins/model-providers/", [
            "*39 个 Provider|./", "Nous|nous/", "OpenRouter|openrouter/", "Anthropic|anthropic/",
            "DeepSeek|deepseek/", "自定义端点|custom/"]),
        (1, "记忆后端插件", "plugins/memory/", [
            "*Honcho 用户建模|honcho/", "Mem0|mem0/", "Supermemory|supermemory/", "Hindsight|hindsight/",
            "RetainDB|retaindb/", "查询改写|query_rewrite.py"]),
        (1, "能力后端插件", "plugins/", [
            "*Web 搜索 ×10|web/", "云浏览器|browser/", "图像生成|image_gen/", "视频生成|video_gen/",
            "上下文引擎|context_engine/", "Cron Provider|cron_providers/"]),
        (1, "功能插件", "plugins/", [
            "*Kanban Dashboard|kanban/dashboard/", "Google Meet|google_meet/", "Teams 会议|teams_pipeline/",
            "Langfuse|observability/langfuse/", "磁盘清理|disk-cleanup/", "安全指引|security-guidance/"]),
        (1, "技能库", "", [
            "*内置技能 13 类|skills/", "可选技能 23 类|optional-skills/", "Hub 来源|tools/skills_hub_sources.py",
            "技能同步|tools/skills_sync.py", "插件目录|plugin-catalog/", "可选 MCP|optional-mcps/"]),
    ]),
    ("orange", "⑥ 数据持久层", [
        (1.1, "会话数据库 SessionDB", "", [
            "*门面|hermes_state.py", "表结构|hermes_state_schema.py", "会话|hermes_state_sessions.py",
            "消息|hermes_state_messages.py", "FTS5 检索|hermes_state_search.py", "WAL|hermes_state_wal.py",
            "读连接池|hermes_state_readpool.py", "用量|hermes_state_usage.py", "修复|hermes_state_repair.py",
            "导入导出|hermes_state_portability.py", "连接注册|hermes_state_registry.py", "压缩记录|hermes_state_compression.py"]),
        (1, "配置 & 密钥", "hermes_cli/", [
            "*配置读写|config.py", "默认配置|config_defaults.py", "配置迁移|config_migrations.py", ".env 加载|env_loader.py",
            "Profile|profiles.py", "Vault 存储|../agent/vault_store.py", "1Password|onepassword_*.py", "密钥来源|../agent/secret_sources/"]),
        (1, "学习资产", "", [
            "*记忆存储|tools/memory_tool_store.py", "技能台账|tools/skill_ledger.py", "技能溯源|tools/skill_provenance.py",
            "默认人格 SOUL|hermes_cli/default_soul.py", "人格|hermes_cli/personality.py", "学习变更|agent/learning_mutations.py"]),
        (1, "业务运行态", "", [
            "*cron 作业|cron/jobs.py", "cron 台账|cron/ledger.py", "Kanban DB|hermes_cli/kanban_db*.py",
            "投递台账|gateway/delivery_ledger.py", "死信目标|gateway/dead_targets.py", "托管房间日志|gateway/hosted_rooms.py",
            "网关状态|gateway/status.py", "项目 DB|hermes_cli/projects_db.py"]),
        (1, "日志 & 轨迹", "", [
            "*分级日志|hermes_logging.py", "日志查看|hermes_cli/logs.py", "轨迹记录|agent/trajectory.py",
            "轨迹压缩|trajectory_compressor.py", "批量运行|batch_runner.py", "调试转储|hermes_cli/dump.py"]),
    ]),
    ("grey", "⑦ 基础设施层", [
        (1, "公共基础", "", [
            "*路径 · Profile|hermes_constants.py", "*日志|hermes_logging.py", "时间|hermes_time.py", "通用助手|utils.py",
            "启动引导|hermes_bootstrap.py", "启动看门狗|hermes_startup_watchdog.py"]),
        (1, "LLM 推理服务", "", [
            "*云端 Provider API|", "本地运行时|hermes_cli/local_runtime/", "本地模型|hermes_cli/models_local.py",
            "Tool Gateway|tools/managed_tool_gateway.py", "Nous Portal|hermes_cli/portal_cli.py", "OpenRouter 客户端|tools/openrouter_client.py"]),
        (1, "平台 & 外部 API", "", [
            "*消息平台 Bot API|", "浏览器目标站点|", "MCP stdio 传输|tools/mcp_tool_transport.py", "MCP 死亡监督|tools/mcp_death_supervisor.py"]),
        (1, "运行环境", "", [
            "*服务托管|hermes_cli/service_manager.py", "Docker 镜像|Dockerfile · docker/", "Nix|flake.nix · nix/",
            "Termux 约束|constraints-termux.txt", "安装脚本|setup-hermes.sh", "Python 包|pyproject.toml"]),
    ]),
]

CROSS = [
    ("red", "安全治理", "", [
        "*命令审批|tools/approval.py", "智能审批|tools/approval_smart.py", "Tirith 扫描|tools/tirith_security.py",
        "路径安全|tools/path_security.py", "URL 安全|tools/url_safety.py", "网站策略|tools/website_policy.py",
        "*密钥作用域|agent/secret_scope.py", "脱敏|agent/redact.py", "写入审批|tools/write_approval.py",
        "文件安全|agent/file_safety.py", "工具护栏|agent/tool_guardrails.py", "威胁模式|tools/threat_patterns.py",
        "技能 AST 审计|tools/skills_ast_audit.py", "技能守卫|tools/skills_guard.py", "OSV 漏洞|tools/osv_check.py",
        "SSL 校验|agent/ssl_verify.py", "仓库保护|tools/self_repo_guard.py", "插件守卫|tools/plugin_guard.py",
        "安全审计|hermes_cli/security_audit.py", "DM 配对|gateway/pairing.py", "斜杠权限|gateway/slash_access.py",
        "Dashboard 认证|plugins/dashboard_auth/"]),
    ("blue", "运维管理 · hermes CLI", "hermes_cli/", [
        "*setup 向导|setup.py", "模型配置流程|model_setup_flows.py", "工具配置|tools_config.py", "认证|auth.py",
        "OAuth 设备流|auth_device_flow.py", "Profile 命令|profile_cmd.py", "插件命令|plugins_cmd.py", "Skills Hub|skills_hub.py",
        "网关服务|gateway.py", "自更新|update_cmd.py", "doctor 诊断|doctor.py", "备份|backup.py",
        "OpenClaw 迁移|claw.py", "worktree|worktree_cmd.py", "项目|projects_cmd.py", "会话|sessions_cmd.py",
        "Webhook|webhook.py", "卸载|uninstall.py"]),
    ("grey", "可观测性", "", [
        "*分级日志|hermes_logging.py", "日志 CLI|hermes_cli/logs.py", "Langfuse|plugins/observability/langfuse/",
        "Insights|agent/insights.py", "活跃度|agent/activity_tracking.py", "卡顿检测|gateway/session_stall.py",
        "关停看门狗|gateway/shutdown_watchdog.py", "就绪探针|gateway/readiness.py", "内存监控|gateway/memory_monitor.py",
        "生命周期台账|gateway/lifecycle_ledger.py", "版本漂移|gateway/code_skew.py", "诊断上传|hermes_cli/diagnostics_upload.py",
        "/status|hermes_cli/status.py", "追踪上传|agent/trace_upload.py"]),
]

# ================= 绘制 =================
TOTAL_W = RIGHT_X + RIGHT_W - X0
v("title", "Hermes-Agent · 业务逻辑架构（分层 × 功能 × 代码路径）",
  f"text;html=1;fontSize=30;fontStyle=1;{FONT}align=left;verticalAlign=middle;", X0, 16, 1600, 44)
v("sub", "每个色块 = 一项功能，下方灰色等宽字 = 对应代码路径（相对卡片标题下的 📁 目录；无 📁 时相对仓库根，支持 * 通配）。"
         "红色虚线框 = AgentRuntime 抽取边界（③ + ④）；框外带 ◆ 红边的色块 = 同样属于 AgentRuntime 依赖闭包、需要一起带走的文件。"
         "所有路径已对 fc71fb63e5 逐一校验存在。",
  f"text;html=1;fontSize=13;{FONT}fontColor=#666666;align=left;verticalAlign=middle;whiteSpace=wrap;", X0, 62, TOTAL_W, 44)

# 边界框先占位，保证画在各层下面
cells.append("__BOUNDARY__")

y = 140
layers = []
for idx, (color, name, mods) in enumerate(LAYERS):
    lid, h = draw_layer(y, color, name, mods, mark_closure=idx not in (2, 3))
    layers.append((lid, y, h))
    y += h + LAYER_GAP
main_bottom = y - LAYER_GAP

EDGES = [
    (0, 1, "down", "TTY · HTTP / WebSocket · Webhook / 长连接 · stdio ACP / MCP"),
    (1, 2, "down", "构造 AIAgent(...) · run_conversation()   ← AgentRuntime 对外入口"),
    (2, 3, "down", "handle_function_call() · 按工具集下发 schema"),
    (4, 3, "up", "插件运行时注册：平台适配器 · 模型 Provider · 能力后端 · 工具 · 技能"),
    (4, 5, "down", "各层经 get_hermes_home() 读写 profile 感知的 ~/.hermes/"),
    (5, 6, "down", "依赖基础设施与外部服务"),
]
for a, b, d, label in EDGES:
    if d == "up":
        st = ("exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;"
              "strokeColor=#9673a6;fontColor=#6a4a7a;dashed=1;")
    else:
        st = "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
    e(label, layers[a][0], layers[b][0], st)

# AgentRuntime 边界（③ + ④）
bt = layers[2][1] - 18
bb = layers[3][1] + layers[3][2] + 18
cells[cells.index("__BOUNDARY__")] = (
    f'<mxCell id="AR_BOUNDARY" value="" style="rounded=1;arcSize=1;html=1;fillColor=none;strokeColor=#c0392b;'
    f'strokeWidth=3;dashed=1;dashPattern=10 6;" vertex="1" parent="1">'
    f'<mxGeometry x="{X0 - 16}" y="{bt}" width="{MAIN_W + 32}" height="{bb - bt}" as="geometry" /></mxCell>')
v("AR_LABEL", "AgentRuntime 抽取边界 · ③ Agent 核心 + ④ 工具能力",
  f"rounded=1;html=1;{FONT}fontSize=14;fontStyle=1;fillColor=#c0392b;strokeColor=#c0392b;fontColor=#ffffff;",
  X0 + 70, bt - 16, 440, 32)

# 右侧横切
top = layers[1][1]
right_h = main_bottom - top
v("X", "横切能力 · 贯穿 ②–⑦ 各层（◆ = AgentRuntime 闭包内）",
  f"swimlane;startSize=40;html=1;{FONT}fontSize=15;fontStyle=1;fillColor=#eeeeee;strokeColor=#999999;swimlaneFillColor=#fbfbfb;",
  RIGHT_X, top, RIGHT_W, right_h)
cw = RIGHT_W - 2 * PAD
need = [card_h(cw, c[3]) for c in CROSS]
avail = right_h - 40 - 2 * PAD - (len(CROSS) - 1) * MOD_GAP
extra = max(0, (avail - sum(need)) / len(CROSS))
if avail < sum(need):
    print("WARN right column overflow", avail, sum(need))
yy = 40 + PAD
for (color, t, base, chips), n in zip(CROSS, need):
    draw_card("X", PAD, yy, cw, n + extra, color, t, base, chips, True)
    yy += n + extra + MOD_GAP

# 典型请求链路：(标题, 显示路径, [校验路径], 颜色)
fy = main_bottom + 50
v("flowT", "典型请求链路（一次对话轮次如何穿过各层）",
  f"text;html=1;fontSize=17;fontStyle=1;{FONT}align=left;verticalAlign=middle;", X0, fy, 900, 30)
STEPS = [
    ("① 渠道接入", "gateway/run_inbound.py · tui_gateway/server.py", ["gateway/run_inbound.py", "tui_gateway/server.py"], "grey"),
    ("② 鉴权路由", "gateway/authz_mixin.py · profile_routing.py", ["gateway/authz_mixin.py", "gateway/profile_routing.py"], "blue"),
    ("③ 装配上下文", "agent/turn_request_assembly.py", ["agent/turn_request_assembly.py"], "green"),
    ("④ 模型推理", "agent/turn_api_call.py", ["agent/turn_api_call.py"], "green"),
    ("⑤ 工具执行", "agent/tool_executor.py → model_tools.py", ["agent/tool_executor.py", "model_tools.py"], "yellow"),
    ("⑥ 流式投递", "gateway/stream_consumer.py", ["gateway/stream_consumer.py"], "blue"),
    ("⑦ 持久化", "agent/session_persistence.py", ["agent/session_persistence.py"], "orange"),
    ("⑧ 学习沉淀", "agent/background_review.py", ["agent/background_review.py"], "green"),
]
for *_, checks, _c in STEPS:
    for p in checks:
        if not os.path.exists(os.path.join(REPO, p)):
            missing.append(p)
for p in ["agent/turn_tool_round.py", "agent/iteration_budget.py", "agent/turn_stop_gates.py", "hermes_cli/goals.py"]:
    if not os.path.exists(os.path.join(REPO, p)):
        missing.append(p)
sw = (TOTAL_W + 7 * 16) / len(STEPS)
for i, (a, b, _chk, c) in enumerate(STEPS):
    fill, stroke = PAL[c]
    v(nid("s"), f'<b>{a}</b><br><font face="Menlo" style="font-size:9px" color="#555555">{html.escape(b)}</font>',
      f"shape=step;perimeter=stepPerimeter;fixedSize=1;size=20;whiteSpace=wrap;html=1;{FONT}fontSize=14;"
      f"fillColor={fill};strokeColor={stroke};", X0 + i * (sw - 16), fy + 40, sw, 66)
v("loop", "④ ⇄ ⑤ 循环：模型返回 tool_calls 时经 agent/turn_tool_round.py 执行工具并回灌结果，直到最终回复或触达 "
          "agent/iteration_budget.py / turn_stop_gates.py；Goals 持久目标（hermes_cli/goals.py）在轮次结束后由辅助模型判定是否继续。",
  f"text;html=1;fontSize=12;{FONT}fontColor=#666666;align=left;verticalAlign=middle;", X0, fy + 112, TOTAL_W, 24)

# AgentRuntime 抽取指南
gy = fy + 160
gid = "GUIDE"
v(gid, "AgentRuntime 抽取指南（依赖统计：对闭包内 608 个 .py 文件的 import 语句逐行扫描 · 基线 fc71fb63e5）",
  f"swimlane;startSize=38;html=1;{FONT}fontSize=16;fontStyle=1;fillColor=#f8cecc;strokeColor=#c0392b;"
  f"swimlaneFillColor=#fffafa;align=left;spacingLeft=14;", X0, gy, TOTAL_W, 330)
col_w = (TOTAL_W - 4 * 20) / 3


def guide_col(i, title, body):
    x = 20 + i * (col_w + 20)
    v(nid("gt"), title, f"text;html=1;{FONT}fontSize=14;fontStyle=1;fontColor=#8e2b21;align=left;verticalAlign=middle;",
      x, 48, col_w, 26, gid)
    v(nid("gb"), body, f"text;html=1;{FONT}fontSize=12;fontColor=#333333;align=left;verticalAlign=top;whiteSpace=wrap;spacingTop=4;",
      x, 76, col_w, 240, gid)


guide_col(0, "① 最小依赖闭包（整体带走）",
          "<b>入口</b>：<font face='Menlo'>run_agent.py</font>（AIAgent · run_conversation）<br>"
          "<b>内核</b>：<font face='Menlo'>agent/</font>（turn_* 轮次 · 提示 · 模型接入 · 学习 · 委派 · 注册表）<br>"
          "<b>工具</b>：<font face='Menlo'>model_tools.py · toolsets.py · toolset_distributions.py · tools/</font><br>"
          "<b>状态</b>：<font face='Menlo'>hermes_state.py + hermes_state_*.py</font>（21 个兄弟模块）<br>"
          "<b>基础</b>：<font face='Menlo'>hermes_constants.py · hermes_logging.py · hermes_time.py · utils.py</font><br><br>"
          "内部依赖链：<font face='Menlo'>tools/registry.py</font>（零本地依赖）← <font face='Menlo'>tools/*.py</font> 导入时自注册 ← "
          "<font face='Menlo'>model_tools.py</font> 发现 ← <font face='Menlo'>run_agent.py</font>")
guide_col(1, "② 闭包向外的反向依赖（必须切断或注入）",
          "<b>hermes_cli · 654 处</b>（顶层 64 / 函数内延迟 590，分布在 240 个文件）<br>"
          "　config 194 · auth 58 · plugin_compat 56 · plugins 38 · _subprocess_compat 30<br>"
          "<b>gateway · 105 处</b>（顶层仅 2）<br>"
          "　session_context 41 · status 16 · platforms 16 · config 11 · platform_registry 8<br>"
          "<b>cron · 25 处</b>：jobs 9 · scheduler 9 · lifecycle_guard 3<br>"
          "<b>plugins · 20 处</b>：platforms 7 · web 5 · memory 3 · browser 2<br>"
          "<b>tui_gateway 2 · acp_adapter 1 · cli 1</b><br><br>"
          "<font color='#8e2b21'>绝大多数是函数体内的延迟 import —— 导入期不会失败，运行到对应分支才报错，"
          "抽取后必须按调用路径做 E2E 验证。</font>")
guide_col(2, "③ 建议的接缝（按引用量排序）",
          "<b>1. 配置读取</b>：hermes_cli.config（194）→ 抽出 ConfigSource 接口注入<br>"
          "<b>2. 凭证解析</b>：hermes_cli.auth（58）→ CredentialProvider 接口<br>"
          "<b>3. 兼容指针</b>：hermes_cli.plugin_compat（56）→ AGENTS.md 标注 2026-09-14 随兼容层移除，改为从定义模块导入<br>"
          "<b>4. 会话上下文</b>：gateway.session_context（41）→ SessionContext 由宿主注入<br>"
          "<b>5. 插件发现</b>：hermes_cli.plugins（38）+ plugins.*（20）→ PluginRegistry 接口<br>"
          "<b>6. 宿主回调</b>：gateway.status / cron.* → 事件回调，由宿主实现<br><br>"
          "<font color='#8e2b21'>注意 contract/README.md 规则 4：只依赖 HTTP/WS 契约、不 import 上游内部路径；"
          "代码级抽取对应 b-line 决策文档中已弃用的「方案 2」，会失去自动跟随上游的能力。</font>")

# 图例
ly = gy + 350
v("legT", "图例", f"text;html=1;fontSize=14;fontStyle=1;{FONT}align=left;verticalAlign=middle;", X0, ly, 60, 26)
LEG = [("grey", "接入渠道 / 基础设施"), ("blue", "交互服务 / 运维"), ("green", "Agent 内核"), ("yellow", "工具运行时"),
       ("purple", "插件 / 技能生态"), ("orange", "会话与持久状态"), ("red", "安全边界")]
lx = X0 + 70
for c, t in LEG:
    fill, stroke = PAL[c]
    v(nid("lg"), "", f"rounded=1;html=1;fillColor={fill};strokeColor={stroke};", lx, ly + 5, 30, 16)
    v(nid("lt"), t, f"text;html=1;fontSize=12;{FONT}align=left;verticalAlign=middle;", lx + 36, ly, 160, 26)
    lx += 210
v(nid("lg"), "", "rounded=1;html=1;fillColor=none;strokeColor=#c0392b;strokeWidth=3;dashed=1;", lx, ly + 4, 40, 18)
v(nid("lt"), "AgentRuntime 抽取边界", f"text;html=1;fontSize=12;{FONT}align=left;verticalAlign=middle;fontColor=#c0392b;",
  lx + 46, ly, 170, 26)
lx += 230
v(nid("lg"), "", "rounded=1;html=1;fillColor=#ffffff;strokeColor=#c0392b;strokeWidth=2;", lx, ly + 5, 30, 16)
v(nid("lt"), "◆ 边界外但属于依赖闭包", f"text;html=1;fontSize=12;{FONT}align=left;verticalAlign=middle;fontColor=#c0392b;",
  lx + 36, ly, 200, 26)
lx += 240
v(nid("lt"), "↑ 紫色虚线 = 插件反向注册", f"text;html=1;fontSize=12;{FONT}align=left;verticalAlign=middle;fontColor=#6a4a7a;",
  lx, ly, 220, 26)

# ---------------- 校验 ----------------
if missing:
    print("MISSING PATHS:")
    for m in sorted(set(missing)):
        print("  ", m)
    sys.exit(1)
if too_long:
    print("WARN long paths (may wrap):", sorted(set(too_long)))

page_h = ly + 60
xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="drawio" version="26.0.0">
  <diagram name="业务逻辑架构（含代码路径）" id="biz">
    <mxGraphModel dx="1600" dy="1000" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{TOTAL_W + 80:.0f}" pageHeight="{page_h:.0f}" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
{chr(10).join("        " + c for c in cells)}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
'''
open(OUT, "w").write(xml)
print("ok", OUT, "cells", len(cells), "size", TOTAL_W, "x", page_h)
