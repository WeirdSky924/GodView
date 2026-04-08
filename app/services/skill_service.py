"""
Skill 服务层
管理 Skill 的创建、查询、分配和执行
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.skill import (
    Skill,
    SkillAssignment,
    SkillExecutionLog,
    SkillType,
    SkillStatus,
    CreateSkillDTO,
    UpdateSkillDTO,
    AssignSkillDTO,
    ExecuteSkillDTO,
    SkillTestResult,
)
from app.models.prompt_template import (
    PromptTemplate,
    PromptTemplateCreate,
    PromptCategory,
)

logger = logging.getLogger(__name__)


class SkillService:
    """Skill 服务"""

    def __init__(self, prompt_template_service=None):
        # 内存存储（生产环境应使用数据库）
        self._skills: Dict[str, Skill] = {}
        self._assignments: Dict[str, SkillAssignment] = {}
        self._execution_logs: Dict[str, SkillExecutionLog] = {}

        # 依赖服务
        self.prompt_template_service = prompt_template_service

    # ==================== Skill CRUD ====================

    async def create_skill(self, dto: CreateSkillDTO) -> Skill:
        """创建 Skill"""
        skill_id = f"skill_{uuid.uuid4().hex[:12]}"

        # 处理 prompt 类型 Skill：创建关联的 PromptTemplate
        prompt_template_id = dto.prompt_template_id

        # 如果提供了 prompt 内容但没有关联的 PromptTemplate，则创建一个
        if dto.skill_type == SkillType.PROMPT and not prompt_template_id:
            if hasattr(dto, 'prompt_template') and dto.prompt_template:
                # 创建一个新的 PromptTemplate
                if self.prompt_template_service:
                    prompt_create_dto = PromptTemplateCreate(
                        name=f"{dto.name} (Skill)",
                        description=f"由 Skill {skill_id} 创建的 PromptTemplate",
                        category=PromptCategory.FUNCTION,  # 默认分类为 FUNCTION
                        tags=dto.tags + ["skill-generated"],
                        content=dto.prompt_template,
                        variables=[],  # 可以从内容中提取，这里简化
                        priority=50,
                    )
                    try:
                        prompt_template = await self.prompt_template_service.create_template(prompt_create_dto)
                        prompt_template_id = prompt_template.id
                        logger.info(f"为 Skill {skill_id} 创建 PromptTemplate: {prompt_template_id}")
                    except Exception as e:
                        logger.error(f"创建 PromptTemplate 失败: {e}")

        skill = Skill(
            id=skill_id,
            name=dto.name,
            description=dto.description,
            skill_type=dto.skill_type,
            prompt_template_id=prompt_template_id,  # 使用新的字段名
            function_code=dto.function_code,
            workflow_steps=dto.workflow_steps,
            knowledge_content=dto.knowledge_content,
            parameters=dto.parameters,
            tags=dto.tags,
            creator_project_id=dto.creator_project_id,
            creator_agent_id=dto.creator_agent_id,
            creator_user_id=dto.creator_user_id,
            status=SkillStatus.DRAFT,
        )

        self._skills[skill_id] = skill
        logger.info(f"创建 Skill: {skill_id} - {skill.name}")

        return skill

    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取 Skill"""
        return self._skills.get(skill_id)

    async def get_all_skills(
        self,
        skill_type: Optional[SkillType] = None,
        status: Optional[SkillStatus] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Skill]:
        """获取 Skill 列表（支持过滤）"""
        skills = list(self._skills.values())

        # 过滤类型
        if skill_type:
            skills = [s for s in skills if s.skill_type == skill_type]

        # 过滤状态
        if status:
            skills = [s for s in skills if s.status == status]

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

        # 排序：按创建时间倒序
        skills.sort(key=lambda x: x.created_at, reverse=True)

        # 分页
        return skills[offset:offset + limit]

    async def update_skill(self, skill_id: str, dto: UpdateSkillDTO) -> Optional[Skill]:
        """更新 Skill"""
        skill = self._skills.get(skill_id)
        if not skill:
            return None

        # 更新字段
        update_data = dto.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(skill, key, value)

        skill.updated_at = datetime.now()

        logger.info(f"更新 Skill: {skill_id}")
        return skill

    async def delete_skill(self, skill_id: str) -> bool:
        """删除 Skill"""
        if skill_id not in self._skills:
            return False

        # 删除相关分配
        assignments_to_delete = [
            aid for aid, a in self._assignments.items()
            if a.skill_id == skill_id
        ]
        for aid in assignments_to_delete:
            del self._assignments[aid]

        del self._skills[skill_id]
        logger.info(f"删除 Skill: {skill_id}")
        return True

    async def search_skills(self, query: str, limit: int = 10) -> List[Skill]:
        """搜索 Skill"""
        query_lower = query.lower()
        results = []

        for skill in self._skills.values():
            # 搜索名称、描述、标签
            if (query_lower in skill.name.lower() or
                query_lower in skill.description.lower() or
                any(query_lower in tag.lower() for tag in skill.tags)):
                results.append(skill)

        results.sort(key=lambda x: x.usage_count, reverse=True)
        return results[:limit]

    # ==================== Skill 分配 ====================

    async def assign_skill_to_agent(self, dto: AssignSkillDTO) -> SkillAssignment:
        """将 Skill 分配给 Agent"""
        # 检查 Skill 是否存在
        if dto.skill_id not in self._skills:
            raise ValueError(f"Skill {dto.skill_id} 不存在")

        # 检查是否已分配
        for assignment in self._assignments.values():
            if (assignment.skill_id == dto.skill_id and
                assignment.project_id == dto.project_id and
                assignment.agent_id == dto.agent_id):
                # 更新现有分配
                assignment.custom_parameters = dto.custom_parameters
                assignment.priority = dto.priority
                assignment.assigned_at = datetime.now()
                return assignment

        # 创建新分配
        assignment_id = f"assign_{uuid.uuid4().hex[:12]}"
        assignment = SkillAssignment(
            id=assignment_id,
            skill_id=dto.skill_id,
            project_id=dto.project_id,
            agent_id=dto.agent_id,
            custom_parameters=dto.custom_parameters,
            priority=dto.priority,
        )

        self._assignments[assignment_id] = assignment
        logger.info(f"分配 Skill {dto.skill_id} 给 Agent {dto.agent_id}")

        return assignment

    async def unassign_skill_from_agent(
        self,
        skill_id: str,
        project_id: str,
        agent_id: str,
    ) -> bool:
        """取消 Skill 分配"""
        assignment_id = None
        for aid, assignment in self._assignments.items():
            if (assignment.skill_id == skill_id and
                assignment.project_id == project_id and
                assignment.agent_id == agent_id):
                assignment_id = aid
                break

        if assignment_id:
            del self._assignments[assignment_id]
            logger.info(f"取消 Skill {skill_id} 分配给 Agent {agent_id}")
            return True

        return False

    async def get_agent_skills(
        self,
        project_id: str,
        agent_id: str,
    ) -> List[Skill]:
        """获取 Agent 已分配的 Skills"""
        skill_ids = [
            a.skill_id for a in self._assignments.values()
            if a.project_id == project_id and a.agent_id == agent_id
        ]

        skills = []
        for skill_id in skill_ids:
            skill = self._skills.get(skill_id)
            if skill:
                skills.append(skill)

        # 按优先级排序
        skills.sort(key=lambda x: x.usage_count, reverse=True)
        return skills

    async def get_skill_assignments(self, skill_id: str) -> List[SkillAssignment]:
        """获取 Skill 的所有分配"""
        return [
            a for a in self._assignments.values()
            if a.skill_id == skill_id
        ]

    # ==================== Skill 执行 ====================

    async def execute_skill(
        self,
        dto: ExecuteSkillDTO,
    ) -> SkillTestResult:
        """执行 Skill"""
        import time

        skill = self._skills.get(dto.skill_id)
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
        if not skill.prompt_template_id:
            return ""

        # 如果有 prompt_template_service，使用它来渲染模板
        if self.prompt_template_service:
            try:
                # 获取 PromptTemplate
                prompt_template = await self.prompt_template_service.get_template(
                    skill.prompt_template_id
                )
                if not prompt_template:
                    logger.warning(f"PromptTemplate 不存在: {skill.prompt_template_id}")
                    return ""

                # 合并 Skill 参数和传入参数
                merged_params = parameters.copy()
                for param in skill.parameters:
                    if param.name not in merged_params and param.default is not None:
                        merged_params[param.name] = param.default

                # 渲染模板
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
        else:
            # 如果没有服务，返回占位符
            logger.warning(f"PromptTemplateService 未注入，无法执行 prompt skill: {skill.id}")
            return f"[需要 PromptTemplateService 来执行: {skill.prompt_template_id}]"

    async def _execute_function_skill(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
    ) -> str:
        """执行 Function 类型 Skill"""
        # 注意：直接执行代码存在安全风险，生产环境应使用沙箱
        if not skill.function_code:
            return ""

        # 简单实现：返回代码内容
        # 实际实现应使用安全的执行环境
        logger.warning(f"Function Skill 执行需要安全沙箱: {skill.id}")
        return f"[Function execution not implemented]\nCode:\n{skill.function_code[:500]}..."

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
        return skill.knowledge_content or ""

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
        log_id = f"log_{uuid.uuid4().hex[:12]}"
        log = SkillExecutionLog(
            id=log_id,
            skill_id=skill_id,
            project_id=project_id,
            agent_id=agent_id,
            input_params=input_params,
            output_result=output_result,
            success=success,
            error_message=error_message,
            execution_time_ms=execution_time_ms,
        )
        self._execution_logs[log_id] = log

    async def get_execution_logs(
        self,
        skill_id: Optional[str] = None,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[SkillExecutionLog]:
        """获取执行日志"""
        logs = list(self._execution_logs.values())

        if skill_id:
            logs = [l for l in logs if l.skill_id == skill_id]
        if project_id:
            logs = [l for l in logs if l.project_id == project_id]
        if agent_id:
            logs = [l for l in logs if l.agent_id == agent_id]

        logs.sort(key=lambda x: x.created_at, reverse=True)
        return logs[:limit]

    # ==================== Skill 生成 ====================

    async def generate_skill_from_description(
        self,
        description: str,
        skill_type: SkillType = SkillType.PROMPT,
    ) -> Skill:
        """根据描述生成 Skill（AI 辅助）"""
        # 简单实现：创建基础 Skill
        # 实际实现应调用 LLM 生成

        skill_id = f"skill_{uuid.uuid4().hex[:12]}"
        skill = Skill(
            id=skill_id,
            name=f"Generated Skill {skill_id[:8]}",
            description=description,
            skill_type=skill_type,
            status=SkillStatus.DRAFT,
        )

        self._skills[skill_id] = skill
        return skill


# 全局单例
_skill_service: Optional[SkillService] = None


def get_skill_service() -> SkillService:
    """获取 SkillService 单例"""
    global _skill_service
    if _skill_service is None:
        _skill_service = SkillService()
    return _skill_service
