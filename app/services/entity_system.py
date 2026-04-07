"""
实体系统 - GodView v5 核心组件
管理世界中的所有实体（角色、物品、组织等），支持自主行为决策
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import random

from app.models.character import Character, PersonalityTrait


class EntityType(Enum):
    """实体类型"""
    CHARACTER = "character"
    ITEM = "item"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"


class EntityStatus(Enum):
    """实体状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEAD = "dead"
    DESTROYED = "destroyed"
    HIDDEN = "hidden"


class ActionPriority(Enum):
    """行动优先级"""
    CRITICAL = 0  # 紧急/关键
    HIGH = 1      # 高优先级
    NORMAL = 2    # 正常优先级
    LOW = 3       # 低优先级


@dataclass
class Action:
    """行动定义"""
    action_id: str
    action_type: str
    entity_id: str
    target_id: Optional[str] = None
    priority: ActionPriority = ActionPriority.NORMAL
    duration: timedelta = field(default_factory=lambda: timedelta(minutes=10))
    cooldown: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    requirements: Dict[str, Any] = field(default_factory=dict)
    effects: List[Dict[str, Any]] = field(default_factory=list)
    description: str = ""


@dataclass
class Goal:
    """目标定义"""
    goal_id: str
    entity_id: str
    goal_type: str
    description: str
    importance: float  # 0.0 - 1.0
    deadline: Optional[datetime] = None
    completion_conditions: List[Dict[str, Any]] = field(default_factory=list)
    related_actions: List[str] = field(default_factory=list)


class Entity:
    """实体基类"""

    def __init__(
        self,
        entity_id: str,
        entity_type: EntityType,
        name: str,
        config: Dict[str, Any] = None
    ):
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.name = name
        self.config = config or {}

        # 状态管理
        self.status = EntityStatus.ACTIVE
        self.current_location: Optional[str] = None
        self.current_action: Optional[Action] = None
        self.current_goal: Optional[Goal] = None

        # 属性
        self.attributes: Dict[str, Any] = {}
        self.skills: Dict[str, float] = {}
        self.inventory: List[str] = []

        # 关系
        self.relationships: Dict[str, float] = {}  # entity_id -> relationship_strength

        # 行为
        self.available_actions: List[Action] = []
        self.goals: List[Goal] = []
        self.behavior_patterns: Dict[str, Any] = {}

        # 时间相关
        self.last_action_time: Optional[datetime] = None
        self.creation_time: datetime = datetime.utcnow()

        # 记忆
        self.episodic_memory: List[Dict[str, Any]] = []

    def is_available_for_action(self) -> bool:
        """检查实体是否可执行行动"""
        return (
            self.status == EntityStatus.ACTIVE and
            self.current_action is None and
            not self.is_in_cooldown()
        )

    def is_in_cooldown(self) -> bool:
        """检查是否在冷却中"""
        if not self.last_action_time or not self.current_action:
            return False

        return datetime.utcnow() < (self.last_action_time + self.current_action.cooldown)

    def add_goal(self, goal: Goal):
        """添加目标"""
        self.goals.append(goal)
        # 按重要性排序
        self.goals.sort(key=lambda g: g.importance, reverse=True)

    def remove_goal(self, goal_id: str):
        """移除目标"""
        self.goals = [g for g in self.goals if g.goal_id != goal_id]

    def get_highest_priority_goal(self) -> Optional[Goal]:
        """获取最高优先级的目标"""
        if not self.goals:
            return None

        # 检查是否有紧急目标
        urgent_goals = [g for g in self.goals if g.deadline and g.deadline <= datetime.utcnow()]
        if urgent_goals:
            return urgent_goals[0]

        return self.goals[0]

    def add_relationship(self, target_id: str, strength: float):
        """添加关系"""
        self.relationships[target_id] = max(-1.0, min(1.0, strength))

    def get_relationship(self, target_id: str) -> float:
        """获取关系强度"""
        return self.relationships.get(target_id, 0.0)

    def remember(self, event: Dict[str, Any]):
        """记录事件到记忆"""
        self.episodic_memory.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event
        })

        # 限制记忆大小（最多100条）
        if len(self.episodic_memory) > 100:
            self.episodic_memory = self.episodic_memory[-100:]

    def get_relevant_memories(self, context: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取相关记忆"""
        # 简化实现：返回最近的记忆
        # 实际实现应该使用向量相似度匹配
        return self.episodic_memory[-limit:]


class CharacterEntity(Entity):
    """角色实体"""

    def __init__(self, character: Character, config: Dict[str, Any] = None):
        super().__init__(
            entity_id=character.id,
            entity_type=EntityType.CHARACTER,
            name=character.name,
            config=config or {}
        )

        self.character_data = character

        # 性格特质
        self.personality_traits: Dict[str, float] = {
            trait.trait_name: trait.trait_value
            for trait in character.personality_traits
        }

        # 情绪状态
        self.mood: float = 0.5  # 0.0-1.0，0.5是中性
        self.energy: float = 1.0  # 0.0-1.0，1.0是充满精力

        # 社交属性
        self.social_openness = self._calculate_social_openness()
        self.aggressiveness = self._calculate_aggressiveness()
        self.curiosity = self._calculate_curiosity()

        # 设定相关
        self.current_location = character.current_location
        self.attributes["description"] = character.description
        self.attributes["background"] = character.background_story
        self.attributes["goals"] = character.goals

        # 语言特征
        self.speech_pattern = character.speech_pattern
        self.lexicon = character.lexicon
        self.forbidden_words = character.forbidden_words

    def _calculate_social_openness(self) -> float:
        """计算社交开放度"""
        traits = self.personality_traits
        openness = traits.get("开放性", 0.5)
        extraversion = traits.get("外向性", 0.5)
        return (openness + extraversion) / 2

    def _calculate_aggressiveness(self) -> float:
        """计算攻击性"""
        traits = self.personality_traits
        neuroticism = traits.get("神经质", 0.5)
        agreeableness = traits.get("宜人性", 0.5)
        return (neuroticism + (1 - agreeableness)) / 2

    def _calculate_curiosity(self) -> float:
        """计算好奇心"""
        traits = self.personality_traits
        openness = traits.get("开放性", 0.5)
        conscientiousness = traits.get("尽责性", 0.5)
        return (openness + conscientiousness) / 2

    def calculate_action_probability(
        self,
        action: Action,
        context: Dict[str, Any]
    ) -> float:
        """计算执行行动的概率

        这是角色自主决策的核心，基于多种因素计算
        """
        probability = 0.0

        # 1. 目标相关性 (40%)
        goal_alignment = self._calculate_goal_alignment(action)
        probability += goal_alignment * 0.4

        # 2. 性格倾向 (30%)
        personality_factor = self._match_personality(action)
        probability += personality_factor * 0.3

        # 3. 环境影响 (20%)
        environmental_influence = self._assess_environment(action, context)
        probability += environmental_influence * 0.2

        # 4. 社交网络影响 (10%)
        social_influence = self._calculate_social_influence(action, context)
        probability += social_influence * 0.1

        return max(0.0, min(1.0, probability))

    def _calculate_goal_alignment(self, action: Action) -> float:
        """计算行动与目标的对齐度"""
        current_goal = self.get_highest_priority_goal()
        if not current_goal or action.action_id not in current_goal.related_actions:
            return 0.1  # 默认低相关性

        # 检查行动是否有助于目标
        goal_importance = current_goal.importance
        action_match = 0.8 if action.action_id in current_goal.related_actions else 0.2

        return goal_importance * action_match

    def _match_personality(self, action: Action) -> float:
        """匹配性格倾向"""
        # 根据行动类型和性格特质计算匹配度
        action_type = action.action_type

        if action_type == "social_interaction":
            return self.social_openness * 0.7 + 0.3
        elif action_type == "aggressive_action":
            return self.aggressiveness * 0.7 + 0.3
        elif action_type == "exploration":
            return self.curiosity * 0.7 + 0.3
        elif action_type == "rest":
            return (1 - self.energy) * 0.7 + 0.3
        else:
            return 0.5  # 默认中等匹配

    def _assess_environment(self, action: Action, context: Dict[str, Any]) -> float:
        """评估环境影响"""
        # 考虑时间、地点、在场人员等因素
        environmental_score = 0.5

        # 时间因素
        time_phase = context.get("time_phase", "day")
        if action.action_type == "social_interaction" and time_phase in ["morning", "afternoon"]:
            environmental_score += 0.2
        elif action.action_type == "rest" and time_phase == "night":
            environmental_score += 0.3

        # 地点因素
        location_type = context.get("location_type", "general")
        if location_type == "tavern" and action.action_type == "social_interaction":
            environmental_score += 0.2

        # 精力因素
        if action.action_type == "physical_action" and self.energy < 0.3:
            environmental_score -= 0.4

        return max(0.0, min(1.0, environmental_score))

    def _calculate_social_influence(self, action: Action, context: Dict[str, Any]) -> float:
        """计算社交网络影响"""
        # 考虑在场他人的影响
        present_entities = context.get("present_entities", [])
        social_influence = 0.0

        for entity_id in present_entities:
            if entity_id == self.entity_id:
                continue

            relationship = self.get_relationship(entity_id)
            # 正向关系倾向于合作，负向关系倾向于对抗
            if relationship > 0.5:
                social_influence += 0.1
            elif relationship < -0.3:
                social_influence -= 0.1

        # 归一化
        return max(0.0, min(1.0, social_influence + 0.5))


class EntitySystem:
    """实体系统

    管理世界中的所有实体，协调实体的自主行为
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

        # 实体存储
        self.entities: Dict[str, Entity] = {}
        self.characters: Dict[str, CharacterEntity] = {}

        # 行动管理
        self.active_actions: Dict[str, Action] = {}  # action_id -> Action
        self.action_queue: List[Action] = []

        # 更新策略
        self.update_strategy = self.config.get("update_strategy", "balanced")
        # balanced: 所有实体更新
        # priority: 优先重要实体
        # random: 随机选择部分实体更新

        # 性能统计
        self.update_stats: Dict[str, Any] = {
            "total_updates": 0,
            "characters_updated": 0,
            "actions_executed": 0,
            "avg_update_time": 0.0
        }

        self.logger = logging.getLogger(__name__)

    def add_entity(self, entity: Entity):
        """添加实体"""
        self.entities[entity.entity_id] = entity

        if isinstance(entity, CharacterEntity):
            self.characters[entity.entity_id] = entity

        self.logger.info(f"添加实体: {entity.name} ({entity.entity_id})")

    def remove_entity(self, entity_id: str):
        """移除实体"""
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            del self.entities[entity_id]

            if entity_id in self.characters:
                del self.characters[entity_id]

            self.logger.info(f"移除实体: {entity.name} ({entity_id})")

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self.entities.get(entity_id)

    def get_character(self, character_id: str) -> Optional[CharacterEntity]:
        """获取角色实体"""
        return self.characters.get(character_id)

    def get_entities_in_location(self, location_id: str) -> List[Entity]:
        """获取在指定位置的所有实体"""
        return [
            entity for entity in self.entities.values()
            if entity.current_location == location_id and
            entity.status == EntityStatus.ACTIVE
        ]

    async def update_all(self, time_delta: timedelta):
        """更新所有实体的状态

        这是实体系统的核心方法，每个时钟周期调用
        """
        update_start = datetime.utcnow()

        # 根据更新策略选择要更新的实体
        entities_to_update = self._select_entities_for_update()

        # 更新每个实体
        for entity in entities_to_update:
            await self._update_entity(entity, time_delta)

        # 处理行动队列
        await self._process_action_queue(time_delta)

        # 更新统计信息
        self._update_statistics(update_start)

    def _select_entities_for_update(self) -> List[Entity]:
        """根据策略选择要更新的实体"""
        if self.update_strategy == "balanced":
            return list(self.entities.values())

        elif self.update_strategy == "priority":
            # 优先更新角色，然后是其他实体
            priority_entities = [e for e in self.entities.values()
                             if e.entity_type == EntityType.CHARACTER]
            other_entities = [e for e in self.entities.values()
                            if e.entity_type != EntityType.CHARACTER]
            return priority_entities + other_entities

        elif self.update_strategy == "random":
            # 随机选择50%的实体更新
            all_entities = list(self.entities.values())
            return random.sample(all_entities, max(1, len(all_entities) // 2))

        else:
            return list(self.entities.values())

    async def _update_entity(self, entity: Entity, time_delta: timedelta):
        """更新单个实体的状态"""
        # 更新实体状态
        if entity.entity_type == EntityType.CHARACTER and isinstance(entity, CharacterEntity):
            await self._update_character(entity, time_delta)

        # 恢复精力
        if hasattr(entity, 'energy'):
            entity.energy = min(1.0, entity.energy + time_delta.total_seconds() / 3600 * 0.1)

        # 检查并执行自主行动
        if entity.is_available_for_action():
            await self._trigger_autonomous_action(entity)

    async def _update_character(self, character: CharacterEntity, time_delta: timedelta):
        """更新角色实体"""
        self.update_stats["characters_updated"] += 1

        # 更新情绪状态
        if random.random() < 0.05:  # 5%概率情绪波动
            character.mood = max(0.0, min(1.0, character.mood + random.uniform(-0.1, 0.1)))

    async def _trigger_autonomous_action(self, entity: Entity):
        """触发实体自主行动"""
        if entity.entity_type != EntityType.CHARACTER:
            return

        character = entity
        if not isinstance(character, CharacterEntity):
            return

        # 获取当前上下文
        context = {
            "time_phase": "day",  # TODO: 从时间系统获取
            "location_type": "general",  # TODO: 从位置系统获取
            "present_entities": self._get_present_entities(entity)
        }

        # 计算每个行动的概率
        action_probabilities = []
        for action in character.available_actions:
            probability = character.calculate_action_probability(action, context)
            if probability > 0.1:  # 只考虑概率大于10%的行动
                action_probabilities.append((action, probability))

        # 根据概率选择行动
        if action_probabilities:
            selected_action = self._weighted_random_select(action_probabilities)
            if selected_action:
                await self._execute_action(character, selected_action)

    def _get_present_entities(self, current_entity: Entity) -> List[str]:
        """获取当前实体周围的实体ID"""
        if not current_entity.current_location:
            return []

        present_entities = self.get_entities_in_location(current_entity.current_location)
        return [e.entity_id for e in present_entities if e.entity_id != current_entity.entity_id]

    def _weighted_random_select(self, items: List[tuple]) -> Optional[Any]:
        """加权随机选择"""
        if not items:
            return None

        total_weight = sum(prob for _, prob in items)
        if total_weight <= 0:
            return None

        rand_val = random.random() * total_weight
        current_weight = 0.0

        for item, weight in items:
            current_weight += weight
            if rand_val <= current_weight:
                return item

        return items[-1][0]

    async def _execute_action(self, entity: Entity, action: Action):
        """执行行动"""
        # 设置当前行动
        entity.current_action = action
        entity.last_action_time = datetime.utcnow()

        # 记录到活跃行动
        self.active_actions[action.action_id] = action

        # 记录记忆
        entity.remember({
            "type": "action_started",
            "action": action.action_type,
            "description": action.description
        })

        # 应用效果
        await self._apply_action_effects(entity, action)

        self.update_stats["actions_executed"] += 1
        self.logger.info(f"执行行动: {entity.name} - {action.description}")

    async def _apply_action_effects(self, entity: Entity, action: Action):
        """应用行动效果"""
        for effect in action.effects:
            effect_type = effect.get("type")

            if effect_type == "relationship_change":
                target_id = effect.get("target_id")
                change = effect.get("change", 0.0)
                if target_id and entity.entity_id in self.entities:
                    current = entity.get_relationship(target_id)
                    entity.add_relationship(target_id, current + change)

            elif effect_type == "energy_change":
                change = effect.get("change", 0.0)
                if hasattr(entity, 'energy'):
                    entity.energy = max(0.0, min(1.0, entity.energy + change))

            elif effect_type == "mood_change":
                change = effect.get("change", 0.0)
                if hasattr(entity, 'mood'):
                    entity.mood = max(0.0, min(1.0, entity.mood + change))

            # 其他效果类型...

    async def _process_action_queue(self, time_delta: timedelta):
        """处理行动队列"""
        # 检查已完成的行动
        completed_actions = []

        for action_id, action in self.active_actions.items():
            if action.entity_id in self.entities:
                entity = self.entities[action.entity_id]

                # 检查行动是否完成
                if entity.last_action_time:
                    elapsed = datetime.utcnow() - entity.last_action_time
                    if elapsed >= action.duration:
                        completed_actions.append(action_id)

                        # 清除当前行动
                        entity.current_action = None

                        # 记录完成记忆
                        entity.remember({
                            "type": "action_completed",
                            "action": action.action_type,
                            "description": f"完成行动: {action.description}"
                        })

        # 移除已完成的行动
        for action_id in completed_actions:
            if action_id in self.active_actions:
                del self.active_actions[action_id]

    def _update_statistics(self, update_start: datetime):
        """更新统计信息"""
        update_duration = (datetime.utcnow() - update_start).total_seconds()

        self.update_stats["total_updates"] += 1

        # 计算平均更新时间
        prev_avg = self.update_stats["avg_update_time"]
        total_updates = self.update_stats["total_updates"]
        new_avg = ((prev_avg * (total_updates - 1)) + update_duration) / total_updates
        self.update_stats["avg_update_time"] = new_avg

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.update_stats,
            "total_entities": len(self.entities),
            "total_characters": len(self.characters),
            "active_actions": len(self.active_actions),
            "action_queue_size": len(self.action_queue)
        }

    def create_character_from_data(self, character_data: Dict[str, Any]) -> CharacterEntity:
        """从数据创建角色实体"""
        # 创建Character对象
        character = Character(**character_data)

        # 创建CharacterEntity
        character_entity = CharacterEntity(character, self.config)

        # 添加默认行动
        character_entity.available_actions = self._create_default_actions(character_entity)

        # 添加默认目标
        character_entity.goals = self._create_default_goals(character_entity)

        return character_entity

    def _create_default_actions(self, character: CharacterEntity) -> List[Action]:
        """创建默认行动"""
        actions = [
            Action(
                action_id=f"{character.entity_id}_social",
                action_type="social_interaction",
                entity_id=character.entity_id,
                priority=ActionPriority.NORMAL,
                description="与他人互动"
            ),
            Action(
                action_id=f"{character.entity_id}_explore",
                action_type="exploration",
                entity_id=character.entity_id,
                priority=ActionPriority.LOW,
                description="探索周围环境"
            ),
            Action(
                action_id=f"{character.entity_id}_rest",
                action_type="rest",
                entity_id=character.entity_id,
                priority=ActionPriority.NORMAL,
                description="休息恢复精力"
            ),
        ]

        return actions

    def _create_default_goals(self, character: CharacterEntity) -> List[Goal]:
        """创建默认目标"""
        goals = [
            Goal(
                goal_id=f"{character.entity_id}_survive",
                entity_id=character.entity_id,
                goal_type="survival",
                description="保持生存和健康",
                importance=0.9,
                related_actions=["social", "explore", "rest"]
            ),
            Goal(
                goal_id=f"{character.entity_id}_social",
                entity_id=character.entity_id,
                goal_type="social",
                description="建立和维护社交关系",
                importance=character.social_openness,
                related_actions=["social"]
            ),
        ]

        return goals