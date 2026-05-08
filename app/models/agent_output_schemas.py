"""Agent 输出契约对应的 Pydantic schema 定义。

集中定义 strict / hybrid 契约对应的 Pydantic schema，供
``StructuredLLMRunner`` 调用 ``with_structured_output(schema)`` 使用。

Schema 通过 ``AgentOutputContract.schema_ref`` 以 dotted-path 字符串引用，避免
在 ``agent_output_contract.py`` 中产生循环 import。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# Evaluator
# ============================================================


class _PacingCheck(BaseModel):
    is_appropriate: bool
    note: str = ""


class _LongTermCheck(BaseModel):
    has_room_for_future: bool
    note: str = ""


class _WorldConsistencyCheck(BaseModel):
    is_consistent: bool
    issues: List[str] = Field(default_factory=list)


class _ChapterEndScores(BaseModel):
    info_gain: float = 0.0
    suspense: float = 0.0
    pacing: float = 0.0
    completeness: float = 0.0
    world_consistency: float = 0.0


class EvaluatorChapterEndSchema(BaseModel):
    """章节结束判定输出。"""

    should_end: bool
    reason: str
    missing_elements: List[str] = Field(default_factory=list)
    suggested_continuation: str = ""
    pacing_check: _PacingCheck
    long_term_check: _LongTermCheck
    world_consistency_check: _WorldConsistencyCheck
    scores: _ChapterEndScores
    quality_passed: bool = False
    score: float = 0.0
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    outline_adherence_check: Dict[str, Any] = Field(default_factory=dict)
    world_rule_check: Dict[str, Any] = Field(default_factory=dict)
    lore_conflict_check: Dict[str, Any] = Field(default_factory=dict)
    character_participation_check: Dict[str, Any] = Field(default_factory=dict)
    word_count_check: Dict[str, Any] = Field(default_factory=dict)
    upstream_context_usage_check: Dict[str, Any] = Field(default_factory=dict)
    asset_persistence_check: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class _ReaderScores(BaseModel):
    opening: float = 0
    pacing: float = 0
    suspense: float = 0
    character: float = 0
    emotion: float = 0
    flow: float = 0
    long_term_appeal: float = 0
    world_immersion: float = 0


class _ReaderDetailedAnalysis(BaseModel):
    opening_analysis: str = ""
    pacing_analysis: str = ""
    character_analysis: str = ""
    world_building_analysis: str = ""


class EvaluatorReaderSimulateSchema(BaseModel):
    """读者模拟评分输出。"""

    scores: _ReaderScores
    overall: float = 0
    comments: str = ""
    detailed_analysis: _ReaderDetailedAnalysis
    suggestions: List[str] = Field(default_factory=list)
    long_term_feedback: str = ""
    world_feedback: str = ""


class EvaluatorOOCSchema(BaseModel):
    """OOC（角色崩坏）审查输出。"""

    is_ooc: bool
    confidence: float = 0.0
    issues: List[str] = Field(default_factory=list)
    suggestion: str = ""


# ============================================================
# Setting Agent — 世界观结构化分析
# ============================================================


class WorldDescriptionAnalysisSchema(BaseModel):
    """对世界观自由文本描述的结构化分析。"""

    power_system: str = ""
    technology_level: str = ""
    history: str = ""
    geography: str = ""


# ============================================================
# World map / ProcGen / Event Generator / Character Agent
# ============================================================

_PERMISSIVE_CONFIG = {"extra": "allow"}


class WorldMapRegionItem(BaseModel):
    """地图概述里的单个区域。"""

    region_name: str = ""
    region_type: str = ""
    description: str = ""
    importance: str = ""

    model_config = _PERMISSIVE_CONFIG


class WorldMapOverviewSchema(BaseModel):
    """`WorldMapManagerAgent._generate_map_overview` 输出。"""

    overview: str = ""
    regions: List[WorldMapRegionItem] = Field(default_factory=list)
    suggested_starting_location: str = ""

    model_config = _PERMISSIVE_CONFIG


class ProcGenRegionSchema(BaseModel):
    """`ProcGenAgent.execute` 生成的区域。"""

    region_id: Optional[str] = None
    region_name: str = ""
    region_type: str = "custom"
    terrain_type: Optional[str] = None
    description: str = ""
    atmosphere: Optional[str] = None
    terrain_features: List[Dict[str, Any]] = Field(default_factory=list)
    landmarks: List[Dict[str, Any]] = Field(default_factory=list)
    encounters: List[Dict[str, Any]] = Field(default_factory=list)
    connections: List[str] = Field(default_factory=list)
    loot: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class ProcGenEncounterSchema(BaseModel):
    """`ProcGenAgent.generate_encounter` 输出。"""

    id: Optional[str] = None
    type: Optional[str] = None
    name: str = ""
    description: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0

    model_config = _PERMISSIVE_CONFIG


class EventGeneratorEventSchema(BaseModel):
    """`EventGeneratorAgent.execute` 生成的事件。"""

    event_id: Optional[str] = None
    event_name: str = ""
    event_type: Optional[str] = None
    description: str = ""
    trigger_condition: Optional[str] = None
    participants: List[str] = Field(default_factory=list)
    consequences: List[str] = Field(default_factory=list)
    narrative_purpose: Optional[str] = None
    suggested_chapter: Optional[Any] = None

    model_config = _PERMISSIVE_CONFIG


class CharacterRelationshipDelta(BaseModel):
    """角色关系变化提案。"""

    target_character: str = ""
    dimension: str = ""
    delta: float = 0.0
    reason: str = ""
    visibility: str = "private"

    model_config = _PERMISSIVE_CONFIG


class CharacterStateDelta(BaseModel):
    """角色状态变化提案。"""

    field: str = ""
    change: str = ""
    persistence: str = "scene_only"
    requires_confirmation: bool = False

    model_config = _PERMISSIVE_CONFIG


class CharacterDecisionSchema(BaseModel):
    """`CharacterAgent.execute` 输出。"""

    dialogue: str = ""
    action: str = ""
    inner_thought: str = ""
    emotion: str = "neutral"
    public_content: str = ""
    private_thought: str = ""
    intent: str = ""
    perceived_facts: List[str] = Field(default_factory=list)
    misinterpretations: List[str] = Field(default_factory=list)
    withheld_information: List[str] = Field(default_factory=list)
    relationship_delta: List[CharacterRelationshipDelta] = Field(default_factory=list)
    state_delta: List[CharacterStateDelta] = Field(default_factory=list)
    continuity_notes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class CharacterLocationUpdateSchema(BaseModel):
    """角色当前地图位置更新。"""

    character_id: Optional[str] = None
    character_name: str = ""
    world_id: Optional[str] = None
    current_region_id: Optional[str] = None
    current_location: Optional[str] = None
    current_location_reason: str = ""

    model_config = _PERMISSIVE_CONFIG


class NarrativeStateChangeOutputSchema(BaseModel):
    """工作流输出中的剧情状态变更提案。"""

    entity_type: str = "custom"
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    change_type: str = "custom"
    title: str = ""
    summary: str = ""
    reason: str = ""
    before_state: Dict[str, Any] = Field(default_factory=dict)
    after_state: Dict[str, Any] = Field(default_factory=dict)
    diff: Dict[str, Any] = Field(default_factory=dict)
    confirmation_required: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = _PERMISSIVE_CONFIG


class SettingWorkflowOutputSchema(BaseModel):
    """设定 Agent 工作流输出。"""

    lores: List[Dict[str, Any]] = Field(default_factory=list)
    characters: List[Dict[str, Any]] = Field(default_factory=list)
    character_location_updates: List[CharacterLocationUpdateSchema] = Field(default_factory=list)
    state_changes: List[NarrativeStateChangeOutputSchema] = Field(default_factory=list)
    hooks: List[Dict[str, Any]] = Field(default_factory=list)
    change_request: Dict[str, Any] = Field(default_factory=dict)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


# ============================================================
# Master plotter / Summarizer / Hook manager
# ============================================================


class _SceneDirections(BaseModel):
    scene_type: str = ""
    main_scene: str = ""
    atmosphere: str = ""
    character_roles: Dict[str, Any] = Field(default_factory=dict)
    plot_focus: str = ""

    model_config = _PERMISSIVE_CONFIG


class MasterPlotterAdvanceSchema(BaseModel):
    """`MasterPlotterAgent.execute` 默认 advance 任务输出。"""

    should_advance: bool = False
    reason: str = ""
    current_progress: float = 0.0
    foreshadow_event: Optional[str] = None
    forced_event: Optional[str] = None
    next_milestone: Optional[str] = None
    pacing_note: Optional[str] = None
    long_term_setup: Optional[str] = None
    scene_directions: Optional[_SceneDirections] = None

    model_config = _PERMISSIVE_CONFIG


class MasterPlotterWritingPlanSchema(BaseModel):
    """章节工作流中总编剧的索引/检查/写作计划输出。"""

    writing_plan: Dict[str, Any] = Field(default_factory=dict)
    plot_guidance: Dict[str, Any] = Field(default_factory=dict)
    scene_integration_plan: Dict[str, Any] = Field(default_factory=dict)
    required_elements_check: Dict[str, Any] = Field(default_factory=dict)
    outline_adherence_notes: List[str] = Field(default_factory=list)
    supporting_character_plan: Dict[str, Any] = Field(default_factory=dict)
    role_delta_resource_requirements: List[Dict[str, Any]] = Field(default_factory=list)
    resource_requirements: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_chapter_outline: Optional[Dict[str, Any]] = None
    suggested_chapter_goals: Optional[List[Any]] = None

    model_config = _PERMISSIVE_CONFIG


class MasterPlotterPlanSchema(BaseModel):
    """`MasterPlotterAgent._execute_plot_planning` 输出。"""

    overall_summary: str = ""
    tone: str = ""
    writing_style: str = ""
    pacing_strategy: str = ""
    chapter_titles: List[str] = Field(default_factory=list)
    chapter_goals: List[Any] = Field(default_factory=list)
    main_conflicts: List[str] = Field(default_factory=list)
    progression_phases: List[Dict[str, Any]] = Field(default_factory=list)
    climax_chapter: Optional[Any] = None
    ending_hint: Optional[str] = None
    world_elements_used: List[str] = Field(default_factory=list)
    long_term_hooks: List[str] = Field(default_factory=list)
    discussion_considerations: List[str] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class _SubtextMarker(BaseModel):
    speaker: str = ""
    implied_meaning: str = ""

    model_config = _PERMISSIVE_CONFIG


class SummarizerSummarySchema(BaseModel):
    """`SummarizerAgent.execute` 默认输出。"""

    summary: str = ""
    subtext_markers: List[_SubtextMarker] = Field(default_factory=list)
    hook_triggers: List[str] = Field(default_factory=list)
    info_gain_score: float = 0.0
    raw_dialogue_refs: List[str] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class SummarizerSettingConfirmSchema(BaseModel):
    """无章节内容时的设定确认输出。"""

    status: str = "confirmed"
    world_name: str = ""
    key_settings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    consistency_check: str = ""

    model_config = _PERMISSIVE_CONFIG


class _SummarizerIssue(BaseModel):
    type: str = ""
    description: str = ""
    location: str = ""
    suggestion: str = ""

    model_config = _PERMISSIVE_CONFIG


class SummarizerSettingCheckSchema(BaseModel):
    """有章节内容时的世界观一致性检查输出。"""

    consistency_status: str = ""
    world_name: str = ""
    checked_items: List[str] = Field(default_factory=list)
    issues: List[_SummarizerIssue] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    lore_expansion_suggestions: List[str] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class _HookToPlant(BaseModel):
    title: str = ""
    description: str = ""
    hook_type: str = ""
    resolution_hint: str = ""
    priority: int = 5
    related_characters: List[str] = Field(default_factory=list)
    related_objects: List[str] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class _HookToResolve(BaseModel):
    id: str = ""
    resolution_context: str = ""

    model_config = _PERMISSIVE_CONFIG


class _HookStatusUpdate(BaseModel):
    id: str = ""
    new_status: str = ""
    reason: str = ""

    model_config = _PERMISSIVE_CONFIG


class HookManagerDecisionSchema(BaseModel):
    """`HookManagerAgent.execute` 输出。"""

    reasoning: str = ""
    hooks_to_plant: List[_HookToPlant] = Field(default_factory=list)
    hooks_to_resolve: List[_HookToResolve] = Field(default_factory=list)
    hooks_status_updates: List[_HookStatusUpdate] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class HookPlantSuggestionSchema(BaseModel):
    """`HookManagerAgent.suggest_hook_planting` 输出。"""

    method: str = ""
    context: str = ""
    dialogue_hint: str = ""
    attention_level: str = "medium"

    model_config = _PERMISSIVE_CONFIG


class HookResolutionSuggestionSchema(BaseModel):
    """`HookManagerAgent.suggest_hook_resolution` 输出。"""

    resolution: str = ""
    emotional_impact: str = "medium"
    ties_to_other_hooks: List[str] = Field(default_factory=list)
    suggested_dialogue: str = ""

    model_config = _PERMISSIVE_CONFIG


# ============================================================
# Writer (hybrid) 正文 + 元数据
# ============================================================


class _WriterStyleCheck(BaseModel):
    action_ratio: float = 0.0
    expression_ratio: float = 0.0
    dialogue_ratio: float = 0.0

    model_config = _PERMISSIVE_CONFIG


class WriterChapterSchema(BaseModel):
    """`WriterAgent._execute_single` 主正文输出。"""

    content: str = ""
    word_count: int = 0
    style_check: Optional[_WriterStyleCheck] = None
    climax_points: List[str] = Field(default_factory=list)
    hooks_embedded: List[str] = Field(default_factory=list)
    future_setup: List[str] = Field(default_factory=list)
    character_candidates: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class WriterContinueSchema(BaseModel):
    """续写输出。"""

    content: str = ""
    word_count: int = 0
    continue_direction: str = ""

    model_config = _PERMISSIVE_CONFIG


class WriterSegmentSchema(BaseModel):
    """分段写作段落输出。"""

    content: str = ""
    word_count: int = 0
    key_points_covered: List[str] = Field(default_factory=list)
    transition_to_next: str = ""

    model_config = _PERMISSIVE_CONFIG


class WriterSupplementSchema(BaseModel):
    """补充内容输出。"""

    content: str = ""
    word_count: int = 0
    supplement_direction: str = ""

    model_config = _PERMISSIVE_CONFIG


class _WriterSegmentInfo(BaseModel):
    focus: str = ""
    key_elements: List[str] = Field(default_factory=list)
    tone: str = ""
    suggested_word_count: Optional[int] = None

    model_config = _PERMISSIVE_CONFIG


class WriterSegmentPlanSchema(BaseModel):
    """分段规划输出。"""

    segments: List[_WriterSegmentInfo] = Field(default_factory=list)
    overall_structure: str = ""
    pacing_note: str = ""

    model_config = _PERMISSIVE_CONFIG


class WriterStyleConsistencySchema(BaseModel):
    """风格一致性检查输出。"""

    is_consistent: bool = True
    confidence: float = 0.5
    differences: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class _WriterSensoryElements(BaseModel):
    visual: str = ""
    auditory: str = ""
    olfactory: str = ""
    tactile: str = ""

    model_config = _PERMISSIVE_CONFIG


class WriterSceneDescriptionSchema(BaseModel):
    """场景描写输出。"""

    description: str = ""
    word_count: int = 0
    sensory_elements: Optional[_WriterSensoryElements] = None

    model_config = _PERMISSIVE_CONFIG


class WriterCharacterVoiceRewriteSchema(BaseModel):
    """角色声音改写输出。"""

    rewritten_text: str = ""
    changes_made: List[str] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


# ============================================================
# Setting Agent Service — 对话抽取 / 建议 / bootstrap seed
# ============================================================


class _SettingLoreItem(BaseModel):
    title: str = ""
    category: str = "custom"
    priority: str = "standard"
    content: str = ""
    summary: str = ""
    keywords: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    related_characters: List[str] = Field(default_factory=list)
    related_locations: List[str] = Field(default_factory=list)
    related_items: List[str] = Field(default_factory=list)
    related_factions: List[str] = Field(default_factory=list)
    depends_on_lore: List[str] = Field(default_factory=list)
    supports_lore: List[str] = Field(default_factory=list)
    potential_conflicts: List[str] = Field(default_factory=list)
    usage_guidance: str = ""
    resource_requirements: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class SettingPendingLoresExtractionSchema(BaseModel):
    """对话中提取的待确认设定列表。"""

    lores: List[_SettingLoreItem] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class _SettingHookItem(BaseModel):
    title: str = ""
    description: str = ""
    hook_type: Optional[str] = None
    status: Optional[str] = "planted"
    related_characters: List[str] = Field(default_factory=list)
    related_locations: List[str] = Field(default_factory=list)
    related_objects: List[str] = Field(default_factory=list)
    plant_context: str = ""
    resolution_hint: str = ""
    priority: Optional[Any] = None

    model_config = _PERMISSIVE_CONFIG


class SettingPendingHooksExtractionSchema(BaseModel):
    """对话中提取的待确认伏笔列表。"""

    hooks: List[_SettingHookItem] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class _SettingSuggestionItem(BaseModel):
    type: str = ""
    target_lore_id: Optional[str] = None
    target_lore_title: str = ""
    issue: str = ""
    suggestion: str = ""
    suggested_content: Optional[str] = None
    priority: str = "medium"
    reason: str = ""

    model_config = _PERMISSIVE_CONFIG


class SettingImprovementSuggestionsSchema(BaseModel):
    """设定改进建议列表。"""

    suggestions: List[_SettingSuggestionItem] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class _SettingCharacterItem(BaseModel):
    name: str = ""
    importance_tier: str = "npc"
    description: str = ""
    appearance: str = ""
    personality: str = ""
    background_story: str = ""
    speech_pattern: str = ""
    age: Optional[Any] = None
    gender: str = ""
    goals: Optional[Any] = None
    relationships: Optional[Any] = None
    key_relationships: Optional[Any] = None
    lexicon: Optional[Any] = None
    forbidden_words: Optional[Any] = None
    voice_samples: Optional[Any] = None
    attributes: Optional[Any] = None
    inventory: Optional[Any] = None
    narrative_weight: Optional[Any] = None
    story_arc_role: Optional[Any] = None
    plot_priority: Optional[Any] = None

    model_config = _PERMISSIVE_CONFIG


class SettingPendingCharactersExtractionSchema(BaseModel):
    """对话中提取的待确认角色列表。"""

    characters: List[_SettingCharacterItem] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class SettingPersonalityGenerationSchema(BaseModel):
    """角色性格生成输出。"""

    appearance: str = ""
    personality: str = ""
    speech_pattern: str = ""
    personality_traits: List[str] = Field(default_factory=list)
    agent_goals: List[Any] = Field(default_factory=list)
    agent_memory: List[Any] = Field(default_factory=list)

    model_config = _PERMISSIVE_CONFIG


class _BootstrapWorldSetting(BaseModel):
    name: str = ""
    description: str = ""
    world_type: str = ""
    tone: str = ""

    model_config = _PERMISSIVE_CONFIG


class BootstrapSeedExtractionSchema(BaseModel):
    """Bootstrap 种子抽取输出。"""

    world_setting: _BootstrapWorldSetting = Field(default_factory=_BootstrapWorldSetting)
    world_rules: List[Any] = Field(default_factory=list)
    power_system: str = ""
    main_characters: List[Any] = Field(default_factory=list)
    regions: List[Any] = Field(default_factory=list)
    plot_hooks: List[Any] = Field(default_factory=list)
    narrative_tone: str = ""

    model_config = _PERMISSIVE_CONFIG


# ============================================================
# 公共注册表（dotted-path 字符串 → schema 类）
# ============================================================


SCHEMA_DOTTED_PATHS: Dict[str, str] = {
    "evaluator.chapter_end": "app.models.agent_output_schemas.EvaluatorChapterEndSchema",
    "evaluator.reader_simulate": "app.models.agent_output_schemas.EvaluatorReaderSimulateSchema",
    "evaluator.ooc": "app.models.agent_output_schemas.EvaluatorOOCSchema",
    "setting.world_description_analysis": "app.models.agent_output_schemas.WorldDescriptionAnalysisSchema",
}


__all__ = [
    "EvaluatorChapterEndSchema",
    "EvaluatorReaderSimulateSchema",
    "EvaluatorOOCSchema",
    "WorldDescriptionAnalysisSchema",
    "SettingPendingLoresExtractionSchema",
    "SettingPendingHooksExtractionSchema",
    "SettingImprovementSuggestionsSchema",
    "SettingPendingCharactersExtractionSchema",
    "SettingPersonalityGenerationSchema",
    "BootstrapSeedExtractionSchema",
    "SCHEMA_DOTTED_PATHS",
]
