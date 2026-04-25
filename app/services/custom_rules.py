"""
用户自定义规则系统
v5.3 功能：允许用户自定义世界运行规则
"""

import logging
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
from pydantic import BaseModel, ConfigDict, Field, validator

logger = logging.getLogger(__name__)


class RuleType(str, Enum):
    """规则类型枚举"""
    BEHAVIOR = "behavior"  # 行为规则
    RELATIONSHIP = "relationship"  # 关系规则
    EVENT = "event"  # 事件规则
    WORLD = "world"  # 世界规则
    CHARACTER = "character"  # 角色规则
    PLOT = "plot"  # 剧情规则


class RuleCondition(BaseModel):
    """规则条件"""

    field: str
    operator: str  # eq, ne, gt, lt, contains, matches
    value: Any
    logical_op: Optional[str] = "and"  # 逻辑操作符：and, or

    model_config = ConfigDict(arbitrary_types_allowed=True)


class RuleAction(BaseModel):
    """规则动作"""

    action_type: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    delay: Optional[int] = 0  # 延迟执行（时间单位）


class CustomRule(BaseModel):
    """自定义规则"""

    id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:12]}")
    name: str
    description: Optional[str] = None
    rule_type: RuleType
    priority: int = 1  # 1-10，数字越大优先级越高
    enabled: bool = True
    conditions: List[RuleCondition] = Field(default_factory=list)
    actions: List[RuleAction] = Field(default_factory=list)
    trigger_count: int = 0
    last_triggered: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @validator("priority")
    def validate_priority(cls, v):
        if v < 1 or v > 10:
            raise ValueError("优先级必须在 1-10 之间")
        return v


class RuleEvaluationContext(BaseModel):
    """规则评估上下文"""

    world_state: Dict[str, Any] = Field(default_factory=dict)
    character_states: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    relationships: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    current_events: List[Dict[str, Any]] = Field(default_factory=list)
    time_info: Dict[str, Any] = Field(default_factory=dict)
    custom_data: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CustomRulesSystem:
    """用户自定义规则系统"""

    def __init__(self):
        self.rules: Dict[str, CustomRule] = {}
        self.rule_groups: Dict[str, List[str]] = {}
        self.rule_history: List[Dict[str, Any]] = []
        self.condition_evaluators = self._initialize_condition_evaluators()
        self.action_executors = self._initialize_action_executors()

        logger.info("用户自定义规则系统初始化完成")

    def _initialize_condition_evaluators(self) -> Dict[str, Callable]:
        """初始化条件评估器"""

        return {
            "eq": lambda field_value, rule_value: field_value == rule_value,
            "ne": lambda field_value, rule_value: field_value != rule_value,
            "gt": lambda field_value, rule_value: field_value > rule_value,
            "lt": lambda field_value, rule_value: field_value < rule_value,
            "ge": lambda field_value, rule_value: field_value >= rule_value,
            "le": lambda field_value, rule_value: field_value <= rule_value,
            "contains": lambda field_value, rule_value: rule_value in field_value if isinstance(field_value, (str, list, dict)) else False,
            "matches": lambda field_value, rule_value: bool(re.match(rule_value, str(field_value))) if isinstance(rule_value, str) else False,
            "in": lambda field_value, rule_value: field_value in rule_value if isinstance(rule_value, (list, tuple, set)) else False,
            "not_in": lambda field_value, rule_value: field_value not in rule_value if isinstance(rule_value, (list, tuple, set)) else False,
            "starts_with": lambda field_value, rule_value: str(field_value).startswith(str(rule_value)),
            "ends_with": lambda field_value, rule_value: str(field_value).endswith(str(rule_value)),
        }

    def _initialize_action_executors(self) -> Dict[str, Callable]:
        """初始化动作执行器"""

        return {
            "modify_character": self._execute_modify_character,
            "trigger_event": self._execute_trigger_event,
            "change_relationship": self._execute_change_relationship,
            "send_notification": self._execute_send_notification,
            "log_message": self._execute_log_message,
            "call_webhook": self._execute_call_webhook,
            "modify_world_state": self._execute_modify_world_state,
        }

    def create_rule(self, rule_data: Dict[str, Any]) -> CustomRule:
        """创建规则"""

        # 确保ID唯一
        if "id" in rule_data:
            if rule_data["id"] in self.rules:
                raise ValueError(f"规则ID已存在: {rule_data['id']}")
        else:
            rule_data["id"] = f"rule_{uuid.uuid4().hex[:12]}"

        # 创建规则对象
        rule = CustomRule(**rule_data)
        self.rules[rule.id] = rule

        logger.info(f"规则创建成功: {rule.id} - {rule.name}")
        return rule

    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> Optional[CustomRule]:
        """更新规则"""

        if rule_id not in self.rules:
            return None

        rule = self.rules[rule_id]

        # 更新字段
        update_data = updates.copy()
        update_data["updated_at"] = datetime.utcnow()

        # 创建新规则对象（保留不可变字段）
        updated_rule = rule.copy(update=update_data)
        self.rules[rule_id] = updated_rule

        logger.info(f"规则更新成功: {rule_id}")
        return updated_rule

    def delete_rule(self, rule_id: str) -> bool:
        """删除规则"""

        if rule_id in self.rules:
            del self.rules[rule_id]

            # 从所有组中移除
            for group_name, rule_ids in self.rule_groups.items():
                if rule_id in rule_ids:
                    rule_ids.remove(rule_id)

            logger.info(f"规则删除成功: {rule_id}")
            return True

        return False

    def get_rule(self, rule_id: str) -> Optional[CustomRule]:
        """获取规则"""

        return self.rules.get(rule_id)

    def get_rules_by_type(self, rule_type: RuleType) -> List[CustomRule]:
        """根据类型获取规则"""

        return [rule for rule in self.rules.values() if rule.rule_type == rule_type and rule.enabled]

    def evaluate_conditions(
        self,
        conditions: List[RuleCondition],
        context: RuleEvaluationContext,
    ) -> bool:
        """评估条件是否满足"""

        if not conditions:
            return True

        import re  # 用于正则匹配

        result = True
        logical_op = "and"

        for condition in conditions:
            # 获取字段值
            field_path = condition.field.split(".")
            field_value = self._get_nested_value(context.dict(), field_path)

            # 获取评估函数
            evaluator = self.condition_evaluators.get(condition.operator)
            if not evaluator:
                logger.warning(f"未知的条件操作符: {condition.operator}")
                condition_result = False
            else:
                # 评估条件
                try:
                    condition_result = evaluator(field_value, condition.value)
                except Exception as e:
                    logger.error(f"条件评估失败: {condition.field} {condition.operator} {condition.value} - {e}")
                    condition_result = False

            # 应用逻辑操作符
            if condition.logical_op:
                logical_op = condition.logical_op

            if logical_op == "and":
                result = result and condition_result
                if not result:  # 短路优化
                    break
            elif logical_op == "or":
                result = result or condition_result
                if result:  # 短路优化
                    break

        return result

    def _get_nested_value(self, obj: Dict[str, Any], path: List[str]) -> Any:
        """获取嵌套字段值"""

        current = obj
        for key in path:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None

            if current is None:
                return None

        return current

    async def evaluate_and_execute_rules(
        self,
        context: RuleEvaluationContext,
        rule_type: Optional[RuleType] = None,
    ) -> Dict[str, Any]:
        """评估并执行规则"""

        # 获取相关规则
        if rule_type:
            relevant_rules = self.get_rules_by_type(rule_type)
        else:
            relevant_rules = [rule for rule in self.rules.values() if rule.enabled]

        # 按优先级排序
        relevant_rules.sort(key=lambda r: r.priority, reverse=True)

        executed_rules = []
        execution_results = []

        for rule in relevant_rules:
            # 评估条件
            conditions_met = self.evaluate_conditions(rule.conditions, context)

            if conditions_met:
                # 执行动作
                rule_results = await self.execute_rule_actions(rule, context)

                # 更新规则状态
                rule.trigger_count += 1
                rule.last_triggered = datetime.utcnow()

                executed_rules.append(rule.id)
                execution_results.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "results": rule_results,
                })

                # 记录历史
                self.rule_history.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "context": context.dict(),
                    "executed_at": datetime.utcnow(),
                    "results": rule_results,
                })

                logger.info(f"规则触发执行: {rule.id} - {rule.name}")

        return {
            "executed_rule_ids": executed_rules,
            "execution_results": execution_results,
            "total_evaluated": len(relevant_rules),
            "total_executed": len(executed_rules),
        }

    async def execute_rule_actions(self, rule: CustomRule, context: RuleEvaluationContext) -> List[Dict[str, Any]]:
        """执行规则动作"""

        results = []

        for action in rule.actions:
            # 查找动作执行器
            executor = self.action_executors.get(action.action_type)

            if executor:
                try:
                    # 执行动作
                    result = await executor(action, context)
                    results.append({
                        "action_type": action.action_type,
                        "success": True,
                        "result": result,
                    })
                except Exception as e:
                    logger.error(f"动作执行失败: {action.action_type} - {e}")
                    results.append({
                        "action_type": action.action_type,
                        "success": False,
                        "error": str(e),
                    })
            else:
                logger.warning(f"未知的动作类型: {action.action_type}")
                results.append({
                    "action_type": action.action_type,
                    "success": False,
                    "error": f"未知的动作类型: {action.action_type}",
                })

        return results

    async def _execute_modify_character(
        self,
        action: RuleAction,
        context: RuleEvaluationContext,
    ) -> Dict[str, Any]:
        """执行修改角色动作"""

        character_id = action.target
        if not character_id:
            return {"error": "未指定角色ID"}

        parameters = action.parameters

        # 这里需要集成到实际的实体系统
        # 假设有修改角色的方法
        result = {
            "action": "modify_character",
            "character_id": character_id,
            "modifications": parameters,
        }

        return result

    async def _execute_trigger_event(
        self,
        action: RuleAction,
        context: RuleEvaluationContext,
    ) -> Dict[str, Any]:
        """执行触发事件动作"""

        event_type = action.parameters.get("event_type")
        event_data = action.parameters.get("event_data", {})

        if not event_type:
            return {"error": "未指定事件类型"}

        # 这里需要集成到实际的事件系统
        result = {
            "action": "trigger_event",
            "event_type": event_type,
            "event_data": event_data,
        }

        return result

    async def _execute_change_relationship(
        self,
        action: RuleAction,
        context: RuleEvaluationContext,
    ) -> Dict[str, Any]:
        """执行改变关系动作"""

        character_a = action.parameters.get("character_a")
        character_b = action.parameters.get("character_b")
        change = action.parameters.get("change", {})

        if not character_a or not character_b:
            return {"error": "未指定角色"}

        result = {
            "action": "change_relationship",
            "character_a": character_a,
            "character_b": character_b,
            "change": change,
        }

        return result

    async def _execute_send_notification(
        self,
        action: RuleAction,
        context: RuleEvaluationContext,
    ) -> Dict[str, Any]:
        """执行发送通知动作"""

        message = action.parameters.get("message", "规则触发通知")
        level = action.parameters.get("level", "info")

        # 记录日志
        logger.info(f"规则通知 [{level}]: {message}")

        return {
            "action": "send_notification",
            "message": message,
            "level": level,
        }

    async def _execute_log_message(
        self,
        action: RuleAction,
        context: RuleEvaluationContext,
    ) -> Dict[str, Any]:
        """执行记录日志动作"""

        message = action.parameters.get("message", "")
        metadata = action.parameters.get("metadata", {})

        # 记录到规则历史
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "metadata": metadata,
        }

        self.rule_history.append(log_entry)

        return {
            "action": "log_message",
            "logged": True,
            "log_entry": log_entry,
        }

    async def _execute_call_webhook(
        self,
        action: RuleAction,
        context: RuleEvaluationContext,
    ) -> Dict[str, Any]:
        """执行调用Webhook动作"""

        import aiohttp
        import asyncio

        url = action.parameters.get("url")
        method = action.parameters.get("method", "POST")
        payload = action.parameters.get("payload", {})
        headers = action.parameters.get("headers", {})

        if not url:
            return {"error": "未指定Webhook URL"}

        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "POST":
                    async with session.post(url, json=payload, headers=headers) as response:
                        result = {
                            "status": response.status,
                            "headers": dict(response.headers),
                            "body": await response.text(),
                        }
                elif method.upper() == "GET":
                    async with session.get(url, headers=headers) as response:
                        result = {
                            "status": response.status,
                            "headers": dict(response.headers),
                            "body": await response.text(),
                        }
                else:
                    return {"error": f"不支持的HTTP方法: {method}"}

            return {
                "action": "call_webhook",
                "success": True,
                "result": result,
            }

        except Exception as e:
            return {
                "action": "call_webhook",
                "success": False,
                "error": str(e),
            }

    async def _execute_modify_world_state(
        self,
        action: RuleAction,
        context: RuleEvaluationContext,
    ) -> Dict[str, Any]:
        """执行修改世界状态动作"""

        modifications = action.parameters.get("modifications", {})

        # 这里需要集成到实际的世界状态系统
        result = {
            "action": "modify_world_state",
            "modifications": modifications,
        }

        return result

    def create_rule_group(self, group_name: str, rule_ids: List[str]) -> bool:
        """创建规则组"""

        if group_name in self.rule_groups:
            return False

        # 验证规则ID
        valid_rule_ids = []
        for rule_id in rule_ids:
            if rule_id in self.rules:
                valid_rule_ids.append(rule_id)
            else:
                logger.warning(f"规则组创建时忽略不存在的规则ID: {rule_id}")

        self.rule_groups[group_name] = valid_rule_ids
        logger.info(f"规则组创建成功: {group_name} - {len(valid_rule_ids)} 个规则")

        return True

    def get_rule_group(self, group_name: str) -> Optional[List[CustomRule]]:
        """获取规则组"""

        rule_ids = self.rule_groups.get(group_name)
        if not rule_ids:
            return None

        rules = []
        for rule_id in rule_ids:
            rule = self.rules.get(rule_id)
            if rule:
                rules.append(rule)

        return rules

    def export_rules(self, rule_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """导出规则"""

        if rule_ids:
            rules_to_export = {}
            for rule_id in rule_ids:
                rule = self.rules.get(rule_id)
                if rule:
                    rules_to_export[rule_id] = rule.dict()
        else:
            rules_to_export = {rule_id: rule.dict() for rule_id, rule in self.rules.items()}

        return {
            "exported_at": datetime.utcnow().isoformat(),
            "total_rules": len(rules_to_export),
            "rules": rules_to_export,
            "rule_groups": self.rule_groups,
        }

    def import_rules(self, import_data: Dict[str, Any]) -> Dict[str, Any]:
        """导入规则"""

        imported_count = 0
        skipped_count = 0
        errors = []

        rules_data = import_data.get("rules", {})
        rule_groups = import_data.get("rule_groups", {})

        for rule_id, rule_data in rules_data.items():
            try:
                # 检查规则是否已存在
                if rule_id in self.rules:
                    logger.info(f"规则已存在，跳过导入: {rule_id}")
                    skipped_count += 1
                    continue

                # 创建规则
                rule = CustomRule(**rule_data)
                self.rules[rule_id] = rule
                imported_count += 1

            except Exception as e:
                errors.append(f"规则导入失败 {rule_id}: {str(e)}")

        # 导入规则组
        for group_name, rule_ids in rule_groups.items():
            if group_name not in self.rule_groups:
                self.rule_groups[group_name] = []
            for rule_id in rule_ids:
                if rule_id in self.rules and rule_id not in self.rule_groups[group_name]:
                    self.rule_groups[group_name].append(rule_id)

        logger.info(f"规则导入完成: {imported_count} 个新规则，{skipped_count} 个跳过")

        return {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "errors": errors,
        }

    def get_rule_statistics(self) -> Dict[str, Any]:
        """获取规则统计信息"""

        total_rules = len(self.rules)
        enabled_rules = sum(1 for rule in self.rules.values() if rule.enabled)
        disabled_rules = total_rules - enabled_rules

        # 按类型统计
        type_stats = {}
        for rule_type in RuleType:
            count = sum(1 for rule in self.rules.values() if rule.rule_type == rule_type)
            type_stats[rule_type.value] = count

        # 触发统计
        total_triggers = sum(rule.trigger_count for rule in self.rules.values())
        avg_triggers = total_triggers / total_rules if total_rules > 0 else 0

        # 最近触发的规则
        recent_triggers = sorted(
            [rule for rule in self.rules.values() if rule.last_triggered],
            key=lambda r: r.last_triggered or datetime.min,
            reverse=True
        )[:5]

        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "disabled_rules": disabled_rules,
            "type_statistics": type_stats,
            "trigger_statistics": {
                "total_triggers": total_triggers,
                "average_triggers": avg_triggers,
                "most_triggered": [
                    {
                        "rule_id": rule.id,
                        "name": rule.name,
                        "trigger_count": rule.trigger_count,
                    }
                    for rule in sorted(
                        self.rules.values(),
                        key=lambda r: r.trigger_count,
                        reverse=True
                    )[:3]
                ],
            },
            "recent_activity": [
                {
                    "rule_id": rule.id,
                    "name": rule.name,
                    "last_triggered": rule.last_triggered,
                    "trigger_count": rule.trigger_count,
                }
                for rule in recent_triggers
            ],
        }