"""Unified assistant context fabric models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AssistantSurface(str, Enum):
    SETTING_AGENT = "setting_agent"
    BOOTSTRAP_SETTING_AGENT = "bootstrap_setting_agent"
    PLOT_OUTLINE_AGENT = "plot_outline_agent"
    WORKFLOW_INTERVENTION = "workflow_intervention"
    WORLD_MAP_AGENT = "world_map_agent"
    VOLUME_PLANNING = "volume_planning"
    OUTLINE_GENERATION = "outline_generation"


class AssistantSessionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    RESET = "reset"


class SnapshotStatus(str, Enum):
    BUILDING = "building"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"


class SnapshotBuildReason(str, Enum):
    INITIAL = "initial"
    DELTA_THRESHOLD = "delta_threshold"
    MANUAL_FORCE_REBUILD = "manual_force_rebuild"
    SCHEMA_MIGRATION = "schema_migration"
    PROJECT_IMPORT = "project_import"


class DeltaOperation(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"


class PacketInvalidationState(str, Enum):
    FRESH = "fresh"
    DELTA_APPLIED = "delta_applied"
    STALE_REBUILD_REQUIRED = "stale_rebuild_required"
    FORCE_REBUILT = "force_rebuilt"


class ContextSectionType(str, Enum):
    PROJECT_BRIEF = "project_brief"
    WORLD = "world"
    LORE = "lore"
    CHARACTERS = "characters"
    PLOT_HOOKS = "plot_hooks"
    CHAPTER_OUTLINES = "chapter_outlines"
    MAP_REGIONS = "map_regions"
    WORKFLOW_STATE = "workflow_state"
    WRITING_RULES = "writing_rules"
    AGENT_TEMPLATES = "agent_templates"


class AssistantContextBudget(BaseModel):
    max_context_tokens: int = Field(default=16000, ge=1000)
    reserved_response_tokens: int = Field(default=4000, ge=0)
    history_tokens: int = Field(default=2500, ge=0)
    snapshot_tokens: int = Field(default=9000, ge=0)
    delta_tokens: int = Field(default=1500, ge=0)
    retrieval_tokens: int = Field(default=3000, ge=0)


class AssistantContextSessionCreateRequest(BaseModel):
    assistant_surface: AssistantSurface
    mode: str = "default"
    session_id: Optional[str] = None
    scope: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None


class AssistantHistoryResetRequest(BaseModel):
    assistant_surface: AssistantSurface
    mode: str = "default"
    clear_pending_items: bool = False
    delete_message_records: bool = True
    reason: str = "user_requested"
    request_id: Optional[str] = None


class AssistantForceRereadRequest(BaseModel):
    assistant_surface: AssistantSurface
    session_id: Optional[str] = None
    mode: str = "default"
    scope: Dict[str, Any] = Field(default_factory=dict)
    clear_history: bool = False
    clear_pending_items: bool = False
    reason: str = "user_requested_after_project_update"
    request_id: Optional[str] = None


class AssistantPacketBuildRequest(BaseModel):
    assistant_surface: AssistantSurface
    task_type: str = "chat"
    session_id: Optional[str] = None
    mode: str = "default"
    request_id: Optional[str] = None
    scope: Dict[str, Any] = Field(default_factory=dict)
    budget: AssistantContextBudget = Field(default_factory=AssistantContextBudget)
    user_message: Optional[str] = None
    force_reread: bool = False
    reset_history: bool = False


class AssistantContextSummary(BaseModel):
    packet_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    snapshot_version: Optional[int] = None
    assistant_surface: Optional[str] = None
    invalidation_state: str = PacketInvalidationState.FRESH.value
    force_reread: bool = False
    history_reset_applied: bool = False
    token_estimate: int = 0
    selected_sections: List[Dict[str, Any]] = Field(default_factory=list)
    omitted_sections: List[Dict[str, Any]] = Field(default_factory=list)
    delta_count: int = 0
    rebuilt_at: Optional[datetime] = None


class AssistantSessionResponse(BaseModel):
    session_id: str
    project_id: str
    assistant_surface: str
    mode: str = "default"
    status: str = AssistantSessionStatus.ACTIVE.value
    snapshot_id: Optional[str] = None
    snapshot_version: Optional[int] = None
    history_summary: str = ""
    history_window: List[Dict[str, Any]] = Field(default_factory=list)
    pending_items: List[Dict[str, Any]] = Field(default_factory=list)
    context_cursor: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AssistantMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    packet_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    created_at: Optional[datetime] = None


class AssistantHistoryResponse(BaseModel):
    session: AssistantSessionResponse
    messages: List[AssistantMessageResponse] = Field(default_factory=list)
    context_packet: Optional[AssistantContextSummary] = None


class AssistantHistoryResetResponse(BaseModel):
    success: bool = True
    old_session_id: str
    new_session_id: str
    history_reset_at: datetime = Field(default_factory=datetime.utcnow)
    messages_deleted: int = 0
    messages_archived: int = 0
    pending_items_cleared: bool = False
    snapshot_id: Optional[str] = None
    snapshot_version: Optional[int] = None


class AssistantForceRereadResponse(BaseModel):
    success: bool = True
    project_id: str
    session_id: Optional[str] = None
    snapshot_id: str
    snapshot_version: int
    previous_snapshot_id: Optional[str] = None
    previous_snapshot_version: Optional[int] = None
    history_cleared: bool = False
    force_reread: bool = True
    packet_metadata: AssistantContextSummary


class AssistantSnapshotStatusResponse(BaseModel):
    project_id: str
    snapshot_id: Optional[str] = None
    snapshot_version: Optional[int] = None
    status: str = SnapshotStatus.STALE.value
    source_revision_hash: Optional[str] = None
    content_hash: Optional[str] = None
    token_estimate: int = 0
    stale_delta_count: int = 0
    build_reason: Optional[str] = None
    built_at: Optional[datetime] = None
    error_message: Optional[str] = None


class AssistantPacketResponse(BaseModel):
    packet_id: str
    project_id: str
    session_id: Optional[str] = None
    assistant_surface: str
    request_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    snapshot_version: Optional[int] = None
    packet_scope: Dict[str, Any] = Field(default_factory=dict)
    budget: Dict[str, Any] = Field(default_factory=dict)
    selected_sections: List[Dict[str, Any]] = Field(default_factory=list)
    delta_ids: List[str] = Field(default_factory=list)
    retrieval_manifest: Dict[str, Any] = Field(default_factory=dict)
    token_estimate: int = 0
    truncated: bool = False
    invalidation_state: str = PacketInvalidationState.FRESH.value
    force_reread: bool = False
    history_reset_applied: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content_hash: Optional[str] = None
    created_at: Optional[datetime] = None


def new_assistant_session_id(surface: str) -> str:
    prefix = "as"
    safe_surface = "".join(ch for ch in surface if ch.isalnum())[:8] or "session"
    return f"{prefix}_{safe_surface}_{uuid4().hex[:12]}"
