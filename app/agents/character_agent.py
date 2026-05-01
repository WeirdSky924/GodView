"""
角色 Agent - 模拟小说中的角色行为和决策
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_output_schemas import CharacterDecisionSchema
from app.models.character import Character
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory
from app.services.structured_llm import StructuredOutputError

logger = logging.getLogger(__name__)


class CharacterAgent(BaseAgent):
    """角色 Agent"""

    AGENT_TYPE = AgentType.CHARACTER
    DEFAULT_SCENARIO = "roleplay"

    def __init__(
        self,
        character: Character,
        model: Optional[BaseLanguageModel] = None,
        prompt_template: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        self.character = character
        self._manual_prompt_provided = bool(prompt_template)

        # 如果没有提供 prompt_template 且没有 project_id，使用最小 fallback（向后兼容）
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
            agent_id=agent_id or character.id,
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
            "current_region_id": char.current_region_id or "未知",
            "current_location_reason": char.current_location_reason or "未记录",
            "goals": ", ".join(char.goals) if char.goals else "无特定目标",
            "inventory": ", ".join(char.inventory) if char.inventory else "无",
        }

    def _build_system_prompt(self) -> str:
        """构建角色系统提示（deprecated fallback）。"""
        return (
            f"你是{self.character.name}，一个虚构故事中的角色。"
            "优先使用 Agent Template 绑定的 md prompt / skills / writing-rules；"
            "仅在未能加载配置资产时，将此最小提示作为 deprecated fallback。"
        )

    def _build_character_profile_block(self) -> str:
        """构建动态角色档案上下文。"""
        variables = self._get_default_variables()
        return "\n".join(
            [
                "【当前角色档案】",
                f"- 名称：{variables['character_name']}",
                f"- 描述：{variables['character_description']}",
                f"- 性格特质：{variables['personality_traits']}",
                f"- 背景故事：{variables['background_story']}",
                f"- 说话风格：{variables['speech_pattern']}",
                f"- 常用词汇：{variables['lexicon']}",
                f"- 禁止使用：{variables['forbidden_words']}",
                f"- 当前位置：{variables['current_location']}",
                f"- 地图区域 ID：{variables['current_region_id']}",
                f"- 来到此地原因：{variables['current_location_reason']}",
                f"- 当前目标：{variables['goals']}",
                f"- 当前物品：{variables['inventory']}",
            ]
        )

    async def _ensure_system_prompt_loaded(self):
        """按 Character 动态变量加载 Agent Template prompt。"""
        if self._system_prompt_loaded or not self._pending_system_prompt_load:
            return

        if not self.project_id or not self.AGENT_TYPE:
            self._system_prompt_loaded = True
            self._pending_system_prompt_load = False
            return

        try:
            from app.services.agent_prompt_service import get_agent_prompt_service

            variables = self._get_default_variables()
            variables.update({"scenario": self.scenario})
            service = get_agent_prompt_service()
            prompt = await service.build_agent_prompt(
                agent_type=self.AGENT_TYPE.value,
                project_id=self.project_id,
                variables=variables,
                scenario=self.scenario,
                context_query=f"{self.character.name} 角色扮演 决策 信息隔离",
            )
            if prompt.strip():
                self.system_prompt = prompt.strip()
                logger.debug(
                    "CharacterAgent 从模板加载 prompt 成功: character=%s, project=%s, scenario=%s",
                    self.character.name,
                    self.project_id,
                    self.scenario,
                )
        except Exception as e:
            logger.warning(
                "CharacterAgent 加载模板 prompt 失败: character=%s, project=%s, scenario=%s, error=%s",
                self.character.name,
                self.project_id,
                self.scenario,
                e,
            )

        if not self.system_prompt:
            self.system_prompt = self._build_system_prompt()
        self._system_prompt_loaded = True
        self._pending_system_prompt_load = False

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
                round_number=input_data.get("round_number"),
                total_rounds=input_data.get("total_rounds"),
                round_focus=input_data.get("round_focus"),
                is_supplement=bool(input_data.get("is_supplement", False)),
                target_word_count=input_data.get("target_word_count"),
            )

            parsed = await self._call_structured(
                CharacterDecisionSchema,
                messages=[HumanMessage(content=user_message)],
                category=UsageCategory.CHARACTER,
            )
            response_data = parsed.model_dump()

            return AgentResponse(
                success=True,
                data=response_data,
                metadata={"character_id": self.character.id, "model_used": self.name},
            )

        except StructuredOutputError as e:
            logger.error(f"CharacterAgent structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"CharacterAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_user_message(
        self,
        context: str,
        present_characters: List[str],
        recent_events: List[str],
        dialogue_history: List[Dict[str, str]],
        round_number: Optional[int] = None,
        total_rounds: Optional[int] = None,
        round_focus: Optional[str] = None,
        is_supplement: bool = False,
        target_word_count: Optional[int] = None,
    ) -> str:
        """构建用户消息。"""
        message_parts = [self._build_character_profile_block()]

        if context:
            message_parts.append(f"【当前情境】\n{context}")

        if present_characters:
            message_parts.append(f"【在场人物】\n{', '.join(present_characters)}")

        if recent_events:
            message_parts.append(f"【最近发生的事】\n{chr(10).join(recent_events)}")

        if dialogue_history:
            dialogue_text = "\n".join(
                [f"{d.get('speaker') or d.get('agent', 'Unknown')}: {d.get('content', '')}" for d in dialogue_history[-5:]]
            )
            message_parts.append(f"【对话历史】\n{dialogue_text}")

        task_lines = ["根据当前角色档案和可见情境，生成下一步角色决策。"]
        if round_number and total_rounds:
            task_lines.append(f"当前是第 {round_number}/{total_rounds} 轮互动。")
        if round_focus:
            task_lines.append(f"本轮剧情焦点：{round_focus}")
        if is_supplement:
            task_lines.append("这是补充表演，只补足当前场景素材，不扩写成完整章节正文。")
        if target_word_count:
            task_lines.append(f"目标长度参考：约 {target_word_count} 字。")
        task_lines.append("只使用当前角色可知信息，输出必须符合 CharacterDecisionSchema。")
        message_parts.append("【当前任务】\n" + "\n".join(f"- {line}" for line in task_lines))

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
        if self.project_id and not self._manual_prompt_provided:
            self.system_prompt = ""
            self._system_prompt_loaded = False
            self._pending_system_prompt_load = True
        else:
            self.system_prompt = self._build_system_prompt()
