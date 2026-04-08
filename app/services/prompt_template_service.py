"""
Prompt 模板服务层
管理 PromptTemplate 的创建、查询、渲染等操作
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.prompt_template import (
    PromptCategory,
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptFilter,
    PromptRenderRequest,
    PromptRenderResult,
)

logger = logging.getLogger(__name__)


class PromptTemplateService:
    """Prompt 模板服务"""

    def __init__(self):
        # 内存存储（生产环境应使用数据库）
        self._templates: Dict[str, PromptTemplate] = {}

    # ==================== CRUD 操作 ====================

    async def create_template(self, dto: PromptTemplateCreate) -> PromptTemplate:
        """创建 Prompt 模板"""
        template_id = f"prompt_{uuid.uuid4().hex[:12]}"

        template = PromptTemplate(
            id=template_id,
            name=dto.name,
            description=dto.description,
            category=dto.category,
            tags=dto.tags,
            content=dto.content,
            variables=dto.variables,
            default_values=dto.default_values,
            priority=dto.priority,
            is_system=False,  # 通过 API 创建的默认不是系统内置
        )

        self._templates[template_id] = template
        logger.info(f"创建 PromptTemplate: {template_id} - {template.name}")

        return template

    async def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """获取单个 Prompt 模板"""
        return self._templates.get(template_id)

    async def list_templates(self, filters: PromptFilter) -> List[PromptTemplate]:
        """获取 Prompt 模板列表（支持过滤）"""
        templates = list(self._templates.values())

        # 按分类过滤
        if filters.category:
            templates = [t for t in templates if t.category == filters.category]

        # 按标签过滤（任一匹配）
        if filters.tags:
            templates = [t for t in templates if any(tag in t.tags for tag in filters.tags)]

        # 按系统内置过滤
        if filters.is_system is not None:
            templates = [t for t in templates if t.is_system == filters.is_system]

        # 搜索
        if filters.search:
            search_lower = filters.search.lower()
            templates = [
                t for t in templates
                if (search_lower in t.name.lower() or
                    search_lower in t.description.lower() or
                    search_lower in t.content.lower())
            ]

        # 排序：按优先级降序，然后按创建时间降序
        templates.sort(key=lambda x: (-x.priority, -x.created_at.timestamp()))

        # 分页
        start = filters.offset
        end = start + filters.limit
        return templates[start:end]

    async def update_template(
        self, template_id: str, dto: PromptTemplateUpdate
    ) -> Optional[PromptTemplate]:
        """更新 Prompt 模板"""
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
        logger.info(f"更新 PromptTemplate: {template_id}")

        return template

    async def delete_template(self, template_id: str) -> bool:
        """删除 Prompt 模板"""
        template = self._templates.get(template_id)
        if not template:
            return False

        # 系统内置模板不可删除
        if template.is_system:
            logger.warning(f"尝试删除系统内置模板 {template_id}，操作被拒绝")
            return False

        del self._templates[template_id]
        logger.info(f"删除 PromptTemplate: {template_id}")
        return True

    # ==================== 查询和搜索 ====================

    async def search_templates(
        self,
        query: str,
        category: Optional[PromptCategory] = None,
        limit: int = 50
    ) -> List[PromptTemplate]:
        """搜索 Prompt 模板"""
        templates = list(self._templates.values())

        # 按分类过滤
        if category:
            templates = [t for t in templates if t.category == category]

        query_lower = query.lower()
        # 加权搜索：名称 > 描述 > 内容 > 标签
        scored_templates = []
        for template in templates:
            score = 0

            # 名称匹配
            if query_lower in template.name.lower():
                score += 10

            # 描述匹配
            if template.description and query_lower in template.description.lower():
                score += 5

            # 内容匹配
            if query_lower in template.content.lower():
                score += 3

            # 标签匹配
            if any(query_lower in tag.lower() for tag in template.tags):
                score += 2

            if score > 0:
                scored_templates.append((score, template))

        # 按分数降序排序
        scored_templates.sort(key=lambda x: -x[0])

        # 返回模板列表
        return [t for _, t in scored_templates[:limit]]

    async def get_categories(self) -> Dict[str, int]:
        """获取分类统计信息"""
        categories = {}
        for template in self._templates.values():
            category = template.category.value
            categories[category] = categories.get(category, 0) + 1
        return categories

    # ==================== 渲染操作 ====================

    def _extract_variables(self, content: str) -> List[str]:
        """从内容中提取变量名（格式：{variable_name}）"""
        pattern = r'\{([^{}]+)\}'
        matches = re.findall(pattern, content)
        # 去除可能的空格，并去重
        return list(set([match.strip() for match in matches]))

    async def render_template(self, request: PromptRenderRequest) -> PromptRenderResult:
        """渲染 Prompt 模板（变量插值）"""
        template = self._templates.get(request.template_id)
        if not template:
            raise ValueError(f"模板不存在: {request.template_id}")

        # 合并默认值和提供的值
        variables = template.default_values.copy()
        variables.update(request.variables)

        # 提取模板中的变量
        template_variables = self._extract_variables(template.content)

        # 检查缺失的变量
        missing_variables = []
        used_variables = {}

        # 渲染内容
        rendered_content = template.content
        for var in template_variables:
            if var in variables:
                value = str(variables[var])
                rendered_content = rendered_content.replace(f"{{{var}}}", value)
                used_variables[var] = variables[var]
            else:
                missing_variables.append(var)
                # 保留变量占位符
                rendered_content = rendered_content.replace(f"{{{var}}}", f"{{{var}}}")

        return PromptRenderResult(
            template_id=template.id,
            original_content=template.content,
            rendered_content=rendered_content,
            used_variables=used_variables,
            missing_variables=missing_variables,
        )

    async def preview_render(
        self,
        content: str,
        variables: Dict[str, Any]
    ) -> str:
        """预览渲染结果（不保存模板）"""
        # 提取变量
        template_variables = self._extract_variables(content)

        # 渲染内容
        rendered_content = content
        for var in template_variables:
            if var in variables:
                value = str(variables[var])
                rendered_content = rendered_content.replace(f"{{{var}}}", value)
            else:
                # 保留变量占位符
                rendered_content = rendered_content.replace(f"{{{var}}}", f"{{{var}}}")

        return rendered_content

    # ==================== 系统初始化 ====================

    async def initialize_system_templates(self, templates: List[PromptTemplate]):
        """初始化系统内置模板"""
        for template in templates:
            if template.id not in self._templates:
                template.is_system = True
                self._templates[template.id] = template
                logger.info(f"初始化系统内置模板: {template.id}")