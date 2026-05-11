"""Assistant Context Fabric facade."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.models.assistant_context import AssistantContextBudget
from app.services.assistant_context.budgets import budget_for_surface
from app.services.assistant_context.delta_service import ContextDeltaService
from app.services.assistant_context.observability import AssistantContextObservability
from app.services.assistant_context.packet_builder import ContextPacketBuilder
from app.services.assistant_context.session_service import AssistantSessionService
from app.services.assistant_context.snapshot_service import ProjectSnapshotService


class AssistantContextFabricService:
    def __init__(self, db: Any):
        self.db = db
        self.sessions = AssistantSessionService(db)
        self.snapshots = ProjectSnapshotService(db)
        self.deltas = ContextDeltaService(db)
        self.packet_builder = ContextPacketBuilder()
        self.observability = AssistantContextObservability()

    async def build_packet(
        self,
        *,
        project_id: str,
        assistant_surface: str,
        task_type: str = "chat",
        session_id: Optional[str] = None,
        mode: str = "default",
        request_id: Optional[str] = None,
        scope: Optional[Dict[str, Any]] = None,
        budget: Optional[AssistantContextBudget] = None,
        user_message: Optional[str] = None,
        force_reread: bool = False,
        reset_history: bool = False,
    ) -> Dict[str, Any]:
        scope = scope or {}
        snapshot = await self.snapshots.force_rebuild(project_id, request_id=request_id) if force_reread else await self.snapshots.get_or_build_snapshot(project_id)
        session = await self.sessions.get_or_create_session(
            project_id=project_id,
            assistant_surface=assistant_surface,
            mode=mode,
            session_id=session_id,
            snapshot=snapshot,
            session_state={"scope": scope},
        )
        history_reset_result = None
        if reset_history:
            history_reset_result = await self.sessions.reset_history(
                session_id=session["id"],
                reason="packet_build_reset",
                clear_pending_items=False,
                delete_message_records=True,
                snapshot=snapshot,
            )
            session = await self.db.get_assistant_session(history_reset_result["new_session_id"])
        sections = await self.db.get_assistant_snapshot_sections(str(snapshot["id"]))
        deltas = await self.deltas.list_recent(project_id, limit=50, consumed=False)
        selected_budget = budget_for_surface(assistant_surface, budget)
        built = self.packet_builder.build(
            project_id=project_id,
            assistant_surface=assistant_surface,
            task_type=task_type,
            snapshot=snapshot,
            sections=sections,
            deltas=deltas,
            session=session,
            scope=scope,
            budget=selected_budget,
            force_reread=force_reread,
            history_reset_applied=reset_history,
        )
        packet_data = built["packet_data"]
        packet_data["request_id"] = request_id
        packet_id = await self.db.save_assistant_packet(packet_data)
        metadata = dict(built["metadata"])
        metadata.update({
            "packet_id": packet_id,
            "snapshot_id": str(snapshot["id"]),
            "snapshot_version": snapshot.get("snapshot_version"),
        })
        await self.observability.record_packet_built(packet_id, metadata)
        if user_message:
            await self.sessions.append_message(
                session=session,
                role="user",
                content=user_message,
                request_id=request_id,
                metadata={"context_packet_id": packet_id},
                packet_id=packet_id,
                snapshot_id=str(snapshot["id"]),
            )
        return {
            "packet_id": packet_id,
            "snapshot_id": str(snapshot["id"]),
            "snapshot_version": snapshot.get("snapshot_version"),
            "session_id": session["id"],
            "prompt_context": built["prompt_context"],
            "history_window": built["history_window"],
            "history_summary": built["history_summary"],
            "metadata": metadata,
            "history_reset": history_reset_result,
        }

    async def create_or_get_session(self, *, project_id: str, assistant_surface: str, mode: str = "default", session_id: Optional[str] = None, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        snapshot = await self.snapshots.get_or_build_snapshot(project_id)
        return await self.sessions.get_or_create_session(
            project_id=project_id,
            assistant_surface=assistant_surface,
            mode=mode,
            session_id=session_id,
            snapshot=snapshot,
            session_state={"scope": scope or {}},
        )

    async def reset_history(self, *, project_id: str, session_id: str, clear_pending_items: bool = False, delete_message_records: bool = True, reason: str = "user_requested") -> Dict[str, Any]:
        snapshot = await self.snapshots.get_or_build_snapshot(project_id)
        result = await self.sessions.reset_history(
            session_id=session_id,
            reason=reason,
            clear_pending_items=clear_pending_items,
            delete_message_records=delete_message_records,
            snapshot=snapshot,
        )
        await self.observability.record_history_reset({"project_id": project_id, **result})
        return result

    async def force_reread(self, *, project_id: str, assistant_surface: str, session_id: Optional[str] = None, mode: str = "default", clear_history: bool = False, clear_pending_items: bool = False, request_id: Optional[str] = None, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        previous = await self.db.get_latest_assistant_snapshot(project_id, status=None)
        snapshot = await self.snapshots.force_rebuild(project_id, request_id=request_id)
        session = None
        reset_result = None
        if session_id:
            session = await self.db.get_assistant_session(session_id)
        if clear_history and session:
            reset_result = await self.sessions.reset_history(
                session_id=session_id,
                reason="force_reread_with_history_reset",
                clear_pending_items=clear_pending_items,
                delete_message_records=True,
                snapshot=snapshot,
            )
            session_id = reset_result["new_session_id"]
        elif session:
            session.update({
                "snapshot_id": snapshot.get("id"),
                "snapshot_version": snapshot.get("snapshot_version"),
                "context_cursor": {
                    "snapshot_id": str(snapshot.get("id")),
                    "snapshot_version": snapshot.get("snapshot_version"),
                    "source_revision_hash": snapshot.get("source_revision_hash"),
                    "content_hash": snapshot.get("content_hash"),
                },
            })
            await self.db.save_assistant_session(session)
        metadata = {
            "packet_id": None,
            "snapshot_id": str(snapshot["id"]),
            "snapshot_version": snapshot.get("snapshot_version"),
            "assistant_surface": assistant_surface,
            "invalidation_state": "force_rebuilt",
            "force_reread": True,
            "history_reset_applied": bool(reset_result),
            "token_estimate": int(snapshot.get("token_estimate") or 0),
            "selected_sections": [],
            "omitted_sections": [],
            "delta_count": 0,
            "rebuilt_at": snapshot.get("built_at"),
        }
        await self.observability.record_force_reread({"project_id": project_id, "session_id": session_id, **metadata})
        return {
            "project_id": project_id,
            "session_id": session_id,
            "snapshot": snapshot,
            "previous_snapshot": previous,
            "history_cleared": bool(reset_result),
            "reset_result": reset_result,
            "packet_metadata": metadata,
        }


_fabric_instances: Dict[int, AssistantContextFabricService] = {}


def get_assistant_context_fabric(db: Any) -> AssistantContextFabricService:
    key = id(db)
    if key not in _fabric_instances:
        _fabric_instances[key] = AssistantContextFabricService(db)
    return _fabric_instances[key]
