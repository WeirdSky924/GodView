"""
上帝视角干预系统
v5.2 功能：允许用户以"上帝视角"干预世界发展
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.models.world import World
from app.services.entity_system import EntitySystem
from app.services.event_system import EventSystem
from app.services.time_system import TimeSystem

logger = logging.getLogger(__name__)


class InterventionType(str, Enum):
    """干预类型枚举"""
    CHARACTER_MODIFY = "character_modify"  # 修改角色属性
    RELATIONSHIP_CHANGE = "relationship_change"  # 改变关系
    EVENT_TRIGGER = "event_trigger"  # 触发事件
    ENVIRONMENT_CHANGE = "environment_change"  # 改变环境
    TIME_MANIPULATION = "time_manipulation"  # 时间操作
    PLOT_DIRECTION = "plot_direction"  # 剧情导向
    WORLD_RULE_CHANGE = "world_rule_change"  # 改变世界规则


class InterventionScope(str, Enum):
    """干预范围枚举"""
    GLOBAL = "global"  # 全局影响
    LOCAL = "local"  # 局部影响
    CHARACTER = "character"  # 角色影响
    LOCATION = "location"  # 地点影响
    EVENT = "event"  # 事件影响


class Intervention:
    """干预类"""

    def __init__(
        self,
        intervention_type: InterventionType,
        scope: InterventionScope,
        target_id: str,
        parameters: Dict[str, Any],
        description: str,
        priority: int = 1,
        immediate: bool = False,
    ):
        self.id = f"intervention_{uuid.uuid4().hex[:12]}"
        self.type = intervention_type
        self.scope = scope
        self.target_id = target_id
        self.parameters = parameters
        self.description = description
        self.priority = priority
        self.immediate = immediate
        self.created_at = datetime.utcnow()
        self.executed_at: Optional[datetime] = None
        self.status = "pending"  # pending, executing, completed, failed
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None


class InterventionSystem:
    """上帝视角干预系统"""

    def __init__(
        self,
        world_simulation,
        entity_system: EntitySystem,
        event_system: EventSystem,
        time_system: TimeSystem,
    ):
        self.world_simulation = world_simulation
        self.entity_system = entity_system
        self.event_system = event_system
        self.time_system = time_system
        self.pending_interventions: List[Intervention] = []
        self.completed_interventions: List[Intervention] = []
        self.intervention_history: List[Dict[str, Any]] = []

        logger.info("上帝视角干预系统初始化完成")

    async def create_intervention(
        self,
        intervention_type: InterventionType,
        scope: InterventionScope,
        target_id: str,
        parameters: Dict[str, Any],
        description: str,
        priority: int = 1,
        immediate: bool = False,
    ) -> Intervention:
        """创建干预"""

        intervention = Intervention(
            intervention_type=intervention_type,
            scope=scope,
            target_id=target_id,
            parameters=parameters,
            description=description,
            priority=priority,
            immediate=immediate,
        )

        self.pending_interventions.append(intervention)
        self.pending_interventions.sort(key=lambda x: x.priority, reverse=True)

        logger.info(f"创建干预: {intervention.id} - {intervention_type} - {description}")

        if immediate:
            await self.execute_intervention(intervention)

        return intervention

    async def execute_intervention(self, intervention: Intervention) -> Dict[str, Any]:
        """执行干预"""

        intervention.status = "executing"
        intervention.executed_at = datetime.utcnow()

        try:
            logger.info(f"执行干预: {intervention.id}")

            # 根据干预类型执行不同逻辑
            if intervention.type == InterventionType.CHARACTER_MODIFY:
                result = await self._execute_character_modify(intervention)
            elif intervention.type == InterventionType.RELATIONSHIP_CHANGE:
                result = await self._execute_relationship_change(intervention)
            elif intervention.type == InterventionType.EVENT_TRIGGER:
                result = await self._execute_event_trigger(intervention)
            elif intervention.type == InterventionType.ENVIRONMENT_CHANGE:
                result = await self._execute_environment_change(intervention)
            elif intervention.type == InterventionType.TIME_MANIPULATION:
                result = await self._execute_time_manipulation(intervention)
            elif intervention.type == InterventionType.PLOT_DIRECTION:
                result = await self._execute_plot_direction(intervention)
            elif intervention.type == InterventionType.WORLD_RULE_CHANGE:
                result = await self._execute_world_rule_change(intervention)
            else:
                raise ValueError(f"未知的干预类型: {intervention.type}")

            intervention.status = "completed"
            intervention.result = result

            # 移动到已完成列表
            self.pending_interventions.remove(intervention)
            self.completed_interventions.append(intervention)

            # 记录历史
            self.intervention_history.append({
                "id": intervention.id,
                "type": intervention.type,
                "scope": intervention.scope,
                "description": intervention.description,
                "executed_at": intervention.executed_at,
                "result": result,
            })

            logger.info(f"干预执行完成: {intervention.id}")
            return result

        except Exception as e:
            intervention.status = "failed"
            intervention.error = str(e)
            logger.error(f"干预执行失败: {intervention.id} - {e}")
            raise

    async def _execute_character_modify(self, intervention: Intervention) -> Dict[str, Any]:
        """执行角色修改干预"""

        character_id = intervention.target_id
        parameters = intervention.parameters

        # 获取角色
        character = await self.entity_system.get_character(character_id)
        if not character:
            raise ValueError(f"角色不存在: {character_id}")

        # 应用修改
        modifications = []

        if "attributes" in parameters:
            for attr_name, attr_value in parameters["attributes"].items():
                old_value = getattr(character, attr_name, None)
                setattr(character, attr_name, attr_value)
                modifications.append({
                    "attribute": attr_name,
                    "old_value": old_value,
                    "new_value": attr_value,
                })

        if "inventory" in parameters:
            operation = parameters["inventory"].get("operation", "add")
            items = parameters["inventory"].get("items", [])

            if operation == "add":
                character.inventory.extend(items)
            elif operation == "remove":
                character.inventory = [item for item in character.inventory if item not in items]
            elif operation == "replace":
                character.inventory = items

            modifications.append({
                "inventory_operation": operation,
                "items": items,
            })

        if "goals" in parameters:
            character.goals = parameters["goals"]
            modifications.append({
                "goals_updated": len(parameters["goals"]),
            })

        if "location" in parameters:
            old_location = character.current_location
            character.current_location = parameters["location"]
            modifications.append({
                "location": {
                    "old": old_location,
                    "new": parameters["location"],
                }
            })

        # 保存修改
        await self.entity_system.update_character(character)

        return {
            "character_id": character_id,
            "modifications": modifications,
            "character_snapshot": character.model_dump(),
        }

    async def _execute_relationship_change(self, intervention: Intervention) -> Dict[str, Any]:
        """执行关系改变干预"""

        parameters = intervention.parameters
        character_a_id = parameters.get("character_a_id")
        character_b_id = parameters.get("character_b_id")
        relationship_type = parameters.get("relationship_type")
        strength_change = parameters.get("strength_change", 0)
        description_change = parameters.get("description_change")

        if not character_a_id or not character_b_id:
            raise ValueError("需要 character_a_id 和 character_b_id")

        # 获取角色
        character_a = await self.entity_system.get_character(character_a_id)
        character_b = await self.entity_system.get_character(character_b_id)

        if not character_a or not character_b:
            raise ValueError(f"角色不存在: {character_a_id} 或 {character_b_id}")

        # 修改关系
        # 这里需要根据实际的关系系统实现
        # 假设 entity_system 有 update_relationship 方法
        result = await self.entity_system.update_relationship(
            character_a_id=character_a_id,
            character_b_id=character_b_id,
            relationship_type=relationship_type,
            strength_change=strength_change,
            description_change=description_change,
        )

        return {
            "relationship_change": {
                "character_a": character_a_id,
                "character_b": character_b_id,
                "type": relationship_type,
                "strength_change": strength_change,
                "result": result,
            }
        }

    async def _execute_event_trigger(self, intervention: Intervention) -> Dict[str, Any]:
        """执行事件触发干预"""

        event_type = intervention.parameters.get("event_type")
        event_data = intervention.parameters.get("event_data", {})

        if not event_type:
            raise ValueError("需要 event_type 参数")

        # 创建自定义事件
        event = {
            "id": f"intervention_event_{uuid.uuid4().hex[:8]}",
            "type": event_type,
            "data": event_data,
            "triggered_by": "intervention",
            "intervention_id": intervention.id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 触发事件
        await self.event_system.trigger_custom_event(event)

        return {
            "event_triggered": {
                "event_id": event["id"],
                "event_type": event_type,
                "data": event_data,
            }
        }

    async def _execute_environment_change(self, intervention: Intervention) -> Dict[str, Any]:
        """执行环境改变干预"""

        location_id = intervention.target_id
        parameters = intervention.parameters

        # 获取地点
        location = await self.entity_system.get_location(location_id)
        if not location:
            raise ValueError(f"地点不存在: {location_id}")

        # 修改环境参数
        modifications = []

        if "weather" in parameters:
            old_weather = location.environment.get("weather") if hasattr(location, "environment") else None
            if hasattr(location, "environment"):
                location.environment["weather"] = parameters["weather"]
            modifications.append({
                "weather": {
                    "old": old_weather,
                    "new": parameters["weather"],
                }
            })

        if "temperature" in parameters:
            old_temp = location.environment.get("temperature") if hasattr(location, "environment") else None
            if hasattr(location, "environment"):
                location.environment["temperature"] = parameters["temperature"]
            modifications.append({
                "temperature": {
                    "old": old_temp,
                    "new": parameters["temperature"],
                }
            })

        if "light_level" in parameters:
            old_light = location.environment.get("light_level") if hasattr(location, "environment") else None
            if hasattr(location, "environment"):
                location.environment["light_level"] = parameters["light_level"]
            modifications.append({
                "light_level": {
                    "old": old_light,
                    "new": parameters["light_level"],
                }
            })

        if "safety_level" in parameters:
            old_safety = location.environment.get("safety_level") if hasattr(location, "environment") else None
            if hasattr(location, "environment"):
                location.environment["safety_level"] = parameters["safety_level"]
            modifications.append({
                "safety_level": {
                    "old": old_safety,
                    "new": parameters["safety_level"],
                }
            })

        # 保存修改
        await self.entity_system.update_location(location)

        return {
            "location_id": location_id,
            "modifications": modifications,
            "location_snapshot": location.model_dump() if hasattr(location, "model_dump") else vars(location),
        }

    async def _execute_time_manipulation(self, intervention: Intervention) -> Dict[str, Any]:
        """执行时间操作干预"""

        operation = intervention.parameters.get("operation")
        amount = intervention.parameters.get("amount")

        if operation == "jump_forward":
            # 向前跳跃时间
            await self.time_system.jump_forward(amount)
            return {
                "time_operation": "jump_forward",
                "amount": amount,
                "new_time": self.time_system.get_current_time(),
            }

        elif operation == "jump_backward":
            # 向后跳跃时间
            await self.time_system.jump_backward(amount)
            return {
                "time_operation": "jump_backward",
                "amount": amount,
                "new_time": self.time_system.get_current_time(),
            }

        elif operation == "set_speed":
            # 设置时间流速
            await self.time_system.set_speed(amount)
            return {
                "time_operation": "set_speed",
                "speed": amount,
            }

        elif operation == "freeze":
            # 冻结时间
            await self.time_system.freeze()
            return {
                "time_operation": "freeze",
                "frozen": True,
            }

        elif operation == "unfreeze":
            # 解冻时间
            await self.time_system.unfreeze()
            return {
                "time_operation": "unfreeze",
                "frozen": False,
            }

        else:
            raise ValueError(f"未知的时间操作: {operation}")

    async def _execute_plot_direction(self, intervention: Intervention) -> Dict[str, Any]:
        """执行剧情导向干预"""

        direction = intervention.parameters.get("direction")
        intensity = intervention.parameters.get("intensity", 1.0)

        # 这里需要根据实际的剧情系统实现
        # 假设 world_simulation 有 influence_plot 方法
        result = await self.world_simulation.influence_plot(
            direction=direction,
            intensity=intensity,
            intervention_id=intervention.id,
        )

        return {
            "plot_direction": {
                "direction": direction,
                "intensity": intensity,
                "result": result,
            }
        }

    async def _execute_world_rule_change(self, intervention: Intervention) -> Dict[str, Any]:
        """执行世界规则改变干预"""

        rule_key = intervention.parameters.get("rule_key")
        rule_value = intervention.parameters.get("rule_value")

        if not rule_key:
            raise ValueError("需要 rule_key 参数")

        # 修改世界规则
        # 假设 world_simulation 有 update_world_rule 方法
        result = await self.world_simulation.update_world_rule(
            rule_key=rule_key,
            rule_value=rule_value,
            intervention_id=intervention.id,
        )

        return {
            "world_rule_change": {
                "rule_key": rule_key,
                "rule_value": rule_value,
                "result": result,
            }
        }

    async def get_pending_interventions(self) -> List[Intervention]:
        """获取待执行的干预"""
        return self.pending_interventions

    async def get_completed_interventions(self, limit: int = 50) -> List[Intervention]:
        """获取已完成的干预"""
        return self.completed_interventions[:limit]

    async def get_intervention_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取干预历史"""
        return self.intervention_history[:limit]

    async def cancel_intervention(self, intervention_id: str) -> bool:
        """取消干预"""

        for i, intervention in enumerate(self.pending_interventions):
            if intervention.id == intervention_id:
                intervention.status = "cancelled"
                self.pending_interventions.pop(i)
                self.completed_interventions.append(intervention)
                logger.info(f"干预已取消: {intervention_id}")
                return True

        return False

    async def get_intervention_by_id(self, intervention_id: str) -> Optional[Intervention]:
        """根据ID获取干预"""

        # 在待执行中查找
        for intervention in self.pending_interventions:
            if intervention.id == intervention_id:
                return intervention

        # 在已完成中查找
        for intervention in self.completed_interventions:
            if intervention.id == intervention_id:
                return intervention

        return None

    async def process_pending_interventions(self):
        """处理所有待执行的干预"""

        interventions_to_execute = [i for i in self.pending_interventions if i.immediate]

        for intervention in interventions_to_execute:
            try:
                await self.execute_intervention(intervention)
            except Exception as e:
                logger.error(f"处理干预失败: {intervention.id} - {e}")
                intervention.status = "failed"
                intervention.error = str(e)

    async def analyze_intervention_impact(self, intervention: Intervention) -> Dict[str, Any]:
        """分析干预的影响"""

        # 这里可以实现影响分析逻辑
        # 例如：预测干预可能带来的连锁反应

        impact_analysis = {
            "direct_impact": {
                "target": intervention.target_id,
                "scope": intervention.scope,
                "type": intervention.type,
            },
            "potential_chain_reactions": [],
            "risk_assessment": "low",  # low, medium, high
            "recommendations": [],
        }

        # 根据干预类型添加特定分析
        if intervention.type == InterventionType.CHARACTER_MODIFY:
            impact_analysis["potential_chain_reactions"].append("角色关系可能发生变化")
            impact_analysis["potential_chain_reactions"].append("角色行为模式可能改变")
            impact_analysis["risk_assessment"] = "medium"
            impact_analysis["recommendations"].append("建议监控相关角色的后续行为")

        elif intervention.type == InterventionType.EVENT_TRIGGER:
            impact_analysis["potential_chain_reactions"].append("可能触发连锁事件")
            impact_analysis["potential_chain_reactions"].append("可能影响多个角色的状态")
            impact_analysis["risk_assessment"] = "high"
            impact_analysis["recommendations"].append("建议准备应对可能的意外后果")

        elif intervention.type == InterventionType.TIME_MANIPULATION:
            impact_analysis["potential_chain_reactions"].append("时间线可能产生分支")
            impact_analysis["potential_chain_reactions"].append("记忆系统需要同步更新")
            impact_analysis["risk_assessment"] = "high"
            impact_analysis["recommendations"].append("建议创建时间快照以便回滚")

        return impact_analysis