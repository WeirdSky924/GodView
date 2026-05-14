"""
章节大纲服务
GodView v9: PlotOutlineAgent 专用

负责章节大纲的生成、管理和存储
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.chapter_outline import (
    ChapterOutline,
    ChapterOutlineStatus,
    CreateChapterOutlineDTO,
    EmotionCurve,
    EmotionPoint,
    EmotionType,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    SceneOutline,
    SceneType,
    ConflictLevel,
    UpdateChapterOutlineDTO,
    ValidateOutlineRequest,
    ValidateOutlineResponse,
)
from app.models.plot import Hook, HookStatus, HookType
from app.models.skill import SkillTestResult

logger = logging.getLogger(__name__)


class PlotOutlineService:
    """章节大纲服务"""

    OUTLINE_CONSISTENCY_REPAIR_PROMPT_ID = "function_plot_outline_consistency_repair"
    OUTLINE_GENERATION_OUTPUT_PROMPT_ID = "plot_outline_output"

    def __init__(self, db=None, skill_service=None, prompt_service=None):
        """
        初始化章节大纲服务

        Args:
            db: 数据库连接
            skill_service: Skill 服务（用于调用大纲生成 Skill）
            prompt_service: Prompt 模板服务
        """
        self._db = db
        self._skill_service = skill_service
        self._prompt_service = prompt_service

        # 内存缓存
        self._outlines_cache: Dict[str, ChapterOutline] = {}
        self._loaded_outline_projects: set[str] = set()

        self._context_cache: Dict[str, Dict[str, Any]] = {}
        self._formatted_context_cache: Dict[str, Dict[str, Any]] = {}
        self._system_prompt_cache: Dict[str, Dict[str, Any]] = {}
        self._system_prompt_trace_cache: Dict[str, Dict[str, Any]] = {}
        self._output_format_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = timedelta(minutes=5)

        # 获取 LLM 配置
        from app.config import settings
        self._llm_provider = settings.llm_provider
        llm_config = settings.get_llm_config(self._llm_provider)
        self._llm_api_key = llm_config.get("api_key", "")
        self._llm_base_url = llm_config.get("base_url", "")
        self._llm_model = llm_config.get("model", "")
        self._llm_temperature = llm_config.get("temperature", 0.7)
        self._llm_max_tokens = llm_config.get("max_tokens", 4096)
        self._outline_chat_max_tokens = max(self._llm_max_tokens, 8192)
        self._outline_chat_max_continuations = 4

        logger.info(f"[PlotOutlineService] LLM 配置 - Provider: {self._llm_provider}, Model: {self._llm_model}, Base: {self._llm_base_url}")


    def _is_cache_entry_valid(self, entry: Optional[Dict[str, Any]]) -> bool:
        if not entry:
            return False

        expires_at = entry.get("expires_at")
        return isinstance(expires_at, datetime) and expires_at > datetime.now()

    def _cache_entry(self, cache: Dict[str, Dict[str, Any]], key: str, value: Any):
        cache[key] = {
            "value": value,
            "expires_at": datetime.now() + self._cache_ttl,
        }
        return value

    def _get_cached_value(self, cache: Dict[str, Dict[str, Any]], key: str):
        entry = cache.get(key)
        if not self._is_cache_entry_valid(entry):
            if key in cache:
                del cache[key]
            return None
        return entry["value"]

    def _invalidate_project_caches(self, project_id: str, chapter_number: Optional[int] = None):
        context_prefix = f"{project_id}:"
        for cache in (self._context_cache, self._formatted_context_cache, self._system_prompt_cache, self._system_prompt_trace_cache):
            stale_keys = [key for key in cache if key.startswith(context_prefix)]
            for key in stale_keys:
                del cache[key]

    def _merge_outline_into_list(self, outline: ChapterOutline):
        self._outlines_cache[outline.id] = outline
        self._loaded_outline_projects.add(outline.project_id)

    def _build_outline_list_cache(self, outlines: List[ChapterOutline]):
        self._outlines_cache = {outline.id: outline for outline in outlines}
        self._loaded_outline_projects = {outline.project_id for outline in outlines}

    def _clone_outline_as_revision(self, outline: ChapterOutline) -> ChapterOutline:
        data = outline.model_dump()
        data.update({
            "id": f"outline_{uuid.uuid4().hex[:8]}",
            "status": ChapterOutlineStatus.REVISION,
            "approved_at": None,
            "approved_by": None,
            "previous_outline_id": outline.id,
            "next_outline_id": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        })
        return ChapterOutline(**data)

    def _get_context_cache_key(self, project_id: str, chapter_number: int) -> str:
        return f"{project_id}:context:{chapter_number}"

    def _get_formatted_context_cache_key(self, project_id: str, chapter_number: int) -> str:
        return f"{project_id}:formatted-context:{chapter_number}"

    def _get_system_prompt_cache_key(self, project_id: str, chapter_number: int) -> str:
        return f"{project_id}:system-prompt:{chapter_number}"

    def _log_timing(self, stage: str, started_at: float):
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(f"[PlotOutline][Timing] {stage}: {elapsed_ms:.1f}ms")

    async def _ensure_cache(self, project_id: str):
        if project_id in self._loaded_outline_projects:
            return

        if not self._db:
            return

        try:
            rows = await self._db.execute_query(
                """
                SELECT * FROM chapter_outlines
                WHERE project_id = :project_id
                  AND deleted_at IS NULL
                ORDER BY chapter_number ASC, approved_at DESC NULLS LAST, updated_at DESC NULLS LAST
                """,
                {"project_id": project_id}
            )

            self._outlines_cache = {
                outline_id: outline
                for outline_id, outline in self._outlines_cache.items()
                if outline.project_id != project_id
            }

            for row in rows:
                outline = self._row_to_outline(row)
                self._outlines_cache[outline.id] = outline

            self._loaded_outline_projects.add(project_id)
            logger.info(f"从数据库加载项目 {project_id} 的 {len(rows)} 个章节大纲")
        except Exception as e:
            logger.warning(f"从数据库加载章节大纲失败: {e}")

    async def _get_cached_project_context(self, project_id: str, chapter_number: int) -> Dict[str, Any]:
        cache_key = self._get_context_cache_key(project_id, chapter_number)
        cached = self._get_cached_value(self._context_cache, cache_key)
        if cached is not None:
            return cached

        started_at = time.perf_counter()
        context = await self.get_full_project_context(project_id, chapter_number)
        self._log_timing("fetch_project_context", started_at)
        return self._cache_entry(self._context_cache, cache_key, context)

    def _get_cached_formatted_context(self, project_id: str, chapter_number: int, full_context: Dict[str, Any]) -> str:
        cache_key = self._get_formatted_context_cache_key(project_id, chapter_number)
        cached = self._get_cached_value(self._formatted_context_cache, cache_key)
        if cached is not None:
            return cached

        started_at = time.perf_counter()
        formatted = self.format_context_for_prompt(full_context)
        self._log_timing("format_project_context", started_at)
        return self._cache_entry(self._formatted_context_cache, cache_key, formatted)

    async def _get_cached_system_prompt_with_trace(
        self,
        project_id: str,
        chapter_number: int,
        full_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        cache_key = self._get_system_prompt_cache_key(project_id, chapter_number)
        cached = self._get_cached_value(self._system_prompt_cache, cache_key)
        cached_trace = self._get_cached_value(self._system_prompt_trace_cache, cache_key)
        if cached is not None and cached_trace is not None:
            return {"content": cached, "trace": cached_trace}

        started_at = time.perf_counter()
        try:
            from app.services.agent_prompt_service import get_agent_prompt_service
            prompt_service = get_agent_prompt_service()
            prompt_data = await prompt_service.build_agent_prompt_with_trace(
                agent_type="plot_outline",
                project_id=project_id,
                include_skills=True,
                scenario="generate_chapter_outline",
            )
            base_prompt = prompt_data.get("content", "")
            trace = prompt_data.get("trace", {}) or {}
        except Exception as e:
            logger.warning(f"加载 plot_outline prompt 模板失败: {e}，使用默认 prompt")
            fallback_data = self._build_fallback_prompt_with_trace(project_id)
            base_prompt = fallback_data["content"]
            trace = fallback_data["trace"]

        context_hints = self._build_context_hints(full_context)
        output_format = await self._get_cached_output_format_prompt()
        system_prompt = f"{base_prompt}\n\n{context_hints}\n\n{output_format}".strip()
        self._log_timing("build_system_prompt", started_at)
        self._cache_entry(self._system_prompt_cache, cache_key, system_prompt)
        self._cache_entry(self._system_prompt_trace_cache, cache_key, trace)
        return {"content": system_prompt, "trace": trace}

    async def _get_cached_system_prompt(
        self,
        project_id: str,
        chapter_number: int,
        full_context: Dict[str, Any],
    ) -> str:
        prompt_data = await self._get_cached_system_prompt_with_trace(project_id, chapter_number, full_context)
        return prompt_data.get("content", "")

    def _build_outline_runtime_context(self, existing_outline: Optional[ChapterOutline]) -> str:
        if not existing_outline:
            return "当前章节暂无大纲，需要创建新的大纲。"

        return f"""
当前章节大纲状态：
- 标题: {existing_outline.title}
- 摘要: {existing_outline.summary if existing_outline.summary else ''}
- 状态: {existing_outline.status.value}
- 场景数: {len(existing_outline.scenes)}
- 目标字数: {existing_outline.target_word_count}
""".strip()

    def _build_context_hints(self, full_context: Optional[Dict[str, Any]]) -> str:
        if not full_context:
            return ""

        char_count = len(full_context.get("characters", []))
        constitutional_count = len(full_context.get("constitutional_rules", []))
        core_count = len(full_context.get("core_settings", []))
        relevant_count = len(full_context.get("relevant_settings", []))
        hooks_pending = len(full_context.get("hooks", {}).get("pending", []))
        hooks_to_resolve = len(full_context.get("hooks", {}).get("to_resolve", []))

        return f"""
【已获取的项目上下文】
- 角色信息：{char_count} 个角色可用
- 宪法级设定：{constitutional_count} 条（不可违反）
- 核心设定：{core_count} 条
- 相关设定：{relevant_count} 条
- 待处理伏笔：{hooks_pending} 个
- 建议回收伏笔：{hooks_to_resolve} 个

生成或修改大纲时，必须优先服从宪法级设定与核心设定，其优先级高于输出格式偏好。
""".strip()

    async def _get_cached_output_format_prompt(self) -> str:
        cache_key = self.OUTLINE_GENERATION_OUTPUT_PROMPT_ID
        cached = self._get_cached_value(self._output_format_cache, cache_key)
        if cached is not None:
            return cached

        content = self._load_md_prompt_content(self.OUTLINE_GENERATION_OUTPUT_PROMPT_ID)
        if content:
            return self._cache_entry(self._output_format_cache, cache_key, content)

        return self._cache_entry(cache=self._output_format_cache, key=cache_key, value=self._get_simple_output_format())

    def _get_output_format_prompt(self) -> str:
        cached = self._get_cached_value(self._output_format_cache, self.OUTLINE_GENERATION_OUTPUT_PROMPT_ID)
        if cached is not None:
            return cached

        content = self._load_md_prompt_content(self.OUTLINE_GENERATION_OUTPUT_PROMPT_ID)
        if not content:
            logger.warning("Plot Outline 输出格式 Prompt 资产缺失: %s", self.OUTLINE_GENERATION_OUTPUT_PROMPT_ID)
            content = self._get_simple_output_format()
        return self._cache_entry(self._output_format_cache, self.OUTLINE_GENERATION_OUTPUT_PROMPT_ID, content)

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

    def _build_md_plot_outline_fallback_prompt(self) -> str:
        """从 md prompt 资产构建 plot_outline 备用 prompt。"""
        prompt_ids = ["role_plot_outline", "function_plot_outline", "plot_outline_output"]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        return "\n\n".join(parts).strip()

    def _build_combined_context(self, context_str: str, user_context: str) -> str:
        if not context_str:
            return user_context
        if not user_context:
            return context_str
        return f"{context_str}\n\n{user_context}"

    def _build_chat_response_contract(self, *, auto_save: bool) -> str:
        save_policy = "本轮允许后端自动保存解析到的大纲。" if auto_save else "本轮只生成预览，后端不会自动保存；用户确认后才保存。"
        return (
            "【本轮响应要求】\n"
            f"{save_policy}\n"
            "如果用户要求生成、修改、审查或保存大纲，必须在回答末尾输出一个可解析的 ```json fenced code block。\n"
            "不要默认限制为当前单章；当用户要求黄金三章、多章、前几章、连续剧情或未明确限定单章时，应主动输出 {\"chapters\":[...]} 多章结构。\n"
            "只有用户明确选择/修改某一章时，才输出单章 {chapter_number,title,summary,chapter_goals,scenes,hooks_planted,hooks_resolved,target_word_count}。\n"
            "每章必须包含 chapter_number/title/summary/scenes；scenes 不得为空；participating_characters 与 pov_character 必须使用直接可出场角色标准名。\n"
            "如果用户只是询问或讨论，可以正常回答；不要为了闲聊强行生成 JSON。"
        )

    def _full_text(self, value: Optional[str]) -> str:
        if not value:
            return ""
        return str(value)

    def _build_lore_context_entry(self, lore: Dict[str, Any], summary_limit: int) -> Dict[str, Any]:
        summary = lore.get("summary") or lore.get("content") or ""
        entry = {
            "title": lore.get("title", ""),
            "category": lore.get("category", "custom"),
            "priority": lore.get("priority", "standard"),
            "summary": summary,
        }
        if lore.get("id"):
            entry["id"] = str(lore.get("id"))
        return entry

    def _split_world_settings(self, world_settings: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        constitutional_rules = [item for item in world_settings if item.get("priority") == "constitutional"]
        core_settings = [item for item in world_settings if item.get("priority") == "core"]
        relevant_settings = [
            item for item in world_settings
            if item.get("priority") not in {"constitutional", "core"}
        ]
        return constitutional_rules, core_settings, relevant_settings

    def _format_lore_section(self, title: str, items: List[Dict[str, Any]], summary_limit: int, max_items: Optional[int] = None) -> List[str]:
        if not items:
            return []

        lines = [title]
        for lore in items:
            lines.append(f"- [{lore.get('priority', 'standard')}] {lore.get('title', '')}")
            summary = self._full_text(lore.get("summary"))
            if summary:
                lines.append(f"  {summary}")
        lines.append("")
        return lines

    def _format_consistency_check_text(self, outline_updates: Dict[str, Any]) -> str:
        if "chapters" in outline_updates:
            blocks = []
            for chapter in outline_updates.get("chapters", []):
                chapter_no = chapter.get("chapter_number", "?")
                title = chapter.get("title", "")
                summary = chapter.get("summary", "")
                blocks.append(f"第{chapter_no}章 {title}\n摘要：{summary}")
                for scene in chapter.get("scenes", []):
                    blocks.append(f"- 场景{scene.get('scene_number', '?')} {scene.get('title', '')}: {scene.get('summary', '')}")
            return "\n".join(blocks)

        title = outline_updates.get("title", "")
        summary = outline_updates.get("summary", "")
        lines = [f"第{outline_updates.get('chapter_number', '?')}章 {title}", f"摘要：{summary}"]
        for scene in outline_updates.get("scenes", []):
            lines.append(f"- 场景{scene.get('scene_number', '?')} {scene.get('title', '')}: {scene.get('summary', '')}")
        return "\n".join(lines)

    async def _check_outline_setting_consistency(
        self,
        project_id: str,
        outline_updates: Dict[str, Any],
        full_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self._skill_service or not outline_updates:
            return {"conflicts": [], "setting_gaps": [], "risk_areas": [], "consistency_score": 100}

        try:
            from app.services.skill_service import ExecuteSkillDTO

            world_sections: List[str] = []
            world_sections.extend(self._format_lore_section("【宪法级设定 - 不可违反】", full_context.get("constitutional_rules", []), 1200))
            world_sections.extend(self._format_lore_section("【核心设定】", full_context.get("core_settings", []), 800))
            world_sections.extend(self._format_lore_section("【相关设定】", full_context.get("relevant_settings", []), 500))

            character_lines = []
            for char in full_context.get("characters", []):
                parts = [char.get("name", "")]
                if char.get("role"):
                    parts.append(f"角色定位: {char['role']}")
                if char.get("personality"):
                    parts.append(f"性格: {char['personality']}")
                if char.get("background"):
                    parts.append(f"背景: {char['background']}")
                character_lines.append(" | ".join(parts))

            result = await self._skill_service.execute_skill(ExecuteSkillDTO(
                skill_id="skill_setting_conflict_detection",
                project_id=project_id,
                parameters={
                    "chapter_content": self._format_consistency_check_text(outline_updates),
                    "world_settings": "\n".join(world_sections),
                    "character_settings": "\n".join(character_lines),
                    "ability_settings": "",
                }
            ))

            if not result.success:
                logger.warning(f"[PlotOutline] 设定一致性检测失败: {result.error}")
                return {"conflicts": [], "setting_gaps": [], "risk_areas": [], "consistency_score": 100}

            parsed = self._parse_consistency_result(
                self._require_structured_dict(result, "解析设定一致性检测结果失败")
            )
            return {
                "conflicts": parsed.get("conflicts", []),
                "setting_gaps": parsed.get("setting_gaps", []),
                "risk_areas": parsed.get("risk_areas", []),
                "consistency_score": parsed.get("consistency_score", 100),
            }
        except Exception as e:
            logger.warning(f"[PlotOutline] 执行设定一致性检测失败: {e}")
            return {"conflicts": [], "setting_gaps": [], "risk_areas": [], "consistency_score": 100}

    def _build_outline_consistency_repair_message(
        self,
        original_message: str,
        consistency: Dict[str, Any],
    ) -> str:
        prompt_asset = self._load_md_prompt_content(
            self.OUTLINE_CONSISTENCY_REPAIR_PROMPT_ID,
        ) or (
            "你刚生成的大纲存在设定一致性风险。请基于原任务修正后重新输出完整 JSON，"
            "并优先服从宪法级设定和核心设定。"
        )
        conflicts = consistency.get("conflicts", [])
        risk_areas = consistency.get("risk_areas", [])
        setting_gaps = consistency.get("setting_gaps", [])

        feedback_blocks = [prompt_asset]
        if conflicts:
            feedback_blocks.append("## 冲突列表\n" + "\n".join([f"- {item}" for item in conflicts]))
        if risk_areas:
            feedback_blocks.append("## 风险区域\n" + "\n".join([f"- {item}" for item in risk_areas]))
        if setting_gaps:
            feedback_blocks.append("## 设定缺口\n" + "\n".join([f"- {item}" for item in setting_gaps]))

        return f"{original_message}\n\n" + "\n\n".join(feedback_blocks)

    async def _repair_outline_with_consistency_feedback(
        self,
        project_id: str,
        chapter_number: int,
        message: str,
        full_context: Dict[str, Any],
        system_prompt: str,
        combined_context: str,
        llm_config: Dict[str, Any],
        consistency: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        conflicts = consistency.get("conflicts", [])
        risk_areas = consistency.get("risk_areas", [])

        if not conflicts and not risk_areas:
            return None

        repaired_response = await self._call_llm_for_chat(
            system_prompt=system_prompt,
            user_message=self._build_outline_consistency_repair_message(message, consistency),
            context=combined_context,
            llm_config=llm_config,
        )
        repaired_updates = self._try_parse_outline_updates(repaired_response)
        if repaired_updates:
            logger.info("[PlotOutline] 已根据设定一致性反馈执行一次自动修正")
        return repaired_updates

    def _extract_json_candidates(self, text: str) -> List[str]:
        import re

        candidates: List[str] = []

        json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', text)
        candidates.extend([block.strip() for block in json_blocks if block.strip()])

        stack: List[str] = []
        start_index: Optional[int] = None
        in_string = False
        escape = False

        for index, char in enumerate(text):
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '{':
                if not stack:
                    start_index = index
                stack.append(char)
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack and start_index is not None:
                        candidate = text[start_index:index + 1].strip()
                        if candidate:
                            candidates.append(candidate)
                        start_index = None

        return candidates

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        for candidate in self._extract_json_candidates(text):
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    chapters = [item for item in data if isinstance(item, dict)]
                    if chapters:
                        return {"chapters": chapters}
            except json.JSONDecodeError:
                continue
        return None

    def _coerce_outline_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """兼容 LLM 常见外层包装，提取真正的大纲 JSON。"""
        if self._has_outline_shape(data):
            return data

        for key in ("outline", "chapter_outline", "outline_update", "chapter", "data", "result"):
            value = data.get(key)
            if isinstance(value, dict) and self._has_outline_shape(value):
                return value

        for key in ("outlines", "chapter_outlines"):
            value = data.get(key)
            if isinstance(value, list):
                chapters = [item for item in value if isinstance(item, dict)]
                if chapters:
                    return {"chapters": chapters}

        return data

    def _has_outline_shape(self, data: Dict[str, Any]) -> bool:
        return any(key in data for key in ["title", "summary", "scenes", "chapters", "chapter_goals", "writing_guide"])

    def _has_meaningful_outline_content(self, outline_data: Dict[str, Any]) -> bool:
        if not outline_data:
            return False
        if outline_data.get("title"):
            return True
        if outline_data.get("summary"):
            return True
        if outline_data.get("scenes"):
            return True
        if outline_data.get("chapter_goals"):
            return True
        hooks = outline_data.get("hooks_planted") or outline_data.get("hooks_resolved")
        if hooks:
            return True
        return False

    def _contains_structured_outline_attempt(self, response: str) -> bool:
        text = str(response or "")
        lower = text.lower()
        return any(
            marker in lower
            for marker in (
                "```json",
                '"chapters"',
                '"chapter_number"',
                '"scenes"',
                '"chapter_outline"',
                '"outline"',
            )
        )

    def _has_unclosed_json_fence(self, response: str) -> bool:
        text = str(response or "")
        return text.lower().count("```json") > text.count("```") - text.lower().count("```json")

    def _has_unbalanced_structured_json(self, response: str) -> bool:
        text = str(response or "")
        stack: List[str] = []
        in_string = False
        escape = False
        saw_json = False
        pairs = {"}": "{", "]": "["}
        for char in text:
            if escape:
                escape = False
                continue
            if char == "\\" and in_string:
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char in "[{":
                stack.append(char)
                saw_json = True
            elif char in "]}":
                if stack and stack[-1] == pairs[char]:
                    stack.pop()
                elif saw_json:
                    return True
        return saw_json and bool(stack)

    def _is_structured_outline_complete(self, response: str) -> bool:
        if not self._contains_structured_outline_attempt(response):
            return True
        if self._extract_json_object(response):
            return True
        if self._has_unclosed_json_fence(response):
            return False
        if self._has_unbalanced_structured_json(response):
            return False
        return False

    def _needs_outline_continuation(self, response: str, finish_reason: Optional[str]) -> bool:
        reason = str(finish_reason or "").lower()
        if reason in {"max_tokens", "length"}:
            return True
        return not self._is_structured_outline_complete(response)

    def _build_outline_continuation_instruction(self, original_message: str, accumulated_response: str) -> str:
        tail = str(accumulated_response or "")[-1600:]
        return (
            "上一轮 Plot Outline Agent 回复因为长度或结构完整性限制没有结束。"
            "请从上一轮回复的最后一个字符之后继续输出，严禁重写、严禁总结、严禁省略、严禁改写已输出内容。"
            "如果正在输出 JSON 或 ```json 代码块，请只补齐剩余 JSON 内容并闭合所有数组、对象和代码块；"
            "不要为了变短而压缩字段，不要丢弃任何章节、场景或设定信息。\n\n"
            f"原始用户请求：\n{original_message}\n\n"
            f"上一轮回复末尾供续写定位：\n{tail}"
        )

    def _merge_continued_response(self, accumulated_response: str, continuation: str) -> str:
        base = str(accumulated_response or "")
        addition = str(continuation or "")
        if not base:
            return addition
        if not addition:
            return base
        max_overlap = min(len(base), len(addition), 1000)
        for size in range(max_overlap, 0, -1):
            if base[-size:] == addition[:size]:
                return base + addition[size:]
        return base + addition

    def _is_saveable_pending_outline(self, outline_data: Dict[str, Any]) -> bool:
        if not isinstance(outline_data, dict):
            return False
        if not outline_data.get("title") or not outline_data.get("summary"):
            return False
        scenes = outline_data.get("scenes")
        return isinstance(scenes, list) and any(isinstance(scene, dict) for scene in scenes)

    def _filter_saveable_outline_updates(self, outline_updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(outline_updates, dict):
            return None
        if isinstance(outline_updates.get("chapters"), list):
            chapters = [
                chapter for chapter in outline_updates.get("chapters") or []
                if self._is_saveable_pending_outline(chapter)
            ]
            if not chapters:
                return None
            filtered = dict(outline_updates)
            filtered["chapters"] = chapters
            return filtered
        if self._is_saveable_pending_outline(outline_updates):
            return outline_updates
        return None

    def _looks_like_outline_request(self, message: str) -> bool:
        text = str(message or "").strip().lower()
        if not text:
            return False
        markers = [
            "保存", "草稿", "生成", "创建", "写一版", "输出", "json", "大纲", "章节", "黄金三章",
            "前几章", "多章", "修改", "修订", "重写", "完善", "续写", "chapter", "outline",
        ]
        return any(marker in text for marker in markers)

    def _require_structured_dict(self, result: SkillTestResult, error_detail: str) -> Dict[str, Any]:
        try:
            return result.require_structured_dict()
        except ValueError as exc:
            logger.warning("[PlotOutline] Skill 返回了无效结构化输出: %s", exc)
            raise ValueError(error_detail) from exc

    def _parse_consistency_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("设定一致性检测结果不是对象")

        conflicts = data.get("conflicts", [])
        critical_conflicts = data.get("critical_conflicts", [])
        suggestions = data.get("suggestions", [])
        checked_settings = data.get("checked_settings", [])
        overall_compliance = data.get("overall_compliance")
        consistency_score = data.get("consistency_score", overall_compliance if overall_compliance is not None else 100)

        risk_areas: List[str] = []
        for item in conflicts:
            if isinstance(item, dict):
                description = item.get("conflict") or item.get("description") or str(item)
                severity = item.get("severity")
                if severity:
                    risk_areas.append(f"{severity}: {description}")
                else:
                    risk_areas.append(description)
            else:
                risk_areas.append(str(item))

        setting_gaps = [str(item) for item in suggestions]
        if checked_settings and not setting_gaps:
            setting_gaps = [str(item) for item in checked_settings]

        return {
            "conflicts": conflicts,
            "setting_gaps": setting_gaps,
            "risk_areas": risk_areas + [str(item) for item in critical_conflicts if not isinstance(item, dict)],
            "consistency_score": consistency_score,
        }

    def _compact_outline_payload(self, outline: ChapterOutline) -> Dict[str, Any]:
        return {
            "id": outline.id,
            "project_id": outline.project_id,
            "chapter_number": outline.chapter_number,
            "title": outline.title,
            "summary": outline.summary,
            "status": outline.status.value,
            "scenes": self._to_plain_data(outline.scenes),
            "emotion_curve": self._to_plain_data(outline.emotion_curve),
            "chapter_goals": outline.chapter_goals,
            "plot_advancement": outline.plot_advancement,
            "character_arcs": outline.character_arcs,
            "hooks_planted": outline.hooks_planted,
            "hooks_resolved": outline.hooks_resolved,
            "quality_metrics": outline.quality_metrics,
            "target_word_count": outline.target_word_count,
            "estimated_word_count": outline.estimated_word_count,
            "created_at": outline.created_at,
            "updated_at": outline.updated_at,
            "approved_at": outline.approved_at,
            "approved_by": outline.approved_by,
            "previous_outline_id": outline.previous_outline_id,
            "next_outline_id": outline.next_outline_id,
        }

    def _to_plain_data(self, value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, list):
            return [self._to_plain_data(item) for item in value]
        if isinstance(value, dict):
            return {key: self._to_plain_data(item) for key, item in value.items()}
        return value

    def _normalize_resource_name(self, value: Any) -> str:
        """标准化资源名，避免空值和明显占位符进入资源需求。"""
        text = str(value or "").strip()
        text = re.sub(r"\s+", " ", text)
        invalid_values = {
            "",
            "无",
            "无地点",
            "未知",
            "未知地点",
            "待定",
            "tbd",
            "none",
            "null",
            "n/a",
            "未命名",
            "未指定",
        }
        if text.lower() in invalid_values or text in invalid_values:
            return ""
        return text

    def _known_resource_names(self, items: List[Dict[str, Any]], fields: Tuple[str, ...]) -> Set[str]:
        names: Set[str] = set()
        for item in items or []:
            if not isinstance(item, dict):
                continue
            for field in fields:
                name = self._normalize_resource_name(item.get(field))
                if name:
                    names.add(name.lower())
        return names

    def _as_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, set):
            return list(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    return [parsed]
            except Exception:
                pass
            return [part.strip() for part in re.split(r"[,，、;；]", text) if part.strip()]
        return [value]

    def _as_dict(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return {}
            try:
                parsed = json.loads(text)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _character_presence_types(self, character: Dict[str, Any]) -> Set[str]:
        values = {
            str(item).strip().lower()
            for item in self._as_list(character.get("available_presence_types"))
            if str(item).strip()
        }
        return values or {"present"}

    def _character_label(self, character: Dict[str, Any]) -> str:
        tier_labels = {
            "protagonist": "主角",
            "co_protagonist": "共同主角",
            "deuteragonist": "第二主角",
            "mentor": "导师",
            "love_interest": "情感关键角色",
            "best_friend": "核心盟友",
            "archenemy": "宿敌",
            "major_ally": "重要盟友",
            "major_antagonist": "主要反派",
            "rival": "竞争者",
            "family_member": "家族角色",
            "supporting": "配角",
            "npc": "背景角色",
        }
        tier = str(character.get("importance_tier") or character.get("importance") or "").strip().lower()
        role = str(character.get("role") or "").strip()
        label = tier_labels.get(tier)
        if label:
            return f"{label}; role={role or '未标注'}" if role and role.lower() != tier else label
        return role or "角色"

    def _can_character_appear_in_chapter(self, character: Dict[str, Any], chapter_number: int) -> Tuple[str, str, str]:
        name = character.get("name") or "未知角色"
        status = str(character.get("status") or "active").strip().lower()
        presence_types = self._character_presence_types(character)
        debut = character.get("debut_chapter")
        exit_chapter = character.get("exit_chapter")
        death_detail = self._as_dict(character.get("death_detail"))

        hard_unavailable_statuses = {"disabled", "unavailable", "sealed", "deleted"}
        mention_only_statuses = {"dead", "deceased", "inactive", "retired", "missing", "lost"}
        mention_presence_types = {"mentioned", "memory", "flashback", "record", "rumor", "offscreen", "off_screen", "reference"}
        direct_presence_types = {"present", "direct", "onscreen", "on_screen", "live", "dialogue", "action"}

        try:
            if debut is not None and int(debut) > chapter_number:
                return "unavailable", "blocking", f"尚未到首次登场章节：第 {debut} 章"
        except (TypeError, ValueError):
            pass

        try:
            if exit_chapter is not None and int(exit_chapter) < chapter_number:
                return "mentioned_only", "blocking", f"已在第 {exit_chapter} 章后退场，只能作为历史/影响被提及"
        except (TypeError, ValueError):
            pass

        if status in hard_unavailable_statuses:
            return "unavailable", "blocking", f"角色状态为 {status}，不能安排本章直接出场"
        if status in mention_only_statuses or death_detail:
            return "mentioned_only", "blocking", f"角色状态为 {status or '非活跃'}，只能作为回忆、记录、传闻或后果被提及"
        if presence_types and not (presence_types & direct_presence_types):
            if presence_types & mention_presence_types:
                return "mentioned_only", "blocking", f"可用出场类型仅为 {', '.join(sorted(presence_types))}，不能直接出场"
            return "unavailable", "blocking", f"可用出场类型不包含 present/direct：{', '.join(sorted(presence_types))}"
        return "direct_available", "ok", "本章允许直接出场"

    def _build_character_availability_packet(self, characters: List[Dict[str, Any]], chapter_number: int) -> Dict[str, Any]:
        packet: Dict[str, Any] = {
            "chapter_number": chapter_number,
            "direct_available_characters": [],
            "mentioned_only_characters": [],
            "unavailable_characters": [],
            "canonical_name_map": {},
            "availability_by_name": {},
        }
        for character in characters or []:
            if not isinstance(character, dict):
                continue
            name = self._normalize_resource_name(character.get("name"))
            if not name:
                continue
            bucket, severity, reason = self._can_character_appear_in_chapter(character, chapter_number)
            aliases = [self._normalize_resource_name(alias) for alias in self._as_list(character.get("aliases"))]
            aliases = [alias for alias in aliases if alias]
            entry = {
                "id": str(character.get("id") or ""),
                "name": name,
                "aliases": aliases,
                "role": character.get("role") or "",
                "importance_tier": character.get("importance_tier") or character.get("importance") or "",
                "hierarchy_label": self._character_label(character),
                "narrative_weight": character.get("narrative_weight") or "",
                "story_arc_role": character.get("story_arc_role") or "",
                "plot_priority": character.get("plot_priority"),
                "status": character.get("status") or "",
                "debut_chapter": character.get("debut_chapter"),
                "debut_scene": character.get("debut_scene"),
                "exit_chapter": character.get("exit_chapter"),
                "exit_reason": character.get("exit_reason") or "",
                "active_arc": character.get("active_arc") or "",
                "available_presence_types": sorted(self._character_presence_types(character)),
                "reason": reason,
                "severity": severity,
                "description": character.get("description") or "",
                "personality": character.get("personality") or "",
                "background_story": character.get("background_story") or character.get("background") or "",
                "goals": self._as_list(character.get("goals")),
                "relationships": self._as_list(character.get("relationships")),
                "key_relationships": self._as_dict(character.get("key_relationships")),
                "current_region_id": character.get("current_region_id") or "",
                "current_location": character.get("current_location") or "",
                "current_location_reason": character.get("current_location_reason") or "",
            }
            packet[f"{bucket}_characters"].append(entry)
            packet["availability_by_name"][name.lower()] = {"bucket": bucket, **entry}
            packet["canonical_name_map"][name.lower()] = name
            for alias in aliases:
                packet["canonical_name_map"][alias.lower()] = name
        return packet

    def _format_character_availability_packet(self, packet: Dict[str, Any]) -> str:
        if not packet:
            return ""
        lines = [
            "【本章角色可用性硬约束】",
            "- pov_character 与 participating_characters 只能使用“直接可出场角色”的标准名称；别名只用于识别，最终字段不得输出别名。",
            "- 仅可提及角色不能说话、行动、进入现场、担任 POV 或参与实时互动；只能作为回忆、传闻、记录、消息、历史影响或离场后果。",
            "- 不可出场角色不得被安排为本章新行动或现场参与；如确需使用，必须触发资源/设定确认，而不是自行改名或强行出场。",
            "- 角色层级以 importance_tier / narrative_weight / story_arc_role 为准，不得只按 role 字段判断主配角。",
        ]
        bucket_titles = [
            ("direct_available_characters", "直接可出场角色"),
            ("mentioned_only_characters", "仅可提及角色"),
            ("unavailable_characters", "不可出场角色"),
        ]
        for key, title in bucket_titles:
            entries = packet.get(key) or []
            if not entries:
                continue
            lines.append(f"{title}：")
            for item in entries:
                aliases = f"；别名：{', '.join(item.get('aliases') or [])}" if item.get("aliases") else ""
                timing = []
                if item.get("debut_chapter") is not None:
                    timing.append(f"首次第{item.get('debut_chapter')}章")
                if item.get("exit_chapter") is not None:
                    timing.append(f"退场第{item.get('exit_chapter')}章")
                timing_text = f"；{'，'.join(timing)}" if timing else ""
                goals = item.get("goals") or []
                goals_text = f"；目标：{' / '.join(str(g) for g in goals)}" if goals else ""
                lines.append(
                    f"- {item.get('name')}（{item.get('hierarchy_label')}; status={item.get('status') or 'unknown'}; "
                    f"presence={','.join(item.get('available_presence_types') or [])}）{aliases}{timing_text}；{item.get('reason')}{goals_text}"
                )
                if item.get("description"):
                    lines.append(f"  简介：{str(item.get('description'))}")
                elif item.get("background_story"):
                    lines.append(f"  背景：{str(item.get('background_story'))}")
        return "\n".join(lines)

    def _outline_text_excerpt(self, outline: ChapterOutline, needle: str) -> str:
        if not needle:
            return outline.summary or outline.title

        chunks = [outline.summary, *outline.chapter_goals, *outline.hooks_planted, *outline.hooks_resolved]
        for scene in outline.scenes:
            chunks.extend([
                scene.title,
                scene.summary,
                scene.conflict_description,
                *scene.key_events,
                *scene.writing_hints,
            ])
        for chunk in chunks:
            text = str(chunk or "").strip()
            if needle in text:
                return text[:500]
        return (outline.summary or outline.title or needle)[:500]

    def _collect_outline_resource_candidates(self, outline: ChapterOutline) -> Dict[str, Set[str]]:
        candidates: Dict[str, Set[str]] = {
            "character": set(),
            "location": set(),
            "lore": set(),
        }

        for name in (outline.character_arcs or {}).keys():
            normalized = self._normalize_resource_name(name)
            if normalized:
                candidates["character"].add(normalized)

        for scene in outline.scenes or []:
            for name in scene.participating_characters or []:
                normalized = self._normalize_resource_name(name)
                if normalized:
                    candidates["character"].add(normalized)
            pov = self._normalize_resource_name(scene.pov_character)
            if pov:
                candidates["character"].add(pov)
            location = self._normalize_resource_name(scene.location)
            if location:
                candidates["location"].add(location)

        return candidates

    def _direct_character_action_detected(self, name: str, text: str) -> bool:
        if not name or not text or name not in text:
            return False
        direct_markers = [
            "说", "问", "答", "喊", "低声", "开口", "回应", "走", "站", "看", "伸手", "转身", "出现", "进入",
            "参与", "攻击", "阻止", "拿起", "推开", "凝视", "命令", "dialogue", "said", "asked", "replied",
        ]
        for marker in direct_markers:
            if re.search(rf"{re.escape(name)}[^。！？\n]{{0,24}}{re.escape(marker)}", text):
                return True
        return False

    def _audit_outline_character_availability(
        self,
        outline: ChapterOutline,
        character_availability_packet: Dict[str, Any],
    ) -> Dict[str, Any]:
        availability_by_name = character_availability_packet.get("availability_by_name") or {}
        canonical_name_map = character_availability_packet.get("canonical_name_map") or {}
        violations: List[Dict[str, Any]] = []

        def resolve(raw_name: Any) -> Tuple[str, Optional[Dict[str, Any]]]:
            normalized = self._normalize_resource_name(raw_name)
            if not normalized:
                return "", None
            canonical = canonical_name_map.get(normalized.lower(), normalized)
            return canonical, availability_by_name.get(canonical.lower())

        def add_violation(raw_name: Any, source_path: str, usage: str, excerpt: str = ""):
            canonical, availability = resolve(raw_name)
            if not canonical or not availability or availability.get("bucket") == "direct_available":
                return
            violations.append({
                "character_name": canonical,
                "source_path": source_path,
                "usage": usage,
                "severity": availability.get("severity") or "blocking",
                "availability_bucket": availability.get("bucket"),
                "reason": availability.get("reason"),
                "source_excerpt": excerpt[:300] if excerpt else self._outline_text_excerpt(outline, canonical),
                "suggested_fix": "改为直接可出场角色、转换为仅提及形式，或先由用户确认更新角色可用性资料。",
            })

        for name in (outline.character_arcs or {}).keys():
            add_violation(name, "character_arcs", "character_arc")

        for index, scene in enumerate(outline.scenes or []):
            for name in scene.participating_characters or []:
                add_violation(name, f"scenes[{index}].participating_characters", "direct_participation", scene.summary)
            if scene.pov_character:
                add_violation(scene.pov_character, f"scenes[{index}].pov_character", "pov", scene.summary)
            text_chunks = [scene.summary, scene.conflict_description, *scene.key_events, *scene.writing_hints]
            scene_text = "\n".join(str(chunk or "") for chunk in text_chunks)
            for lookup_name, availability in availability_by_name.items():
                if availability.get("bucket") == "direct_available":
                    continue
                canonical = availability.get("name") or lookup_name
                if self._direct_character_action_detected(canonical, scene_text):
                    add_violation(canonical, f"scenes[{index}].text", "direct_action_text", scene_text)

        unique: List[Dict[str, Any]] = []
        seen = set()
        for violation in violations:
            key = (violation.get("character_name"), violation.get("source_path"), violation.get("usage"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(violation)
        return {
            "passed": not unique,
            "violations": unique,
            "violation_count": len(unique),
            "direct_available_names": [item.get("name") for item in character_availability_packet.get("direct_available_characters") or []],
            "mentioned_only_names": [item.get("name") for item in character_availability_packet.get("mentioned_only_characters") or []],
            "unavailable_names": [item.get("name") for item in character_availability_packet.get("unavailable_characters") or []],
        }

    def _apply_character_availability_audit(
        self,
        outline: ChapterOutline,
        character_availability_packet: Dict[str, Any],
    ) -> Dict[str, Any]:
        audit = self._audit_outline_character_availability(outline, character_availability_packet)
        outline.quality_metrics["character_availability_audit"] = audit
        return audit

    def _summarize_character_availability_warnings(self, audit: Dict[str, Any]) -> List[str]:
        warnings = []
        for violation in audit.get("violations") or []:
            warnings.append(
                f"角色可用性阻断：{violation.get('character_name')} 在 {violation.get('source_path')} 被作为{violation.get('usage')}使用，"
                f"但当前为 {violation.get('availability_bucket')}：{violation.get('reason')}"
            )
        return warnings

    async def _get_known_location_names(self, project_id: str) -> Set[str]:
        names: Set[str] = set()
        if not self._db:
            return names

        try:
            if hasattr(self._db, "get_locations"):
                locations = await self._db.get_locations(project_id=project_id, limit=500)
                names.update(self._known_resource_names(locations, ("name", "title")))
        except Exception as e:
            logger.warning(f"[PlotOutline] 获取地点资源失败: {e}")

        try:
            rows = await self._db.execute_query(
                """
                SELECT r.name
                FROM regions r
                JOIN worlds w ON w.id = r.world_id
                WHERE w.project_id = CAST(:project_id AS UUID)
                """,
                {"project_id": project_id},
            )
            names.update(self._known_resource_names(rows, ("name", "title")))
        except Exception as e:
            logger.debug(f"[PlotOutline] 查询区域地点名失败: {e}")

        return names

    def _build_outline_resource_requirements(
        self,
        outline: ChapterOutline,
        full_context: Dict[str, Any],
        known_location_names: Set[str],
    ) -> List[Dict[str, Any]]:
        candidates = self._collect_outline_resource_candidates(outline)
        known_characters = self._known_resource_names(full_context.get("characters", []), ("name",))
        known_lore = self._known_resource_names(full_context.get("world_settings", []), ("title", "name"))
        lore_by_name = {
            str(item.get("title") or item.get("name") or "").strip().lower(): item
            for item in full_context.get("world_settings", [])
            if str(item.get("title") or item.get("name") or "").strip()
        }
        hooks_by_name = {
            str(hook.get("title") or "").strip().lower(): hook
            for bucket in (full_context.get("hooks") or {}).values()
            if isinstance(bucket, list)
            for hook in bucket
            if str(hook.get("title") or "").strip()
        }
        availability_packet = full_context.get("character_availability_packet") or self._build_character_availability_packet(
            full_context.get("characters", []),
            outline.chapter_number,
        )
        availability_by_name = availability_packet.get("availability_by_name") or {}
        canonical_name_map = availability_packet.get("canonical_name_map") or {}
        requirements: List[Dict[str, Any]] = []

        for name in sorted(candidates["character"]):
            canonical_name = canonical_name_map.get(name.lower(), name)
            availability = availability_by_name.get(canonical_name.lower())
            if name.lower() not in known_characters and canonical_name.lower() not in known_characters:
                requirements.append({
                    "project_id": outline.project_id,
                    "outline_id": outline.id,
                    "chapter_num": outline.chapter_number,
                    "requirement_type": "character",
                    "resource_name": name,
                    "severity": "blocking",
                    "status": "pending",
                    "reason": f"第 {outline.chapter_number} 章大纲安排角色“{name}”出场，但项目角色资源中尚未找到同名角色。",
                    "source_excerpt": self._outline_text_excerpt(outline, name),
                    "source_agent": "plot_outline.resource_audit",
                    "source_node_id": "outline_save_audit",
                    "suggested_payload": {
                        "name": name,
                        "role": "supporting",
                        "status": "active",
                        "importance_tier": "supporting",
                        "description": f"由第 {outline.chapter_number} 章大纲资源审计发现，需要用户确认后补全角色档案。",
                    },
                    "metadata": {
                        "audit_type": "outline_save",
                        "audit_basis": "scene.participating_characters/pov_character/character_arcs",
                    },
                })
                continue
            if availability and availability.get("bucket") != "direct_available":
                requirements.append({
                    "project_id": outline.project_id,
                    "outline_id": outline.id,
                    "chapter_num": outline.chapter_number,
                    "requirement_type": "character_availability",
                    "resource_name": canonical_name,
                    "severity": availability.get("severity") or "blocking",
                    "status": "pending",
                    "reason": f"第 {outline.chapter_number} 章大纲安排角色“{canonical_name}”直接出场，但该角色当前为 {availability.get('bucket')}：{availability.get('reason')}",
                    "source_excerpt": self._outline_text_excerpt(outline, canonical_name),
                    "source_agent": "plot_outline.resource_audit",
                    "source_node_id": "outline_save_audit",
                    "suggested_payload": {
                        "name": canonical_name,
                        "resolution_options": [
                            "将直接出场改为回忆/记录/传闻等仅提及形式",
                            "调整本章参与角色或 POV 为直接可出场角色",
                            "如项目资料已过期，由用户确认后更新角色登场/退场/状态/available_presence_types",
                        ],
                    },
                    "metadata": {
                        "audit_type": "outline_save",
                        "audit_basis": "scene.participating_characters/pov_character/character_arcs",
                        "availability_bucket": availability.get("bucket"),
                        "canonical_name": canonical_name,
                    },
                })

        for name in sorted(candidates["location"]):
            lowered = name.lower()
            matched_lore = lore_by_name.get(lowered)
            if lowered in known_location_names or matched_lore:
                if matched_lore and matched_lore.get("id"):
                    requirements.append({
                        "project_id": outline.project_id,
                        "outline_id": outline.id,
                        "chapter_num": outline.chapter_number,
                        "requirement_type": "location",
                        "resource_name": name,
                        "severity": "advisory",
                        "status": "resolved",
                        "reason": f"第 {outline.chapter_number} 章大纲使用地点“{name}”，已自动绑定同名设定资源。",
                        "source_excerpt": self._outline_text_excerpt(outline, name),
                        "source_agent": "plot_outline.resource_audit",
                        "source_node_id": "outline_save_audit",
                        "matched_resource_id": str(matched_lore.get("id")),
                        "matched_resource_type": "lore",
                        "metadata": {
                            "audit_type": "outline_save",
                            "audit_basis": "scene.location",
                            "auto_resolved": True,
                        },
                    })
                continue
            requirements.append({
                "project_id": outline.project_id,
                "outline_id": outline.id,
                "chapter_num": outline.chapter_number,
                "requirement_type": "location",
                "resource_name": name,
                "severity": "advisory",
                "status": "pending",
                "reason": f"第 {outline.chapter_number} 章大纲使用地点“{name}”，但当前地点/设定资源中尚未找到同名资源。",
                "source_excerpt": self._outline_text_excerpt(outline, name),
                "source_agent": "plot_outline.resource_audit",
                "source_node_id": "outline_save_audit",
                "suggested_payload": {
                    "title": name,
                    "name": name,
                    "category": "location",
                    "summary": f"由第 {outline.chapter_number} 章大纲资源审计发现，需要补充地点用途、可见层级和场景限制。",
                    "related_locations": [name],
                },
                "metadata": {
                    "audit_type": "outline_save",
                    "audit_basis": "scene.location",
                },
            })

        lore_keywords = {
            "能力": "ability",
            "秘法": "ability",
            "术式": "ability",
            "法术": "ability",
            "阵法": "ability",
            "仪式": "event_rule",
            "规则": "event_rule",
            "协议": "event_rule",
            "神器": "item",
            "法器": "item",
            "道具": "item",
            "组织": "faction",
            "势力": "faction",
            "伏笔": "hook",
        }
        outline_text = "\n".join([
            outline.title,
            outline.summary,
            *outline.chapter_goals,
            *outline.hooks_planted,
            *outline.hooks_resolved,
            *[scene.summary for scene in outline.scenes],
            *[event for scene in outline.scenes for event in scene.key_events],
        ])
        for keyword, requirement_type in lore_keywords.items():
            if keyword not in outline_text:
                continue
            resource_name = f"第{outline.chapter_number}章{keyword}规则"
            source_excerpt = self._outline_text_excerpt(outline, keyword)
            matched_lore = lore_by_name.get(resource_name.lower())
            if not matched_lore:
                matched_lore = next(
                    (
                        lore_by_name[lore_name]
                        for lore_name in known_lore
                        if lore_name and (lore_name in source_excerpt.lower() or keyword in lore_name)
                    ),
                    None,
                )
            matched_hook = next(
                (
                    hook
                    for hook_title, hook in hooks_by_name.items()
                    if hook_title and (hook_title in source_excerpt.lower() or keyword in hook_title or hook_title in outline_text.lower())
                ),
                None,
            )
            if matched_lore and matched_lore.get("id"):
                requirements.append({
                    "project_id": outline.project_id,
                    "outline_id": outline.id,
                    "chapter_num": outline.chapter_number,
                    "requirement_type": requirement_type,
                    "resource_name": matched_lore.get("title") or resource_name,
                    "severity": "advisory",
                    "status": "resolved",
                    "reason": f"第 {outline.chapter_number} 章大纲涉及“{keyword}”相关剧情，已自动绑定既有设定“{matched_lore.get('title') or resource_name}”。",
                    "source_excerpt": source_excerpt,
                    "source_agent": "plot_outline.resource_audit",
                    "source_node_id": "outline_save_audit",
                    "matched_resource_id": str(matched_lore.get("id")),
                    "matched_resource_type": "lore",
                    "metadata": {
                        "audit_type": "outline_save",
                        "audit_basis": "outline_text_keyword",
                        "keyword": keyword,
                        "auto_resolved": True,
                    },
                })
                continue
            if matched_hook and matched_hook.get("id"):
                requirements.append({
                    "project_id": outline.project_id,
                    "outline_id": outline.id,
                    "chapter_num": outline.chapter_number,
                    "requirement_type": requirement_type,
                    "resource_name": matched_hook.get("title") or resource_name,
                    "severity": "advisory",
                    "status": "resolved",
                    "reason": f"第 {outline.chapter_number} 章大纲涉及“{keyword}”相关剧情，已自动绑定既有伏笔“{matched_hook.get('title') or resource_name}”。",
                    "source_excerpt": source_excerpt,
                    "source_agent": "plot_outline.resource_audit",
                    "source_node_id": "outline_save_audit",
                    "matched_resource_id": str(matched_hook.get("id")),
                    "matched_resource_type": "hook",
                    "metadata": {
                        "audit_type": "outline_save",
                        "audit_basis": "outline_text_keyword",
                        "keyword": keyword,
                        "auto_resolved": True,
                    },
                })
                continue
            requirements.append({
                "project_id": outline.project_id,
                "outline_id": outline.id,
                "chapter_num": outline.chapter_number,
                "requirement_type": requirement_type,
                "resource_name": resource_name,
                "severity": "advisory",
                "status": "pending",
                "reason": f"第 {outline.chapter_number} 章大纲涉及“{keyword}”相关剧情，建议补充或绑定对应设定，避免写作阶段临场发明规则。",
                "source_excerpt": source_excerpt,
                "source_agent": "plot_outline.resource_audit",
                "source_node_id": "outline_save_audit",
                "suggested_payload": {
                    "title": resource_name,
                    "category": requirement_type,
                    "priority": "standard",
                    "content": f"补充第 {outline.chapter_number} 章中“{keyword}”相关剧情的使用边界、限制和与既有设定的关系。",
                },
                "metadata": {
                    "audit_type": "outline_save",
                    "audit_basis": "outline_text_keyword",
                    "keyword": keyword,
                },
            })

        return requirements

    def _requirement_identity(self, requirement: Dict[str, Any]) -> Tuple[str, str, str, str]:
        return (
            str(requirement.get("requirement_type") or "").strip(),
            str(requirement.get("resource_name") or "").strip(),
            str(requirement.get("reason") or "").strip(),
            str(requirement.get("source_node_id") or "").strip(),
        )

    async def _supersede_stale_outline_audit_requirements(
        self,
        outline: ChapterOutline,
        active_requirements: List[Dict[str, Any]],
    ):
        if not self._db or not hasattr(self._db, "execute_query"):
            return

        active_identities = {self._requirement_identity(requirement) for requirement in active_requirements}
        existing_requirements = await self._db.execute_query(
            """
            SELECT id, requirement_type, resource_name, reason, source_node_id, status
            FROM outline_resource_requirements
            WHERE project_id = CAST(:project_id AS UUID)
              AND outline_id = :outline_id
              AND chapter_num = :chapter_num
              AND source_agent = 'plot_outline.resource_audit'
              AND source_node_id = 'outline_save_audit'
              AND status IN ('pending', 'in_progress')
            """,
            {
                "project_id": outline.project_id,
                "outline_id": outline.id,
                "chapter_num": outline.chapter_number,
            },
        )

        stale_ids = [
            str(requirement["id"])
            for requirement in existing_requirements or []
            if self._requirement_identity(requirement) not in active_identities
        ]
        for requirement_id in stale_ids:
            if hasattr(self._db, "update_outline_resource_requirement_status"):
                await self._db.update_outline_resource_requirement_status(
                    requirement_id=requirement_id,
                    status="superseded",
                )
        if stale_ids:
            logger.info(f"[PlotOutline] 已将 {len(stale_ids)} 条过期大纲资源需求标记为 superseded: {outline.id}")

    async def persist_outline_resource_audit(self, outline: ChapterOutline):
        """公开入口：按当前大纲内容重新执行资源审计。"""
        await self._persist_outline_resource_audit(outline)

    async def _persist_outline_resource_audit(self, outline: ChapterOutline):
        """保存或更新大纲后自动审计资源缺口，并刷新章节 readiness。"""
        if not self._db or not hasattr(self._db, "save_outline_resource_requirements"):
            return

        try:
            full_context = await self.get_full_project_context(outline.project_id, outline.chapter_number)
            known_location_names = await self._get_known_location_names(outline.project_id)
            requirements = self._build_outline_resource_requirements(outline, full_context, known_location_names)

            if requirements:
                await self._db.save_outline_resource_requirements(requirements)
                logger.info(f"[PlotOutline] 大纲资源审计写入 {len(requirements)} 条需求: {outline.id}")
            else:
                logger.info(f"[PlotOutline] 大纲资源审计未发现缺口: {outline.id}")

            await self._supersede_stale_outline_audit_requirements(outline, requirements)

            if hasattr(self._db, "update_chapter_resource_readiness"):
                await self._db.update_chapter_resource_readiness(
                    outline.project_id,
                    outline_id=outline.id,
                    chapter_num=outline.chapter_number,
                )
        except Exception as e:
            logger.warning(f"[PlotOutline] 大纲资源自动审计失败: {e}")


    def _outline_saved_response(self, outline: Optional[ChapterOutline]) -> Optional[Dict[str, Any]]:
        if not outline:
            return None
        return self._compact_outline_payload(outline)

    def _outlines_saved_response(self, outlines: List[ChapterOutline]) -> List[Dict[str, Any]]:
        return [self._compact_outline_payload(outline) for outline in outlines]

    def _normalize_emotion_value(self, emotion: Any) -> str:
        """标准化情绪枚举值，兼容模型返回的近义词"""
        if isinstance(emotion, EmotionType):
            return emotion.value

        value = str(emotion or "neutral").strip().lower()
        aliases = {
            "shock": "surprise",
            "shocked": "surprise",
            "astonishment": "surprise",
            "astonished": "surprise",
            "surprised": "surprise",
            "anxious": "fear",
            "anxiety": "fear",
            "panic": "fear",
            "tense": "tension",
            "suspense": "tension",
            "calm": "neutral",
            "peace": "relief",
            "hope": "anticipation",
            "hopeful": "anticipation",
        }
        normalized = aliases.get(value, value)

        try:
            return EmotionType(normalized).value
        except ValueError:
            logger.warning(f"未知情绪类型，回退为 neutral: {emotion}")
            return EmotionType.NEUTRAL.value

    def _normalize_scene_type_value(self, scene_type: Any) -> str:
        if isinstance(scene_type, SceneType):
            return scene_type.value
        value = str(scene_type or "dialogue").strip().lower()
        aliases = {
            "对话": "dialogue",
            "对白": "dialogue",
            "交谈": "dialogue",
            "行动": "action",
            "动作": "action",
            "战斗": "action",
            "追逐": "action",
            "描写": "description",
            "描述": "description",
            "环境": "description",
            "转场": "transition",
            "过渡": "transition",
            "高潮": "climax",
            "决战": "climax",
            "收束": "resolution",
            "解决": "resolution",
            "结局": "resolution",
            "回忆": "flashback",
            "闪回": "flashback",
            "伏笔": "foreshadow",
            "铺垫": "foreshadow",
        }
        normalized = aliases.get(value, value)
        try:
            return SceneType(normalized).value
        except ValueError:
            logger.warning(f"未知场景类型，回退为 dialogue: {scene_type}")
            return SceneType.DIALOGUE.value

    def _normalize_conflict_level_value(self, conflict_level: Any) -> str:
        if isinstance(conflict_level, ConflictLevel):
            return conflict_level.value
        value = str(conflict_level or "low").strip().lower()
        aliases = {
            "低": "low",
            "轻微": "low",
            "弱": "low",
            "中": "medium",
            "中等": "medium",
            "普通": "medium",
            "高": "high",
            "强": "high",
            "激烈": "high",
            "危急": "critical",
            "关键": "critical",
            "致命": "critical",
            "最高": "critical",
        }
        normalized = aliases.get(value, value)
        try:
            return ConflictLevel(normalized).value
        except ValueError:
            logger.warning(f"未知冲突等级，回退为 low: {conflict_level}")
            return ConflictLevel.LOW.value

    def _normalize_scene_payload(self, scene: Dict[str, Any], index: int = 0) -> Dict[str, Any]:
        scene_data = dict(scene)
        scene_data["scene_number"] = scene_data.get("scene_number") or index + 1
        scene_data["title"] = str(scene_data.get("title") or f"场景{index + 1}").strip() or f"场景{index + 1}"
        scene_data["summary"] = str(scene_data.get("summary") or scene_data.get("description") or scene_data["title"]).strip()
        scene_data["scene_type"] = self._normalize_scene_type_value(scene_data.get("scene_type", "dialogue"))
        scene_data["conflict_level"] = self._normalize_conflict_level_value(scene_data.get("conflict_level", "low"))
        scene_data["emotion_start"] = self._normalize_emotion_value(scene_data.get("emotion_start", "neutral"))
        scene_data["emotion_end"] = self._normalize_emotion_value(scene_data.get("emotion_end", "neutral"))
        normalized_arc = []
        for emotion in scene_data.get("emotion_arc") or []:
            normalized_arc.append(self._normalize_emotion_value(emotion))
        scene_data["emotion_arc"] = normalized_arc
        return scene_data

    def _normalize_outline_updates(self, outline_updates: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(outline_updates)

        if "hooks_planted" not in normalized and "hooks_to_plant" in normalized:
            normalized["hooks_planted"] = normalized.get("hooks_to_plant") or []
        if "hooks_resolved" not in normalized and "hooks_to_resolve" in normalized:
            normalized["hooks_resolved"] = normalized.get("hooks_to_resolve") or []

        if normalized.get("emotion_curve"):
            emotion_curve = dict(normalized.get("emotion_curve") or {})
            emotion_curve["dominant_emotion"] = self._normalize_emotion_value(
                emotion_curve.get("dominant_emotion", "neutral")
            )

            normalized_points = []
            for point in emotion_curve.get("points") or []:
                if isinstance(point, dict):
                    point_data = dict(point)
                    point_data["emotion"] = self._normalize_emotion_value(
                        point_data.get("emotion", "neutral")
                    )
                    normalized_points.append(point_data)
                else:
                    normalized_points.append(point)
            emotion_curve["points"] = normalized_points
            normalized["emotion_curve"] = emotion_curve

        normalized_scenes = []
        for i, scene in enumerate(normalized.get("scenes") or []):
            if isinstance(scene, dict):
                normalized_scenes.append(self._normalize_scene_payload(scene, i))
            else:
                normalized_scenes.append(scene)
        if "scenes" in normalized:
            normalized["scenes"] = normalized_scenes

        if "chapters" in normalized:
            normalized_chapters = []
            for chapter in normalized.get("chapters") or []:
                chapter_data = dict(chapter)
                if "hooks_planted" not in chapter_data and "hooks_to_plant" in chapter_data:
                    chapter_data["hooks_planted"] = chapter_data.get("hooks_to_plant") or []
                if "hooks_resolved" not in chapter_data and "hooks_to_resolve" in chapter_data:
                    chapter_data["hooks_resolved"] = chapter_data.get("hooks_to_resolve") or []

                normalized_chapter_scenes = []
                for i, scene in enumerate(chapter_data.get("scenes") or []):
                    if isinstance(scene, dict):
                        normalized_chapter_scenes.append(self._normalize_scene_payload(scene, i))
                    else:
                        normalized_chapter_scenes.append(scene)
                if "scenes" in chapter_data:
                    chapter_data["scenes"] = normalized_chapter_scenes

                if chapter_data.get("emotion_curve"):
                    chapter_curve = dict(chapter_data.get("emotion_curve") or {})
                    chapter_curve["dominant_emotion"] = self._normalize_emotion_value(
                        chapter_curve.get("dominant_emotion", "neutral")
                    )
                    chapter_points = []
                    for point in chapter_curve.get("points") or []:
                        if isinstance(point, dict):
                            point_data = dict(point)
                            point_data["emotion"] = self._normalize_emotion_value(
                                point_data.get("emotion", "neutral")
                            )
                            chapter_points.append(point_data)
                        else:
                            chapter_points.append(point)
                    chapter_curve["points"] = chapter_points
                    chapter_data["emotion_curve"] = chapter_curve

                normalized_chapters.append(chapter_data)
            normalized["chapters"] = normalized_chapters

        return normalized

    def _has_consistency_risk(self, consistency: Dict[str, Any]) -> bool:
        return bool(consistency.get("conflicts") or consistency.get("risk_areas"))

    def _select_outline_payload(self, data: Dict[str, Any], chapter_number: int) -> Dict[str, Any]:
        if "chapters" not in data:
            return data

        chapters = data.get("chapters") or []
        if not chapters:
            return {}

        for chapter in chapters:
            if chapter.get("chapter_number") == chapter_number:
                return chapter
        return chapters[0]

    def _summarize_consistency_warnings(self, consistency: Dict[str, Any]) -> List[str]:
        warnings: List[str] = []
        for item in consistency.get("conflicts", []):
            warnings.append(f"设定冲突风险：{item}")
        for item in consistency.get("risk_areas", []):
            warnings.append(f"设定风险：{item}")
        return warnings

    async def _save_outline_updates(
        self,
        project_id: str,
        default_chapter_number: int,
        outline_updates: Dict[str, Any],
    ) -> tuple[Optional[ChapterOutline], List[ChapterOutline]]:
        saved_outline: Optional[ChapterOutline] = None
        saved_outlines: List[ChapterOutline] = []
        outline_updates = self._normalize_outline_updates(outline_updates)

        if "chapters" in outline_updates:
            for chapter_data in outline_updates["chapters"]:
                ch_num = chapter_data.get("chapter_number") or default_chapter_number
                scenes = self._convert_scenes_data(chapter_data.get("scenes", []))
                existing = await self.get_outline(project_id, ch_num)

                if existing:
                    update_dto = UpdateChapterOutlineDTO(
                        title=chapter_data.get("title", existing.title),
                        summary=chapter_data.get("summary", existing.summary),
                        chapter_goals=chapter_data.get("chapter_goals", existing.chapter_goals),
                        hooks_planted=chapter_data.get("hooks_planted", existing.hooks_planted),
                        hooks_resolved=chapter_data.get("hooks_resolved", existing.hooks_resolved),
                        target_word_count=chapter_data.get("target_word_count", existing.target_word_count),
                    )
                    if scenes:
                        update_dto.scenes = scenes
                    updated = await self.update_outline(existing.id, update_dto)
                    if updated:
                        saved_outlines.append(updated)
                        logger.info(f"更新草稿大纲: 第{ch_num}章")
                else:
                    created = await self.create_outline(CreateChapterOutlineDTO(
                        project_id=project_id,
                        chapter_number=ch_num,
                        title=chapter_data.get("title", f"第{ch_num}章"),
                        summary=chapter_data.get("summary", ""),
                        scenes=scenes,
                        chapter_goals=chapter_data.get("chapter_goals", []),
                        hooks_planted=chapter_data.get("hooks_planted", []),
                        hooks_resolved=chapter_data.get("hooks_resolved", []),
                        target_word_count=chapter_data.get("target_word_count", 3000),
                    ))
                    if created:
                        saved_outlines.append(created)
                        logger.info(f"创建草稿大纲: 第{ch_num}章")

            if saved_outlines:
                self._mark_outline_project_dirty(project_id)
                await self._invalidate_assistant_context_after_outline_mutation(project_id, reason="outline_batch_save")
                saved_outline = saved_outlines[-1]
                logger.info(f"批量保存了 {len(saved_outlines)} 章大纲")
            return saved_outline, saved_outlines

        if (
            self._has_meaningful_outline_content(outline_updates)
            or ("chapters" in outline_updates and bool(outline_updates.get("chapters")))
        ):
            existing = await self.get_outline(project_id, default_chapter_number)
            scenes = self._convert_scenes_data(outline_updates.get("scenes", []))

            if existing:
                update_dto = UpdateChapterOutlineDTO(
                    title=outline_updates.get("title", existing.title),
                    summary=outline_updates.get("summary", existing.summary),
                    chapter_goals=outline_updates.get("chapter_goals", existing.chapter_goals),
                    hooks_planted=outline_updates.get("hooks_planted", existing.hooks_planted),
                    hooks_resolved=outline_updates.get("hooks_resolved", existing.hooks_resolved),
                    target_word_count=outline_updates.get("target_word_count", existing.target_word_count),
                )
                if scenes:
                    update_dto.scenes = scenes
                saved_outline = await self.update_outline(existing.id, update_dto)
                if saved_outline:
                    saved_outlines.append(saved_outline)
                    logger.info(f"更新草稿大纲: 第{default_chapter_number}章")
            else:
                saved_outline = await self.create_outline(CreateChapterOutlineDTO(
                    project_id=project_id,
                    chapter_number=default_chapter_number,
                    title=outline_updates.get("title", f"第{default_chapter_number}章"),
                    summary=outline_updates.get("summary", ""),
                    scenes=scenes,
                    chapter_goals=outline_updates.get("chapter_goals", []),
                    hooks_planted=outline_updates.get("hooks_planted", []),
                    hooks_resolved=outline_updates.get("hooks_resolved", []),
                    target_word_count=outline_updates.get("target_word_count", 3000),
                ))
                if saved_outline:
                    saved_outlines.append(saved_outline)
                    logger.info(f"创建草稿大纲: 第{default_chapter_number}章")

            if saved_outline:
                self._mark_outline_project_dirty(project_id, default_chapter_number)
                await self._invalidate_assistant_context_after_outline_mutation(project_id, reason="outline_chat_save")

        return saved_outline, saved_outlines

    def _mark_outline_project_dirty(self, project_id: str, chapter_number: Optional[int] = None):
        self._loaded_outline_projects.discard(project_id)
        self._invalidate_project_caches(project_id, chapter_number)

    async def _invalidate_assistant_context_after_outline_mutation(
        self,
        project_id: str,
        *,
        reason: str,
        force_rebuild: bool = False,
        request_id: Optional[str] = None,
    ) -> None:
        """Mark Assistant Context snapshots stale after outline mutations.

        Outline snapshot sections are reused by default. A delta alone is not
        enough because the same packet can still include an older outline section
        that contradicts the delta, so every outline mutation invalidates the
        project snapshot. Destructive operations can force an immediate rebuild.
        """
        if not self._db:
            return
        try:
            from app.services.assistant_context import get_assistant_context_fabric

            fabric = get_assistant_context_fabric(self._db)
            await self._db.mark_assistant_snapshots_stale(project_id)
            if force_rebuild:
                await fabric.snapshots.force_rebuild(project_id, request_id=request_id)
        except Exception:
            logger.warning("大纲变更后刷新 Assistant Context 失败: %s", reason, exc_info=True)

    async def _record_outline_delta(
        self,
        *,
        project_id: str,
        outline: ChapterOutline,
        operation: str,
        before: Optional[Dict[str, Any]] = None,
        source_table: str = "chapter_outlines",
    ) -> None:
        if not self._db:
            return
        try:
            from app.services.assistant_context import get_assistant_context_fabric

            await get_assistant_context_fabric(self._db).deltas.record_entity_change(
                project_id=project_id,
                entity_type="chapter_outline",
                entity_id=outline.id,
                operation=operation,
                before=before,
                after=outline.model_dump(mode="json"),
                payload_summary={
                    "title": outline.title,
                    "chapter_number": outline.chapter_number,
                    "status": outline.status.value if hasattr(outline.status, "value") else str(outline.status),
                },
                source_table=source_table,
                source_updated_at=outline.updated_at,
            )
        except Exception:
            logger.warning("记录 Assistant Context 大纲 delta 失败", exc_info=True)

    def invalidate_project_context(self, project_id: str):
        """清理指定项目的 Plot Outline 上下文缓存"""
        self._invalidate_project_caches(project_id)

    def _row_to_outline(self, row: Dict) -> ChapterOutline:
        """将数据库行转换为章节大纲对象"""
        # 处理 JSON 字段（可能已经是 dict/list，也可能需要 json.loads）
        def parse_json(value, default=None):
            if value is None:
                return default
            if isinstance(value, (dict, list)):
                return value
            if isinstance(value, str):
                return json.loads(value)
            return default

        return ChapterOutline(
            id=row['id'],
            project_id=row['project_id'],
            chapter_number=row['chapter_number'],
            title=row['title'],
            summary=row['summary'],
            status=ChapterOutlineStatus(row['status']),
            scenes=[SceneOutline(**s) for s in parse_json(row.get('scenes'), [])],
            emotion_curve=None,  # 暂时跳过，数据库格式与模型不匹配
            # emotion_curve=EmotionCurve(**parse_json(row.get('emotion_curve'), {})) if row.get('emotion_curve') else None,
            chapter_goals=parse_json(row.get('chapter_goals'), []),
            plot_advancement=row.get('plot_advancement'),
            character_arcs=parse_json(row.get('character_arcs'), {}),
            hooks_planted=parse_json(row.get('hooks_planted'), []),
            hooks_resolved=parse_json(row.get('hooks_resolved'), []),
            quality_metrics=parse_json(row.get('quality_metrics'), {}),
            target_word_count=row.get('target_word_count', 3000),
            estimated_word_count=row.get('estimated_word_count', 0),
            created_at=row.get('created_at', datetime.now()),
            updated_at=row.get('updated_at', datetime.now()),
            approved_at=row.get('approved_at'),
            approved_by=row.get('approved_by'),
            previous_outline_id=row.get('previous_outline_id'),
            next_outline_id=row.get('next_outline_id'),
            deleted_at=row.get('deleted_at'),
        )

    async def create_outline(self, dto: CreateChapterOutlineDTO) -> ChapterOutline:
        """
        创建章节大纲

        Args:
            dto: 创建请求

        Returns:
            ChapterOutline: 创建的大纲
        """
        outline = ChapterOutline(
            id=f"outline_{uuid.uuid4().hex[:8]}",
            project_id=dto.project_id,
            chapter_number=dto.chapter_number,
            title=dto.title,
            summary=dto.summary,
            scenes=dto.scenes or [],
            chapter_goals=dto.chapter_goals,
            hooks_planted=dto.hooks_planted or [],
            hooks_resolved=dto.hooks_resolved or [],
            target_word_count=dto.target_word_count,
        )

        # 保存到数据库
        if self._db:
            try:
                await self._db.execute_write(
                    """
                    INSERT INTO chapter_outlines
                    (id, project_id, chapter_number, title, summary, scenes, chapter_goals,
                     hooks_planted, hooks_resolved, target_word_count, status, created_at, updated_at)
                    VALUES (:id, :project_id, :chapter_number, :title, :summary, :scenes, :chapter_goals,
                     :hooks_planted, :hooks_resolved, :target_word_count, :status, :created_at, :updated_at)
                    """,
                    {
                        "id": outline.id,
                        "project_id": outline.project_id,
                        "chapter_number": outline.chapter_number,
                        "title": outline.title,
                        "summary": outline.summary,
                        "scenes": json.dumps(self._to_plain_data(outline.scenes)) if outline.scenes else "[]",
                        "chapter_goals": json.dumps(outline.chapter_goals),
                        "hooks_planted": json.dumps(outline.hooks_planted),
                        "hooks_resolved": json.dumps(outline.hooks_resolved),
                        "target_word_count": outline.target_word_count,
                        "status": outline.status.value,
                        "created_at": outline.created_at,
                        "updated_at": outline.updated_at,
                    }
                )
                logger.info(f"创建章节大纲: {outline.id}")
            except Exception as e:
                logger.error(f"保存章节大纲失败: {e}")

        self._merge_outline_into_list(outline)
        self._mark_outline_project_dirty(outline.project_id, outline.chapter_number)
        await self._record_outline_delta(project_id=outline.project_id, outline=outline, operation="create")
        await self._invalidate_assistant_context_after_outline_mutation(outline.project_id, reason="outline_create")
        await self._persist_outline_resource_audit(outline)
        return outline

    async def get_outline(self, project_id: str, chapter_number: int) -> Optional[ChapterOutline]:
        """
        获取指定章节的大纲。

        章节号路由只返回可作为当前章节基准的版本，避免 approved 和 revision
        同章共存时误把修订提案当成当前可写作版本。
        """
        await self._ensure_cache(project_id)

        chapter_outlines = [
            outline for outline in self._outlines_cache.values()
            if outline.project_id == project_id and outline.chapter_number == chapter_number
        ]
        if not chapter_outlines:
            return None

        status_priority = {
            ChapterOutlineStatus.APPROVED: 0,
            ChapterOutlineStatus.IN_WRITING: 1,
            ChapterOutlineStatus.COMPLETED: 2,
            ChapterOutlineStatus.DRAFT: 3,
            ChapterOutlineStatus.REVISION: 4,
            ChapterOutlineStatus.REJECTED: 5,
        }

        def current_sort_key(outline: ChapterOutline):
            is_superseded_approved = outline.status == ChapterOutlineStatus.APPROVED and bool(outline.next_outline_id)
            effective_priority = 10 if is_superseded_approved else status_priority.get(outline.status, 99)
            recency = outline.approved_at or outline.updated_at or outline.created_at or datetime.min
            return (effective_priority, -recency.timestamp())

        return sorted(chapter_outlines, key=current_sort_key)[0]

    async def get_outline_by_id(self, project_id: str, outline_id: str) -> Optional[ChapterOutline]:
        """按 outline ID 精确获取大纲版本。"""
        await self._ensure_cache(project_id)
        outline = self._outlines_cache.get(outline_id)
        if not outline or outline.project_id != project_id:
            return None
        return outline

    async def get_outline_versions(self, project_id: str, chapter_number: int) -> Dict[str, Any]:
        """获取某章节的所有大纲版本和当前版本摘要。"""
        await self._ensure_cache(project_id)
        versions = sorted(
            [
                outline for outline in self._outlines_cache.values()
                if outline.project_id == project_id and outline.chapter_number == chapter_number
            ],
            key=lambda outline: (outline.created_at, outline.updated_at),
        )
        current_approved_candidates = [
            outline for outline in versions
            if outline.status == ChapterOutlineStatus.APPROVED and not outline.next_outline_id
        ]
        current_approved = sorted(
            current_approved_candidates,
            key=lambda outline: outline.approved_at or outline.updated_at or outline.created_at or datetime.min,
            reverse=True,
        )[0] if current_approved_candidates else None
        pending_revisions = [outline for outline in versions if outline.status == ChapterOutlineStatus.REVISION]
        rejected_revisions = [outline for outline in versions if outline.status == ChapterOutlineStatus.REJECTED]
        return {
            "chapter_number": chapter_number,
            "current_approved": current_approved,
            "pending_revisions": pending_revisions,
            "rejected_revisions": rejected_revisions,
            "versions": versions,
            "total": len(versions),
        }

    async def get_outlines_by_project(self, project_id: str) -> List[ChapterOutline]:
        """
        获取项目的所有章节大纲

        Args:
            project_id: 项目ID

        Returns:
            List[ChapterOutline]: 章节大纲列表
        """
        await self._ensure_cache(project_id)

        outlines = [
            o for o in self._outlines_cache.values()
            if o.project_id == project_id
        ]
        return sorted(outlines, key=lambda x: x.chapter_number)

    async def update_outline(self, outline_id: str, dto: UpdateChapterOutlineDTO) -> Optional[ChapterOutline]:
        """
        更新章节大纲

        Args:
            outline_id: 大纲ID
            dto: 更新请求

        Returns:
            更新后的大纲
        """
        outline = self._outlines_cache.get(outline_id)
        if not outline:
            return None

        if outline.status == ChapterOutlineStatus.APPROVED:
            revision = self._clone_outline_as_revision(outline)
            for key in dto.model_fields_set:
                value = getattr(dto, key)
                if value is not None:
                    setattr(revision, key, value)
            revision.updated_at = datetime.now()

            if self._db:
                try:
                    await self._db.execute_write(
                        """
                        INSERT INTO chapter_outlines
                        (id, project_id, chapter_number, title, summary, scenes, emotion_curve, chapter_goals,
                         status, hooks_planted, hooks_resolved, target_word_count, created_at, updated_at,
                         previous_outline_id)
                        VALUES (:id, :project_id, :chapter_number, :title, :summary, :scenes, :emotion_curve,
                         :chapter_goals, :status, :hooks_planted, :hooks_resolved, :target_word_count,
                         :created_at, :updated_at, :previous_outline_id)
                        """,
                        {
                            "id": revision.id,
                            "project_id": revision.project_id,
                            "chapter_number": revision.chapter_number,
                            "title": revision.title,
                            "summary": revision.summary,
                            "scenes": json.dumps(self._to_plain_data(revision.scenes)),
                            "emotion_curve": json.dumps(self._to_plain_data(revision.emotion_curve)) if revision.emotion_curve else None,
                            "chapter_goals": json.dumps(revision.chapter_goals),
                            "status": revision.status.value,
                            "hooks_planted": json.dumps(revision.hooks_planted),
                            "hooks_resolved": json.dumps(revision.hooks_resolved),
                            "target_word_count": revision.target_word_count,
                            "created_at": revision.created_at,
                            "updated_at": revision.updated_at,
                            "previous_outline_id": revision.previous_outline_id,
                        },
                    )
                    logger.info(f"为已审批大纲创建修订提案: {outline_id} -> {revision.id}")
                except Exception as e:
                    logger.error(f"创建章节大纲修订提案失败: {e}")
                    return None

            self._merge_outline_into_list(revision)
            self._mark_outline_project_dirty(revision.project_id, revision.chapter_number)
            await self._record_outline_delta(
                project_id=revision.project_id,
                outline=revision,
                operation="create",
                before=outline.model_dump(mode="json"),
            )
            await self._invalidate_assistant_context_after_outline_mutation(revision.project_id, reason="outline_revision_create")
            await self._persist_outline_resource_audit(revision)
            return revision

        before_outline = outline.model_dump(mode="json")
        for key in dto.model_fields_set:
            value = getattr(dto, key)
            if value is not None:
                setattr(outline, key, value)

        outline.updated_at = datetime.now()

        # 保存到数据库
        if self._db:
            try:
                await self._db.execute_write(
                    """
                    UPDATE chapter_outlines
                    SET title = :title, summary = :summary, scenes = :scenes, emotion_curve = :emotion_curve,
                        chapter_goals = :chapter_goals, status = :status, hooks_planted = :hooks_planted, hooks_resolved = :hooks_resolved,
                        target_word_count = :target_word_count, updated_at = :updated_at
                    WHERE id = :id
                    """,
                    {
                        "title": outline.title,
                        "summary": outline.summary,
                        "scenes": json.dumps(self._to_plain_data(outline.scenes)),
                        "emotion_curve": json.dumps(self._to_plain_data(outline.emotion_curve)) if outline.emotion_curve else None,
                        "chapter_goals": json.dumps(outline.chapter_goals),
                        "status": outline.status.value,
                        "hooks_planted": json.dumps(outline.hooks_planted),
                        "hooks_resolved": json.dumps(outline.hooks_resolved),
                        "target_word_count": outline.target_word_count,
                        "updated_at": outline.updated_at,
                        "id": outline_id,
                    }
                )
                logger.info(f"更新章节大纲: {outline_id}")
            except Exception as e:
                logger.error(f"更新章节大纲失败: {e}")

        self._mark_outline_project_dirty(outline.project_id, outline.chapter_number)
        await self._record_outline_delta(
            project_id=outline.project_id,
            outline=outline,
            operation="update",
            before=before_outline,
        )
        await self._invalidate_assistant_context_after_outline_mutation(outline.project_id, reason="outline_update")
        await self._persist_outline_resource_audit(outline)
        return outline

    async def generate_outline(
        self,
        project_id: str,
        chapter_number: int,
        context: Optional[str] = None,
        previous_events: Optional[str] = None,
        characters: Optional[List[Dict]] = None,
        world_info: Optional[Dict] = None,
        existing_hooks: Optional[List[Dict]] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> GenerateOutlineResponse:
        """
        生成章节大纲

        使用 Skill 或 LLM 生成结构化的章节大纲

        Args:
            project_id: 项目ID
            chapter_number: 章节号
            context: 上下文信息
            previous_events: 前文事件
            characters: 角色列表（可选，会自动从数据库获取）
            world_info: 世界观信息（可选，会自动从数据库获取）
            existing_hooks: 已有伏笔（可选，会自动从数据库获取）

        Returns:
            GenerateOutlineResponse: 生成的大纲和建议
        """
        # 判断是否为黄金三章（1-3章）
        is_golden_three = 1 <= chapter_number <= 3

        context_packet = await self._build_outline_context_packet(
            project_id=project_id,
            chapter_number=chapter_number,
            task_type="generate",
            session_id=session_id,
            request_id=request_id,
            user_message=context or previous_events or f"生成第{chapter_number}章大纲",
            extra_scope={"previous_events": bool(previous_events), "special_context": bool(context)},
        )
        context_packet_metadata = self._context_packet_metadata(context_packet)

        # 获取完整项目上下文用于结构化一致性检查和资源名映射；LLM prompt 的权威项目上下文来自 Assistant Context Fabric packet
        full_context = await self.get_full_project_context(project_id, chapter_number)

        # 如果调用者没有提供特定信息，使用自动获取的上下文
        if not characters:
            characters = full_context.get("characters", [])
        character_availability_packet = self._build_character_availability_packet(characters or [], chapter_number)
        full_context["character_availability_packet"] = character_availability_packet
        if not world_info:
            world_info = {
                "name": full_context.get("project", {}).get("title", ""),
                "world_type": full_context.get("project", {}).get("world_type", ""),
                "description": full_context.get("project", {}).get("description", ""),
                "settings": full_context.get("world_settings", []),
            }
        if not existing_hooks:
            hooks_data = full_context.get("hooks", {})
            existing_hooks = hooks_data.get("pending", []) + hooks_data.get("to_resolve", [])

        # 构建生成 Prompt
        prompt = self._build_generation_prompt(
            chapter_number=chapter_number,
            context=context,
            previous_events=previous_events,
            characters=characters,
            world_info=world_info,
            existing_hooks=existing_hooks,
            full_context=full_context,
            context_packet=context_packet,
        )

        # 尝试使用 Skill
        if self._skill_service:
            try:
                from app.services.skill_service import ExecuteSkillDTO
                result = await self._skill_service.execute_skill(ExecuteSkillDTO(
                    skill_id="skill_chapter_outline_generation",
                    project_id=project_id,
                    parameters={
                        "prompt": prompt,
                        "chapter_number": chapter_number,
                        "story_context": context_packet.get("prompt_context") if context_packet else self.format_context_for_prompt(full_context),
                        "character_availability_packet": character_availability_packet,
                        "is_golden_three": is_golden_three,
                    }
                ))
                if result.success:
                    data = self._require_structured_dict(result, "解析章节大纲生成结果失败")
                    outline = self._parse_generated_outline(project_id, chapter_number, self._select_outline_payload(data, chapter_number))
                    availability_audit = self._apply_character_availability_audit(outline, character_availability_packet)
                    consistency = await self._check_outline_setting_consistency(project_id, data, full_context)
                    warnings = list(data.get("warnings", []))
                    warnings.extend(self._summarize_consistency_warnings(consistency))
                    warnings.extend(self._summarize_character_availability_warnings(availability_audit))
                    return GenerateOutlineResponse(
                        outline=outline,
                        suggestions=data.get("suggestions", []),
                        warnings=warnings,
                        prompt_render_trace=outline.quality_metrics.get("prompt_render_trace"),
                        context_packet=context_packet_metadata,
                    )
            except Exception as e:
                logger.warning(f"使用 Skill 生成大纲失败，fallback 到直接生成: {e}")

        # 直接生成（fallback）
        outline = await self._generate_outline_direct(
            project_id=project_id,
            chapter_number=chapter_number,
            prompt=prompt,
            full_context=full_context,
            context_packet=context_packet,
        )
        availability_audit = self._apply_character_availability_audit(outline, character_availability_packet)

        return GenerateOutlineResponse(
            outline=outline,
            suggestions=["大纲已生成，建议人工审核后使用"],
            warnings=self._summarize_character_availability_warnings(availability_audit),
            prompt_render_trace=outline.quality_metrics.get("prompt_render_trace"),
            context_packet=context_packet_metadata,
        )

    def _build_generation_prompt(
        self,
        chapter_number: int,
        context: Optional[str],
        previous_events: Optional[str],
        characters: Optional[List[Dict]],
        world_info: Optional[Dict],
        existing_hooks: Optional[List[Dict]],
        full_context: Optional[Dict[str, Any]] = None,
        context_packet: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建大纲生成 Prompt，稳定输出合同来自 md prompt 资产。"""
        output_format_prompt = self._get_output_format_prompt()
        prompt_parts = [
            f"请为第 {chapter_number} 章生成详细的章节大纲。",
            "",
        ]

        if context_packet:
            prompt_parts.append(context_packet.get("prompt_context") or "")
        elif full_context:
            context_str = self.format_context_for_prompt(full_context)
            if context_str:
                prompt_parts.append(context_str)

        availability_text = self._format_character_availability_packet(
            (full_context or {}).get("character_availability_packet") or self._build_character_availability_packet(characters or [], chapter_number)
        )
        if availability_text:
            prompt_parts.append(availability_text)
            prompt_parts.append("")

        if world_info:
            prompt_parts.append("【世界观设定】")
            prompt_parts.append(f"名称: {world_info.get('name', '未知')}")
            prompt_parts.append(f"类型: {world_info.get('world_type', '奇幻')}")
            if world_info.get('description'):
                desc = world_info.get('description') or ''
                prompt_parts.append(f"描述: {desc}")
            if world_info.get('settings'):
                constitutional_settings = [s for s in world_info['settings'] if s.get('priority') == 'constitutional']
                core_settings = [s for s in world_info['settings'] if s.get('priority') == 'core']
                other_settings = [s for s in world_info['settings'] if s.get('priority') not in {'constitutional', 'core'}]

                if constitutional_settings:
                    prompt_parts.append("\n【宪法级设定 - 不可违反】")
                    for setting in constitutional_settings:
                        summary = setting.get('summary') or ''
                        prompt_parts.append(f"- {setting.get('title', '')}: {summary}")

                if core_settings:
                    prompt_parts.append("\n【核心设定】")
                    for setting in core_settings:
                        summary = setting.get('summary') or ''
                        prompt_parts.append(f"- {setting.get('title', '')}: {summary}")

                if other_settings:
                    prompt_parts.append("\n【相关设定】")
                    for setting in other_settings:
                        summary = setting.get('summary') or ''
                        prompt_parts.append(f"- {setting.get('title', '')}: {summary}")
            prompt_parts.append("")

        if characters:
            prompt_parts.append("【主要角色身份与层级】")
            for char in characters:
                name = char.get('name', '未知')
                prompt_parts.append(f"- {name} ({self._character_label(char)})")
                if char.get("description"):
                    prompt_parts.append(f"  简介：{str(char.get('description'))}")
                if char.get("personality"):
                    prompt_parts.append(f"  性格：{str(char.get('personality'))}")
                goals = self._as_list(char.get("goals"))
                if goals:
                    prompt_parts.append(f"  目标：{' / '.join(str(goal) for goal in goals)}")
            prompt_parts.append("")

        if previous_events:
            prompt_parts.append("【前文事件概要】")
            prompt_parts.append(previous_events)
            prompt_parts.append("")

        if existing_hooks:
            prompt_parts.append("【待回收伏笔】")
            for hook in existing_hooks:
                title = hook.get('title', '未知伏笔')
                desc = hook.get('description') or ''
                prompt_parts.append(f"- {title}: {desc}")
            prompt_parts.append("")

        if context:
            prompt_parts.append("【额外上下文】")
            prompt_parts.append(context)
            prompt_parts.append("")

        prompt_parts.append("【输出格式要求】")
        prompt_parts.append(output_format_prompt)
        return "\n".join(prompt_parts)

    def _parse_generated_outline(
        self,
        project_id: str,
        chapter_number: int,
        data: Dict
    ) -> ChapterOutline:
        """解析生成的大纲数据"""
        scenes = []
        for s in data.get("scenes", []):
            scene = SceneOutline(
                id=f"scene_{uuid.uuid4().hex[:8]}",
                scene_number=s.get("scene_number", len(scenes) + 1),
                title=s.get("title", f"场景{len(scenes) + 1}"),
                scene_type=SceneType(s.get("scene_type", "dialogue")),
                summary=s.get("summary", ""),
                participating_characters=s.get("participating_characters", []),
                pov_character=s.get("pov_character"),
                location=s.get("location"),
                time_of_day=s.get("time_of_day"),
                emotion_start=EmotionType(self._normalize_emotion_value(s.get("emotion_start", "neutral"))),
                emotion_end=EmotionType(self._normalize_emotion_value(s.get("emotion_end", "neutral"))),
                conflict_level=ConflictLevel(s.get("conflict_level", "low")),
                conflict_description=s.get("conflict_description"),
                estimated_words=s.get("estimated_words", 500),
                key_events=s.get("key_events", []),
                writing_hints=s.get("writing_hints", []),
            )
            scenes.append(scene)

        emotion_curve = None
        if data.get("emotion_curve"):
            ec = data["emotion_curve"]
            points = [
                EmotionPoint(
                    position=p.get("position", i / max(len(ec.get("points", [])) - 1, 1)),
                    emotion=EmotionType(self._normalize_emotion_value(p.get("emotion", "neutral"))),
                    intensity=p.get("intensity", 0.5),
                    description=p.get("description"),
                )
                for i, p in enumerate(ec.get("points", []))
            ]
            emotion_curve = EmotionCurve(
                chapter_number=chapter_number,
                points=points,
                dominant_emotion=EmotionType(self._normalize_emotion_value(ec.get("dominant_emotion", "neutral"))),
            )

        return ChapterOutline(
            id=f"outline_{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            chapter_number=chapter_number,
            title=data.get("title", f"第{chapter_number}章"),
            summary=data.get("summary", ""),
            scenes=scenes,
            emotion_curve=emotion_curve,
            chapter_goals=data.get("chapter_goals", []),
            hooks_planted=data.get("hooks_to_plant", []),
            hooks_resolved=data.get("hooks_to_resolve", []),
            target_word_count=sum(s.estimated_words for s in scenes) or 3000,
            writing_guide=data.get("writing_guide"),
        )

    async def _generate_outline_direct(
        self,
        project_id: str,
        chapter_number: int,
        prompt: str,
        full_context: Optional[Dict[str, Any]] = None,
        context_packet: Optional[Dict[str, Any]] = None,
    ) -> ChapterOutline:
        """直接调用 LLM 生成大纲（Skill 失败时的 fallback）"""
        from app.config import settings

        # 从数据库加载 prompt 模板
        try:
            from app.services.agent_prompt_service import get_agent_prompt_service
            prompt_service = get_agent_prompt_service()
            prompt_data = await prompt_service.build_agent_prompt_with_trace(
                agent_type="plot_outline",
                project_id=project_id,
                include_skills=True,
                scenario="generate_chapter_outline",
            )
            system_prompt = prompt_data.get("content", "")
            prompt_render_trace = prompt_data.get("trace", {}) or {}
        except Exception as e:
            logger.warning(f"加载 plot_outline prompt 模板失败: {e}")
            fallback_data = self._build_fallback_prompt_with_trace(project_id)
            system_prompt = fallback_data["content"]
            prompt_render_trace = fallback_data["trace"]

        try:
            llm_config = settings.get_llm_config(settings.llm_provider)
            response = await self._call_llm_for_chat(
                system_prompt=system_prompt,
                user_message=prompt,
                context=context_packet.get("prompt_context") if context_packet else "",
                llm_config=llm_config,
            )

            outline_updates = self._try_parse_outline_updates(response)
            if not outline_updates:
                raise ValueError("未能从 LLM 响应中解析出大纲 JSON")

            outline_updates = self._normalize_outline_updates(outline_updates)
            if full_context:
                consistency = await self._check_outline_setting_consistency(project_id, outline_updates, full_context)
                if self._has_consistency_risk(consistency):
                    repaired_updates = await self._repair_outline_with_consistency_feedback(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        message=prompt,
                        full_context=full_context,
                        system_prompt=system_prompt,
                        combined_context=context_packet.get("prompt_context") if context_packet else "",
                        llm_config=llm_config,
                        consistency=consistency,
                    )
                    if repaired_updates:
                        outline_updates = self._normalize_outline_updates(repaired_updates)

            outline = self._parse_generated_outline(
                project_id,
                chapter_number,
                self._select_outline_payload(outline_updates, chapter_number),
            )
            outline.quality_metrics["prompt_render_trace"] = prompt_render_trace
            return outline
        except Exception as e:
            logger.error(f"直接生成大纲失败: {e}")
            # 最终 fallback：返回基本模板
            return ChapterOutline(
                id=f"outline_{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                chapter_number=chapter_number,
                title=f"第{chapter_number}章",
                summary="待填写",
                scenes=[],
                chapter_goals=["推进剧情"],
                target_word_count=3000,
            )

    async def validate_outline(
        self,
        project_id: str,
        outline: ChapterOutline,
    ) -> ValidateOutlineResponse:
        """
        验证章节大纲

        检查大纲的完整性、逻辑性和可行性

        Args:
            project_id: 项目ID
            outline: 待验证的大纲

        Returns:
            ValidateOutlineResponse: 验证结果
        """
        issues = []
        suggestions = []
        score = 1.0

        # 检查基本信息
        if not outline.title or len(outline.title) < 2:
            issues.append({
                "type": "error",
                "field": "title",
                "message": "章节标题过短或缺失",
            })
            score -= 0.1

        if not outline.summary or len(outline.summary) < 50:
            issues.append({
                "type": "warning",
                "field": "summary",
                "message": "章节摘要过短，建议至少50字",
            })
            score -= 0.05

        # 检查场景规划
        if not outline.scenes:
            issues.append({
                "type": "warning",
                "field": "scenes",
                "message": "未规划具体场景",
            })
            score -= 0.15
            suggestions.append("建议为章节规划至少2-3个场景")
        else:
            # 检查场景完整性
            for i, scene in enumerate(outline.scenes):
                if not scene.summary:
                    issues.append({
                        "type": "warning",
                        "field": f"scenes[{i}].summary",
                        "message": f"场景{i+1}缺少摘要",
                    })
                    score -= 0.02

                if not scene.participating_characters:
                    suggestions.append(f"场景{i+1}未指定参与角色")

            # 检查情绪曲线连贯性
            if outline.emotion_curve:
                emotions = [p.emotion for p in outline.emotion_curve.points]
                if len(emotions) > 1:
                    # 检查情绪变化是否合理
                    for i in range(1, len(emotions)):
                        # 从恐惧直接跳到喜悦可能不合理
                        if emotions[i-1] == EmotionType.FEAR and emotions[i] == EmotionType.JOY:
                            suggestions.append(f"情绪从恐惧直接跳到喜悦可能需要过渡")

        # 检查章节目标
        if not outline.chapter_goals:
            issues.append({
                "type": "info",
                "field": "chapter_goals",
                "message": "未设定章节目标",
            })
            suggestions.append("建议设定1-3个明确的章节目标")
            score -= 0.05

        # 检查字数规划
        total_scene_words = sum(s.estimated_words for s in outline.scenes)
        if total_scene_words > 0 and abs(total_scene_words - outline.target_word_count) > 500:
            suggestions.append(
                f"场景预估字数({total_scene_words})与目标字数({outline.target_word_count})差异较大"
            )

        # 使用 Skill 进行深度验证
        if self._skill_service:
            try:
                from app.services.skill_service import ExecuteSkillDTO
                result = await self._skill_service.execute_skill(ExecuteSkillDTO(
                    skill_id="skill_chapter_outline_validation",
                    project_id=project_id,
                    parameters={
                        "outline": self._to_plain_data(outline),
                    }
                ))
                if result.success:
                    data = self._require_structured_dict(result, "解析章节大纲验证结果失败")
                    # 合并 Skill 返回的问题
                    issues.extend(data.get("issues", []))
                    suggestions.extend(data.get("suggestions", []))
                    score = min(score, data.get("score", score))
            except Exception as e:
                logger.warning(f"使用 Skill 验证大纲失败: {e}")

        return ValidateOutlineResponse(
            valid=len([i for i in issues if i.get("type") == "error"]) == 0,
            issues=issues,
            suggestions=suggestions,
            score=max(0, score),
        )

    async def delete_outline(self, outline_id: str, soft_delete_generated_chapters: bool = False) -> Dict[str, Any]:
        """
        删除章节大纲，默认保留已生成正文。

        Args:
            outline_id: 大纲ID
            soft_delete_generated_chapters: 是否同步软删除该大纲生成的章节

        Returns:
            Dict: 删除结果
        """
        outline = self._outlines_cache.get(outline_id)
        soft_deleted_chapters = 0

        if self._db and not outline:
            try:
                rows = await self._db.execute_query(
                    """
                    SELECT * FROM chapter_outlines
                    WHERE id = :id AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    {"id": outline_id},
                )
                if rows:
                    outline = self._row_to_outline(dict(rows[0]))
            except Exception as exc:
                logger.warning("删除大纲前加载版本失败: %s", exc)

        if self._db:
            try:
                if soft_delete_generated_chapters and outline:
                    soft_deleted_chapters = await self._db.soft_delete_chapters_by_outline(
                        outline.project_id,
                        outline_id,
                    )

                await self._db.execute_write(
                    """
                    UPDATE chapter_outlines
                    SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id AND deleted_at IS NULL
                    """,
                    {"id": outline_id}
                )
                logger.info(f"软删除章节大纲: {outline_id}，软删除关联章节: {soft_deleted_chapters}")
            except Exception as e:
                logger.error(f"删除章节大纲失败: {e}")
                return {"success": False, "soft_deleted_chapters": soft_deleted_chapters}

        if outline_id in self._outlines_cache:
            del self._outlines_cache[outline_id]

        if outline:
            self._mark_outline_project_dirty(outline.project_id, outline.chapter_number)
            await self._record_outline_delta(
                project_id=outline.project_id,
                outline=outline,
                operation="delete",
                before=outline.model_dump(mode="json"),
            )
            await self._invalidate_assistant_context_after_outline_mutation(
                outline.project_id,
                reason="outline_delete",
                force_rebuild=True,
            )

        return {"success": True, "soft_deleted_chapters": soft_deleted_chapters}

    async def approve_outline(self, outline_id: str, approved_by: str) -> Optional[ChapterOutline]:
        """
        审批章节大纲

        Args:
            outline_id: 大纲ID
            approved_by: 审批人

        Returns:
            更新后的大纲
        """
        outline = self._outlines_cache.get(outline_id)
        if not outline:
            return None
        if outline.status == ChapterOutlineStatus.REJECTED:
            return None

        before_outline = outline.model_dump(mode="json")
        previous_outline_id = outline.previous_outline_id
        outline.status = ChapterOutlineStatus.APPROVED
        outline.approved_at = datetime.now()
        outline.approved_by = approved_by
        outline.updated_at = datetime.now()

        if self._db:
            try:
                await self._db.execute_write(
                    """
                    UPDATE chapter_outlines
                    SET status = :status, approved_at = :approved_at,
                        approved_by = :approved_by, updated_at = :updated_at
                    WHERE id = :id
                    """,
                    {
                        "status": outline.status.value,
                        "approved_at": outline.approved_at,
                        "approved_by": outline.approved_by,
                        "updated_at": outline.updated_at,
                        "id": outline_id,
                    }
                )
                if previous_outline_id:
                    await self._db.execute_write(
                        """
                        UPDATE chapter_outlines
                        SET next_outline_id = :next_outline_id, updated_at = :updated_at
                        WHERE id = :id
                        """,
                        {
                            "next_outline_id": outline.id,
                            "updated_at": outline.updated_at,
                            "id": previous_outline_id,
                        },
                    )
                logger.info(f"审批章节大纲: {outline_id}")
            except Exception as e:
                logger.error(f"审批章节大纲失败: {e}")
                return None

        if previous_outline_id and previous_outline_id in self._outlines_cache:
            previous_outline = self._outlines_cache[previous_outline_id]
            previous_outline.next_outline_id = outline.id
            previous_outline.updated_at = outline.updated_at

        self._mark_outline_project_dirty(outline.project_id, outline.chapter_number)
        await self._record_outline_delta(
            project_id=outline.project_id,
            outline=outline,
            operation="update",
            before=before_outline,
        )
        await self._invalidate_assistant_context_after_outline_mutation(outline.project_id, reason="outline_approve", force_rebuild=True)
        await self._persist_outline_resource_audit(outline)
        return outline

    async def reject_outline_revision(self, outline_id: str) -> Optional[ChapterOutline]:
        """拒绝修订提案，保留原 approved 版本不变。"""
        outline = self._outlines_cache.get(outline_id)
        if not outline or outline.status != ChapterOutlineStatus.REVISION:
            return None

        before_outline = outline.model_dump(mode="json")
        outline.status = ChapterOutlineStatus.REJECTED
        outline.updated_at = datetime.now()

        if self._db:
            try:
                await self._db.execute_write(
                    """
                    UPDATE chapter_outlines
                    SET status = :status, updated_at = :updated_at
                    WHERE id = :id
                    """,
                    {
                        "status": outline.status.value,
                        "updated_at": outline.updated_at,
                        "id": outline_id,
                    },
                )
                logger.info(f"拒绝章节大纲修订提案: {outline_id}")
            except Exception as e:
                logger.error(f"拒绝章节大纲修订提案失败: {e}")
                return None

        self._mark_outline_project_dirty(outline.project_id, outline.chapter_number)
        await self._record_outline_delta(
            project_id=outline.project_id,
            outline=outline,
            operation="update",
            before=before_outline,
        )
        await self._invalidate_assistant_context_after_outline_mutation(outline.project_id, reason="outline_reject")
        return outline

    async def get_outline_statistics(self, project_id: str) -> Dict[str, Any]:
        """
        获取项目大纲统计

        Args:
            project_id: 项目ID

        Returns:
            Dict: 统计数据
        """
        outlines = await self.get_outlines_by_project(project_id)

        total_words = sum(o.target_word_count for o in outlines)
        status_counts = {}
        for o in outlines:
            status = o.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_outlines": len(outlines),
            "total_target_words": total_words,
            "status_distribution": status_counts,
            "average_scenes_per_chapter": sum(len(o.scenes) for o in outlines) / max(len(outlines), 1),
            "hooks_planned": sum(len(o.hooks_planted) for o in outlines),
            "hooks_resolved": sum(len(o.hooks_resolved) for o in outlines),
        }

    async def get_full_project_context(
        self,
        project_id: str,
        chapter_number: int,
    ) -> Dict[str, Any]:
        """
        获取项目完整上下文信息，用于大纲生成

        包括：角色信息、世界设定、伏笔状态、前文大纲、项目元数据

        Args:
            project_id: 项目ID
            chapter_number: 当前章节号

        Returns:
            Dict: 完整上下文信息
        """
        context = {
            "project": {},
            "characters": [],
            "constitutional_rules": [],
            "core_settings": [],
            "relevant_settings": [],
            "world_settings": [],
            "hooks": {"to_plant": [], "to_resolve": [], "pending": []},
            "previous_outlines": [],
            "current_chapter": chapter_number,
        }

        if not self._db:
            return context

        try:
            # 1. 获取项目元数据
            project = await self._db.get_project(project_id)
            if project:
                metadata = project.get("metadata") or {}
                description = project.get("description") or ""
                context["project"] = {
                    "title": project.get("title", ""),
                    "description": description,
                    "world_type": metadata.get("world_type", ""),
                    "tone": metadata.get("tone", ""),
                }

            # 2. 获取角色信息
            characters = await self._db.execute_query(
                """
                SELECT id, name, aliases, description, role, importance_tier,
                       narrative_weight, story_arc_role, plot_priority, status,
                       debut_chapter, debut_scene, exit_chapter, exit_reason, active_arc,
                       available_presence_types, personality, background_story, goals,
                       relationships, key_relationships, current_region_id, current_location,
                       current_location_reason, death_detail, major_events, appearance, age, gender
                FROM characters
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY
                    CASE importance_tier
                        WHEN 'protagonist' THEN 1
                        WHEN 'co_protagonist' THEN 2
                        WHEN 'deuteragonist' THEN 3
                        WHEN 'mentor' THEN 4
                        WHEN 'love_interest' THEN 5
                        WHEN 'best_friend' THEN 6
                        WHEN 'archenemy' THEN 7
                        WHEN 'major_ally' THEN 8
                        WHEN 'major_antagonist' THEN 9
                        WHEN 'rival' THEN 10
                        WHEN 'family_member' THEN 11
                        ELSE 100
                    END,
                    COALESCE(plot_priority, 999),
                    name
                """,
                {"project_id": project_id}
            )
            for char in characters:
                normalized_char = dict(char)
                normalized_char["aliases"] = self._as_list(normalized_char.get("aliases"))
                normalized_char["goals"] = self._as_list(normalized_char.get("goals"))
                normalized_char["relationships"] = self._as_list(normalized_char.get("relationships"))
                normalized_char["key_relationships"] = self._as_dict(normalized_char.get("key_relationships"))
                normalized_char["available_presence_types"] = sorted(self._character_presence_types(normalized_char))
                normalized_char["death_detail"] = self._as_dict(normalized_char.get("death_detail"))
                normalized_char["major_events"] = self._as_list(normalized_char.get("major_events"))
                normalized_char["background"] = normalized_char.get("background_story") or ""
                normalized_char["importance"] = normalized_char.get("importance_tier") or "npc"
                normalized_char["hierarchy_label"] = self._character_label(normalized_char)
                context["characters"].append(normalized_char)
            context["character_availability_packet"] = self._build_character_availability_packet(context["characters"], chapter_number)

            # 3. 获取世界设定
            lores = await self._db.execute_query(
                """
                SELECT id, title, category, priority, content, summary
                FROM lore_entries
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY
                    CASE priority
                        WHEN 'constitutional' THEN 1
                        WHEN 'core' THEN 2
                        WHEN 'standard' THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                """,
                {"project_id": project_id}
            )
            for lore in lores:
                context["world_settings"].append(
                    self._build_lore_context_entry(
                        lore,
                        summary_limit=1200 if lore.get("priority") == "constitutional" else 800 if lore.get("priority") == "core" else 500,
                    )
                )

            constitutional_rules, core_settings, relevant_settings = self._split_world_settings(context["world_settings"])
            context["constitutional_rules"] = constitutional_rules
            context["core_settings"] = core_settings
            context["relevant_settings"] = relevant_settings

            # 4. 获取伏笔状态
            hooks = await self._db.execute_query(
                """
                SELECT id, title, description, hook_type, status, plant_chapter
                FROM hooks
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY plant_chapter DESC
                """,
                {"project_id": project_id}
            )
            for hook in hooks:
                hook_status = hook.get("status", "planted")
                hook_desc = hook.get("description") or ""
                hook_info = {
                    "id": hook.get("id", ""),
                    "title": hook.get("title", ""),
                    "description": hook_desc,
                    "planted_chapter": hook.get("plant_chapter"),
                }
                if hook_status == "planted":
                    context["hooks"]["pending"].append(hook_info)
                elif hook_status == "hinted":
                    context["hooks"]["to_resolve"].append(hook_info)

            # 5. 获取前文大纲
            if chapter_number > 1:
                prev_outlines = await self.get_outlines_by_project(project_id)
                for outline in prev_outlines:
                    if outline.chapter_number < chapter_number:
                        context["previous_outlines"].append({
                            "chapter_number": outline.chapter_number,
                            "title": outline.title,
                            "summary": outline.summary,
                            "status": outline.status.value,
                        })
                # 保留所有前文大纲

            logger.info(f"获取项目 {project_id} 上下文: {len(context['characters'])} 角色, "
                       f"{len(context['world_settings'])} 设定, {len(hooks)} 伏笔")

        except Exception as e:
            logger.error(f"获取项目上下文失败: {e}")

        return context

    async def get_next_chapter_number(self, project_id: str) -> int:
        """
        自动确定下一章节序号

        优先返回最小的、已有 approved/completed 大纲但正文尚未完成的章节号。
        如果没有可写大纲，再回退到已完成章节最大值 + 1。

        Args:
            project_id: 项目ID

        Returns:
            int: 下一章节序号
        """
        if not self._db:
            logger.warning("数据库连接不存在，使用默认章节号 1")
            return 1

        try:
            try:
                chapters = await self._db.get_chapters_by_project(project_id, status="completed")
                completed_chapter_numbers = {
                    int(c.chapter_number) for c in chapters or []
                    if getattr(c, "chapter_number", None) is not None
                }
            except Exception:
                completed_chapter_numbers = set()

            outline_result = await self._db.execute_query('''
                SELECT chapter_number
                FROM chapter_outlines
                WHERE project_id = :project_id
                  AND status IN ('approved', 'completed')
                  AND deleted_at IS NULL
                  AND next_outline_id IS NULL
                ORDER BY chapter_number ASC
            ''', {"project_id": project_id})

            for row in outline_result or []:
                chapter_number = row.get("chapter_number")
                if chapter_number is None:
                    continue
                chapter_number = int(chapter_number)
                if chapter_number not in completed_chapter_numbers:
                    logger.info(f"项目 {project_id} 下一可写章节序号: {chapter_number}")
                    return chapter_number

            max_chapter = max(completed_chapter_numbers, default=0)
            next_num = max_chapter + 1

            logger.info(f"项目 {project_id} 无待写 approved 大纲，回退下一章节序号: {next_num} (已完成正文最大: {max_chapter})")
            return next_num

        except Exception as e:
            logger.error(f"获取下一章节号失败: {e}，使用默认值 1")
            return 1

    async def get_chapter_outline_for_workflow(
        self,
        project_id: str,
        chapter_number: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        为工作流获取指定章节的大纲

        Args:
            project_id: 项目ID
            chapter_number: 章节号，如果为None则自动获取下一章

        Returns:
            大纲字典，如果不存在则返回None
        """
        # 自动确定章节号
        if chapter_number is None:
            chapter_number = await self.get_next_chapter_number(project_id)

        if not self._db:
            return None

        try:
            result = await self._db.execute_query('''
                SELECT * FROM chapter_outlines
                WHERE project_id = :project_id
                  AND chapter_number = :chapter_num
                  AND status IN ('approved', 'completed')
                  AND deleted_at IS NULL
                  AND next_outline_id IS NULL
                ORDER BY approved_at DESC NULLS LAST, updated_at DESC NULLS LAST, created_at DESC
                LIMIT 1
            ''', {"project_id": project_id, "chapter_num": chapter_number})

            if not result:
                logger.warning(f"第 {chapter_number} 章大纲不存在")
                return None

            outline = dict(result[0])

            # 解析JSON字段
            for field in ['scenes', 'chapter_goals', 'emotion_curve', 'hooks_planted', 'hooks_resolved']:
                if outline.get(field) and isinstance(outline[field], str):
                    import json
                    try:
                        outline[field] = json.loads(outline[field])
                    except:
                        outline[field] = []

            logger.info(f"加载第 {chapter_number} 章大纲: {outline.get('title', '未命名')}")
            return outline

        except Exception as e:
            logger.error(f"加载章节大纲失败: {e}")
            return None

    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        将上下文信息格式化为 Prompt 可用的字符串

        Args:
            context: 上下文字典

        Returns:
            str: 格式化后的上下文字符串
        """
        parts = []

        # 项目信息
        if context.get("project"):
            proj = context["project"]
            parts.append("【作品信息】")
            if proj.get("title"):
                parts.append(f"作品名称：{proj['title']}")
            if proj.get("world_type"):
                parts.append(f"世界类型：{proj['world_type']}")
            if proj.get("tone"):
                parts.append(f"叙事基调：{proj['tone']}")
            if proj.get("description"):
                parts.append(f"作品简介：{proj['description']}")
            parts.append("")

        availability_text = self._format_character_availability_packet(context.get("character_availability_packet") or {})
        if availability_text:
            parts.append(availability_text)
            parts.append("")

        # 角色信息
        if context.get("characters"):
            parts.append("【主要角色身份与层级】")
            for char in context["characters"]:
                name = char.get("name", "未知")
                parts.append(f"- {name} ({self._character_label(char)})")
                aliases = self._as_list(char.get("aliases"))
                if aliases:
                    parts.append(f"  标准名别名：{', '.join(str(alias) for alias in aliases)}；输出字段必须使用标准名“{name}”。")
                lifecycle = []
                if char.get("debut_chapter") is not None:
                    lifecycle.append(f"首次第{char.get('debut_chapter')}章")
                if char.get("exit_chapter") is not None:
                    lifecycle.append(f"退场第{char.get('exit_chapter')}章")
                if char.get("status"):
                    lifecycle.append(f"状态：{char.get('status')}")
                if lifecycle:
                    parts.append(f"  生命周期：{'；'.join(lifecycle)}")
                if char.get("description"):
                    parts.append(f"  简介：{str(char.get('description'))}")
                if char.get("personality"):
                    parts.append(f"  性格：{str(char.get('personality'))}")
                if char.get("background") or char.get("background_story"):
                    parts.append(f"  背景：{str(char.get('background') or char.get('background_story'))}")
                goals = self._as_list(char.get("goals"))
                if goals:
                    parts.append(f"  目标：{' / '.join(str(goal) for goal in goals)}")
                key_relationships = self._as_dict(char.get("key_relationships"))
                if key_relationships:
                    rel_text = "；".join(f"{k}:{v}" for k, v in key_relationships.items())
                    parts.append(f"  关键关系：{rel_text}")
                if char.get("current_location") or char.get("current_region_id"):
                    parts.append(f"  当前位置：{char.get('current_location') or char.get('current_region_id')}；原因：{char.get('current_location_reason') or '未说明'}")
            parts.append("")

        parts.extend(self._format_lore_section("【宪法级设定 - 不可违反】", context.get("constitutional_rules", []), 1200))
        parts.extend(self._format_lore_section("【核心设定】", context.get("core_settings", []), 800))
        parts.extend(self._format_lore_section("【相关设定】", context.get("relevant_settings", []), 500))

        # 伏笔状态
        hooks = context.get("hooks", {})
        if hooks.get("pending") or hooks.get("to_resolve"):
            parts.append("【伏笔状态】")
            if hooks.get("pending"):
                parts.append("待处理伏笔：")
                for h in hooks["pending"]:
                    parts.append(f"- [{h.get('plant_chapter', '?')}章] {h['title']}")
                    if h.get("description"):
                        parts.append(f"  {h['description']}")
            if hooks.get("to_resolve"):
                parts.append("建议回收的伏笔：")
                for h in hooks["to_resolve"]:
                    parts.append(f"- {h['title']}: {h.get('description') or ''}")
            parts.append("")

        # 前文大纲
        if context.get("previous_outlines"):
            parts.append("【前文大纲】")
            for outline in context["previous_outlines"]:
                parts.append(f"第{outline['chapter_number']}章：{outline['title']}")
                if outline.get("summary"):
                    parts.append(f"  {outline['summary']}")
            parts.append("")

        return "\n".join(parts)

    async def chat_with_agent(
        self,
        project_id: str,
        chapter_number: int,
        message: str,
        existing_outline: Optional[ChapterOutline] = None,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        auto_save: bool = False,
    ) -> Dict[str, Any]:
        """
        与 Plot Outline Agent 聊天

        协作生成或修改章节大纲

        Args:
            project_id: 项目ID
            chapter_number: 章节号
            message: 用户消息
            existing_outline: 现有的大纲
            context: 额外上下文

        Returns:
            Dict: 响应结果
        """
        from app.config import settings

        try:
            context_packet = await self._build_outline_context_packet(
                project_id=project_id,
                chapter_number=chapter_number,
                task_type="chat",
                session_id=session_id,
                request_id=request_id,
                user_message=message,
                extra_scope=context or {},
            )
            full_context = await self._get_cached_project_context(project_id, chapter_number)
            packet_context = context_packet.get("prompt_context") if context_packet else ""
            full_formatted_context = self._get_cached_formatted_context(project_id, chapter_number, full_context)
            context_str = self._build_combined_context(packet_context, full_formatted_context) if packet_context else full_formatted_context
            prompt_data = await self._get_cached_system_prompt_with_trace(project_id, chapter_number, full_context)
            base_system_prompt = prompt_data.get("content", "")
            prompt_render_trace = prompt_data.get("trace")
            outline_runtime_context = self._build_outline_runtime_context(existing_outline)
            system_prompt = f"{base_system_prompt}\n\n{outline_runtime_context}".strip()

            system_prompt = f"{system_prompt}\n\n{self._build_chat_response_contract(auto_save=auto_save)}".strip()
            user_context = await self._build_chat_user_context(
                project_id, chapter_number, existing_outline, context
            )
            combined_context = self._build_combined_context(context_str, user_context)

            llm_config = settings.get_llm_config(settings.llm_provider)
            response = await self._call_llm_for_chat(
                system_prompt=system_prompt,
                user_message=message,
                context=combined_context,
                llm_config=llm_config,
            )

            logger.info(f"[PlotOutline] LLM 响应长度: {len(response)} 字符")
            logger.debug(f"[PlotOutline] LLM 响应内容: {response}")

            outline_updates = self._try_parse_outline_updates(response)
            if outline_updates:
                outline_updates = self._normalize_outline_updates(outline_updates)
                outline_updates = self._filter_saveable_outline_updates(outline_updates)
            parse_status = "outline_update" if outline_updates else "no_outline_updates"
            if not outline_updates and self._looks_like_outline_request(message):
                parse_status = "outline_parse_failed"
            logger.info(
                "[PlotOutline] 解析状态: %s outline_keys=%s response_chars=%s",
                parse_status,
                sorted(outline_updates.keys()) if isinstance(outline_updates, dict) else [],
                len(response),
            )

            saved_outline = None
            saved_outlines = []
            consistency_warnings: List[str] = []

            if outline_updates:
                try:
                    consistency = await self._check_outline_setting_consistency(project_id, outline_updates, full_context)
                    if self._has_consistency_risk(consistency):
                        repaired_updates = await self._repair_outline_with_consistency_feedback(
                            project_id=project_id,
                            chapter_number=chapter_number,
                            message=message,
                            full_context=full_context,
                            system_prompt=system_prompt,
                            combined_context=combined_context,
                            llm_config=llm_config,
                            consistency=consistency,
                        )
                        if repaired_updates:
                            outline_updates = self._normalize_outline_updates(repaired_updates)
                            outline_updates = self._filter_saveable_outline_updates(outline_updates)
                            if not outline_updates:
                                parse_status = "outline_parse_failed"
                                consistency = {}
                            else:
                                consistency = await self._check_outline_setting_consistency(project_id, outline_updates, full_context)

                    consistency_warnings = self._summarize_consistency_warnings(consistency)

                    if outline_updates and auto_save:
                        save_started_at = time.perf_counter()
                        saved_outline, saved_outlines = await self._save_outline_updates(
                            project_id=project_id,
                            default_chapter_number=chapter_number,
                            outline_updates=outline_updates,
                        )
                        self._log_timing("auto_save_outline", save_started_at)

                except Exception as e:
                    logger.error(f"自动保存草稿失败: {e}")

            context_packet_metadata = self._context_packet_metadata(context_packet)
            if context_packet and self._db:
                try:
                    await self._append_outline_assistant_response(
                        context_packet=context_packet,
                        response=response,
                        request_id=request_id,
                    )
                except Exception:
                    logger.warning(
                        "Plot Outline assistant 响应落库失败，已继续返回解析结果: session=%s request_id=%s",
                        context_packet.get("session_id"),
                        request_id,
                        exc_info=True,
                    )

            result = {
                "message": response,
                "outline_updates": outline_updates,
                "suggestions": self._extract_suggestions(response),
                "saved_outline": self._outline_saved_response(saved_outline),
                "prompt_render_trace": prompt_render_trace,
                "assistant_session_id": context_packet.get("session_id") if context_packet else None,
                "context_packet": context_packet_metadata,
                "parse_status": parse_status,
            }
            if parse_status == "outline_parse_failed":
                result["warnings"] = [
                    "Agent 回复中没有解析到可保存的大纲 JSON，因此未创建左侧草稿。请让 Agent 按 ```json 代码块输出包含 chapter_number/title/summary/scenes 的单章对象，或 {\"chapters\":[...]} 多章对象。"
                ]
            if outline_updates and not auto_save:
                pending_payload = outline_updates.get("chapters") if isinstance(outline_updates.get("chapters"), list) else [outline_updates]
                result["pending_outlines"] = [dict(item) for item in pending_payload if isinstance(item, dict)]
            if consistency_warnings:
                result["warnings"] = consistency_warnings
            if saved_outlines:
                result["saved_outlines"] = self._outlines_saved_response(saved_outlines)

            return result
        except Exception as e:
            logger.error(f"Agent 聊天失败: {e}")
            return {
                "message": "抱歉，处理您的请求时遇到问题。请稍后再试。",
                "outline_updates": None,
                "suggestions": None,
                "saved_outline": None,
            }


    def _get_simple_output_format(self) -> str:
        """获取简化的输出格式（仅当 md 输出格式资产不可用时使用）。"""
        return (
            "【Plot Outline deprecated 最小输出格式 fallback】\n"
            "必须输出完整 JSON：单章使用 chapter_number/title/summary/chapter_goals/scenes；"
            "多章使用 chapters 数组；不要省略必需字段。"
        )

    def _build_fallback_prompt_with_trace(self, project_id: Optional[str]) -> Dict[str, Any]:
        md_prompt = self._build_md_plot_outline_fallback_prompt()
        if md_prompt:
            return {
                "content": md_prompt,
                "trace": {
                    "agent_type": "plot_outline",
                    "scenario": "generate_chapter_outline",
                    "project_id": project_id,
                    "template_id": None,
                    "template_scenario": None,
                    "config_id": None,
                    "prompt_ids": [],
                    "skill_ids": [],
                    "skills": None,
                    "writing_rule_ids": [],
                    "writing_rules": None,
                    "context_blocks": [],
                    "fallbacks_used": ["plot_outline_md_prompt_fallback"],
                    "deprecated_sources_used": [],
                    "missing_prompt_ids": [],
                },
            }

        logger.warning("plot_outline md prompt 资产不可用，使用 deprecated 最小硬编码备用 prompt")
        return {
            "content": (
                "你是 Plot Outline Agent。优先使用 Agent Template 绑定的 md prompt、skills 和 writing-rules；"
                "当前仅因配置资产不可用而启用 deprecated 最小 fallback。\n\n"
                f"{self._get_simple_output_format()}"
            ),
            "trace": {
                "agent_type": "plot_outline",
                "scenario": "generate_chapter_outline",
                "project_id": project_id,
                "template_id": None,
                "template_scenario": None,
                "config_id": None,
                "prompt_ids": [],
                "skill_ids": [],
                "skills": None,
                "writing_rule_ids": [],
                "writing_rules": None,
                "context_blocks": [],
                "fallbacks_used": ["plot_outline_deprecated_minimal_system_prompt"],
                "deprecated_sources_used": ["PlotOutlineService._build_fallback_prompt_with_trace"],
                "missing_prompt_ids": [
                    "role_plot_outline",
                    "function_plot_outline",
                    "plot_outline_output",
                ],
            },
        }

    def _build_fallback_prompt(self) -> str:
        """构建备用 prompt（优先使用 prompts/**/*.md 资产）。"""
        return self._build_fallback_prompt_with_trace(None)["content"]

    async def _build_outline_context_packet(
        self,
        *,
        project_id: str,
        chapter_number: int,
        task_type: str,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        user_message: Optional[str] = None,
        extra_scope: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self._db:
            return None
        from app.services.assistant_context import get_assistant_context_fabric

        scope = {
            "chapter_number": chapter_number,
            "surface_entry": "outlines",
            "needs": ["chapter_outlines", "plot_hooks", "characters", "lore", "world", "recent_deltas"],
        }
        if user_message:
            scope["user_message"] = user_message
        if extra_scope:
            scope.update(extra_scope)
        packet = await get_assistant_context_fabric(self._db).build_packet(
            project_id=project_id,
            assistant_surface="plot_outline_agent",
            task_type=task_type,
            session_id=session_id,
            mode="chapter:1",
            request_id=request_id,
            scope=scope,
            user_message=user_message,
        )
        logger.info(
            "[PlotOutline] 使用 Assistant Context Fabric packet=%s snapshot=v%s tokens=%s",
            packet.get("packet_id"),
            packet.get("snapshot_version"),
            packet.get("metadata", {}).get("token_estimate"),
        )
        return packet

    def _context_packet_metadata(self, context_packet: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not context_packet:
            return None
        return {
            "packet_id": context_packet.get("packet_id"),
            "snapshot_id": context_packet.get("snapshot_id"),
            "snapshot_version": context_packet.get("snapshot_version"),
            **(context_packet.get("metadata") or {}),
        }

    async def _append_outline_assistant_response(
        self,
        *,
        context_packet: Optional[Dict[str, Any]],
        response: str,
        request_id: Optional[str],
    ) -> None:
        if not context_packet or not self._db:
            return
        packet_id = context_packet.get("packet_id")
        snapshot_id = context_packet.get("snapshot_id")
        assistant_session_id = context_packet.get("session_id")
        assistant_session = await self._db.get_assistant_session(assistant_session_id) if assistant_session_id else None
        if not assistant_session:
            return
        from app.services.assistant_context import get_assistant_context_fabric

        await get_assistant_context_fabric(self._db).sessions.append_message(
            session=assistant_session,
            role="assistant",
            content=response,
            request_id=request_id,
            metadata={"context_packet_id": packet_id, "surface_entry": "outlines"},
            packet_id=packet_id,
            snapshot_id=snapshot_id,
        )

    async def _build_chat_user_context(
        self,
        project_id: str,
        chapter_number: int,
        existing_outline: Optional[ChapterOutline],
        extra_context: Optional[Dict[str, Any]],
    ) -> str:
        """构建用户消息上下文"""
        parts = [f"章节号: 第{chapter_number}章"]

        # 添加项目信息
        try:
            from app.api.app import postgres_db
            if postgres_db:
                project = await postgres_db.get_project(project_id)
                if project:
                    parts.append(f"作品: {project.get('title', '未命名')}")
        except Exception:
            pass

        # 添加上下文信息
        if extra_context:
            if extra_context.get("previous_events"):
                parts.append(f"前文事件: {extra_context['previous_events']}")
            if extra_context.get("special_requirements"):
                parts.append(f"特殊要求: {', '.join(extra_context['special_requirements'])}")

        # 添加相邻章节信息
        if existing_outline:
            parts.append(f"当前目标字数: {existing_outline.target_word_count}")
            if existing_outline.chapter_goals:
                parts.append(f"当前章节目标: {', '.join(existing_outline.chapter_goals)}")

        return "\n".join(parts)

    async def _call_llm_for_chat(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
        llm_config: Dict[str, Any],
    ) -> str:
        """调用 LLM 进行聊天，并在 provider 截断或结构化 JSON 未闭合时续写到完整输出。"""
        provider = self._llm_provider
        base_url = self._llm_base_url
        model = self._llm_model
        api_key = self._llm_api_key

        logger.info(
            f"[PlotOutline] LLM调用: provider={provider}, base_url={base_url}, model={model}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"上下文信息：\n{context}"},
            {"role": "user", "content": user_message},
        ]

        if provider == "anthropic":
            try:
                import anthropic
            except ImportError:
                return "无法连接到语言模型，请检查 anthropic 包。"

            if not api_key:
                return "处理请求时出错: API Key 未配置"

            client = anthropic.AsyncAnthropic(
                api_key=api_key,
                base_url=base_url if base_url else "https://api.anthropic.com",
            )

            system_parts = []
            claude_messages = []
            for m in messages:
                if m["role"] == "system":
                    system_parts.append(m["content"])
                else:
                    claude_messages.append({"role": m["role"], "content": m["content"]})
            system_message = "\n\n".join(system_parts)
            accumulated_response = ""

            for attempt in range(self._outline_chat_max_continuations + 1):
                started_at = time.perf_counter()
                try:
                    response = await client.messages.create(
                        model=model,
                        max_tokens=self._outline_chat_max_tokens,
                        temperature=self._llm_temperature,
                        system=system_message,
                        messages=claude_messages,
                    )
                    self._log_timing("provider_call" if attempt == 0 else "provider_continuation_call", started_at)

                    text_content = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            text_content += block.text
                        elif hasattr(block, 'thinking'):
                            logger.debug("收到 ThinkingBlock")
                    accumulated_response = self._merge_continued_response(accumulated_response, text_content)
                    finish_reason = getattr(response, "stop_reason", None)
                    if not self._needs_outline_continuation(accumulated_response, finish_reason):
                        return accumulated_response
                    if attempt >= self._outline_chat_max_continuations:
                        logger.warning(
                            "[PlotOutline] Agent 输出在 %s 次续写后仍不完整，返回完整累积文本供上层拒绝保存",
                            attempt,
                        )
                        return accumulated_response
                    logger.info(
                        "[PlotOutline] Agent 输出需要续写: attempt=%s finish_reason=%s chars=%s",
                        attempt + 1,
                        finish_reason,
                        len(accumulated_response),
                    )
                    claude_messages.append({"role": "assistant", "content": text_content})
                    claude_messages.append({
                        "role": "user",
                        "content": self._build_outline_continuation_instruction(user_message, accumulated_response),
                    })
                except Exception as e:
                    self._log_timing("provider_call_failed", started_at)
                    logger.error(f"[PlotOutline] LLM 调用失败: {e}")
                    return accumulated_response or f"处理请求时出错: {str(e)}"
            return accumulated_response

        try:
            from openai import AsyncOpenAI
        except ImportError:
            return "无法连接到语言模型，请检查 openai 包。"

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url if base_url else "https://api.openai.com/v1",
        )
        openai_messages = [dict(item) for item in messages]
        accumulated_response = ""

        for attempt in range(self._outline_chat_max_continuations + 1):
            started_at = time.perf_counter()
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                    temperature=self._llm_temperature,
                    max_tokens=self._outline_chat_max_tokens,
                )
                self._log_timing("provider_call" if attempt == 0 else "provider_continuation_call", started_at)
                choice = response.choices[0]
                text_content = choice.message.content or ""
                accumulated_response = self._merge_continued_response(accumulated_response, text_content)
                finish_reason = getattr(choice, "finish_reason", None)
                if not self._needs_outline_continuation(accumulated_response, finish_reason):
                    return accumulated_response
                if attempt >= self._outline_chat_max_continuations:
                    logger.warning(
                        "[PlotOutline] Agent 输出在 %s 次续写后仍不完整，返回完整累积文本供上层拒绝保存",
                        attempt,
                    )
                    return accumulated_response
                logger.info(
                    "[PlotOutline] Agent 输出需要续写: attempt=%s finish_reason=%s chars=%s",
                    attempt + 1,
                    finish_reason,
                    len(accumulated_response),
                )
                openai_messages.append({"role": "assistant", "content": text_content})
                openai_messages.append({
                    "role": "user",
                    "content": self._build_outline_continuation_instruction(user_message, accumulated_response),
                })
            except Exception as e:
                self._log_timing("provider_call_failed", started_at)
                logger.error(f"[PlotOutline] LLM 调用失败: {e}")
                return accumulated_response or f"处理请求时出错: {str(e)}"
        return accumulated_response

    def _try_parse_outline_updates(self, response: str) -> Optional[Dict[str, Any]]:
        """
        尝试从响应中解析大纲更新

        支持两种返回格式：
        1. 单章大纲：{"title": "...", "summary": "...", ...}
        2. 多章大纲：{"chapters": [{"chapter_number": 1, ...}, {"chapter_number": 2, ...}, ...]}
        """
        try:
            parsed_json = self._extract_json_object(response)
            if parsed_json:
                parsed_json = self._coerce_outline_payload(parsed_json)
                if self._has_outline_shape(parsed_json):
                    return parsed_json

            if self._contains_structured_outline_attempt(response):
                return None

            chapters = self._extract_chapters_from_text(response)
            valid_chapters = [chapter for chapter in chapters if self._is_saveable_pending_outline(chapter)]
            if valid_chapters and len(valid_chapters) > 1:
                logger.info(f"从文本中提取了 {len(valid_chapters)} 章大纲")
                return {"chapters": valid_chapters}
            elif valid_chapters and len(valid_chapters) == 1:
                return valid_chapters[0]

            outline_data = self._extract_single_outline_from_text(response)
            if self._is_saveable_pending_outline(outline_data):
                logger.info(f"从文本中提取大纲信息: {outline_data}")
                return outline_data

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"解析大纲更新失败: {e}")
        return None

    def _extract_chapters_from_text(self, response: str) -> List[Dict[str, Any]]:
        """从文本中提取多章大纲信息"""
        import re
        chapters = []

        # 匹配章节标题模式：
        # 1. ## 第X章：标题 (markdown 标题)
        # 2. 第X章：标题 (行首)
        # 支持中文数字和阿拉伯数字
        chapter_pattern = r'(?:^|\n)[ \t]*(?:##\s*)?第([一二三四五六七八九十\d]+)章[：:]\s*([^\n\[\]✓×✗]+?)[ \t]*$'

        # 中文数字转阿拉伯数字
        def chinese_to_num(cn: str) -> int:
            mapping = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                      '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
            if cn in mapping:
                return mapping[cn]
            try:
                return int(cn)
            except:
                return 0

        matches = list(re.finditer(chapter_pattern, response, re.MULTILINE))

        # 过滤掉检查列表中的匹配
        valid_matches = []
        for match in matches:
            start_pos = match.start()
            prefix = response[max(0, start_pos-10):start_pos]
            if not re.search(r'\[✓\]|\[×\]|\[✗\]|\[X\]', prefix):
                valid_matches.append(match)

        if not valid_matches:
            return []

        for i, match in enumerate(valid_matches):
            chapter_num = chinese_to_num(match.group(1))
            title = match.group(2).strip()

            if chapter_num == 0:
                continue

            # 提取该章节的内容范围
            start = match.end()
            if i + 1 < len(valid_matches):
                end = valid_matches[i + 1].start()
            else:
                # 查找结束标记
                end_markers = ['## 反派', '## 核心卖点', '---\n```json', '## 伏笔管理', '## 黄金三章自查']
                end = len(response)
                for marker in end_markers:
                    marker_pos = response.find(marker, start)
                    if marker_pos != -1 and marker_pos < end:
                        end = marker_pos

            chapter_text = response[start:end]

            # 提取摘要 - 查找 summary 字段或描述段落
            summary = ""
            # 先尝试从JSON格式的summary提取
            summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', chapter_text)
            if summary_match:
                summary = summary_match.group(1).strip()
            else:
                # 尝试从文本描述提取（核心策略后面的内容）
                strategy_match = re.search(r'\*\*核心策略\*\*[：:]\s*([^\n]+(?:\n[^\n#]*){0,3})', chapter_text)
                if strategy_match:
                    summary = strategy_match.group(1).strip()

            # 提取章节目标
            goals = []
            goals_match = re.search(r'"chapter_goals"\s*:\s*\[((?:[^\[\]]+|\[(?:[^\[\]]+|\[[^\[\]]*\])*\])*)\]', chapter_text)
            if goals_match:
                # 解析JSON数组
                try:
                    goals_str = '[' + goals_match.group(1) + ']'
                    goals = json.loads(goals_str)
                except:
                    pass
            else:
                # 从文本列表提取
                goals = re.findall(r'"([^"]+展示[^"]*|[^"]+建立[^"]*|[^"]+埋设[^"]*|[^"]+制造[^"]*)"', chapter_text)

            # 提取场景规划表格
            scenes = []
            scene_table = re.findall(r'\|\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*(\d+)字\s*\|', chapter_text)
            for s in scene_table:
                scenes.append({
                    "scene_number": int(s[0]),
                    "title": s[1].strip(),
                    "estimated_words": int(s[2])
                })

            # 如果没有表格，尝试从JSON格式的scenes提取
            if not scenes:
                scenes_match = re.search(r'"scenes"\s*:\s*\[', chapter_text)
                if scenes_match:
                    # 找到scenes数组的开始和结束
                    start_idx = scenes_match.start()
                    brace_count = 0
                    bracket_count = 0
                    in_string = False
                    escape = False
                    end_idx = start_idx

                    for idx, char in enumerate(chapter_text[start_idx:], start_idx):
                        if escape:
                            escape = False
                            continue
                        if char == '\\':
                            escape = True
                            continue
                        if char == '"':
                            in_string = not in_string
                            continue
                        if in_string:
                            continue
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                        elif char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0 and brace_count == 0:
                                end_idx = idx + 1
                                break

                    if end_idx > start_idx:
                        try:
                            scenes_json = json.loads(chapter_text[start_idx:end_idx])
                            for scene in scenes_json:
                                scenes.append({
                                    "scene_number": scene.get("scene_number", 0),
                                    "title": scene.get("title", ""),
                                    "summary": scene.get("summary", ""),
                                    "estimated_words": scene.get("estimated_words", 500),
                                    "key_events": scene.get("key_events", []),
                                })
                        except Exception as e:
                            logger.debug(f"解析scenes失败: {e}")

            # 提取钩子
            hooks_planted = []
            hook_patterns = [
                r'\*\*开篇钩子\*\*[（(][^)）]+[)）][：:]\s*\n?\s*>?\s*([^\n#]+)',
                r'\*\*结尾钩子\*\*[（(][^)）]+[)）][：:]\s*\n?\s*>?\s*([^\n#]+)',
            ]
            for pattern in hook_patterns:
                hook_match = re.search(pattern, chapter_text, re.IGNORECASE)
                if hook_match:
                    hooks_planted.append(hook_match.group(1).strip())

            # 提取伏笔
            hooks_from_text = re.findall(r'\*\*埋设\*\*[：:]\s*([^\n]+)', chapter_text)
            hooks_planted.extend(hooks_from_text)

            chapters.append({
                "chapter_number": chapter_num,
                "title": title,
                "summary": summary if summary else "",
                "chapter_goals": goals if goals else [],
                "hooks_planted": hooks_planted if hooks_planted else [],
                "scenes": scenes,
            })

        if chapters:
            logger.info(f"从文本中提取了 {len(chapters)} 章大纲: {[c['title'] for c in chapters]}")

        return chapters

    def _extract_single_outline_from_text(self, response: str) -> Dict[str, Any]:
        """从文本中提取单章大纲信息"""
        import re
        outline_data = {}

        # 提取标题
        title_match = re.search(r'(?:章节标题|标题|第\d+章[：:]?\s*)([^\n「」【】\|]+)', response)
        if title_match:
            outline_data["title"] = title_match.group(1).strip()

        parsed_json = self._extract_json_object(response)
        if parsed_json and isinstance(parsed_json, dict):
            for key in [
                "summary", "chapter_goals", "scenes", "hooks_planted", "hooks_resolved",
                "target_word_count", "emotion_curve", "writing_guide", "quality_check",
                "quality_metrics", "notes", "foreshadowing", "villain_arc", "cool_points",
            ]:
                if key in parsed_json:
                    outline_data[key] = parsed_json[key]

        # 提取摘要
        summary_match = re.search(r'(?:章节摘要|摘要|内容概要|summary)[：:]\s*([^\n]+(?:\n[^\n#]*)*)', response, re.IGNORECASE)
        if summary_match:
            outline_data["summary"] = summary_match.group(1).strip()

        # 提取章节目标
        goals_match = re.search(r'(?:章节目标|目标|goals)[：:]\s*((?:[-•]\s*[^\n]+\n?)+)', response, re.IGNORECASE)
        if goals_match:
            goals_text = goals_match.group(1)
            goals = re.findall(r'[-•]\s*([^\n]+)', goals_text)
            if goals:
                outline_data["chapter_goals"] = goals

        # 提取场景（新格式：**场景1：标题（约800字）**）
        scenes = []
        scene_pattern = r'\*\*场景(\d+)[：:]\s*([^(（]+)(?:[(（]约(\d+)字[)）])?\*\*\s*\n((?:[-•]\s*[^\n]+\n?)+)'
        scene_matches = re.finditer(scene_pattern, response)

        for match in scene_matches:
            scene_num = int(match.group(1))
            scene_title = match.group(2).strip()
            estimated_words = int(match.group(3)) if match.group(3) else 500
            scene_content = match.group(4)

            # 提取场景内的关键事件
            key_events = re.findall(r'[-•]\s*\*\*([^*]+)\*\*[：:]\s*([^\n]+)', scene_content)
            if not key_events:
                key_events = [(f"事件{i+1}", line.strip()) for i, line in enumerate(re.findall(r'[-•]\s*([^\n]+)', scene_content))]

            summary = ""
            for event_title, event_content in key_events:
                summary += event_content + "。"
            if not summary:
                lines = re.findall(r'[-•]\s*([^\n]+)', scene_content)
                summary = lines[0] if lines else ""

            scenes.append({
                "scene_number": scene_num,
                "title": scene_title,
                "summary": summary,
                "estimated_words": estimated_words,
                "key_events": [e[1] if isinstance(e, tuple) else e for e in key_events]
            })

        # 如果找到了场景，添加到大纲数据
        if scenes:
            outline_data["scenes"] = scenes

        # 提取结尾钩子
        ending_hook = re.search(r'\*\*结尾钩子\*\*[^\n]*\n([\s\S]*?)(?=\n---|\n##|\n```json|$)', response)
        if ending_hook:
            hook_text = ending_hook.group(1).strip()
            # 提取结尾句
            ending_sentence = re.search(r'\*\*结尾句\*\*[：:]\s*"([^"]+)"', hook_text)
            if ending_sentence:
                outline_data["hooks_planted"] = [ending_sentence.group(1)]

        return outline_data

    def _convert_scenes_data(self, scenes_data: List[Any]) -> List[SceneOutline]:
        """
        转换场景数据为 SceneOutline 对象

        Args:
            scenes_data: 场景数据列表（可以是 dict 或 SceneOutline）

        Returns:
            List[SceneOutline]: SceneOutline 对象列表
        """
        if not scenes_data:
            return []

        scenes = []
        for i, scene_data in enumerate(scenes_data):
            try:
                if isinstance(scene_data, SceneOutline):
                    scenes.append(scene_data)
                elif isinstance(scene_data, dict):
                    scene = SceneOutline(
                        id=scene_data.get("id", f"scene_{uuid.uuid4().hex[:8]}"),
                        scene_number=scene_data.get("scene_number", i + 1),
                        title=scene_data.get("title", f"场景{i + 1}"),
                        scene_type=SceneType(self._normalize_scene_type_value(scene_data.get("scene_type", "dialogue"))),
                        summary=scene_data.get("summary", ""),
                        key_events=scene_data.get("key_events", []),
                        participating_characters=scene_data.get("participating_characters", []),
                        pov_character=scene_data.get("pov_character"),
                        location=scene_data.get("location"),
                        time_of_day=scene_data.get("time_of_day"),
                        emotion_start=EmotionType(
                            self._normalize_emotion_value(
                                scene_data.get("emotion_start", "neutral")
                            )
                        ),
                        emotion_end=EmotionType(
                            self._normalize_emotion_value(
                                scene_data.get("emotion_end", "neutral")
                            )
                        ),
                        emotion_arc=[
                            EmotionType(self._normalize_emotion_value(emotion))
                            for emotion in scene_data.get("emotion_arc", [])
                        ],
                        conflict_level=ConflictLevel(self._normalize_conflict_level_value(scene_data.get("conflict_level", "low"))),
                        conflict_description=scene_data.get("conflict_description"),
                        hooks_to_plant=scene_data.get("hooks_to_plant", []),
                        hooks_to_resolve=scene_data.get("hooks_to_resolve", []),
                        estimated_words=scene_data.get("estimated_words", 500),
                        writing_hints=scene_data.get("writing_hints", []),
                    )
                    scenes.append(scene)
            except Exception as e:
                logger.warning(f"转换场景数据失败: {e}, 数据: {scene_data}")

        return scenes

    def _extract_suggestions(self, response: str) -> List[str]:
        """从响应中提取建议"""
        suggestions = []
        # 简单提取：查找"建议"开头的行
        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("建议") or line.startswith("- 建议"):
                suggestions.append(line.lstrip("- ").lstrip("建议：").lstrip("建议:"))
        return suggestions


# 全局实例
_plot_outline_service: Optional[PlotOutlineService] = None


def get_plot_outline_service() -> PlotOutlineService:
    """获取章节大纲服务实例"""
    global _plot_outline_service
    if _plot_outline_service is None:
        from app.api.app import postgres_db
        from app.services.skill_service import get_skill_service
        _plot_outline_service = PlotOutlineService(
            db=postgres_db,
            skill_service=get_skill_service(),
        )
    return _plot_outline_service


def set_plot_outline_service(service: PlotOutlineService):
    """设置章节大纲服务实例"""
    global _plot_outline_service
    _plot_outline_service = service
