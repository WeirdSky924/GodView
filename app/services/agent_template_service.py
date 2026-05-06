"""
Agent 模板服务层
管理 AgentTemplate 的创建、查询、更新等操作
支持数据库持久化
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.agent_template import (
    AgentType,
    PromptSlot,
    SkillSlot,
    AgentTemplate,
    AgentTemplateCreate,
    AgentTemplateUpdate,
)

logger = logging.getLogger(__name__)


class AgentTemplateService:
    """Agent 模板服务"""

    def __init__(self, db=None):
        """
        初始化 Agent 模板服务

        Args:
            db: 数据库连接（可选，用于持久化）
        """
        self._db = db
        self._templates: Dict[str, AgentTemplate] = {}
        self._cache_valid: bool = False

    async def _ensure_cache(self):
        """确保缓存有效"""
        if self._cache_valid:
            return

        if self._db:
            try:
                rows = await self._db.execute_query(
                    "SELECT * FROM agent_templates ORDER BY is_system DESC, created_at DESC"
                )
                for row in rows:
                    template = self._row_to_template(row)
                    self._templates[template.id] = template
                self._cache_valid = True
                logger.info(f"从数据库加载 {len(self._templates)} 个 Agent 模板")
            except Exception as e:
                logger.warning(f"从数据库加载 Agent 模板失败: {e}")

    def _row_to_template(self, row: Dict) -> AgentTemplate:
        """将数据库行转换为 AgentTemplate 对象"""
        prompt_slots = row.get('prompt_slots', [])
        if isinstance(prompt_slots, str):
            prompt_slots = json.loads(prompt_slots)

        skill_slots = row.get('skill_slots', [])
        if isinstance(skill_slots, str):
            skill_slots = json.loads(skill_slots)

        default_prompt_order = row.get('default_prompt_order', [])
        if isinstance(default_prompt_order, str):
            default_prompt_order = json.loads(default_prompt_order)

        default_skill_order = row.get('default_skill_order', [])
        if isinstance(default_skill_order, str):
            default_skill_order = json.loads(default_skill_order)

        tags = row.get('tags', [])
        if isinstance(tags, str):
            tags = json.loads(tags)

        return AgentTemplate(
            id=row['id'],
            name=row['name'],
            description=row.get('description', ''),
            agent_type=AgentType(row['agent_type']),
            scenario=row.get('scenario') or 'default',
            tags=tags,
            prompt_slots=[PromptSlot(**slot) for slot in prompt_slots],
            default_prompt_order=default_prompt_order,
            skill_slots=[SkillSlot(**slot) for slot in skill_slots],
            default_skill_order=default_skill_order,
            default_model=row.get('default_model'),
            default_temperature=float(row.get('default_temperature', 0.7)),
            is_system=row.get('is_system', False),
            is_optional=row.get('is_optional', False),
            is_enabled=row.get('is_enabled', True),
            version=row.get('version', '1.0.0'),
            created_at=row.get('created_at', datetime.now()),
            updated_at=row.get('updated_at', datetime.now()),
        )

    def _copy_template(self, template: AgentTemplate) -> AgentTemplate:
        """复制模板，避免合并运行时 assignment 时污染缓存对象。"""
        return template.model_copy(deep=True)

    async def _merge_skill_assignments(self, template: AgentTemplate) -> AgentTemplate:
        """
        将 skill_assignments 表中的分配关系合并到模板的 skill_slots 中

        这确保前端显示和运行时使用的 Skills 列表一致。

        Args:
            template: Agent 模板

        Returns:
            AgentTemplate: 合并后的模板
        """
        if not self._db:
            return self._copy_template(template)

        merged_template = self._copy_template(template)

        try:
            # 从 skill_assignments 表加载该 agent_type 的所有分配
            rows = await self._db.execute_query(
                """
                SELECT sa.skill_id, sa.slot_name, sa.priority, sa.is_enabled,
                       sa.is_required, sa.variable_overrides, sa.execution_condition,
                       s.name as skill_name, s.description as skill_description
                FROM skill_assignments sa
                JOIN skills s ON sa.skill_id = s.id
                WHERE sa.agent_type = :agent_type
                  AND sa.scenario = :scenario
                  AND sa.is_enabled = true
                  AND s.is_enabled = true
                  AND s.status = 'active'
                ORDER BY sa.priority DESC
                """,
                {
                    "agent_type": merged_template.agent_type.value,
                    "scenario": self._normalize_scenario(merged_template.scenario),
                }
            )

            if not rows and self._normalize_scenario(merged_template.scenario) != "default":
                rows = await self._db.execute_query(
                    """
                    SELECT sa.skill_id, sa.slot_name, sa.priority, sa.is_enabled,
                           sa.is_required, sa.variable_overrides, sa.execution_condition,
                           s.name as skill_name, s.description as skill_description
                    FROM skill_assignments sa
                    JOIN skills s ON sa.skill_id = s.id
                    WHERE sa.agent_type = :agent_type
                      AND sa.scenario = 'default'
                      AND sa.is_enabled = true
                      AND s.is_enabled = true
                      AND s.status = 'active'
                    ORDER BY sa.priority DESC
                    """,
                    {"agent_type": merged_template.agent_type.value}
                )
                if rows:
                    logger.warning(
                        "未找到 AgentTemplate 场景 Skill 分配，回退 default: agent_type=%s, scenario=%s, count=%s",
                        merged_template.agent_type.value,
                        self._normalize_scenario(merged_template.scenario),
                        len(rows),
                    )

            # 获取现有的 skill_slots 中的 skill_id 集合
            existing_skill_ids = {slot.skill_id for slot in merged_template.skill_slots if slot.skill_id}

            # 添加新的 skill_slots（不覆盖已存在的）
            for row in rows:
                if row['skill_id'] not in existing_skill_ids:
                    new_slot = SkillSlot(
                        slot_name=row['slot_name'] or row['skill_name'],
                        description=row['skill_description'] or '',
                        skill_id=row['skill_id'],
                        is_enabled=row['is_enabled'],
                        is_required=row['is_required'],
                        priority=row['priority'],
                        variable_overrides=row.get('variable_overrides', {}) or {},
                        execution_condition=row.get('execution_condition'),
                    )
                    merged_template.skill_slots.append(new_slot)
                    existing_skill_ids.add(row['skill_id'])

            # 按 priority 降序排列
            merged_template.skill_slots.sort(key=lambda x: -x.priority)

            logger.debug(f"模板 {merged_template.id} 合并了 {len(rows)} 个 skill_assignments，现有 {len(merged_template.skill_slots)} 个插槽")

        except Exception as e:
            logger.warning(f"合并 skill_assignments 失败: {e}")

        return merged_template
    def _template_to_db_dict(self, template: AgentTemplate) -> Dict[str, Any]:
        """将 AgentTemplate 对象转换为数据库字典"""
        return {
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'agent_type': template.agent_type.value,
            'scenario': template.scenario,
            'tags': json.dumps(template.tags),
            'prompt_slots': json.dumps([slot.dict() for slot in template.prompt_slots]),
            'default_prompt_order': json.dumps(template.default_prompt_order),
            'skill_slots': json.dumps([slot.dict() for slot in template.skill_slots]),
            'default_skill_order': json.dumps(template.default_skill_order),
            'default_model': template.default_model,
            'default_temperature': template.default_temperature,
            'is_system': template.is_system,
            'is_optional': template.is_optional,
            'is_enabled': template.is_enabled,
            'version': template.version,
            'updated_at': datetime.now(),
        }

    @staticmethod
    def _normalize_scenario(scenario: Optional[str]) -> str:
        """规范化 Agent 场景名称。"""
        scenario_value = (scenario or "default").strip()
        return scenario_value or "default"

    def invalidate_cache(self):
        """使缓存失效"""
        self._cache_valid = False
        self._templates.clear()

    def _sync_missing_slots_from_seed(self, existing: AgentTemplate, seed: AgentTemplate) -> bool:
        """从系统种子模板补齐缺失插槽，不覆盖已有绑定。"""
        changed = False

        if self._normalize_scenario(existing.scenario) == "default" and self._normalize_scenario(seed.scenario) != "default":
            existing.scenario = seed.scenario
            changed = True

        merged_tags = list(dict.fromkeys([*existing.tags, *seed.tags]))
        if merged_tags != existing.tags:
            existing.tags = merged_tags
            changed = True

        existing_prompt_slots = {slot.slot_name for slot in existing.prompt_slots}
        for slot in seed.prompt_slots:
            if slot.slot_name not in existing_prompt_slots:
                existing.prompt_slots.append(slot.model_copy(deep=True))
                existing_prompt_slots.add(slot.slot_name)
                changed = True

        seed_prompt_names = [slot.slot_name for slot in seed.prompt_slots]
        extra_prompt_order = [name for name in existing.default_prompt_order if name not in seed_prompt_names]
        new_prompt_order = [name for name in seed.default_prompt_order if name in existing_prompt_slots]
        new_prompt_order.extend(name for name in extra_prompt_order if name in existing_prompt_slots)
        if new_prompt_order and new_prompt_order != existing.default_prompt_order:
            existing.default_prompt_order = new_prompt_order
            changed = True

        existing_skill_slots = {slot.slot_name for slot in existing.skill_slots}
        for slot in seed.skill_slots:
            if slot.slot_name not in existing_skill_slots:
                existing.skill_slots.append(slot.model_copy(deep=True))
                existing_skill_slots.add(slot.slot_name)
                changed = True

        seed_skill_names = [slot.slot_name for slot in seed.skill_slots]
        extra_skill_order = [name for name in existing.default_skill_order if name not in seed_skill_names]
        new_skill_order = [name for name in seed.default_skill_order if name in existing_skill_slots]
        new_skill_order.extend(name for name in extra_skill_order if name in existing_skill_slots)
        if new_skill_order and new_skill_order != existing.default_skill_order:
            existing.default_skill_order = new_skill_order
            changed = True

        if changed:
            existing.updated_at = datetime.now()

        return changed

    # ==================== CRUD 操作 ====================

    async def create_template(self, dto: AgentTemplateCreate) -> AgentTemplate:
        """创建 Agent 模板"""
        await self._ensure_cache()

        template_id = f"agent_tmpl_{uuid.uuid4().hex[:12]}"

        template = AgentTemplate(
            id=template_id,
            name=dto.name,
            description=dto.description,
            agent_type=dto.agent_type,
            scenario=dto.scenario,
            tags=dto.tags or [],
            prompt_slots=dto.prompt_slots or [],
            default_prompt_order=dto.default_prompt_order or [],
            skill_slots=dto.skill_slots or [],
            default_model=dto.default_model,
            default_temperature=dto.default_temperature,
            is_system=dto.is_system or False,
            is_optional=dto.is_optional or False,
            is_enabled=dto.is_enabled,
        )

        # 保存到数据库
        if self._db:
            try:
                data = self._template_to_db_dict(template)
                columns = ', '.join(data.keys())
                placeholders = ', '.join([f':{k}' for k in data.keys()])

                await self._db.execute_write(
                    f"INSERT INTO agent_templates ({columns}) VALUES ({placeholders})",
                    data
                )
                logger.info(f"创建 AgentTemplate 到数据库: {template_id}")
            except Exception as e:
                logger.error(f"创建 AgentTemplate 到数据库失败: {e}")

        self._templates[template_id] = template
        return template

    async def get_template(self, template_id: str) -> Optional[AgentTemplate]:
        """获取 Agent 模板"""
        await self._ensure_cache()
        template = self._templates.get(template_id)
        if template:
            template = await self._merge_skill_assignments(template)
        return template

    async def get_template_by_type(
        self,
        agent_type: AgentType,
        scenario: Optional[str] = None,
    ) -> Optional[AgentTemplate]:
        """按 Agent 类型和场景获取 active 模板，数据库配置优先，系统种子仅作兜底。"""
        await self._ensure_cache()
        normalized_scenario = self._normalize_scenario(scenario)
        templates = [
            template
            for template in self._templates.values()
            if template.agent_type == agent_type and template.is_enabled
        ]

        def sort_key(template: AgentTemplate):
            return (
                template.is_system,
                -template.updated_at.timestamp(),
                -template.created_at.timestamp(),
            )

        for template in sorted(templates, key=sort_key):
            if self._normalize_scenario(template.scenario) == normalized_scenario:
                return await self._merge_skill_assignments(template)

        if normalized_scenario != "default":
            for template in sorted(templates, key=sort_key):
                if self._normalize_scenario(template.scenario) == "default":
                    logger.warning(
                        "未找到 AgentTemplate 场景模板，回退 default: agent_type=%s, scenario=%s, template=%s",
                        agent_type.value,
                        normalized_scenario,
                        template.id,
                    )
                    return await self._merge_skill_assignments(template)

        if templates:
            fallback = sorted(templates, key=sort_key)[0]
            if normalized_scenario != "default":
                logger.warning(
                    "未找到 AgentTemplate 场景模板，回退首个可用模板: agent_type=%s, scenario=%s, template=%s",
                    agent_type.value,
                    normalized_scenario,
                    fallback.id,
                )
            return await self._merge_skill_assignments(fallback)

        return None

    async def list_templates(
        self,
        agent_type: Optional[AgentType] = None,
        is_system: Optional[bool] = None,
        scenario: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
        merge_skill_assignments: bool = True,
    ) -> List[AgentTemplate]:
        """获取 Agent 模板列表"""
        await self._ensure_cache()
        templates = list(self._templates.values())

        # 按类型过滤
        if agent_type:
            templates = [t for t in templates if t.agent_type == agent_type]

        # 按场景过滤
        if scenario:
            normalized_scenario = self._normalize_scenario(scenario)
            templates = [t for t in templates if self._normalize_scenario(t.scenario) == normalized_scenario]

        # 按系统内置过滤
        if is_system is not None:
            templates = [t for t in templates if t.is_system == is_system]

        # 按标签过滤（任一匹配）
        if tags:
            tag_set = set(tags)
            templates = [t for t in templates if tag_set.intersection(t.tags)]

        # 排序：系统模板优先，然后按场景和创建时间倒序
        templates.sort(key=lambda x: (-x.is_system, x.scenario, -x.created_at.timestamp()))

        # 分页
        start = max(offset, 0)
        end = start + limit if limit and limit > 0 else None
        result = templates[start:end]

        # 合并 skill_assignments
        if merge_skill_assignments and self._db:
            result = [await self._merge_skill_assignments(template) for template in result]

        return result

    async def update_template(
        self, template_id: str, dto: AgentTemplateUpdate
    ) -> tuple[Optional[AgentTemplate], Optional[str]]:
        """
        更新 Agent 模板

        Returns:
            tuple: (模板, 错误类型) 错误类型为 'not_found' 或 None
        """
        await self._ensure_cache()

        template = self._templates.get(template_id)
        if not template:
            return None, 'not_found'

        # 更新字段
        update_data = dto.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                if field == 'prompt_slots':
                    value = [
                        slot if isinstance(slot, PromptSlot) else PromptSlot(**slot)
                        for slot in value
                    ]
                elif field == 'skill_slots':
                    value = [
                        slot if isinstance(slot, SkillSlot) else SkillSlot(**slot)
                        for slot in value
                    ]
                setattr(template, field, value)

        template.updated_at = datetime.now()

        # 更新数据库
        if self._db:
            try:
                data = self._template_to_db_dict(template)
                set_clauses = ', '.join([f"{k} = :{k}" for k in data.keys() if k != 'id'])
                data['id'] = template_id

                await self._db.execute_write(
                    f"UPDATE agent_templates SET {set_clauses} WHERE id = :id",
                    data
                )
                logger.info(f"更新 AgentTemplate 到数据库: {template_id}")
            except Exception as e:
                logger.error(f"更新 AgentTemplate 到数据库失败: {e}")

        return template, None

    async def delete_template(self, template_id: str) -> tuple[bool, Optional[str]]:
        """
        删除 Agent 模板

        Returns:
            tuple: (是否成功, 错误类型) 错误类型为 'not_found' 或 'is_system' 或 None
        """
        await self._ensure_cache()

        template = self._templates.get(template_id)
        if not template:
            return False, 'not_found'

        # 系统内置模板不可删除
        if template.is_system:
            logger.warning(f"尝试删除系统内置模板 {template_id}，操作被拒绝")
            return False, 'is_system'

        # 从数据库删除
        if self._db:
            try:
                await self._db.execute_write(
                    "DELETE FROM agent_templates WHERE id = :id",
                    {'id': template_id}
                )
                logger.info(f"从数据库删除 AgentTemplate: {template_id}")
            except Exception as e:
                logger.error(f"从数据库删除 AgentTemplate 失败: {e}")

        del self._templates[template_id]
        return True, None

    # ==================== Prompt 插槽管理 ====================

    async def add_prompt_to_template(
        self,
        template_id: str,
        slot_name: str,
        description: str,
        prompt_template_id: Optional[str] = None,
        required: bool = False,
        priority: int = 50,
        variable_overrides: Optional[Dict[str, Any]] = None,
        is_enabled: bool = True,
    ) -> Optional[AgentTemplate]:
        """添加 Prompt 插槽到模板"""
        await self._ensure_cache()

        template = self._templates.get(template_id)
        if not template:
            return None

        # 检查插槽是否已存在
        for slot in template.prompt_slots:
            if slot.slot_name == slot_name:
                logger.warning(f"插槽已存在: {slot_name} in template {template_id}")
                return None

        # 创建新插槽
        new_slot = PromptSlot(
            slot_name=slot_name,
            description=description,
            prompt_template_id=prompt_template_id,
            required=required,
            priority=priority,
            variable_overrides=variable_overrides or {},
            is_enabled=is_enabled,
        )

        template.prompt_slots.append(new_slot)

        # 如果默认顺序中不包含此插槽，则添加到末尾
        if slot_name not in template.default_prompt_order:
            template.default_prompt_order.append(slot_name)

        template.updated_at = datetime.now()

        # 更新数据库
        await self._save_template_to_db(template)

        logger.info(f"添加插槽 {slot_name} 到模板 {template_id}")
        return template

    async def remove_prompt_from_template(
        self, template_id: str, slot_name: str
    ) -> Optional[AgentTemplate]:
        """从模板中移除 Prompt 插槽"""
        await self._ensure_cache()

        template = self._templates.get(template_id)
        if not template:
            return None

        # 查找并移除插槽
        original_count = len(template.prompt_slots)
        template.prompt_slots = [
            slot for slot in template.prompt_slots
            if slot.slot_name != slot_name
        ]

        # 如果插槽不存在
        if len(template.prompt_slots) == original_count:
            logger.warning(f"插槽不存在: {slot_name} in template {template_id}")
            return None

        # 从默认顺序中移除
        if slot_name in template.default_prompt_order:
            template.default_prompt_order.remove(slot_name)

        template.updated_at = datetime.now()

        # 更新数据库
        await self._save_template_to_db(template)

        logger.info(f"从模板 {template_id} 移除插槽 {slot_name}")
        return template

    async def reorder_prompts(
        self, template_id: str, new_order: List[str]
    ) -> Optional[AgentTemplate]:
        """重新排序模板中的 Prompt 插槽"""
        await self._ensure_cache()

        template = self._templates.get(template_id)
        if not template:
            return None

        # 验证新顺序：必须包含所有启用的插槽
        enabled_slots = {
            slot.slot_name for slot in template.prompt_slots
            if slot.is_enabled
        }

        if set(new_order) != enabled_slots:
            logger.warning(f"新顺序不匹配启用的插槽: {new_order} vs {enabled_slots}")
            return None

        template.default_prompt_order = new_order
        template.updated_at = datetime.now()

        # 更新数据库
        await self._save_template_to_db(template)

        logger.info(f"更新模板 {template_id} 的 Prompt 顺序")
        return template

    async def _save_template_to_db(self, template: AgentTemplate):
        """保存模板到数据库"""
        if not self._db:
            return

        try:
            data = self._template_to_db_dict(template)
            set_clauses = ', '.join([f"{k} = :{k}" for k in data.keys() if k != 'id'])
            data['id'] = template.id

            await self._db.execute_write(
                f"UPDATE agent_templates SET {set_clauses} WHERE id = :id",
                data
            )
        except Exception as e:
            logger.error(f"保存模板到数据库失败: {e}")

    # ==================== 模板验证 ====================

    async def validate_template(self, template_id: str) -> Dict[str, Any]:
        """验证模板的完整性"""
        await self._ensure_cache()

        template = self._templates.get(template_id)
        if not template:
            return {"valid": False, "error": "模板不存在"}

        issues = []

        # 检查必需插槽是否有关联的 PromptTemplate
        for slot in template.prompt_slots:
            if slot.required and not slot.prompt_template_id:
                issues.append(f"必需插槽 '{slot.slot_name}' 未关联 PromptTemplate")

        # 检查默认顺序中的插槽是否存在
        for slot_name in template.default_prompt_order:
            if not any(slot.slot_name == slot_name for slot in template.prompt_slots):
                issues.append(f"默认顺序中的插槽 '{slot_name}' 不存在")

        # 检查启用的插槽是否都在默认顺序中
        enabled_slots = {
            slot.slot_name for slot in template.prompt_slots
            if slot.is_enabled
        }
        missing_in_order = enabled_slots - set(template.default_prompt_order)
        if missing_in_order:
            issues.append(f"启用的插槽未在默认顺序中: {missing_in_order}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "template_id": template_id,
            "agent_type": template.agent_type,
            "slot_count": len(template.prompt_slots),
            "enabled_slots": len(enabled_slots),
        }

    # ==================== 系统初始化 ====================

    async def initialize_system_templates(self, templates: List[AgentTemplate]):
        """
        初始化系统内置模板（数据库优先）

        逻辑：
        1. 先从数据库加载已有的模板（通过 _ensure_cache）
        2. 只在数据库中不存在时，才使用硬编码模板作为默认值
        3. 数据库中的版本优先级高于硬编码版本

        这确保了：
        - 迁移文件中的数据更新会被正确使用
        - 硬编码模板仅作为首次初始化的默认值
        - 不会用旧版硬编码数据覆盖数据库中的新版本

        Args:
            templates: 硬编码的系统模板列表（作为默认值）
        """
        # 先确保从数据库加载
        await self._ensure_cache()

        added_count = 0
        skipped_count = 0
        updated_count = 0

        for template in templates:
            if template.id in self._templates:
                existing_template = self._templates[template.id]
                if existing_template.is_system and self._sync_missing_slots_from_seed(existing_template, template):
                    await self._save_template_to_db(existing_template)
                    updated_count += 1
                    logger.info(f"同步系统 Agent模板增量更新: {template.id}")
                else:
                    skipped_count += 1
                    logger.debug(f"数据库中已存在 Agent模板 {template.id}，跳过硬编码版本")
                continue

            # 数据库中不存在，添加硬编码版本
            template.is_system = True

            # 写入数据库
            if self._db:
                try:
                    data = self._template_to_db_dict(template)
                    if 'created_at' not in data:
                        data['created_at'] = datetime.now()

                    columns = ', '.join(data.keys())
                    placeholders = ', '.join([f':{k}' for k in data.keys()])

                    await self._db.execute_write(
                        f"INSERT INTO agent_templates ({columns}) VALUES ({placeholders})",
                        data
                    )
                    logger.info(f"初始化系统 Agent模板到数据库: {template.id}")
                except Exception as e:
                    logger.error(f"初始化系统 Agent模板到数据库失败: {e}")

            self._templates[template.id] = template
            added_count += 1
            logger.info(f"初始化系统内置 AgentTemplate: {template.id}")

        logger.info(f"Agent模板初始化完成: 从数据库加载 {len(self._templates) - added_count} 个，新增 {added_count} 个，更新 {updated_count} 个，跳过 {skipped_count} 个")
