"""
总编剧 Agent - 把控主线进度和剧情走向
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_template import AgentType

logger = logging.getLogger(__name__)


class MasterPlotterAgent(BaseAgent):
    """总编剧 Agent"""

    AGENT_TYPE = AgentType.MASTER_PLOTTER

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
            name="MasterPlotterAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（MasterPlotter 特定）"""
        return {
            "agent_role": "总编剧",
            "task_description": "把控主线进度和剧情走向",
        }

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示（向后兼容）"""
        return """你是总编剧，负责把控主线进度和剧情走向。

你的职责：
1. 评估当前剧情是否应该推进到下一阶段
2. 决定是否需要埋设"即将发生的事件"
3. 如果触发强制推进，提供合理的外部事件
4. 确保剧情不跑题、不拖沓

输出 JSON 格式：
{
    "should_advance": true/false,
    "reason": "判断理由",
    "current_progress": 0.0-1.0,
    "foreshadow_event": "即将发生的事件描述（如有）",
    "forced_event": "强制推进事件（如触发阈值）",
    "next_milestone": "下一个剧情里程碑"
}"""

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行主线剧情评估

        Args:
            input_data: 包含以下字段
                - main_plot_progress: 主线进度 (0-1)
                - pending_hooks: 已埋设未回收的伏笔列表
                - chapter_goal: 当前章节目标
                - recent_events: 最近发生的事件
                - interaction_turns: 当前交互轮次
                - max_turns_threshold: 最大轮次阈值

        Returns:
            AgentResponse: 剧情推进决策
        """
        try:
            main_plot_progress = input_data.get("main_plot_progress", 0.0)
            pending_hooks = input_data.get("pending_hooks", [])
            chapter_goal = input_data.get("chapter_goal", "")
            recent_events = input_data.get("recent_events", [])
            interaction_turns = input_data.get("interaction_turns", 0)
            max_turns_threshold = input_data.get("max_turns_threshold", 5)

            # 构建用户消息
            user_message = self._build_user_message(
                main_plot_progress=main_plot_progress,
                pending_hooks=pending_hooks,
                chapter_goal=chapter_goal,
                recent_events=recent_events,
                interaction_turns=interaction_turns,
                max_turns_threshold=max_turns_threshold,
            )

            # 调用 LLM
            response_text = await self._call_llm(
                messages=[HumanMessage(content=user_message)], temperature=0.5
            )

            # 解析响应
            result = self._parse_json_response(response_text)

            # 检查是否需要强制推进
            if interaction_turns >= max_turns_threshold and not result.get("forced_event"):
                result["forced_event"] = await self._generate_forced_event(
                    recent_events=recent_events,
                    pending_hooks=pending_hooks,
                )

            return AgentResponse(
                success=True,
                data=result,
                metadata={
                    "progress": main_plot_progress,
                    "turns": interaction_turns,
                    "threshold": max_turns_threshold,
                },
            )

        except Exception as e:
            logger.error(f"MasterPlotterAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_user_message(
        self,
        main_plot_progress: float,
        pending_hooks: List[Dict[str, Any]],
        chapter_goal: str,
        recent_events: List[str],
        interaction_turns: int,
        max_turns_threshold: int,
    ) -> str:
        """构建用户消息"""
        message_parts = []

        # 主线进度
        message_parts.append(f"【主线进度】\n{main_plot_progress * 100:.1f}%")

        # 当前章节目标
        if chapter_goal:
            message_parts.append(f"【当前章节目标】\n{chapter_goal}")

        #  pending 伏笔
        if pending_hooks:
            hooks_text = "\n".join(
                [f"- {h.get('id')}: {h.get('title', '无标题')} (优先级：{h.get('priority', 1)})" for h in pending_hooks]
            )
            message_parts.append(f"【已埋设未回收伏笔】\n{hooks_text}")

        # 最近事件
        if recent_events:
            message_parts.append(f"【最近发生的事件】\n{chr(10).join(recent_events)}")

        # 交互轮次
        message_parts.append(f"【当前交互轮次】\n{interaction_turns} / {max_turns_threshold}")
        if interaction_turns >= max_turns_threshold:
            message_parts.append("⚠️ 已达到强制推进阈值！")

        message_parts.append(
            "\n请评估：\n"
            "1. 是否应该推进剧情到下一阶段\n"
            "2. 是否需要埋设即将发生的事件\n"
            "3. 如需强制推进，请提供合理的外部事件"
        )

        return "\n\n".join(message_parts)

    async def _generate_forced_event(
        self,
        recent_events: List[str],
        pending_hooks: List[Dict[str, Any]],
    ) -> str:
        """
        生成强制推进事件

        Args:
            recent_events: 最近事件
            pending_hooks: 待回收伏笔

        Returns:
            str: 强制事件描述
        """
        prompt = f"""基于以下情境，生成一个合理的外部事件来强制推进剧情：

【最近事件】
{chr(10).join(recent_events[-3:]) if recent_events else '无'}

【待回收伏笔】
{chr(10).join([h.get('title', '') for h in pending_hooks[:3]]) if pending_hooks else '无'}

要求：
1. 事件应该是外部的、突然的（如：刺客袭击、天灾、意外来客）
2. 如果能与现有伏笔关联更好
3. 简洁描述（50 字以内）"""

        try:
            response = await self._call_llm(
                messages=[HumanMessage(content=prompt)],
                temperature=0.7,
                max_tokens=100,
            )
            return response.strip()
        except Exception:
            # 默认 fallback 事件
            fallback_events = [
                "突然传来一声巨响，地面开始震动",
                "就在此时，窗外飞进一支冷箭",
                "远处传来急促的号角声",
                "天空突然乌云密布，狂风大作",
            ]
            import random
            return random.choice(fallback_events)

    async def set_next_milestone(
        self, current_progress: float, plot_goals: List[str]
    ) -> AgentResponse:
        """
        设定下一个剧情里程碑

        Args:
            current_progress: 当前进度
            plot_goals: 剧情目标列表

        Returns:
            AgentResponse: 里程碑设定
        """
        remaining_goals = [
            g for i, g in enumerate(plot_goals)
            if i / len(plot_goals) > current_progress
        ]

        next_goal = remaining_goals[0] if remaining_goals else "完成最终目标"

        return AgentResponse(
            success=True,
            data={
                "next_milestone": next_goal,
                "estimated_progress": min(current_progress + 0.2, 1.0),
            },
        )
