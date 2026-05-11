"""
系统内置 Agent 模板数据
提供预定义的 Agent 模板配置
"""

from typing import List

from app.models.agent_template import (
    AgentTemplate,
    AgentType,
    PromptSlot,
    SkillSlot,
)


# ==================== Director System Agent 模板 ====================

DIRECTOR_SUMMARIZER = AgentTemplate(
    id="director_summarizer",
    name="Director Summarizer 模板",
    description="Director System 中的摘要生成 Agent 模板",
    agent_type=AgentType.SUMMARIZER,
    scenario="workflow_summary",
    tags=["director", "summarizer", "summary"],
    prompt_slots=[
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：摘要生成专家",
            prompt_template_id="role_summarizer",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：摘要生成职责",
            prompt_template_id="function_summarize",
            required=True,
            priority=80,
        ),
        PromptSlot(
            slot_name="workflow_performance_summary",
            description="工作流场景演绎总结：剧情推进、角色一致性和可用素材索引",
            prompt_template_id="function_workflow_performance_summary",
            required=False,
            priority=81,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
        # 原创性规范
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "function_spec", "workflow_performance_summary", "output_format"],
    skill_slots=[
        # 通用技能
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        # 摘要员专属技能
        SkillSlot(
            slot_name="primary",
            description="内容摘要技能",
            skill_id="skill_content_summary",
            is_enabled=True,
            is_required=True,
            priority=60,
        ),
        SkillSlot(
            slot_name="discussion",
            description="讨论总结技能",
            skill_id="skill_discussion_summary",
            is_enabled=True,
            is_required=False,
            priority=65,
        ),
        # 字数统计技能
        SkillSlot(
            slot_name="analysis",
            description="字数统计分析",
            skill_id="skill_word_count",
            is_enabled=True,
            is_required=False,
            priority=55,
        ),
    ],
    default_skill_order=["context", "primary", "discussion", "analysis"],
    is_system=True,
)

DIRECTOR_MASTER_PLOTTER = AgentTemplate(
    id="director_master_plotter",
    name="Director Master Plotter 模板",
    description="Director System 中的总编剧 Agent 模板",
    agent_type=AgentType.MASTER_PLOTTER,
    scenario="workflow_plot_planning",
    tags=["director", "master_plotter", "plot", "story_structure"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：总编剧",
            prompt_template_id="role_master_plotter",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：剧情管理职责",
            prompt_template_id="function_plot_management",
            required=True,
            priority=80,
        ),
        PromptSlot(
            slot_name="plot_planning",
            description="整体剧情规划：长篇大纲、章节目标和讨论资产承接",
            prompt_template_id="function_master_plotter_plot_planning",
            required=False,
            priority=85,
        ),
        PromptSlot(
            slot_name="advance_decision",
            description="剧情推进判定：主线进度、伏笔节奏和强制推进边界",
            prompt_template_id="function_master_plotter_advance_decision",
            required=False,
            priority=84,
        ),
        PromptSlot(
            slot_name="workflow_discussion_opening",
            description="工作流集体讨论开场：议题、边界和参会 Agent 引导",
            prompt_template_id="function_workflow_discussion_opening",
            required=False,
            priority=83,
        ),
        PromptSlot(
            slot_name="workflow_discussion_summary",
            description="工作流集体讨论汇总：共识、分歧、待确认讨论资产和用户确认",
            prompt_template_id="function_workflow_discussion_summary",
            required=False,
            priority=82,
        ),
        PromptSlot(
            slot_name="workflow_scene_direction",
            description="工作流场景演绎方向：场景设定、角色分工和信息隔离",
            prompt_template_id="function_workflow_scene_direction",
            required=False,
            priority=81,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=[
        "originality", "role_definition", "function_spec",
        "plot_planning", "advance_decision",
        "workflow_discussion_opening", "workflow_discussion_summary", "workflow_scene_direction",
        "output_format",
    ],
    skill_slots=[
        # 通用技能
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
        # 编剧专属技能
        SkillSlot(
            slot_name="primary",
            description="剧情规划技能",
            skill_id="skill_plot_planning",
            is_enabled=True,
            is_required=True,
            priority=80,
        ),
        SkillSlot(
            slot_name="advancement",
            description="剧情推进评估",
            skill_id="skill_plot_advancement",
            is_enabled=True,
            is_required=False,
            priority=70,
        ),
        SkillSlot(
            slot_name="directions",
            description="场景表演指导",
            skill_id="skill_scene_directions",
            is_enabled=True,
            is_required=False,
            priority=75,
        ),
        # 质量检测技能
        SkillSlot(
            slot_name="power_check",
            description="战力体系校验",
            skill_id="skill_power_level_check",
            is_enabled=True,
            is_required=False,
            priority=85,
        ),
        SkillSlot(
            slot_name="pacing",
            description="节奏分析",
            skill_id="skill_pacing_analysis",
            is_enabled=True,
            is_required=False,
            priority=75,
        ),
    ],
    default_skill_order=["context", "world", "primary", "directions", "power_check", "pacing", "advancement"],
    is_system=True,
)

DIRECTOR_HOOK_MANAGER = AgentTemplate(
    id="director_hook_manager",
    name="Director Hook Manager 模板",
    description="Director System 中的伏笔管理 Agent 模板",
    agent_type=AgentType.HOOK_MANAGER,
    scenario="workflow_hook_management",
    tags=["director", "hook_manager", "foreshadowing", "suspense"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：伏笔管理专家",
            prompt_template_id="role_hook_manager",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：伏笔管理职责",
            prompt_template_id="function_hook_management",
            required=True,
            priority=80,
        ),
        PromptSlot(
            slot_name="workflow_agent_opinion",
            description="工作流创作讨论专业意见：伏笔状态、回收规划和风险预警",
            prompt_template_id="function_workflow_agent_opinion",
            required=False,
            priority=82,
        ),
        PromptSlot(
            slot_name="writing_rules",
            description="写作规则提示（动态加载项目配置的规则）",
            prompt_template_id=None,
            required=False,
            priority=75,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "function_spec", "workflow_agent_opinion", "writing_rules", "output_format"],
    skill_slots=[
        # 通用技能
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        # 伏笔管理员专属技能
        SkillSlot(
            slot_name="primary",
            description="伏笔规划技能",
            skill_id="skill_hook_planning",
            is_enabled=True,
            is_required=True,
            priority=70,
        ),
        SkillSlot(
            slot_name="tracker",
            description="伏笔追踪与提醒",
            skill_id="skill_foreshadowing_tracker",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
    ],
    default_skill_order=["context", "tracker", "primary"],
    is_system=True,
)

DIRECTOR_WRITER = AgentTemplate(
    id="director_writer",
    name="Director Writer 模板",
    description="Director System 中的作家 Agent 模板",
    agent_type=AgentType.WRITER,
    scenario="workflow_chapter_generation",
    tags=["director", "writer", "writing", "story"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：专业作家",
            prompt_template_id="role_writer",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：写作规范",
            prompt_template_id="function_writing",
            required=True,
            priority=85,
        ),
        PromptSlot(
            slot_name="workflow_context_binding",
            description="工作流上下文绑定规则：大纲、设定、角色与讨论资产的优先级",
            prompt_template_id="function_writer_workflow_context_binding",
            required=True,
            priority=82,
        ),
        PromptSlot(
            slot_name="segment_generation",
            description="分段生成与续写补写规则",
            prompt_template_id="function_writer_segment_generation",
            required=False,
            priority=78,
        ),
        PromptSlot(
            slot_name="writing_rules",
            description="写作规则提示（动态加载项目配置的规则）",
            prompt_template_id=None,  # 动态加载，不绑定固定模板
            required=False,
            priority=75,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=False,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "function_spec", "workflow_context_binding", "segment_generation", "writing_rules", "output_format"],
    skill_slots=[
        # 核心技能
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
        SkillSlot(
            slot_name="character_stance",
            description="角色立场约束",
            skill_id="skill_character_stance_constraint",
            is_enabled=True,
            is_required=True,  # 强制要求
            priority=92,
        ),
        SkillSlot(
            slot_name="de_ai",
            description="去AI感自然化写作",
            skill_id="skill_de_ai_if_y",
            is_enabled=True,
            is_required=True,
            priority=91,
        ),
        # 作家专属技能
        SkillSlot(
            slot_name="primary",
            description="章节写作技能",
            skill_id="skill_chapter_writing",
            is_enabled=True,
            is_required=True,
            priority=80,
        ),
        SkillSlot(
            slot_name="scene",
            description="场景描写技能",
            skill_id="skill_scene_description",
            is_enabled=True,
            is_required=False,
            priority=60,
        ),
        # 分段写作技能
        SkillSlot(
            slot_name="planning",
            description="分段生成规划",
            skill_id="skill_segmented_writing",
            is_enabled=True,
            is_required=False,
            priority=85,
        ),
        SkillSlot(
            slot_name="analysis",
            description="字数统计分析",
            skill_id="skill_word_count",
            is_enabled=True,
            is_required=False,
            priority=55,
        ),
        SkillSlot(
            slot_name="postprocessing",
            description="内容合并处理",
            skill_id="skill_content_merge",
            is_enabled=True,
            is_required=False,
            priority=50,
        ),
        # 质量检测技能
        SkillSlot(
            slot_name="cool_check",
            description="爽点检测分析",
            skill_id="skill_cool_point_detection",
            is_enabled=True,
            is_required=False,
            priority=85,
        ),
        SkillSlot(
            slot_name="sensitive",
            description="敏感词检测",
            skill_id="skill_sensitive_word_detection",
            is_enabled=True,
            is_required=False,
            priority=95,
        ),
        SkillSlot(
            slot_name="golden_lines",
            description="金句生成",
            skill_id="skill_golden_line_generator",
            is_enabled=True,
            is_required=False,
            priority=70,
        ),
        SkillSlot(
            slot_name="hook",
            description="章节悬念钩子生成",
            skill_id="skill_chapter_hook_generator",
            is_enabled=True,
            is_required=False,
            priority=75,
        ),
        SkillSlot(
            slot_name="title",
            description="章节标题优化",
            skill_id="skill_chapter_title_optimizer",
            is_enabled=True,
            is_required=False,
            priority=65,
        ),
    ],
    default_skill_order=["context", "character_stance", "de_ai", "world", "primary", "planning", "cool_check", "sensitive", "golden_lines", "hook", "scene", "title", "analysis", "postprocessing"],
    is_system=True,
)

# ==================== 其他 Agent 模板 ====================

EVALUATOR = AgentTemplate(
    id="evaluator",
    name="Evaluator 模板",
    description="内容质量评估 Agent 模板",
    agent_type=AgentType.EVALUATOR,
    scenario="chapter_quality_review",
    tags=["evaluator", "quality", "review", "assessment"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：评估专家",
            prompt_template_id="role_evaluator",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：评估审查职责",
            prompt_template_id="function_evaluation",
            required=True,
            priority=80,
        ),
        PromptSlot(
            slot_name="chapter_quality_gate",
            description="章节质量门禁：章节收尾、上游上下文和长篇逻辑检查",
            prompt_template_id="function_evaluator_chapter_quality_gate",
            required=True,
            priority=82,
        ),
        PromptSlot(
            slot_name="reader_simulation",
            description="读者模拟评分：长篇网文读者体验与后续期待评估",
            prompt_template_id="function_evaluator_reader_simulation",
            required=False,
            priority=76,
        ),
        PromptSlot(
            slot_name="ooc_review",
            description="OOC 角色一致性审查：台词风格、禁用语和角色立场",
            prompt_template_id="function_evaluator_ooc_review",
            required=False,
            priority=74,
        ),
        PromptSlot(
            slot_name="writing_rules",
            description="写作规则提示（动态加载项目配置的规则）",
            prompt_template_id=None,
            required=False,
            priority=75,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "function_spec", "chapter_quality_gate", "reader_simulation", "ooc_review", "writing_rules", "output_format"],
    skill_slots=[
        # 通用技能
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
        # 评估员专属技能
        SkillSlot(
            slot_name="primary",
            description="章节质量评估技能",
            skill_id="skill_chapter_evaluation",
            is_enabled=True,
            is_required=True,
            priority=80,
        ),
        SkillSlot(
            slot_name="simulation",
            description="读者模拟评分技能",
            skill_id="skill_reader_simulation",
            is_enabled=True,
            is_required=False,
            priority=70,
        ),
        SkillSlot(
            slot_name="ooc",
            description="OOC角色崩坏检查技能",
            skill_id="skill_ooc_check",
            is_enabled=True,
            is_required=False,
            priority=75,
        ),
        # 质量检测技能（P0核心）
        SkillSlot(
            slot_name="cool_detection",
            description="爽点检测分析",
            skill_id="skill_cool_point_detection",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
        SkillSlot(
            slot_name="plot_hole",
            description="剧情漏洞检测",
            skill_id="skill_plot_hole_detection",
            is_enabled=True,
            is_required=True,
            priority=95,
        ),
        SkillSlot(
            slot_name="memory_check",
            description="角色记忆一致性检查",
            skill_id="skill_character_memory_check",
            is_enabled=True,
            is_required=False,
            priority=90,
        ),
        SkillSlot(
            slot_name="sensitive",
            description="敏感词检测",
            skill_id="skill_sensitive_word_detection",
            is_enabled=True,
            is_required=True,
            priority=95,
        ),
        SkillSlot(
            slot_name="power_check",
            description="战力体系校验",
            skill_id="skill_power_level_check",
            is_enabled=True,
            is_required=False,
            priority=90,
        ),
        SkillSlot(
            slot_name="setting_conflict",
            description="设定冲突检测",
            skill_id="skill_setting_conflict_detection",
            is_enabled=True,
            is_required=False,
            priority=85,
        ),
        SkillSlot(
            slot_name="pacing",
            description="节奏分析",
            skill_id="skill_pacing_analysis",
            is_enabled=True,
            is_required=False,
            priority=80,
        ),
        SkillSlot(
            slot_name="dialogue_check",
            description="对话风格一致性检查",
            skill_id="skill_dialogue_style_check",
            is_enabled=True,
            is_required=False,
            priority=80,
        ),
        SkillSlot(
            slot_name="golden_three",
            description="黄金三章检测",
            skill_id="skill_golden_three_chapters",
            is_enabled=True,
            is_required=False,
            priority=85,
        ),
        SkillSlot(
            slot_name="timeline",
            description="时间线校验",
            skill_id="skill_timeline_verification",
            is_enabled=True,
            is_required=False,
            priority=70,
        ),
        # 字数统计技能
        SkillSlot(
            slot_name="analysis",
            description="字数统计分析",
            skill_id="skill_word_count",
            is_enabled=True,
            is_required=False,
            priority=55,
        ),
    ],
    default_skill_order=["context", "world", "primary", "plot_hole", "sensitive", "cool_detection", "memory_check", "power_check", "setting_conflict", "golden_three", "pacing", "dialogue_check", "ooc", "simulation", "timeline", "analysis"],
    is_system=True,
)

PROC_GEN = AgentTemplate(
    id="proc_gen",
    name="ProcGen 模板",
    description="过程内容生成 Agent 模板（可选）",
    agent_type=AgentType.PROC_GEN,
    scenario="procedural_generation",
    tags=["proc_gen", "generation", "procedural", "random", "optional"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：生成专家",
            prompt_template_id="role_proc_gen",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="writing_rules",
            description="写作规则提示（动态加载项目配置的规则）",
            prompt_template_id=None,
            required=False,
            priority=75,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "writing_rules", "output_format"],
    skill_slots=[
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
    ],
    default_skill_order=["context"],
    is_system=True,
    is_optional=True,
    is_enabled=False,  # 默认不启用
)

SETTING = AgentTemplate(
    id="setting",
    name="Setting Agent 模板",
    description="设定管理 Agent 模板",
    agent_type=AgentType.SETTING,
    scenario="workflow_context",
    tags=["setting", "lore", "management", "worldbuilding"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：设定管理者",
            prompt_template_id="role_setting",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="resource_management",
            description="资源管理职责：/lore 设定助手、保存确认和副作用边界",
            prompt_template_id="function_setting_resource_management",
            required=False,
            priority=84,
        ),
        PromptSlot(
            slot_name="segmented_context_synthesis",
            description="分段上下文综合：关键信息索引、JSON 容错和跨段综合",
            prompt_template_id="function_setting_segmented_context_synthesis",
            required=False,
            priority=83,
        ),
        PromptSlot(
            slot_name="lore_interconnection",
            description="设定互联规则：依赖、支撑、冲突和使用指引",
            prompt_template_id="function_setting_lore_interconnection",
            required=False,
            priority=82,
        ),
        PromptSlot(
            slot_name="requirement_resolution",
            description="大纲资源需求解决：绑定已有资源、创建待确认草案或提出缺口",
            prompt_template_id="function_setting_requirement_resolution",
            required=False,
            priority=81,
        ),
        PromptSlot(
            slot_name="writing_rules",
            description="写作规则提示（动态加载项目配置的规则）",
            prompt_template_id=None,
            required=False,
            priority=75,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "resource_management", "segmented_context_synthesis", "lore_interconnection", "requirement_resolution", "writing_rules", "output_format"],
    skill_slots=[
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
    ],
    default_skill_order=["context", "world"],
    is_system=True,
)

CHARACTER = AgentTemplate(
    id="character",
    name="Character Agent 模板",
    description="角色对话 Agent 模板",
    agent_type=AgentType.CHARACTER,
    scenario="roleplay",
    tags=["character", "conversation", "dialogue", "npc"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：虚拟角色",
            prompt_template_id="role_character",
            required=True,
            priority=90,
            variable_overrides={
                "character_background": "",
                "character_personality": "",
                "character_goals": "",
            },
        ),
        PromptSlot(
            slot_name="roleplay_decision",
            description="角色决策规则：结构化台词、动作、内心和情绪输出",
            prompt_template_id="function_character_roleplay_decision",
            required=True,
            priority=83,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "roleplay_decision"],
    skill_slots=[
        # 通用技能
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
        # 角色演绎专属技能
        SkillSlot(
            slot_name="primary",
            description="角色表演技能",
            skill_id="skill_character_performance",
            is_enabled=True,
            is_required=True,
            priority=80,
        ),
        SkillSlot(
            slot_name="ooc",
            description="OOC检查技能",
            skill_id="skill_ooc_check",
            is_enabled=True,
            is_required=False,
            priority=70,
        ),
        SkillSlot(
            slot_name="dialogue",
            description="对话风格一致性检查",
            skill_id="skill_dialogue_style_check",
            is_enabled=True,
            is_required=False,
            priority=85,
        ),
        SkillSlot(
            slot_name="memory",
            description="角色记忆一致性检查",
            skill_id="skill_character_memory_check",
            is_enabled=True,
            is_required=False,
            priority=80,
        ),
    ],
    default_skill_order=["context", "world", "primary", "dialogue", "memory", "ooc"],
    is_system=True,
)

# ==================== 核心扩展 Agent 模板 ====================

EVENT_GENERATOR = AgentTemplate(
    id="event_generator",
    name="事件生成 Agent 模板",
    description="生成故事事件、转折和随机变数的核心 Agent",
    agent_type=AgentType.EVENT_GENERATOR,
    scenario="event_generation",
    tags=["event", "generator", "core", "plot"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：事件生成专家",
            prompt_template_id="role_event_generator",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：事件生成职责",
            prompt_template_id="function_event_generation",
            required=True,
            priority=80,
        ),
        PromptSlot(
            slot_name="writing_rules",
            description="写作规则提示（动态加载项目配置的规则）",
            prompt_template_id=None,
            required=False,
            priority=75,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "function_spec", "writing_rules", "output_format"],
    skill_slots=[
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
    ],
    default_skill_order=["context", "world"],
    is_system=True,
    is_optional=False,  # 核心 Agent
    is_enabled=True,
)

WORLD_MAP_MANAGER = AgentTemplate(
    id="world_map_manager",
    name="世界地图管理 Agent 模板",
    description="管理世界地图、地点和空间关系的核心 Agent",
    agent_type=AgentType.WORLD_MAP_MANAGER,
    scenario="world_map_management",
    tags=["map", "world", "geography", "core", "location"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：地图管理专家",
            prompt_template_id="role_world_map_manager",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：地图管理职责",
            prompt_template_id="function_map_management",
            required=True,
            priority=80,
        ),
        PromptSlot(
            slot_name="writing_rules",
            description="写作规则提示（动态加载项目配置的规则）",
            prompt_template_id=None,
            required=False,
            priority=75,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "function_spec", "writing_rules", "output_format"],
    skill_slots=[
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
    ],
    default_skill_order=["context", "world"],
    is_system=True,
    is_optional=False,  # 核心 Agent
    is_enabled=True,
)

# ==================== 可选 Agent 模板 ====================

DUNGEON_GENERATOR = AgentTemplate(
    id="dungeon_generator",
    name="副本生成 Agent 模板",
    description="生成故事副本、挑战和任务的可选 Agent",
    agent_type=AgentType.DUNGEON_GENERATOR,
    scenario="dungeon_generation",
    tags=["dungeon", "instance", "generator", "optional", "challenge"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：副本生成专家",
            prompt_template_id="role_dungeon_generator",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：副本设计职责",
            prompt_template_id="function_dungeon_design",
            required=True,
            priority=80,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "function_spec", "output_format"],
    skill_slots=[
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
    ],
    default_skill_order=["context", "world"],
    is_system=True,
    is_optional=True,
    is_enabled=False,  # 默认不启用
)

# ==================== 场景协调 Agent 模板 ====================

# ==================== 章节大纲规划 Agent 模板 (v9) ====================

PLOT_OUTLINE = AgentTemplate(
    id="plot_outline",
    name="章节大纲规划 Agent 模板",
    description="v9 新增：规划章节大纲的 Agent，负责场景规划、情绪曲线设计、爽点设计和章节目标设定",
    agent_type=AgentType.PLOT_OUTLINE,
    scenario="generate_chapter_outline",
    tags=["outline", "planning", "chapter", "v9", "core"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：章节大纲规划师",
            prompt_template_id="role_plot_outline",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：章节大纲规划职责",
            prompt_template_id="function_plot_outline",
            required=True,
            priority=80,
        ),
        PromptSlot(
            slot_name="writing_rules",
            description="写作规则提示（动态加载项目配置的规则）",
            prompt_template_id=None,
            required=False,
            priority=75,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "function_spec", "writing_rules", "output_format"],
    skill_slots=[
        # 核心技能（必须加载）
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
        SkillSlot(
            slot_name="outline_context",
            description="大纲上下文组装",
            skill_id="skill_outline_context",
            is_enabled=True,
            is_required=True,
            priority=95,
        ),
        SkillSlot(
            slot_name="character_stance",
            description="角色立场约束",
            skill_id="skill_character_stance_constraint",
            is_enabled=True,
            is_required=True,  # 强制要求
            priority=92,
        ),
        # 大纲生成核心技能
        SkillSlot(
            slot_name="outline_gen",
            description="章节大纲生成",
            skill_id="skill_chapter_outline_generation",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
        SkillSlot(
            slot_name="outline_val",
            description="章节大纲验证",
            skill_id="skill_chapter_outline_validation",
            is_enabled=True,
            is_required=False,
            priority=75,
        ),
        # 网文特色技能
        SkillSlot(
            slot_name="cool_points",
            description="网文爽点设计",
            skill_id="skill_webnovel_cool_points",
            is_enabled=True,
            is_required=True,  # 网文必备
            priority=88,
        ),
        SkillSlot(
            slot_name="hooks_design",
            description="章节钩子设计",
            skill_id="skill_chapter_hooks_design",
            is_enabled=True,
            is_required=True,  # 网文必备
            priority=87,
        ),
        # 反派戏份规划
        SkillSlot(
            slot_name="villain_arc",
            description="章节反派戏份规划",
            skill_id="skill_chapter_villain_arc",
            is_enabled=True,
            is_required=False,
            priority=86,
        ),
        SkillSlot(
            slot_name="villain",
            description="反派管理",
            skill_id="skill_villain_management",
            is_enabled=True,
            is_required=False,
            priority=85,
        ),
        # 其他规划技能
        SkillSlot(
            slot_name="opening",
            description="开局设计",
            skill_id="skill_opening_design",
            is_enabled=True,
            is_required=False,
            priority=85,
        ),
        SkillSlot(
            slot_name="volume",
            description="卷规划",
            skill_id="skill_volume_planning",
            is_enabled=True,
            is_required=False,
            priority=80,
        ),
    ],
    default_skill_order=[
        "context", "outline_context", "character_stance", "world",
        "outline_gen", "cool_points", "hooks_design",
        "villain_arc", "villain",
        "outline_val", "opening", "volume"
    ],
    is_system=True,
    is_optional=False,  # 核心 Agent
    is_enabled=True,
)


# ==================== 关键场景变体模板 ====================

def _template_with_prompt_slots(
    base: AgentTemplate,
    *,
    template_id: str,
    name: str,
    description: str,
    scenario: str,
    tags: List[str],
    slots: List[PromptSlot],
    order: List[str],
) -> AgentTemplate:
    template = base.model_copy(
        deep=True,
        update={
            "id": template_id,
            "name": name,
            "description": description,
            "scenario": scenario,
            "tags": tags,
        },
    )
    existing = {slot.slot_name for slot in template.prompt_slots}
    template.prompt_slots.extend(slot for slot in slots if slot.slot_name not in existing)
    template.default_prompt_order = order
    return template


MASTER_PLOTTER_WORKFLOW_CHAPTER_PLANNING = _template_with_prompt_slots(
    DIRECTOR_MASTER_PLOTTER,
    template_id="director_master_plotter_workflow_chapter_planning",
    name="Director Master Plotter 章节执行计划模板",
    description="总编剧在章节工作流中把 approved 大纲转译为 Writer 可执行计划的场景模板",
    scenario="workflow_chapter_planning",
    tags=["director", "master_plotter", "chapter_planning", "workflow"],
    slots=[
        PromptSlot(
            slot_name="chapter_writing_plan",
            description="章节写作执行计划：Writer 可执行计划、素材整合和冲突提示",
            prompt_template_id="function_master_plotter_chapter_writing_plan",
            required=True,
            priority=86,
        ),
    ],
    order=["originality", "role_definition", "function_spec", "chapter_writing_plan", "output_format"],
)

MASTER_PLOTTER_WORKFLOW_PLOT_ADVANCE = _template_with_prompt_slots(
    DIRECTOR_MASTER_PLOTTER,
    template_id="director_master_plotter_workflow_plot_advance",
    name="Director Master Plotter 剧情推进判定模板",
    description="总编剧在章节交互中判断主线推进、伏笔提示和强制推进事件边界的场景模板",
    scenario="workflow_plot_advance",
    tags=["director", "master_plotter", "plot", "advance", "workflow"],
    slots=[
        PromptSlot(
            slot_name="advance_decision",
            description="剧情推进判定：主线进度、伏笔节奏和强制推进边界",
            prompt_template_id="function_master_plotter_advance_decision",
            required=True,
            priority=84,
        ),
    ],
    order=["originality", "role_definition", "function_spec", "advance_decision", "output_format"],
)

MASTER_PLOTTER_WORKFLOW_FORCED_EVENT = _template_with_prompt_slots(
    DIRECTOR_MASTER_PLOTTER,
    template_id="director_master_plotter_workflow_forced_event",
    name="Director Master Plotter 强制推进事件模板",
    description="总编剧在互动停滞或达到轮次阈值时生成轻量外部推进事件的场景模板",
    scenario="workflow_forced_event",
    tags=["director", "master_plotter", "forced_event", "workflow", "pacing"],
    slots=[
        PromptSlot(
            slot_name="forced_event",
            description="强制推进事件：低侵入、可写、承接既有伏笔的外部触发",
            prompt_template_id="function_master_plotter_forced_event",
            required=True,
            priority=82,
        ),
    ],
    order=["originality", "role_definition", "function_spec", "forced_event"],
)

WRITER_REWRITE_BY_REVIEW = DIRECTOR_WRITER.model_copy(
    deep=True,
    update={
        "id": "director_writer_rewrite_by_review",
        "name": "Director Writer 评审重写模板",
        "description": "Writer 根据 Evaluator 反馈和既有大纲约束进行章节修订的场景模板",
        "scenario": "rewrite_by_review",
        "tags": ["director", "writer", "rewrite", "review"],
    },
)

WRITER_STYLE_CONSISTENCY = DIRECTOR_WRITER.model_copy(
    deep=True,
    update={
        "id": "director_writer_style_consistency",
        "name": "Director Writer 风格一致性检查模板",
        "description": "Writer 对新生成章节与前文样本进行叙述视角、句式、用词和节奏一致性检查的场景模板",
        "scenario": "style_consistency_check",
        "tags": ["director", "writer", "style", "consistency", "review"],
        "prompt_slots": [
            PromptSlot(
                slot_name="originality",
                description="原创性创作指南",
                prompt_template_id="originality_guidelines",
                required=True,
                priority=95,
            ),
            PromptSlot(
                slot_name="role_definition",
                description="角色定义：专业作家",
                prompt_template_id="role_writer",
                required=True,
                priority=90,
            ),
            PromptSlot(
                slot_name="function_spec",
                description="功能规范：写作规范",
                prompt_template_id="function_writing",
                required=True,
                priority=85,
            ),
            PromptSlot(
                slot_name="style_consistency",
                description="风格一致性检查：叙述视角、句式、用词和节奏对比",
                prompt_template_id="function_writer_style_consistency",
                required=True,
                priority=82,
            ),
            PromptSlot(
                slot_name="writing_rules",
                description="写作规则提示（动态加载项目配置的规则）",
                prompt_template_id=None,
                required=False,
                priority=75,
            ),
            PromptSlot(
                slot_name="output_format",
                description="输出格式规范",
                prompt_template_id="base_json_output",
                required=True,
                priority=70,
            ),
        ],
        "default_prompt_order": ["originality", "role_definition", "function_spec", "style_consistency", "writing_rules", "output_format"],
    },
)

EVALUATOR_OUTLINE_QUALITY_REVIEW = EVALUATOR.model_copy(
    deep=True,
    update={
        "id": "evaluator_outline_quality_review",
        "name": "Evaluator 大纲质量评审模板",
        "description": "Evaluator 对章节大纲进行长篇节奏、资源门禁和后续兼容性评审的场景模板",
        "scenario": "outline_quality_review",
        "tags": ["evaluator", "outline", "quality", "review"],
    },
)

SETTING_RESOURCE_MANAGEMENT = SETTING.model_copy(
    deep=True,
    update={
        "id": "setting_resource_management",
        "name": "Setting 资源管理模板",
        "description": "Setting 在 /lore 和资源管理界面分析、创建、修订设定资源的场景模板",
        "scenario": "resource_management",
        "tags": ["setting", "lore", "resource_management"],
    },
)

SETTING_OUTLINE_REQUIREMENT_RESOLUTION = SETTING.model_copy(
    deep=True,
    update={
        "id": "setting_outline_requirement_resolution",
        "name": "Setting 大纲资源需求解决模板",
        "description": "Setting 根据大纲资源缺口补齐或绑定设定资源的场景模板",
        "scenario": "outline_requirement_resolution",
        "tags": ["setting", "outline", "requirement_resolution"],
    },
)

SETTING_OUTLINE_REVISION_PROPOSAL = SETTING.model_copy(
    deep=True,
    update={
        "id": "setting_outline_revision_proposal",
        "name": "Setting 大纲修订建议模板",
        "description": "Setting 在设定变化影响 approved 大纲时只提出 revision proposal 的场景模板",
        "scenario": "outline_revision_proposal",
        "tags": ["setting", "outline", "revision_proposal"],
    },
)

PLOT_OUTLINE_VALIDATE_LONG_NOVEL_PACING = PLOT_OUTLINE.model_copy(
    deep=True,
    update={
        "id": "plot_outline_validate_long_novel_pacing",
        "name": "章节大纲长篇节奏验证模板",
        "description": "Plot Outline 验证章节大纲是否符合长篇慢热节奏和反派层级控制的场景模板",
        "scenario": "validate_long_novel_pacing",
        "tags": ["outline", "validation", "long_novel", "pacing"],
    },
)

PLOT_OUTLINE_AUDIT_RESOURCE_REQUIREMENTS = PLOT_OUTLINE.model_copy(
    deep=True,
    update={
        "id": "plot_outline_audit_resource_requirements",
        "name": "章节大纲资源需求审计模板",
        "description": "Plot Outline 审计章节大纲所需角色、设定、地点和危机解决资源缺口的场景模板",
        "scenario": "audit_resource_requirements",
        "tags": ["outline", "resource_audit", "requirements"],
    },
)

PLOT_OUTLINE_PROPOSE_REVISION = PLOT_OUTLINE.model_copy(
    deep=True,
    update={
        "id": "plot_outline_propose_revision",
        "name": "章节大纲修订建议模板",
        "description": "Plot Outline 对 approved 大纲提出修订草案而非静默覆盖的场景模板",
        "scenario": "propose_revision",
        "tags": ["outline", "revision_proposal"],
    },
)

WORLD_MAP_MANAGER_DRAFT = _template_with_prompt_slots(
    WORLD_MAP_MANAGER,
    template_id="world_map_manager_draft",
    name="世界地图管理 Agent 草稿模板",
    description="WorldMapManager 在地图管理页根据用户自然语言生成可编辑区域草稿的场景模板",
    scenario="world_map_draft_generation",
    tags=["map", "world", "geography", "draft", "location"],
    slots=[
        PromptSlot(
            slot_name="map_draft_request",
            description="地图草稿生成：用户请求、现有区域、选中区域和草稿输出边界",
            prompt_template_id="function_map_draft_generation",
            required=True,
            priority=82,
        ),
    ],
    order=["originality", "role_definition", "function_spec", "map_draft_request", "writing_rules", "output_format"],
)


MASTER_PLOTTER_WORKFLOW_DISCUSSION_OPENING = _template_with_prompt_slots(
    DIRECTOR_MASTER_PLOTTER,
    template_id="director_master_plotter_workflow_discussion_opening",
    name="Director Master Plotter 创作讨论开场模板",
    description="总编剧在集体讨论节点中开启会议、设定议题和声明讨论边界的场景模板",
    scenario="workflow_discussion_opening",
    tags=["director", "master_plotter", "workflow", "discussion", "opening"],
    slots=[
        PromptSlot(
            slot_name="workflow_discussion_opening",
            description="工作流集体讨论开场：议题、边界和参会 Agent 引导",
            prompt_template_id="function_workflow_discussion_opening",
            required=True,
            priority=83,
        ),
    ],
    order=["originality", "role_definition", "function_spec", "workflow_discussion_opening", "output_format"],
)

MASTER_PLOTTER_WORKFLOW_DISCUSSION_SUMMARY = _template_with_prompt_slots(
    DIRECTOR_MASTER_PLOTTER,
    template_id="director_master_plotter_workflow_discussion_summary",
    name="Director Master Plotter 创作讨论汇总模板",
    description="总编剧在集体讨论节点中汇总观点、整理待确认资产并请求用户确认的场景模板",
    scenario="workflow_discussion_summary",
    tags=["director", "master_plotter", "workflow", "discussion", "summary"],
    slots=[
        PromptSlot(
            slot_name="workflow_discussion_summary",
            description="工作流集体讨论汇总：共识、分歧、待确认讨论资产和用户确认",
            prompt_template_id="function_workflow_discussion_summary",
            required=True,
            priority=82,
        ),
    ],
    order=["originality", "role_definition", "function_spec", "workflow_discussion_summary", "output_format"],
)

MASTER_PLOTTER_WORKFLOW_SCENE_DIRECTION = _template_with_prompt_slots(
    DIRECTOR_MASTER_PLOTTER,
    template_id="director_master_plotter_workflow_scene_direction",
    name="Director Master Plotter 场景演绎方向模板",
    description="总编剧为多角色演绎生成场景设定、角色分工和信息边界的场景模板",
    scenario="workflow_scene_direction",
    tags=["director", "master_plotter", "workflow", "scene", "direction"],
    slots=[
        PromptSlot(
            slot_name="workflow_scene_direction",
            description="工作流场景演绎方向：场景设定、角色分工和信息隔离",
            prompt_template_id="function_workflow_scene_direction",
            required=True,
            priority=81,
        ),
    ],
    order=["originality", "role_definition", "function_spec", "workflow_scene_direction", "output_format"],
)

SUMMARIZER_WORKFLOW_PERFORMANCE_SUMMARY = _template_with_prompt_slots(
    DIRECTOR_SUMMARIZER,
    template_id="director_summarizer_workflow_performance_summary",
    name="Director Summarizer 场景演绎总结模板",
    description="Summarizer 将多角色演绎整理为 Writer / Master Plotter 可参考素材索引的场景模板",
    scenario="workflow_performance_summary",
    tags=["director", "summarizer", "workflow", "performance", "summary"],
    slots=[
        PromptSlot(
            slot_name="workflow_performance_summary",
            description="工作流场景演绎总结：剧情推进、角色一致性和可用素材索引",
            prompt_template_id="function_workflow_performance_summary",
            required=True,
            priority=81,
        ),
    ],
    order=["originality", "role_definition", "function_spec", "workflow_performance_summary", "output_format"],
)

CHARACTER_WORKFLOW_PERFORMANCE = _template_with_prompt_slots(
    CHARACTER,
    template_id="character_workflow_character_performance",
    name="Character 工作流角色演绎模板",
    description="Character 在多角色场景中按角色认知、信息隔离和角色定位进行第一人称表演的场景模板",
    scenario="workflow_character_performance",
    tags=["character", "workflow", "performance", "roleplay"],
    slots=[
        PromptSlot(
            slot_name="workflow_character_performance",
            description="工作流角色演绎：第一人称表演、信息隔离和角色定位",
            prompt_template_id="function_workflow_character_performance",
            required=True,
            priority=82,
        ),
    ],
    order=["originality", "role_definition", "workflow_character_performance"],
)
CHARACTER_WORKFLOW_PERFORMANCE.prompt_slots = [
    slot for slot in CHARACTER_WORKFLOW_PERFORMANCE.prompt_slots
    if slot.slot_name != "roleplay_decision"
]


def _workflow_agent_opinion_template(base: AgentTemplate, template_id: str, name: str, description: str) -> AgentTemplate:
    return _template_with_prompt_slots(
        base,
        template_id=template_id,
        name=name,
        description=description,
        scenario="workflow_agent_opinion",
        tags=list(dict.fromkeys([*base.tags, "workflow", "discussion", "opinion"])),
        slots=[
            PromptSlot(
                slot_name="workflow_agent_opinion",
                description="工作流创作讨论专业意见：职责分析、问题诊断、改进建议和风险预警",
                prompt_template_id="function_workflow_agent_opinion",
                required=True,
                priority=82,
            ),
        ],
        order=["originality", "role_definition", "function_spec", "workflow_agent_opinion", "writing_rules", "output_format"],
    )


HOOK_MANAGER_WORKFLOW_AGENT_OPINION = _workflow_agent_opinion_template(
    DIRECTOR_HOOK_MANAGER,
    "director_hook_manager_workflow_agent_opinion",
    "Director Hook Manager 创作讨论意见模板",
    "Hook Manager 在集体讨论节点中审查伏笔状态、回收规划和悬念风险的场景模板",
)

WRITER_WORKFLOW_AGENT_OPINION = _workflow_agent_opinion_template(
    DIRECTOR_WRITER,
    "director_writer_workflow_agent_opinion",
    "Director Writer 创作讨论意见模板",
    "Writer 在集体讨论节点中审查文字表达、章节事件推进和素材可写性的场景模板",
)

EVALUATOR_WORKFLOW_AGENT_OPINION = _workflow_agent_opinion_template(
    EVALUATOR,
    "evaluator_workflow_agent_opinion",
    "Evaluator 创作讨论意见模板",
    "Evaluator 在集体讨论节点中提供质量诊断、长篇逻辑 gate 和风险预警的场景模板",
)

SETTING_WORKFLOW_AGENT_OPINION = _workflow_agent_opinion_template(
    SETTING,
    "setting_workflow_agent_opinion",
    "Setting 创作讨论意见模板",
    "Setting 在集体讨论节点中审查设定一致性、资源缺口和潜在冲突的场景模板",
)

CHARACTER_WORKFLOW_AGENT_OPINION = _workflow_agent_opinion_template(
    CHARACTER,
    "character_workflow_agent_opinion",
    "Character 创作讨论意见模板",
    "Character 在集体讨论节点中审查角色行为、人设一致性、对话和 OOC 风险的场景模板",
)

# ==================== 场景协调 Agent 模板 ====================

SCENE_COORDINATOR = AgentTemplate(
    id="scene_coordinator",
    name="场景协调 Agent 模板",
    description="统筹多角色演绎场景的核心 Agent，负责信息分配、顺序协调和内容整合",
    agent_type=AgentType.SCENE_COORDINATOR,
    scenario="scene_coordination",
    tags=["scene", "coordinator", "multi-character", "core", "performance"],
    prompt_slots=[
        PromptSlot(
            slot_name="originality",
            description="原创性创作指南",
            prompt_template_id="originality_guidelines",
            required=True,
            priority=95,
        ),
        PromptSlot(
            slot_name="role_definition",
            description="角色定义：场景协调者",
            prompt_template_id="role_scene_coordinator",
            required=True,
            priority=90,
        ),
        PromptSlot(
            slot_name="function_spec",
            description="功能规范：场景协调职责",
            prompt_template_id="function_scene_coordination",
            required=True,
            priority=80,
        ),
        PromptSlot(
            slot_name="workflow_scene_direction",
            description="工作流场景演绎方向：场景设定、角色分工和信息隔离",
            prompt_template_id="function_workflow_scene_direction",
            required=False,
            priority=81,
        ),
        PromptSlot(
            slot_name="output_format",
            description="输出格式规范",
            prompt_template_id="base_json_output",
            required=True,
            priority=70,
        ),
    ],
    default_prompt_order=["originality", "role_definition", "function_spec", "workflow_scene_direction", "output_format"],
    skill_slots=[
        SkillSlot(
            slot_name="context",
            description="长篇小说创作意识",
            skill_id="skill_long_novel_awareness",
            is_enabled=True,
            is_required=True,
            priority=100,
        ),
        SkillSlot(
            slot_name="world",
            description="世界观上下文",
            skill_id="skill_world_context",
            is_enabled=True,
            is_required=True,
            priority=90,
        ),
        SkillSlot(
            slot_name="directions",
            description="场景表演指导",
            skill_id="skill_scene_directions",
            is_enabled=True,
            is_required=True,
            priority=85,
        ),
        SkillSlot(
            slot_name="performance",
            description="角色表演技能",
            skill_id="skill_character_performance",
            is_enabled=True,
            is_required=False,
            priority=75,
        ),
        # 分段写作技能
        SkillSlot(
            slot_name="planning",
            description="分段生成规划",
            skill_id="skill_segmented_writing",
            is_enabled=True,
            is_required=False,
            priority=80,
        ),
        SkillSlot(
            slot_name="analysis",
            description="字数统计分析",
            skill_id="skill_word_count",
            is_enabled=True,
            is_required=False,
            priority=55,
        ),
        SkillSlot(
            slot_name="postprocessing",
            description="内容合并处理",
            skill_id="skill_content_merge",
            is_enabled=True,
            is_required=False,
            priority=50,
        ),
    ],
    default_skill_order=["context", "world", "directions", "performance", "planning", "analysis", "postprocessing"],
    is_system=True,
    is_optional=False,  # 核心 Agent
    is_enabled=True,
)

# ==================== 系统 Agent 模板列表 ====================

SYSTEM_AGENT_TEMPLATES = [
    # 核心 Agent（不可关闭）
    DIRECTOR_SUMMARIZER,
    SUMMARIZER_WORKFLOW_PERFORMANCE_SUMMARY,
    DIRECTOR_MASTER_PLOTTER,
    MASTER_PLOTTER_WORKFLOW_CHAPTER_PLANNING,
    MASTER_PLOTTER_WORKFLOW_PLOT_ADVANCE,
    MASTER_PLOTTER_WORKFLOW_FORCED_EVENT,
    MASTER_PLOTTER_WORKFLOW_DISCUSSION_OPENING,
    MASTER_PLOTTER_WORKFLOW_DISCUSSION_SUMMARY,
    MASTER_PLOTTER_WORKFLOW_SCENE_DIRECTION,
    DIRECTOR_HOOK_MANAGER,
    HOOK_MANAGER_WORKFLOW_AGENT_OPINION,
    DIRECTOR_WRITER,
    WRITER_REWRITE_BY_REVIEW,
    WRITER_STYLE_CONSISTENCY,
    WRITER_WORKFLOW_AGENT_OPINION,
    EVALUATOR,
    EVALUATOR_OUTLINE_QUALITY_REVIEW,
    EVALUATOR_WORKFLOW_AGENT_OPINION,
    PROC_GEN,
    SETTING,
    SETTING_RESOURCE_MANAGEMENT,
    SETTING_OUTLINE_REQUIREMENT_RESOLUTION,
    SETTING_OUTLINE_REVISION_PROPOSAL,
    SETTING_WORKFLOW_AGENT_OPINION,
    CHARACTER,
    CHARACTER_WORKFLOW_PERFORMANCE,
    CHARACTER_WORKFLOW_AGENT_OPINION,
    SCENE_COORDINATOR,
    PLOT_OUTLINE,
    PLOT_OUTLINE_VALIDATE_LONG_NOVEL_PACING,
    PLOT_OUTLINE_AUDIT_RESOURCE_REQUIREMENTS,
    PLOT_OUTLINE_PROPOSE_REVISION,
    # 可选 Agent（可按需启用）
    EVENT_GENERATOR,
    DUNGEON_GENERATOR,
    WORLD_MAP_MANAGER,
    WORLD_MAP_MANAGER_DRAFT,
]

# 按 Agent 类型映射
TEMPLATES_BY_TYPE = {
    AgentType.SUMMARIZER: DIRECTOR_SUMMARIZER,
    AgentType.MASTER_PLOTTER: DIRECTOR_MASTER_PLOTTER,
    AgentType.HOOK_MANAGER: DIRECTOR_HOOK_MANAGER,
    AgentType.WRITER: DIRECTOR_WRITER,
    AgentType.EVALUATOR: EVALUATOR,
    AgentType.PROC_GEN: PROC_GEN,
    AgentType.SETTING: SETTING,
    AgentType.CHARACTER: CHARACTER,
    AgentType.SCENE_COORDINATOR: SCENE_COORDINATOR,
    AgentType.EVENT_GENERATOR: EVENT_GENERATOR,
    AgentType.DUNGEON_GENERATOR: DUNGEON_GENERATOR,
    AgentType.WORLD_MAP_MANAGER: WORLD_MAP_MANAGER,
    AgentType.PLOT_OUTLINE: PLOT_OUTLINE,
}

# 核心 Agent 列表（不可关闭）
CORE_AGENT_TYPES = [
    AgentType.SETTING,
    AgentType.WRITER,
    AgentType.MASTER_PLOTTER,
    AgentType.SUMMARIZER,
    AgentType.EVALUATOR,
    AgentType.HOOK_MANAGER,
    AgentType.EVENT_GENERATOR,
    AgentType.WORLD_MAP_MANAGER,
    AgentType.SCENE_COORDINATOR,
    AgentType.PLOT_OUTLINE,
]

# 可选 Agent 列表（可按需启用）
OPTIONAL_AGENT_TYPES = [
    AgentType.DUNGEON_GENERATOR,
    AgentType.PROC_GEN,
]