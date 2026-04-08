"""
伏笔管理员 Agent - 负责伏笔的埋设与回收
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_template import AgentType

logger = logging.getLogger(__name__)


class HookManagerAgent(BaseAgent):
    """伏笔管理员 Agent"""

    AGENT_TYPE = AgentType.HOOK_MANAGER

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        # 如果没有提供 system_prompt 且没有 project_id，使用默认的硬编码 prompt（向后兼容）
        if not system_prompt and not project_id:
            system_prompt = self._build_default_system_prompt()

        super().__init__(
            name="HookManagerAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（HookManager 特定）"""
        return {
            "agent_role": "伏笔管理员",
            "task_description": "负责在日常互动中埋设和回收伏笔",
        }

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示（向后兼容）"""
        return """你是伏笔管理员，负责在日常互动中埋设和回收伏笔。

你的职责：
1. 根据当前场景选择合适的伏笔进行埋设
2. 识别伏笔回收的最佳时机
3. 确保伏笔的"展示"而非"告知"
4. 追踪伏笔状态变化

输出 JSON 格式：
{
    "hooks_to_plant": [{"hook_id": "ID", "method": "埋设方式", "context": "具体情境"}],
    "hooks_to_resolve": [{"hook_id": "ID", "resolution": "回收方式"}],
    "hooks_status_updates": [{"hook_id": "ID", "new_status": "triggered/resolved"}]
}"""

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行伏笔管理

        Args:
            input_data: 包含以下字段
                - available_hooks: 可用伏笔池
                - triggered_hooks: 已触发伏笔
                - pending_hooks: 待回收伏笔
                - current_scene: 当前场景描述
                - recent_events: 最近发生的事件

        Returns:
            AgentResponse: 伏笔管理决策
        """
        try:
            available_hooks = input_data.get("available_hooks", [])
            triggered_hooks = input_data.get("triggered_hooks", [])
            pending_hooks = input_data.get("pending_hooks", [])
            current_scene = input_data.get("current_scene", "")
            recent_events = input_data.get("recent_events", [])

            # 构建用户消息
            user_message = self._build_user_message(
                available_hooks=available_hooks,
                triggered_hooks=triggered_hooks,
                pending_hooks=pending_hooks,
                current_scene=current_scene,
                recent_events=recent_events,
            )

            # 调用 LLM
            response_text = await self._call_llm(
                messages=[HumanMessage(content=user_message)], temperature=0.5
            )

            # 解析响应
            result = self._parse_json_response(response_text)

            return AgentResponse(
                success=True,
                data=result,
                metadata={
                    "available_count": len(available_hooks),
                    "pending_count": len(pending_hooks),
                },
            )

        except Exception as e:
            logger.error(f"HookManagerAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_user_message(
        self,
        available_hooks: List[Dict[str, Any]],
        triggered_hooks: List[Dict[str, Any]],
        pending_hooks: List[Dict[str, Any]],
        current_scene: str,
        recent_events: List[str],
    ) -> str:
        """构建用户消息"""
        message_parts = []

        # 当前场景
        if current_scene:
            message_parts.append(f"【当前场景】\n{current_scene}")

        # 可用伏笔池
        if available_hooks:
            hooks_text = "\n".join(
                [f"- {h.get('id')}: {h.get('title', '无标题')} (类型：{h.get('hook_type', 'unknown')})" for h in available_hooks[:10]]
            )
            message_parts.append(f"【可用伏笔池】\n{hooks_text}")

        # 已触发待回收伏笔
        if pending_hooks:
            hooks_text = "\n".join(
                [f"- {h.get('id')}: {h.get('title', '无标题')} (优先级：{h.get('priority', 1)})" for h in pending_hooks]
            )
            message_parts.append(f"【待回收伏笔】\n{hooks_text}")
            message_parts.append("请识别回收这些伏笔的最佳时机。")

        # 最近事件
        if recent_events:
            message_parts.append(f"【最近事件】\n{chr(10).join(recent_events)}")

        message_parts.append(
            "\n请决定：\n"
            "1. 哪些伏笔应该在此时埋设（hooks_to_plant）\n"
            "2. 哪些伏笔应该在此时回收（hooks_to_resolve）\n"
            "3. 伏笔状态更新（hooks_status_updates）"
        )

        return "\n\n".join(message_parts)

    async def suggest_hook_planting(
        self,
        hook: Dict[str, Any],
        scene_context: str,
        character_ids: List[str],
    ) -> AgentResponse:
        """
        建议特定伏笔的埋设方式

        Args:
            hook: 伏笔数据
            scene_context: 场景上下文
            character_ids: 在场角色 ID 列表

        Returns:
            AgentResponse: 埋设建议
        """
        prompt = f"""请为以下伏笔设计一个自然的埋设方式：

【伏笔信息】
- ID: {hook.get('id')}
- 标题：{hook.get('title')}
- 描述：{hook.get('description')}
- 类型：{hook.get('hook_type')}

【当前场景】
{scene_context}

【在场角色】
{', '.join(character_ids)}

要求：
1. 埋设方式要自然，不突兀
2. 符合"展示而非告知"原则
3. 与场景和角色行为融合

输出 JSON 格式：
{{
    "method": "埋设方式（如：对话暗示/物品发现/行为异常）",
    "context": "具体情境描述",
    "dialogue_hint": "暗示性台词（如有）",
    "attention_level": "low/medium/high"
}}"""

        try:
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)], temperature=0.6
            )
            result = self._parse_json_response(response_text)
            return AgentResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"伏笔埋设建议失败：{e}")
            return AgentResponse(success=False, error=str(e))

    async def suggest_hook_resolution(
        self,
        hook: Dict[str, Any],
        current_context: str,
    ) -> AgentResponse:
        """
        建议特定伏笔的回收方式

        Args:
            hook: 伏笔数据
            current_context: 当前上下文

        Returns:
            AgentResponse: 回收建议
        """
        prompt = f"""请为以下伏笔设计一个令人满意的回收方式：

【伏笔信息】
- ID: {hook.get('id')}
- 标题：{hook.get('title')}
- 描述：{hook.get('description')}
- 埋设时的情境：{hook.get('plant_context', '未知')}

【当前上下文】
{current_context}

要求：
1. 回收要自然，有"原来如此"的感觉
2. 如果能产生情感冲击更好
3. 与当前情境融合

输出 JSON 格式：
{{
    "resolution": "回收方式描述",
    "emotional_impact": "low/medium/high",
    "ties_to_other_hooks": ["关联的其他伏笔 ID"],
    "suggested_dialogue": "揭示真相时的台词（如有）"
}}"""

        try:
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)], temperature=0.5
            )
            result = self._parse_json_response(response_text)
            return AgentResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"伏笔回收建议失败：{e}")
            return AgentResponse(success=False, error=str(e))

    async def prioritize_hooks(
        self,
        pending_hooks: List[Dict[str, Any]],
        current_plot_progress: float,
    ) -> AgentResponse:
        """
        对待回收伏笔进行优先级排序

        Args:
            pending_hooks: 待回收伏笔列表
            current_plot_progress: 当前剧情进度

        Returns:
            AgentResponse: 排序后的伏笔列表
        """
        if not pending_hooks:
            return AgentResponse(
                success=True,
                data={"prioritized_hooks": [], "count": 0},
            )

        # 按优先级和剧情进度排序
        scored_hooks = []
        for hook in pending_hooks:
            base_priority = hook.get("priority", 1)
            # 剧情进度越靠后，高优先级伏笔权重越高
            progress_bonus = current_plot_progress * 2
            score = base_priority + progress_bonus
            scored_hooks.append({**hook, "priority_score": score})

        scored_hooks.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

        return AgentResponse(
            success=True,
            data={
                "prioritized_hooks": scored_hooks,
                "count": len(scored_hooks),
            },
        )
