"""
数据模型包
"""

from app.models.character import Character, CharacterStatus, CharacterRole
from app.models.world import World, Region
from app.models.plot import Chapter, Hook, Plot
from app.models.prompt_template import (
    PromptCategory,
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptFilter,
    PromptRenderRequest,
    PromptRenderResult
)
from app.models.agent_template import (
    AgentType,
    PromptSlot,
    AgentTemplate,
    AgentTemplateCreate,
    AgentTemplateUpdate
)
from app.models.agent_config import (
    ConfigOverrideType,
    SlotOverride,
    ModelConfig,
    AgentConfig,
    AgentConfigCreate,
    AgentConfigUpdate
)
from app.models.skill import (
    SkillType,
    SkillStatus,
    SkillParameter,
    Skill,
    SkillAssignment,
    SkillExecutionLog,
    CreateSkillDTO,
    UpdateSkillDTO,
    AssignSkillDTO,
    ExecuteSkillDTO,
    SkillTestResult
)
from app.models.writing_rule import (
    WritingRuleCategory,
    RuleSeverity,
    WritingRule,
    WritingRuleCreate,
    WritingRuleUpdate,
    WritingRuleSet,
    WritingRuleSetCreate,
    WritingRuleSetUpdate,
    ProjectWritingConfig,
    ProjectWritingConfigUpdate
)

__all__ = [
    # Character models
    "Character",
    "CharacterStatus",
    "CharacterRole",
    # World models
    "World",
    "Region",
    # Plot models
    "Chapter",
    "Hook",
    "Plot",
    # Prompt template models
    "PromptCategory",
    "PromptTemplate",
    "PromptTemplateCreate",
    "PromptTemplateUpdate",
    "PromptFilter",
    "PromptRenderRequest",
    "PromptRenderResult",
    # Agent template models
    "AgentType",
    "PromptSlot",
    "AgentTemplate",
    "AgentTemplateCreate",
    "AgentTemplateUpdate",
    # Agent config models
    "ConfigOverrideType",
    "SlotOverride",
    "ModelConfig",
    "AgentConfig",
    "AgentConfigCreate",
    "AgentConfigUpdate",
    # Skill models
    "SkillType",
    "SkillStatus",
    "SkillParameter",
    "Skill",
    "SkillAssignment",
    "SkillExecutionLog",
    "CreateSkillDTO",
    "UpdateSkillDTO",
    "AssignSkillDTO",
    "ExecuteSkillDTO",
    "SkillTestResult",
    # Writing rule models
    "WritingRuleCategory",
    "RuleSeverity",
    "WritingRule",
    "WritingRuleCreate",
    "WritingRuleUpdate",
    "WritingRuleSet",
    "WritingRuleSetCreate",
    "WritingRuleSetUpdate",
    "ProjectWritingConfig",
    "ProjectWritingConfigUpdate"
]
