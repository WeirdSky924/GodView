"""Project snapshot builder for Assistant Context Fabric."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.services.assistant_context.utils import compact_text, estimate_tokens, hash_text, hash_value, stable_json


class ProjectSnapshotService:
    def __init__(self, db: Any):
        self.db = db

    async def get_latest_ready_snapshot(self, project_id: str) -> Optional[Dict[str, Any]]:
        return await self.db.get_latest_assistant_snapshot(project_id, status="ready")

    async def build_snapshot(
        self,
        project_id: str,
        *,
        build_reason: str = "initial",
        force_rebuild_request_id: Optional[str] = None,
        forced_by_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        previous = await self.db.get_latest_assistant_snapshot(project_id, status=None)
        version = int(previous.get("snapshot_version") or 0) + 1 if previous else 1
        source = await self._load_project_source(project_id)
        sections = self._build_sections(project_id, source)
        source_revision_hash = hash_value(self._revision_source(source))
        content_hash = hash_value([section["content_hash"] for section in sections])
        summary = self._build_summary(source, sections)
        token_estimate = sum(int(section.get("token_estimate") or 0) for section in sections)
        snapshot_id = str(uuid4())
        snapshot_data = {
            "id": snapshot_id,
            "project_id": project_id,
            "snapshot_version": version,
            "status": "ready",
            "source_revision_hash": source_revision_hash,
            "content_hash": content_hash,
            "summary": summary,
            "structured_index": self._structured_index(source),
            "entity_index": self._entity_index(source),
            "retrieval_manifest": {
                "section_count": len(sections),
                "section_types": sorted({section["section_type"] for section in sections}),
            },
            "token_estimate": token_estimate,
            "build_reason": build_reason,
            "forced_by_user_id": forced_by_user_id,
            "force_rebuild_request_id": force_rebuild_request_id,
            "built_at": datetime.utcnow(),
            "error_message": None,
        }
        await self.db.save_assistant_snapshot(snapshot_data, sections)
        await self.db.mark_assistant_snapshots_stale(project_id, except_snapshot_id=snapshot_id)
        return await self.db.get_latest_assistant_snapshot(project_id, status="ready") or snapshot_data

    async def get_or_build_snapshot(self, project_id: str) -> Dict[str, Any]:
        snapshot = await self.get_latest_ready_snapshot(project_id)
        if snapshot:
            return snapshot
        return await self.build_snapshot(project_id, build_reason="initial")

    async def force_rebuild(
        self,
        project_id: str,
        *,
        request_id: Optional[str] = None,
        forced_by_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        await self.db.mark_assistant_snapshots_stale(project_id)
        return await self.build_snapshot(
            project_id,
            build_reason="manual_force_rebuild",
            force_rebuild_request_id=request_id,
            forced_by_user_id=forced_by_user_id,
        )

    async def _load_project_source(self, project_id: str) -> Dict[str, Any]:
        project = await self.db.get_project(project_id) or {}
        worlds = await self.db.get_worlds_by_project(project_id, limit=200)
        characters = await self.db.get_all_characters(project_id=project_id, limit=500)
        lores = await self.db.execute_query(
            """
            SELECT id, title, category, priority, summary, content, keywords, updated_at, created_at
            FROM lore_entries
            WHERE project_id = CAST(:project_id AS UUID)
            ORDER BY
                CASE priority WHEN 'constitutional' THEN 1 WHEN 'core' THEN 2 WHEN 'standard' THEN 3 ELSE 4 END,
                updated_at DESC NULLS LAST,
                created_at DESC
            LIMIT 1000
            """,
            {"project_id": project_id},
        )
        hooks = await self.db.execute_query(
            """
            SELECT id, title, description, hook_type, status, plant_chapter, resolution_chapter, created_at, resolved_at
            FROM hooks
            WHERE project_id = CAST(:project_id AS UUID)
            ORDER BY created_at DESC
            LIMIT 500
            """,
            {"project_id": project_id},
        )
        outlines = await self.db.execute_query(
            """
            SELECT id, chapter_number, title, summary, status, updated_at, created_at
            FROM chapter_outlines
            WHERE project_id = :project_id
            ORDER BY chapter_number ASC, updated_at DESC NULLS LAST
            LIMIT 500
            """,
            {"project_id": project_id},
        )
        regions = await self.db.execute_query(
            """
            SELECT r.id, r.name, r.world_id, r.region_type, r.terrain_type, r.description,
                   r.atmosphere, r.connections, r.updated_at, r.created_at, w.name AS world_name
            FROM regions r
            JOIN worlds w ON w.id = r.world_id
            WHERE w.project_id = CAST(:project_id AS UUID)
            ORDER BY w.name ASC, r.name ASC
            LIMIT 1000
            """,
            {"project_id": project_id},
        )
        return {
            "project": project,
            "worlds": worlds,
            "characters": characters,
            "lores": lores,
            "hooks": hooks,
            "outlines": outlines,
            "regions": regions,
        }

    def _build_sections(self, project_id: str, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []
        project = source.get("project") or {}
        sections.append(self._section(
            project_id,
            "project_brief",
            "project",
            project.get("name") or project.get("title") or "Project",
            f"项目：{project.get('name') or project.get('title') or '未命名'}\n描述：{compact_text(project.get('description'), 1800)}",
            project,
            [{"type": "project", "id": str(project.get("id") or project_id)}],
            10,
        ))
        if source.get("worlds"):
            content = "\n\n".join(
                f"世界：{item.get('name') or '未命名'}\n类型：{item.get('world_type') or ''}\n基调：{item.get('tone') or ''}\n描述：{compact_text(item.get('description'), 1200)}"
                for item in source["worlds"]
            )
            sections.append(self._section(project_id, "world", "worlds", "世界设定", content, {"count": len(source["worlds"])}, self._refs("world", source["worlds"]), 20))
        sections.extend(self._grouped_entity_sections(project_id, "lore", source.get("lores") or [], "设定", 30, ["title", "category", "priority", "summary", "content"]))
        sections.extend(self._grouped_entity_sections(project_id, "characters", source.get("characters") or [], "角色", 35, ["name", "role", "personality", "background_story", "importance_tier", "status"]))
        sections.extend(self._grouped_entity_sections(project_id, "plot_hooks", source.get("hooks") or [], "伏笔", 45, ["title", "hook_type", "status", "description"]))
        sections.extend(self._grouped_entity_sections(project_id, "chapter_outlines", source.get("outlines") or [], "大纲", 50, ["chapter_number", "title", "status", "summary"]))
        sections.extend(self._grouped_entity_sections(project_id, "map_regions", source.get("regions") or [], "地图区域", 55, ["world_name", "name", "region_type", "terrain_type", "description", "atmosphere"]))
        return sections

    def _grouped_entity_sections(self, project_id: str, section_type: str, rows: List[Dict[str, Any]], title: str, priority: int, fields: List[str]) -> List[Dict[str, Any]]:
        if not rows:
            return []
        chunks = [rows[index:index + 40] for index in range(0, len(rows), 40)]
        sections = []
        for idx, chunk in enumerate(chunks, start=1):
            lines = []
            for item in chunk:
                parts = []
                for field in fields:
                    value = item.get(field)
                    if value not in (None, "", [], {}):
                        parts.append(f"{field}: {compact_text(value, 700)}")
                lines.append("；".join(parts))
            sections.append(self._section(
                project_id,
                section_type,
                f"{section_type}:{idx}",
                f"{title} {idx}",
                "\n".join(lines),
                {"count": len(chunk), "chunk": idx},
                self._refs(section_type, chunk),
                priority,
            ))
        return sections

    def _section(self, project_id: str, section_type: str, scope_key: str, title: str, content: str, payload: Dict[str, Any], refs: List[Dict[str, Any]], priority: int) -> Dict[str, Any]:
        content_hash = hash_text(content)
        return {
            "project_id": project_id,
            "section_type": section_type,
            "scope_key": scope_key,
            "title": title,
            "content": content,
            "structured_payload": payload,
            "entity_refs": refs,
            "priority": priority,
            "content_hash": content_hash,
            "token_estimate": estimate_tokens(content),
        }

    def _refs(self, entity_type: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{"type": entity_type, "id": str(row.get("id")), "title": row.get("title") or row.get("name")} for row in rows if row.get("id")]

    def _revision_source(self, source: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, rows in source.items():
            if isinstance(rows, list):
                result[key] = [{"id": str(row.get("id")), "updated_at": str(row.get("updated_at") or row.get("created_at") or "")} for row in rows]
            elif isinstance(rows, dict):
                result[key] = {"id": str(rows.get("id")), "updated_at": str(rows.get("updated_at") or rows.get("created_at") or "")}
        return result

    def _structured_index(self, source: Dict[str, Any]) -> Dict[str, Any]:
        return {key: len(value) for key, value in source.items() if isinstance(value, list)}

    def _entity_index(self, source: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: [str(row.get("id")) for row in rows if row.get("id")]
            for key, rows in source.items()
            if isinstance(rows, list)
        }

    def _build_summary(self, source: Dict[str, Any], sections: List[Dict[str, Any]]) -> str:
        project = source.get("project") or {}
        return (
            f"项目 {project.get('name') or project.get('title') or project.get('id')} 的上下文快照："
            f"{len(source.get('worlds') or [])} 个世界，"
            f"{len(source.get('lores') or [])} 条设定，"
            f"{len(source.get('characters') or [])} 个角色，"
            f"{len(source.get('hooks') or [])} 条伏笔，"
            f"{len(source.get('outlines') or [])} 个大纲，"
            f"{len(source.get('regions') or [])} 个地图区域，"
            f"{len(sections)} 个分段。"
        )
