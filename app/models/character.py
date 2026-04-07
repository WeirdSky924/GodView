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


class CharacterRole(str, Enum):
    """角色类型"""

    MAIN = "main"  # 主角
    SUPPORTING = "supporting"  # 配角
    NPC = "npc"  # NPC
    ANTAGONIST = "antagonist"  # 反派


class PersonalityTrait(BaseModel):
    """性格特质"""

    name: str = Field(..., description="特质名称，如'勇敢'、'谨慎'")
    value: float = Field(..., ge=0, le=1, description="特质强度 0-1")
    description: Optional[str] = Field(None, description="特质描述")


class Character(BaseModel):
    """角色模型"""

    id: str = Field(..., description="角色唯一 ID")
    name: str = Field(..., description="角色名称")

    # 项目归属
    project_id: Optional[str] = Field(None, description="所属项目ID")
    world_id: Optional[str] = Field(None, description="所属世界ID")

    # 基础信息
    description: Optional[str] = Field(None, description="角色描述")
    role: str = Field(default="supporting", description="角色类型：main/supporting/npc")
    status: CharacterStatus = Field(default=CharacterStatus.ACTIVE, description="角色状态")

    # 外观信息
    appearance: Optional[str] = Field(None, description="外貌描述")
    age: Optional[int] = Field(None, description="年龄")
    gender: Optional[str] = Field(None, description="性别")

    # 性格设定
    personality_traits: List[PersonalityTrait] = Field(
        default_factory=list, description="性格特质列表"
    )
    background_story: Optional[str] = Field(None, description="背景故事")

    # 语言风格
    speech_pattern: Optional[str] = Field(None, description="说话风格描述")
    lexicon: List[str] = Field(default_factory=list, description="常用词汇表")
    forbidden_words: List[str] = Field(default_factory=list, description="禁用语")
    voice_samples: List[str] = Field(default_factory=list, description="典型台词样本")

    # 状态属性
    attributes: Dict[str, Any] = Field(default_factory=dict, description="属性面板")
    goals: List[str] = Field(default_factory=list, description="当前目标列表")
    inventory: List[str] = Field(default_factory=list, description="物品清单")

    # 位置信息
    current_location: Optional[str] = Field(None, description="当前位置 ID")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    created_by: str = Field(default="system", description="创建者：system/user")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "char_001",
                "name": "张三",
                "description": "一个初入江湖的年轻侠客",
                "role": "main",
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
                "forbidden_words": ["之乎者也", "斟酌", "考量"],
                "voice_samples": [
                    "路见不平，岂能袖手旁观！",
                    "有话直说，别绕弯子！",
                ],
                "attributes": {"health": 100, "energy": 80, "mood": 60},
                "goals": ["寻找失散的师妹", "提升武功修为"],
                "inventory": ["铁剑", "干粮", "地图"],
                "current_location": "region_001",
            }
        }


class CharacterVoiceSample(BaseModel):
    """角色声音样本（用于向量嵌入）"""

    id: str = Field(..., description="样本 ID")
    character_id: str = Field(..., description="所属角色 ID")
    text: str = Field(..., description="台词文本")
    context: Optional[str] = Field(None, description="台词上下文")
    embedding: Optional[List[float]] = Field(None, description="向量嵌入")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "sample_001",
                "character_id": "char_001",
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
