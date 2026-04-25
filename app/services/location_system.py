"""
位置系统 - GodView v5 核心组件
管理世界中的地点和区域，处理角色移动和位置交互
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import random

from app.models.world import Region, RegionType, TerrainType


class LocationState(Enum):
    """地点状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    HAZARDOUS = "hazardous"
    BLOCKED = "blocked"


@dataclass
class LocationEvent:
    """地点事件"""
    event_id: str
    location_id: str
    event_type: str
    description: str
    affected_entities: List[str] = field(default_factory=list)
    environmental_effects: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration: timedelta = field(default_factory=lambda: timedelta(minutes=30))


@dataclass
class LocationStateData:
    """地点状态数据"""
    location_id: str
    state: LocationState
    environmental_conditions: Dict[str, Any] = field(default_factory=dict)
    special_effects: List[str] = field(default_factory=list)
    population: int = 0
    activity_level: float = 0.5  # 0.0-1.0
    last_updated: datetime = field(default_factory=datetime.utcnow)


class LocationEntity:
    """地点实体"""
    def __init__(self, region: Region, config: Dict[str, Any] = None):
        self.region = region
        self.config = config or {}

        # 状态管理
        self.state = LocationState.ACTIVE
        self.state_data = LocationStateData(
            location_id=region.id,
            state=LocationState.ACTIVE
        )

        # 环境条件
        self.weather = self._generate_initial_weather()
        self.temperature = 20.0  # 摄氏度
        self.lighting = "normal"  # bright, normal, dim, dark

        # 事件
        self.active_events: List[LocationEvent] = []
        self.event_history: List[LocationEvent] = []

        # 连接
        self.connections: Dict[str, float] = {}  # location_id -> travel_time
        self._initialize_connections()

        # 特殊属性
        self.safety_level = region.coordinates.get("safety_level", 0.8) if region.coordinates else 0.8
        self.comfort_level = region.coordinates.get("comfort_level", 0.7) if region.coordinates else 0.7

    def _generate_initial_weather(self) -> str:
        """生成初始天气"""
        weathers = ["晴天", "多云", "阴天", "小雨", "大风"]
        return random.choice(weathers)

    def _initialize_connections(self):
        """初始化连接关系"""
        for connection_id in self.region.connections:
            # 随机生成旅行时间（10-60分钟）
            travel_time = random.randint(10, 60)
            self.connections[connection_id] = travel_time

    def get_atmosphere(self, time_phase: str) -> str:
        """根据时间获取氛围"""
        base_atmosphere = self.region.atmosphere or "普通"

        if time_phase == "夜晚":
            return f"夜晚的{base_atmosphere}"
        elif time_phase == "早晨":
            return f"清晨的{base_atmosphere}"
        else:
            return base_atmosphere

    def update_environmental_conditions(self, time_phase: str):
        """更新环境条件"""
        # 根据时间和天气更新环境
        if time_phase == "夜晚":
            self.lighting = "dim"
            self.temperature -= 5.0  # 夜晚降温
        elif time_phase == "早晨":
            self.lighting = "bright"
            self.temperature += 2.0  # 早晨升温
        elif time_phase == "中午":
            self.lighting = "bright"
            self.temperature += 3.0  # 中午升温
        else:
            self.lighting = "normal"

        # 天气影响
        if self.weather in ["大雨", "暴雪"]:
            self.lighting = "dim"
            self.temperature -= 3.0
        elif self.weather == "晴天":
            self.lighting = "bright"
            self.temperature += 2.0

        # 限制温度范围
        self.temperature = max(-10.0, min(40.0, self.temperature))

    def is_safe(self) -> bool:
        """检查地点是否安全"""
        return (
            self.state == LocationState.ACTIVE and
            self.safety_level > 0.5 and
            not any(e.event_type == "danger" for e in self.active_events)
        )

    def is_accessible(self, entity_id: str) -> bool:
        """检查实体是否可以进入"""
        if self.state == LocationState.BLOCKED:
            return False

        if self.state == LocationState.HAZARDOUS:
            # 高危险度地点需要特定技能或装备才能进入
            # 这里简化实现
            return random.random() < 0.7  # 70%概率可以进入

        return True

    def add_event(self, event: LocationEvent):
        """添加地点事件"""
        self.active_events.append(event)
        self.state_data.last_updated = datetime.utcnow()

        # 更新安全等级
        if event.event_type == "danger":
            self.state = LocationState.HAZARDOUS

    def remove_event(self, event_id: str):
        """移除地点事件"""
        self.active_events = [e for e in self.active_events if e.event_id != event_id]

        # 如果没有危险事件，恢复正常状态
        if not any(e.event_type == "danger" for e in self.active_events):
            self.state = LocationState.ACTIVE

    def get_inhabitants(self, entity_system) -> List[str]:
        """获取在场的实体ID"""
        if not hasattr(entity_system, 'get_entities_in_location'):
            return []

        entities = entity_system.get_entities_in_location(self.region.id)
        return [e.entity_id for e in entities]

    def update_population(self, entity_system):
        """更新人口统计"""
        inhabitants = self.get_inhabitants(entity_system)
        self.state_data.population = len(inhabitants)

        # 计算活跃度
        if len(inhabitants) > 10:
            self.state_data.activity_level = 0.8
        elif len(inhabitants) > 5:
            self.state_data.activity_level = 0.5
        else:
            self.state_data.activity_level = 0.2


class LocationSystem:
    """位置系统

    管理世界中的所有地点，处理角色移动和位置交互
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

        # 地点存储
        self.locations: Dict[str, LocationEntity] = {}
        self.character_locations: Dict[str, str] = {}  # character_id -> location_id

        # 移动管理
        self.active_movements: Dict[str, Dict[str, Any]] = {}  # movement_id -> movement_data

        # 环境效果
        self.environmental_effects = EnvironmentalEffects(self.config.get("environment_config", {}))

        # 事件系统
        self.location_events: List[LocationEvent] = []

        # 统计
        self.movement_stats: Dict[str, Any] = {
            "total_movements": 0,
            "movements_by_location": {},
            "average_movement_time": 0.0
        }

        self.logger = logging.getLogger(__name__)

    def add_location(self, region: Region):
        """添加地点"""
        location = LocationEntity(region, self.config)
        self.locations[region.id] = location
        self.logger.info(f"添加地点: {region.name} ({region.id})")

    def remove_location(self, location_id: str):
        """移除地点"""
        if location_id in self.locations:
            location = self.locations[location_id]
            del self.locations[location_id]

            # 移除该地点的所有角色
            for char_id, loc_id in list(self.character_locations.items()):
                if loc_id == location_id:
                    del self.character_locations[char_id]

            self.logger.info(f"移除地点: {location.region.name} ({location_id})")

    def get_location(self, location_id: str) -> Optional[LocationEntity]:
        """获取地点"""
        return self.locations.get(location_id)

    def get_character_location(self, character_id: str) -> Optional[str]:
        """获取角色位置"""
        return self.character_locations.get(character_id)

    async def move_character(
        self,
        character_id: str,
        target_location_id: str,
        entity_system = None,
        reason: Optional[str] = None,
    ) -> bool:
        """移动角色到新地点

        Args:
            character_id: 角色ID
            target_location_id: 目标地点ID
            entity_system: 实体系统（用于验证）
            reason: 角色来到目标地点的理由概述

        Returns:
            bool: 是否成功移动
        """
        target_location = self.get_location(target_location_id)
        if not target_location:
            self.logger.warning(f"目标地点不存在: {target_location_id}")
            return False

        # 检查是否可以进入
        if not target_location.is_accessible(character_id):
            self.logger.info(f"角色 {character_id} 无法进入 {target_location_id}")
            return False

        # 获取当前地点
        current_location_id = self.get_character_location(character_id)
        travel_time = 30  # 默认30分钟

        if current_location_id and current_location_id in self.locations:
            current_location = self.locations[current_location_id]
            if target_location_id in current_location.connections:
                travel_time = current_location.connections[target_location_id]

        # 更新位置
        self.character_locations[character_id] = target_location_id

        # 更新统计
        self.movement_stats["total_movements"] += 1
        if target_location_id not in self.movement_stats["movements_by_location"]:
            self.movement_stats["movements_by_location"][target_location_id] = 0
        self.movement_stats["movements_by_location"][target_location_id] += 1

        # 计算平均移动时间
        prev_avg = self.movement_stats["average_movement_time"]
        total_moves = self.movement_stats["total_movements"]
        new_avg = ((prev_avg * (total_moves - 1)) + travel_time) / total_moves
        self.movement_stats["average_movement_time"] = new_avg

        self.logger.info(f"角色 {character_id} 移动到 {target_location.region.name}")

        # 如果有实体系统，更新实体的位置
        if entity_system:
            entity = entity_system.get_entity(character_id)
            if entity:
                entity.current_location = target_location_id
                entity.current_region_id = target_location_id
                entity.current_location_reason = reason or ""

        return True

    async def simulate_activity(self, time_delta: timedelta, entity_system=None):
        """模拟地点活动

        这是位置系统的核心方法，每个时钟周期调用
        """
        for location in self.locations.values():
            # 更新人口统计
            if entity_system:
                location.update_population(entity_system)

            # 更新环境条件
            time_phase = "day"  # TODO: 从时间系统获取
            location.update_environmental_conditions(time_phase)

            # 应用环境效果
            await self.environmental_effects.apply(location, time_delta)

            # 生成地点事件
            await self._generate_location_events(location, entity_system)

    async def _generate_location_events(
        self,
        location: LocationEntity,
        entity_system = None
    ):
        """为地点生成事件"""
        # 获取在场实体
        inhabitants = location.get_inhabitants(entity_system)

        if len(inhabitants) == 0:
            return

        # 随机事件概率
        event_probability = 0.05  # 5%概率生成事件

        if random.random() < event_probability:
            event_type = self._select_event_type(location, inhabitants)
            event = self._create_location_event(location, event_type, inhabitants)

            if event:
                location.add_event(event)
                self.location_events.append(event)

                # 通知相关实体
                await self._notify_entities_of_event(event, entity_system)

    def _select_event_type(
        self,
        location: LocationEntity,
        inhabitants: List[str]
    ) -> str:
        """选择事件类型"""
        event_types = [
            "weather_change",
            "social_interaction",
            "discovery",
            "danger"
        ]

        # 根据地点状态调整权重
        weights = {
            "weather_change": 0.3,
            "social_interaction": 0.4,
            "discovery": 0.2,
            "danger": 0.1
        }

        # 高活跃度地点更多社交事件
        if location.state_data.activity_level > 0.6:
            weights["social_interaction"] = 0.5
            weights["weather_change"] = 0.2

        # 危险地点更多危险事件
        if location.safety_level < 0.5:
            weights["danger"] = 0.3
            weights["discovery"] = 0.1

        # 加权随机选择
        events = list(weights.keys())
        event_weights = [weights[e] for e in events]
        return random.choices(events, weights=event_weights)[0]

    def _create_location_event(
        self,
        location: LocationEntity,
        event_type: str,
        inhabitants: List[str]
    ) -> Optional[LocationEvent]:
        """创建地点事件"""
        event_id = f"event_{location.region.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        if event_type == "weather_change":
            new_weather = random.choice(["晴天", "多云", "阴天", "小雨", "大雨"])
            description = f"天气变化：{new_weather}"
            environmental_effects = {
                "weather": new_weather,
                "visibility": 0.8 if new_weather in ["晴天", "多云"] else 0.5
            }

        elif event_type == "social_interaction":
            selected_inhabitants = random.sample(inhabitants, min(2, len(inhabitants)))
            description = f"角色间的社交互动"
            affected_entities = selected_inhabitants
            environmental_effects = {}

        elif event_type == "discovery":
            discoveries = ["新资源", "隐藏路径", "古代遗迹", "稀有物品"]
            discovered = random.choice(discoveries)
            description = f"发现：{discovered}"
            affected_entities = inhabitants
            environmental_effects = {}

        elif event_type == "danger":
            dangers = ["怪物袭击", "自然灾害", "陷阱触发", "强盗出没"]
            danger = random.choice(dangers)
            description = f"危险：{danger}"
            affected_entities = inhabitants
            environmental_effects = {"safety_reduction": 0.3}

        else:
            return None

        event = LocationEvent(
            event_id=event_id,
            location_id=location.region.id,
            event_type=event_type,
            description=description,
            affected_entities=affected_entities,
            environmental_effects=environmental_effects
        )

        return event

    async def _notify_entities_of_event(
        self,
        event: LocationEvent,
        entity_system=None
    ):
        """通知实体事件"""
        if not entity_system:
            return

        for entity_id in event.affected_entities:
            entity = entity_system.get_entity(entity_id)
            if entity:
                entity.remember({
                    "type": "location_event",
                    "location_id": event.location_id,
                    "event_type": event.event_type,
                    "description": event.description
                })

    def get_location_statistics(self) -> Dict[str, Any]:
        """获取地点统计信息"""
        return {
            "total_locations": len(self.locations),
            "total_characters": len(self.character_locations),
            "active_events": len(self.location_events),
            "movement_statistics": self.movement_stats,
            "locations_by_state": self._count_locations_by_state()
        }

    def _count_locations_by_state(self) -> Dict[str, int]:
        """统计各种状态的地点数量"""
        state_counts = {}
        for location in self.locations.values():
            state_name = location.state.value
            state_counts[state_name] = state_counts.get(state_name, 0) + 1
        return state_counts

    def get_locations_by_type(self, location_type: RegionType) -> List[LocationEntity]:
        """根据类型获取地点"""
        return [
            location for location in self.locations.values()
            if location.region.region_type == location_type
        ]

    def get_safe_locations(self) -> List[LocationEntity]:
        """获取所有安全地点"""
        return [loc for loc in self.locations.values() if loc.is_safe()]

    def get_hazardous_locations(self) -> List[LocationEntity]:
        """获取所有危险地点"""
        return [loc for loc in self.locations.values() if not loc.is_safe()]

    def get_connection_path(self, from_location: str, to_location: str) -> List[str]:
        """获取连接路径（简化实现）"""
        # TODO: 实现最短路径算法
        if from_location == to_location:
            return [from_location]

        # 直接连接
        from_loc = self.get_location(from_location)
        if from_loc and to_location in from_loc.connections:
            return [from_location, to_location]

        # 暂不支持复杂路径
        return []


class EnvironmentalEffects:
    """环境效果系统"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def apply(self, location: LocationEntity, time_delta: timedelta):
        """应用环境效果到地点"""
        # 应用天气效果
        await self._apply_weather_effects(location)

        # 应用光照效果
        await self._apply_lighting_effects(location)

        # 应用温度效果
        await self._apply_temperature_effects(location)

        # 更新环境条件数据
        location.state_data.environmental_conditions = {
            "weather": location.weather,
            "temperature": location.temperature,
            "lighting": location.lighting,
            "safety": location.safety_level,
            "comfort": location.comfort_level
        }

    async def _apply_weather_effects(self, location: LocationEntity):
        """应用天气效果"""
        weather_effects = {
            "晴天": {"comfort": 0.1, "activity": 0.2},
            "多云": {"comfort": 0.0, "activity": 0.1},
            "阴天": {"comfort": -0.1, "activity": 0.0},
            "小雨": {"comfort": -0.2, "activity": -0.1},
            "大雨": {"comfort": -0.4, "activity": -0.3},
            "大风": {"comfort": -0.3, "activity": -0.2}
        }

        effects = weather_effects.get(location.weather, {})
        location.comfort_level = max(0.0, min(1.0, location.comfort_level + effects.get("comfort", 0.0)))

        # 活跃度影响
        activity_change = effects.get("activity", 0.0)
        location.state_data.activity_level = max(0.0, min(1.0, location.state_data.activity_level + activity_change))

    async def _apply_lighting_effects(self, location: LocationEntity):
        """应用光照效果"""
        lighting_effects = {
            "bright": {"comfort": 0.1, "activity": 0.1},
            "normal": {"comfort": 0.0, "activity": 0.0},
            "dim": {"comfort": -0.1, "activity": -0.1},
            "dark": {"comfort": -0.2, "activity": -0.2}
        }

        effects = lighting_effects.get(location.lighting, {})
        location.comfort_level = max(0.0, min(1.0, location.comfort_level + effects.get("comfort", 0.0)))

    async def _apply_temperature_effects(self, location: LocationEntity):
        """应用温度效果"""
        # 舒适温度范围：18-25度
        optimal_temp = 22.0
        temp_diff = abs(location.temperature - optimal_temp)

        # 温度差异越大，舒适度越低
        comfort_penalty = min(0.3, temp_diff / 20.0)
        location.comfort_level = max(0.0, 1.0 - comfort_penalty)