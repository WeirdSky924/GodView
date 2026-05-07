"""
预设工作流模板
v8 Agent协作可视化工作台

定义常用的小说创作工作流模板
"""

from app.models.workflow_definition import (
    NodeType,
    WorkflowNode,
    WorkflowEdge,
    WorkflowDefinition,
)


def create_node(
    node_id: str,
    node_type: NodeType,
    label: str,
    x: float,
    y: float,
    agent_type: str = None,
    config: dict = None,
) -> WorkflowNode:
    """创建节点辅助函数"""
    return WorkflowNode(
        id=node_id,
        node_type=node_type,
        label=label,
        agent_type=agent_type,
        config=config or {},
        position={"x": x, "y": y},
    )


def create_edge(edge_id: str, source: str, target: str, condition: dict = None) -> WorkflowEdge:
    """创建边辅助函数"""
    return WorkflowEdge(
        id=edge_id,
        source=source,
        target=target,
        condition=condition,
    )


# ==================== 完整小说创作流程（用户期望的流程） ====================

FULL_NOVEL_WORKFLOW = WorkflowDefinition(
    project_id="system_template",
    name="完整小说创作流程",
    description="开始 → 并行(地图/设定/伏笔/事件) → 编剧 → 角色 → 作家 → 评估 → 条件判断 → 集体讨论/重试 → 结束",
    is_template=True,
    nodes=[
        # 开始
        create_node("start", NodeType.START, "开始", 400, 50),
        # 并行执行: 地图/设定/伏笔/事件
        create_node("parallel_init", NodeType.PARALLEL, "并行初始化", 400, 150, config={"branch_count": 4}),
        create_node("map_agent", NodeType.AGENT, "地图 Agent", 100, 250, "world_map_manager"),
        create_node("setting_agent", NodeType.AGENT, "设定 Agent", 300, 250, "setting"),
        create_node("hook_agent", NodeType.AGENT, "伏笔 Agent", 500, 250, "hook_manager"),
        create_node("event_agent", NodeType.AGENT, "事件 Agent", 700, 250, "event_generator"),
        # 汇聚点
        create_node("merge_point", NodeType.AGENT, "编剧 Agent", 400, 400, "plotter"),
        # 角色互动
        create_node("character_agent", NodeType.AGENT, "角色 Agent", 400, 500, "character"),
        # 作家
        create_node("writer_agent", NodeType.AGENT, "作家 Agent", 400, 600, "writer"),
        # 评估
        create_node("evaluator_agent", NodeType.AGENT, "评估 Agent", 400, 700, "evaluator"),
        # 条件判断
        create_node("quality_check", NodeType.CONDITION, "质量判断", 400, 800),
        # 通过分支
        create_node("group_discussion", NodeType.GROUP_DISCUSSION, "集体讨论", 600, 900),
        # 结束
        create_node("end", NodeType.END, "结束", 400, 1000),
    ],
    edges=[
        # 开始 → 并行节点
        create_edge("e_start_parallel", "start", "parallel_init"),
        # 并行节点 → 4个Agent
        create_edge("e_parallel_map", "parallel_init", "map_agent"),
        create_edge("e_parallel_setting", "parallel_init", "setting_agent"),
        create_edge("e_parallel_hook", "parallel_init", "hook_agent"),
        create_edge("e_parallel_event", "parallel_init", "event_agent"),
        # 4个Agent → 编剧（汇聚）
        create_edge("e_map_plotter", "map_agent", "merge_point"),
        create_edge("e_setting_plotter", "setting_agent", "merge_point"),
        create_edge("e_hook_plotter", "hook_agent", "merge_point"),
        create_edge("e_event_plotter", "event_agent", "merge_point"),
        # 编剧 → 角色 → 作家 → 评估
        create_edge("e_plotter_char", "merge_point", "character_agent"),
        create_edge("e_char_writer", "character_agent", "writer_agent"),
        create_edge("e_writer_eval", "writer_agent", "evaluator_agent"),
        # 评估 → 条件判断
        create_edge("e_eval_check", "evaluator_agent", "quality_check"),
        # 条件判断分支: pass → 集体讨论
        create_edge("e_check_pass", "quality_check", "group_discussion", {"result": "pass"}),
        # 条件判断分支: retry → 回到开始
        create_edge("e_check_retry", "quality_check", "start", {"result": "retry"}),
        # 集体讨论 → 结束
        create_edge("e_discussion_end", "group_discussion", "end"),
    ],
    variables={
        "chapter_num": 1,
        "evaluation_passed": False,
        "retry_count": 0,
    },
)


# ==================== 小说创作标准流程 ====================

DEFAULT_NOVEL_WORKFLOW = WorkflowDefinition(
    project_id="system_template",
    name="小说创作标准流程",
    description="完整的小说章节创作流程：设定确认 → 剧情规划 → 角色互动 → 写作 → 评估",
    is_template=True,
    nodes=[
        # 开始
        create_node("start", NodeType.START, "开始", 300, 50),
        # 阶段1: 设定确认
        create_node("setting_confirm", NodeType.AGENT, "确认设定", 300, 150, "setting"),
        # 阶段2: 剧情规划
        create_node("plot_plan", NodeType.AGENT, "规划剧情", 300, 250, "plotter"),
        create_node("hook_plan", NodeType.AGENT, "规划伏笔", 300, 350, "hook_manager"),
        # 阶段3: 角色互动循环
        create_node("character_loop", NodeType.PARALLEL, "角色互动", 300, 450, config={"branch_count": 3}),
        create_node("dialogue_gen", NodeType.AGENT, "对话生成", 150, 550, "character"),
        create_node("summary", NodeType.AGENT, "摘要提取", 450, 550, "summarizer"),
        # 条件: 章节是否结束
        create_node("chapter_check", NodeType.CONDITION, "章节检查", 300, 650, config={"condition": "context.chapter_complete == true"}),
        # 阶段4: 写作与评估
        create_node("writing", NodeType.AGENT, "章节写作", 300, 750, "writer"),
        create_node("evaluation", NodeType.AGENT, "质量评估", 300, 850, "evaluator"),
        # 条件: 是否需要修改
        create_node("revision_check", NodeType.CONDITION, "修改检查", 300, 950, config={"condition": "context.needs_revision == true"}),
        # 结束
        create_node("end", NodeType.END, "结束", 300, 1050),
    ],
    edges=[
        create_edge("e1", "start", "setting_confirm"),
        create_edge("e2", "setting_confirm", "plot_plan"),
        create_edge("e3", "plot_plan", "hook_plan"),
        create_edge("e4", "hook_plan", "character_loop"),
        create_edge("e5a", "character_loop", "dialogue_gen"),
        create_edge("e5b", "character_loop", "summary"),
        create_edge("e6a", "dialogue_gen", "chapter_check"),
        create_edge("e6b", "summary", "chapter_check"),
        # 分支: 章节未完成返回角色互动
        create_edge("e7a", "chapter_check", "character_loop", {"result": "retry"}),
        # 分支: 章节完成继续写作
        create_edge("e7b", "chapter_check", "writing", {"result": "pass"}),
        create_edge("e8", "writing", "evaluation"),
        # 分支: 需要修改返回写作
        create_edge("e9a", "revision_check", "writing", {"result": "retry"}),
        # 分支: 不需要修改结束
        create_edge("e9b", "revision_check", "end", {"result": "pass"}),
    ],
    variables={
        "chapter_complete": False,
        "needs_revision": False,
        "current_chapter": 1,
    },
)


# ==================== 快速对话流程 ====================

QUICK_DIALOGUE_WORKFLOW = WorkflowDefinition(
    project_id="system_template",
    name="快速对话流程",
    description="简化的对话生成流程，适合快速生成角色对话场景",
    is_template=True,
    nodes=[
        create_node("start", NodeType.START, "开始", 300, 50),
        create_node("select_chars", NodeType.INPUT, "选择角色", 300, 150),
        create_node("dialogue", NodeType.AGENT, "生成对话", 300, 250, "character"),
        create_node("end", NodeType.END, "结束", 300, 350),
    ],
    edges=[
        create_edge("e1", "start", "select_chars"),
        create_edge("e2", "select_chars", "dialogue"),
        create_edge("e3", "dialogue", "end"),
    ],
    variables={
        "present_characters": [],
        "dialogue_turns": 5,
    },
)


# ==================== 章节审核流程 ====================

CHAPTER_REVIEW_WORKFLOW = WorkflowDefinition(
    project_id="system_template",
    name="章节审核流程",
    description="对已写章节进行审核评估，检查逻辑一致性、伏笔状态、角色行为",
    is_template=True,
    nodes=[
        create_node("start", NodeType.START, "开始", 300, 50),
        create_node("load_chapter", NodeType.INPUT, "加载章节", 300, 150),
        # 并行审核
        create_node("parallel_check", NodeType.PARALLEL, "并行审核", 300, 250, config={"branch_count": 3}),
        create_node("logic_check", NodeType.AGENT, "逻辑检查", 100, 350, "evaluator"),
        create_node("hook_check", NodeType.AGENT, "伏笔检查", 300, 350, "hook_manager"),
        create_node("char_check", NodeType.AGENT, "角色检查", 500, 350, "character"),
        # 汇总
        create_node("summary", NodeType.AGENT, "汇总报告", 300, 450, "summarizer"),
        # 条件: 是否需要修改
        create_node("revision_decision", NodeType.CONDITION, "修改决策", 300, 550),
        create_node("apply_fix", NodeType.AGENT, "应用修改", 300, 650, "writer"),
        create_node("end", NodeType.END, "结束", 300, 750),
    ],
    edges=[
        create_edge("e1", "start", "load_chapter"),
        create_edge("e2", "load_chapter", "parallel_check"),
        create_edge("e3a", "parallel_check", "logic_check"),
        create_edge("e3b", "parallel_check", "hook_check"),
        create_edge("e3c", "parallel_check", "char_check"),
        create_edge("e4a", "logic_check", "summary"),
        create_edge("e4b", "hook_check", "summary"),
        create_edge("e4c", "char_check", "summary"),
        create_edge("e5", "summary", "revision_decision"),
        # 分支: 不需要修改直接结束
        create_edge("e6a", "revision_decision", "end", {"result": "pass"}),
        # 分支: 需要修改则应用修改
        create_edge("e6b", "revision_decision", "apply_fix", {"result": "retry"}),
        create_edge("e7", "apply_fix", "end"),
    ],
    variables={
        "needs_revision": False,
        "issues_found": [],
    },
)


# ==================== 世界设定生成流程 ====================

WORLD_BUILDING_WORKFLOW = WorkflowDefinition(
    project_id="system_template",
    name="世界设定生成流程",
    description="从零开始构建完整的世界设定，包括地理、历史、文化、势力",
    is_template=True,
    nodes=[
        create_node("start", NodeType.START, "开始", 300, 50),
        create_node("concept_input", NodeType.INPUT, "输入概念", 300, 150),
        # 并行生成设定
        create_node("parallel_gen", NodeType.PARALLEL, "并行生成", 300, 250, config={"branch_count": 4}),
        create_node("geography", NodeType.AGENT, "地理设定", 50, 350, "world_map_manager"),
        create_node("history", NodeType.AGENT, "历史设定", 200, 350, "setting"),
        create_node("culture", NodeType.AGENT, "文化设定", 400, 350, "setting"),
        create_node("factions", NodeType.AGENT, "势力设定", 550, 350, "setting"),
        # 汇总整合
        create_node("integrate", NodeType.AGENT, "整合设定", 300, 450, "setting"),
        # 生成事件池
        create_node("events", NodeType.AGENT, "生成事件池", 300, 550, "event_generator"),
        create_node("end", NodeType.END, "结束", 300, 650),
    ],
    edges=[
        create_edge("e1", "start", "concept_input"),
        create_edge("e2", "concept_input", "parallel_gen"),
        create_edge("e3a", "parallel_gen", "geography"),
        create_edge("e3b", "parallel_gen", "history"),
        create_edge("e3c", "parallel_gen", "culture"),
        create_edge("e3d", "parallel_gen", "factions"),
        create_edge("e4a", "geography", "integrate"),
        create_edge("e4b", "history", "integrate"),
        create_edge("e4c", "culture", "integrate"),
        create_edge("e4d", "factions", "integrate"),
        create_edge("e5", "integrate", "events"),
        create_edge("e6", "events", "end"),
    ],
    variables={
        "world_concept": "",
        "geography_data": {},
        "history_data": {},
        "culture_data": {},
        "factions_data": {},
        "event_pool": [],
    },
)


# ==================== 模板注册 ====================

WORKFLOW_TEMPLATES: dict[str, WorkflowDefinition] = {
    "full_novel": FULL_NOVEL_WORKFLOW,
    "default_novel": DEFAULT_NOVEL_WORKFLOW,
    "quick_dialogue": QUICK_DIALOGUE_WORKFLOW,
    "chapter_review": CHAPTER_REVIEW_WORKFLOW,
    "world_building": WORLD_BUILDING_WORKFLOW,
}


def get_template(template_id: str) -> WorkflowDefinition | None:
    """获取模板"""
    return WORKFLOW_TEMPLATES.get(template_id)


def list_templates() -> list[dict]:
    """列出所有模板"""
    return [
        {
            "id": template_id,
            "name": template.name,
            "description": template.description,
            "node_count": len(template.nodes),
            "edge_count": len(template.edges),
        }
        for template_id, template in WORKFLOW_TEMPLATES.items()
    ]


def instantiate_template(template_id: str, project_id: str) -> WorkflowDefinition | None:
    """
    从模板创建工作流实例

    Args:
        template_id: 模板ID
        project_id: 项目ID

    Returns:
        WorkflowDefinition: 新的工作流实例
    """
    template = get_template(template_id)
    if not template:
        return None

    # 创建新实例，复制模板内容
    import uuid
    return WorkflowDefinition(
        project_id=project_id,
        name=template.name,
        description=template.description,
        nodes=[WorkflowNode(**n.model_dump()) for n in template.nodes],
        edges=[WorkflowEdge(**e.model_dump()) for e in template.edges],
        variables=dict(template.variables),
        is_template=False,
    )
