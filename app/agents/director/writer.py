"""
内容执行官 Agent - 将剧情意图润色成小说文本
支持自动字数检查和续写，以及分段生成策略
"""

import logging
import json
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


class PromptGovernanceError(RuntimeError):
    """Raised when a production Writer task cannot resolve a governed prompt."""

    def __init__(self, message: str, trace: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.trace = trace or {}


# 分段生成的阈值配置
SEGMENT_THRESHOLD = 1500  # 超过此字数时采用分段生成
SEGMENT_SIZE = 800  # 每段目标字数
MAX_SEGMENTS = 5  # 最大分段数
WORDS_PER_RETRY = 250  # 每次续写预期增加的字数，用于计算最大续写次数


class WriterAgent(BaseAgent):
    """内容执行官 Agent"""

    AGENT_TYPE = AgentType.WRITER
    DEFAULT_SCENARIO = "workflow_chapter_generation"
    TASK_SCENARIOS = {
        "chapter_generation": "workflow_chapter_generation",
        "segment_plan": "workflow_chapter_generation",
        "segment_generation": "workflow_chapter_generation",
        "supplement": "workflow_chapter_generation",
        "continue": "workflow_chapter_generation",
        "rewrite_by_review": "rewrite_by_review",
        "style_check": "style_consistency_check",
        "scene_description": "scene_description",
        "character_voice_rewrite": "character_voice_rewrite",
    }
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
        # 如果没有提供 system_prompt 且没有 project_id，使用 md prompt 资产作为 legacy 备用 prompt
        if not system_prompt and not project_id:
            system_prompt = self._build_default_system_prompt()
            self._legacy_fallback_trace = {
                "agent_type": AgentType.WRITER.value,
                "scenario": self.DEFAULT_SCENARIO,
                "project_id": None,
                "template_id": None,
                "template_scenario": None,
                "config_id": None,
                "prompt_ids": [],
                "skill_ids": [],
                "writing_rule_ids": [],
                "context_blocks": [],
                "fallbacks_used": ["writer_legacy_md_prompt_fallback"],
                "deprecated_sources_used": [],
            }
            if "deprecated 最小 fallback" in system_prompt:
                self._legacy_fallback_trace["fallbacks_used"] = ["writer_deprecated_minimal_system_prompt"]
                self._legacy_fallback_trace["deprecated_sources_used"] = ["WriterAgent._build_default_system_prompt"]

        super().__init__(
            name="WriterAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )
        legacy_trace = getattr(self, "_legacy_fallback_trace", None)
        if legacy_trace and not self.get_system_prompt_render_trace():
            self._system_prompt_render_trace = legacy_trace

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（Writer 特定）"""
        return {
            "agent_role": "内容执行官",
            "task_description": "将剧情意图润色成长篇网文文本",
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
            logger.warning(f"加载 {prompt_id} prompt 失败: {e}")

        return ""

    def _build_md_writer_fallback_prompt(self) -> str:
        """从 md prompt 资产构建 Writer 备用 prompt。"""
        prompt_ids = [
            "role_writer",
            "function_writing",
            "function_writer_workflow_context_binding",
            "function_writer_segment_generation",
            "function_writer_style_consistency",
            "function_writer_scene_description",
            "function_writer_character_voice_rewrite",
        ]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        return "\n\n".join(parts).strip()

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示（优先使用 prompts/**/*.md 资产）。"""
        md_prompt = self._build_md_writer_fallback_prompt()
        if md_prompt:
            return md_prompt

        logger.warning("writer md prompt 资产不可用，使用 deprecated 最小硬编码默认系统提示")
        return (
            "你是 Writer Agent。优先使用 Agent Template 绑定的 md prompt、skills 和 writing-rules；"
            "当前仅因配置资产不可用而启用 deprecated 最小 fallback。"
        )

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
            word_count = (
                input_data.get("target_word_count")
                or input_data.get("chapter_target_word_count")
                or input_data.get("word_count")
                or 500
            )
            try:
                word_count = int(word_count)
            except (TypeError, ValueError):
                word_count = 500
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

            # 计算字数要求：Writer 要写到章节目标附近，允许适度展开但不能失控超写。
            min_word_count = max(1, int(word_count * 0.9))
            max_word_count = max(word_count, int(word_count * 1.25))

            # ========== 决定生成策略 ==========
            use_segmented = word_count >= SEGMENT_THRESHOLD

            if use_segmented:
                logger.info(f"目标字数 {word_count} 超过阈值 {SEGMENT_THRESHOLD}，采用分段生成策略")
                result = await self._execute_segmented(
                    input_data=input_data,
                    word_count=word_count,
                    min_word_count=min_word_count,
                    max_word_count=max_word_count,
                )
            else:
                # 普通生成流程
                result = await self._execute_single(
                    input_data=input_data,
                    word_count=word_count,
                    min_word_count=min_word_count,
                    max_word_count=max_word_count,
                )

            # 如果是重试，添加重试标记
            if is_retry:
                result["is_retry"] = True
                result["retry_count"] = retry_count

            # 最终字数验证
            content = result.get("chapter_content") or result.get("content", "")
            actual_word_count = await self._count_words_async(content)

            # 字数检查
            word_count_passed = min_word_count <= actual_word_count <= max_word_count
            result["word_count_check"] = {
                "actual": actual_word_count,
                "target": word_count,
                "min_required": min_word_count,
                "max_allowed": max_word_count,
                "passed": word_count_passed,
            }

            if actual_word_count < min_word_count:
                logger.warning(f"字数不达标: 实际 {actual_word_count} < 最低要求 {min_word_count}")
                result["word_count_warning"] = f"字数不足 {min_word_count - actual_word_count} 字"
            elif actual_word_count > max_word_count:
                logger.warning(f"字数超标: 实际 {actual_word_count} > 允许上限 {max_word_count}")
                result["word_count_warning"] = f"字数超标 {actual_word_count - max_word_count} 字"
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
                "max_word_count": max_word_count,
                "word_count_passed": word_count_passed,
                "auto_write_mode": auto_write_mode,
                "is_retry": is_retry,
                "retry_count": retry_count,
                "use_segmented": use_segmented,
                "config_prompt_source": getattr(self, "_writer_config_prompt_source", None),
                "config_prompt_length": len(getattr(self, "_writer_config_prompt", "") or ""),
                **self._get_runtime_trace_metadata(),
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

        except PromptGovernanceError as e:
            logger.error("WriterAgent prompt governance failed: %s", e)
            return AgentResponse(
                success=False,
                error=str(e),
                metadata={
                    "prompt_governance_error": True,
                    "prompt_render_trace": e.trace,
                },
            )
        except Exception as e:
            logger.error(f"WriterAgent 执行失败：{e}", exc_info=True)
            return AgentResponse(success=False, error=str(e))

    def _scenario_for_task(self, task_type: str) -> str:
        return self.TASK_SCENARIOS.get(task_type, self.DEFAULT_SCENARIO)

    async def _get_writer_config_prompt(self, variables: Optional[Dict[str, Any]] = None) -> str:
        """获取 Writer 指定任务场景的配置 prompt。"""
        variables = variables or {}
        task_type = str(variables.get("task_type") or "chapter_generation")
        scenario = self._scenario_for_task(task_type)
        cache_key = f"_writer_config_prompt__{scenario}"
        source_key = f"_writer_config_prompt_source__{scenario}"
        trace_key = f"_writer_config_prompt_trace__{scenario}"

        if hasattr(self, cache_key):
            self._writer_config_prompt = getattr(self, cache_key)
            self._writer_config_prompt_source = getattr(self, source_key, None)
            self._system_prompt_render_trace = getattr(self, trace_key, self._system_prompt_render_trace)
            self.scenario = scenario
            return self._writer_config_prompt

        runtime_variables = {
            **self._get_default_variables(),
            **variables,
            "task_type": task_type,
            "scenario": scenario,
        }

        if self.project_id:
            try:
                from app.services.agent_prompt_service import get_agent_prompt_service

                prompt_data = await get_agent_prompt_service().build_agent_prompt_with_trace(
                    agent_type=self.AGENT_TYPE.value if hasattr(self.AGENT_TYPE, "value") else str(self.AGENT_TYPE),
                    project_id=self.project_id,
                    variables=runtime_variables,
                    scenario=scenario,
                )
                prompt = (prompt_data.get("content") or "").strip()
                trace = prompt_data.get("trace", {}) or {}
                if prompt:
                    setattr(self, cache_key, prompt)
                    setattr(self, source_key, "agent_template_runtime")
                    setattr(self, trace_key, trace)
                    self._writer_config_prompt = prompt
                    self._writer_config_prompt_source = "agent_template_runtime"
                    self._system_prompt_render_trace = trace
                    self.scenario = scenario
                    return prompt
            except Exception as e:
                logger.warning(
                    "Writer 加载场景配置 prompt 失败: project=%s, scenario=%s, error=%s",
                    self.project_id,
                    scenario,
                    e,
                )
                self._system_prompt_render_trace = {
                    "agent_type": self.AGENT_TYPE.value if hasattr(self.AGENT_TYPE, "value") else str(self.AGENT_TYPE),
                    "scenario": scenario,
                    "project_id": self.project_id,
                    "template_id": None,
                    "template_scenario": None,
                    "config_id": None,
                    "prompt_ids": [],
                    "skill_ids": [],
                    "writing_rule_ids": [],
                    "context_blocks": [],
                    "fallbacks_used": ["writer_runtime_prompt_error"],
                    "deprecated_sources_used": [],
                    "missing_prompt_ids": [],
                }

        fallback = self._build_md_writer_fallback_prompt()
        if fallback:
            trace = {
                "agent_type": self.AGENT_TYPE.value if hasattr(self.AGENT_TYPE, "value") else str(self.AGENT_TYPE),
                "scenario": scenario,
                "project_id": self.project_id,
                "template_id": None,
                "template_scenario": None,
                "config_id": None,
                "prompt_ids": [
                    "role_writer",
                    "function_writing",
                    "function_writer_workflow_context_binding",
                    "function_writer_segment_generation",
                    "function_writer_style_consistency",
                    "function_writer_scene_description",
                    "function_writer_character_voice_rewrite",
                ],
                "skill_ids": [],
                "writing_rule_ids": [],
                "context_blocks": [],
                "fallbacks_used": ["writer_md_prompt_fallback"],
                "deprecated_sources_used": [],
                "missing_prompt_ids": [],
            }
            setattr(self, cache_key, fallback)
            setattr(self, source_key, "md_prompt_fallback")
            setattr(self, trace_key, trace)
            self._writer_config_prompt = fallback
            self._writer_config_prompt_source = "md_prompt_fallback"
            self._system_prompt_render_trace = trace
            self.scenario = scenario
            return fallback

        trace = {
            "agent_type": self.AGENT_TYPE.value if hasattr(self.AGENT_TYPE, "value") else str(self.AGENT_TYPE),
            "scenario": scenario,
            "project_id": self.project_id,
            "template_id": None,
            "template_scenario": None,
            "config_id": None,
            "prompt_ids": [],
            "skill_ids": [],
            "writing_rule_ids": [],
            "context_blocks": [],
            "fallbacks_used": ["writer_missing_config_prompt"],
            "deprecated_sources_used": ["WriterAgent._build_md_writer_fallback_prompt"],
            "missing_prompt_ids": [
                "role_writer",
                "function_writing",
                "function_writer_workflow_context_binding",
                "function_writer_segment_generation",
                "function_writer_style_consistency",
                "function_writer_scene_description",
                "function_writer_character_voice_rewrite",
            ],
        }
        setattr(self, cache_key, "")
        setattr(self, source_key, "missing")
        setattr(self, trace_key, trace)
        self._writer_config_prompt = ""
        self._writer_config_prompt_source = "missing"
        self._system_prompt_render_trace = trace
        self.scenario = scenario
        if self.project_id:
            raise PromptGovernanceError(
                f"Writer prompt configuration is missing for production scenario: {scenario}",
                trace,
            )
        return ""

    def _format_task_context_block(self, title: str, value: Any) -> str:
        block = self._format_workflow_context_block(title, value)
        return block if block else ""

    def _format_writer_task_prompt(
        self,
        task_title: str,
        sections: List[Tuple[str, Any]],
        output_schema: str,
        task_notes: Optional[List[str]] = None,
        config_prompt: str = "",
    ) -> str:
        parts: List[str] = []
        if config_prompt:
            parts.append(
                "【Writer 配置规则】\n"
                "以下内容来自 Agent Template 绑定的 md prompt / skills / writing-rules，是本次写作的稳定规则来源。\n"
                f"{config_prompt}"
            )

        parts.append(f"【当前任务】\n{task_title}")
        for title, value in sections:
            block = self._format_task_context_block(title, value)
            if block:
                parts.append(block)

        if task_notes:
            parts.append("【本次任务补充要求】\n" + "\n".join(f"- {note}" for note in task_notes if note))

        parts.append(f"【输出 JSON Schema】\n{output_schema}")
        return "\n\n".join(part for part in parts if part)

    def _build_writer_segment_task_notes(
        self,
        task_kind: str,
        runtime_notes: Optional[List[str]] = None,
    ) -> List[str]:
        """构建 Writer 分段/续写/补写任务补充要求。"""
        prompt_asset = self._load_md_prompt_content("function_writer_segment_generation")
        notes = [
            "稳定分段规划、分段写作、续写和补写规则以 md prompt 资产 function_writer_segment_generation 为准。"
        ]
        if prompt_asset:
            notes.append(prompt_asset)
        notes.append(f"当前子任务类型：{task_kind}")
        notes.extend(note for note in (runtime_notes or []) if note)
        return notes

    async def _execute_single(
        self,
        input_data: Dict[str, Any],
        word_count: int,
        min_word_count: int,
        max_word_count: int,
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

        writer_config_prompt = await self._get_writer_config_prompt({
            **input_data,
            "target_word_count": word_count,
            "min_word_count": min_word_count,
        })
        workflow_binding_block = self._build_workflow_binding_block(input_data)

        # 构建用户消息
        if auto_write_mode and writing_prompt:
            user_message = writing_prompt
            if writer_config_prompt:
                user_message = (
                    "【Writer 配置规则】\n"
                    "以下内容来自 Agent Template 绑定的 md prompt / skills / writing-rules，是本次写作的稳定规则来源。\n"
                    f"{writer_config_prompt}\n\n"
                    "【当前写作任务】\n"
                    f"{user_message}"
                )
            if workflow_binding_block:
                user_message = f"{user_message}\n\n{workflow_binding_block}"
            if writing_rules_guidance:
                user_message = f"{user_message}\n\n{writing_rules_guidance}"
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
                workflow_context=input_data,
                writing_rules_guidance=writing_rules_guidance,
                discussion_asset_digest=discussion_asset_digest,
                config_prompt=writer_config_prompt,
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
                workflow_binding_block=workflow_binding_block,
                config_prompt=writer_config_prompt,
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
        max_word_count: int,
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

        workflow_binding_block = self._build_workflow_binding_block(input_data)
        writer_config_prompt = await self._get_writer_config_prompt({
            **input_data,
            "target_word_count": word_count,
            "min_word_count": min_word_count,
        })

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
            workflow_binding_block=workflow_binding_block,
            config_prompt=writer_config_prompt,
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
                min_words=max(1, int(segment_target * 0.85)),
                max_words=max(segment_target, int(segment_target * 1.25)),
                world_info=world_info,
                previous_style=previous_style if i == 0 else None,
                writing_rules_guidance=segment_writing_rules_guidance,
                discussion_asset_digest=discussion_asset_digest,
                workflow_binding_block=workflow_binding_block,
                config_prompt=writer_config_prompt,
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
                workflow_binding_block=workflow_binding_block,
                config_prompt=writer_config_prompt,
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

        # 若模型偶发超写，保留完整内容但标记不合格，交由 Evaluator/条件节点触发修订；
        # 不在这里机械截断，避免破坏章节语义完整性。
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
            "target_word_count": word_count,
            "min_word_count": min_word_count,
            "max_word_count": max_word_count,
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
        workflow_binding_block: str = "",
        config_prompt: str = "",
    ) -> Dict[str, Any]:
        """
        规划分段结构

        Returns:
            Dict: 包含 segments 列表，每段有 focus 和 key_elements
        """
        prompt = self._format_writer_task_prompt(
            task_title="为当前章节规划分段结构。",
            sections=[
                ("章节信息", {
                    "chapter_num": chapter_num,
                    "total_chapters": total_chapters,
                    "target_word_count": word_count,
                    "segment_count": segment_count,
                }),
                ("环境设定", environment or "无特定环境"),
                ("需要表达的意图", intents or "自由发挥"),
                ("角色状态", character_moods or "无特定状态"),
                ("工作流绑定上下文", workflow_binding_block),
                ("已确认讨论资产", discussion_asset_digest),
                ("世界观参考", world_info),
            ],
            task_notes=self._build_writer_segment_task_notes(
                "segment_plan",
                [
                    "当前运行时目标：把本章动态输入拆成具体段落，并输出 WriterSegmentPlanSchema。",
                ],
            ),
            output_schema=self._writer_segment_plan_output_schema(),
            config_prompt=config_prompt,
        )

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
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
        world_info: Optional[Dict[str, Any]] = None,
        previous_style: Optional[str] = None,
        writing_rules_guidance: str = "",
        discussion_asset_digest: str = "",
        workflow_binding_block: str = "",
        config_prompt: str = "",
    ) -> str:
        """构建分段生成提示"""
        min_words = min_words or max(1, int(target_words * 0.85))
        max_words = max_words or max(target_words, int(target_words * 1.25))
        key_elements = self._as_list(segment_info.get('key_elements', []))

        return self._format_writer_task_prompt(
            task_title="按分段计划写作当前段落。",
            sections=[
                ("分段写作任务", {
                    "segment_num": segment_num,
                    "total_segments": total_segments,
                    "focus": segment_info.get("focus", "自由发挥"),
                    "target_words": target_words,
                    "min_words": min_words,
                    "max_words": max_words,
                    "tone": segment_info.get("tone", "平稳"),
                }),
                ("本段关键元素", key_elements),
                ("工作流绑定上下文", workflow_binding_block),
                ("当前相关写作规则", writing_rules_guidance),
                ("世界观参考", world_info),
                ("已确认讨论资产", discussion_asset_digest),
                ("前一段落结尾", previous_content),
                ("前文风格样本", previous_style if segment_num == 1 else ""),
            ],
            task_notes=self._build_writer_segment_task_notes(
                "segment_generation",
                [
                    f"当前运行时字数范围：{min_words}-{max_words} 字，接近目标 {target_words} 字。",
                    "当前运行时目标：写作当前段落，并输出 WriterSegmentSchema。",
                ],
            ),
            output_schema=self._writer_segment_output_schema(),
            config_prompt=config_prompt,
        )

    def _build_supplement_prompt(
        self,
        existing_content: str,
        shortage: int,
        chapter_num: int,
        total_chapters: int,
        writing_rules_guidance: str = "",
        workflow_binding_block: str = "",
        config_prompt: str = "",
    ) -> str:
        """构建补充内容提示"""
        return self._format_writer_task_prompt(
            task_title=f"为已有章节内容补写约 {shortage} 字，补足字数或未覆盖的大纲节点。",
            sections=[
                ("章节信息", {"chapter_num": chapter_num, "total_chapters": total_chapters, "shortage": shortage}),
                ("已有内容", existing_content),
                ("工作流绑定上下文", workflow_binding_block),
                ("当前相关写作规则", writing_rules_guidance),
            ],
            task_notes=self._build_writer_segment_task_notes(
                "supplement",
                [
                    f"当前运行时目标：为已有章节补写约 {shortage} 字，并输出 WriterSupplementSchema。",
                ],
            ),
            output_schema=self._writer_supplement_output_schema(),
            config_prompt=config_prompt,
        )

    def _build_continue_prompt(
        self,
        existing_content: str,
        shortage: int,
        intents: List[str],
        character_moods: Dict[str, str],
        chapter_num: int,
        total_chapters: int,
        writing_rules_guidance: str = "",
        workflow_binding_block: str = "",
        config_prompt: str = "",
    ) -> str:
        """构建续写提示"""
        return self._format_writer_task_prompt(
            task_title=f"在已有内容后自然续写约 {shortage} 字，补足字数或未覆盖的大纲节点。",
            sections=[
                ("章节信息", {"chapter_num": chapter_num, "total_chapters": total_chapters, "shortage": shortage}),
                ("已有内容", existing_content),
                ("需要表达的意图", intents),
                ("角色状态", character_moods),
                ("工作流绑定上下文", workflow_binding_block),
                ("当前相关写作规则", writing_rules_guidance),
            ],
            task_notes=self._build_writer_segment_task_notes(
                "continue",
                [
                    f"当前运行时目标：在已有内容后自然续写约 {shortage} 字，并输出 WriterContinueSchema。",
                ],
            ),
            output_schema=self._writer_continue_output_schema(),
            config_prompt=config_prompt,
        )

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

    def _format_workflow_context_block(self, title: str, value: Any, max_chars: Optional[int] = None) -> str:
        if value in (None, "", [], {}):
            return ""
        if isinstance(value, str):
            text = value
        else:
            try:
                text = json.dumps(value, ensure_ascii=False, indent=2)
            except TypeError:
                text = str(value)
        text = text.strip()
        if not text:
            return ""
        return f"【{title}】\n{text}"

    def _build_workflow_binding_block(self, workflow_context: Optional[Dict[str, Any]]) -> str:
        """构建所有写作路径共享的工作流硬约束块。"""
        workflow_context = workflow_context or {}
        binding_blocks = [
            ("绑定章节大纲（必须遵循，不可替换）", workflow_context.get("chapter_outline")),
            ("章节目标", workflow_context.get("chapter_goals") or workflow_context.get("chapter_goal")),
            ("后续大纲参考（只参考已存在的大纲，不可擅自新建）", workflow_context.get("upcoming_outline_context")),
            ("后续大纲策略", workflow_context.get("upcoming_outline_policy")),
            ("角色出场硬约束", workflow_context.get("character_constraints")),
            ("场景方向", workflow_context.get("scene_directions")),
            ("场景演绎素材（参考材料，不得照抄或覆盖大纲）", workflow_context.get("performance_result")),
            ("场景演绎分层上下文（public 可写入正文；private/delta 仅用于潜台词、连续性和评估线索，不得让其他角色无故知晓）", workflow_context.get("scene_performance_context") or workflow_context.get("role_performance_context")),
            ("角色表演包", workflow_context.get("character_performance_packets")),
            ("关系/状态/连续性变化", {
                "relationship_deltas": workflow_context.get("relationship_deltas"),
                "state_deltas": workflow_context.get("state_deltas"),
                "continuity_notes": workflow_context.get("continuity_notes"),
                "performance_warnings": workflow_context.get("performance_warnings"),
            }),
            ("已确认前文状态", {
                "使用规则": [
                    "confirmed/applied 状态是已确认正史，必须遵守。",
                    "proposed/unapplied 状态只是待审提示，不得当作已发生事实。",
                    "若已确认状态与当前大纲冲突，在输出 metadata 中标记 conflict，不要擅自重写正史。",
                ],
                "packet": workflow_context.get("confirmed_prior_state_packet"),
            }),
            ("总编剧写作计划", workflow_context.get("writing_plan") or workflow_context.get("plot_guidance")),
            ("次要角色辅助计划", workflow_context.get("supporting_character_plan")),
            ("已确认/待使用次要角色", workflow_context.get("plotter_created_characters") or workflow_context.get("character_candidates")),
            ("固定最高级设定", workflow_context.get("fixed_lore_entries")),
            ("本章动态设定", workflow_context.get("dynamic_lore_entries") or workflow_context.get("selected_lore_entries")),
            ("上一轮评估修订要求", workflow_context.get("retry_message") or workflow_context.get("revision_notes")),
        ]

        parts: List[str] = []
        for title, value in binding_blocks:
            block = self._format_workflow_context_block(title, value)
            if block:
                parts.append(block)

        if parts:
            parts.append(
                "【工作流状态使用要求】\n"
                "以上内容是本次章节写作的动态事实输入源，必须按 Writer 配置规则中的工作流上下文绑定规则使用。"
            )

        return "\n\n".join(parts)

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
        workflow_context: Optional[Dict[str, Any]] = None,
        writing_rules_guidance: str = "",
        discussion_asset_digest: str = "",
        config_prompt: str = "",
    ) -> str:
        """构建用户消息"""
        message_parts = []

        if config_prompt:
            message_parts.append(
                "【Writer 配置规则】\n"
                "以下内容来自 Agent Template 绑定的 md prompt / skills / writing-rules，是本次写作的稳定规则来源。\n"
                f"{config_prompt}"
            )

        message_parts.append(
            f"【章节信息】\n"
            f"- 当前章节：第 {chapter_num} 章\n"
            f"- 总章节数：{total_chapters}\n"
            "- 请按 Writer 配置规则、绑定大纲和当前动态上下文完成本章写作。"
        )

        # 字数要求（放在最前面强调）
        message_parts.append(
            f"【字数要求（强制）】\n"
            f"目标：约 {word_count} 字\n"
            f"可接受范围：{min_word_count}-{int(word_count * 1.25)} 字\n"
            "写作完成后请自行统计字数；不要只追求超过最低值，也不要明显超出上限。"
        )

        if writing_rules_guidance:
            message_parts.append(writing_rules_guidance)

        if world_info:
            message_parts.append(self._format_workflow_context_block("世界观设定", world_info))

        workflow_binding_block = self._build_workflow_binding_block(workflow_context)
        if workflow_binding_block:
            message_parts.append(workflow_binding_block)

        # 团队讨论共识（如果有）
        if discussion_summary:
            message_parts.append(
                f"【团队讨论共识】\n{discussion_summary}\n"
                "请在写作中体现以上讨论中不违反绑定大纲、固定设定、角色设定和角色出场硬约束的共识；"
                "凡是引入未授权角色或违反角色状态的讨论内容，一律作为无效素材跳过。"
            )

        if discussion_asset_digest:
            message_parts.append(
                f"【已确认讨论资产】\n{discussion_asset_digest}\n"
                "这些资产来自已确认的集体讨论；只有不违反绑定大纲、固定设定、角色设定和角色出场硬约束的部分才能作为本章写作事实使用。"
                "若资产包含未授权角色、死亡/未激活角色正面出场，或与角色来源历史冲突，必须跳过或改写。"
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
            "本次任务只保留当前章节生成所需的动态输入；稳定写作规则以 Writer 配置规则中的 md prompt、skills 和 writing-rules 为准。"
        )

        return "\n\n".join(message_parts)

    def _writer_segment_plan_output_schema(self) -> str:
        return '''{
    "segments": [
        {
            "focus": "该段的叙事焦点",
            "key_elements": ["该段需要包含的关键元素"],
            "tone": "该段的情感基调",
            "suggested_word_count": 建议字数
        }
    ],
    "overall_structure": "整体结构说明",
    "pacing_note": "节奏把控建议"
}'''

    def _writer_segment_output_schema(self) -> str:
        return '''{
    "content": "本段正文内容",
    "word_count": 字数,
    "key_points_covered": ["已覆盖的关键元素"],
    "transition_to_next": "与下一段的衔接思路"
}'''

    def _writer_supplement_output_schema(self) -> str:
        return '''{
    "content": "补充的内容",
    "word_count": 字数,
    "supplement_direction": "选择的补充方向"
}'''

    def _writer_continue_output_schema(self) -> str:
        return '''{
    "content": "续写的内容",
    "word_count": 续写字数,
    "continue_direction": "选择的续写方向说明"
}'''

    def _writer_style_consistency_output_schema(self) -> str:
        return '''{
    "is_consistent": true/false,
    "confidence": 0.0-1.0,
    "differences": ["风格差异列表"],
    "suggestions": ["修改建议"]
}'''

    def _writer_scene_description_output_schema(self) -> str:
        return '''{
    "description": "场景描写文本",
    "word_count": 字数,
    "sensory_elements": {
        "visual": "视觉元素",
        "auditory": "听觉元素",
        "olfactory": "嗅觉元素",
        "tactile": "触觉元素"
    }
}'''

    def _writer_character_voice_rewrite_output_schema(self) -> str:
        return '''{
    "rewritten_text": "改写后的文本",
    "changes_made": ["修改说明列表"]
}'''

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
        config_prompt = await self._get_writer_config_prompt({"task_type": "style_check"})
        prompt = self._format_writer_task_prompt(
            task_title="检查新生成文本与前文样本的风格一致性。",
            sections=[
                ("前文样本", previous_style),
                ("新生成文本", generated_text),
            ],
            output_schema=self._writer_style_consistency_output_schema(),
            config_prompt=config_prompt,
        )

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
        config_prompt = await self._get_writer_config_prompt({"task_type": "scene_description"})
        prompt = self._format_writer_task_prompt(
            task_title="生成一段服务情节和氛围的短场景描写。",
            sections=[
                ("地点", location),
                ("氛围", atmosphere),
                ("感官细节", sensory_details if sensory_details else "自由发挥"),
            ],
            output_schema=self._writer_scene_description_output_schema(),
            config_prompt=config_prompt,
        )

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
        except PromptGovernanceError as e:
            logger.error("场景描写 prompt governance 失败：%s", e)
            return AgentResponse(
                success=False,
                error=str(e),
                metadata={
                    "prompt_governance_error": True,
                    "prompt_render_trace": e.trace,
                },
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
        config_prompt = await self._get_writer_config_prompt({"task_type": "character_voice_rewrite"})
        prompt = self._format_writer_task_prompt(
            task_title="将原始文本改写为符合指定角色声音的版本。",
            sections=[
                ("角色信息", {
                    "name": character_name,
                    "speech_pattern": speech_pattern,
                    "lexicon": lexicon,
                    "forbidden_words": forbidden_words,
                }),
                ("原始文本", original_text),
            ],
            output_schema=self._writer_character_voice_rewrite_output_schema(),
            config_prompt=config_prompt,
        )

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
        except PromptGovernanceError as e:
            logger.error("角色声音重写 prompt governance 失败：%s", e)
            return AgentResponse(
                success=False,
                error=str(e),
                metadata={
                    "prompt_governance_error": True,
                    "prompt_render_trace": e.trace,
                },
            )
        except StructuredOutputError as e:
            logger.error(f"角色声音改写 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"角色声音重写失败：{e}")
            return AgentResponse(success=False, error=str(e))
