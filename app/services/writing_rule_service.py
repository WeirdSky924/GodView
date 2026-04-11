"""
写作规则服务层
管理写作规则、规则集和项目写作配置
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.writing_rule import (
    WritingRuleCategory,
    RuleSeverity,
    WritingRule,
    WritingRuleCreate,
    WritingRuleUpdate,
    WritingRuleSet,
    WritingRuleSetCreate,
    WritingRuleSetUpdate,
    ProjectWritingConfig,
    ProjectWritingConfigUpdate,
)

logger = logging.getLogger(__name__)


class WritingRuleService:
    """写作规则服务"""

    def __init__(self):
        # 内存存储（生产环境应使用数据库）
        self._rules: Dict[str, WritingRule] = {}
        self._rule_sets: Dict[str, WritingRuleSet] = {}
        self._project_configs: Dict[str, ProjectWritingConfig] = {}

    # ==================== WritingRule CRUD ====================

    async def get_rule(self, rule_id: str) -> Optional[WritingRule]:
        """获取写作规则"""
        return self._rules.get(rule_id)

    async def list_rules(
        self,
        category: Optional[WritingRuleCategory] = None,
        severity: Optional[RuleSeverity] = None,
        tags: Optional[List[str]] = None,
        is_system: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WritingRule]:
        """获取写作规则列表（支持过滤）"""
        rules = list(self._rules.values())

        # 按分类过滤
        if category:
            rules = [r for r in rules if r.category == category]

        # 按严重程度过滤
        if severity:
            rules = [r for r in rules if r.severity == severity]

        # 按系统内置过滤
        if is_system is not None:
            rules = [r for r in rules if r.is_system == is_system]

        # 按标签过滤（任一匹配）
        if tags:
            rules = [r for r in rules if any(tag in r.tags for tag in tags)]

        # 搜索
        if search:
            search_lower = search.lower()
            rules = [
                r for r in rules
                if (search_lower in r.name.lower() or
                    search_lower in r.description.lower() or
                    search_lower in r.content.lower())
            ]

        # 排序：按严重程度（required > strong > recommended > optional > info），然后按使用次数降序
        severity_order = {
            RuleSeverity.REQUIRED: 5,
            RuleSeverity.STRONG: 4,
            RuleSeverity.RECOMMENDED: 3,
            RuleSeverity.OPTIONAL: 2,
            RuleSeverity.INFO: 1,
        }
        rules.sort(key=lambda x: (-severity_order.get(x.severity, 0), -x.usage_count))

        # 分页
        start = offset
        end = start + limit
        return rules[start:end]

    async def create_rule(self, dto: WritingRuleCreate) -> WritingRule:
        """创建写作规则"""
        rule_id = f"writing_rule_{uuid.uuid4().hex[:12]}"

        rule = WritingRule(
            id=rule_id,
            name=dto.name,
            description=dto.description,
            category=dto.category,
            severity=dto.severity,
            tags=dto.tags,
            content=dto.content,
            examples=dto.examples,
            counter_examples=dto.counter_examples,
            conditions=dto.conditions,
            exceptions=dto.exceptions,
            author=dto.author,
            source=dto.source,
            is_system=dto.is_system,
        )

        self._rules[rule_id] = rule
        logger.info(f"创建 WritingRule: {rule_id} - {rule.name}")

        return rule

    async def update_rule(
        self, rule_id: str, dto: WritingRuleUpdate
    ) -> tuple[Optional[WritingRule], Optional[str]]:
        """
        更新写作规则

        Returns:
            tuple: (规则, 错误类型) 错误类型为 'not_found' 或 'is_system' 或 None
        """
        rule = self._rules.get(rule_id)
        if not rule:
            return None, 'not_found'

        # 系统内置规则不可更新
        if rule.is_system:
            logger.warning(f"尝试更新系统内置规则 {rule_id}，操作被拒绝")
            return None, 'is_system'

        # 更新字段
        update_data = dto.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(rule, field, value)

        rule.updated_at = datetime.now()
        logger.info(f"更新 WritingRule: {rule_id}")

        return rule, None

    async def delete_rule(self, rule_id: str) -> tuple[bool, Optional[str]]:
        """
        删除写作规则

        Returns:
            tuple: (是否成功, 错误类型) 错误类型为 'not_found' 或 'is_system' 或 'in_use' 或 None
        """
        rule = self._rules.get(rule_id)
        if not rule:
            return False, 'not_found'

        # 系统内置规则不可删除
        if rule.is_system:
            logger.warning(f"尝试删除系统内置规则 {rule_id}，操作被拒绝")
            return False, 'is_system'

        # 检查是否有规则集引用此规则
        for rule_set in self._rule_sets.values():
            if rule_id in rule_set.rule_ids:
                logger.warning(f"规则 {rule_id} 被规则集 {rule_set.id} 引用，无法删除")
                return False, 'in_use'

        del self._rules[rule_id]
        logger.info(f"删除 WritingRule: {rule_id}")
        return True, None

    # ==================== WritingRuleSet CRUD ====================

    async def get_rule_set(self, rule_set_id: str) -> Optional[WritingRuleSet]:
        """获取写作规则集"""
        return self._rule_sets.get(rule_set_id)

    async def list_rule_sets(
        self,
        category: Optional[WritingRuleCategory] = None,
        tags: Optional[List[str]] = None,
        target_genre: Optional[str] = None,
        is_system: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WritingRuleSet]:
        """列出写作规则集"""
        rule_sets = list(self._rule_sets.values())

        # 按分类过滤
        if category:
            rule_sets = [rs for rs in rule_sets if rs.category == category]

        # 按标签过滤
        if tags:
            rule_sets = [rs for rs in rule_sets if any(tag in rs.tags for tag in tags)]

        # 按目标体裁过滤
        if target_genre:
            rule_sets = [rs for rs in rule_sets if target_genre in rs.target_genres]

        # 按系统内置过滤
        if is_system is not None:
            rule_sets = [rs for rs in rule_sets if rs.is_system == is_system]

        # 排序：按使用次数降序，然后按创建时间倒序
        rule_sets.sort(key=lambda x: (-x.usage_count, -x.created_at.timestamp()))

        # 分页
        start = offset
        end = start + limit
        return rule_sets[start:end]

    async def create_rule_set(self, dto: WritingRuleSetCreate) -> WritingRuleSet:
        """创建写作规则集"""
        rule_set_id = f"writing_rule_set_{uuid.uuid4().hex[:12]}"

        # 验证规则是否存在
        for rule_id in dto.rule_ids:
            if rule_id not in self._rules:
                logger.warning(f"规则 {rule_id} 不存在，将跳过")

        rule_set = WritingRuleSet(
            id=rule_set_id,
            name=dto.name,
            description=dto.description,
            rule_ids=dto.rule_ids,
            rule_overrides=dto.rule_overrides,
            category=dto.category,
            tags=dto.tags,
            target_genres=dto.target_genres,
            author=dto.author,
            is_system=dto.is_system,
        )

        self._rule_sets[rule_set_id] = rule_set
        logger.info(f"创建 WritingRuleSet: {rule_set_id} - {rule_set.name}")

        return rule_set

    # ==================== ProjectWritingConfig 管理 ====================

    async def get_project_writing_config(
        self, project_id: str
    ) -> Optional[ProjectWritingConfig]:
        """获取项目写作配置"""
        for config in self._project_configs.values():
            if config.project_id == project_id:
                return config
        return None

    async def update_project_writing_config(
        self, project_id: str, dto: ProjectWritingConfigUpdate
    ) -> Optional[ProjectWritingConfig]:
        """更新项目写作配置"""
        # 查找现有配置
        config = None
        config_id = None
        for cid, cfg in self._project_configs.items():
            if cfg.project_id == project_id:
                config = cfg
                config_id = cid
                break

        # 如果不存在，创建新配置
        if not config:
            config_id = f"writing_cfg_{uuid.uuid4().hex[:12]}"
            config = ProjectWritingConfig(
                id=config_id,
                project_id=project_id,
            )
            self._project_configs[config_id] = config

        # 更新字段
        update_data = dto.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(config, field, value)

        config.updated_at = datetime.now()
        logger.info(f"更新 ProjectWritingConfig: {config_id} for project {project_id}")

        return config

    # ==================== Prompt 构建 ====================

    async def build_writing_prompt(
        self,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建写作规则 prompt"""
        # 获取项目配置
        config = await self.get_project_writing_config(project_id)
        if not config or not config.is_active:
            return ""

        # 获取所有启用的规则
        enabled_rules = await self._get_enabled_rules(config)
        if not enabled_rules:
            return ""

        # 按优先级排序
        sorted_rules = self._sort_rules_by_priority(enabled_rules, config)

        # 构建 prompt 片段
        prompt_pieces = []
        for rule in sorted_rules:
            # 获取规则覆盖配置
            rule_override = config.rule_overrides.get(rule.id, {})
            severity = rule_override.get("severity", rule.severity)

            # 构建规则描述
            rule_prompt = self._build_rule_prompt(rule, severity, context)
            if rule_prompt:
                prompt_pieces.append(rule_prompt)

        # 合并所有片段
        if not prompt_pieces:
            return ""

        prompt_header = "请遵循以下写作规则：\n\n"
        return prompt_header + "\n\n".join(prompt_pieces)

    async def _get_enabled_rules(
        self, config: ProjectWritingConfig
    ) -> List[WritingRule]:
        """获取所有启用的规则"""
        enabled_rules = []

        # 从直接启用的规则中获取
        for rule_id in config.enabled_rule_ids:
            rule = self._rules.get(rule_id)
            if rule:
                enabled_rules.append(rule)

        # 从规则集中获取规则
        for rule_set_id in config.enabled_rule_set_ids:
            rule_set = self._rule_sets.get(rule_set_id)
            if not rule_set:
                continue

            for rule_id in rule_set.rule_ids:
                # 检查是否已添加
                if any(r.id == rule_id for r in enabled_rules):
                    continue

                rule = self._rules.get(rule_id)
                if rule:
                    # 应用规则集级别的覆盖
                    rule_copy = self._apply_rule_overrides(rule, rule_set.rule_overrides.get(rule_id, {}))
                    enabled_rules.append(rule_copy)

        return enabled_rules

    def _sort_rules_by_priority(
        self, rules: List[WritingRule], config: ProjectWritingConfig
    ) -> List[WritingRule]:
        """按优先级排序规则"""
        # 获取优先级配置
        rule_priorities = config.rule_priorities

        # 排序：先按配置的优先级，然后按严重程度
        def sort_key(rule: WritingRule) -> tuple:
            # 优先级（数值越大优先级越高）
            priority = rule_priorities.get(rule.id, 50)
            # 严重程度（required > strong > recommended > optional > info）
            severity_order = {
                RuleSeverity.REQUIRED: 5,
                RuleSeverity.STRONG: 4,
                RuleSeverity.RECOMMENDED: 3,
                RuleSeverity.OPTIONAL: 2,
                RuleSeverity.INFO: 1,
            }
            severity = severity_order.get(rule.severity, 0)
            return (-priority, -severity)

        return sorted(rules, key=sort_key)

    def _apply_rule_overrides(
        self, rule: WritingRule, overrides: Dict[str, Any]
    ) -> WritingRule:
        """应用规则覆盖配置"""
        if not overrides:
            return rule

        # 创建规则副本
        rule_dict = rule.dict()
        for key, value in overrides.items():
            if key in rule_dict and value is not None:
                rule_dict[key] = value

        return WritingRule(**rule_dict)

    def _build_rule_prompt(
        self,
        rule: WritingRule,
        severity: RuleSeverity,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建单个规则的 prompt"""
        # 严重程度标签
        severity_labels = {
            RuleSeverity.REQUIRED: "[必须遵守]",
            RuleSeverity.STRONG: "[强烈建议]",
            RuleSeverity.RECOMMENDED: "[推荐]",
            RuleSeverity.OPTIONAL: "[可选]",
            RuleSeverity.INFO: "[参考]",
        }
        severity_label = severity_labels.get(severity, "")

        # 构建规则内容
        rule_content = f"{severity_label} {rule.name}: {rule.content}"

        # 添加示例
        if rule.examples:
            example_text = "\n".join([f"- {example}" for example in rule.examples[:3]])
            rule_content += f"\n示例：\n{example_text}"

        # 添加应用条件
        if rule.conditions and context:
            # 这里可以添加条件判断逻辑
            pass

        return rule_content

    # ==================== 使用统计 ====================

    async def record_rule_usage(self, rule_id: str):
        """记录规则使用次数"""
        rule = self._rules.get(rule_id)
        if not rule:
            return

        rule.usage_count += 1
        rule.last_used_at = datetime.now()
        rule.updated_at = datetime.now()

    async def record_rule_set_usage(self, rule_set_id: str):
        """记录规则集使用次数"""
        rule_set = self._rule_sets.get(rule_set_id)
        if not rule_set:
            return

        rule_set.usage_count += 1
        rule_set.last_used_at = datetime.now()
        rule_set.updated_at = datetime.now()

        # 同时记录规则集中所有规则的使用
        for rule_id in rule_set.rule_ids:
            await self.record_rule_usage(rule_id)

    # ==================== 系统初始化 ====================

    async def initialize_system_rules(self, rules: List[WritingRule]):
        """初始化系统内置规则"""
        for rule in rules:
            if rule.id not in self._rules:
                rule.is_system = True
                self._rules[rule.id] = rule
                logger.info(f"初始化系统内置 WritingRule: {rule.id}")

    async def initialize_system_rule_sets(self, rule_sets: List[WritingRuleSet]):
        """初始化系统内置规则集"""
        for rule_set in rule_sets:
            if rule_set.id not in self._rule_sets:
                rule_set.is_system = True
                self._rule_sets[rule_set.id] = rule_set
                logger.info(f"初始化系统内置 WritingRuleSet: {rule_set.id}")