"""
内容执行官 Agent - 将剧情意图润色成小说文本
支持自动字数检查和续写
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """内容执行官 Agent"""

    AGENT_TYPE = AgentType.WRITER
    MAX_RETRY_COUNT = 3  # 最大续写次数

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
            name="WriterAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（Writer 特定）"""
        return {
            "agent_role": "内容执行官",
            "task_description": "将剧情意图润色成长篇网文文本",
        }

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示（向后兼容）"""
        return """你是内容执行官，负责将剧情意图润色成有网文质感的连贯文本。

【重要：长篇网文创作原则】
这是一部长篇小说，不是短篇故事！你需要：
1. **可持续发展**：所有剧情、设定、伏笔都要能够支撑后续几百章的发展
2. **渐进式展开**：不要一次性揭露所有设定和秘密，要留有余地
3. **避免急躁感**：不要让读者感觉"开头就是高潮，马上要大结局"
4. **埋下长线伏笔**：为后续剧情埋下可回收的伏笔，不是所有伏笔都要立刻揭晓
5. **角色成长空间**：主角和配角都要有成长的空间，不要一开始就无敌
6. **世界观层次**：世界观要有多层次，让读者感觉还有更深的内容待探索

【网文写作技巧】
1. 展示，而不是告知 (Show, Don't Tell)
2. 描写比例：动作 35% + 神态 35% + 对话 30%
3. 段落简短有力，便于移动端阅读
4. 使用生动的感官描写（视觉、听觉、嗅觉、触觉）
5. 对话要符合角色性格和口癖

【字数要求】
- 必须达到目标字数的 80% 以上
- 如果字数不足，系统会要求你继续写作
- 你会在一次生成中完成足够字数的内容

【网文节奏技巧】
- 关键时刻要有"卡点"感
- 战斗场面要有画面感和节奏感
- 对话要有"梗"和记忆点
- 适当安排反转和惊喜
- 爽点设计要到位（升级、打脸、逆袭、揭秘等）

输出 JSON 格式：
{
    "content": "生成的网文正文",
    "word_count": 字数统计（必须自行统计）,
    "style_check": {
        "action_ratio": 0.35,
        "expression_ratio": 0.35,
        "dialogue_ratio": 0.3
    },
    "climax_points": ["本章爽点描述"],
    "hooks_embedded": ["嵌入的伏笔描述"],
    "future_setup": ["为后续剧情埋下的铺垫"]
}"""

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行小说文本生成
        支持自动字数检查和续写

        Args:
            input_data: 包含以下字段
                - intents: 需要表达的意图列表
                - environment: 环境描述
                - character_moods: 角色情绪状态
                - hooks: 需要埋设/回收的伏笔
                - previous_style: 前文风格样本
                - word_count: 目标字数
                - auto_write_mode: 自动写作模式（使用完整提示）
                - writing_prompt: 自动写作的完整提示
                - is_retry: 是否是重试
                - retry_count: 重试次数
                - retry_message: 重试提示消息
                - discussion_summary: 团队讨论的总结（如有）
                - chapter_num: 当前章节号（用于长篇创作意识）
                - total_chapters: 总章节数（用于长篇创作意识）

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
            auto_write_mode = input_data.get("auto_write_mode", False)
            writing_prompt = input_data.get("writing_prompt", "")
            discussion_summary = input_data.get("last_discussion_summary", "")
            chapter_num = input_data.get("chapter_num", 1)
            total_chapters = input_data.get("total_chapters", 10)
            world_info = input_data.get("world_info")  # 世界观设定

            # 重试相关上下文
            is_retry = input_data.get("is_retry", False)
            retry_count = input_data.get("retry_count", 0)
            retry_message = input_data.get("retry_message", "")

            # 计算最低字数要求
            min_word_count = int(word_count * 0.8)

            # 构建用户消息
            if auto_write_mode and writing_prompt:
                # 自动写作模式：使用完整提示
                user_message = writing_prompt
            else:
                # 普通模式：构建用户消息
                user_message = self._build_user_message(
                    intents=intents,
                    environment=environment,
                    character_moods=character_moods,
                    hooks=hooks,
                    previous_style=previous_style,
                    word_count=word_count,
                    min_word_count=min_word_count,
                    discussion_summary=discussion_summary,
                    chapter_num=chapter_num,
                    total_chapters=total_chapters,
                    world_info=world_info,
                )

            # 如果是重试，添加重试提示
            if is_retry and retry_message:
                user_message = f"{retry_message}\n\n---\n\n{user_message}"
                logger.info(f"Writer Agent 第 {retry_count} 次重试，已添加评估反馈")

            # 调用 LLM（自动写作模式使用更高的 temperature 增加创造性）
            temperature = 0.8 if auto_write_mode else 0.7
            response_text = await self._call_llm(
                messages=[HumanMessage(content=user_message)], temperature=temperature,
                category=UsageCategory.CHAPTER
            )

            # 解析响应
            result = self._parse_json_response(response_text)

            # 如果解析失败，尝试直接返回文本
            if not result or not result.get("content"):
                result = {
                    "content": response_text,
                    "word_count": len(response_text),
                }

            # 进行字数统计验证
            content = result.get("content", "")
            actual_word_count = self._count_words(content)

            # 如果LLM报告的字数与实际统计差距较大，使用实际统计
            if abs(result.get("word_count", 0) - actual_word_count) > 100:
                logger.warning(f"字数统计差异较大: LLM报告 {result.get('word_count')} vs 实际 {actual_word_count}")
                result["word_count"] = actual_word_count

            # ========== 自动续写逻辑 ==========
            # 如果字数不足且未达到最大重试次数，自动续写
            continue_count = 0
            while actual_word_count < min_word_count and continue_count < self.MAX_RETRY_COUNT:
                continue_count += 1
                shortage = min_word_count - actual_word_count

                logger.info(f"字数不足 ({actual_word_count}/{min_word_count})，开始第 {continue_count} 次续写...")

                # 构建续写提示
                continue_prompt = self._build_continue_prompt(
                    existing_content=content,
                    shortage=shortage,
                    intents=intents,
                    character_moods=character_moods,
                    chapter_num=chapter_num,
                    total_chapters=total_chapters,
                )

                # 调用 LLM 续写
                continue_response = await self._call_llm(
                    messages=[HumanMessage(content=continue_prompt)], temperature=0.75,
                    category=UsageCategory.CHAPTER
                )

                # 解析续写内容
                continue_result = self._parse_json_response(continue_response)
                if continue_result and continue_result.get("content"):
                    new_content = continue_result.get("content", "")
                    content = content + "\n\n" + new_content
                    actual_word_count = self._count_words(content)
                    logger.info(f"续写完成，新增 {self._count_words(new_content)} 字，当前总字数: {actual_word_count}")
                else:
                    # 如果解析失败，直接追加
                    content = content + "\n\n" + continue_response
                    actual_word_count = self._count_words(content)

            # 更新结果
            result["content"] = content
            result["word_count"] = actual_word_count
            result["continue_count"] = continue_count

            # 字数检查
            word_count_passed = actual_word_count >= min_word_count
            result["word_count_check"] = {
                "actual": actual_word_count,
                "target": word_count,
                "min_required": min_word_count,
                "passed": word_count_passed,
            }

            if not word_count_passed:
                logger.warning(f"经过 {continue_count} 次续写后字数仍不达标: 实际 {actual_word_count} < 最低要求 {min_word_count}")
                result["word_count_warning"] = f"字数不足 {min_word_count - actual_word_count} 字"
            elif continue_count > 0:
                logger.info(f"经过 {continue_count} 次续写后字数达标: {actual_word_count} 字")

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
                    "actual_word_count": actual_word_count,
                    "min_word_count": min_word_count,
                    "word_count_passed": word_count_passed,
                    "auto_write_mode": auto_write_mode,
                    "is_retry": is_retry,
                    "retry_count": retry_count,
                    "continue_count": continue_count,
                },
            )

        except Exception as e:
            logger.error(f"WriterAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_continue_prompt(
        self,
        existing_content: str,
        shortage: int,
        intents: List[str],
        character_moods: Dict[str, str],
        chapter_num: int,
        total_chapters: int,
    ) -> str:
        """构建续写提示"""
        return f"""请继续写作，补充约 {shortage} 字的内容。

【已有内容（最后 500 字）】
{existing_content[-500:]}

【长篇创作意识】
- 当前是第 {chapter_num} 章，全书共 {total_chapters} 章
- 请保持剧情可持续发展的节奏
- 不要急于推进到高潮或结局
- 续写内容要与上文自然衔接

【续写方向】
请选择以下方向之一进行续写：
1. 深化当前场景的细节描写
2. 增加角色之间的互动和对话
3. 添加环境氛围的渲染
4. 推进剧情的自然发展
5. 为后续情节埋下伏笔

输出 JSON 格式：
{{
    "content": "续写的内容",
    "word_count": 续写字数,
    "continue_direction": "选择的续写方向说明"
}}"""

    def _count_words(self, text: str) -> int:
        """
        统计字数（中文按字计，英文按词计）

        Args:
            text: 输入文本

        Returns:
            int: 字数
        """
        if not text:
            return 0

        try:
            from app.utils.text_utils import count_mixed_text
            return count_mixed_text(text)
        except ImportError:
            # 回退到简单统计
            import re
            # 中文字符
            chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
            # 英文单词
            english = len(re.findall(r'\b[a-zA-Z]+\b', text))
            return chinese + english

    def _build_user_message(
        self,
        intents: List[str],
        environment: str,
        character_moods: Dict[str, str],
        hooks: List[Dict[str, Any]],
        previous_style: str,
        word_count: int,
        min_word_count: int,
        discussion_summary: str = "",
        chapter_num: int = 1,
        total_chapters: int = 10,
        world_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建用户消息"""
        message_parts = []

        # 长篇创作意识（放在最前面）
        message_parts.append(f"""【长篇网文创作意识】
- 当前是第 {chapter_num} 章，全书计划共 {total_chapters} 章
- 这是长篇小说，不是短篇故事
- 剧情要可持续发展，不要让读者感觉开头就是高潮、马上要大结局
- 为后续剧情留有余地和伏笔空间
- 角色要有成长空间，不要一开始就无敌
- 世界观要有多层次，让读者感觉还有更深的内容待探索""")

        # 字数要求（放在最前面强调）
        message_parts.append(f"【字数要求（强制）】\n目标：约 {word_count} 字\n最低要求：{min_word_count} 字（必须达到）\n写作完成后请自行统计字数。")

        # 世界观设定（重要！所有写作都要符合世界观）
        if world_info:
            world_section = f"""【世界观设定】
名称：{world_info.get('name', '未知世界')}
类型：{world_info.get('world_type', '奇幻')}
基调：{world_info.get('tone', '正剧')}
背景：{world_info.get('background', world_info.get('description', ''))[:300]}"""
            rules = world_info.get('rules', {})
            if rules:
                if isinstance(rules, dict):
                    rules_text = '\n'.join([f'- {k}: {v}' for k, v in list(rules.items())[:5]])
                else:
                    rules_text = str(rules)[:200]
                world_section += f"\n\n【世界规则】\n{rules_text}"
            themes = world_info.get('themes', [])
            if themes:
                world_section += f"\n\n【核心主题】\n{', '.join(themes[:5])}"
            message_parts.append(world_section)

        # 团队讨论共识（如果有）
        if discussion_summary:
            message_parts.append(f"【团队讨论共识】\n{discussion_summary[:600]}\n请在写作中体现以上讨论达成的共识。")

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

        message_parts.append(
            "\n请将以上要素融合，生成一段有小说质感的连贯文本。"
            "注意：\n"
            "- 多用动作和神态描写，少用直接告知\n"
            "- 对话要符合角色性格\n"
            "- 伏笔要自然嵌入，不突兀\n"
            "- 必须达到最低字数要求\n"
            "- 保持长篇网文的节奏感，不要急于推进到高潮"
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
                messages=[HumanMessage(content=prompt)], temperature=0.3,
                category=UsageCategory.CHAPTER
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
{sensory_details if sensory_details else '自由发挥'}

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
                messages=[HumanMessage(content=prompt)], temperature=0.6,
                category=UsageCategory.CHAPTER
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
                messages=[HumanMessage(content=prompt)], temperature=0.5,
                category=UsageCategory.CHAPTER
            )
            result = self._parse_json_response(response_text)
            return AgentResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"角色声音重写失败：{e}")
            return AgentResponse(success=False, error=str(e))
