"""剧情状态变更记录与应用服务。"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.narrative import (
    NarrativeStateChange,
    NarrativeStateChangeStatus,
    NarrativeStateChangeType,
    NarrativeStateEntityType,
)


class NarrativeStateChangeService:
    """负责创建、确认、拒绝和应用剧情状态变更。"""

    def __init__(self, db: Any):
        self.db = db
        self.applier = StateChangeApplier(db)

    async def create_change(
        self,
        payload: Dict[str, Any],
        source_context: Optional[Dict[str, Any]] = None,
        default_status: str = NarrativeStateChangeStatus.PROPOSED.value,
    ) -> Dict[str, Any]:
        change_data = await self.normalize_change(payload, source_context, default_status)
        change_id = await self.db.save_narrative_state_change(change_data)
        change = await self.db.get_narrative_state_change(change_id)
        if not change:
            raise ValueError("剧情状态变更保存失败")
        return change

    async def normalize_change(
        self,
        payload: Dict[str, Any],
        source_context: Optional[Dict[str, Any]] = None,
        default_status: str = NarrativeStateChangeStatus.PROPOSED.value,
    ) -> Dict[str, Any]:
        data = dict(payload or {})
        if source_context:
            for key in [
                "workflow_execution_id",
                "workflow_id",
                "node_id",
                "agent_type",
                "chapter_id",
                "discussion_id",
                "source_text",
            ]:
                if data.get(key) is None and source_context.get(key) is not None:
                    data[key] = source_context[key]

        data["status"] = _enum_value(data.get("status") or default_status)
        data["entity_type"] = _enum_value(data.get("entity_type") or NarrativeStateEntityType.CUSTOM.value)
        data["change_type"] = _enum_value(data.get("change_type") or NarrativeStateChangeType.CUSTOM.value)
        data["before_state"] = _as_dict(data.get("before_state"))
        data["after_state"] = _as_dict(data.get("after_state"))
        data["diff"] = _as_dict(data.get("diff"))
        data["metadata"] = _as_dict(data.get("metadata"))

        if not data["before_state"]:
            data["before_state"] = await self._load_before_state(
                data.get("entity_type"),
                data.get("entity_id"),
            )

        if not data.get("fingerprint"):
            data["fingerprint"] = self.generate_fingerprint(data)

        change = NarrativeStateChange(**data)
        return change.model_dump(mode="json")

    async def list_changes(
        self,
        project_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: Optional[str] = None,
        change_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return await self.db.list_narrative_state_changes(
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            change_type=change_type,
            limit=limit,
        )

    async def get_change(self, change_id: str) -> Dict[str, Any]:
        change = await self.db.get_narrative_state_change(change_id)
        if not change:
            raise ValueError("剧情状态变更不存在")
        return change

    async def confirm_change(self, change_id: str) -> Dict[str, Any]:
        change = await self.db.get_narrative_state_change(change_id)
        if not change:
            raise ValueError("剧情状态变更不存在")
        if change.get("status") == NarrativeStateChangeStatus.APPLIED.value:
            return change
        if change.get("status") == NarrativeStateChangeStatus.REJECTED.value:
            raise ValueError("已拒绝的剧情状态变更不能确认")
        await self.db.update_narrative_state_change_status(
            change_id,
            NarrativeStateChangeStatus.CONFIRMED.value,
            "confirmed_at",
        )
        confirmed = await self.db.get_narrative_state_change(change_id)
        if not confirmed:
            raise ValueError("剧情状态变更不存在")
        return confirmed

    async def reject_change(self, change_id: str) -> Dict[str, Any]:
        change = await self.db.get_narrative_state_change(change_id)
        if not change:
            raise ValueError("剧情状态变更不存在")
        if change.get("status") == NarrativeStateChangeStatus.APPLIED.value:
            raise ValueError("已应用的剧情状态变更不能拒绝")
        await self.db.update_narrative_state_change_status(
            change_id,
            NarrativeStateChangeStatus.REJECTED.value,
            "rejected_at",
        )
        rejected = await self.db.get_narrative_state_change(change_id)
        if not rejected:
            raise ValueError("剧情状态变更不存在")
        return rejected

    async def apply_change(self, change_id: str) -> Dict[str, Any]:
        change = await self.db.get_narrative_state_change(change_id)
        if not change:
            raise ValueError("剧情状态变更不存在")
        return await self.applier.apply(change)

    async def _load_before_state(self, entity_type: Optional[str], entity_id: Optional[str]) -> Dict[str, Any]:
        if not entity_id:
            return {}
        entity_type = _enum_value(entity_type)
        if entity_type == NarrativeStateEntityType.CHARACTER.value:
            return await self.db.get_character(entity_id) or {}
        if entity_type == NarrativeStateEntityType.HOOK.value:
            return await self.db.get_hook(entity_id) or {}
        if entity_type == NarrativeStateEntityType.REGION.value:
            return await self.db.get_region(entity_id) or {}
        return {}

    def generate_fingerprint(self, data: Dict[str, Any]) -> str:
        source = {
            "project_id": data.get("project_id"),
            "entity_type": _enum_value(data.get("entity_type")),
            "entity_id": data.get("entity_id"),
            "entity_name": data.get("entity_name"),
            "change_type": _enum_value(data.get("change_type")),
            "title": data.get("title") or "",
            "summary": data.get("summary") or "",
            "after_state": _as_dict(data.get("after_state")),
            "workflow_execution_id": data.get("workflow_execution_id"),
            "node_id": data.get("node_id"),
            "discussion_id": data.get("discussion_id"),
        }
        serialized = json.dumps(source, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class StateChangeApplier:
    """将已确认的剧情状态变更投影到当前状态表。"""

    def __init__(self, db: Any):
        self.db = db

    async def apply(self, change: Dict[str, Any]) -> Dict[str, Any]:
        if change.get("status") == NarrativeStateChangeStatus.APPLIED.value:
            return {"success": True, "applied": False, "change": change, "message": "剧情状态变更已应用"}
        if change.get("status") == NarrativeStateChangeStatus.REJECTED.value:
            raise ValueError("已拒绝的剧情状态变更不能应用")
        if change.get("confirmation_required", True) and change.get("status") != NarrativeStateChangeStatus.CONFIRMED.value:
            raise ValueError("剧情状态变更尚未确认，不能应用")
        if change.get("status") == NarrativeStateChangeStatus.PROPOSED.value:
            await self.db.update_narrative_state_change_status(
                change["id"],
                NarrativeStateChangeStatus.CONFIRMED.value,
                "confirmed_at",
            )

        entity_type = _enum_value(change.get("entity_type"))
        if entity_type == NarrativeStateEntityType.CHARACTER.value:
            projection = await self._apply_character_change(change)
        elif entity_type == NarrativeStateEntityType.HOOK.value:
            projection = await self._apply_hook_change(change)
        elif entity_type == NarrativeStateEntityType.REGION.value:
            projection = await self._apply_region_change(change)
        else:
            projection = {"projection": "log_only"}

        await self.db.mark_narrative_state_change_applied(change["id"])
        applied = await self.db.get_narrative_state_change(change["id"])
        return {
            "success": True,
            "applied": True,
            "change": applied,
            "projection": projection,
        }

    async def _apply_character_change(self, change: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = change.get("entity_id")
        if not entity_id:
            raise ValueError("角色状态变更缺少 entity_id")
        character = await self.db.get_character(entity_id)
        if not character:
            raise ValueError("角色不存在，无法应用状态变更")

        after_state = _as_dict(change.get("after_state"))
        metadata = _as_dict(change.get("metadata"))
        change_type = _enum_value(change.get("change_type"))
        updated = dict(character)

        if change_type == NarrativeStateChangeType.DEATH.value:
            updated["status"] = after_state.get("status") or "dead"
            updated["death_detail"] = after_state.get("death_detail") or metadata.get("death_detail") or {
                "death_chapter": change.get("chapter_id"),
                "death_scene": change.get("summary") or change.get("title") or "",
                "cause": change.get("reason") or "",
                "witnesses": metadata.get("witnesses") or [],
                "is_confirmed": True,
                "resurrection_possible": bool(metadata.get("resurrection_possible", False)),
                "resurrection_conditions": metadata.get("resurrection_conditions"),
            }
            if change.get("reason"):
                updated["exit_reason"] = change.get("reason")
        elif change_type == NarrativeStateChangeType.RESURRECTION.value:
            updated["status"] = after_state.get("status") or "resurrected"
            updated["death_detail"] = after_state.get("death_detail")
        elif change_type == NarrativeStateChangeType.LOCATION_CHANGE.value:
            self._merge_fields(updated, after_state, [
                "world_id",
                "current_region_id",
                "current_location",
                "current_location_reason",
            ])
        else:
            self._merge_fields(updated, after_state, [
                "status",
                "world_id",
                "current_region_id",
                "current_location",
                "current_location_reason",
                "death_detail",
                "available_presence_types",
                "exit_reason",
                "exit_chapter",
                "active_arc",
            ])

        await self.db.save_character(updated)
        from app.services.graph_projection_service import enqueue_graph_projection_best_effort
        await enqueue_graph_projection_best_effort("character", updated)
        return {"projection": "character", "entity_id": entity_id}

    async def _apply_hook_change(self, change: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = change.get("entity_id")
        if not entity_id:
            raise ValueError("伏笔状态变更缺少 entity_id")
        hook = await self.db.get_hook(entity_id)
        if not hook:
            raise ValueError("伏笔不存在，无法应用状态变更")

        after_state = _as_dict(change.get("after_state"))
        change_type = _enum_value(change.get("change_type"))
        status_by_type = {
            NarrativeStateChangeType.HOOK_TRIGGERED.value: "triggered",
            NarrativeStateChangeType.HOOK_RESOLVED.value: "resolved",
            NarrativeStateChangeType.HOOK_DROPPED.value: "dropped",
        }
        status = after_state.get("status") or status_by_type.get(change_type)
        if not status:
            raise ValueError("伏笔状态变更缺少目标 status")

        updated = dict(hook)
        updated["status"] = status
        self._merge_fields(updated, after_state, [
            "resolution_context",
            "resolution_chapter",
            "resolved_at",
            "resolution_hint",
        ])
        if status == "resolved" and not updated.get("resolved_at"):
            updated["resolved_at"] = datetime.utcnow()
        await self.db.save_hook(updated)
        from app.services.graph_projection_service import enqueue_graph_projection_best_effort
        await enqueue_graph_projection_best_effort("hook", updated)
        return {"projection": "hook", "entity_id": entity_id, "status": status}

    async def _apply_region_change(self, change: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = change.get("entity_id")
        if not entity_id:
            raise ValueError("区域状态变更缺少 entity_id")
        region = await self.db.get_region(entity_id)
        if not region:
            raise ValueError("区域不存在，无法应用状态变更")

        after_state = _as_dict(change.get("after_state"))
        change_type = _enum_value(change.get("change_type"))
        updated = dict(region)
        if change_type == NarrativeStateChangeType.REGION_DESTROYED.value:
            updated["state"] = after_state.get("state") or "destroyed"
            updated["state_summary"] = after_state.get("state_summary") or change.get("summary") or change.get("reason") or ""
            updated["destroyed_at"] = after_state.get("destroyed_at") or datetime.utcnow()
        else:
            self._merge_fields(updated, after_state, ["state", "state_summary", "destroyed_at"])
        await self.db.save_region(updated)
        from app.services.graph_projection_service import enqueue_graph_projection_best_effort
        await enqueue_graph_projection_best_effort("region", updated)
        return {"projection": "region", "entity_id": entity_id, "state": updated.get("state")}

    def _merge_fields(self, target: Dict[str, Any], source: Dict[str, Any], fields: List[str]) -> None:
        for field in fields:
            if field in source:
                target[field] = source[field]


def _enum_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
