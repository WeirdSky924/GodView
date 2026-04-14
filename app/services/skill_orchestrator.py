# -*- coding: utf-8 -*-
"""
Agent Skill 编排器
让 Agent 能够自主编排 Skill 调用链，形成工作流

核心能力：
1. Function Calling：LLM 决定调用哪个 Skill
2. 工作流编排：支持顺序、循环、条件分支
3. 状态管理：Skill 间传递上下文
4. 反馈循环：根据执行结果决定下一步

使用场景：
- 章节 Writing Skill → 字数不足 → 继续生成
- 分段生成 → 内容合并 → 质量检查 → 修改
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from app.models.skill import Skill, SkillType

logger = logging.getLogger(__name__)


class SkillCallStatus(str, Enum):
    """Skill 调用状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SkillCall:
    """Skill 调用记录"""
    skill_id: str
    skill_name: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    status: SkillCallStatus = SkillCallStatus.PENDING
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "parameters": self.parameters,
            "result": self.result,
            "status": self.status.value,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class OrchestrationContext:
    """编排上下文"""
    agent_type: str
    initial_goal: str
    variables: Dict[str, Any] = field(default_factory=dict)
    call_history: List[SkillCall] = field(default_factory=list)
    max_iterations: int = 10
    current_iteration: int = 0

    def get_result(self, skill_id: str) -> Optional[Any]:
        """获取某个 Skill 的执行结果"""
        for call in reversed(self.call_history):
            if call.skill_id == skill_id and call.status == SkillCallStatus.SUCCESS:
                return call.result
        return None

    def get_last_result(self) -> Optional[Any]:
        """获取最后一个成功调用的结果"""
        for call in reversed(self.call_history):
            if call.status == SkillCallStatus.SUCCESS:
                return call.result
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "initial_goal": self.initial_goal,
            "variables": self.variables,
            "call_history": [c.to_dict() for c in self.call_history],
            "max_iterations": self.max_iterations,
            "current_iteration": self.current_iteration,
        }


@dataclass
class LLMDecision:
    """LLM 的决策结果"""
    action: str  # "call_skill" | "finish" | "abort"
    skill_id: Optional[str] = None
    skill_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    should_continue: bool = True  # 是否继续编排


class SkillOrchestrator:
    """
    Skill 编排器

    让 Agent 自主决定：
    1. 调用哪个 Skill
    2. 传递什么参数
    3. 是否需要继续调用
    4. 如何处理结果
    """

    def __init__(
        self,
        skill_service=None,
        llm_client=None,
        skill_executor: Optional[Callable] = None,
    ):
        """
        Args:
            skill_service: Skill 服务
            llm_client: LLM 客户端
            skill_executor: Skill 执行函数（可选，默认使用 skill_service）
        """
        self.skill_service = skill_service
        self.llm_client = llm_client
        self.skill_executor = skill_executor

    async def orchestrate(
        self,
        agent_type: str,
        goal: str,
        initial_params: Optional[Dict[str, Any]] = None,
        available_skills: Optional[List[Skill]] = None,
        max_iterations: int = 10,
    ) -> OrchestrationContext:
        """
        执行 Skill 编排

        Args:
            agent_type: Agent 类型
            goal: 目标描述
            initial_params: 初始参数
            available_skills: 可用的 Skills（None 则自动加载）
            max_iterations: 最大迭代次数

        Returns:
            OrchestrationContext: 编排上下文（包含所有调用记录）
        """
        # 初始化上下文
        context = OrchestrationContext(
            agent_type=agent_type,
            initial_goal=goal,
            variables=initial_params or {},
            max_iterations=max_iterations,
        )

        # 获取可用的 Skills
        if available_skills is None:
            available_skills = await self._get_available_skills(agent_type)

        if not available_skills:
            logger.warning(f"Agent {agent_type} 没有可用的 Skills")
            return context

        logger.info(f"开始编排: {goal}")
        logger.info(f"可用 Skills: {[s.name for s in available_skills]}")

        # 主循环
        while context.current_iteration < context.max_iterations:
            context.current_iteration += 1
            logger.info(f"--- 迭代 {context.current_iteration} ---")

            # 让 LLM 决定下一步
            decision = await self._get_llm_decision(context, available_skills)

            if not decision.should_continue or decision.action == "finish":
                logger.info(f"编排完成: {decision.reason}")
                break

            if decision.action == "abort":
                logger.warning(f"编排中止: {decision.reason}")
                break

            if decision.action == "call_skill" and decision.skill_id:
                # 执行 Skill
                call = await self._execute_skill(
                    context,
                    decision.skill_id,
                    decision.skill_name or "",
                    decision.parameters,
                )
                context.call_history.append(call)

                # 更新上下文变量
                if call.status == SkillCallStatus.SUCCESS and call.result:
                    context.variables[f"{call.skill_id}_result"] = call.result

            # 短暂延迟避免过快调用
            import asyncio
            await asyncio.sleep(0.1)

        logger.info(f"编排结束，共 {len(context.call_history)} 次调用")
        return context

    async def _get_llm_decision(
        self,
        context: OrchestrationContext,
        available_skills: List[Skill],
    ) -> LLMDecision:
        """
        让 LLM 决定下一步行动

        Args:
            context: 当前上下文
            available_skills: 可用的 Skills

        Returns:
            LLMDecision: LLM 的决策
        """
        # 构建 Skills 描述
        skills_desc = self._build_skills_description(available_skills)

        # 构建上下文描述
        context_desc = self._build_context_description(context)

        # 构建 Prompt
        prompt = f"""你是一个智能技能调度器。根据当前任务状态，决定下一步应该调用哪个技能，或者是否完成任务。

## 任务目标
{context.initial_goal}

## 当前状态
{context_desc}

## 可用技能
{skills_desc}

## 你的任务
分析当前状态，决定下一步行动：
1. 如果需要调用技能，选择最合适的技能并提供参数
2. 如果任务已完成，返回 finish
3. 如果遇到无法解决的问题，返回 abort

## 输出格式
返回 JSON：
```json
{{
  "action": "call_skill" | "finish" | "abort",
  "skill_id": "技能ID（调用技能时必填）",
  "skill_name": "技能名称",
  "parameters": {{}},  // 调用参数
  "reason": "决策理由",
  "should_continue": true  // 是否继续编排
}}
```

## 重要规则
1. 优先使用已有结果，避免重复调用
2. 参数中可以使用 ${{变量名}} 引用上下文变量
3. 如果上一步的结果不理想，可以调整参数重试
4. 注意迭代次数限制（当前 {context.current_iteration}/{context.max_iterations}）

请直接输出 JSON："""

        try:
            response = await self._call_llm(prompt)
            decision = self._parse_decision(response, available_skills)
            return decision
        except Exception as e:
            logger.error(f"LLM 决策失败: {e}")
            return LLMDecision(
                action="abort",
                reason=f"LLM 决策失败: {str(e)}",
                should_continue=False,
            )

    def _build_skills_description(self, skills: List[Skill]) -> str:
        """构建 Skills 描述"""
        lines = []
        for i, skill in enumerate(skills, 1):
            params_desc = ""
            if skill.parameters:
                params = []
                for p in skill.parameters:
                    params.append(f"  - {p.name} ({p.type}): {p.description}")
                    if p.default is not None:
                        params[-1] += f" [默认: {p.default}]"
                    if p.required:
                        params[-1] += " [必填]"
                params_desc = "\n" + "\n".join(params)

            lines.append(f"""
### {i}. {skill.name} (ID: {skill.id})
- 类型: {skill.skill_type.value}
- 描述: {skill.description}{params_desc}
""")

        return "\n".join(lines)

    def _build_context_description(self, context: OrchestrationContext) -> str:
        """构建上下文描述"""
        lines = [
            f"- 当前迭代: {context.current_iteration}/{context.max_iterations}",
            f"- 已调用次数: {len(context.call_history)}",
        ]

        # 变量
        if context.variables:
            lines.append("\n### 上下文变量")
            for k, v in context.variables.items():
                if isinstance(v, str) and len(v) > 100:
                    v = v[:100] + "..."
                lines.append(f"- {k}: {v}")

        # 最近调用
        if context.call_history:
            lines.append("\n### 最近调用")
            for call in context.call_history[-3:]:  # 只显示最近3次
                status_emoji = "✅" if call.status == SkillCallStatus.SUCCESS else "❌"
                result_preview = ""
                if call.result:
                    if isinstance(call.result, str):
                        result_preview = call.result[:100] + "..." if len(call.result) > 100 else call.result
                    else:
                        result_preview = str(call.result)[:100]
                lines.append(f"- {status_emoji} {call.skill_name}: {result_preview}")

        return "\n".join(lines)

    def _parse_decision(
        self,
        response: str,
        available_skills: List[Skill],
    ) -> LLMDecision:
        """解析 LLM 响应为决策"""
        try:
            # 提取 JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start == -1:
                raise ValueError("未找到 JSON")

            json_str = response[json_start:json_end]
            data = json.loads(json_str)

            action = data.get("action", "finish")
            skill_id = data.get("skill_id")
            skill_name = data.get("skill_name", "")

            # 验证 skill_id
            if action == "call_skill":
                skill = next((s for s in available_skills if s.id == skill_id), None)
                if not skill:
                    # 尝试按名称匹配
                    skill = next((s for s in available_skills if s.name == skill_name), None)
                    if skill:
                        skill_id = skill.id
                        skill_name = skill.name
                    else:
                        logger.warning(f"未找到 Skill: {skill_id or skill_name}")
                        return LLMDecision(
                            action="abort",
                            reason=f"未找到 Skill: {skill_id or skill_name}",
                            should_continue=False,
                        )

            return LLMDecision(
                action=action,
                skill_id=skill_id,
                skill_name=skill_name,
                parameters=data.get("parameters", {}),
                reason=data.get("reason", ""),
                should_continue=data.get("should_continue", True),
            )

        except json.JSONDecodeError as e:
            logger.error(f"解析 JSON 失败: {e}")
            return LLMDecision(action="finish", reason="JSON 解析失败")
        except Exception as e:
            logger.error(f"解析决策失败: {e}")
            return LLMDecision(action="finish", reason=str(e))

    async def _execute_skill(
        self,
        context: OrchestrationContext,
        skill_id: str,
        skill_name: str,
        parameters: Dict[str, Any],
    ) -> SkillCall:
        """执行 Skill"""
        call = SkillCall(
            skill_id=skill_id,
            skill_name=skill_name,
            parameters=parameters,
            status=SkillCallStatus.RUNNING,
            started_at=datetime.now(),
        )

        try:
            # 替换参数中的变量引用
            resolved_params = self._resolve_parameters(parameters, context)

            logger.info(f"调用 Skill: {skill_name}({skill_id})")
            logger.debug(f"参数: {resolved_params}")

            # 执行
            if self.skill_executor:
                result = await self.skill_executor(skill_id, resolved_params)
            elif self.skill_service:
                from app.models.skill import ExecuteSkillDTO
                dto = ExecuteSkillDTO(skill_id=skill_id, parameters=resolved_params)
                test_result = await self.skill_service.execute_skill(dto)
                if test_result.success:
                    result = test_result.output
                else:
                    raise RuntimeError(test_result.error)
            else:
                raise RuntimeError("没有可用的 Skill 执行器")

            call.result = result
            call.status = SkillCallStatus.SUCCESS
            logger.info(f"Skill {skill_name} 执行成功")

        except Exception as e:
            call.status = SkillCallStatus.FAILED
            call.error = str(e)
            logger.error(f"Skill {skill_name} 执行失败: {e}")

        call.completed_at = datetime.now()
        return call

    def _resolve_parameters(
        self,
        parameters: Dict[str, Any],
        context: OrchestrationContext,
    ) -> Dict[str, Any]:
        """
        解析参数中的变量引用

        支持：
        - ${{variable_name}} 引用上下文变量
        - ${{last_result}} 引用上一个结果
        """
        import re

        resolved = {}
        for key, value in parameters.items():
            if isinstance(value, str):
                # 匹配 ${{variable_name}} 模式
                pattern = r'\$\{([^}]+)\}'

                def replace_var(match):
                    var_name = match.group(1)
                    if var_name == "last_result":
                        return str(context.get_last_result() or "")
                    return str(context.variables.get(var_name, match.group(0)))

                resolved[key] = re.sub(pattern, replace_var, value)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_parameters(value, context)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_parameters({"_": v}, context)["_"]
                    if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                resolved[key] = value

        return resolved

    async def _get_available_skills(self, agent_type: str) -> List[Skill]:
        """获取 Agent 可用的 Skills"""
        if not self.skill_service:
            return []

        try:
            assigned = await self.skill_service.get_assigned_skills_for_agent(agent_type)
            return [skill for skill, _ in assigned]
        except Exception as e:
            logger.error(f"获取可用 Skills 失败: {e}")
            return []

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if not self.llm_client:
            raise RuntimeError("LLM 客户端未配置")

        if hasattr(self.llm_client, 'chat'):
            return await self.llm_client.chat(prompt)
        elif hasattr(self.llm_client, 'ainvoke'):
            response = await self.llm_client.ainvoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        elif hasattr(self.llm_client, 'messages'):
            response = await self.llm_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return response.choices[0].message.content
        else:
            raise RuntimeError("不支持的 LLM 客户端类型")


# ==================== 预定义工作流模板 ====================

class WorkflowTemplate:
    """工作流模板"""

    @staticmethod
    def chapter_writing_workflow() -> Dict[str, Any]:
        """
        章节写作工作流模板

        流程：
        1. 章节大纲 Skill → 确定结构和字数目标
        2. 分段生成 Skill → 循环生成各段内容
        3. 内容合并 Skill → 合并所有段落
        4. 字数统计 Skill → 检查是否达标
        5. 如果不足 → 继续生成缺失部分
        """
        return {
            "name": "章节写作工作流",
            "description": "支持长章节的分段生成和字数控制",
            "skills": [
                {
                    "skill_id": "skill_chapter_outline",
                    "skill_name": "章节大纲",
                    "description": "生成章节大纲，确定各段落的主题和字数分配",
                },
                {
                    "skill_id": "skill_segment_writing",
                    "skill_name": "分段写作",
                    "description": "根据大纲生成单个段落内容",
                },
                {
                    "skill_id": "skill_content_merge",
                    "skill_name": "内容合并",
                    "description": "合并多个段落为完整章节",
                },
                {
                    "skill_id": "skill_word_count",
                    "skill_name": "字数统计",
                    "description": "统计内容字数，与目标对比",
                },
                {
                    "skill_id": "skill_continue_writing",
                    "skill_name": "续写",
                    "description": "根据已有内容继续写作",
                },
            ],
            "flow": {
                "start": "skill_chapter_outline",
                "transitions": {
                    "skill_chapter_outline": {
                        "success": "skill_segment_writing",
                    },
                    "skill_segment_writing": {
                        "has_more": "skill_segment_writing",  # 循环
                        "done": "skill_content_merge",
                    },
                    "skill_content_merge": {
                        "success": "skill_word_count",
                    },
                    "skill_word_count": {
                        "enough": "finish",
                        "not_enough": "skill_continue_writing",
                    },
                    "skill_continue_writing": {
                        "success": "skill_word_count",  # 循环检查
                    },
                },
            },
        }


# 全局单例
_skill_orchestrator: Optional[SkillOrchestrator] = None


def get_skill_orchestrator(
    skill_service=None,
    llm_client=None,
) -> SkillOrchestrator:
    """获取 SkillOrchestrator 单例"""
    global _skill_orchestrator
    if _skill_orchestrator is None:
        _skill_orchestrator = SkillOrchestrator(
            skill_service=skill_service,
            llm_client=llm_client,
        )
    return _skill_orchestrator


def set_skill_orchestrator(orchestrator: SkillOrchestrator):
    """设置 SkillOrchestrator 实例"""
    global _skill_orchestrator
    _skill_orchestrator = orchestrator
