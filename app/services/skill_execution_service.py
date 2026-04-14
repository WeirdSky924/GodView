"""
技能执行服务 - 处理技能执行、子技能编排、评估阈值检查

职责：
1. 执行单个技能
2. 编排复合技能的子技能执行
3. 检查评估阈值并处理重试
4. 集成记忆和全局状态
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from app.models.skill import (
    Skill,
    SkillType,
    EvaluationThreshold,
    SubSkillReference,
)
from app.services.global_state_service import get_global_state_service
from app.services.skill_memory_integration import get_skill_memory_integration

logger = logging.getLogger(__name__)


class SkillExecutionResult:
    """技能执行结果"""

    def __init__(
        self,
        success: bool,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        score: Optional[float] = None,
        passed_threshold: bool = True,
        retry_count: int = 0,
    ):
        self.success = success
        self.output = output or {}
        self.error = error
        self.score = score
        self.passed_threshold = passed_threshold
        self.retry_count = retry_count
        self.execution_time_ms = 0
        self.token_usage = {}
        self.global_state_changes = {}
        self.memory_changes = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "score": self.score,
            "passed_threshold": self.passed_threshold,
            "retry_count": self.retry_count,
            "execution_time_ms": self.execution_time_ms,
            "token_usage": self.token_usage,
            "global_state_changes": self.global_state_changes,
        }


class SkillExecutionService:
    """技能执行服务"""

    def __init__(self, db=None, llm=None):
        self._db = db
        self._llm = llm
        self._global_state_service = None
        self._memory_integration = None

    @property
    def global_state_service(self):
        if self._global_state_service is None:
            self._global_state_service = get_global_state_service(self._db)
        return self._global_state_service

    @property
    def memory_integration(self):
        if self._memory_integration is None:
            self._memory_integration = get_skill_memory_integration(self._db)
        return self._memory_integration

    async def execute_skill(
        self,
        skill: Skill,
        project_id: str,
        agent_type: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> SkillExecutionResult:
        """
        执行技能

        Args:
            skill: 技能对象
            project_id: 项目 ID
            agent_type: Agent 类型
            parameters: 输入参数
            context: 额外上下文

        Returns:
            SkillExecutionResult: 执行结果
        """
        start_time = time.time()

        try:
            # 1. 准备上下文（包括记忆和全局状态）
            full_context = await self._prepare_context(
                skill, project_id, agent_type, context
            )

            # 2. 根据技能类型执行
            if skill.skill_type == SkillType.WORKFLOW and skill.sub_skills:
                result = await self._execute_composite_skill(
                    skill, project_id, agent_type, parameters, full_context
                )
            else:
                result = await self._execute_single_skill(
                    skill, parameters, full_context
                )

            # 3. 检查评估阈值
            if skill.evaluation_threshold and result.success:
                result = await self._check_evaluation_threshold(
                    skill, result, parameters, full_context
                )

            # 4. 更新全局状态
            if skill.writes_global_state and result.success:
                await self._update_global_state(
                    skill, project_id, agent_type, result.output
                )

            # 5. 记录到记忆
            if skill.use_agent_memory:
                await self.memory_integration.record_skill_execution(
                    skill, project_id, agent_type, parameters, result.output,
                    result.success, result.error
                )

            # 6. 记录执行日志
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            await self._log_execution(
                skill, project_id, agent_type, parameters, result
            )

            return result

        except Exception as e:
            logger.error(f"执行技能失败: {skill.name} - {e}")
            return SkillExecutionResult(success=False, error=str(e))

    async def _prepare_context(
        self,
        skill: Skill,
        project_id: str,
        agent_type: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """准备执行上下文"""
        full_context = context or {}

        # 加载全局状态
        if skill.reads_global_state:
            state = await self.global_state_service.get_state(
                project_id, skill.reads_global_state
            )
            full_context["global_state"] = state

        # 加载记忆
        if skill.use_agent_memory:
            memory_context = await self.memory_integration.prepare_skill_context(
                skill, project_id, agent_type, full_context
            )
            full_context.update(memory_context)

        return full_context

    async def _execute_single_skill(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> SkillExecutionResult:
        """执行单个技能"""
        try:
            if skill.skill_type == SkillType.PROMPT:
                output = await self._execute_prompt_skill(skill, parameters, context)
            elif skill.skill_type == SkillType.FUNCTION:
                output = await self._execute_function_skill(skill, parameters, context)
            elif skill.skill_type == SkillType.KNOWLEDGE:
                output = await self._execute_knowledge_skill(skill, parameters, context)
            else:
                return SkillExecutionResult(
                    success=False,
                    error=f"不支持的技能类型: {skill.skill_type}"
                )

            return SkillExecutionResult(success=True, output=output)

        except Exception as e:
            return SkillExecutionResult(success=False, error=str(e))

    async def _execute_composite_skill(
        self,
        skill: Skill,
        project_id: str,
        agent_type: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> SkillExecutionResult:
        """
        执行复合技能（包含子技能）

        子技能按 execution_order 顺序执行，输出传递给下一个子技能
        """
        # 按 execution_order 排序
        sub_skills = sorted(skill.sub_skills, key=lambda x: x.execution_order)

        # 存储各子技能的输出
        sub_outputs = {}
        combined_output = {}

        for sub_ref in sub_skills:
            # 检查执行条件
            if not sub_ref.is_required:
                # 可选子技能，检查是否有必要执行
                should_execute = self._should_execute_optional_subskill(
                    sub_ref, parameters, sub_outputs
                )
                if not should_execute:
                    logger.info(f"跳过可选子技能: {sub_ref.skill_id}")
                    continue

            # 准备子技能参数
            sub_params = self._prepare_subskill_params(
                sub_ref, parameters, sub_outputs
            )

            # 加载子技能
            sub_skill = await self._load_skill(sub_ref.skill_id)
            if not sub_skill:
                if sub_ref.is_required:
                    return SkillExecutionResult(
                        success=False,
                        error=f"无法加载必需子技能: {sub_ref.skill_id}"
                    )
                continue

            # 执行子技能
            sub_result = await self.execute_skill(
                sub_skill, project_id, agent_type, sub_params, context
            )

            if not sub_result.success and sub_ref.is_required:
                return SkillExecutionResult(
                    success=False,
                    error=f"必需子技能执行失败: {sub_ref.skill_id} - {sub_result.error}"
                )

            # 存储输出
            sub_outputs[sub_ref.skill_id] = sub_result.output
            if sub_ref.pass_output_to:
                combined_output[sub_ref.pass_output_to] = sub_result.output

        # 组装最终输出
        combined_output["sub_skills_output"] = sub_outputs
        combined_output["success"] = True

        return SkillExecutionResult(success=True, output=combined_output)

    def _should_execute_optional_subskill(
        self,
        sub_ref: SubSkillReference,
        parameters: Dict[str, Any],
        sub_outputs: Dict[str, Any],
    ) -> bool:
        """判断是否应执行可选子技能"""
        # 示例：反派动态技能只在有反派出场时执行
        if sub_ref.skill_id == "skill_chapter_villain_arc":
            return parameters.get("villain_presence") is not None

        return True

    def _prepare_subskill_params(
        self,
        sub_ref: SubSkillReference,
        parameters: Dict[str, Any],
        sub_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """准备子技能参数"""
        sub_params = parameters.copy()

        # 传递前一个子技能的输出
        if sub_ref.pass_output_to and sub_ref.pass_output_to in sub_outputs:
            sub_params[sub_ref.pass_output_to] = sub_outputs[sub_ref.pass_output_to]

        return sub_params

    async def _check_evaluation_threshold(
        self,
        skill: Skill,
        result: SkillExecutionResult,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> SkillExecutionResult:
        """检查评估阈值"""
        threshold = skill.evaluation_threshold

        # 从输出中提取分数
        output = result.output or {}
        score = output.get("overall_score") or output.get("score", 1.0)
        result.score = score

        # 检查是否通过阈值
        passed = score >= threshold.min_score
        result.passed_threshold = passed

        # 检查是否有阻断性问题
        issues = output.get("issues", [])
        blocking_issues = [i for i in issues if i.get("type") == "blocking"]
        if blocking_issues:
            result.passed_threshold = False

        # 如果未通过且配置了自动重试
        if not passed and threshold.auto_retry and result.retry_count < threshold.max_retries:
            logger.info(
                f"技能 {skill.name} 未通过阈值 ({score} < {threshold.min_score})，"
                f"准备重试 ({result.retry_count + 1}/{threshold.max_retries})"
            )

            # 根据重试策略调整参数
            retry_params = self._adjust_params_for_retry(
                parameters, output, threshold.retry_strategy
            )

            # 重新执行
            result.retry_count += 1
            retry_result = await self._execute_single_skill(skill, retry_params, context)
            retry_result.retry_count = result.retry_count
            retry_result.score = retry_result.output.get("overall_score", 1.0) if retry_result.success else 0

            # 递归检查阈值
            if retry_result.score >= threshold.min_score:
                retry_result.passed_threshold = True
                return retry_result

            # 继续重试
            return await self._check_evaluation_threshold(
                skill, retry_result, retry_params, context
            )

        return result

    def _adjust_params_for_retry(
        self,
        parameters: Dict[str, Any],
        previous_output: Dict[str, Any],
        strategy: str,
    ) -> Dict[str, Any]:
        """根据重试策略调整参数"""
        retry_params = parameters.copy()

        if strategy == "improve":
            # 添加改进指令
            issues = previous_output.get("issues", [])
            suggestions = previous_output.get("suggestions", [])
            retry_params["improvement_hints"] = {
                "previous_issues": issues,
                "suggestions": suggestions,
                "focus_areas": [i.get("dimension") for i in issues if i.get("dimension")],
            }

        elif strategy == "regenerate":
            # 添加重新生成指令
            retry_params["regenerate"] = True
            retry_params["avoid_previous"] = previous_output

        return retry_params

    async def _update_global_state(
        self,
        skill: Skill,
        project_id: str,
        agent_type: str,
        output: Dict[str, Any],
    ):
        """更新全局状态"""
        updates = {}

        for key in skill.writes_global_state:
            if key in output:
                updates[key] = output[key]

        if updates:
            await self.global_state_service.set_state(
                project_id, updates, agent_type
            )
            logger.info(f"更新全局状态: {list(updates.keys())}")

    async def _execute_prompt_skill(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行 Prompt 类型技能"""
        if not self._llm:
            raise ValueError("LLM 未配置")

        # 渲染 prompt 模板
        prompt = skill.prompt_template or ""
        for key, value in {**parameters, **context}.items():
            placeholder = "{{" + key + "}}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, str(value))

        # 调用 LLM
        response = await self._llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        # 解析 JSON 输出
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {"content": response_text}

    async def _execute_function_skill(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行 Function 类型技能"""
        # 在实际实现中，这里需要动态执行 Python 代码
        # 出于安全考虑，这里只返回提示
        logger.warning(f"Function 类型技能需要实现: {skill.id}")
        return {"error": "Function 类型技能未实现"}

    async def _execute_knowledge_skill(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行 Knowledge 类型技能"""
        # 知识类型技能直接返回知识内容
        return {
            "knowledge": skill.knowledge_content or skill.prompt_template,
            "context": context,
        }

    async def _load_skill(self, skill_id: str) -> Optional[Skill]:
        """加载技能"""
        # 从数据库或缓存加载技能
        if not self._db:
            return None

        try:
            query = """
                SELECT * FROM skills WHERE id = :skill_id AND is_enabled = TRUE
            """
            results = await self._db.execute_query(query, {"skill_id": skill_id})

            if results and len(results) > 0:
                row = results[0]
                return Skill(
                    id=row["id"],
                    name=row["name"],
                    description=row.get("description", ""),
                    skill_type=row["skill_type"],
                    category=row.get("category", "general"),
                    tags=row.get("tags", []),
                    applicable_agent_types=row.get("applicable_agent_types", []),
                    prompt_template=row.get("prompt_template"),
                    knowledge_content=row.get("knowledge_content"),
                    sub_skills=row.get("sub_skills", []),
                    evaluation_threshold=row.get("evaluation_threshold"),
                    use_agent_memory=row.get("use_agent_memory", False),
                    memory_types=row.get("memory_types", []),
                    reads_global_state=row.get("reads_global_state", []),
                    writes_global_state=row.get("writes_global_state", []),
                    priority=row.get("priority", 50),
                )

        except Exception as e:
            logger.error(f"加载技能失败: {skill_id} - {e}")

        return None

    async def _log_execution(
        self,
        skill: Skill,
        project_id: str,
        agent_type: str,
        parameters: Dict[str, Any],
        result: SkillExecutionResult,
    ):
        """记录执行日志"""
        if not self._db:
            return

        try:
            query = """
                INSERT INTO skill_executions (
                    skill_id, project_id, agent_type,
                    input_params, output_result,
                    evaluation_score, passed_threshold,
                    status, retry_count, error_message,
                    execution_time_ms
                ) VALUES (
                    :skill_id, CAST(:project_id AS UUID), :agent_type,
                    CAST(:input_params AS jsonb), CAST(:output_result AS jsonb),
                    :evaluation_score, :passed_threshold,
                    :status, :retry_count, :error_message,
                    :execution_time_ms
                )
            """
            await self._db.execute_write(
                query,
                {
                    "skill_id": skill.id,
                    "project_id": project_id,
                    "agent_type": agent_type,
                    "input_params": json.dumps(parameters, default=str),
                    "output_result": json.dumps(result.output, default=str),
                    "evaluation_score": result.score,
                    "passed_threshold": result.passed_threshold,
                    "status": "completed" if result.success else "failed",
                    "retry_count": result.retry_count,
                    "error_message": result.error,
                    "execution_time_ms": result.execution_time_ms,
                },
            )

        except Exception as e:
            logger.error(f"记录技能执行日志失败: {e}")


# 单例实例
_execution_service: Optional[SkillExecutionService] = None


def get_skill_execution_service(db=None, llm=None) -> SkillExecutionService:
    """获取技能执行服务单例"""
    global _execution_service
    if _execution_service is None:
        _execution_service = SkillExecutionService(db, llm)
    else:
        if db is not None:
            _execution_service._db = db
        if llm is not None:
            _execution_service._llm = llm
    return _execution_service
