"""
内容执行官 Agent - 将剧情意图润色成小说文本
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """内容执行官 Agent"""

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        system_prompt = """你是内容执行官，负责将干巴巴的剧情意图润色成有小说质感的连贯文本。

写作要求：
1. 展示，而不是告知 (Show, Don't Tell)
2. 描写比例：动作 40% + 神态 40% + 对话 20%
3. 保持与前文风格一致
4. 使用生动的感官描写（视觉、听觉、嗅觉、触觉）
5. 对话要符合角色性格和口癖

输出 JSON 格式：
{
    "content": "生成的小说正文",
    "word_count": 字数统计，
    "style_check": {
        "action_ratio": 0.4,
        "expression_ratio": 0.4,
        "dialogue_ratio": 0.2
    },
    "hooks_embedded": ["嵌入的伏笔 ID 列表"]
}"""

        super().__init__(
            name="WriterAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
        )

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行小说文本生成

        Args:
            input_data: 包含以下字段
                - intents: 需要表达的意图列表
                - environment: 环境描述
                - character_moods: 角色情绪状态
                - hooks: 需要埋设/回收的伏笔
                - previous_style: 前文风格样本
                - word_count: 目标字数

        Returns:
            AgentResponse: 生成的小说文本
        """
        try:
            intents = input_data.get("intents", [])
            environment = input_data.get("environment", "")
            character_moods = input_data.get("character_moods", {})
            hooks = input_data.get("hooks", [])
            previous_style = input_data.get("previous_style", "")
            word_count = input_data.get("word_count", 500)

            # 构建用户消息
            user_message = self._build_user_message(
                intents=intents,
                environment=environment,
                character_moods=character_moods,
                hooks=hooks,
                previous_style=previous_style,
                word_count=word_count,
            )

            # 调用 LLM
            response_text = await self._call_llm(
                messages=[HumanMessage(content=user_message)], temperature=0.7
            )

            # 解析响应
            result = self._parse_json_response(response_text)

            # 验证风格一致性（如果有前文样本）
            if previous_style and self.config.get("style_check_enabled", True):
                style_check = await self._check_style_consistency(
                    generated_text=result.get("content", ""),
                    previous_style=previous_style,
                )
                result["style_check_result"] = style_check

            return AgentResponse(
                success=True,
                data=result,
                metadata={
                    "target_word_count": word_count,
                    "actual_word_count": result.get("word_count", 0),
                },
            )

        except Exception as e:
            logger.error(f"WriterAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_user_message(
        self,
        intents: List[str],
        environment: str,
        character_moods: Dict[str, str],
        hooks: List[Dict[str, Any]],
        previous_style: str,
        word_count: int,
    ) -> str:
        """构建用户消息"""
        message_parts = []

        # 环境描写
        if environment:
            message_parts.append(f"【环境】\n{environment}")

        # 需要表达的意图
        if intents:
            message_parts.append(f"【需要表达的意图】\n{chr(10).join(intents)}")

        # 角色情绪
        if character_moods:
            moods_text = "\n".join(
                [f"- {name}: {mood}" for name, mood in character_moods.items()]
            )
            message_parts.append(f"【角色情绪】\n{moods_text}")

        # 伏笔处理
        if hooks:
            hooks_text = "\n".join(
                [f"- {h.get('id')}: {h.get('type', 'plant')} - {h.get('description', '')}" for h in hooks]
            )
            message_parts.append(f"【伏笔处理】\n{hooks_text}")

        # 前文风格样本
        if previous_style:
            message_parts.append(f"【前文风格样本】\n{previous_style[:500]}")
            message_parts.append("请保持与上述样本风格一致。")

        # 字数要求
        message_parts.append(f"【目标字数】\n约{word_count}字")

        message_parts.append(
            "\n请将以上要素融合，生成一段有小说质感的连贯文本。"
            "注意：\n"
            "- 多用动作和神态描写，少用直接告知\n"
            "- 对话要符合角色性格\n"
            "- 伏笔要自然嵌入，不突兀"
        )

        return "\n\n".join(message_parts)

    async def _check_style_consistency(
        self,
        generated_text: str,
        previous_style: str,
    ) -> Dict[str, Any]:
        """
        检查风格一致性

        Args:
            generated_text: 生成的文本
            previous_style: 前文风格样本

        Returns:
            Dict: 风格一致性检查结果
        """
        prompt = f"""请检查以下两段文本的风格一致性：

【前文样本】
{previous_style[:1000]}

【新生成文本】
{generated_text[:1000]}

请从以下维度评估：
1. 叙述视角是否一致
2. 句式长短是否相似
3. 用词风格是否统一
4. 节奏感是否连贯

输出 JSON 格式：
{{
    "is_consistent": true/false,
    "confidence": 0.0-1.0,
    "differences": ["风格差异列表"],
    "suggestions": ["修改建议"]
}}"""

        try:
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)], temperature=0.3
            )
            return self._parse_json_response(response_text)
        except Exception:
            return {"is_consistent": True, "confidence": 0.5, "differences": [], "suggestions": []}

    async def generate_scene_description(
        self,
        location: str,
        atmosphere: str,
        sensory_details: Optional[Dict[str, str]] = None,
    ) -> AgentResponse:
        """
        生成场景描写

        Args:
            location: 地点
            atmosphere: 氛围
            sensory_details: 感官细节

        Returns:
            AgentResponse: 场景描写
        """
        prompt = f"""请生成一段场景描写：

【地点】
{location}

【氛围】
{atmosphere}

【感官细节】
{sensor y_details if sensory_details else '自由发挥'}

要求：
- 调动多种感官（视觉、听觉、嗅觉、触觉）
- 100-200 字
- 有画面感

输出 JSON 格式：
{{
    "description": "场景描写文本",
    "word_count": 字数，
    "sensory_elements": {{
        "visual": "视觉元素",
        "auditory": "听觉元素",
        "olfactory": "嗅觉元素",
        "tactile": "触觉元素"
    }}
}}"""

        try:
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)], temperature=0.6
            )
            result = self._parse_json_response(response_text)
            return AgentResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"场景描写生成失败：{e}")
            return AgentResponse(success=False, error=str(e))

    async def rewrite_with_character_voice(
        self,
        original_text: str,
        character_name: str,
        speech_pattern: str,
        lexicon: List[str],
        forbidden_words: List[str],
    ) -> AgentResponse:
        """
        根据角色声音重写文本

        Args:
            original_text: 原始文本
            character_name: 角色名称
            speech_pattern: 说话风格
            lexicon: 常用词汇
            forbidden_words: 禁用语

        Returns:
            AgentResponse: 重写后的文本
        """
        prompt = f"""请将以下文本改写为符合角色声音的版本：

【角色信息】
- 名称：{character_name}
- 说话风格：{speech_pattern}
- 常用词汇：{', '.join(lexicon) if lexicon else '无特殊要求'}
- 禁止使用：{', '.join(forbidden_words) if forbidden_words else '无禁止'}

【原始文本】
{original_text}

要求：
1. 保持原意不变
2. 调整用词和句式以符合角色声音
3. 不使用禁用语

输出 JSON 格式：
{{
    "rewritten_text": "改写后的文本",
    "changes_made": ["修改说明列表"]
}}"""

        try:
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)], temperature=0.5
            )
            result = self._parse_json_response(response_text)
            return AgentResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"角色声音重写失败：{e}")
            return AgentResponse(success=False, error=str(e))
