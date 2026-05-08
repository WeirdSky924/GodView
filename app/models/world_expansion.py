"""
世界观层次展开数据模型
GodView v9: 世界观层次展开系统

管理地图升级路线、势力更迭、战力天花板等数据
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class MapLevel(str, Enum):
    """地图等级"""

    NEWBIE_VILLAGE = "newbie_village"     # 新手村
    TOWN = "town"                         # 乡镇
    CITY = "city"                         # 城市
    PROVINCE = "province"                 # 省/大区
    CAPITAL = "capital"                   # 首都/主城
    CONTINENT = "continent"               # 州/大陆
    WORLD = "world"                       # 界/域
    DIMENSION = "dimension"               # 异世界/维度


class ForceStatus(str, Enum):
    """势力状态"""

    RISING = "rising"     # 崛起中
    PEAK = "peak"         # 鼎盛
    DECLINING = "declining" # 衰落中
    EXTINCT = "extinct"   # 已灭亡


class WorldMapLevel(BaseModel):
    """地图升级路线"""

    id: str = Field(default_factory=lambda: f"map_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")

    # 地图信息
    level: MapLevel = Field(..., description="地图等级")
    name: str = Field(..., description="地图名称")
    description: str = Field(default="", description="地图描述")

    # 升级条件
    unlock_requirement: str = Field(default="", description="解锁条件")
    unlock_chapter: Optional[int] = Field(None, description="解锁章节")

    # 战力天花板
    power_ceiling: int = Field(default=0, description="战力天花板")
    power_ceiling_description: str = Field(default="", description="战力天花板说明")

    # 特色元素
    unique_features: List[str] = Field(default_factory=list, description="特色元素")
    npc_types: List[str] = Field(default_factory=list, description="NPC类型")

    # 关联章节
    related_chapters: List[int] = Field(default_factory=list, description="关联章节")

    # 元数据
    is_active: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ForceFaction(BaseModel):
    """势力"""

    id: str = Field(default_factory=lambda: f"force_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")

    # 势力信息
    name: str = Field(..., description="势力名称")
    alias: str = Field(default="", description="势力简称/代号")
    faction_type: str = Field(default="", description="势力类型（宗门/帝国/家族等）")

    # 状态
    status: ForceStatus = Field(default=ForceStatus.RISING, description="势力状态")
    founded_chapter: Optional[int] = Field(None, description="创立章节")
    peak_chapter: Optional[int] = Field(None, description="鼎盛章节")
    decline_chapter: Optional[int] = Field(None, description="衰落章节")
    end_chapter: Optional[int] = Field(None, description="终结章节")

    # 实力
    current_power_level: int = Field(default=0, description="当前实力等级")
    max_power_level: int = Field(default=0, description="巅峰实力等级")

    # 核心成员
    core_members: List[str] = Field(default_factory=list, description="核心成员")

    # 关系
    allies: List[str] = Field(default_factory=list, description="盟友")
    enemies: List[str] = Field(default_factory=list, description="敌人")

    # 目标/动机
    goals: List[str] = Field(default_factory=list, description="目标")
    motivation: str = Field(default="", description="行事动机")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PowerCeiling(BaseModel):
    """战力天花板"""

    id: str = Field(default_factory=lambda: f"power_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")

    # 章节范围
    start_chapter: int = Field(..., description="起始章节")
    end_chapter: Optional[int] = Field(None, description="结束章节（当前章节用NULL）")

    # 战力天花板
    ceiling_level: str = Field(..., description="战力等级名称")
    ceiling_value: int = Field(default=0, description="战力数值")
    description: str = Field(default="", description="说明")

    # 突破条件
    breakthrough_condition: str = Field(default="", description="突破条件")
    breakthrough_hint: str = Field(default="", description="突破提示")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class InformationLevel(BaseModel):
    """信息层级"""

    id: str = Field(default_factory=lambda: f"info_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")

    # 信息
    info_name: str = Field(..., description="信息名称")
    info_type: str = Field(..., description="信息类型")
    description: str = Field(default="", description="信息描述")

    # 揭示时机
    first_hint_chapter: Optional[int] = Field(None, description="首次暗示章节")
    partial_reveal_chapter: Optional[int] = Field(None, description="部分揭示章节")
    full_reveal_chapter: Optional[int] = Field(None, description="完全揭示章节")

    # 揭示方式
    reveal_method: str = Field(default="", description="揭示方式")

    # 重要性
    importance: int = Field(default=5, ge=1, le=10, description="重要性等级")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ==================== DTO 模型 ====================

class CreateWorldMapLevelDTO(BaseModel):
    """创建地图等级请求"""

    project_id: str
    level: MapLevel
    name: str
    description: str = ""
    unlock_requirement: str = ""
    unlock_chapter: Optional[int] = None
    power_ceiling: int = 0
    power_ceiling_description: str = ""
    unique_features: List[str] = Field(default_factory=list)
    npc_types: List[str] = Field(default_factory=list)


class CreateForceFactionDTO(BaseModel):
    """创建势力请求"""

    project_id: str
    name: str
    alias: str = ""
    faction_type: str = ""
    status: ForceStatus = ForceStatus.RISING
    founded_chapter: Optional[int] = None
    current_power_level: int = 0
    max_power_level: int = 0
    core_members: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    motivation: str = ""


class UpdateForceFactionDTO(BaseModel):
    """更新势力请求"""

    name: Optional[str] = None
    alias: Optional[str] = None
    faction_type: Optional[str] = None
    status: Optional[ForceStatus] = None
    current_power_level: Optional[int] = None
    core_members: Optional[List[str]] = None
    allies: Optional[List[str]] = None
    enemies: Optional[List[str]] = None
    goals: Optional[List[str]] = None
    motivation: Optional[str] = None


class CreatePowerCeilingDTO(BaseModel):
    """创建战力天花板请求"""

    project_id: str
    start_chapter: int
    end_chapter: Optional[int] = None
    ceiling_level: str
    ceiling_value: int = 0
    description: str = ""
    breakthrough_condition: str = ""
    breakthrough_hint: str = ""


class CreateInformationLevelDTO(BaseModel):
    """创建信息层级请求"""

    project_id: str
    info_name: str
    info_type: str
    description: str = ""
    first_hint_chapter: Optional[int] = None
    partial_reveal_chapter: Optional[int] = None
    full_reveal_chapter: Optional[int] = None
    reveal_method: str = ""
    importance: int = 5


class WorldExpansionSummary(BaseModel):
    """世界观展开摘要"""

    project_id: str
    map_levels: List[WorldMapLevel]
    forces: List[ForceFaction]
    power_ceilings: List[PowerCeiling]
    information_levels: List[InformationLevel]
    next_expansion_hint: Optional[str] = None