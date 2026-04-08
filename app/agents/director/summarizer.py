"""
剧情总结员 Agent - 将对话压缩为事件摘要
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_template import AgentType

logger = logging.getLogger(__name__)


class SummarizerAgent(BaseAgent):
    """剧情总结员 Agent"""

    AGENT_TYPE = AgentType.SUMMARIZER

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
            name="SummarizerAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（Summarizer 特定）"""
        return {
            "agent_role": "剧情总结员",
            "task_description": "将角色之间的对话压缩成干练的事件摘要",
        }

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示（向后兼容）"""
        return """你是剧情总结员。你的任务是将角色之间的对话压缩成干练的"事件摘要"。

要求：
1. 提取核心信息：谁做了什么，结果如何
2. 识别并标记"潜台词"——角色言外之意
3. 检测关键伏笔触发点
4. 保持客观，不添加主观解读
5. 评估信息增量（0-1 分）

输出 JSON 格式：
{
    "summary": "一句话事件摘要",
    "subtext_markers": [{"speaker": "角色名", "implied_meaning": "潜台词内容"}],
    "hook_triggers": ["相关伏笔 ID 列表"],
    "info_gain_score": 0.0-1.0,
    "raw_dialogue_refs": ["需要保留原始对话的引用 ID"]
}"""

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行剧情总结

        Args:
            input_data: 包含以下字段
                - dialogue_history: 对话历史列表
                - participants: 参与角色列表
                - context: 当前情境
                - active_hooks: 当前活跃的伏笔列表

        Returns:
            AgentResponse: 总结结果
        """
        try:
            dialogue_history = input_data.get("dialogue_history", [])
            participants = input_data.get("participants", [])
            context = input_data.get("context", "")
            active_hooks = input_data.get("active_hooks", [])

            # 构建用户消息
            user_message = self._build_user_message(
                dialogue_history=dialogue_history,
                participants=participants,
                context=context,
                active_hooks=active_hooks,
            )

            # 调用 LLM
            response_text = await self._call_llm(
                messages=[HumanMessage(content=user_message)], temperature=0.3
            )

            # 解析响应
            result = self._parse_json_response(response_text)

            return AgentResponse(
                success=True,
                data=result,
                metadata={"participant_count": len(participants), "dialogue_turns": len(dialogue_history)},
            )

        except Exception as e:
            logger.error(f"SummarizerAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_user_message(
        self,
        dialogue_history: List[Dict[str, str]],
        participants: List[str],
        context: str,
        active_hooks: List[Dict[str, Any]],
    ) -> str:
        """构建用户消息"""
        message_parts = []

        # 情境
        if context:
            message_parts.append(f"【当前情境】\n{context}")

        # 参与角色
        if participants:
            message_parts.append(f"【参与角色】\n{', '.join(participants)}")

        # 对话历史
        if dialogue_history:
            dialogue_text = "\n".join(
                [f"{d.get('speaker', 'Unknown')}: {d.get('content', '')}" for d in dialogue_history[-10:]]
            )
            message_parts.append(f"【对话历史】\n{dialogue_text}")

        # 活跃伏笔
        if active_hooks:
            hooks_text = "\n".join(
                [f"- {h.get('id')}: {h.get('title', '无标题')}" for h in active_hooks]
            )
            message_parts.append(f"【活跃伏笔】\n{hooks_text}")
            message_parts.append("如果对话触发了任何伏笔，请在 hook_triggers 中列出相关 ID。")

        message_parts.append(
            "\n请将以上对话压缩成事件摘要，识别潜台词，检测伏笔触发。"
        )

        return "\n\n".join(message_parts)

    async def summarize_batch(
        self, multiple_dialogues: List[Dict[str, Any]]
    ) -> AgentResponse:
        """
        批量总结多段对话

        Args:
            multiple_dialogues: 多段对话数据

        Returns:
            AgentResponse: 包含多个总结结果
        """
        results = []
        for dialogue_data in multiple_dialogues:
            result = await self.execute(dialogue_data)
            if result.success:
                results.append(result.data)
            else:
                return result

        return AgentResponse(
            success=True,
            data={"summaries": results, "count": len(results)},
        )
