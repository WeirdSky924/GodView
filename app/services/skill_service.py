"""
Skill 服务层
管理 Skill 的创建、查询、分配和执行
支持数据库持久化和与 Agent 模板的集成
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.skill import (
    Skill,
    SkillAssignment,
    SkillExecutionLog,
    SkillType,
    SkillStatus,
    SkillCategory,
    CreateSkillDTO,
    UpdateSkillDTO,
    AssignSkillDTO,
    ExecuteSkillDTO,
    SkillTestResult,
    SkillParameter,
    SkillOutputSpec,
)

logger = logging.getLogger(__name__)


class SkillService:
    """Skill 服务"""

    def __init__(self, db=None, prompt_template_service=None):
        """
        初始化 Skill 服务

        Args:
            db: 数据库连接（可选，用于持久化）
            prompt_template_service: Prompt 模板服务
        """
        self._db = db
        # 内存缓存
        self._skills_cache: Dict[str, Skill] = {}
        self._cache_valid: bool = False

        # 依赖服务
        self.prompt_template_service = prompt_template_service

    async def _ensure_cache(self):
        """确保缓存有效"""
        if self._cache_valid:
            return

        if self._db:
            try:
                rows = await self._db.execute_query("SELECT * FROM skills ORDER BY priority DESC")
                for row in rows:
                    skill = self._row_to_skill(row)
                    self._skills_cache[skill.id] = skill
                self._cache_valid = True
                logger.info(f"从数据库加载 {len(self._skills_cache)} 个 Skills")
            except Exception as e:
                logger.warning(f"从数据库加载 Skills 失败: {e}")

    def _row_to_skill(self, row: Dict) -> Skill:
        """将数据库行转换为 Skill 对象"""
        return Skill(
            id=row['id'],
            name=row['name'],
            description=row['description'] or '',
            skill_type=SkillType(row['skill_type']),
            category=SkillCategory(row.get('category', 'general')),
            tags=json.loads(row.get('tags', '[]')) if isinstance(row.get('tags'), str) else row.get('tags', []),
            applicable_agent_types=json.loads(row.get('applicable_agent_types', '[]')) if isinstance(row.get('applicable_agent_types'), str) else row.get('applicable_agent_types', []),
            prompt_template=row.get('prompt_template'),
            prompt_template_id=row.get('prompt_template_id'),
            function_code=row.get('function_code'),
            workflow_steps=json.loads(row.get('workflow_steps', 'null')) if isinstance(row.get('workflow_steps'), str) else row.get('workflow_steps'),
            knowledge_content=row.get('knowledge_content'),
            parameters=[SkillParameter(**p) for p in (json.loads(row.get('parameters', '[]')) if isinstance(row.get('parameters'), str) else row.get('parameters', []))],
            output_spec=[SkillOutputSpec(**o) for o in (json.loads(row.get('output_spec', '[]')) if isinstance(row.get('output_spec'), str) else row.get('output_spec', []))],
            temperature=row.get('temperature', 0.7),
            max_tokens=row.get('max_tokens'),
            timeout=row.get('timeout', 60),
            retry_count=row.get('retry_count', 0),
            priority=row.get('priority', 50),
            status=SkillStatus(row.get('status', 'active')),
            is_system=row.get('is_system', False),
            is_enabled=row.get('is_enabled', True),
            is_composable=row.get('is_composable', True),
            creator_project_id=row.get('creator_project_id'),
            creator_agent_id=row.get('creator_agent_id'),
            creator_user_id=row.get('creator_user_id'),
            version=row.get('version', '1.0.0'),
            author=row.get('author', 'system'),
            examples=json.loads(row.get('examples', '[]')) if isinstance(row.get('examples'), str) else row.get('examples', []),
            usage_count=row.get('usage_count', 0),
            last_used_at=row.get('last_used_at'),
            created_at=row.get('created_at', datetime.now()),
            updated_at=row.get('updated_at', datetime.now()),
        )

    def _skill_to_db_dict(self, skill: Skill) -> Dict:
        """将 Skill 对象转换为数据库字典"""
        return {
            'id': skill.id,
            'name': skill.name,
            'description': skill.description,
            'skill_type': skill.skill_type.value,
            'category': skill.category.value,
            'tags': json.dumps(skill.tags, ensure_ascii=False),
            'applicable_agent_types': json.dumps(skill.applicable_agent_types, ensure_ascii=False),
            'prompt_template': skill.prompt_template,
            'prompt_template_id': skill.prompt_template_id,
            'function_code': skill.function_code,
            'workflow_steps': json.dumps(skill.workflow_steps, ensure_ascii=False) if skill.workflow_steps else None,
            'knowledge_content': skill.knowledge_content,
            'parameters': json.dumps([p.model_dump() for p in skill.parameters], ensure_ascii=False),
            'output_spec': json.dumps([o.model_dump() for o in skill.output_spec], ensure_ascii=False),
            'temperature': skill.temperature,
            'max_tokens': skill.max_tokens,
            'timeout': skill.timeout,
            'retry_count': skill.retry_count,
            'priority': skill.priority,
            'status': skill.status.value,
            'is_system': skill.is_system,
            'is_enabled': skill.is_enabled,
            'is_composable': skill.is_composable,
            'creator_project_id': skill.creator_project_id,
            'creator_agent_id': skill.creator_agent_id,
            'creator_user_id': skill.creator_user_id,
            'version': skill.version,
            'author': skill.author,
            'examples': json.dumps(skill.examples, ensure_ascii=False),
            'usage_count': skill.usage_count,
            'last_used_at': skill.last_used_at,
            'created_at': skill.created_at,
            'updated_at': skill.updated_at,
        }

    def invalidate_cache(self):
        """使缓存失效"""
        self._cache_valid = False
        self._skills_cache.clear()

    # ==================== Skill CRUD ====================

    async def create_skill(self, dto: CreateSkillDTO) -> Skill:
        """创建 Skill"""
        skill_id = f"skill_{uuid.uuid4().hex[:12]}"

        skill = Skill(
            id=skill_id,
            name=dto.name,
            description=dto.description or '',
            skill_type=dto.skill_type,
            category=dto.category or SkillCategory.GENERAL,
            tags=dto.tags or [],
            applicable_agent_types=dto.applicable_agent_types or [],
            prompt_template=dto.prompt_template,
            prompt_template_id=dto.prompt_template_id,
            function_code=dto.function_code,
            workflow_steps=dto.workflow_steps,
            knowledge_content=dto.knowledge_content,
            parameters=dto.parameters or [],
            output_spec=dto.output_spec or [],
            temperature=dto.temperature or 0.7,
            max_tokens=dto.max_tokens,
            timeout=dto.timeout or 60,
            priority=dto.priority or 50,
            status=SkillStatus.DRAFT,
            is_enabled=True,
            is_composable=dto.is_composable if dto.is_composable is not None else True,
            examples=dto.examples or [],
            creator_project_id=dto.creator_project_id,
            creator_agent_id=dto.creator_agent_id,
            creator_user_id=dto.creator_user_id,
        )

        # 存入数据库
        if self._db:
            try:
                data = self._skill_to_db_dict(skill)
                columns = ', '.join(data.keys())
                placeholders = ', '.join([f':{k}' for k in data.keys()])

                await self._db.execute_write(
                    f"INSERT INTO skills ({columns}) VALUES ({placeholders})",
                    data
                )
                logger.info(f"创建 Skill 到数据库: {skill_id} - {skill.name}")
            except Exception as e:
                logger.error(f"创建 Skill 到数据库失败: {e}")
                raise

        # 更新缓存
        self._skills_cache[skill_id] = skill
        self._cache_valid = True

        return skill

    async def create_skill_from_model(self, skill: Skill) -> Skill:
        """从 Skill 模型创建（用于初始化默认 Skills）"""
        # 存入数据库
        if self._db:
            try:
                data = self._skill_to_db_dict(skill)
                columns = ', '.join(data.keys())
                placeholders = ', '.join([f':{k}' for k in data.keys()])

                await self._db.execute_write(
                    f"INSERT INTO skills ({columns}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING",
                    data
                )
                logger.info(f"创建 Skill 到数据库: {skill.id} - {skill.name}")
            except Exception as e:
                logger.error(f"创建 Skill 到数据库失败: {e}")
                # 不抛出异常，继续处理

        # 更新缓存
        self._skills_cache[skill.id] = skill

        return skill

    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取 Skill"""
        await self._ensure_cache()
        return self._skills_cache.get(skill_id)

    async def get_all_skills(
        self,
        skill_type: Optional[SkillType] = None,
        status: Optional[SkillStatus] = None,
        category: Optional[SkillCategory] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Skill]:
        """获取 Skill 列表（支持过滤）"""
        await self._ensure_cache()
        skills = list(self._skills_cache.values())

        # 过滤类型
        if skill_type:
            skills = [s for s in skills if s.skill_type == skill_type]

        # 过滤状态
        if status:
            skills = [s for s in skills if s.status == status]

        # 过滤类别
        if category:
            skills = [s for s in skills if s.category == category]

        # 过滤标签
        if tags:
            skills = [s for s in skills if any(tag in s.tags for tag in tags)]

        # 搜索
        if search:
            search_lower = search.lower()
            skills = [
                s for s in skills
                if search_lower in s.name.lower() or search_lower in s.description.lower()
            ]

        # 排序：按优先级降序
        skills.sort(key=lambda x: (-x.priority, x.created_at))

        # 分页
        return skills[offset:offset + limit]

    async def update_skill(self, skill_id: str, dto: UpdateSkillDTO) -> Optional[Skill]:
        """更新 Skill"""
        await self._ensure_cache()
        skill = self._skills_cache.get(skill_id)
        if not skill:
            return None

        # 更新字段
        update_data = dto.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(skill, key, value)

        skill.updated_at = datetime.now()

        # 更新数据库
        if self._db:
            try:
                data = self._skill_to_db_dict(skill)
                set_clause = ', '.join([f"{k} = :{k}" for k in data.keys()])
                data['skill_id'] = skill_id

                await self._db.execute_write(
                    f"UPDATE skills SET {set_clause} WHERE id = :skill_id",
                    data
                )
            except Exception as e:
                logger.error(f"更新 Skill 到数据库失败: {e}")

        logger.info(f"更新 Skill: {skill_id}")
        return skill

    async def delete_skill(self, skill_id: str) -> bool:
        """删除 Skill"""
        await self._ensure_cache()

        if skill_id not in self._skills_cache:
            return False

        # 从数据库删除
        if self._db:
            try:
                await self._db.execute_write(
                    "DELETE FROM skill_assignments WHERE skill_id = :skill_id",
                    {"skill_id": skill_id}
                )
                await self._db.execute_write(
                    "DELETE FROM skills WHERE id = :skill_id",
                    {"skill_id": skill_id}
                )
            except Exception as e:
                logger.error(f"从数据库删除 Skill 失败: {e}")

        del self._skills_cache[skill_id]
        logger.info(f"删除 Skill: {skill_id}")
        return True

    async def search_skills(self, query: str, limit: int = 10) -> List[Skill]:
        """搜索 Skill"""
        await self._ensure_cache()
        query_lower = query.lower()
        results = []

        for skill in self._skills_cache.values():
            if (query_lower in skill.name.lower() or
                query_lower in skill.description.lower() or
                any(query_lower in tag.lower() for tag in skill.tags)):
                results.append(skill)

        results.sort(key=lambda x: (-x.priority, -x.usage_count))
        return results[:limit]

    # ==================== Skill 分配 ====================

    async def assign_skill(self, dto: AssignSkillDTO) -> SkillAssignment:
        """将 Skill 分配给 Agent 类型"""
        await self._ensure_cache()

        if dto.skill_id not in self._skills_cache:
            raise ValueError(f"Skill {dto.skill_id} 不存在")

        assignment_id = f"assign_{uuid.uuid4().hex[:12]}"
        assignment = SkillAssignment(
            id=assignment_id,
            skill_id=dto.skill_id,
            agent_type=dto.agent_type,
            slot_name=dto.slot_name or '',
            custom_parameters=dto.custom_parameters,
            variable_overrides=dto.variable_overrides or {},
            priority=dto.priority or 50,
            execution_condition=dto.execution_condition,
            is_enabled=dto.is_enabled if dto.is_enabled is not None else True,
            is_required=dto.is_required if dto.is_required is not None else False,
        )

        # 存入数据库
        if self._db:
            try:
                await self._db.execute_write(
                    """
                    INSERT INTO skill_assignments
                    (id, skill_id, agent_type, slot_name, custom_parameters, variable_overrides,
                     priority, execution_condition, is_enabled, is_required)
                    VALUES (:id, :skill_id, :agent_type, :slot_name, :custom_parameters, :variable_overrides,
                     :priority, :execution_condition, :is_enabled, :is_required)
                    ON CONFLICT (skill_id, agent_type, slot_name) DO UPDATE SET
                    custom_parameters = :custom_parameters, variable_overrides = :variable_overrides, priority = :priority,
                    execution_condition = :execution_condition, is_enabled = :is_enabled, is_required = :is_required
                    """,
                    {
                        "id": assignment_id,
                        "skill_id": dto.skill_id,
                        "agent_type": dto.agent_type,
                        "slot_name": dto.slot_name or '',
                        "custom_parameters": json.dumps(dto.custom_parameters or {}, ensure_ascii=False),
                        "variable_overrides": json.dumps(dto.variable_overrides or {}, ensure_ascii=False),
                        "priority": dto.priority or 50,
                        "execution_condition": dto.execution_condition,
                        "is_enabled": dto.is_enabled if dto.is_enabled is not None else True,
                        "is_required": dto.is_required if dto.is_required is not None else False,
                    }
                )
            except Exception as e:
                logger.error(f"分配 Skill 到数据库失败: {e}")

        logger.info(f"分配 Skill {dto.skill_id} 给 Agent 类型 {dto.agent_type}")
        return assignment

    async def get_skills_for_agent_type(self, agent_type: str) -> List[Skill]:
        """
        获取适用于某个 Agent 类型的所有 Skill

        Args:
            agent_type: Agent 类型

        Returns:
            List[Skill]: 适用的 Skill 列表
        """
        skills = await self.get_all_skills(status=SkillStatus.ACTIVE)

        result = []
        for skill in skills:
            # 空列表表示所有 Agent 都可用
            if not skill.applicable_agent_types or agent_type in skill.applicable_agent_types:
                result.append(skill)

        # 按优先级降序排序
        result.sort(key=lambda x: -x.priority)
        return result

    async def get_skill_assignments(self, skill_id: str) -> List[SkillAssignment]:
        """获取 Skill 的所有分配"""
        if not self._db:
            return []

        try:
            rows = await self._db.execute_query(
                "SELECT * FROM skill_assignments WHERE skill_id = :skill_id",
                {"skill_id": skill_id}
            )
            return [self._row_to_assignment(row) for row in rows]
        except Exception as e:
            logger.error(f"获取 Skill 分配失败: {e}")
            return []

    def _row_to_assignment(self, row: Dict) -> SkillAssignment:
        """将数据库行转换为 SkillAssignment 对象"""
        return SkillAssignment(
            id=row['id'],
            skill_id=row['skill_id'],
            agent_type=row['agent_type'],
            slot_name=row.get('slot_name', ''),
            custom_parameters=json.loads(row.get('custom_parameters', '{}')) if isinstance(row.get('custom_parameters'), str) else row.get('custom_parameters', {}),
            variable_overrides=json.loads(row.get('variable_overrides', '{}')) if isinstance(row.get('variable_overrides'), str) else row.get('variable_overrides', {}),
            priority=row.get('priority', 50),
            execution_condition=row.get('execution_condition'),
            is_enabled=row.get('is_enabled', True),
            is_required=row.get('is_required', False),
            assigned_by=row.get('assigned_by', 'user'),
            assigned_at=row.get('assigned_at', datetime.now()),
        )

    # ==================== Skill 执行 ====================

    async def execute_skill(
        self,
        dto: ExecuteSkillDTO,
    ) -> SkillTestResult:
        """执行 Skill"""
        import time

        await self._ensure_cache()
        skill = self._skills_cache.get(dto.skill_id)
        if not skill:
            return SkillTestResult(success=False, error=f"Skill {dto.skill_id} 不存在")

        if skill.status != SkillStatus.ACTIVE:
            return SkillTestResult(success=False, error=f"Skill 状态为 {skill.status}，无法执行")

        start_time = time.time()

        try:
            result = await self._execute_skill_internal(skill, dto.parameters)
            execution_time_ms = int((time.time() - start_time) * 1000)

            # 更新使用统计
            skill.usage_count += 1
            skill.last_used_at = datetime.now()

            # 更新数据库中的使用统计
            if self._db:
                try:
                    await self._db.execute_write(
                        "UPDATE skills SET usage_count = :usage_count, last_used_at = :last_used_at WHERE id = :skill_id",
                        {
                            "usage_count": skill.usage_count,
                            "last_used_at": skill.last_used_at,
                            "skill_id": skill.id,
                        }
                    )
                except Exception as e:
                    logger.warning(f"更新 Skill 使用统计失败: {e}")

            # 记录执行日志
            await self._log_execution(
                skill_id=skill.id,
                project_id=dto.project_id,
                agent_id=dto.agent_id,
                input_params=dto.parameters,
                output_result=result,
                success=True,
                execution_time_ms=execution_time_ms,
            )

            return SkillTestResult(
                success=True,
                output=result,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_message = str(e)

            # 记录错误日志
            await self._log_execution(
                skill_id=skill.id,
                project_id=dto.project_id,
                agent_id=dto.agent_id,
                input_params=dto.parameters,
                success=False,
                error_message=error_message,
                execution_time_ms=execution_time_ms,
            )

            return SkillTestResult(
                success=False,
                error=error_message,
                execution_time_ms=execution_time_ms,
            )

    async def _execute_skill_internal(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
    ) -> str:
        """内部执行逻辑"""
        if skill.skill_type == SkillType.PROMPT:
            return await self._execute_prompt_skill(skill, parameters)
        elif skill.skill_type == SkillType.FUNCTION:
            return await self._execute_function_skill(skill, parameters)
        elif skill.skill_type == SkillType.WORKFLOW:
            return await self._execute_workflow_skill(skill, parameters)
        elif skill.skill_type == SkillType.KNOWLEDGE:
            return await self._execute_knowledge_skill(skill, parameters)
        else:
            raise ValueError(f"未知的 Skill 类型: {skill.skill_type}")

    async def _execute_prompt_skill(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
    ) -> str:
        """执行 Prompt 类型 Skill"""
        if skill.prompt_template:
            # 直接使用内嵌的模板
            content = skill.prompt_template
            for var_name, var_value in parameters.items():
                placeholder = f"{{{var_name}}}"
                if placeholder in content:
                    if isinstance(var_value, (list, dict)):
                        content = content.replace(placeholder, json.dumps(var_value, ensure_ascii=False, indent=2))
                    else:
                        content = content.replace(placeholder, str(var_value))
            return content

        if skill.prompt_template_id and self.prompt_template_service:
            try:
                prompt_template = await self.prompt_template_service.get_template(
                    skill.prompt_template_id
                )
                if prompt_template:
                    merged_params = parameters.copy()
                    for param in skill.parameters:
                        if param.name not in merged_params and param.default is not None:
                            merged_params[param.name] = param.default

                    from app.models.prompt_template import PromptRenderRequest
                    request = PromptRenderRequest(
                        template_id=skill.prompt_template_id,
                        variables=merged_params,
                    )
                    result = await self.prompt_template_service.render_template(request)
                    return result.rendered_content
            except Exception as e:
                logger.error(f"渲染 PromptTemplate 失败: {e}")
                return f"[渲染失败: {str(e)}]"

        return ""

    async def _execute_function_skill(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
    ) -> str:
        """
        执行 Function 类型 Skill

        在受限环境中执行 Python 代码，只允许访问安全的内置函数和模块

        Args:
            skill: Skill 对象
            parameters: 执行参数

        Returns:
            str: 执行结果（JSON 字符串）
        """
        if not skill.function_code:
            return ""

        import json

        # 创建安全的执行环境
        safe_globals = {
            '__builtins__': {
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'sorted': sorted,
                'reversed': reversed,
                'sum': sum,
                'max': max,
                'min': min,
                'abs': abs,
                'round': round,
                'isinstance': isinstance,
                'type': type,
                'hasattr': hasattr,
                'getattr': getattr,
                'any': any,
                'all': all,
                'print': print,
                '__import__': __import__,  # 允许导入模块
            },
            're': re,
            'json': json,
        }

        # 添加参数到执行环境
        local_vars = parameters.copy()

        try:
            # 执行代码
            exec(skill.function_code, safe_globals, local_vars)

            # 查找 execute 函数并调用
            if 'execute' in local_vars and callable(local_vars['execute']):
                result = local_vars['execute'](**parameters)
            else:
                # 如果没有 execute 函数，尝试返回所有新定义的变量
                result = {k: v for k, v in local_vars.items()
                         if k not in parameters and not k.startswith('_')}

            # 将结果转换为 JSON 字符串
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            else:
                return json.dumps({"result": result}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"执行 Function Skill {skill.id} 失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _execute_workflow_skill(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
    ) -> str:
        """执行 Workflow 类型 Skill"""
        if not skill.workflow_steps:
            return ""

        results = []
        for i, step in enumerate(skill.workflow_steps):
            step_name = step.get("name", f"Step {i + 1}")
            step_action = step.get("action", "")
            results.append(f"[{step_name}] {step_action}")

        return "\n".join(results)

    async def _execute_knowledge_skill(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
    ) -> str:
        """执行 Knowledge 类型 Skill"""
        content = skill.knowledge_content or ""

        # 替换参数占位符
        for var_name, var_value in parameters.items():
            placeholder = f"{{{var_name}}}"
            if placeholder in content:
                if isinstance(var_value, (list, dict)):
                    content = content.replace(placeholder, json.dumps(var_value, ensure_ascii=False, indent=2))
                else:
                    content = content.replace(placeholder, str(var_value))

        return content

    async def _log_execution(
        self,
        skill_id: str,
        project_id: Optional[str],
        agent_id: Optional[str],
        input_params: Dict[str, Any],
        output_result: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
    ):
        """记录执行日志"""
        if not self._db:
            return

        try:
            log_id = f"log_{uuid.uuid4().hex[:12]}"
            await self._db.execute_write(
                """
                INSERT INTO skill_execution_logs
                (id, skill_id, project_id, agent_id, input_params, output_result, success, error_message, execution_time_ms)
                VALUES (:id, :skill_id, :project_id, :agent_id, :input_params, :output_result, :success, :error_message, :execution_time_ms)
                """,
                {
                    "id": log_id,
                    "skill_id": skill_id,
                    "project_id": project_id,
                    "agent_id": agent_id,
                    "input_params": json.dumps(input_params, ensure_ascii=False),
                    "output_result": output_result,
                    "success": success,
                    "error_message": error_message,
                    "execution_time_ms": execution_time_ms,
                }
            )
        except Exception as e:
            logger.warning(f"记录 Skill 执行日志失败: {e}")

    async def get_execution_logs(
        self,
        skill_id: Optional[str] = None,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[SkillExecutionLog]:
        """获取执行日志"""
        if not self._db:
            return []

        try:
            query = "SELECT * FROM skill_execution_logs WHERE 1=1"
            params = {}

            if skill_id:
                query += " AND skill_id = :skill_id"
                params["skill_id"] = skill_id
            if project_id:
                query += " AND project_id = :project_id"
                params["project_id"] = project_id
            if agent_id:
                query += " AND agent_id = :agent_id"
                params["agent_id"] = agent_id

            query += " ORDER BY created_at DESC LIMIT :limit"
            params["limit"] = limit

            rows = await self._db.execute_query(query, params)
            return [
                SkillExecutionLog(
                    id=row['id'],
                    skill_id=row['skill_id'],
                    project_id=row.get('project_id'),
                    agent_id=row.get('agent_id'),
                    input_params=json.loads(row.get('input_params', '{}')) if isinstance(row.get('input_params'), str) else row.get('input_params', {}),
                    output_result=row.get('output_result'),
                    success=row.get('success', True),
                    error_message=row.get('error_message'),
                    execution_time_ms=row.get('execution_time_ms'),
                    created_at=row.get('created_at', datetime.now()),
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"获取执行日志失败: {e}")
            return []

    # ==================== Skill 生成 ====================

    async def generate_skill_from_description(
        self,
        description: str,
        skill_type: SkillType = SkillType.PROMPT,
    ) -> Skill:
        """根据描述生成 Skill（AI 辅助）"""
        skill_id = f"skill_{uuid.uuid4().hex[:12]}"
        skill = Skill(
            id=skill_id,
            name=f"Generated Skill {skill_id[:8]}",
            description=description,
            skill_type=skill_type,
            status=SkillStatus.DRAFT,
        )

        return await self.create_skill_from_model(skill)


# 全局单例
_skill_service: Optional[SkillService] = None


def get_skill_service() -> SkillService:
    """获取 SkillService 单例"""
    global _skill_service
    if _skill_service is None:
        # 尝试获取数据库连接
        try:
            from app.api.app import postgres_db
            _skill_service = SkillService(db=postgres_db)
        except ImportError:
            _skill_service = SkillService()
    return _skill_service


def set_skill_service(service: SkillService):
    """设置 SkillService 实例"""
    global _skill_service
    _skill_service = service
