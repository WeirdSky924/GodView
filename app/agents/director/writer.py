"""
内容执行官 Agent - 将剧情意图润色成小说文本
支持自动字数检查和续写，以及分段生成策略
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import asyncio

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_output_contract import DEFAULT_AGENT_OUTPUT_CONTRACT_REGISTRY
from app.models.agent_output_schemas import (
    WriterChapterSchema,
    WriterCharacterVoiceRewriteSchema,
    WriterContinueSchema,
    WriterSceneDescriptionSchema,
    WriterSegmentPlanSchema,
    WriterSegmentSchema,
    WriterStyleConsistencySchema,
    WriterSupplementSchema,
)
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory
from app.services.structured_llm import StructuredOutputError
from app.services.writing_rule_rag import get_writing_rule_rag_service

logger = logging.getLogger(__name__)

# 分段生成的阈值配置
SEGMENT_THRESHOLD = 1500  # 超过此字数时采用分段生成
SEGMENT_SIZE = 800  # 每段目标字数
MAX_SEGMENTS = 5  # 最大分段数
WORDS_PER_RETRY = 250  # 每次续写预期增加的字数，用于计算最大续写次数


class WriterAgent(BaseAgent):
    """内容执行官 Agent"""

    AGENT_TYPE = AgentType.WRITER
    WRITER_OUTPUT_CONTRACT = DEFAULT_AGENT_OUTPUT_CONTRACT_REGISTRY.get("writer.workflow_output")

    def _as_list(self, value: Any) -> List[Any]:
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _as_dict(self, value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _as_text(self, value: Any, fallback: str = "") -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return fallback

    def _ensure_chapter_content(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """统一正文文本字段，兼容旧 content 与新 chapter_content。"""
        chapter_content = result.get("chapter_content") or result.get("content") or ""
        result["chapter_content"] = chapter_content
        result["content"] = chapter_content
        return result

    def _ensure_rewritten_text(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """统一改写文本字段，兼容旧 rewritten_text 与通用 text_output。"""
        rewritten_text = result.get("rewritten_text") or result.get("text_output") or result.get("content") or ""
        result["rewritten_text"] = rewritten_text
        if "text_output" not in result:
            result["text_output"] = rewritten_text
        return result

    def _normalize_workflow_output_fields(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """补齐 writer.workflow_output 契约要求的顶层字段。"""
        result = self._ensure_chapter_content(result)

        style_check = result.get("style_check")
        if hasattr(style_check, "model_dump"):
            style_check = style_check.model_dump()
        if not isinstance(style_check, dict):
            style_check = {}
        result["style_check"] = {
            "action_ratio": style_check.get("action_ratio", 0.0),
            "expression_ratio": style_check.get("expression_ratio", 0.0),
            "dialogue_ratio": style_check.get("dialogue_ratio", 0.0),
        }

        for field_name in ("hooks_embedded", "future_setup", "climax_points"):
            value = result.get(field_name)
            if isinstance(value, list):
                result[field_name] = value
            elif value in (None, ""):
                result[field_name] = []
            else:
                result[field_name] = [str(value)]

        return result

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
- 必须达到目标字数
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

    def _extract_discussion_summary(self, input_data: Dict[str, Any]) -> str:
        """提取讨论总结，优先读取统一后的 discussion 结构。"""
        discussion_summary = input_data.get("discussion_summary", "")
        if isinstance(discussion_summary, str) and discussion_summary.strip():
            return discussion_summary.strip()

        group_discussion = input_data.get("group_discussion") or {}
        if isinstance(group_discussion, dict):
            summary = group_discussion.get("summary", "")
            if isinstance(summary, str) and summary.strip():
                return summary.strip()

            full_content = group_discussion.get("full_content", "")
            if isinstance(full_content, str) and full_content.strip():
                return full_content.strip()

            messages = group_discussion.get("messages", [])
            if isinstance(messages, list):
                for message in reversed(messages):
                    if isinstance(message, dict):
                        content = message.get("content", "")
                        if isinstance(content, str) and content.strip():
                            return content.strip()

        legacy_summary = input_data.get("last_discussion_summary", "")
        if isinstance(legacy_summary, str):
            return legacy_summary.strip()
        return str(legacy_summary) if legacy_summary else ""

    def _extract_discussion_asset_context(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取已确认讨论资产，兼容直接字段与 group_discussion 嵌套字段。"""
        group_discussion = input_data.get("group_discussion") or {}
        if not isinstance(group_discussion, dict):
            group_discussion = {}

        assets = input_data.get("discussion_assets") or group_discussion.get("discussion_assets") or {}
        digest = input_data.get("discussion_asset_digest") or group_discussion.get("discussion_asset_digest") or {}
        persisted_refs = input_data.get("persisted_asset_refs") or {}
        committed = bool(input_data.get("discussion_assets_committed") or persisted_refs)

        return {
            "discussion_assets": assets if isinstance(assets, dict) else {},
            "discussion_asset_digest": digest if isinstance(digest, dict) else {},
            "persisted_asset_refs": persisted_refs if isinstance(persisted_refs, dict) else {},
            "discussion_assets_committed": committed,
        }

    def _format_discussion_asset_context(self, asset_context: Dict[str, Any]) -> str:
        """将讨论资产压缩为可放入 prompt 的摘要。"""
        assets = asset_context.get("discussion_assets") or {}
        digest = asset_context.get("discussion_asset_digest") or {}
        persisted_refs = asset_context.get("persisted_asset_refs") or {}
        if not assets and not digest and not persisted_refs:
            return ""

        def _labels(items: Any) -> List[str]:
            if not isinstance(items, list):
                return []
            labels: List[str] = []
            for item in items[:6]:
                if isinstance(item, dict):
                    label = item.get("title") or item.get("name") or item.get("id") or item.get("summary")
                    if label:
                        labels.append(str(label)[:80])
                elif item not in (None, ""):
                    labels.append(str(item)[:80])
            return labels

        lines = []
        topic = digest.get("topic") or assets.get("source_metadata", {}).get("topic")
        if topic:
            lines.append(f"讨论主题：{topic}")
        if asset_context.get("discussion_assets_committed"):
            lines.append("状态：已确认并提交，可作为本章写作事实使用")
        elif assets:
            lines.append("状态：讨论资产提案，请优先体现已确认上下文，避免擅自扩写为长期事实")

        sections = [
            ("剧情加码", _labels(assets.get("plot_updates"))),
            ("新增/待埋伏笔", _labels(assets.get("hooks"))),
            ("设定/世界观", _labels(assets.get("lore_candidates"))),
            ("地图/地点", _labels(assets.get("region_candidates"))),
            ("角色", _labels(assets.get("character_candidates"))),
        ]
        for title, labels in sections:
            if labels:
                lines.append(f"{title}：" + "；".join(labels))

        ref_lines = []
        for key, value in persisted_refs.items():
            if value:
                count = len(value) if isinstance(value, list) else 1
                ref_lines.append(f"{key}={count}")
        if ref_lines:
            lines.append("已持久化引用：" + "，".join(ref_lines))

        return "\n".join(lines)

    def _build_writing_rule_context(
        self,
        *,
        chapter_num: Optional[int] = None,
        total_chapters: Optional[int] = None,
        discussion_summary: Optional[str] = None,
        environment: Optional[str] = None,
        intents: Optional[List[str]] = None,
        hooks: Optional[List[Dict[str, Any]]] = None,
        character_moods: Optional[Dict[str, str]] = None,
        world_info: Optional[Dict[str, Any]] = None,
        scene: Optional[str] = None,
        segment_focus: Optional[str] = None,
        segment_elements: Optional[List[str]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "chapter_num": chapter_num,
            "total_chapters": total_chapters,
            "discussion_summary": discussion_summary,
            "environment": environment,
            "intents": intents,
            "hooks": hooks,
            "character_moods": character_moods,
            "world_info": world_info,
            "scene": scene,
            "segment_focus": segment_focus,
            "segment_elements": segment_elements,
        }
        if extra:
            context.update(extra)
        return {
            key: value
            for key, value in context.items()
            if value not in (None, "", [], {})
        }

    async def _retrieve_writing_rule_guidance(
        self,
        context: Optional[Dict[str, Any]] = None,
        limit: int = 6,
    ) -> str:
        if not self.project_id:
            return ""

        try:
            result = await get_writing_rule_rag_service().retrieve_for_project(
                project_id=self.project_id,
                context=context or {},
                limit=limit,
            )
            return (result.get("rendered_guidance") or "").strip()
        except Exception as e:
            logger.warning(f"写作规则检索失败: {e}")
            return ""

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行小说文本生成
        支持自动字数检查、续写和分段生成

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
        # 加载绑定的 Skills（包括字数统计工具）
        await self.load_skills()

        try:
            intents = self._as_list(input_data.get("intents", []))
            environment = self._as_text(input_data.get("environment", ""))
            character_moods = self._as_dict(input_data.get("character_moods", {}))
            hooks = self._as_list(input_data.get("hooks", []))
            previous_style = self._as_text(input_data.get("previous_style", ""))
            word_count = input_data.get("word_count", 500)
            auto_write_mode = bool(input_data.get("auto_write_mode", False))
            writing_prompt = self._as_text(input_data.get("writing_prompt", ""))
            discussion_summary = self._extract_discussion_summary(input_data)
            chapter_num = input_data.get("chapter_num", 1)
            total_chapters = input_data.get("total_chapters", 10)
            world_info = self._as_dict(input_data.get("world_info"))  # 世界观设定

            # 重试相关上下文
            is_retry = input_data.get("is_retry", False)
            retry_count = input_data.get("retry_count", 0)
            retry_message = input_data.get("retry_message", "")

            # 计算最低字数要求
            min_word_count = int(word_count)

            # ========== 决定生成策略 ==========
            use_segmented = word_count >= SEGMENT_THRESHOLD

            if use_segmented:
                logger.info(f"目标字数 {word_count} 超过阈值 {SEGMENT_THRESHOLD}，采用分段生成策略")
                result = await self._execute_segmented(
                    input_data=input_data,
                    word_count=word_count,
                    min_word_count=min_word_count,
                )
            else:
                # 普通生成流程
                result = await self._execute_single(
                    input_data=input_data,
                    word_count=word_count,
                    min_word_count=min_word_count,
                )

            # 如果是重试，添加重试标记
            if is_retry:
                result["is_retry"] = True
                result["retry_count"] = retry_count

            # 最终字数验证
            content = result.get("chapter_content") or result.get("content", "")
            actual_word_count = await self._count_words_async(content)

            # 字数检查
            word_count_passed = actual_word_count >= min_word_count
            result["word_count_check"] = {
                "actual": actual_word_count,
                "target": word_count,
                "min_required": min_word_count,
                "passed": word_count_passed,
            }

            if not word_count_passed:
                logger.warning(f"字数不达标: 实际 {actual_word_count} < 最低要求 {min_word_count}")
                result["word_count_warning"] = f"字数不足 {min_word_count - actual_word_count} 字"
            else:
                logger.info(f"字数达标: {actual_word_count} 字 (目标: {word_count})")

            # 验证风格一致性（如果有前文样本）
            if previous_style and self.config.get("style_check_enabled", True):
                style_check = await self._check_style_consistency(
                    generated_text=result.get("content", ""),
                    previous_style=previous_style,
                )
                result["style_check_result"] = style_check

            metadata = {
                "target_word_count": word_count,
                "actual_word_count": actual_word_count,
                "min_word_count": min_word_count,
                "word_count_passed": word_count_passed,
                "auto_write_mode": auto_write_mode,
                "is_retry": is_retry,
                "retry_count": retry_count,
                "use_segmented": use_segmented,
            }
            result["metadata"] = {**metadata, **result.get("metadata", {})}
            chapter_content = result.get("chapter_content") or result.get("content", "")

            return AgentResponse.hybrid(
                text_output=chapter_content,
                structured_data=result,
                contract_id=self.WRITER_OUTPUT_CONTRACT.contract_id if self.WRITER_OUTPUT_CONTRACT else None,
                schema_name=self.WRITER_OUTPUT_CONTRACT.schema_name if self.WRITER_OUTPUT_CONTRACT else None,
                schema_version=self.WRITER_OUTPUT_CONTRACT.schema_version if self.WRITER_OUTPUT_CONTRACT else None,
                metadata=metadata,
                data=result,
            )

        except Exception as e:
            logger.error(f"WriterAgent 执行失败：{e}", exc_info=True)
            return AgentResponse(success=False, error=str(e))

    async def _execute_single(
        self,
        input_data: Dict[str, Any],
        word_count: int,
        min_word_count: int,
    ) -> Dict[str, Any]:
        """
        单次生成流程（适用于较小字数需求）
        """
        intents = self._as_list(input_data.get("intents", []))
        environment = self._as_text(input_data.get("environment", ""))
        character_moods = self._as_dict(input_data.get("character_moods", {}))
        hooks = self._as_list(input_data.get("hooks", []))
        previous_style = self._as_text(input_data.get("previous_style", ""))
        auto_write_mode = bool(input_data.get("auto_write_mode", False))
        writing_prompt = self._as_text(input_data.get("writing_prompt", ""))
        discussion_summary = self._extract_discussion_summary(input_data)
        discussion_asset_context = self._extract_discussion_asset_context(input_data)
        discussion_asset_digest = self._format_discussion_asset_context(discussion_asset_context)
        chapter_num = input_data.get("chapter_num", 1)
        total_chapters = input_data.get("total_chapters", 10)
        world_info = self._as_dict(input_data.get("world_info"))

        rule_context = self._build_writing_rule_context(
            chapter_num=chapter_num,
            total_chapters=total_chapters,
            discussion_summary=discussion_summary,
            environment=environment,
            intents=intents,
            hooks=hooks,
            character_moods=character_moods,
            world_info=world_info,
            extra={"discussion_asset_digest": discussion_asset_context.get("discussion_asset_digest")},
        )
        writing_rules_guidance = await self._retrieve_writing_rule_guidance(
            context=rule_context,
            limit=6,
        )

        # 构建用户消息
        if auto_write_mode and writing_prompt:
            user_message = writing_prompt
            if writing_rules_guidance:
                user_message = f"{writing_prompt}\n\n{writing_rules_guidance}"
        else:
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
                writing_rules_guidance=writing_rules_guidance,
                discussion_asset_digest=discussion_asset_digest,
            )

        # 调用 LLM (structured)
        temperature = 0.8 if auto_write_mode else 0.7
        try:
            parsed = await self._call_structured(
                WriterChapterSchema,
                messages=[HumanMessage(content=user_message)],
                temperature=temperature,
                category=UsageCategory.CHAPTER,
            )
            result = parsed.model_dump()
        except StructuredOutputError as e:
            logger.warning(f"Writer structured 失败，降级为纯文本: {e}")
            # hybrid 场景：即使结构化失败也尝试 fallback 纯文本
            response_text = await self._call_llm(
                messages=[HumanMessage(content=user_message)], temperature=temperature,
                category=UsageCategory.CHAPTER
            )
            result = {
                "content": response_text,
                "word_count": len(response_text),
            }

        # 进行字数统计验证
        content = result.get("chapter_content") or result.get("content", "")
        actual_word_count = await self._count_words_async(content)

        # 如果LLM报告的字数与实际统计差距较大，使用实际统计
        if abs(result.get("word_count", 0) - actual_word_count) > 100:
            logger.warning(f"字数统计差异: LLM报告 {result.get('word_count')} vs 实际 {actual_word_count}")
            result["word_count"] = actual_word_count

        # ========== 自动续写逻辑（必须达到字数要求）==========
        # 计算最大续写次数：需求字数 / 250，至少 3 次
        max_retry_count = max(3, word_count // WORDS_PER_RETRY)
        logger.info(f"最大续写次数: {max_retry_count} (目标字数: {word_count})")

        continue_count = 0
        while actual_word_count < min_word_count and continue_count < max_retry_count:
            continue_count += 1
            shortage = min_word_count - actual_word_count

            logger.info(f"字数不足 ({actual_word_count}/{min_word_count})，开始第 {continue_count}/{max_retry_count} 次续写...")

            # 构建续写提示
            continue_prompt = self._build_continue_prompt(
                existing_content=content,
                shortage=shortage,
                intents=intents,
                character_moods=character_moods,
                chapter_num=chapter_num,
                total_chapters=total_chapters,
                writing_rules_guidance=writing_rules_guidance,
            )

            # 调用 LLM 续写 (structured)
            try:
                continue_parsed = await self._call_structured(
                    WriterContinueSchema,
                    messages=[HumanMessage(content=continue_prompt)],
                    temperature=0.75,
                    category=UsageCategory.CHAPTER,
                )
                continue_result = continue_parsed.model_dump()
            except StructuredOutputError as e:
                logger.warning(f"续写 structured 失败，降级纯文本: {e}")
                continue_response = await self._call_llm(
                    messages=[HumanMessage(content=continue_prompt)], temperature=0.75,
                    category=UsageCategory.CHAPTER
                )
                continue_result = {"content": continue_response}

            if continue_result and continue_result.get("content"):
                new_content = continue_result.get("content", "")
                content = content + "\n\n" + new_content
                actual_word_count = await self._count_words_async(content)
                logger.info(f"续写完成，新增 {await self._count_words_async(new_content)} 字，当前总字数: {actual_word_count}")
            else:
                actual_word_count = await self._count_words_async(content)

        # 更新结果
        result["content"] = content
        result["chapter_content"] = content
        result["word_count"] = actual_word_count
        result["continue_count"] = continue_count
        result["max_retry_count"] = max_retry_count
        result["generation_strategy"] = "single"

        return self._normalize_workflow_output_fields(result)

    async def _execute_segmented(
        self,
        input_data: Dict[str, Any],
        word_count: int,
        min_word_count: int,
    ) -> Dict[str, Any]:
        """
        分段生成流程（适用于大字数需求）

        策略：
        1. 先规划分段结构
        2. 每段独立生成
        3. 汇总并检查字数
        4. 必要时补充内容
        """
        intents = self._as_list(input_data.get("intents", []))
        environment = self._as_text(input_data.get("environment", ""))
        character_moods = self._as_dict(input_data.get("character_moods", {}))
        hooks = self._as_list(input_data.get("hooks", []))
        previous_style = self._as_text(input_data.get("previous_style", ""))
        discussion_summary = self._extract_discussion_summary(input_data)
        discussion_asset_context = self._extract_discussion_asset_context(input_data)
        discussion_asset_digest = self._format_discussion_asset_context(discussion_asset_context)
        chapter_num = input_data.get("chapter_num", 1)
        total_chapters = input_data.get("total_chapters", 10)
        world_info = self._as_dict(input_data.get("world_info"))

        chapter_rule_context = self._build_writing_rule_context(
            chapter_num=chapter_num,
            total_chapters=total_chapters,
            discussion_summary=discussion_summary,
            environment=environment,
            intents=intents,
            hooks=hooks,
            character_moods=character_moods,
            world_info=world_info,
            extra={"discussion_asset_digest": discussion_asset_context.get("discussion_asset_digest")},
        )
        chapter_writing_rules_guidance = await self._retrieve_writing_rule_guidance(
            context=chapter_rule_context,
            limit=6,
        )

        # 计算分段数
        segment_count = min(MAX_SEGMENTS, (word_count + SEGMENT_SIZE - 1) // SEGMENT_SIZE)
        segment_target = word_count // segment_count

        logger.info(f"分段生成: {segment_count} 段，每段目标 {segment_target} 字")

        # ========== 第一阶段：规划分段结构 ==========
        segment_plan = await self._plan_segments(
            intents=intents,
            environment=environment,
            character_moods=character_moods,
            word_count=word_count,
            segment_count=segment_count,
            chapter_num=chapter_num,
            total_chapters=total_chapters,
            world_info=world_info,
            discussion_asset_digest=discussion_asset_digest,
        )

        # ========== 第二阶段：逐段生成 ==========
        all_content = []
        total_words = 0
        segment_results = []

        for i, raw_segment_info in enumerate(segment_plan.get("segments", [])):
            segment_info = raw_segment_info if isinstance(raw_segment_info, dict) else {"focus": str(raw_segment_info)}
            segment_num = i + 1
            logger.info(f"生成第 {segment_num}/{segment_count} 段...")

            segment_rule_context = self._build_writing_rule_context(
                chapter_num=chapter_num,
                total_chapters=total_chapters,
                discussion_summary=discussion_summary,
                environment=environment,
                intents=intents,
                hooks=hooks,
                character_moods=character_moods,
                world_info=world_info,
                segment_focus=segment_info.get("focus"),
                segment_elements=segment_info.get("key_elements"),
                extra={"discussion_asset_digest": discussion_asset_context.get("discussion_asset_digest")},
            )
            segment_writing_rules_guidance = await self._retrieve_writing_rule_guidance(
                context=segment_rule_context,
                limit=4,
            )
            if not segment_writing_rules_guidance:
                segment_writing_rules_guidance = chapter_writing_rules_guidance

            # 构建分段提示
            segment_prompt = self._build_segment_prompt(
                segment_info=segment_info,
                previous_content=all_content[-1] if all_content else None,
                segment_num=segment_num,
                total_segments=segment_count,
                target_words=segment_target,
                world_info=world_info,
                previous_style=previous_style if i == 0 else None,
                writing_rules_guidance=segment_writing_rules_guidance,
                discussion_asset_digest=discussion_asset_digest,
            )

            # 生成该段 (structured)
            try:
                segment_parsed = await self._call_structured(
                    WriterSegmentSchema,
                    messages=[HumanMessage(content=segment_prompt)],
                    temperature=0.75,
                    category=UsageCategory.CHAPTER,
                )
                segment_result = segment_parsed.model_dump()
                segment_content = segment_result.get("content", "")
            except StructuredOutputError as e:
                logger.warning(f"分段 structured 失败，降级纯文本: {e}")
                segment_response = await self._call_llm(
                    messages=[HumanMessage(content=segment_prompt)], temperature=0.75,
                    category=UsageCategory.CHAPTER
                )
                segment_content = segment_response

            segment_words = await self._count_words_async(segment_content)
            all_content.append(segment_content)
            total_words += segment_words

            segment_results.append({
                "segment_num": segment_num,
                "focus": segment_info.get("focus", ""),
                "word_count": segment_words,
                "target": segment_target,
            })

            logger.info(f"第 {segment_num} 段完成: {segment_words} 字")

        # ========== 第三阶段：合并内容 ==========
        full_content = "\n\n".join(all_content)
        actual_word_count = await self._count_words_async(full_content)

        logger.info(f"分段生成完成: 总计 {actual_word_count} 字")

        # ========== 第四阶段：补充内容（必须达到字数要求）==========
        # 计算最大续写次数：需求字数 / 250，至少 3 次
        max_retry_count = max(3, word_count // WORDS_PER_RETRY)
        logger.info(f"最大补充次数: {max_retry_count} (目标字数: {word_count})")

        continue_count = 0
        while actual_word_count < min_word_count and continue_count < max_retry_count:
            continue_count += 1
            shortage = min_word_count - actual_word_count

            logger.info(f"分段生成后字数不足 ({actual_word_count}/{min_word_count})，开始第 {continue_count}/{max_retry_count} 次补充...")

            # 构建补充提示
            supplement_prompt = self._build_supplement_prompt(
                existing_content=full_content,
                shortage=shortage,
                chapter_num=chapter_num,
                total_chapters=total_chapters,
                writing_rules_guidance=chapter_writing_rules_guidance,
            )

            try:
                supplement_parsed = await self._call_structured(
                    WriterSupplementSchema,
                    messages=[HumanMessage(content=supplement_prompt)],
                    temperature=0.7,
                    category=UsageCategory.CHAPTER,
                )
                supplement_result = supplement_parsed.model_dump()
            except StructuredOutputError as e:
                logger.warning(f"补充 structured 失败，降级纯文本: {e}")
                supplement_response = await self._call_llm(
                    messages=[HumanMessage(content=supplement_prompt)], temperature=0.7,
                    category=UsageCategory.CHAPTER
                )
                supplement_result = {"content": supplement_response}

            if supplement_result and supplement_result.get("content"):
                new_content = supplement_result.get("content", "")
                full_content = full_content + "\n\n" + new_content
                actual_word_count = await self._count_words_async(full_content)
                logger.info(f"补充完成，新增 {await self._count_words_async(new_content)} 字，当前总字数: {actual_word_count}")
            else:
                actual_word_count = await self._count_words_async(full_content)

        return self._normalize_workflow_output_fields({
            "content": full_content,
            "chapter_content": full_content,
            "word_count": actual_word_count,
            "continue_count": continue_count,
            "max_retry_count": max_retry_count,
            "generation_strategy": "segmented",
            "segment_count": segment_count,
            "segment_results": segment_results,
            "segment_plan": segment_plan,
        })

    async def _plan_segments(
        self,
        intents: List[str],
        environment: str,
        character_moods: Dict[str, str],
        word_count: int,
        segment_count: int,
        chapter_num: int,
        total_chapters: int,
        world_info: Optional[Dict[str, Any]] = None,
        discussion_asset_digest: str = "",
    ) -> Dict[str, Any]:
        """
        规划分段结构

        Returns:
            Dict: 包含 segments 列表，每段有 focus 和 key_elements
        """
        prompt = f"""你是小说结构规划师，请为以下章节内容规划分段结构。

【章节信息】
- 第 {chapter_num} 章，全书共 {total_chapters} 章
- 目标字数: {word_count} 字
- 分段数: {segment_count} 段

【环境设定】
{environment if environment else "无特定环境"}

【需要表达的意图】
{chr(10).join(intents) if intents else "自由发挥"}

【角色状态】
{chr(10).join([f"- {k}: {v}" for k, v in character_moods.items()]) if character_moods else "无特定状态"}
"""
        if discussion_asset_digest:
            prompt += f"""

【已确认讨论资产】
{discussion_asset_digest}
请在分段结构中显式承接这些已确认的剧情、伏笔、地点、设定或角色信息，不要与其冲突。
"""
        prompt += f"""

【规划要求】
1. 每段应该有明确的叙事焦点
2. 段落之间要自然过渡
3. 保持剧情连贯性
4. 合理分配信息密度

请输出 JSON 格式：
{{
    "segments": [
        {{
            "focus": "该段的叙事焦点（如：开篇铺垫、冲突展开、对话互动、情节推进、高潮渲染、结尾收束等）",
            "key_elements": ["该段需要包含的关键元素"],
            "tone": "该段的情感基调",
            "suggested_word_count": 建议字数
        }}
    ],
    "overall_structure": "整体结构说明",
    "pacing_note": "节奏把控建议"
}}"""

        try:
            parsed = await self._call_structured(
                WriterSegmentPlanSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.5,
                category=UsageCategory.PLANNING,
            )
            result = parsed.model_dump()
            return result if result.get("segments") else {"segments": self._get_default_segments(segment_count)}
        except StructuredOutputError as e:
            logger.warning(f"分段规划 structured 失败，使用默认结构: {e}")
            return {"segments": self._get_default_segments(segment_count)}
        except Exception as e:
            logger.warning(f"分段规划失败，使用默认结构: {e}")
            return {"segments": self._get_default_segments(segment_count)}

    def _get_default_segments(self, segment_count: int) -> List[Dict[str, Any]]:
        """获取默认分段结构"""
        default_focuses = [
            {"focus": "开篇铺垫", "key_elements": ["场景描写", "氛围渲染"], "tone": "平稳"},
            {"focus": "情节展开", "key_elements": ["角色互动", "对话推进"], "tone": "渐强"},
            {"focus": "冲突深化", "key_elements": ["矛盾激化", "悬念设置"], "tone": "紧张"},
            {"focus": "高潮渲染", "key_elements": ["情感爆发", "关键转折"], "tone": "激烈"},
            {"focus": "结尾收束", "key_elements": ["悬念钩子", "情感余韵"], "tone": "回味"},
        ]
        return default_focuses[:segment_count]

    def _build_segment_prompt(
        self,
        segment_info: Dict[str, Any],
        previous_content: Optional[str],
        segment_num: int,
        total_segments: int,
        target_words: int,
        world_info: Optional[Dict[str, Any]] = None,
        previous_style: Optional[str] = None,
        writing_rules_guidance: str = "",
        discussion_asset_digest: str = "",
    ) -> str:
        """构建分段生成提示"""
        parts = []

        parts.append(f"""【分段写作任务】
- 当前是第 {segment_num}/{total_segments} 段
- 本段焦点: {segment_info.get('focus', '自由发挥')}
- 目标字数: 约 {target_words} 字（最低 {target_words} 字）
- 情感基调: {segment_info.get('tone', '平稳')}""")

        key_elements = self._as_list(segment_info.get('key_elements', []))
        if key_elements:
            parts.append(f"\n【本段关键元素】\n{chr(10).join(['- ' + str(e) for e in key_elements])}")

        if writing_rules_guidance:
            parts.append(f"\n{writing_rules_guidance}")

        if world_info:
            parts.append(f"\n【世界观参考】\n名称：{world_info.get('name', '未知')}\n类型：{world_info.get('world_type', '奇幻')}")

        if discussion_asset_digest:
            parts.append(
                f"\n【已确认讨论资产】\n{discussion_asset_digest}\n"
                "本段需要承接这些已确认的剧情资产；如涉及新增角色、地点、设定或伏笔，按已确认信息写作，不要随意改名或改设定。"
            )

        if previous_content:
            parts.append(f"\n【前一段落结尾】\n{previous_content}")

        if previous_style and segment_num == 1:
            parts.append(f"\n【前文风格样本】\n{previous_style}\n请保持与上述风格一致。")

        parts.append(f"""
【写作要求】
1. 必须达到最低字数要求
2. 与前文自然衔接
3. 突出本段的叙事焦点
4. 保持网文的节奏感和可读性

输出 JSON 格式：
{{
    "content": "本段正文内容",
    "word_count": 字数,
    "key_points_covered": ["已覆盖的关键元素"],
    "transition_to_next": "与下一段的衔接思路"
}}""")

        return "\n".join(parts)

    def _build_supplement_prompt(
        self,
        existing_content: str,
        shortage: int,
        chapter_num: int,
        total_chapters: int,
        writing_rules_guidance: str = "",
    ) -> str:
        """构建补充内容提示"""
        guidance_block = f"\n【当前相关写作规则】\n{writing_rules_guidance}\n" if writing_rules_guidance else ""
        return f"""请为以下章节内容进行补充，增加约 {shortage} 字。

【已有内容】
{existing_content}{guidance_block}
【长篇创作意识】
- 当前是第 {chapter_num} 章，全书共 {total_chapters} 章
- 保持剧情可持续发展，不要急于推进到高潮

【补充方向】
请选择以下方向之一进行补充：
1. 深化场景细节描写
2. 增加角色内心活动
3. 丰富对话和互动
4. 添加环境氛围渲染
5. 埋下伏笔或悬念

输出 JSON 格式：
{{
    "content": "补充的内容",
    "word_count": 字数,
    "supplement_direction": "选择的补充方向"
}}"""

    def _build_continue_prompt(
        self,
        existing_content: str,
        shortage: int,
        intents: List[str],
        character_moods: Dict[str, str],
        chapter_num: int,
        total_chapters: int,
        writing_rules_guidance: str = "",
    ) -> str:
        """构建续写提示"""
        guidance_block = f"\n【当前相关写作规则】\n{writing_rules_guidance}\n" if writing_rules_guidance else ""
        return f"""请继续写作，补充约 {shortage} 字的内容。

【已有内容】
{existing_content}{guidance_block}
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
        同步字数统计方法（向后兼容）

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
            import re
            chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
            english = len(re.findall(r'\b[a-zA-Z]+\b', text))
            return chinese + english

    async def _count_words_async(self, text: str) -> int:
        """
        异步字数统计（优先使用 Skill）

        Args:
            text: 输入文本

        Returns:
            int: 字数
        """
        if not text:
            return 0

        # 尝试使用 Skill 进行精确统计
        try:
            result = await self.execute_skill("skill_word_count", {"text": text})
            if result.get("success") and result.get("output"):
                import json
                data = result["output"] if isinstance(result["output"], dict) else json.loads(result["output"])
                total = data.get("total_count", 0)
                if total > 0:
                    logger.debug(f"Skill 字数统计: {total} 字")
                    return total
        except Exception as e:
            logger.debug(f"Skill 字数统计失败，使用内置方法: {e}")

        # 回退到内置统计
        return self._count_words(text)

    async def count_words_with_skill(self, text: str) -> Dict[str, int]:
        """
        使用 Skill 统计字数（异步版本，返回详细统计）

        Args:
            text: 输入文本

        Returns:
            Dict: 包含 chinese_count, english_count, total_count 等字段
        """
        if not text:
            return {"chinese_count": 0, "english_count": 0, "total_count": 0}

        # 尝试使用 Skill
        result = await self.execute_skill("skill_word_count", {"text": text})
        if result.get("success") and result.get("output"):
            # 解析 Skill 返回的 JSON
            try:
                import json
                data = json.loads(result["output"]) if isinstance(result["output"], str) else result["output"]
                return data
            except:
                pass

        # 回退到内置方法
        count = self._count_words(text)
        return {"total_count": count, "chinese_count": count, "english_count": 0}

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
        writing_rules_guidance: str = "",
        discussion_asset_digest: str = "",
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

        if writing_rules_guidance:
            message_parts.append(writing_rules_guidance)

        # 世界观设定（重要！所有写作都要符合世界观）
        if world_info:
            world_section = f"""【世界观设定】
名称：{world_info.get('name', '未知世界')}
类型：{world_info.get('world_type', '奇幻')}
基调：{world_info.get('tone', '正剧')}
背景：{world_info.get('background', world_info.get('description', ''))}"""
            rules = world_info.get('rules', {})
            if rules:
                if isinstance(rules, dict):
                    rules_text = '\n'.join([f'- {k}: {v}' for k, v in rules.items()])
                else:
                    rules_text = str(rules)
                world_section += f"\n\n【世界规则】\n{rules_text}"
            themes = world_info.get('themes', [])
            if themes:
                world_section += f"\n\n【核心主题】\n{', '.join(str(theme) for theme in themes)}"
            message_parts.append(world_section)

        # 团队讨论共识（如果有）
        if discussion_summary:
            message_parts.append(f"【团队讨论共识】\n{discussion_summary}\n请在写作中体现以上讨论达成的共识。")

        if discussion_asset_digest:
            message_parts.append(
                f"【已确认讨论资产】\n{discussion_asset_digest}\n"
                "这些资产来自已确认的集体讨论，可作为本章写作事实使用；请承接其中的剧情加码、伏笔、设定、地点和角色信息，不要与其冲突。"
            )

        # 环境描写
        if environment:
            message_parts.append(f"【环境】\n{environment}")

        # 需要表达的意图
        if intents:
            message_parts.append(f"【需要表达的意图】\n{chr(10).join(str(intent) for intent in intents)}")

        # 角色情绪
        if character_moods:
            moods_text = "\n".join(
                [f"- {name}: {mood}" for name, mood in character_moods.items()]
            )
            message_parts.append(f"【角色情绪】\n{moods_text}")

        # 伏笔处理
        if hooks:
            hooks_text = "\n".join(
                [
                    f"- {h.get('id')}: {h.get('type', 'plant')} - {h.get('description', '')}"
                    if isinstance(h, dict)
                    else f"- {h}"
                    for h in hooks
                ]
            )
            message_parts.append(f"【伏笔处理】\n{hooks_text}")

        # 前文风格样本
        if previous_style:
            message_parts.append(f"【前文风格样本】\n{previous_style}")
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
{previous_style}

【新生成文本】
{generated_text}

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
            parsed = await self._call_structured(
                WriterStyleConsistencySchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.3,
                category=UsageCategory.CHAPTER,
            )
            return parsed.model_dump()
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
            parsed = await self._call_structured(
                WriterSceneDescriptionSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.6,
                category=UsageCategory.CHAPTER,
            )
            result = parsed.model_dump()

            description = result.get("description") or ""
            result["description"] = description
            result["word_count"] = result.get("word_count") or await self._count_words_async(description)

            return AgentResponse.hybrid(
                text_output=description,
                structured_data=result,
                metadata={"surface": "scene_description"},
                data=result,
            )
        except StructuredOutputError as e:
            logger.error(f"场景描写 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
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
            parsed = await self._call_structured(
                WriterCharacterVoiceRewriteSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.5,
                category=UsageCategory.CHAPTER,
            )
            result = parsed.model_dump()

            result = self._ensure_rewritten_text(result)
            rewritten_text = result.get("rewritten_text", "")

            return AgentResponse.hybrid(
                text_output=rewritten_text,
                structured_data=result,
                metadata={"surface": "character_voice_rewrite"},
                data=result,
            )
        except StructuredOutputError as e:
            logger.error(f"角色声音改写 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"角色声音重写失败：{e}")
            return AgentResponse(success=False, error=str(e))
