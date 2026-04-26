from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.services.lore_index_service import get_lore_index_service

logger = logging.getLogger(__name__)


_LIST_FIELDS = {
    "keywords",
    "tags",
    "constraints",
    "forbidden_actions",
    "related_characters",
    "related_locations",
    "related_items",
}


class SettingWorkflowAdapter:
    """Workflow-only Setting adapter that selects existing lore without generating changes."""

    async def execute(self, node, execution, db=None) -> Dict[str, Any]:
        context = execution.context.copy()
        config = dict(getattr(node, "config", None) or {})
        limit = self._resolve_limit(config)
        categories = self._resolve_categories(config)
        include_constitutional_rules = bool(config.get("include_constitutional_rules", False))

        query_parts = self._collect_query_parts(context, config)
        setting_query = self._compact_query(query_parts)
        keywords = self._extract_keywords(context, config, setting_query)
        related_entities = self._extract_related_entities(context, config)
        warnings: list[str] = []

        if not setting_query and not keywords and not related_entities:
            warnings.append("缺少可用于检索设定的章节、场景、角色或地点线索")
            return self._build_output([], setting_query, "empty", warnings)

        selected_entries: list[dict[str, Any]] = []
        setting_source = "empty"

        context_candidates = self._normalize_lore_entries(context.get("lore_entries"))
        if context_candidates:
            selected_entries = self._filter_context_candidates(
                context_candidates,
                setting_query=setting_query,
                keywords=keywords,
                related_entities=related_entities,
                categories=categories,
                limit=limit,
            )
            setting_source = "context_filtered"
            if not selected_entries:
                warnings.append("上下文候选设定中没有与当前节点输入匹配的条目")
        else:
            selected_entries, setting_source = await self._search_existing_lore(
                project_id=execution.project_id,
                db=db,
                setting_query=setting_query,
                keywords=keywords,
                related_entities=related_entities,
                categories=categories,
                limit=limit,
                warnings=warnings,
            )

        if include_constitutional_rules and db:
            selected_entries = await self._merge_constitutional_rules(
                project_id=execution.project_id,
                db=db,
                entries=selected_entries,
                limit=limit,
                warnings=warnings,
            )

        if not selected_entries and not any("没有" in warning for warning in warnings):
            warnings.append("未检索到与当前节点输入相关的已有设定")
            setting_source = "empty" if setting_source == "keyword_db" else setting_source

        return self._build_output(selected_entries, setting_query, setting_source, warnings)

    def _resolve_limit(self, config: Dict[str, Any]) -> int:
        raw_limit = config.get("setting_limit", config.get("lore_limit", 10))
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = 10
        return max(1, min(limit, 30))

    def _resolve_categories(self, config: Dict[str, Any]) -> list[str]:
        raw_categories = config.get("setting_categories", config.get("lore_categories", []))
        if isinstance(raw_categories, str):
            return [raw_categories]
        if isinstance(raw_categories, list):
            return [str(item) for item in raw_categories if str(item).strip()]
        return []

    def _collect_query_parts(self, context: Dict[str, Any], config: Dict[str, Any]) -> list[str]:
        parts: list[str] = []
        for key in ("setting_query", "lore_query", "query"):
            self._append_text(parts, config.get(key))

        for key in (
            "chapter_title",
            "chapter_summary",
            "chapter_goal",
            "user_guidance",
            "current_scene",
            "main_scene",
        ):
            self._append_text(parts, context.get(key))

        self._append_text(parts, context.get("chapter_goals"))
        self._append_text(parts, context.get("selected_characters"))
        self._append_text(parts, context.get("locations"))
        self._append_text(parts, context.get("events"))
        self._append_text(parts, context.get("event_candidates"))

        chapter_outline = context.get("chapter_outline")
        if isinstance(chapter_outline, dict):
            for key in ("title", "summary", "chapter_goals", "goals", "key_events", "conflicts"):
                self._append_text(parts, chapter_outline.get(key))
            self._append_scene_text(parts, chapter_outline.get("scenes"))

        scene_directions = context.get("scene_directions")
        if isinstance(scene_directions, dict):
            for key in (
                "chapter_title",
                "plot_focus",
                "chapter_goals",
                "main_scene",
                "scene_type",
                "selected_characters",
            ):
                self._append_text(parts, scene_directions.get(key))
            self._append_scene_text(parts, scene_directions.get("scenes"))

        world_info = context.get("world_info")
        if isinstance(world_info, dict):
            for key in ("name", "world_type", "themes", "tone"):
                self._append_text(parts, world_info.get(key))

        return parts

    def _append_scene_text(self, parts: list[str], scenes: Any) -> None:
        if not isinstance(scenes, list):
            return
        for scene in scenes:
            if isinstance(scene, dict):
                for key in (
                    "title",
                    "summary",
                    "description",
                    "location",
                    "participating_characters",
                    "goals",
                    "conflict",
                ):
                    self._append_text(parts, scene.get(key))
            else:
                self._append_text(parts, scene)

    def _append_text(self, parts: list[str], value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            text = value.strip()
            if text:
                parts.append(text)
            return
        if isinstance(value, dict):
            for key in ("name", "title", "summary", "description", "content", "location", "reason"):
                self._append_text(parts, value.get(key))
            return
        if isinstance(value, list):
            for item in value:
                self._append_text(parts, item)
            return
        text = str(value).strip()
        if text:
            parts.append(text)

    def _compact_query(self, parts: Sequence[str]) -> str:
        seen: set[str] = set()
        compacted: list[str] = []
        for part in parts:
            normalized = re.sub(r"\s+", " ", part).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            compacted.append(normalized)
        return "\n".join(compacted)[:4000]

    def _extract_keywords(self, context: Dict[str, Any], config: Dict[str, Any], setting_query: str) -> list[str]:
        keywords: list[str] = []
        for key in ("setting_keywords", "lore_keywords", "keywords"):
            self._extend_keywords(keywords, config.get(key))
        for key in ("chapter_goals", "selected_characters"):
            self._extend_keywords(keywords, context.get(key))

        scene_directions = context.get("scene_directions")
        if isinstance(scene_directions, dict):
            self._extend_keywords(keywords, scene_directions.get("selected_characters"))
            self._extend_keywords(keywords, scene_directions.get("main_scene"))

        for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", setting_query):
            if len(token) <= 24:
                keywords.append(token)

        return self._dedupe_texts(keywords)[:40]

    def _extend_keywords(self, keywords: list[str], value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            for token in re.split(r"[,，、;；\s]+", value):
                token = token.strip()
                if token:
                    keywords.append(token)
            return
        if isinstance(value, dict):
            for key in ("name", "title", "summary", "description"):
                self._extend_keywords(keywords, value.get(key))
            return
        if isinstance(value, list):
            for item in value:
                self._extend_keywords(keywords, item)

    def _extract_related_entities(self, context: Dict[str, Any], config: Dict[str, Any]) -> list[str]:
        entities: list[str] = []
        for key in ("related_entities", "related_characters", "related_locations"):
            self._extend_keywords(entities, config.get(key))
        for key in ("selected_characters", "locations", "characters"):
            self._extend_keywords(entities, context.get(key))

        scene_directions = context.get("scene_directions")
        if isinstance(scene_directions, dict):
            self._extend_keywords(entities, scene_directions.get("selected_characters"))
            self._extend_keywords(entities, scene_directions.get("main_scene"))

        chapter_outline = context.get("chapter_outline")
        if isinstance(chapter_outline, dict):
            scenes = chapter_outline.get("scenes") or []
            if isinstance(scenes, list):
                for scene in scenes:
                    if isinstance(scene, dict):
                        self._extend_keywords(entities, scene.get("participating_characters"))
                        self._extend_keywords(entities, scene.get("location"))

        return self._dedupe_texts(entities)[:40]

    def _dedupe_texts(self, values: Iterable[Any]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(text)
        return deduped

    def _normalize_lore_entries(self, raw_entries: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_entries, list):
            return []
        entries: list[dict[str, Any]] = []
        for raw_entry in raw_entries:
            entry = self._normalize_lore_entry(raw_entry)
            if entry:
                entries.append(entry)
        return entries

    def _normalize_lore_entry(self, raw_entry: Any) -> Optional[dict[str, Any]]:
        if raw_entry is None:
            return None
        if isinstance(raw_entry, dict):
            entry = dict(raw_entry)
        elif hasattr(raw_entry, "model_dump"):
            entry = raw_entry.model_dump(mode="json")
        else:
            return None

        for field in _LIST_FIELDS:
            entry[field] = self._normalize_list(entry.get(field))
        if entry.get("id") is not None:
            entry["id"] = str(entry["id"])
        if entry.get("category") is not None and hasattr(entry.get("category"), "value"):
            entry["category"] = entry["category"].value
        if entry.get("priority") is not None and hasattr(entry.get("priority"), "value"):
            entry["priority"] = entry["priority"].value
        return entry

    def _normalize_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [item.strip() for item in re.split(r"[,，、;；]+", stripped) if item.strip()]
        return [value]

    def _filter_context_candidates(
        self,
        candidates: list[dict[str, Any]],
        *,
        setting_query: str,
        keywords: list[str],
        related_entities: list[str],
        categories: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        scored: list[tuple[float, dict[str, Any]]] = []
        category_set = {c.lower() for c in categories}
        for candidate in candidates:
            if category_set and str(candidate.get("category", "")).lower() not in category_set:
                continue
            score = self._score_lore(candidate, setting_query, keywords, related_entities)
            if score >= 2.0:
                scored.append((score, candidate))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def _score_lore(
        self,
        lore: dict[str, Any],
        setting_query: str,
        keywords: list[str],
        related_entities: list[str],
    ) -> float:
        query_lower = setting_query.lower()
        title = str(lore.get("title") or "").strip().lower()
        summary = str(lore.get("summary") or "").strip().lower()
        content = str(lore.get("content") or "").strip().lower()
        category = str(lore.get("category") or "").strip().lower()
        source = str(lore.get("source") or "").strip().lower()
        lore_keywords = [str(item).lower() for item in lore.get("keywords", []) + lore.get("tags", [])]
        lore_relations = [
            str(item).lower()
            for item in (
                lore.get("related_characters", [])
                + lore.get("related_locations", [])
                + lore.get("related_items", [])
            )
        ]

        score = 0.0
        matched_structured = False
        if title and title in query_lower:
            score += 5.0
            matched_structured = True

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if not keyword_lower:
                continue
            if keyword_lower in lore_keywords:
                score += 3.0
                matched_structured = True
            elif keyword_lower in title or keyword_lower in summary:
                score += 1.5
            elif keyword_lower in category or keyword_lower in source:
                score += 1.0
            elif matched_structured and keyword_lower in content:
                score += 0.5

        for lore_keyword in lore_keywords:
            if lore_keyword and lore_keyword in query_lower:
                score += 3.0
                matched_structured = True

        for entity in related_entities:
            entity_lower = entity.lower()
            if entity_lower in lore_relations:
                score += 2.0
                matched_structured = True
            elif entity_lower and (entity_lower in title or entity_lower in summary):
                score += 1.0
            elif matched_structured and entity_lower and entity_lower in content:
                score += 0.5

        return score

    async def _search_existing_lore(
        self,
        *,
        project_id: str,
        db: Any,
        setting_query: str,
        keywords: list[str],
        related_entities: list[str],
        categories: list[str],
        limit: int,
        warnings: list[str],
    ) -> tuple[list[dict[str, Any]], str]:
        if not db or not hasattr(db, "execute_query"):
            warnings.append("数据库连接不可用，无法检索已有设定")
            return [], "empty"

        try:
            index_service = get_lore_index_service()
            lore_ids = await index_service.smart_search(
                project_id=project_id,
                query=setting_query,
                keywords=keywords,
                related_entities=related_entities,
                limit=limit,
            )
            if lore_ids:
                entries = await self._fetch_lore_by_ids(project_id, db, lore_ids, categories, limit)
                if entries:
                    return entries, "semantic_index"
        except Exception as exc:
            warnings.append(f"设定索引检索失败，改用关键词检索: {exc}")
            logger.warning("workflow setting adapter index search failed: %s", exc)

        entries = await self._keyword_db_search(project_id, db, setting_query, categories, limit, warnings)
        if entries:
            return entries, "keyword_db"
        return [], "empty"

    async def _fetch_lore_by_ids(
        self,
        project_id: str,
        db: Any,
        lore_ids: list[str],
        categories: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        entries_by_id: dict[str, dict[str, Any]] = {}
        category_set = {category.lower() for category in categories}
        for lore_id in lore_ids[:limit]:
            rows = await db.execute_query(
                """
                SELECT * FROM lore_entries
                WHERE id = CAST(:id AS UUID)
                AND project_id = CAST(:project_id AS UUID)
                LIMIT 1
                """,
                {"id": lore_id, "project_id": project_id},
            )
            for row in rows or []:
                entry = self._normalize_lore_entry(row)
                if not entry:
                    continue
                if category_set and str(entry.get("category", "")).lower() not in category_set:
                    continue
                entries_by_id[str(entry.get("id"))] = entry

        return [entries_by_id[lore_id] for lore_id in lore_ids if lore_id in entries_by_id][:limit]

    async def _keyword_db_search(
        self,
        project_id: str,
        db: Any,
        setting_query: str,
        categories: list[str],
        limit: int,
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        if not setting_query.strip():
            warnings.append("关键词检索缺少查询文本")
            return []

        conditions = ["project_id = CAST(:project_id AS UUID)"]
        params: dict[str, Any] = {
            "project_id": project_id,
            "query": f"%{setting_query[:500]}%",
            "limit": limit,
        }

        if categories:
            category_conditions: list[str] = []
            for index, category in enumerate(categories):
                key = f"category_{index}"
                category_conditions.append(f"category = :{key}")
                params[key] = category
            conditions.append(f"({' OR '.join(category_conditions)})")

        conditions.append(
            "(title ILIKE :query OR summary ILIKE :query OR content ILIKE :query OR keywords::text ILIKE :query OR tags::text ILIKE :query)"
        )
        where_clause = " AND ".join(conditions)
        rows = await db.execute_query(
            f"""
            SELECT * FROM lore_entries
            WHERE {where_clause}
            ORDER BY
                CASE priority
                    WHEN 'constitutional' THEN 1
                    WHEN 'core' THEN 2
                    WHEN 'standard' THEN 3
                    ELSE 4
                END,
                updated_at DESC
            LIMIT :limit
            """,
            params,
        )
        return self._normalize_lore_entries(rows or [])[:limit]

    async def _merge_constitutional_rules(
        self,
        *,
        project_id: str,
        db: Any,
        entries: list[dict[str, Any]],
        limit: int,
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        try:
            rows = await db.execute_query(
                """
                SELECT * FROM lore_entries
                WHERE project_id = CAST(:project_id AS UUID)
                AND priority = 'constitutional'
                ORDER BY created_at
                LIMIT :limit
                """,
                {"project_id": project_id, "limit": limit},
            )
        except Exception as exc:
            warnings.append(f"宪法级设定读取失败: {exc}")
            return entries

        merged: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for entry in [*self._normalize_lore_entries(rows or []), *entries]:
            entry_id = str(entry.get("id") or entry.get("title") or "")
            if entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)
            merged.append(entry)
            if len(merged) >= limit:
                break
        return merged

    def _build_output(
        self,
        selected_entries: list[dict[str, Any]],
        setting_query: str,
        setting_source: str,
        warnings: list[str],
    ) -> Dict[str, Any]:
        return {
            "lore_entries": selected_entries,
            "selected_lore_entries": selected_entries,
            "setting_updates": [],
            "new_lores": [],
            "updated_lores": [],
            "validated_lores": [],
            "setting_query": setting_query,
            "setting_source": setting_source,
            "setting_count": len(selected_entries),
            "setting_read_only": True,
            "warnings": warnings,
        }


_setting_workflow_adapter: Optional[SettingWorkflowAdapter] = None


def get_setting_workflow_adapter() -> SettingWorkflowAdapter:
    global _setting_workflow_adapter
    if _setting_workflow_adapter is None:
        _setting_workflow_adapter = SettingWorkflowAdapter()
    return _setting_workflow_adapter
