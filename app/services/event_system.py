"""
事件系统 - GodView v5 核心组件
处理随机事件和事件效果，基于世界状态生成和执行事件
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import random

from app.models.world import Encounter, EncounterType


class EventType(Enum):
    """事件类型"""
    WEATHER = "weather"
    SOCIAL = "social"
    COMBAT = "combat"
    DISCOVERY = "discovery"
    QUEST = "quest"
    HAZARD = "hazard"
    MILESTONE = "milestone"
    RANDOM = "random"


class EventPriority(Enum):
    """事件优先级"""
    CRITICAL = 0  # 必须立即处理
    HIGH = 1      # 高优先级
    NORMAL = 2    # 正常优先级
    LOW = 3       # 低优先级


class EventStatus(Enum):
    """事件状态"""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class EventTrigger:
    """事件触发条件"""
    trigger_type: str  # time, location, entity_state, relationship, etc.
    conditions: Dict[str, Any] = field(default_factory=dict)
    probability: float = 1.0  # 触发概率
    cooldown: timedelta = field(default_factory=lambda: timedelta(hours=1))


@dataclass
class EventEffect:
    """事件效果"""
    effect_type: str
    target_type: str  # entity, location, world, relationship, etc.
    target_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[timedelta] = None


@dataclass
class Event:
    """事件定义"""
    event_id: str
    event_type: EventType
    name: str
    description: str
    priority: EventPriority = EventPriority.NORMAL
    status: EventStatus = EventStatus.PENDING

    # 触发相关
    triggers: List[EventTrigger] = field(default_factory=list)
    trigger_time: Optional[datetime] = None

    # 效果相关
    effects: List[EventEffect] = field(default_factory=list)

    # 时间相关
    created_time: datetime = field(default_factory=datetime.utcnow)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[timedelta] = None

    # 参与者
    involved_entities: List[str] = field(default_factory=list)
    involved_locations: List[str] = field(default_factory=list)

    # 数据
    event_data: Dict[str, Any] = field(default_factory=dict)

    def is_complete(self) -> bool:
        """检查事件是否完成"""
        return self.status == EventStatus.COMPLETED

    def should_trigger(self, world_state: Dict[str, Any]) -> bool:
        """检查是否应该触发事件"""
        # 检查时间条件
        if self.trigger_time and datetime.utcnow() < self.trigger_time:
            return False

        # 检查触发条件
        for trigger in self.triggers:
            if not self._check_trigger(trigger, world_state):
                return False

        # 随机概率检查
        total_probability = 1.0
        for trigger in self.triggers:
            total_probability *= trigger.probability

        if random.random() > total_probability:
            return False

        return True

    def _check_trigger(self, trigger: EventTrigger, world_state: Dict[str, Any]) -> bool:
        """检查单个触发条件"""
        trigger_type = trigger.trigger_type
        conditions = trigger.conditions

        if trigger_type == "time":
            current_time = world_state.get("current_time")
            if not current_time:
                return False

            # 检查时间段
            if "time_phase" in conditions:
                time_phase = world_state.get("time_phase")
                if time_phase != conditions["time_phase"]:
                    return False

            # 检查特定时间
            if "specific_time" in conditions:
                from datetime import datetime as dt
                specific_time = dt.fromisoformat(conditions["specific_time"])
                if abs((current_time - specific_time).total_seconds()) > 300:  # 5分钟容差
                    return False

        elif trigger_type == "location":
            location_id = conditions.get("location_id")
            if location_id:
                current_location = world_state.get("current_location")
                if current_location != location_id:
                    return False

            # 检查地点类型
            if "location_type" in conditions:
                current_location_type = world_state.get("location_type")
                if current_location_type != conditions["location_type"]:
                    return False

        elif trigger_type == "entity_state":
            entity_id = conditions.get("entity_id")
            if not entity_id:
                return False

            # 检查实体属性
            entity = world_state.get("entities", {}).get(entity_id)
            if not entity:
                return False

            for attr_name, attr_value in conditions.get("attributes", {}).items():
                if getattr(entity, attr_name, None) != attr_value:
                    return False

        elif trigger_type == "relationship":
            entity_id_1 = conditions.get("entity_id_1")
            entity_id_2 = conditions.get("entity_id_2")
            relationship_strength = conditions.get("relationship_strength")

            if not (entity_id_1 and entity_id_2 and relationship_strength is not None):
                return False

            # 检查关系强度（简化实现）
            # 实际应该查询关系系统
            # 这里只是示意

        return True


class EventTemplateLibrary:
    """事件模板库

    存储所有可用的事件模板
    """

    def __init__(self):
        self.templates: Dict[str, Dict[str, Any]] = {}
        self._initialize_default_templates()

    def _initialize_default_templates(self):
        """初始化默认事件模板"""
        # 天气事件
        self.templates["weather_storm"] = {
            "name": "暴风雨",
            "description": "强烈的暴风雨席卷整个地区",
            "event_type": EventType.WEATHER,
            "priority": EventPriority.HIGH,
            "duration": timedelta(hours=2),
            "effects": [
                {
                    "effect_type": "weather_change",
                    "target_type": "world",
                    "parameters": {"weather": "storm", "visibility": 0.3}
                },
                {
                    "effect_type": "safety_reduction",
                    "target_type": "location",
                    "parameters": {"safety_reduction": 0.4}
                }
            ]
        }

        # 社交事件
        self.templates["social_chance_meeting"] = {
            "name": "偶遇",
            "description": "在旅途中遇到陌生人",
            "event_type": EventType.SOCIAL,
            "priority": EventPriority.NORMAL,
            "triggers": [
                {
                    "trigger_type": "location",
                    "conditions": {"location_type": "path", "time_phase": "day"},
                    "probability": 0.3
                }
            ],
            "effects": [
                {
                    "effect_type": "relationship_opportunity",
                    "target_type": "entity",
                    "parameters": {"relationship_change": 0.2}
                }
            ]
        }

        # 战斗事件
        self.templates["combat_ambush"] = {
            "name": "埋伏袭击",
            "description": "遭到敌人埋伏",
            "event_type": EventType.COMBAT,
            "priority": EventPriority.CRITICAL,
            "triggers": [
                {
                    "trigger_type": "location",
                    "conditions": {"location_type": "dangerous_path"},
                    "probability": 0.2
                }
            ],
            "effects": [
                {
                    "effect_type": "damage",
                    "target_type": "entity",
                    "parameters": {"damage_amount": 10}
                }
            ]
        }

        # 发现事件
        self.templates["discovery_treasure"] = {
            "name": "发现宝藏",
            "description": "在探索中发现宝藏",
            "event_type": EventType.DISCOVERY,
            "priority": EventPriority.NORMAL,
            "triggers": [
                {
                    "trigger_type": "location",
                    "conditions": {"location_type": "ruins"},
                    "probability": 0.1
                }
            ],
            "effects": [
                {
                    "effect_type": "add_item",
                    "target_type": "entity",
                    "parameters": {"item": "treasure_chest"}
                }
            ]
        }

        # 里程碑事件
        self.templates["milestone_level_up"] = {
            "name": "角色成长",
            "description": "角色能力提升",
            "event_type": EventType.MILESTONE,
            "priority": EventPriority.NORMAL,
            "triggers": [
                {
                    "trigger_type": "entity_state",
                    "conditions": {"attributes": {"level_threshold_reached": True}},
                    "probability": 1.0
                }
            ],
            "effects": [
                {
                    "effect_type": "level_up",
                    "target_type": "entity",
                    "parameters": {"level_increase": 1}
                }
            ]
        }

    def get_eligible_templates(self, world_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取符合条件的事件模板"""
        eligible = []

        for template_id, template in self.templates.items():
            # 检查优先级限制
            event_priority = template.get("priority", EventPriority.NORMAL)
            if event_priority == EventPriority.CRITICAL:
                # 事件模板是静态定义，不在这里检查优先级
                pass

            eligible.append({
                **template,
                "template_id": template_id
            })

        return eligible

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取事件模板"""
        return self.templates.get(template_id)

    def get_templates_by_type(self, event_type: EventType) -> List[Dict[str, Any]]:
        """根据类型获取事件模板"""
        return [
            {"template_id": template_id, **template}
            for template_id, template in self.templates.items()
            if template.get("event_type") == event_type
        ]


class TriggerSystem:
    """触发系统

    管理事件的触发条件
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.trigger_history: Dict[str, List[datetime]] = {}  # trigger_key -> trigger_times
        self.logger = logging.getLogger(__name__)

    def should_trigger(self, event: Event, world_state: Dict[str, Any]) -> bool:
        """检查事件是否应该触发"""
        # 基本触发检查
        if not event.should_trigger(world_state):
            return False

        # 冷却时间检查
        for trigger in event.triggers:
            if self._is_in_cooldown(trigger):
                return False

        return True

    def _is_in_cooldown(self, trigger: EventTrigger) -> bool:
        """检查是否在冷却中"""
        trigger_key = f"{trigger.trigger_type}_{hash(str(trigger.conditions))}"

        if trigger_key not in self.trigger_history:
            return False

        last_trigger_time = self.trigger_history[trigger_key][-1]
        cooldown_expired = (datetime.utcnow() - last_trigger_time) >= trigger.cooldown

        return not cooldown_expired

    def record_trigger(self, trigger: EventTrigger):
        """记录触发时间"""
        trigger_key = f"{trigger.trigger_type}_{hash(str(trigger.conditions))}"

        if trigger_key not in self.trigger_history:
            self.trigger_history[trigger_key] = []

        self.trigger_history[trigger_key].append(datetime.utcnow())

        # 清理旧记录（保留最近10次）
        if len(self.trigger_history[trigger_key]) > 10:
            self.trigger_history[trigger_key] = self.trigger_history[trigger_key][-10]


class EffectSystem:
    """效果系统

    管理事件效果的执行
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.active_effects: Dict[str, Dict[str, Any]] = {}  # effect_id -> effect_data
        self.logger = logging.getLogger(__name__)

    async def apply(self, event: Event, world_context: Dict[str, Any]):
        """应用事件效果"""
        for effect in event.effects:
            try:
                await self._apply_single_effect(effect, world_context)
                self.logger.info(f"应用效果: {effect.effect_type} -> {effect.target_type}")
            except Exception as e:
                self.logger.error(f"应用效果失败: {e}")

    async def _apply_single_effect(self, effect: EventEffect, world_context: Dict[str, Any]):
        """应用单个效果"""
        effect_type = effect.effect_type
        target_type = effect.target_type
        parameters = effect.parameters

        if effect_type == "weather_change":
            # 改变天气
            self._apply_weather_change(parameters)

        elif effect_type == "safety_reduction":
            # 降低安全等级
            self._apply_safety_reduction(parameters, world_context)

        elif effect_type == "damage":
            # 造成伤害
            self._apply_damage(parameters, world_context)

        elif effect_type == "heal":
            # 治疗效果
            self._apply_heal(parameters, world_context)

        elif effect_type == "relationship_opportunity":
            # 关系机会
            self._apply_relationship_opportunity(parameters, world_context)

        elif effect_type == "add_item":
            # 添加物品
            self._apply_add_item(parameters, world_context)

        elif effect_type == "level_up":
            # 升级效果
            self._apply_level_up(parameters, world_context)

        # 其他效果类型...

    def _apply_weather_change(self, parameters: Dict[str, Any]):
        """应用天气变化"""
        weather = parameters.get("weather")
        if weather:
            # 这里应该通知世界天气系统
            pass

    def _apply_safety_reduction(self, parameters: Dict[str, Any], world_context: Dict[str, Any]):
        """应用安全等级降低"""
        reduction = parameters.get("safety_reduction", 0.0)
        # 这里应该更新相关地点的安全等级
        pass

    def _apply_damage(self, parameters: Dict[str, Any], world_context: Dict[str, Any]):
        """应用伤害效果"""
        damage_amount = parameters.get("damage_amount", 0)
        # 这里应该伤害相关实体
        pass

    def _apply_heal(self, parameters: Dict[str, Any], world_context: Dict[str, Any]):
        """应用治疗效果"""
        heal_amount = parameters.get("heal_amount", 0)
        # 这里应该治疗相关实体
        pass

    def _apply_relationship_opportunity(self, parameters: Dict[str, Any], world_context: Dict[str, Any]):
        """应用关系机会"""
        relationship_change = parameters.get("relationship_change", 0.0)
        # 这里应该提供社交机会
        pass

    def _apply_add_item(self, parameters: Dict[str, Any], world_context: Dict[str, Any]):
        """应用添加物品效果"""
        item = parameters.get("item")
        # 这里应该给相关实体添加物品
        pass

    def _apply_level_up(self, parameters: Dict[str, Any], world_context: Dict[str, Any]):
        """应用升级效果"""
        level_increase = parameters.get("level_increase", 0)
        # 这里应该升级相关实体
        pass


class EventSystem:
    """事件系统

    处理随机事件和事件效果，基于世界状态生成和执行事件
    """

    def __init__(self, world_config: Dict[str, Any] = None):
        self.config = world_config or {}

        # 核心组件
        self.template_library = EventTemplateLibrary()
        self.trigger_system = TriggerSystem(self.config.get("trigger_config", {}))
        self.effect_system = EffectSystem(self.config.get("effect_config", {}))

        # 事件管理
        self.active_events: List[Event] = []
        self.pending_events: List[Event] = []
        self.completed_events: List[Event] = []

        # 配置
        self.max_active_events = self.config.get("max_active_events", 5)
        self.event_generation_probability = self.config.get("event_generation_probability", 0.1)

        # 统计
        self.event_stats: Dict[str, Any] = {
            "total_events": 0,
            "events_by_type": {},
            "triggered_events": 0,
            "completed_events": 0
        }

        self.logger = logging.getLogger(__name__)

    async def generate_random_event(self, world_state: Dict[str, Any]) -> Optional[Event]:
        """根据世界状态生成随机事件"""
        if len(self.active_events) >= self.max_active_events:
            return None

        # 随机决定是否生成事件
        if random.random() > self.event_generation_probability:
            return None

        # 获取符合条件的事件模板
        eligible_templates = self.template_library.get_eligible_templates(world_state)

        if not eligible_templates:
            return None

        # 根据权重随机选择模板
        selected_template = self._weighted_template_select(eligible_templates)

        if not selected_template:
            return None

        # 实例化事件
        event = self._instantiate_event(selected_template, world_state)

        if event:
            self.pending_events.append(event)
            self.event_stats["total_events"] += 1

            event_type = event.event_type.value
            self.event_stats["events_by_type"][event_type] = (
                self.event_stats["events_by_type"].get(event_type, 0) + 1
            )

        return event

    def _weighted_template_select(self, templates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """加权随机选择事件模板"""
        if not templates:
            return None

        # 根据优先级设置权重
        weights = []
        for template in templates:
            priority = template.get("priority", EventPriority.NORMAL)
            if priority == EventPriority.CRITICAL:
                weight = 4
            elif priority == EventPriority.HIGH:
                weight = 3
            elif priority == EventPriority.NORMAL:
                weight = 2
            else:
                weight = 1
            weights.append(weight)

        # 加权随机选择
        selected_index = random.choices(range(len(templates)), weights=weights, k=1)[0]
        return templates[selected_index]

    def _instantiate_event(self, template: Dict[str, Any], world_state: Dict[str, Any]) -> Optional[Event]:
        """实例化事件"""
        event_id = f"event_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"

        # 构建触发器
        triggers_data = template.get("triggers", [])
        triggers = []
        for trigger_data in triggers_data:
            triggers.append(EventTrigger(
                trigger_type=trigger_data["trigger_type"],
                conditions=trigger_data.get("conditions", {}),
                probability=trigger_data.get("probability", 1.0),
                cooldown=timedelta(hours=trigger_data.get("cooldown_hours", 1))
            ))

        # 构建效果
        effects_data = template.get("effects", [])
        effects = []
        for effect_data in effects_data:
            effects.append(EventEffect(
                effect_type=effect_data["effect_type"],
                target_type=effect_data["target_type"],
                target_id=effect_data.get("target_id"),
                parameters=effect_data.get("parameters", {})
            ))

        # 创建事件对象
        event = Event(
            event_id=event_id,
            event_type=template["event_type"],
            name=template["name"],
            description=template["description"],
            priority=template.get("priority", EventPriority.NORMAL),
            triggers=triggers,
            effects=effects,
            duration=template.get("duration"),
            event_data=template.get("event_data", {})
        )

        return event

    async def process_triggers(self, time_delta: timedelta, world_state: Dict[str, Any]):
        """处理事件触发器"""
        # 检查待处理事件
        events_to_trigger = []
        for event in self.pending_events[:]:
            if self.trigger_system.should_trigger(event, world_state):
                events_to_trigger.append(event)

        # 触发事件
        for event in events_to_trigger:
            await self._trigger_event(event)
            self.pending_events.remove(event)

    async def _trigger_event(self, event: Event):
        """触发事件"""
        event.status = EventStatus.ACTIVE
        event.start_time = datetime.utcnow()

        if event.duration:
            event.end_time = event.start_time + event.duration

        self.active_events.append(event)
        self.event_stats["triggered_events"] += 1

        # 记录触发器历史
        for trigger in event.triggers:
            self.trigger_system.record_trigger(trigger)

        self.logger.info(f"触发事件: {event.name} ({event.event_id})")

    async def execute_event(self, event: Event, world_context: Dict[str, Any]):
        """执行事件效果"""
        # 应用事件效果
        await self.effect_system.apply(event, world_context)

        # 通知相关实体
        await self._notify_entities(event, world_context)

    async def _notify_entities(self, event: Event, world_context: Dict[str, Any]):
        """通知相关实体事件"""
        # 这里应该通知事件涉及的所有实体
        # 实际实现需要与实体系统集成
        pass

    async def update_active_events(self, time_delta: timedelta):
        """更新活跃事件"""
        completed_events = []

        for event in self.active_events[:]:
            # 检查事件是否完成
            if event.is_complete():
                completed_events.append(event)
                continue

            # 检查是否有结束时间
            if event.end_time and datetime.utcnow() >= event.end_time:
                await self._complete_event(event)
                completed_events.append(event)
                continue

        # 移除已完成事件
        for event in completed_events:
            self.active_events.remove(event)

    async def _complete_event(self, event: Event):
        """完成事件"""
        event.status = EventStatus.COMPLETED
        event.end_time = datetime.utcnow()
        self.completed_events.append(event)
        self.event_stats["completed_events"] += 1

        self.logger.info(f"完成事件: {event.name} ({event.event_id})")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.event_stats,
            "active_events_count": len(self.active_events),
            "pending_events_count": len(self.pending_events),
            "completed_events_count": len(self.completed_events)
        }

    def get_events_by_type(self, event_type: EventType) -> List[Event]:
        """根据类型获取事件"""
        return [e for e in self.active_events if e.event_type == event_type]

    def get_high_priority_events(self) -> List[Event]:
        """获取高优先级事件"""
        return [e for e in self.active_events if e.priority in [EventPriority.CRITICAL, EventPriority.HIGH]]

    def create_custom_event(
        self,
        event_id: str,
        event_type: EventType,
        name: str,
        description: str,
        effects: List[EventEffect],
        priority: EventPriority = EventPriority.NORMAL
    ) -> Event:
        """创建自定义事件"""
        event = Event(
            event_id=event_id,
            event_type=event_type,
            name=name,
            description=description,
            effects=effects,
            priority=priority
        )

        return event

    def schedule_event(
        self,
        event_id: str,
        event_type: EventType,
        name: str,
        description: str,
        trigger_time: datetime,
        effects: List[EventEffect],
        involved_entities: List[str] = None,
        involved_locations: List[str] = None
    ) -> Event:
        """计划定时事件"""
        event = Event(
            event_id=event_id,
            event_type=event_type,
            name=name,
            description=description,
            trigger_time=trigger_time,
            effects=effects,
            involved_entities=involved_entities or [],
            involved_locations=involved_locations or []
        )

        self.pending_events.append(event)
        return event