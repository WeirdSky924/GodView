"""
角色 Agent - 模拟小说中的角色行为和决策
"""

import json
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
        legacy_trace = None

        # 如果没有提供 prompt_template 且没有 project_id，使用 md prompt 资产 fallback（向后兼容）
        if not prompt_template and not project_id:
            system_prompt = self._build_system_prompt()
            legacy_trace = getattr(self, "_legacy_fallback_trace", None)
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
        if legacy_trace and not self.get_system_prompt_render_trace():
            self._system_prompt_render_trace = legacy_trace

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

    def _load_md_prompt_content(self, prompt_id: str) -> str:
        try:
            from app.services.md_file_service import get_md_file_service

            md_service = get_md_file_service()
            prompt = md_service.get_prompt(prompt_id)
            if prompt:
                content = prompt.get("content") or prompt.get("raw_content") or ""
                if content:
                    return content.strip()
        except Exception as e:
            logger.warning("加载 Character md prompt 失败: prompt_id=%s, error=%s", prompt_id, e)
        return ""

    def _build_md_character_fallback_prompt(self) -> str:
        """从 md prompt 资产构建 Character 备用 prompt。"""
        prompt_ids = [
            "role_character",
            "function_character_roleplay_decision",
            "function_workflow_character_performance",
            "function_character_runtime_context_packet",
            "function_character_performance_packet",
        ]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        return "\n\n".join(parts).strip()

    def _character_fallback_trace(self, *, deprecated: bool = False, prompt_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        return {
            "agent_type": self.AGENT_TYPE.value,
            "scenario": getattr(self, "scenario", None) or self.DEFAULT_SCENARIO,
            "project_id": getattr(self, "project_id", None),
            "template_id": None,
            "template_scenario": None,
            "config_id": None,
            "prompt_ids": prompt_ids or [],
            "skill_ids": [],
            "writing_rule_ids": [],
            "context_blocks": [],
            "fallbacks_used": ["character_deprecated_minimal_system_prompt" if deprecated else "character_md_prompt_fallback"],
            "deprecated_sources_used": ["CharacterAgent._build_system_prompt"] if deprecated else [],
            "missing_prompt_ids": [
                "role_character",
                "function_character_roleplay_decision",
                "function_workflow_character_performance",
                "function_character_runtime_context_packet",
                "function_character_performance_packet",
            ] if deprecated else [],
        }

    def _build_system_prompt(self) -> str:
        """构建角色系统提示（优先使用 prompts/**/*.md 资产）。"""
        md_prompt = self._build_md_character_fallback_prompt()
        if md_prompt:
            self._legacy_fallback_trace = self._character_fallback_trace(
                prompt_ids=[
                    "role_character",
                    "function_character_roleplay_decision",
                    "function_workflow_character_performance",
                    "function_character_runtime_context_packet",
                    "function_character_performance_packet",
                ],
            )
            return md_prompt

        logger.warning("Character md prompt 资产不可用，使用 deprecated 最小硬编码默认系统提示")
        self._legacy_fallback_trace = self._character_fallback_trace(deprecated=True)
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
            prompt_data = await service.build_agent_prompt_with_trace(
                agent_type=self.AGENT_TYPE.value,
                project_id=self.project_id,
                variables=variables,
                scenario=self.scenario,
                context_query=f"{self.character.name} 角色扮演 决策 信息隔离",
            )
            prompt = prompt_data.get("content", "")
            self._system_prompt_render_trace = prompt_data.get("trace", {}) or {}
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
            md_prompt = self._build_md_character_fallback_prompt()
            if md_prompt:
                self.system_prompt = md_prompt
                self._system_prompt_render_trace = self._character_fallback_trace(
                    prompt_ids=[
                        "role_character",
                        "function_character_roleplay_decision",
                        "function_workflow_character_performance",
                        "function_character_runtime_context_packet",
                    ],
                )
            else:
                self.system_prompt = self._build_system_prompt()
                self._system_prompt_render_trace = self._legacy_fallback_trace
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
            character_context_packet = input_data.get("character_context_packet") or {}

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
                character_context_packet=character_context_packet,
            )

            parsed = await self._call_structured(
                CharacterDecisionSchema,
                messages=[HumanMessage(content=user_message)],
                category=UsageCategory.CHARACTER,
            )
            response_data = parsed.model_dump()
            response_data = self._normalize_decision_packet(response_data)

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
        character_context_packet: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建用户消息。"""
        message_parts = [self._build_character_profile_block()]

        packet_block = self._build_character_context_packet_block(character_context_packet)
        if packet_block:
            message_parts.append(packet_block)

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

        task_payload = {
            "scenario": self.scenario,
            "round_number": round_number,
            "total_rounds": total_rounds,
            "round_focus": round_focus,
            "is_supplement": bool(is_supplement),
            "target_word_count": target_word_count,
            "output_schema": "CharacterDecisionSchema",
        }
        message_parts.append("【运行时任务参数】\n" + self._format_context_value(task_payload))

        return "\n\n".join(message_parts)

    def _normalize_string_list(self, value: Any) -> List[str]:
        """把运行期/LLM 输出中的列表字段规范为字符串列表。"""
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                parsed = json.loads(stripped)
                value = parsed
            except (json.JSONDecodeError, TypeError):
                value = [stripped]
        elif isinstance(value, dict):
            value = list(value.values())
        elif not isinstance(value, (list, tuple, set)):
            value = [value]

        result: List[str] = []
        seen = set()
        for item in value:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _normalize_dict_list(self, value: Any) -> List[Dict[str, Any]]:
        """把运行期/LLM 输出中的对象列表字段规范为 dict 列表。"""
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                value = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(value, dict):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return [item for item in value if isinstance(item, dict)]
        return []

    def _format_context_value(self, value: Any) -> str:
        """稳定格式化角色可知上下文包，避免 prompt 中出现 Python repr 噪音。"""
        if value in (None, "", [], {}):
            return ""
        if isinstance(value, str):
            return value.strip()
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except TypeError:
            return str(value)

    def _build_character_context_packet_block(self, packet: Any) -> str:
        """构建 SceneCoordinator 分发给当前角色的可知上下文包。"""
        if not isinstance(packet, dict) or not packet:
            return ""

        ordered_fields = [
            ("visible_scene", "可见场景"),
            ("role_objectives", "当前目标/顾虑"),
            ("relationship_context", "当前角色可知关系"),
            ("state_context", "当前角色状态"),
            ("visible_events", "可见事件"),
            ("public_history", "公开历史"),
            ("information_boundaries", "信息边界"),
            ("forbidden_knowledge", "禁止使用的信息"),
            ("continuity_notes", "连续性提示"),
        ]
        lines = ["【角色可知上下文包】", "以下内容是当前角色可见、可听或合理可推断的信息边界；不得使用包外信息。"]
        for key, label in ordered_fields:
            formatted = self._format_context_value(packet.get(key))
            if formatted:
                lines.append(f"\n### {label}\n{formatted}")

        extra_keys = [key for key in packet.keys() if key not in {field for field, _ in ordered_fields}]
        if extra_keys:
            extra_payload = {key: packet.get(key) for key in extra_keys if packet.get(key) not in (None, "", [], {})}
            formatted = self._format_context_value(extra_payload)
            if formatted:
                lines.append(f"\n### 其他可知信息\n{formatted}")
        return "\n".join(lines)

    def _normalize_decision_packet(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """规范化角色输出，确保公开/私有边界和兼容字段稳定。"""
        packet = dict(data or {})
        dialogue = str(packet.get("dialogue") or "")
        action = str(packet.get("action") or "")
        public_content = str(packet.get("public_content") or "").strip()
        inner_thought = str(packet.get("inner_thought") or packet.get("private_thought") or "")
        private_thought = str(packet.get("private_thought") or inner_thought or "")
        if not public_content:
            public_parts = []
            if action:
                public_parts.append(f"（{action}）")
            if dialogue:
                public_parts.append(dialogue)
            public_content = " ".join(part for part in public_parts if part).strip()

        packet["dialogue"] = dialogue
        packet["action"] = action
        packet["public_content"] = public_content
        packet["inner_thought"] = inner_thought
        packet["private_thought"] = private_thought
        packet["emotion"] = str(packet.get("emotion") or "neutral")
        packet["intent"] = str(packet.get("intent") or "")
        packet["perceived_facts"] = self._normalize_string_list(packet.get("perceived_facts"))
        packet["misinterpretations"] = self._normalize_string_list(packet.get("misinterpretations"))
        packet["withheld_information"] = self._normalize_string_list(packet.get("withheld_information"))
        packet["relationship_delta"] = self._normalize_dict_list(packet.get("relationship_delta"))
        packet["state_delta"] = self._normalize_dict_list(packet.get("state_delta"))
        packet["continuity_notes"] = self._normalize_string_list(packet.get("continuity_notes"))
        packet["warnings"] = self._normalize_string_list(packet.get("warnings"))
        return packet

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
