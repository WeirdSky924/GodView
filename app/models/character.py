"""
角色数据模型
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CharacterStatus(str, Enum):
    """角色状态"""

    ACTIVE = "active"  # 活跃
    INACTIVE = "inactive"  # 不活跃
    DEAD = "dead"  # 死亡
    PAUSED = "paused"  # 暂停（用户干预）
    GHOST = "ghost"  # 幽灵/灵魂形态
    RESURRECTED = "resurrected"  # 复活


class CharacterPresence(str, Enum):
    """角色在场形式"""

    PRESENT = "present"  # 正常在场
    MEMORY = "memory"  # 回忆中出现
    FLASHBACK = "flashback"  # 闪回/前传
    ALTERNATE_TIMELINE = "alternate_timeline"  # 平行时间线
    SPIRIT = "spirit"  # 灵魂/幽灵
    CORPSE = "corpse"  # 尸体
    MENTIONED = "mentioned"  # 被提及


class DeathDetail(BaseModel):
    """死亡详情"""

    death_chapter: Optional[str] = Field(None, description="死亡章节")
    death_scene: Optional[str] = Field(None, description="死亡场景描述")
    cause: Optional[str] = Field(None, description="死因")
    witnesses: List[str] = Field(default_factory=list, description="目击者")
    is_confirmed: bool = Field(default=True, description="是否确认死亡")
    resurrection_possible: bool = Field(default=False, description="是否可能复活")
    resurrection_conditions: Optional[str] = Field(None, description="复活条件")


class CharacterRole(str, Enum):
    """角色类型（基础分类）"""

    MAIN = "main"  # 主角
    SUPPORTING = "supporting"  # 配角
    NPC = "npc"  # NPC
    ANTAGONIST = "antagonist"  # 反派


class CharacterImportanceTier(str, Enum):
    """
    角色重要性层级 - 决定角色在剧情中的权重和关注度

    层级越高，Agent 在生成剧情时越优先考虑该角色的：
    - 行动和决策
    - 情感和心理变化
    - 与剧情主线的关联
    - 出场频率和重要性
    """

    # ========== 主角层 (Tier 1) ==========
    PROTAGONIST = "protagonist"  # 主角 - 故事核心，所有剧情围绕其展开
    CO_PROTAGONIST = "co_protagonist"  # 双主角/共同主角 - 与主角同等重要

    # ========== 核心配角层 (Tier 2) ==========
    DEUTERAGONIST = "deuteragonist"  # 第二主角 - 重要性仅次于主角，贯穿全文
    MENTOR = "mentor"  # 导师/引路人 - 指导主角成长的关键人物
    LOVE_INTEREST = "love_interest"  # 恋爱对象 - 主角的感情线核心
    BEST_FRIEND = "best_friend"  # 挚友/跟班 - 主角最亲密的伙伴
    ARCHENEMY = "archenemy"  # 宿敌/主要反派 - 贯穿全文的反派BOSS

    # ========== 重要配角层 (Tier 3) ==========
    MAJOR_ALLY = "major_ally"  # 重要盟友 - 有独立剧情线的正派角色
    MAJOR_ANTAGONIST = "major_antagonist"  # 重要反派 - 阶段性BOSS或重要反派
    RIVAL = "rival"  # 竞争对手 - 与主角存在竞争关系
    FAMILY_MEMBER = "family_member"  # 家人 - 主角的重要家庭成员
    GUARDIAN = "guardian"  # 守护者 - 保护主角的角色

    # ========== 阶段性角色层 (Tier 4) ==========
    ARC_ANtagonist = "arc_antagonist"  # 篇章反派 - 特定篇章的反派
    ARC_ALLY = "arc_ally"  # 篇章盟友 - 特定篇章的盟友
    RECURRING = "recurring"  # 常驻配角 - 多次出现但非核心
    CATALYST = "catalyst"  # 催化剂角色 - 推动剧情转折的人物
    MYSTERY_FIGURE = "mystery_figure"  # 神秘人物 - 身份不明的重要角色

    # ========== 功能性角色层 (Tier 5) ==========
    MINION = "minion"  # 爪牙/手下 - 反派的跟班
    INFORMANT = "informant"  # 消息提供者 - 提供情报的角色
    MENTOR_FIGURE = "mentor_figure"  # 指导型NPC - 提供指导但非核心
    COMIC_RELIEF = "comic_relief"  # 喜剧担当 - 活跃气氛的角色
    VICTIM = "victim"  # 受害者 - 被救助或被害的角色

    # ========== 背景层 (Tier 6) ==========
    NPC = "npc"  # 普通NPC - 路人、店主、村民等
    BACKGROUND = "background"  # 背景人物 - 无名字的群众
    CAMEO = "cameo"  # 客串 - 短暂出现的角色


class NarrativeWeight(str, Enum):
    """
    叙事权重 - 决定角色在场景中的描写详细程度
    """

    FULL_FOCUS = "full_focus"  # 完全聚焦 - 详细描写心理、动作、对话
    MAJOR_FOCUS = "major_focus"  # 主要关注 - 详细描写动作和对话
    MODERATE = "moderate"  # 中等关注 - 主要描写对话和关键动作
    MINIMAL = "minimal"  # 最小关注 - 仅描写必要行为
    BACKGROUND = "background"  # 背景处理 - 简单提及或作为环境


class StoryArcRole(str, Enum):
    """
    角色在故事线中的作用类型
    """

    # 正面作用
    HERO = "hero"  # 英雄 - 拯救者
    GUIDE = "guide"  # 引导者 - 指引方向
    HELPER = "helper"  # 帮助者 - 提供援助
    PROTECTOR = "protector"  # 保护者 - 守护他人
    MENTOR_ROLE = "mentor_role"  # 导师 - 传授知识

    # 反面作用
    VILLAIN = "villain"  # 反派 - 主要敌对者
    OBSTACLE = "obstacle"  # 阻碍 - 制造困难
    BETRAYER = "betrayer"  # 叛徒 - 背叛者
    CORRUPTOR = "corruptor"  # 堕落者 - 诱惑他人堕落

    # 中性作用
    NEUTRAL = "neutral"  # 中立 - 不偏不倚
    WILD_CARD = "wild_card"  # 变数 - 立场不明确
    DOUBLE_AGENT = "double_agent"  # 双面间谍 - 同时为两方工作

    # 特殊作用
    SACRIFICE = "sacrifice"  # 牺牲者 - 为他人牺牲
    REDEEMED = "redeemed"  # 救赎者 - 从反派转为正派
    TRAGIC = "tragic"  # 悲剧角色 - 命运悲惨
    HERALD = "herald"  # 先驱 - 带来变化的消息


# 角色层级与叙事权重、剧情优先级的默认映射
TIER_DEFAULTS = {
    # Tier 1: 主角层
    CharacterImportanceTier.PROTAGONIST: {
        "narrative_weight": NarrativeWeight.FULL_FOCUS,
        "plot_priority": 10,
        "min_scenes_per_chapter": 3,
        "description": "故事的核心，所有主线剧情围绕其展开",
    },
    CharacterImportanceTier.CO_PROTAGONIST: {
        "narrative_weight": NarrativeWeight.FULL_FOCUS,
        "plot_priority": 9,
        "min_scenes_per_chapter": 3,
        "description": "与主角同等重要，拥有独立的故事线",
    },
    # Tier 2: 核心配角层
    CharacterImportanceTier.DEUTERAGONIST: {
        "narrative_weight": NarrativeWeight.MAJOR_FOCUS,
        "plot_priority": 8,
        "min_scenes_per_chapter": 2,
        "description": "第二主角，贯穿全文，有完整的人物弧光",
    },
    CharacterImportanceTier.MENTOR: {
        "narrative_weight": NarrativeWeight.MAJOR_FOCUS,
        "plot_priority": 7,
        "min_scenes_per_chapter": 1,
        "description": "主角的导师，关键剧情节点出现",
    },
    CharacterImportanceTier.LOVE_INTEREST: {
        "narrative_weight": NarrativeWeight.MAJOR_FOCUS,
        "plot_priority": 7,
        "min_scenes_per_chapter": 2,
        "description": "主角的恋爱对象，感情线核心",
    },
    CharacterImportanceTier.BEST_FRIEND: {
        "narrative_weight": NarrativeWeight.MAJOR_FOCUS,
        "plot_priority": 7,
        "min_scenes_per_chapter": 2,
        "description": "主角的挚友，经常陪伴在侧",
    },
    CharacterImportanceTier.ARCHENEMY: {
        "narrative_weight": NarrativeWeight.MAJOR_FOCUS,
        "plot_priority": 8,
        "min_scenes_per_chapter": 1,
        "description": "主要反派，主角的宿敌，贯穿全文",
    },
    # Tier 3: 重要配角层
    CharacterImportanceTier.MAJOR_ALLY: {
        "narrative_weight": NarrativeWeight.MODERATE,
        "plot_priority": 5,
        "min_scenes_per_chapter": 1,
        "description": "重要盟友，有独立剧情线",
    },
    CharacterImportanceTier.MAJOR_ANTAGONIST: {
        "narrative_weight": NarrativeWeight.MODERATE,
        "plot_priority": 6,
        "min_scenes_per_chapter": 1,
        "description": "重要反派，阶段性BOSS",
    },
    CharacterImportanceTier.RIVAL: {
        "narrative_weight": NarrativeWeight.MODERATE,
        "plot_priority": 5,
        "min_scenes_per_chapter": 1,
        "description": "主角的竞争对手",
    },
    CharacterImportanceTier.FAMILY_MEMBER: {
        "narrative_weight": NarrativeWeight.MODERATE,
        "plot_priority": 4,
        "min_scenes_per_chapter": 0,
        "description": "主角的重要家人",
    },
    CharacterImportanceTier.GUARDIAN: {
        "narrative_weight": NarrativeWeight.MODERATE,
        "plot_priority": 5,
        "min_scenes_per_chapter": 1,
        "description": "保护主角的角色",
    },
    # Tier 4: 阶段性角色层
    CharacterImportanceTier.ARC_ANtagonist: {
        "narrative_weight": NarrativeWeight.MODERATE,
        "plot_priority": 4,
        "min_scenes_per_chapter": 1,
        "description": "特定篇章的反派",
    },
    CharacterImportanceTier.ARC_ALLY: {
        "narrative_weight": NarrativeWeight.MODERATE,
        "plot_priority": 3,
        "min_scenes_per_chapter": 1,
        "description": "特定篇章的盟友",
    },
    CharacterImportanceTier.RECURRING: {
        "narrative_weight": NarrativeWeight.MINIMAL,
        "plot_priority": 2,
        "min_scenes_per_chapter": 0,
        "description": "多次出现的配角",
    },
    CharacterImportanceTier.CATALYST: {
        "narrative_weight": NarrativeWeight.MODERATE,
        "plot_priority": 4,
        "min_scenes_per_chapter": 0,
        "description": "推动剧情转折的角色",
    },
    CharacterImportanceTier.MYSTERY_FIGURE: {
        "narrative_weight": NarrativeWeight.MODERATE,
        "plot_priority": 4,
        "min_scenes_per_chapter": 0,
        "description": "身份不明的神秘角色",
    },
    # Tier 5: 功能性角色层
    CharacterImportanceTier.MINION: {
        "narrative_weight": NarrativeWeight.MINIMAL,
        "plot_priority": 1,
        "min_scenes_per_chapter": 0,
        "description": "反派的爪牙手下",
    },
    CharacterImportanceTier.INFORMANT: {
        "narrative_weight": NarrativeWeight.MINIMAL,
        "plot_priority": 2,
        "min_scenes_per_chapter": 0,
        "description": "提供情报的角色",
    },
    CharacterImportanceTier.MENTOR_FIGURE: {
        "narrative_weight": NarrativeWeight.MINIMAL,
        "plot_priority": 2,
        "min_scenes_per_chapter": 0,
        "description": "一次性指导的NPC",
    },
    CharacterImportanceTier.COMIC_RELIEF: {
        "narrative_weight": NarrativeWeight.MINIMAL,
        "plot_priority": 2,
        "min_scenes_per_chapter": 0,
        "description": "喜剧担当角色",
    },
    CharacterImportanceTier.VICTIM: {
        "narrative_weight": NarrativeWeight.MINIMAL,
        "plot_priority": 2,
        "min_scenes_per_chapter": 0,
        "description": "受害者角色",
    },
    # Tier 6: 背景层
    CharacterImportanceTier.NPC: {
        "narrative_weight": NarrativeWeight.BACKGROUND,
        "plot_priority": 0,
        "min_scenes_per_chapter": 0,
        "description": "普通NPC，路人角色",
    },
    CharacterImportanceTier.BACKGROUND: {
        "narrative_weight": NarrativeWeight.BACKGROUND,
        "plot_priority": 0,
        "min_scenes_per_chapter": 0,
        "description": "无名字的背景人物",
    },
    CharacterImportanceTier.CAMEO: {
        "narrative_weight": NarrativeWeight.BACKGROUND,
        "plot_priority": 0,
        "min_scenes_per_chapter": 0,
        "description": "客串角色",
    },
}


class PersonalityTrait(BaseModel):
    """性格特质"""

    name: str = Field(..., description="特质名称，如'勇敢'、'谨慎'")
    value: float = Field(..., ge=0, le=1, description="特质强度 0-1")
    description: Optional[str] = Field(None, description="特质描述")


class Character(BaseModel):
    """角色模型"""

    id: Optional[str] = Field(None, description="角色唯一 ID（创建时自动生成）")
    name: str = Field(..., description="角色名称")

    # 项目归属
    project_id: Optional[str] = Field(None, description="所属项目ID")
    world_id: Optional[str] = Field(None, description="所属世界ID")

    # 基础信息
    description: Optional[str] = Field(None, description="角色描述")

    # 角色类型（向后兼容，现在从 importance_tier 推导）
    role: Optional[str] = Field(default=None, description="角色类型（已弃用，从 importance_tier 推导）")

    status: CharacterStatus = Field(default=CharacterStatus.ACTIVE, description="角色状态")

    # ========== 角色层级系统（核心分类） ==========
    importance_tier: CharacterImportanceTier = Field(
        default=CharacterImportanceTier.NPC,
        description="角色重要性层级，决定在剧情中的权重"
    )
    narrative_weight: NarrativeWeight = Field(
        default=NarrativeWeight.MINIMAL,
        description="叙事权重，决定描写详细程度"
    )
    story_arc_role: StoryArcRole = Field(
        default=StoryArcRole.NEUTRAL,
        description="角色在故事线中的作用类型"
    )
    plot_priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="剧情优先级 (0-10)，越高越优先考虑"
    )

    # ========== 登场控制 ==========
    debut_chapter: Optional[int] = Field(None, description="首次登场章节号")
    debut_scene: Optional[str] = Field(None, description="首次登场场景描述")
    exit_chapter: Optional[int] = Field(None, description="退场章节号（死亡或离开）")
    exit_reason: Optional[str] = Field(None, description="退场原因")
    active_arc: Optional[str] = Field(None, description="活跃的故事篇章 (如'第一卷', '学院篇')")

    # ========== 角色关系网络 ==========
    relationships: List[str] = Field(
        default_factory=list,
        description="与主角的关系类型列表 (如['mentor', 'ally'])"
    )
    key_relationships: Dict[str, str] = Field(
        default_factory=dict,
        description="关键关系映射 {角色ID: 关系描述}"
    )

    # 外观信息
    appearance: Optional[str] = Field(None, description="外貌描述")
    age: Optional[int] = Field(None, description="年龄")
    gender: Optional[str] = Field(None, description="性别")

    # 性格设定
    personality: Optional[str] = Field(None, description="性格特点描述")
    personality_traits: List[PersonalityTrait] = Field(
        default_factory=list, description="性格特质列表"
    )
    background_story: Optional[str] = Field(None, alias="background", description="背景故事")

    class Config:
        populate_by_name = True  # 允许通过别名填充

    # 语言风格
    speech_pattern: Optional[str] = Field(None, description="说话风格描述")
    lexicon: List[str] = Field(default_factory=list, description="常用词汇表")
    forbidden_words: List[str] = Field(default_factory=list, description="禁用语")
    voice_samples: List[str] = Field(default_factory=list, description="典型台词样本")

    # Agent 配置（角色专属 Agent）
    has_agent: bool = Field(default=False, description="是否启用角色 Agent")
    agent_enabled: bool = Field(default=True, description="Agent 是否激活")
    agent_goals: List[str] = Field(default_factory=list, description="Agent 当前目标")
    agent_memory: List[str] = Field(default_factory=list, description="Agent 记忆要点")

    # 状态属性
    attributes: Dict[str, Any] = Field(default_factory=dict, description="属性面板")
    goals: List[str] = Field(default_factory=list, description="当前目标列表")
    inventory: List[str] = Field(default_factory=list, description="物品清单")

    # 位置信息
    current_location: Optional[str] = Field(None, description="当前位置 ID")

    # 死亡相关
    death_detail: Optional[DeathDetail] = Field(None, description="死亡详情（仅死亡状态时有效）")
    available_presence_types: List[CharacterPresence] = Field(
        default_factory=lambda: [CharacterPresence.PRESENT],
        description="角色可出现的在场形式"
    )

    # ========== 剧情参与统计 ==========
    total_scenes: int = Field(default=0, description="总出场场景数")
    dialogue_count: int = Field(default=0, description="对话次数")
    major_events: List[str] = Field(default_factory=list, description="参与的重大事件")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    created_by: str = Field(default="system", description="创建者：system/user")

    def get_tier_info(self) -> Dict[str, Any]:
        """获取角色层级信息"""
        return TIER_DEFAULTS.get(self.importance_tier, TIER_DEFAULTS[CharacterImportanceTier.NPC])

    def get_derived_role(self) -> str:
        """
        从 importance_tier 推导角色类型（向后兼容）

        Returns:
            str: 角色类型 (main/antagonist/supporting/npc)
        """
        # 主角层
        if self.importance_tier in [
            CharacterImportanceTier.PROTAGONIST,
            CharacterImportanceTier.CO_PROTAGONIST,
            CharacterImportanceTier.DEUTERAGONIST,
        ]:
            return "main"

        # 反派
        if self.importance_tier in [
            CharacterImportanceTier.ARCHENEMY,
            CharacterImportanceTier.MAJOR_ANTAGONIST,
            CharacterImportanceTier.ARC_ANtagonist,
        ]:
            return "antagonist"

        # NPC / 背景
        if self.importance_tier in [
            CharacterImportanceTier.NPC,
            CharacterImportanceTier.BACKGROUND,
            CharacterImportanceTier.CAMEO,
            CharacterImportanceTier.MINION,
        ]:
            return "npc"

        # 其他都是配角
        return "supporting"

    def is_protagonist(self) -> bool:
        """是否是主角层角色"""
        return self.importance_tier in [
            CharacterImportanceTier.PROTAGONIST,
            CharacterImportanceTier.CO_PROTAGONIST,
        ]

    def is_core_character(self) -> bool:
        """是否是核心角色（Tier 1-2）"""
        return self.importance_tier in [
            CharacterImportanceTier.PROTAGONIST,
            CharacterImportanceTier.CO_PROTAGONIST,
            CharacterImportanceTier.DEUTERAGONIST,
            CharacterImportanceTier.MENTOR,
            CharacterImportanceTier.LOVE_INTEREST,
            CharacterImportanceTier.BEST_FRIEND,
            CharacterImportanceTier.ARCHENEMY,
        ]

    def is_antagonist(self) -> bool:
        """是否是反派角色"""
        return self.importance_tier in [
            CharacterImportanceTier.ARCHENEMY,
            CharacterImportanceTier.MAJOR_ANTAGONIST,
            CharacterImportanceTier.ARC_ANtagonist,
            CharacterImportanceTier.MINION,
        ] or self.story_arc_role in [
            StoryArcRole.VILLAIN,
            StoryArcRole.OBSTACLE,
            StoryArcRole.BETRAYER,
            StoryArcRole.CORRUPTOR,
        ]

    def get_narrative_focus_instruction(self) -> str:
        """获取叙事焦点指令（供 Agent 参考）"""
        tier_info = self.get_tier_info()
        weight_instructions = {
            NarrativeWeight.FULL_FOCUS: "需要详细描写角色的心理活动、微表情、动作细节，每个决策都要展现内心挣扎",
            NarrativeWeight.MAJOR_FOCUS: "需要详细描写角色的对话和关键动作，适当展现心理活动",
            NarrativeWeight.MODERATE: "主要描写角色的对话和行动，简单带过心理活动",
            NarrativeWeight.MINIMAL: "简单描写角色的必要行为，不需要深入刻画",
            NarrativeWeight.BACKGROUND: "作为背景人物简单提及即可",
        }
        return weight_instructions.get(self.narrative_weight, "")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "char_001",
                "name": "张三",
                "description": "一个初入江湖的年轻侠客",
                "role": "main",
                "importance_tier": "protagonist",
                "narrative_weight": "full_focus",
                "story_arc_role": "hero",
                "plot_priority": 10,
                "status": "active",
                "appearance": "身穿青衫，眉目清秀",
                "age": 20,
                "gender": "男",
                "personality_traits": [
                    {"name": "正直", "value": 0.9, "description": "为人正直，见不得欺压弱小"},
                    {"name": "冲动", "value": 0.7, "description": "容易冲动行事"},
                ],
                "background_story": "出身普通农家，因偶然机会得到一本武功秘籍",
                "speech_pattern": "说话直接，不喜欢拐弯抹角",
                "lexicon": ["江湖", "武功", "义气"],
                "relationships": ["protagonist"],
                "key_relationships": {"char_002": "师妹", "char_003": "宿敌"},
            }
        }


class CharacterVoiceSample(BaseModel):
    """角色声音样本（用于向量嵌入）"""

    id: str = Field(..., description="样本 ID")
    character_id: str = Field(..., description="所属角色 ID")
    project_id: Optional[str] = Field(None, description="所属项目 ID")
    text: str = Field(..., description="台词文本")
    context: Optional[str] = Field(None, description="台词上下文")
    embedding: Optional[List[float]] = Field(None, description="向量嵌入")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "sample_001",
                "character_id": "char_001",
                "project_id": "proj_001",
                "text": "路见不平，岂能袖手旁观！",
                "context": "看到恶霸欺负老人时所说",
            }
        }


class RelationshipType(str, Enum):
    """关系类型"""

    FRIEND = "friend"  # 朋友
    ENEMY = "enemy"  # 敌人
    LOVER = "lover"  # 恋人
    FAMILY = "family"  # 家人
    MASTER_APPRENTICE = "master_apprentice"  # 师徒
    COLLEAGUE = "colleague"  # 同僚
    STRANGER = "stranger"  # 陌生人
    CUSTOM = "custom"  # 自定义


class Relationship(BaseModel):
    """角色关系模型"""

    id: str = Field(..., description="关系 ID")
    character_id_1: str = Field(..., description="角色 1 ID")
    character_id_2: str = Field(..., description="角色 2 ID")
    relationship_type: RelationshipType = Field(..., description="关系类型")

    # 关系强度 -1 到 1，-1 为死敌，1 为挚友
    strength: float = Field(default=0, ge=-1, le=1, description="关系强度")

    # 关系描述
    description: Optional[str] = Field(None, description="关系描述")

    # 关系历史（关键事件）
    history: List[str] = Field(default_factory=list, description="关系历史事件")

    # 动态更新
    last_interaction: Optional[datetime] = Field(None, description="最后互动时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "rel_001",
                "character_id_1": "char_001",
                "character_id_2": "char_002",
                "relationship_type": "friend",
                "strength": 0.8,
                "description": "张三和李四是结拜兄弟",
                "history": ["在酒馆相识", "共同对抗敌人", "结拜为兄弟"],
            }
        }
