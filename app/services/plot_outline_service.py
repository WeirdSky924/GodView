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
        for cache in (self._context_cache, self._formatted_context_cache, self._system_prompt_cache):
            stale_keys = [key for key in cache if key.startswith(context_prefix)]
            for key in stale_keys:
                del cache[key]

    def _merge_outline_into_list(self, outline: ChapterOutline):
        self._outlines_cache[outline.id] = outline
        self._loaded_outline_projects.add(outline.project_id)

    def _build_outline_list_cache(self, outlines: List[ChapterOutline]):
        self._outlines_cache = {outline.id: outline for outline in outlines}
        self._loaded_outline_projects = {outline.project_id for outline in outlines}

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
                "SELECT * FROM chapter_outlines WHERE project_id = :project_id ORDER BY chapter_number",
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

    async def _get_cached_system_prompt(
        self,
        project_id: str,
        chapter_number: int,
        full_context: Dict[str, Any],
    ) -> str:
        cache_key = self._get_system_prompt_cache_key(project_id, chapter_number)
        cached = self._get_cached_value(self._system_prompt_cache, cache_key)
        if cached is not None:
            return cached

        started_at = time.perf_counter()
        try:
            from app.services.agent_prompt_service import get_agent_prompt_service
            prompt_service = get_agent_prompt_service()
            base_prompt = await prompt_service.build_agent_prompt(
                agent_type="plot_outline",
                project_id=project_id,
                include_skills=True,
                scenario="generate_chapter_outline",
            )
        except Exception as e:
            logger.warning(f"加载 plot_outline prompt 模板失败: {e}，使用默认 prompt")
            base_prompt = self._build_fallback_prompt()

        context_hints = self._build_context_hints(full_context)
        output_format = await self._get_cached_output_format_prompt()
        system_prompt = f"{base_prompt}\n\n{context_hints}\n\n{output_format}".strip()
        self._log_timing("build_system_prompt", started_at)
        return self._cache_entry(self._system_prompt_cache, cache_key, system_prompt)

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
        cache_key = "plot_outline_output"
        cached = self._get_cached_value(self._output_format_cache, cache_key)
        if cached is not None:
            return cached

        content = self._load_md_prompt_content("plot_outline_output")
        if content:
            return self._cache_entry(self._output_format_cache, cache_key, content)

        return self._cache_entry(self._output_format_cache, cache_key, self._get_simple_output_format())

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

    def _truncate_text(self, value: Optional[str], limit: int) -> str:
        if not value:
            return ""
        return value

    def _build_lore_context_entry(self, lore: Dict[str, Any], summary_limit: int) -> Dict[str, Any]:
        summary = lore.get("summary") or lore.get("content") or ""
        return {
            "title": lore.get("title", ""),
            "category": lore.get("category", "custom"),
            "priority": lore.get("priority", "standard"),
            "summary": summary,
        }

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
            summary = self._truncate_text(lore.get("summary"), summary_limit)
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
        setting_gaps = consistency.get("setting_gaps", [])

        if not conflicts and not risk_areas:
            return None

        repair_feedback = [
            "你刚生成的大纲存在设定一致性风险，请基于原任务立即修正后重新输出完整 JSON。",
            "修正时必须优先服从宪法级设定和核心设定，不要输出解释，不要省略字段。",
        ]
        if conflicts:
            repair_feedback.append("冲突列表：")
            repair_feedback.extend([f"- {item}" for item in conflicts])
        if risk_areas:
            repair_feedback.append("风险区域：")
            repair_feedback.extend([f"- {item}" for item in risk_areas])
        if setting_gaps:
            repair_feedback.append("设定缺口：")
            repair_feedback.extend([f"- {item}" for item in setting_gaps])

        repaired_response = await self._call_llm_for_chat(
            system_prompt=system_prompt,
            user_message=f"{message}\n\n" + "\n".join(repair_feedback),
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
            except json.JSONDecodeError:
                continue
        return None

    def _has_outline_shape(self, data: Dict[str, Any]) -> bool:
        return any(key in data for key in ["title", "summary", "scenes", "chapters", "chapter_goals", "writing_guide"])

    def _has_meaningful_outline_content(self, outline_data: Dict[str, Any]) -> bool:
        if not outline_data:
            return False
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
        requirements: List[Dict[str, Any]] = []

        for name in sorted(candidates["character"]):
            if name.lower() in known_characters:
                continue
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

        for name in sorted(candidates["location"]):
            lowered = name.lower()
            if lowered in known_location_names or lowered in known_lore:
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
            if resource_name.lower() in known_lore or any(
                lore_name and (lore_name in source_excerpt.lower() or keyword in lore_name)
                for lore_name in known_lore
            ):
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
                await self._db.update_chapter_resource_readiness(
                    outline.project_id,
                    outline_id=None,
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
        for scene in normalized.get("scenes") or []:
            if isinstance(scene, dict):
                scene_data = dict(scene)
                scene_data["emotion_start"] = self._normalize_emotion_value(
                    scene_data.get("emotion_start", "neutral")
                )
                scene_data["emotion_end"] = self._normalize_emotion_value(
                    scene_data.get("emotion_end", "neutral")
                )
                normalized_scenes.append(scene_data)
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
                for scene in chapter_data.get("scenes") or []:
                    if isinstance(scene, dict):
                        scene_payload = dict(scene)
                        scene_payload["emotion_start"] = self._normalize_emotion_value(
                            scene_payload.get("emotion_start", "neutral")
                        )
                        scene_payload["emotion_end"] = self._normalize_emotion_value(
                            scene_payload.get("emotion_end", "neutral")
                        )
                        normalized_chapter_scenes.append(scene_payload)
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

        return saved_outline, saved_outlines

    def _mark_outline_project_dirty(self, project_id: str, chapter_number: Optional[int] = None):
        self._loaded_outline_projects.discard(project_id)
        self._invalidate_project_caches(project_id, chapter_number)

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
        await self._persist_outline_resource_audit(outline)
        return outline

    async def get_outline(self, project_id: str, chapter_number: int) -> Optional[ChapterOutline]:
        """
        获取指定章节的大纲

        Args:
            project_id: 项目ID
            chapter_number: 章节号

        Returns:
            ChapterOutline 或 None
        """
        await self._ensure_cache(project_id)

        for outline in self._outlines_cache.values():
            if outline.project_id == project_id and outline.chapter_number == chapter_number:
                return outline

        return None

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

        # 获取完整项目上下文
        full_context = await self.get_full_project_context(project_id, chapter_number)

        # 如果调用者没有提供特定信息，使用自动获取的上下文
        if not characters:
            characters = full_context.get("characters", [])
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
                        "story_context": self.format_context_for_prompt(full_context),
                        "is_golden_three": is_golden_three,
                    }
                ))
                if result.success:
                    data = self._require_structured_dict(result, "解析章节大纲生成结果失败")
                    outline = self._parse_generated_outline(project_id, chapter_number, self._select_outline_payload(data, chapter_number))
                    consistency = await self._check_outline_setting_consistency(project_id, data, full_context)
                    warnings = list(data.get("warnings", []))
                    warnings.extend(self._summarize_consistency_warnings(consistency))
                    return GenerateOutlineResponse(
                        outline=outline,
                        suggestions=data.get("suggestions", []),
                        warnings=warnings,
                    )
            except Exception as e:
                logger.warning(f"使用 Skill 生成大纲失败，fallback 到直接生成: {e}")

        # 直接生成（fallback）
        outline = await self._generate_outline_direct(
            project_id=project_id,
            chapter_number=chapter_number,
            prompt=prompt,
            full_context=full_context,
        )

        return GenerateOutlineResponse(
            outline=outline,
            suggestions=["大纲已生成，建议人工审核后使用"],
            warnings=[],
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
    ) -> str:
        """构建大纲生成 Prompt"""
        prompt_parts = [
            f"请为第 {chapter_number} 章生成详细的章节大纲。",
            "",
        ]

        # 如果有完整上下文，优先使用
        if full_context:
            context_str = self.format_context_for_prompt(full_context)
            if context_str:
                prompt_parts.append(context_str)

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
            prompt_parts.append("【主要角色】")
            for char in characters:
                name = char.get('name', '未知')
                role = char.get('role', '')
                prompt_parts.append(f"- {name} ({role})" if role else f"- {name}")
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

        prompt_parts.append("""
【输出格式要求】
请输出 JSON 格式：
{
    "title": "章节标题",
    "summary": "章节摘要（100-200字）",
    "scenes": [
        {
            "scene_number": 1,
            "title": "场景标题",
            "scene_type": "dialogue/action/description/climax",
            "summary": "场景摘要",
            "participating_characters": ["角色名"],
            "location": "地点",
            "emotion_start": "neutral/joy/fear/tension等",
            "emotion_end": "neutral/joy/fear/tension等",
            "conflict_level": "low/medium/high/critical",
            "estimated_words": 800,
            "key_events": ["关键事件1", "关键事件2"]
        }
    ],
    "emotion_curve": {
        "points": [
            {"position": 0.0, "emotion": "neutral", "intensity": 0.3},
            {"position": 0.5, "emotion": "tension", "intensity": 0.8},
            {"position": 1.0, "emotion": "relief", "intensity": 0.5}
        ],
        "dominant_emotion": "tension"
    },
    "chapter_goals": ["目标1", "目标2"],
    "hooks_to_plant": ["建议埋设的伏笔"],
    "hooks_to_resolve": ["建议回收的伏笔ID"],
    "suggestions": ["写作建议"],
    "warnings": ["注意事项"]
}
""")
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
                location=s.get("location"),
                emotion_start=EmotionType(self._normalize_emotion_value(s.get("emotion_start", "neutral"))),
                emotion_end=EmotionType(self._normalize_emotion_value(s.get("emotion_end", "neutral"))),
                conflict_level=ConflictLevel(s.get("conflict_level", "low")),
                estimated_words=s.get("estimated_words", 500),
                key_events=s.get("key_events", []),
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
    ) -> ChapterOutline:
        """直接调用 LLM 生成大纲（Skill 失败时的 fallback）"""
        from app.config import settings

        # 从数据库加载 prompt 模板
        try:
            from app.services.agent_prompt_service import get_agent_prompt_service
            prompt_service = get_agent_prompt_service()
            system_prompt = await prompt_service.build_agent_prompt(
                agent_type="plot_outline",
                project_id=project_id,
                include_skills=True,
                scenario="generate_chapter_outline",
            )
        except Exception as e:
            logger.warning(f"加载 plot_outline prompt 模板失败: {e}")
            system_prompt = self._build_fallback_prompt()

        try:
            llm_config = settings.get_llm_config(settings.llm_provider)
            response = await self._call_llm_for_chat(
                system_prompt=system_prompt,
                user_message=prompt,
                context="",
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
                        combined_context="",
                        llm_config=llm_config,
                        consistency=consistency,
                    )
                    if repaired_updates:
                        outline_updates = self._normalize_outline_updates(repaired_updates)

            return self._parse_generated_outline(
                project_id,
                chapter_number,
                self._select_outline_payload(outline_updates, chapter_number),
            )
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

        if self._db:
            try:
                if soft_delete_generated_chapters and outline:
                    soft_deleted_chapters = await self._db.soft_delete_chapters_by_outline(
                        outline.project_id,
                        outline_id,
                    )

                await self._db.execute_write(
                    "DELETE FROM chapter_outlines WHERE id = :id",
                    {"id": outline_id}
                )
                logger.info(f"删除章节大纲: {outline_id}，软删除关联章节: {soft_deleted_chapters}")
            except Exception as e:
                logger.error(f"删除章节大纲失败: {e}")
                return {"success": False, "soft_deleted_chapters": soft_deleted_chapters}

        if outline_id in self._outlines_cache:
            del self._outlines_cache[outline_id]

        if outline:
            self._mark_outline_project_dirty(outline.project_id, outline.chapter_number)

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
                logger.info(f"审批章节大纲: {outline_id}")
            except Exception as e:
                logger.error(f"审批章节大纲失败: {e}")

        self._mark_outline_project_dirty(outline.project_id, outline.chapter_number)
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
                SELECT id, name, role, personality, background_story,
                       importance_tier, status
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
                    name
                """,
                {"project_id": project_id}
            )
            for char in characters:
                personality = char.get("personality") or ""
                background = char.get("background_story") or ""
                context["characters"].append({
                    "name": char.get("name", ""),
                    "role": char.get("role", "supporting"),
                    "personality": personality,
                    "background": background,
                    "importance": char.get("importance_tier", "npc"),
                    "status": char.get("status", ""),
                })

            # 3. 获取世界设定
            lores = await self._db.execute_query(
                """
                SELECT title, category, priority, content, summary
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

        # 角色信息
        if context.get("characters"):
            parts.append("【主要角色】")
            for char in context["characters"]:
                role_label = {"main": "主角", "antagonist": "反派", "supporting": "配角"}.get(char.get("role", ""), "角色")
                parts.append(f"- {char['name']} ({role_label})")
                if char.get("personality"):
                    parts.append(f"  性格：{char['personality']}")
                if char.get("background"):
                    parts.append(f"  背景：{char['background']}")
                if char.get("status"):
                    parts.append(f"  当前状态：{char['status']}")
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
            full_context = await self._get_cached_project_context(project_id, chapter_number)
            context_str = self._get_cached_formatted_context(project_id, chapter_number, full_context)
            base_system_prompt = await self._get_cached_system_prompt(project_id, chapter_number, full_context)
            outline_runtime_context = self._build_outline_runtime_context(existing_outline)
            system_prompt = f"{base_system_prompt}\n\n{outline_runtime_context}".strip()

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
            logger.info(f"[PlotOutline] 解析结果: {outline_updates}")

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
                            consistency = await self._check_outline_setting_consistency(project_id, outline_updates, full_context)

                    consistency_warnings = self._summarize_consistency_warnings(consistency)

                    save_started_at = time.perf_counter()
                    saved_outline, saved_outlines = await self._save_outline_updates(
                        project_id=project_id,
                        default_chapter_number=chapter_number,
                        outline_updates=outline_updates,
                    )
                    self._log_timing("auto_save_outline", save_started_at)

                except Exception as e:
                    logger.error(f"自动保存草稿失败: {e}")

            result = {
                "message": response,
                "outline_updates": outline_updates,
                "suggestions": self._extract_suggestions(response),
                "saved_outline": self._outline_saved_response(saved_outline),
            }
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
        """获取简化的输出格式（当 prompt 库加载失败时使用）"""
        return """【重要：输出格式要求】

当用户要求生成大纲时，必须输出完整的 JSON 格式：

单章格式：
```json
{"chapter_number": 1, "title": "标题", "summary": "摘要", "chapter_goals": ["目标1"], "scenes": [{"scene_number": 1, "title": "场景", "summary": "内容", "estimated_words": 800}]}
```

多章格式：
```json
{"chapters": [{"chapter_number": 1, "title": "标题", "summary": "摘要", "scenes": [...]}, {"chapter_number": 2, ...}]}
```

规则：必须输出完整 JSON，不要省略字段。"""

    def _build_fallback_prompt(self) -> str:
        """构建备用 prompt（优先使用 prompts/**/*.md 资产）。"""
        md_prompt = self._build_md_plot_outline_fallback_prompt()
        if md_prompt:
            return md_prompt

        logger.warning("plot_outline md prompt 资产不可用，使用 deprecated 硬编码备用 prompt")
        return """你是专业的章节大纲规划助手（Plot Outline Agent）。

你的职责是帮助用户规划章节结构和场景设计，设计情绪曲线和节奏控制，管理章节目标、伏笔埋设和回收。

""" + self._get_simple_output_format()

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
        """调用 LLM 进行聊天"""
        # 使用实例保存的配置
        provider = self._llm_provider
        base_url = self._llm_base_url
        model = self._llm_model
        api_key = self._llm_api_key

        # 记录调用信息用于调试
        logger.info(
            f"[PlotOutline] LLM调用: provider={provider}, base_url={base_url}, model={model}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"上下文信息：\n{context}"},
            {"role": "user", "content": user_message},
        ]

        # 根据 provider 选择合适的 SDK
        if provider == "anthropic":
            # 使用 Anthropic SDK（适用于百度千帆的 anthropic 端点）
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

            # 合并所有 system 消息为一个
            system_parts = []
            claude_messages = []

            for m in messages:
                if m["role"] == "system":
                    system_parts.append(m["content"])
                else:
                    claude_messages.append({"role": m["role"], "content": m["content"]})

            system_message = "\n\n".join(system_parts)
            started_at = time.perf_counter()

            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=self._llm_max_tokens,
                    temperature=self._llm_temperature,
                    system=system_message,
                    messages=claude_messages,
                )
                self._log_timing("provider_call", started_at)

                # 处理响应内容（可能有 ThinkingBlock）
                text_content = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        text_content += block.text
                    elif hasattr(block, 'thinking'):
                        logger.debug("收到 ThinkingBlock")
                return text_content
            except Exception as e:
                self._log_timing("provider_call_failed", started_at)
                logger.error(f"[PlotOutline] LLM 调用失败: {e}")
                return f"处理请求时出错: {str(e)}"
        else:
            # 使用 OpenAI 兼容客户端
            try:
                from openai import AsyncOpenAI
            except ImportError:
                return "无法连接到语言模型，请检查 openai 包。"

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url if base_url else "https://api.openai.com/v1",
            )
            started_at = time.perf_counter()

            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=self._llm_temperature,
                    max_tokens=self._llm_max_tokens,
                )
                self._log_timing("provider_call", started_at)
                return response.choices[0].message.content
            except Exception as e:
                self._log_timing("provider_call_failed", started_at)
                logger.error(f"[PlotOutline] LLM 调用失败: {e}")
                return f"处理请求时出错: {str(e)}"

    def _try_parse_outline_updates(self, response: str) -> Optional[Dict[str, Any]]:
        """
        尝试从响应中解析大纲更新

        支持两种返回格式：
        1. 单章大纲：{"title": "...", "summary": "...", ...}
        2. 多章大纲：{"chapters": [{"chapter_number": 1, ...}, {"chapter_number": 2, ...}, ...]}
        """
        try:
            parsed_json = self._extract_json_object(response)
            if parsed_json and self._has_outline_shape(parsed_json):
                return parsed_json

            chapters = self._extract_chapters_from_text(response)
            valid_chapters = [chapter for chapter in chapters if self._has_meaningful_outline_content(chapter)]
            if valid_chapters and len(valid_chapters) > 1:
                logger.info(f"从文本中提取了 {len(valid_chapters)} 章大纲")
                return {"chapters": valid_chapters}
            elif valid_chapters and len(valid_chapters) == 1:
                return valid_chapters[0]

            outline_data = self._extract_single_outline_from_text(response)
            if self._has_meaningful_outline_content(outline_data):
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
                        scene_type=SceneType(scene_data.get("scene_type", "dialogue")),
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
                        emotion_arc=scene_data.get("emotion_arc", []),
                        conflict_level=ConflictLevel(scene_data.get("conflict_level", "low")),
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
