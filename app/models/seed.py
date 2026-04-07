"""
项目种子数据模型
GodView v4 新增：存储结构化项目种子，用于自动创建世界和角色
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class SeedType(str, Enum):
    """种子类型"""

    INITIAL = "initial"  # 初始种子（提取的）
    CONFIRMED = "confirmed"  # 已确认种子（用户确认的）
    BOOTSTRAPPED = "bootstrapped"  # 已引导种子（已创建实体的）


class CharacterCandidate(BaseModel):
    """角色候选模型

    从大纲和设定对话中提取的角色信息
    """

    name: str = Field(..., description="角色名")
    role: str = Field(default="supporting", description="角色类型：main/supporting/npc")
    description: str = Field(..., description="角色描述")
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0, description="重要性评分")
    traits: List[str] = Field(default_factory=list, description="性格特质")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="关系列表")
    background_story: Optional[str] = Field(None, description="背景故事")
    appearance: Optional[str] = Field(None, description="外貌描述")
    goals: List[str] = Field(default_factory=list, description="目标列表")
    inventory: List[str] = Field(default_factory=list, description="物品清单")
    current_location: Optional[str] = Field(None, description="当前位置")
    speech_pattern: Optional[str] = Field(None, description="语音模式")
    lexicon: List[str] = Field(default_factory=list, description="词汇表")
    forbidden_words: List[str] = Field(default_factory=list, description="禁忌词")
    voice_samples: List[str] = Field(default_factory=list, description="语音样本")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="属性字典")


class ProjectSeed(BaseModel):
    """项目种子模型

    包含创建完整项目所需的所有结构化信息
    """

    id: str = Field(..., description="种子ID")
    project_id: str = Field(..., description="项目ID")
    session_id: Optional[str] = Field(None, description="关联的Bootstrap会话ID")

    # 种子元信息
    version: int = Field(default=1, description="种子版本")
    seed_type: SeedType = Field(default=SeedType.INITIAL, description="种子类型")
    status: str = Field(default="draft", description="种子状态")

    # 世界设定
    world_setting: Dict[str, Any] = Field(
        default_factory=dict,
        description="世界设定字典，包含名称、描述、类型、基调等"
    )
    world_rules: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="世界规则列表"
    )
    power_system: Optional[str] = Field(None, description="力量体系")
    technology_level: Optional[str] = Field(None, description="科技水平")
    history: Optional[str] = Field(None, description="世界历史")
    geography: Optional[str] = Field(None, description="世界地理")
    factions: List[Dict[str, Any]] = Field(default_factory=list, description="势力列表")

    # 角色候选
    main_characters: List[CharacterCandidate] = Field(
        default_factory=list,
        description="主要角色候选列表"
    )
    supporting_characters: List[CharacterCandidate] = Field(
        default_factory=list,
        description="配角候选列表"
    )
    npc_characters: List[CharacterCandidate] = Field(
        default_factory=list,
        description="NPC角色候选列表"
    )

    # 区域
    regions: List[Dict[str, Any]] = Field(default_factory=list, description="区域列表")
    landmarks: List[Dict[str, Any]] = Field(default_factory=list, description="地标列表")

    # 情节线索
    plot_hooks: List[Dict[str, Any]] = Field(default_factory=list, description="情节线索列表")
    story_arcs: List[Dict[str, Any]] = Field(default_factory=list, description="故事线列表")

    # 叙事风格
    narrative_tone: Optional[str] = Field(None, description="叙事基调")
    writing_style: Optional[str] = Field(None, description="写作风格")
    target_audience: Optional[str] = Field(None, description="目标读者群")

    # Agent 配置
    agent_configs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent配置字典"
    )

    # 引导参数
    bootstrap_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="引导配置参数"
    )

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="种子元数据")


class SeedSummary(BaseModel):
    """种子摘要模型（用于列表展示）"""

    id: str = Field(..., description="种子ID")
    project_id: str = Field(..., description="项目ID")
    version: int = Field(..., description="种子版本")
    seed_type: SeedType = Field(..., description="种子类型")
    status: str = Field(..., description="种子状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    character_count: int = Field(default=0, description="角色数量")
    region_count: int = Field(default=0, description="区域数量")
    hook_count: int = Field(default=0, description="伏笔数量")


class SeedCreationRequest(BaseModel):
    """种子创建请求"""

    project_id: str = Field(..., description="项目ID")
    session_id: str = Field(..., description="Bootstrap会话ID")
    seed_data: Dict[str, Any] = Field(..., description="种子数据")
    seed_type: SeedType = Field(default=SeedType.INITIAL, description="种子类型")


class SeedUpdateRequest(BaseModel):
    """种子更新请求"""

    seed_data: Dict[str, Any] = Field(..., description="种子数据")
    version_increment: bool = Field(default=True, description="是否增加版本号")
    update_type: SeedType = Field(default=SeedType.CONFIRMED, description="更新类型")


class SeedPromotionRequest(BaseModel):
    """种子晋升请求（用于将候选角色晋升为正式角色）"""

    character_candidate_id: str = Field(..., description="角色候选ID")
    promotion_reason: str = Field(..., description="晋升原因")
    additional_data: Optional[Dict[str, Any]] = Field(None, description="附加数据")