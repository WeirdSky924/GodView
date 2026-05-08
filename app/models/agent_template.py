"""
Agent 模板模型 - 预定义的 Agent 配置模板

Agent 模板定义了不同类型的 Agent 应包含哪些 Prompt 片段和 Skills，以及它们如何组合。
通过模板可以快速创建项目级别的 Agent 配置。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentType(str, Enum):
    """Agent 类型枚举"""

    CHARACTER = "character"           # 角色 Agent
    SETTING = "setting"               # 设定 Agent
    SUMMARIZER = "summarizer"         # 摘要生成 Agent (Director System)
    MASTER_PLOTTER = "master_plotter" # 总编剧 Agent (Director System)
    PLOTTER = "plotter"               # 编剧 Agent
    HOOK_MANAGER = "hook_manager"     # 伏笔管理 Agent (Director System)
    WRITER = "writer"                 # 作家 Agent (Director System)
    EVALUATOR = "evaluator"           # 评估 Agent
    PROC_GEN = "proc_gen"             # 过程生成 Agent
    SCENE_COORDINATOR = "scene_coordinator"  # 场景协调 Agent (多角色演绎)
    PLOT_OUTLINE = "plot_outline"     # 章节大纲规划 Agent (v9)

    # 新增可选 Agent
    EVENT_GENERATOR = "event_generator"       # 事件生成 Agent
    DUNGEON_GENERATOR = "dungeon_generator"   # 副本生成 Agent
    WORLD_MAP_MANAGER = "world_map_manager"   # 世界地图管理 Agent

    @classmethod
    def director_agents(cls) -> List[str]:
        """获取 Director System 中的 Agent 类型列表"""
        return [
            cls.SUMMARIZER,
            cls.MASTER_PLOTTER,
            cls.PLOTTER,
            cls.HOOK_MANAGER,
            cls.WRITER,
        ]

    @classmethod
    def core_agents(cls) -> List[str]:
        """获取核心 Agent 类型列表（不可关闭）"""
        return [
            cls.SETTING,
            cls.WRITER,
            cls.MASTER_PLOTTER,
            cls.PLOTTER,
            cls.SUMMARIZER,
            cls.EVALUATOR,
            cls.HOOK_MANAGER,
            cls.EVENT_GENERATOR,
            cls.WORLD_MAP_MANAGER,
            cls.SCENE_COORDINATOR,
            cls.PLOT_OUTLINE,
        ]

    @classmethod
    def optional_agents(cls) -> List[str]:
        """获取可选 Agent 类型列表（可按需启用）"""
        return [
            cls.DUNGEON_GENERATOR,
            cls.PROC_GEN,
        ]


class PromptSlot(BaseModel):
    """Prompt 插槽定义

    定义模板中的一个 Prompt 位置，可以绑定特定的 PromptTemplate。
    支持配置优先级、变量覆盖等。
    """

    slot_name: str = Field(..., description="插槽名称")
    description: str = Field(default="", description="插槽描述")

    # 关联的 PromptTemplate
    prompt_template_id: Optional[str] = Field(None, description="关联的 PromptTemplate ID")
    required: bool = Field(default=False, description="是否为必需插槽")

    # 配置
    priority: int = Field(default=50, description="插槽优先级")
    variable_overrides: Dict[str, Any] = Field(default_factory=dict, description="变量覆盖")
    is_enabled: bool = Field(default=True, description="是否启用此插槽")

    # 约束
    allowed_categories: Optional[List[str]] = Field(None, description="允许的 Prompt 分类")
    min_version: Optional[str] = Field(None, description="最小版本要求")


class SkillSlot(BaseModel):
    """Skill 插槽定义

    定义模板中的一个 Skill 位置，Agent 执行时会加载对应的 Skill。
    """

    slot_name: str = Field(..., description="插槽名称")
    description: str = Field(default="", description="插槽描述")

    # 关联的 Skill
    skill_id: Optional[str] = Field(None, description="绑定的 Skill ID")

    # 配置
    is_enabled: bool = Field(default=True, description="是否启用")
    is_required: bool = Field(default=False, description="是否必需")
    priority: int = Field(default=50, description="执行优先级")

    # 变量覆盖
    variable_overrides: Dict[str, Any] = Field(default_factory=dict, description="变量覆盖")

    # 执行条件
    execution_condition: Optional[str] = Field(
        default=None,
        description="执行条件表达式（如：input.task_type == 'evaluation'）"
    )


class AgentTemplate(BaseModel):
    """Agent 模板模型"""

    id: str = Field(..., description="模板 ID")
    name: str = Field(..., description="模板名称")
    description: str = Field(default="", description="模板描述")

    # 类型定义
    agent_type: AgentType = Field(..., description="Agent 类型")
    scenario: str = Field(default="default", description="Agent 使用场景")
    tags: List[str] = Field(default_factory=list, description="标签")

    # Prompt 配置
    prompt_slots: List[PromptSlot] = Field(default_factory=list, description="Prompt 插槽列表")
    default_prompt_order: List[str] = Field(default_factory=list, description="默认 Prompt 顺序")

    # Skill 配置
    skill_slots: List[SkillSlot] = Field(default_factory=list, description="Skill 插槽列表")
    default_skill_order: List[str] = Field(default_factory=list, description="默认 Skill 执行顺序")

    # 模型配置
    default_model: Optional[str] = Field(default=None, description="默认模型")
    default_temperature: float = Field(default=0.7, description="默认温度")

    # 元数据
    is_system: bool = Field(default=False, description="是否系统内置模板")
    is_optional: bool = Field(default=False, description="是否为可选 Agent（可禁用）")
    is_enabled: bool = Field(default=True, description="是否启用（仅对可选 Agent 有效）")
    version: str = Field(default="1.0.0", description="模板版本")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "director_writer",
                "name": "Director Writer 模板",
                "description": "Director System 中的作家 Agent 模板",
                "agent_type": "writer",
                "scenario": "workflow_chapter_generation",
                "tags": ["director", "writing"],
                "prompt_slots": [
                    {
                        "slot_name": "role_definition",
                        "description": "角色定义",
                        "prompt_template_id": "role_writer",
                        "required": True,
                        "priority": 90
                    }
                ],
                "skill_slots": [
                    {
                        "slot_name": "context",
                        "description": "长篇小说创作意识",
                        "skill_id": "skill_long_novel_awareness",
                        "is_enabled": True,
                        "priority": 100
                    }
                ],
                "default_prompt_order": ["role_definition"],
                "is_system": True
            }
        }
    )


class AgentTemplateCreate(BaseModel):
    """创建 Agent 模板请求"""

    name: str = Field(..., description="模板名称", min_length=1, max_length=200)
    description: str = Field(default="", description="模板描述")
    agent_type: AgentType = Field(..., description="Agent 类型")
    scenario: str = Field(default="default", description="Agent 使用场景")
    tags: List[str] = Field(default_factory=list, description="标签")

    # Prompt 配置
    prompt_slots: List[PromptSlot] = Field(default_factory=list, description="Prompt 插槽列表")
    default_prompt_order: List[str] = Field(default_factory=list, description="默认 Prompt 顺序")

    # Skill 配置
    skill_slots: List[SkillSlot] = Field(default_factory=list, description="Skill 插槽列表")
    default_skill_order: List[str] = Field(default_factory=list, description="默认 Skill 执行顺序")

    # 模型配置
    default_model: Optional[str] = Field(default=None, description="默认模型")
    default_temperature: float = Field(default=0.7, description="默认温度")

    # 元数据
    is_system: bool = Field(default=False, description="是否系统内置模板")
    is_optional: bool = Field(default=False, description="是否为可选 Agent")
    is_enabled: bool = Field(default=True, description="是否启用")


class AgentTemplateUpdate(BaseModel):
    """更新 Agent 模板请求"""

    name: Optional[str] = Field(None, description="模板名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="模板描述")
    agent_type: Optional[AgentType] = Field(None, description="Agent 类型")
    scenario: Optional[str] = Field(None, description="Agent 使用场景")
    tags: Optional[List[str]] = Field(None, description="标签")

    # Prompt 配置
    prompt_slots: Optional[List[PromptSlot]] = Field(None, description="Prompt 插槽列表")
    default_prompt_order: Optional[List[str]] = Field(None, description="默认 Prompt 顺序")

    # Skill 配置
    skill_slots: Optional[List[SkillSlot]] = Field(None, description="Skill 插槽列表")
    default_skill_order: Optional[List[str]] = Field(None, description="默认 Skill 执行顺序")

    # 模型配置
    default_model: Optional[str] = Field(None, description="默认模型")
    default_temperature: Optional[float] = Field(None, description="默认温度")

    # 元数据
    is_optional: Optional[bool] = Field(None, description="是否为可选 Agent")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    version: Optional[str] = Field(None, description="模板版本")