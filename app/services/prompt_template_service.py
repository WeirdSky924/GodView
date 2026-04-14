"""
Prompt 模板服务层
管理 PromptTemplate 的创建、查询、渲染等操作

Prompt 模板定义 Agent 的身份（你是谁）
- 在创建 Agent 时绑定
- 包含基本准则、角色知识、行为规范

混合存储模式：
- MD 文件存储内容（Git 可版本化，无编码问题）
- 数据库存储元数据和向量（用于搜索）
"""

import json
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

    def __init__(self, db=None):
        """
        Args:
            db: 数据库连接（可选）
        """
        self._db = db
        self._templates: Dict[str, PromptTemplate] = {}
        self._cache_valid: bool = False

    async def _ensure_cache(self):
        """确保缓存有效"""
        if self._cache_valid:
            return

        if self._db:
            try:
                rows = await self._db.execute_query(
                    "SELECT * FROM prompt_templates ORDER BY priority DESC, name"
                )
                for row in rows:
                    template = self._row_to_template(row)
                    self._templates[template.id] = template
                self._cache_valid = True
                logger.info(f"从数据库加载 {len(self._templates)} 个 Prompt 模板")
            except Exception as e:
                logger.warning(f"从数据库加载 Prompt 模板失败: {e}")

    def _row_to_template(self, row: Dict) -> PromptTemplate:
        """将数据库行转换为 PromptTemplate 对象"""
        # category 映射：数据库中可能的值 -> PromptCategory 枚举
        category_mapping = {
            'identity': PromptCategory.ROLE,
            'instruction': PromptCategory.FUNCTION,
            'constraint': PromptCategory.CONSTRAINT,
            'output': PromptCategory.OUTPUT,
            'base': PromptCategory.BASE,
            'role': PromptCategory.ROLE,
            'function': PromptCategory.FUNCTION,
            'value': PromptCategory.VALUE,
        }

        category = PromptCategory.OUTPUT
        if row.get('category'):
            category_str = row['category']
            category = category_mapping.get(category_str, PromptCategory.OUTPUT)

        variables = row.get('variables', [])
        if isinstance(variables, str):
            variables = json.loads(variables)

        default_values = row.get('default_values', {})
        if isinstance(default_values, str):
            default_values = json.loads(default_values)

        tags = row.get('tags', [])
        if isinstance(tags, str):
            tags = json.loads(tags)

        # 运行时读取策略：
        # 1. 优先使用数据库内容（完整持久化）
        # 2. 数据库为空时，从 MD 文件读取（回退）
        content = row.get('content', '')
        prompt_id = row['id']

        if not content:
            # 数据库为空，尝试从 MD 文件读取
            md_content = self._try_load_md_content(prompt_id)
            if md_content is not None:
                content = md_content
                logger.debug(f"从 MD 文件加载 Prompt 内容: {prompt_id}")

        return PromptTemplate(
            id=prompt_id,
            name=row['name'],
            description=row.get('description', ''),
            category=category,
            tags=tags,
            content=content,
            variables=variables,
            default_values=default_values,
            priority=row.get('priority', 50),
            is_system=row.get('is_system', False),
            created_at=row.get('created_at', datetime.now()),
            updated_at=row.get('updated_at', datetime.now()),
        )

    def _try_load_md_content(self, prompt_id: str) -> Optional[str]:
        """
        尝试从 MD 文件加载内容

        Args:
            prompt_id: Prompt ID

        Returns:
            Optional[str]: MD 文件内容，如果不存在则返回 None
        """
        try:
            from app.services.md_file_service import get_md_file_service
            md_service = get_md_file_service()
            return md_service.get_prompt_content(prompt_id)
        except Exception as e:
            logger.debug(f"从 MD 文件加载失败 {prompt_id}: {e}")
            return None

    def _template_to_db_dict(self, template: PromptTemplate) -> Dict:
        """将 PromptTemplate 对象转换为数据库字典"""
        return {
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'category': template.category.value if isinstance(template.category, PromptCategory) else template.category,
            'tags': json.dumps(template.tags, ensure_ascii=False),
            'content': template.content,
            'variables': json.dumps(template.variables, ensure_ascii=False),
            'default_values': json.dumps(template.default_values, ensure_ascii=False),
            'priority': template.priority,
            'is_system': template.is_system,
            'updated_at': datetime.now(),
        }

    def invalidate_cache(self):
        """使缓存失效"""
        self._cache_valid = False
        self._templates.clear()

    # ==================== CRUD 操作 ====================

    async def create_template(self, dto: PromptTemplateCreate) -> PromptTemplate:
        """创建 Prompt 模板"""
        await self._ensure_cache()

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
            is_system=False,
        )

        # 存入数据库
        if self._db:
            try:
                data = self._template_to_db_dict(template)
                columns = ', '.join(data.keys())
                placeholders = ', '.join([f':{k}' for k in data.keys()])

                await self._db.execute_write(
                    f"INSERT INTO prompt_templates ({columns}) VALUES ({placeholders})",
                    data
                )
                logger.info(f"创建 PromptTemplate 到数据库: {template_id}")
            except Exception as e:
                logger.error(f"创建 PromptTemplate 到数据库失败: {e}")
                raise

        self._templates[template_id] = template
        return template

    async def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """获取单个 Prompt 模板"""
        await self._ensure_cache()
        return self._templates.get(template_id)

    async def list_templates(self, filters: PromptFilter) -> List[PromptTemplate]:
        """获取 Prompt 模板列表（支持过滤）"""
        await self._ensure_cache()
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
    ) -> tuple[Optional[PromptTemplate], Optional[str]]:
        """
        更新 Prompt 模板

        Returns:
            tuple: (模板, 错误类型) 错误类型为 'not_found' 或 'is_system' 或 None
        """
        await self._ensure_cache()
        template = self._templates.get(template_id)
        if not template:
            return None, 'not_found'

        # 系统内置模板不可更新
        if template.is_system:
            logger.warning(f"尝试更新系统内置模板 {template_id}，操作被拒绝")
            return None, 'is_system'

        # 更新字段
        update_data = dto.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(template, field, value)

        template.updated_at = datetime.now()

        # 更新数据库
        if self._db:
            try:
                data = self._template_to_db_dict(template)
                set_clause = ', '.join([f"{k} = :{k}" for k in data.keys()])
                data['template_id'] = template_id

                await self._db.execute_write(
                    f"UPDATE prompt_templates SET {set_clause} WHERE id = :template_id",
                    data
                )
            except Exception as e:
                logger.error(f"更新 PromptTemplate 到数据库失败: {e}")

        logger.info(f"更新 PromptTemplate: {template_id}")
        return template, None

    async def delete_template(self, template_id: str) -> tuple[bool, Optional[str]]:
        """
        删除 Prompt 模板

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
                    "DELETE FROM prompt_templates WHERE id = :template_id",
                    {"template_id": template_id}
                )
            except Exception as e:
                logger.error(f"从数据库删除 PromptTemplate 失败: {e}")

        del self._templates[template_id]
        logger.info(f"删除 PromptTemplate: {template_id}")
        return True, None

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
        """
        初始化系统内置模板（数据库优先）

        逻辑：
        1. 先从数据库加载已有的模板
        2. 只在数据库中不存在时，才使用硬编码模板作为默认值
        3. 数据库中的版本优先级高于硬编码版本

        Args:
            templates: 硬编码的系统模板列表（作为默认值）
        """
        # 先确保从数据库加载
        await self._ensure_cache()

        added_count = 0
        skipped_count = 0

        for template in templates:
            if template.id in self._templates:
                # 数据库中已存在，跳过
                skipped_count += 1
                logger.debug(f"数据库中已存在模板 {template.id}，跳过硬编码版本")
                continue

            # 数据库中不存在，添加硬编码版本
            template.is_system = True
            self._templates[template.id] = template
            added_count += 1

            # 尝试写入数据库
            if self._db:
                try:
                    data = self._template_to_db_dict(template)
                    data['created_at'] = template.created_at or datetime.now()
                    columns = ', '.join(data.keys())
                    placeholders = ', '.join([f':{k}' for k in data.keys()])
                    await self._db.execute_write(
                        f"INSERT INTO prompt_templates ({columns}) VALUES ({placeholders})",
                        data
                    )
                    logger.info(f"初始化系统模板到数据库: {template.id}")
                except Exception as e:
                    logger.warning(f"写入系统模板到数据库失败 {template.id}: {e}")

        logger.info(f"Prompt模板初始化完成: 从数据库加载 {len(self._templates) - added_count} 个，新增 {added_count} 个，跳过 {skipped_count} 个")

    # ==================== Agent 身份定义 ====================

    async def get_identity_prompts_for_agent(self, agent_type: str) -> List[PromptTemplate]:
        """
        获取 Agent 类型需要的身份定义 Prompts

        Prompt 模板定义 Agent 的身份（你是谁）：
        - 在创建 Agent 时绑定
        - 包含基本准则、角色知识、行为规范

        Args:
            agent_type: Agent 类型

        Returns:
            List[PromptTemplate]: 身份定义 Prompts 列表
        """
        await self._ensure_cache()

        prompts = []

        # 所有 Agent 都需要通用准则
        common_rules = self._templates.get("prompt_common_rules")
        if common_rules:
            prompts.append(common_rules)

        writing_standards = self._templates.get("prompt_writing_standards")
        if writing_standards:
            prompts.append(writing_standards)

        # 根据类型添加特定身份定义
        type_prompt_map = {
            "writer": "prompt_writer_identity",
            "master_plotter": "prompt_master_plotter_identity",
            "evaluator": "prompt_evaluator_identity",
            "summarizer": "prompt_summarizer_identity",
            "hook_manager": "prompt_hook_manager_identity",
            "setting": "prompt_setting_identity",
            "character": "prompt_character_identity",
        }

        identity_id = type_prompt_map.get(agent_type)
        if identity_id:
            identity_prompt = self._templates.get(identity_id)
            if identity_prompt:
                prompts.append(identity_prompt)

        return prompts

    async def build_agent_identity_prompt(
        self,
        agent_type: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        构建 Agent 的完整身份定义 Prompt

        Args:
            agent_type: Agent 类型
            variables: 模板变量

        Returns:
            str: 组合后的身份定义 Prompt
        """
        prompts = await self.get_identity_prompts_for_agent(agent_type)

        pieces = []
        for prompt in prompts:
            # 渲染变量
            content = prompt.content
            if variables:
                merged_vars = prompt.default_values.copy()
                merged_vars.update(variables)
                for var_name, var_value in merged_vars.items():
                    placeholder = f"{{{var_name}}}"
                    if placeholder in content:
                        content = content.replace(placeholder, str(var_value))

            pieces.append(content)

        return "\n\n---\n\n".join(pieces)

    # ==================== MD 文件同步 ====================

    async def sync_md_files_to_db(self) -> Dict[str, int]:
        """
        将 MD 文件同步到数据库

        这个方法会：
        1. 扫描 prompts/ 目录下的所有 MD 文件
        2. 提取 frontmatter 作为元数据
        3. 将元数据存入数据库（content 字段可以为空或存摘要）

        Returns:
            Dict[str, int]: 同步结果统计
        """
        if not self._db:
            logger.warning("数据库未连接，无法同步 MD 文件")
            return {"error": 1, "synced": 0, "skipped": 0}

        try:
            from app.services.md_file_service import get_md_file_service
            md_service = get_md_file_service()
            md_service.invalidate_cache()

            # 获取所有 MD 文件中的 Prompts
            md_prompts = md_service.list_prompts()

            synced = 0
            skipped = 0
            errors = 0

            for md_prompt in md_prompts:
                prompt_id = md_prompt['id']

                try:
                    # 解析 category，支持映射转换
                    # MD 文件中使用的 category -> 后端 PromptCategory
                    category_mapping = {
                        'identity': PromptCategory.ROLE,
                        'instruction': PromptCategory.FUNCTION,
                        'constraint': PromptCategory.CONSTRAINT,
                        'output': PromptCategory.OUTPUT,
                        'base': PromptCategory.BASE,
                        'role': PromptCategory.ROLE,
                        'function': PromptCategory.FUNCTION,
                        'value': PromptCategory.VALUE,
                    }
                    category_str = md_prompt.get('category', 'output')
                    category = category_mapping.get(category_str, PromptCategory.OUTPUT)

                    # 准备数据
                    # 完整持久化：元数据 + 内容都存入数据库
                    # MD 文件是编辑入口，数据库是运行时数据源

                    # 提取 variables，支持两种格式
                    variables = md_prompt.get('variables', md_prompt.get('parameters', []))

                    # 构建 default_values 从 variables 中提取
                    default_values = {}
                    for var in variables:
                        if isinstance(var, dict) and 'name' in var and 'default' in var:
                            default_values[var['name']] = var['default']

                    data = {
                        'id': prompt_id,
                        'name': md_prompt.get('name', prompt_id),
                        'description': md_prompt.get('description', ''),
                        'category': category.value,
                        'tags': json.dumps(md_prompt.get('tags', []), ensure_ascii=False),
                        'content': md_prompt.get('content', ''),  # 完整内容存入数据库
                        'variables': json.dumps(variables, ensure_ascii=False),
                        'default_values': json.dumps(default_values, ensure_ascii=False),
                        'priority': md_prompt.get('priority', 50),
                        'is_system': md_prompt.get('is_system', True),
                    }

                    # UPSERT
                    columns = ', '.join(data.keys())
                    placeholders = ', '.join([f':{k}' for k in data.keys()])
                    update_clauses = ', '.join([
                        f"{k} = :{k}" for k in data.keys() if k != 'id'
                    ])

                    await self._db.execute_write(
                        f"""
                        INSERT INTO prompt_templates ({columns})
                        VALUES ({placeholders})
                        ON CONFLICT (id) DO UPDATE SET {update_clauses}
                        """,
                        data
                    )

                    synced += 1
                    logger.debug(f"同步 Prompt 到数据库: {prompt_id}")

                except Exception as e:
                    errors += 1
                    logger.error(f"同步 Prompt {prompt_id} 失败: {e}")

            # 刷新缓存
            self.invalidate_cache()

            logger.info(f"MD 文件同步完成: {synced} 个成功, {skipped} 个跳过, {errors} 个错误")
            return {"synced": synced, "skipped": skipped, "errors": errors}

        except Exception as e:
            logger.error(f"同步 MD 文件失败: {e}")
            return {"error": 1, "synced": 0, "skipped": 0}

# 全局单例
_prompt_template_service: Optional[PromptTemplateService] = None


def get_prompt_template_service() -> PromptTemplateService:
    """获取 PromptTemplateService 单例"""
    global _prompt_template_service
    if _prompt_template_service is None:
        try:
            from app.api.app import postgres_db
            _prompt_template_service = PromptTemplateService(db=postgres_db)
        except ImportError:
            _prompt_template_service = PromptTemplateService()
    return _prompt_template_service


def set_prompt_template_service(service: PromptTemplateService):
    """设置 PromptTemplateService 实例"""
    global _prompt_template_service
    _prompt_template_service = service
