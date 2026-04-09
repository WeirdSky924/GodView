"""
Agent 模板服务层
管理 AgentTemplate 的创建、查询、更新等操作
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.agent_template import (
    AgentType,
    PromptSlot,
    AgentTemplate,
    AgentTemplateCreate,
    AgentTemplateUpdate,
)

logger = logging.getLogger(__name__)


class AgentTemplateService:
    """Agent 模板服务"""

    def __init__(self):
        # 内存存储（生产环境应使用数据库）
        self._templates: Dict[str, AgentTemplate] = {}

    # ==================== CRUD 操作 ====================

    async def create_template(self, dto: AgentTemplateCreate) -> AgentTemplate:
        """创建 Agent 模板"""
        template_id = f"agent_tmpl_{uuid.uuid4().hex[:12]}"

        template = AgentTemplate(
            id=template_id,
            name=dto.name,
            description=dto.description,
            agent_type=dto.agent_type,
            tags=dto.tags,
            prompt_slots=dto.prompt_slots,
            default_prompt_order=dto.default_prompt_order,
            is_system=dto.is_system,
        )

        self._templates[template_id] = template
        logger.info(f"创建 AgentTemplate: {template_id} - {template.name}")

        return template

    async def get_template(self, template_id: str) -> Optional[AgentTemplate]:
        """获取 Agent 模板"""
        return self._templates.get(template_id)

    async def get_template_by_type(self, agent_type: AgentType) -> Optional[AgentTemplate]:
        """按类型获取 Agent 模板（返回第一个匹配的系统模板）"""
        for template in self._templates.values():
            if template.agent_type == agent_type and template.is_system:
                return template
        return None

    async def list_templates(
        self,
        agent_type: Optional[AgentType] = None,
        is_system: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AgentTemplate]:
        """获取 Agent 模板列表"""
        templates = list(self._templates.values())

        # 按类型过滤
        if agent_type:
            templates = [t for t in templates if t.agent_type == agent_type]

        # 按系统内置过滤
        if is_system is not None:
            templates = [t for t in templates if t.is_system == is_system]

        # 按标签过滤（任一匹配）
        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]

        # 排序：系统模板优先，然后按创建时间倒序
        templates.sort(key=lambda x: (-x.is_system, -x.created_at.timestamp()))

        # 分页
        start = offset
        end = start + limit
        return templates[start:end]

    async def update_template(
        self, template_id: str, dto: AgentTemplateUpdate
    ) -> Optional[AgentTemplate]:
        """更新 Agent 模板"""
        template = self._templates.get(template_id)
        if not template:
            return None

        # 系统内置模板不可更新
        if template.is_system:
            logger.warning(f"尝试更新系统内置模板 {template_id}，操作被拒绝")
            return None

        # 更新字段
        update_data = dto.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(template, field, value)

        template.updated_at = datetime.now()
        logger.info(f"更新 AgentTemplate: {template_id}")

        return template

    async def delete_template(self, template_id: str) -> bool:
        """删除 Agent 模板"""
        template = self._templates.get(template_id)
        if not template:
            return False

        # 系统内置模板不可删除
        if template.is_system:
            logger.warning(f"尝试删除系统内置模板 {template_id}，操作被拒绝")
            return False

        del self._templates[template_id]
        logger.info(f"删除 AgentTemplate: {template_id}")
        return True

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
        logger.info(f"添加插槽 {slot_name} 到模板 {template_id}")

        return template

    async def remove_prompt_from_template(
        self, template_id: str, slot_name: str
    ) -> Optional[AgentTemplate]:
        """从模板中移除 Prompt 插槽"""
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
        logger.info(f"从模板 {template_id} 移除插槽 {slot_name}")

        return template

    async def reorder_prompts(
        self, template_id: str, new_order: List[str]
    ) -> Optional[AgentTemplate]:
        """重新排序模板中的 Prompt 插槽"""
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
        logger.info(f"更新模板 {template_id} 的 Prompt 顺序")

        return template

    # ==================== 模板验证 ====================

    async def validate_template(self, template_id: str) -> Dict[str, Any]:
        """验证模板的完整性"""
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
        """初始化系统内置模板"""
        for template in templates:
            if template.id not in self._templates:
                template.is_system = True
                self._templates[template.id] = template
                logger.info(f"初始化系统内置 AgentTemplate: {template.id}")