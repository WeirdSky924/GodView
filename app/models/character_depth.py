"""
角色深度数据模型
GodView v9: 角色深度系统

用于管理角色性格特质、成长弧线、关系网络等
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class PersonalityTrait(BaseModel):
    """性格特质"""

    trait_name: str = Field(..., description="特质名称")
    description: str = Field(..., description="特质描述")
    intensity: float = Field(default=0.5, ge=0, le=1, description="强度")
    manifestation: List[str] = Field(default_factory=list, description="表现形式")


class SpeakingStyle(BaseModel):
    """说话风格"""

    tone: str = Field(default="中性", description="语调")
    vocabulary: List[str] = Field(default_factory=list, description="常用词汇")
    catchphrases: List[str] = Field(default_factory=list, description="口头禅")
    forbidden_words: List[str] = Field(default_factory=list, description="禁用词")
    speaking_patterns: List[str] = Field(default_factory=list, description="说话模式")


class GrowthArcPhase(str, Enum):
    """成长弧线阶段"""

    INTRODUCTION = "introduction"      # 引入期
    DEVELOPMENT = "development"        # 发展期
    TRANSFORMATION = "transformation"  # 转变期
    MATURATION = "maturation"          # 成熟期
    RESOLUTION = "resolution"          # 完结期


class GrowthArc(BaseModel):
    """成长弧线"""

    id: str = Field(default_factory=lambda: f"arc_{uuid.uuid4().hex[:8]}")
    character_id: str = Field(..., description="角色ID")
    project_id: str = Field(..., description="项目ID")

    # 弧线信息
    arc_name: str = Field(..., description="弧线名称")
    arc_description: str = Field(..., description="弧线描述")

    # 阶段
    current_phase: GrowthArcPhase = Field(default=GrowthArcPhase.INTRODUCTION, description="当前阶段")
    phase_progress: Dict[str, float] = Field(default_factory=dict, description="各阶段进度")

    # 关键节点
    milestones: List[Dict[str, Any]] = Field(default_factory=list, description="成长里程碑")
    turning_points: List[Dict[str, Any]] = Field(default_factory=list, description="转折点")

    # 变化记录
    changes: List[Dict[str, Any]] = Field(default_factory=list, description="变化记录")

    # 关联章节
    start_chapter: Optional[int] = Field(None, description="开始章节")
    end_chapter: Optional[int] = Field(None, description="结束章节")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "arc_abc123",
                "character_id": "char_001",
                "project_id": "proj_001",
                "arc_name": "从懦弱到勇敢",
                "arc_description": "主角从害怕承担责任到勇于面对挑战",
                "current_phase": "development",
                "milestones": [
                    {"chapter": 5, "event": "第一次主动承担责任", "change": "勇气+10"}
                ]
            }
        }
    )


class RelationshipType(str, Enum):
    """关系类型"""

    FAMILY = "family"           # 家人
    FRIEND = "friend"           # 朋友
    ENEMY = "enemy"             # 敌人
    RIVAL = "rival"             # 对手
    LOVER = "lover"             # 恋人
    MENTOR = "mentor"           # 导师
    STUDENT = "student"         # 学生
    ALLY = "ally"               # 盟友
    SUBORDINATE = "subordinate" # 下属
    SUPERIOR = "superior"       # 上级
    NEUTRAL = "neutral"         # 中立
    COMPLEX = "complex"         # 复杂


class CharacterRelationship(BaseModel):
    """角色关系"""

    id: str = Field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")

    # 关系双方
    character_a_id: str = Field(..., description="角色A ID")
    character_b_id: str = Field(..., description="角色B ID")

    # 关系类型
    relationship_type: RelationshipType = Field(default=RelationshipType.NEUTRAL, description="关系类型")
    relationship_description: str = Field(default="", description="关系描述")

    # 关系强度 (-1 到 1，负数为敌对，正数为友好)
    strength: float = Field(default=0.0, ge=-1, le=1, description="关系强度")

    # 关系变化历史
    history: List[Dict[str, Any]] = Field(default_factory=list, description="关系变化历史")

    # 关联章节
    established_chapter: Optional[int] = Field(None, description="建立章节")
    last_updated_chapter: Optional[int] = Field(None, description="最后更新章节")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "rel_xyz789",
                "project_id": "proj_001",
                "character_a_id": "char_001",
                "character_b_id": "char_002",
                "relationship_type": "rival",
                "relationship_description": "同门师兄弟，互相竞争",
                "strength": -0.3
            }
        }
    )


class AppearanceRule(BaseModel):
    """出场规则"""

    character_id: str
    project_id: str

    # 出场频率
    min_appearance_interval: int = Field(default=1, description="最小出场间隔（章）")
    max_absence_chapters: int = Field(default=5, description="最大缺席章数")

    # 出场条件
    required_scenes: List[str] = Field(default_factory=list, description="必须出场的场景类型")
    optional_scenes: List[str] = Field(default_factory=list, description="可选出场的场景类型")

    # 出场优先级
    priority: int = Field(default=5, ge=1, le=10, description="出场优先级")

    # 出场历史
    appearance_history: List[int] = Field(default_factory=list, description="出场章节列表")
    last_appearance: Optional[int] = Field(None, description="最后出场章节")

    # 违规警告
    warnings: List[str] = Field(default_factory=list, description="违规警告")


class CharacterDepthProfile(BaseModel):
    """角色深度档案"""

    id: str = Field(default_factory=lambda: f"profile_{uuid.uuid4().hex[:8]}")
    character_id: str = Field(..., description="角色ID")
    project_id: str = Field(..., description="项目ID")

    # 性格特质
    personality_traits: List[PersonalityTrait] = Field(default_factory=list, description="性格特质")

    # 说话风格
    speaking_style: Optional[SpeakingStyle] = Field(None, description="说话风格")

    # 成长弧线
    growth_arcs: List[GrowthArc] = Field(default_factory=list, description="成长弧线")

    # 关系网络
    relationships: List[CharacterRelationship] = Field(default_factory=list, description="角色关系")

    # 出场规则
    appearance_rules: Optional[AppearanceRule] = Field(None, description="出场规则")

    # 背景故事
    backstory: Optional[str] = Field(None, description="背景故事")

    # 内心世界
    inner_world: Dict[str, Any] = Field(default_factory=dict, description="内心世界")

    # 隐藏秘密
    secrets: List[str] = Field(default_factory=list, description="隐藏秘密")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "profile_abc123",
                "character_id": "char_001",
                "project_id": "proj_001",
                "personality_traits": [
                    {"trait_name": "果断", "description": "做事雷厉风行", "intensity": 0.8}
                ],
                "backstory": "出身贫寒，凭借努力成为宗门弟子"
            }
        }
    )


# ==================== DTO 模型 ====================

class CreateCharacterDepthDTO(BaseModel):
    """创建角色深度档案请求"""

    character_id: str
    project_id: str
    personality_traits: List[PersonalityTrait] = Field(default_factory=list)


class UpdateCharacterDepthDTO(BaseModel):
    """更新角色深度档案请求"""

    personality_traits: Optional[List[PersonalityTrait]] = None
    speaking_style: Optional[SpeakingStyle] = None
    backstory: Optional[str] = None
    inner_world: Optional[Dict[str, Any]] = None
    secrets: Optional[List[str]] = None


class CreateGrowthArcDTO(BaseModel):
    """创建成长弧线请求"""

    character_id: str
    project_id: str
    arc_name: str
    arc_description: str
    start_chapter: Optional[int] = None


class UpdateGrowthArcDTO(BaseModel):
    """更新成长弧线请求"""

    current_phase: Optional[GrowthArcPhase] = None
    milestones: Optional[List[Dict[str, Any]]] = None
    turning_points: Optional[List[Dict[str, Any]]] = None


class CreateRelationshipDTO(BaseModel):
    """创建角色关系请求"""

    project_id: str
    character_a_id: str
    character_b_id: str
    relationship_type: RelationshipType
    relationship_description: Optional[str] = None
    strength: float = 0.0


class UpdateRelationshipDTO(BaseModel):
    """更新角色关系请求"""

    relationship_type: Optional[RelationshipType] = None
    relationship_description: Optional[str] = None
    strength: Optional[float] = None
