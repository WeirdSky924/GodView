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
from app.models.chapter_outline import (
    EmotionType,
    SceneType,
    ConflictLevel,
    SceneOutline,
    EmotionPoint,
    EmotionCurve,
    ChapterOutlineStatus,
    ChapterOutline,
    CreateChapterOutlineDTO,
    UpdateChapterOutlineDTO,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    ValidateOutlineRequest,
    ValidateOutlineResponse
)
from app.models.memory import (
    MemoryType,
    MemoryCategory,
    MemoryEntry,
    MemorySnapshot,
    CharacterMemoryState,
    CreateMemoryDTO,
    UpdateMemoryDTO,
    SearchMemoryDTO,
    MemorySearchResult,
    BuildSnapshotDTO,
)
from app.models.character_depth import (
    PersonalityTrait,
    SpeakingStyle,
    GrowthArcPhase,
    GrowthArc,
    RelationshipType,
    CharacterRelationship,
    AppearanceRule,
    CharacterDepthProfile,
    CreateCharacterDepthDTO,
    UpdateCharacterDepthDTO,
    CreateGrowthArcDTO,
    UpdateGrowthArcDTO,
    CreateRelationshipDTO,
    UpdateRelationshipDTO,
)
from app.models.satisfaction import (
    CoolPointType,
    CoolPointIntensity,
    PibuBurstPhase,
    CoolPointDefinition,
    CoolPointInstance,
    PibuBurstDesign,
    SatisfactionAnalysisRecord,
    CreateCoolPointDTO,
    CreatePibuBurstDTO,
    AnalyzeSatisfactionDTO,
    CoolPointSuggestion,
)
from app.models.golden_three import (
    GoldenThreeRuleType,
    RuleSeverity,
    GoldenThreeRule,
    GoldenThreeCheckResult,
    CreateGoldenThreeRuleDTO,
    UpdateGoldenThreeRuleDTO,
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
    "ProjectWritingConfigUpdate",
    # Chapter outline models
    "EmotionType",
    "SceneType",
    "ConflictLevel",
    "SceneOutline",
    "EmotionPoint",
    "EmotionCurve",
    "ChapterOutlineStatus",
    "ChapterOutline",
    "CreateChapterOutlineDTO",
    "UpdateChapterOutlineDTO",
    "GenerateOutlineRequest",
    "GenerateOutlineResponse",
    "ValidateOutlineRequest",
    "ValidateOutlineResponse",
    # Memory models
    "MemoryType",
    "MemoryCategory",
    "MemoryEntry",
    "MemorySnapshot",
    "CharacterMemoryState",
    "CreateMemoryDTO",
    "UpdateMemoryDTO",
    "SearchMemoryDTO",
    "MemorySearchResult",
    "BuildSnapshotDTO",
    # Character depth models
    "PersonalityTrait",
    "SpeakingStyle",
    "GrowthArcPhase",
    "GrowthArc",
    "RelationshipType",
    "CharacterRelationship",
    "AppearanceRule",
    "CharacterDepthProfile",
    "CreateCharacterDepthDTO",
    "UpdateCharacterDepthDTO",
    "CreateGrowthArcDTO",
    "UpdateGrowthArcDTO",
    "CreateRelationshipDTO",
    "UpdateRelationshipDTO",
    # Satisfaction models
    "CoolPointType",
    "CoolPointIntensity",
    "PibuBurstPhase",
    "CoolPointDefinition",
    "CoolPointInstance",
    "PibuBurstDesign",
    "SatisfactionAnalysisRecord",
    "CreateCoolPointDTO",
    "CreatePibuBurstDTO",
    "AnalyzeSatisfactionDTO",
    "CoolPointSuggestion",
    # Golden three models
    "GoldenThreeRuleType",
    "RuleSeverity",
    "GoldenThreeRule",
    "GoldenThreeCheckResult",
    "CreateGoldenThreeRuleDTO",
    "UpdateGoldenThreeRuleDTO",
]
