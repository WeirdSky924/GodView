"""Generalized assistant session persistence and history operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.assistant_context import new_assistant_session_id
from app.services.assistant_context.utils import hash_text, stable_json


class AssistantSessionService:
    def __init__(self, db: Any):
        self.db = db

    async def get_or_create_session(
        self,
        *,
        project_id: str,
        assistant_surface: str,
        mode: str = "default",
        session_id: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if session_id:
            existing = await self.db.get_assistant_session(session_id)
            if (
                existing
                and str(existing.get("project_id")) == str(project_id)
                and str(existing.get("assistant_surface") or "") == str(assistant_surface)
                and str(existing.get("mode") or "default") == str(mode or "default")
            ):
                return existing

        active = await self.db.get_active_assistant_session(project_id, assistant_surface, mode)
        if active:
            return active

        data = {
            "id": new_assistant_session_id(assistant_surface),
            "project_id": project_id,
            "assistant_surface": assistant_surface,
            "mode": mode,
            "status": "active",
            "snapshot_id": snapshot.get("id") if snapshot else None,
            "snapshot_version": snapshot.get("snapshot_version") if snapshot else None,
            "history_window": [],
            "history_summary": "",
            "history_summary_hash": None,
            "session_state": session_state or {},
            "pending_items": [],
            "context_cursor": self._snapshot_cursor(snapshot),
            "last_activity_at": datetime.utcnow(),
        }
        await self.db.save_assistant_session(data)
        return await self.db.get_assistant_session(data["id"]) or data

    async def append_message(
        self,
        *,
        session: Dict[str, Any],
        role: str,
        content: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        packet_id: Optional[str] = None,
        snapshot_id: Optional[str] = None,
    ) -> str:
        message_id = await self.db.append_assistant_message(
            session_id=session["id"],
            project_id=str(session["project_id"]),
            role=role,
            content=content,
            request_id=request_id,
            metadata=metadata or {},
            packet_id=packet_id,
            snapshot_id=snapshot_id,
        )
        messages = await self.db.get_assistant_messages(session["id"], limit=40)
        history_window = [self._message_to_window_item(item) for item in messages[-12:]]
        history_summary = session.get("history_summary") or ""
        if len(messages) > 12:
            history_summary = self._summarize_messages(messages[:-12])
        updated = dict(session)
        updated.update({
            "history_window": history_window,
            "history_summary": history_summary,
            "history_summary_hash": hash_text(history_summary) if history_summary else None,
            "last_activity_at": datetime.utcnow(),
        })
        await self.db.save_assistant_session(updated)
        return message_id

    async def get_history(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        return await self.db.get_assistant_messages(session_id, limit=limit)

    async def reset_history(
        self,
        *,
        session_id: str,
        reason: str = "user_requested",
        clear_pending_items: bool = False,
        delete_message_records: bool = True,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        old_session = await self.db.get_assistant_session(session_id)
        if not old_session:
            raise ValueError("assistant session not found")
        old_messages = await self.db.get_assistant_messages(session_id, limit=10000)
        messages_deleted = 0
        messages_archived = 0
        if delete_message_records:
            messages_deleted = await self.db.delete_assistant_messages(session_id)
        else:
            messages_archived = len(old_messages)
        await self.db.reset_assistant_session(session_id, reason=reason)
        pending_items = [] if clear_pending_items else (old_session.get("pending_items") or [])
        active_collision = await self.db.get_active_assistant_session(
            str(old_session["project_id"]),
            old_session["assistant_surface"],
            old_session.get("mode") or "default",
        )
        if active_collision:
            return {
                "old_session_id": session_id,
                "new_session_id": active_collision["id"],
                "messages_deleted": messages_deleted,
                "messages_archived": messages_archived,
                "pending_items_cleared": clear_pending_items,
                "snapshot_id": active_collision.get("snapshot_id"),
                "snapshot_version": active_collision.get("snapshot_version"),
            }
        new_session_data = {
            "id": new_assistant_session_id(str(old_session.get("assistant_surface") or "assistant")),
            "project_id": str(old_session["project_id"]),
            "assistant_surface": old_session["assistant_surface"],
            "mode": old_session.get("mode") or "default",
            "status": "active",
            "snapshot_id": (snapshot or old_session).get("snapshot_id"),
            "snapshot_version": (snapshot or old_session).get("snapshot_version"),
            "history_window": [],
            "history_summary": "",
            "history_summary_hash": None,
            "session_state": old_session.get("session_state") or {},
            "pending_items": pending_items,
            "context_cursor": self._snapshot_cursor(snapshot) if snapshot else (old_session.get("context_cursor") or {}),
            "last_activity_at": datetime.utcnow(),
            "reset_reason": None,
            "reset_at": None,
        }
        await self.db.save_assistant_session(new_session_data)
        return {
            "old_session_id": session_id,
            "new_session_id": new_session_data["id"],
            "messages_deleted": messages_deleted,
            "messages_archived": messages_archived,
            "pending_items_cleared": clear_pending_items,
            "snapshot_id": new_session_data.get("snapshot_id"),
            "snapshot_version": new_session_data.get("snapshot_version"),
        }

    def _message_to_window_item(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "role": message.get("role"),
            "content": message.get("content", ""),
            "request_id": message.get("request_id"),
            "created_at": str(message.get("created_at")) if message.get("created_at") else None,
        }

    def _summarize_messages(self, messages: List[Dict[str, Any]]) -> str:
        compact = []
        for msg in messages[-20:]:
            role = msg.get("role", "unknown")
            content = str(msg.get("content") or "").strip().replace("\n", " ")
            compact.append(f"{role}: {content[:180]}")
        summary = "\n".join(compact)
        if len(messages) > 20:
            summary = f"已压缩更早 {len(messages) - 20} 条消息。\n" + summary
        return summary

    def _snapshot_cursor(self, snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not snapshot:
            return {}
        return {
            "snapshot_id": str(snapshot.get("id")),
            "snapshot_version": snapshot.get("snapshot_version"),
            "source_revision_hash": snapshot.get("source_revision_hash"),
            "content_hash": snapshot.get("content_hash"),
        }

    def session_fingerprint(self, session: Dict[str, Any]) -> str:
        return hash_text(stable_json({
            "id": session.get("id"),
            "surface": session.get("assistant_surface"),
            "mode": session.get("mode"),
            "history_summary": session.get("history_summary"),
            "history_window": session.get("history_window") or [],
        }))
