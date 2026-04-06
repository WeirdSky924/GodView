"""
世界观与区域数据模型
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RegionType(str, Enum):
    """区域类型"""

    CITY = "city"  # 城市
    VILLAGE = "village"  # 村庄
    WILDERNESS = "wilderness"  # 荒野
    DUNGEON = "dungeon"  # 副本/秘境
    BUILDING = "building"  # 建筑
    WATER = "water"  # 水域
    MOUNTAIN = "mountain"  # 山脉
    FOREST = "forest"  # 森林
    CUSTOM = "custom"  # 自定义


class TerrainType(str, Enum):
    """地形类型"""

    PLAIN = "plain"  # 平原
    HILL = "hill"  # 丘陵
    MOUNTAIN = "mountain"  # 山地
    DESERT = "desert"  # 沙漠
    SWAMP = "swamp"  # 沼泽
    ICE = "ice"  # 冰原
    VOLCANO = "volcano"  # 火山
    CUSTOM = "custom"  # 自定义


class WorldRule(BaseModel):
    """世界规则模型"""

    id: str = Field(..., description="规则 ID")
    name: str = Field(..., description="规则名称")
    description: str = Field(..., description="规则描述")
    category: str = Field(default="general", description="规则类别：physics/magic/social/etc")
    priority: int = Field(default=0, description="优先级，数字越大优先级越高")
    is_absolute: bool = Field(default=False, description="是否为绝对规则（不可违反）")
    conditions: Optional[Dict[str, Any]] = Field(None, description="触发条件")
    effects: Optional[Dict[str, Any]] = Field(None, description="规则效果")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "rule_001",
                "name": "重力法则",
                "description": "所有物体都受到向下的重力作用",
                "category": "physics",
                "priority": 10,
                "is_absolute": True,
            }
        }


class World(BaseModel):
    """世界模型"""

    id: str = Field(..., description="世界唯一 ID")
    name: str = Field(..., description="世界名称")

    # 基础设定
    description: Optional[str] = Field(None, description="世界描述")
    world_type: str = Field(default="fantasy", description="世界类型：fantasy/scifi/wuxia/etc")
    tone: str = Field(default="serious", description="故事基调：serious/humorous/dark/etc")

    # 核心法则
    rules: List[WorldRule] = Field(default_factory=list, description="世界规则列表")
    power_system: Optional[str] = Field(None, description="力量体系描述")
    technology_level: Optional[str] = Field(None, description="科技水平")

    # 背景设定
    history: Optional[str] = Field(None, description="世界历史")
    geography: Optional[str] = Field(None, description="地理概况")
    factions: List[Dict[str, Any]] = Field(default_factory=list, description="势力列表")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "world_001",
                "name": "九霄大陆",
                "description": "一个以武为尊的玄幻世界",
                "world_type": "fantasy",
                "tone": "serious",
                "power_system": "修真体系：炼气→筑基→金丹→元婴→化神",
                "technology_level": "古代冷兵器",
            }
        }


class Encounter(BaseModel):
    """遭遇事件模型"""

    id: str = Field(..., description="遭遇 ID")
    type: str = Field(..., description="遭遇类型：monster/npc/event/treasure")
    name: str = Field(..., description="遭遇名称")
    description: str = Field(..., description="遭遇描述")

    # 触发条件
    trigger_conditions: Optional[Dict[str, Any]] = Field(None, description="触发条件")

    # 遭遇内容
    data: Dict[str, Any] = Field(default_factory=dict, description="遭遇详细数据")

    # 概率权重
    weight: float = Field(default=1.0, ge=0, description="出现权重")
    is_once: bool = Field(default=False, description="是否一次性遭遇")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "enc_001",
                "type": "monster",
                "name": "荒野狼群",
                "description": "一群饥饿的荒野狼",
                "data": {
                    "count": 5,
                    "level": 10,
                    "behavior": "aggressive",
                },
                "weight": 0.8,
            }
        }


class Region(BaseModel):
    """区域模型"""

    id: str = Field(..., description="区域唯一 ID")
    name: str = Field(..., description="区域名称")
    world_id: str = Field(..., description="所属世界 ID")

    # 区域类型
    region_type: RegionType = Field(default=RegionType.CUSTOM, description="区域类型")
    terrain_type: TerrainType = Field(default=TerrainType.CUSTOM, description="地形类型")

    # 描述信息
    description: Optional[str] = Field(None, description="区域描述")
    atmosphere: Optional[str] = Field(None, description="氛围描述")

    # 地理信息
    coordinates: Optional[Dict[str, float]] = Field(None, description="坐标信息")
    area_size: Optional[float] = Field(None, description="区域面积")

    # 地形特征
    terrain_features: List[Dict[str, Any]] = Field(default_factory=list, description="地形特征")
    landmarks: List[Dict[str, Any]] = Field(default_factory=list, description="地标建筑")

    # 遭遇池
    encounters: List[Encounter] = Field(default_factory=list, description="遭遇池")

    # 连接区域
    connections: List[str] = Field(default_factory=list, description="相邻区域 ID 列表")

    # 区域规则（可覆盖世界规则）
    local_rules: List[str] = Field(default_factory=list, description="本地规则 ID 列表")

    # 状态
    is_generated: bool = Field(default=False, description="是否为程序生成")
    visit_count: int = Field(default=0, description="访问次数")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "region_001",
                "name": "青石镇",
                "world_id": "world_001",
                "region_type": "village",
                "terrain_type": "plain",
                "description": "坐落在平原上的小镇，以出产青石闻名",
                "atmosphere": "宁静祥和，民风淳朴",
                "connections": ["region_002", "region_003"],
                "encounters": [
                    {
                        "id": "enc_001",
                        "type": "npc",
                        "name": "老铁匠",
                        "description": "镇上唯一的铁匠",
                    }
                ],
            }
        }
