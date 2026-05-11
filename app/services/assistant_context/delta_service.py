"""Assistant Context Fabric delta recording."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.assistant_context.utils import hash_value


class ContextDeltaService:
    def __init__(self, db: Any):
        self.db = db

    async def record_entity_change(
        self,
        *,
        project_id: str,
        entity_type: str,
        entity_id: str,
        operation: str,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        payload_summary: Optional[Dict[str, Any]] = None,
        source_table: Optional[str] = None,
        source_updated_at: Any = None,
    ) -> str:
        summary = payload_summary or self._summary(entity_type, entity_id, before, after)
        return await self.db.save_assistant_delta({
            "project_id": project_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "operation": operation,
            "before_hash": hash_value(before) if before else None,
            "after_hash": hash_value(after) if after else None,
            "payload_summary": summary,
            "source_table": source_table,
            "source_updated_at": source_updated_at,
        })

    async def list_recent(self, project_id: str, limit: int = 100, consumed: Optional[bool] = None):
        return await self.db.get_assistant_deltas(project_id, limit=limit, consumed=consumed)

    def _summary(self, entity_type: str, entity_id: str, before: Optional[Dict[str, Any]], after: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        source = after or before or {}
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "title": source.get("title") or source.get("name") or source.get("summary") or entity_id,
            "status": source.get("status"),
        }
