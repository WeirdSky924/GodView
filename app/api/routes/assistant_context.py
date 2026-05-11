"""Unified Assistant Context Fabric API routes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.assistant_context import (
    AssistantContextSessionCreateRequest,
    AssistantForceRereadRequest,
    AssistantForceRereadResponse,
    AssistantHistoryResetRequest,
    AssistantHistoryResetResponse,
    AssistantHistoryResponse,
    AssistantMessageResponse,
    AssistantPacketResponse,
    AssistantSessionResponse,
    AssistantSnapshotStatusResponse,
)
from app.services.assistant_context import get_assistant_context_fabric

router = APIRouter()


def _db():
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")
    return postgres_db


def _fabric():
    return get_assistant_context_fabric(_db())


def _session_response(row: Dict[str, Any]) -> AssistantSessionResponse:
    return AssistantSessionResponse(
        session_id=str(row["id"]),
        project_id=str(row["project_id"]),
        assistant_surface=row.get("assistant_surface"),
        mode=row.get("mode") or "default",
        status=row.get("status") or "active",
        snapshot_id=str(row.get("snapshot_id")) if row.get("snapshot_id") else None,
        snapshot_version=row.get("snapshot_version"),
        history_summary=row.get("history_summary") or "",
        history_window=row.get("history_window") or [],
        pending_items=row.get("pending_items") or [],
        context_cursor=row.get("context_cursor") or {},
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _message_response(row: Dict[str, Any]) -> AssistantMessageResponse:
    return AssistantMessageResponse(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        role=row.get("role"),
        content=row.get("content") or "",
        request_id=row.get("request_id"),
        metadata=row.get("metadata") or {},
        packet_id=str(row.get("packet_id")) if row.get("packet_id") else None,
        snapshot_id=str(row.get("snapshot_id")) if row.get("snapshot_id") else None,
        created_at=row.get("created_at"),
    )


@router.post("/{project_id}/sessions", response_model=AssistantSessionResponse)
async def create_assistant_session(project_id: str, request: AssistantContextSessionCreateRequest):
    project = await _db().get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    session = await _fabric().create_or_get_session(
        project_id=project_id,
        assistant_surface=request.assistant_surface.value,
        mode=request.mode,
        session_id=request.session_id,
        scope=request.scope,
    )
    return _session_response(session)


@router.get("/{project_id}/sessions/{session_id}/history", response_model=AssistantHistoryResponse)
async def get_assistant_history(project_id: str, session_id: str, limit: int = Query(default=200, ge=1, le=500)):
    session = await _db().get_assistant_session(session_id)
    if not session or str(session.get("project_id")) != str(project_id):
        raise HTTPException(status_code=404, detail="助手会话不存在")
    messages = await _db().get_assistant_messages(session_id, limit=limit)
    return AssistantHistoryResponse(
        session=_session_response(session),
        messages=[_message_response(row) for row in messages],
    )


@router.post("/{project_id}/sessions/{session_id}/reset-history", response_model=AssistantHistoryResetResponse)
async def reset_assistant_history(project_id: str, session_id: str, request: AssistantHistoryResetRequest):
    session = await _db().get_assistant_session(session_id)
    if not session or str(session.get("project_id")) != str(project_id):
        raise HTTPException(status_code=404, detail="助手会话不存在")
    if session.get("assistant_surface") != request.assistant_surface.value:
        raise HTTPException(status_code=400, detail="助手 surface 与会话不匹配")
    result = await _fabric().reset_history(
        project_id=project_id,
        session_id=session_id,
        clear_pending_items=request.clear_pending_items,
        delete_message_records=request.delete_message_records,
        reason=request.reason,
    )
    return AssistantHistoryResetResponse(**result)


@router.post("/{project_id}/force-reread", response_model=AssistantForceRereadResponse)
async def force_reread_project(project_id: str, request: AssistantForceRereadRequest):
    project = await _db().get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if request.session_id:
        session = await _db().get_assistant_session(request.session_id)
        if not session or str(session.get("project_id")) != str(project_id):
            raise HTTPException(status_code=404, detail="助手会话不存在")
    result = await _fabric().force_reread(
        project_id=project_id,
        assistant_surface=request.assistant_surface.value,
        session_id=request.session_id,
        mode=request.mode,
        clear_history=request.clear_history,
        clear_pending_items=request.clear_pending_items,
        request_id=request.request_id,
        scope=request.scope,
    )
    snapshot = result["snapshot"]
    previous = result.get("previous_snapshot") or {}
    return AssistantForceRereadResponse(
        project_id=project_id,
        session_id=result.get("session_id"),
        snapshot_id=str(snapshot["id"]),
        snapshot_version=int(snapshot.get("snapshot_version") or 1),
        previous_snapshot_id=str(previous.get("id")) if previous.get("id") else None,
        previous_snapshot_version=previous.get("snapshot_version"),
        history_cleared=result.get("history_cleared", False),
        packet_metadata=result["packet_metadata"],
    )


@router.post("/{project_id}/sessions/{session_id}/reset-and-reread", response_model=AssistantForceRereadResponse)
async def reset_and_reread(project_id: str, session_id: str, request: AssistantForceRereadRequest):
    request.session_id = session_id
    request.clear_history = True
    return await force_reread_project(project_id, request)


@router.get("/{project_id}/snapshots/latest", response_model=AssistantSnapshotStatusResponse)
async def latest_snapshot(project_id: str):
    snapshot = await _db().get_latest_assistant_snapshot(project_id, status=None)
    deltas = await _db().get_assistant_deltas(project_id, limit=1000, consumed=False)
    if not snapshot:
        return AssistantSnapshotStatusResponse(project_id=project_id, stale_delta_count=len(deltas))
    return AssistantSnapshotStatusResponse(
        project_id=project_id,
        snapshot_id=str(snapshot.get("id")),
        snapshot_version=snapshot.get("snapshot_version"),
        status=snapshot.get("status") or "stale",
        source_revision_hash=snapshot.get("source_revision_hash"),
        content_hash=snapshot.get("content_hash"),
        token_estimate=int(snapshot.get("token_estimate") or 0),
        stale_delta_count=len(deltas),
        build_reason=snapshot.get("build_reason"),
        built_at=snapshot.get("built_at"),
        error_message=snapshot.get("error_message"),
    )


@router.get("/{project_id}/packets/{packet_id}", response_model=AssistantPacketResponse)
async def get_packet(project_id: str, packet_id: str):
    packet = await _db().get_assistant_packet(packet_id)
    if not packet or str(packet.get("project_id")) != str(project_id):
        raise HTTPException(status_code=404, detail="上下文包不存在")
    return AssistantPacketResponse(
        packet_id=str(packet["id"]),
        project_id=str(packet["project_id"]),
        session_id=packet.get("session_id"),
        assistant_surface=packet.get("assistant_surface"),
        request_id=packet.get("request_id"),
        snapshot_id=str(packet.get("snapshot_id")) if packet.get("snapshot_id") else None,
        snapshot_version=packet.get("snapshot_version"),
        packet_scope=packet.get("packet_scope") or {},
        budget=packet.get("budget") or {},
        selected_sections=packet.get("selected_sections") or [],
        delta_ids=packet.get("delta_ids") or [],
        retrieval_manifest=packet.get("retrieval_manifest") or {},
        token_estimate=int(packet.get("token_estimate") or 0),
        truncated=bool(packet.get("truncated")),
        invalidation_state=packet.get("invalidation_state") or "fresh",
        force_reread=bool(packet.get("force_reread")),
        history_reset_applied=bool(packet.get("history_reset_applied")),
        metadata=packet.get("metadata") or {},
        content_hash=packet.get("content_hash"),
        created_at=packet.get("created_at"),
    )


@router.get("/{project_id}/health", response_model=Dict[str, Any])
async def assistant_context_health(project_id: str):
    snapshot = await _db().get_latest_assistant_snapshot(project_id, status=None)
    deltas = await _db().get_assistant_deltas(project_id, limit=1000, consumed=False)
    return {
        "project_id": project_id,
        "latest_snapshot": {
            "id": str(snapshot.get("id")) if snapshot else None,
            "version": snapshot.get("snapshot_version") if snapshot else None,
            "status": snapshot.get("status") if snapshot else "missing",
            "built_at": snapshot.get("built_at") if snapshot else None,
            "error_message": snapshot.get("error_message") if snapshot else None,
        },
        "stale_delta_count": len(deltas),
        "healthy": bool(snapshot and snapshot.get("status") == "ready"),
    }
