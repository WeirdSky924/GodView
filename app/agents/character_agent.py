"""
角色 Agent - 模拟小说中的角色行为和决策
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.character import Character
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory

logger = logging.getLogger(__name__)


class CharacterAgent(BaseAgent):
    """角色 Agent"""

    AGENT_TYPE = AgentType.CHARACTER

    def __init__(
        self,
        character: Character,
        model: Optional[BaseLanguageModel] = None,
        prompt_template: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
    ):
        self.character = character

        # 如果没有提供 prompt_template，使用旧的构建方式（向后兼容）
        if not prompt_template and not project_id:
            system_prompt = self._build_system_prompt()
        else:
            system_prompt = prompt_template

        super().__init__(
            name=f"CharacterAgent-{character.name}",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（Character 特定）"""
        char = self.character

        # 处理 personality_traits - 可能是 PersonalityTrait 对象列表或字典列表
        traits_list = []
        for t in (char.personality_traits or []):
            if hasattr(t, 'name') and hasattr(t, 'value'):
                traits_list.append(f"{t.name}({t.value})")
            elif isinstance(t, dict):
                traits_list.append(f"{t.get('name', '未知')}({t.get('value', 0)})")
            else:
                traits_list.append(str(t))
        traits_desc = ", ".join(traits_list)

        return {
            "character_name": char.name,
            "character_description": char.description or "无",
            "personality_traits": traits_desc,
            "background_story": char.background_story or "无",
            "speech_pattern": char.speech_pattern or "无特殊限制",
            "lexicon": ", ".join(char.lexicon) if char.lexicon else "无限制",
            "forbidden_words": ", ".join(char.forbidden_words) if char.forbidden_words else "无禁止",
            "current_location": char.current_location or "未知",
            "goals": ", ".join(char.goals) if char.goals else "无特定目标",
            "inventory": ", ".join(char.inventory) if char.inventory else "无",
        }

    def _build_system_prompt(self) -> str:
        """构建角色系统提示"""
        char = self.character

        # 处理 personality_traits - 可能是 PersonalityTrait 对象列表或字典列表
        traits_list = []
        for t in (char.personality_traits or []):
            if hasattr(t, 'name') and hasattr(t, 'value'):
                traits_list.append(f"{t.name}({t.value})")
            elif isinstance(t, dict):
                traits_list.append(f"{t.get('name', '未知')}({t.get('value', 0)})")
            else:
                traits_list.append(str(t))
        traits_desc = ", ".join(traits_list)

        prompt = f"""你是{char.name}，一个虚构故事中的角色。请完全沉浸在这个角色中。

【角色设定】
- 名称：{char.name}
- 描述：{char.description or '无'}
- 性格特质：{traits_desc}
- 背景故事：{char.background_story or '无'}
- 说话风格：{char.speech_pattern or '无特殊限制'}

【语言规范】
- 常用词汇：{', '.join(char.lexicon) if char.lexicon else '无限制'}
- 禁止使用：{', '.join(char.forbidden_words) if char.forbidden_words else '无禁止'}

【当前状态】
- 位置：{char.current_location or '未知'}
- 目标：{', '.join(char.goals) if char.goals else '无特定目标'}
- 物品：{', '.join(char.inventory) if char.inventory else '无'}

请根据情境做出符合角色设定的决策。输出 JSON 格式：
{{
    "dialogue": "你的台词",
    "action": "你的动作",
    "inner_thought": "内心独白",
    "emotion": "当前情绪"
}}"""

        return prompt

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行角色决策

        Args:
            input_data: 包含以下字段
                - context: 当前情境描述
                - present_characters: 在场角色列表
                - recent_events: 最近发生的事件
                - dialogue_history: 对话历史

        Returns:
            AgentResponse: 角色决策结果
        """
        try:
            context = input_data.get("context", "")
            present_characters = input_data.get("present_characters", [])
            recent_events = input_data.get("recent_events", [])
            dialogue_history = input_data.get("dialogue_history", [])

            # 构建用户消息
            user_message = self._build_user_message(
                context=context,
                present_characters=present_characters,
                recent_events=recent_events,
                dialogue_history=dialogue_history,
            )

            # 调用 LLM
            response_text = await self._call_llm(
                messages=[HumanMessage(content=user_message)],
                category=UsageCategory.CHARACTER
            )

            # 解析响应
            try:
                response_data = self._parse_json_response(response_text)
            except ValueError:
                # 如果 JSON 解析失败，尝试提取关键信息
                response_data = {
                    "dialogue": response_text.strip(),
                    "action": "",
                    "inner_thought": "",
                    "emotion": "neutral",
                }

            return AgentResponse(
                success=True,
                data=response_data,
                metadata={"character_id": self.character.id, "model_used": self.name},
            )

        except Exception as e:
            logger.error(f"CharacterAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_user_message(
        self,
        context: str,
        present_characters: List[str],
        recent_events: List[str],
        dialogue_history: List[Dict[str, str]],
    ) -> str:
        """构建用户消息"""
        message_parts = []

        # 当前情境
        if context:
            message_parts.append(f"【当前情境】\n{context}")

        # 在场人物
        if present_characters:
            message_parts.append(f"【在场人物】\n{', '.join(present_characters)}")

        # 最近事件
        if recent_events:
            message_parts.append(f"【最近发生的事】\n{chr(10).join(recent_events)}")

        # 对话历史
        if dialogue_history:
            dialogue_text = "\n".join(
                [f"{d.get('speaker', 'Unknown')}: {d.get('content', '')}" for d in dialogue_history[-5:]]  # 最近 5 轮
            )
            message_parts.append(f"【对话历史】\n{dialogue_text}")

        # 行动请求
        message_parts.append(
            "\n请决定你接下来的行动：\n"
            "1. 你会说什么（如果有）\n"
            "2. 你会做什么动作\n"
            "3. 你的内心独白\n"
            "4. 你的当前情绪"
        )

        return "\n\n".join(message_parts)

    def update_character(self, updates: Dict[str, Any]):
        """
        更新角色状态

        Args:
            updates: 更新字段
        """
        for key, value in updates.items():
            if hasattr(self.character, key):
                setattr(self.character, key, value)

        # 更新系统提示
        self.system_prompt = self._build_system_prompt()
