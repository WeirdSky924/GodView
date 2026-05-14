"""Workflow state helpers for reliable stateful orchestration.

The physical store remains ``WorkflowExecution.context`` for compatibility, but
all workflow runtime code should use these helpers for protected state updates,
node-output namespacing, and persistence traces.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from app.models.workflow_execution import WorkflowExecution


CANONICAL_STATE_KEYS = {
    "project_id",
    "world_id",
    "chapter_num",
    "chapter_outline_id",
    "chapter_outline",
    "chapter_title",
    "chapter_summary",
    "chapter_goals",
    "target_word_count",
    "chapter_target_word_count",
}

RETRIEVED_STATE_KEYS = {
    "fixed_lore_entries",
    "dynamic_lore_entries",
    "selected_lore_entries",
    "previous_chapters",
    "chapter_summaries",
    "characters",
    "hooks",
    "existing_hooks",
    "existing_regions",
}

RUNTIME_STATE_KEYS = {
    "scene_directions",
    "performers",
    "mentioned_characters",
    "background_characters",
    "unavailable_characters",
    "participation_trace",
    "participation_warnings",
    "writing_plan",
    "plot_guidance",
    "scene_integration_plan",
    "master_scene_plan",
    "scene_plan",
    "scene_plan_id",
    "scene_plan_attempt",
    "scene_plan_checksum",
    "scene_plan_provenance",
    "scene_plan_history",
    "writer_brief",
    "evaluator_checklist",
    "master_revision_directive",
    "revision_directive",
    "revision_directive_id",
    "revision_directive_attempt",
    "revision_directive_checksum",
    "revision_directive_history",
    "writer_revision_brief",
    "evaluator_focus",
    "quality_failure_packet",
    "performance_result",
    "role_performance_context",
    "scene_performance_context",
    "character_performance_packets",
    "public_performances",
    "private_performances",
    "relationship_deltas",
    "state_deltas",
    "continuity_notes",
    "performance_warnings",
    "role_performance_gate",
    "role_performance_gate_passed",
    "role_performance_gate_blockers",
    "role_performance_gate_warnings",
    "evaluation_feedback",
    "resource_requirements",
    "role_delta_resource_requirements",
    "pending_resource_requirements",
    "workflow_resource_requirements",
    "latest_resource_requirements",
    "latest_role_delta_resource_requirements",
}

SAVED_CHAPTER_HANDOFF_KEYS = {
    "chapter_id",
    "chapter_saved",
    "chapter_saved_at",
    "chapter_saved_payload",
    "chapter_writer_provenance",
    "chapter_content_storage",
    "chapter_content_path",
    "chapter_content_size_bytes",
    "chapter_content_checksum",
}

QUALITY_GATE_HANDOFF_KEYS = {
    "chapter_draft_payload",
    "chapter_draft_provenance",
    "chapter_draft_attempt",
    "chapter_draft_word_count",
    "chapter_draft_checksum",
    "pending_chapter_save",
    "quality_gate",
    "quality_gate_history",
    "quality_gate_status",
    "revision_history",
}

STATE_WRITEBACK_HANDOFF_KEYS = {
    "saved_chapter_state_writeback",
    "state_writeback_status",
    "state_writeback_counts",
    "state_writeback_error",
    "confirmed_prior_state_packet",
    "confirmed_prior_state_packet_provenance",
}

ASSET_STATE_KEYS = {
    "saved_chapter_id",
    "saved_region_ids",
    "saved_hook_ids",
    "saved_lore_ids",
    "saved_event_ids",
    "saved_location_ids",
    "duplicate_candidates",
    "map_persistence_state",
    "event_persistence_state",
    "location_persistence_state",
    "asset_persistence_state",
    "resource_requirement_persistence_state",
    "persisted_asset_refs",
}

PROTECTED_CONTEXT_KEYS = (
    CANONICAL_STATE_KEYS
    | RETRIEVED_STATE_KEYS
    | SAVED_CHAPTER_HANDOFF_KEYS
    | QUALITY_GATE_HANDOFF_KEYS
    | STATE_WRITEBACK_HANDOFF_KEYS
)

CANONICAL_WRITE_SOURCES = {
    "workflow_initial_context",
    "workflow_initialization",
    "plot_outline_adapter",
    "user_outline_revision",
    "explicit_user_input",
}


class WorkflowStateManager:
    """Small adapter over WorkflowExecution.context with write policy tracing."""

    def __init__(self, execution: WorkflowExecution):
        self.execution = execution
        self.context = execution.context
        self.context.setdefault("workflow_state", {})
        self.context["workflow_state"].setdefault("canonical_state", {})
        self.context["workflow_state"].setdefault("retrieved_state", {})
        self.context["workflow_state"].setdefault("runtime_state", {})
        self.context["workflow_state"].setdefault("asset_state", {})
        self.context.setdefault("node_outputs", {})
        self.context.setdefault("state_transitions", [])
        self._mirror_known_keys()

    def _mirror_known_keys(self) -> None:
        for key in CANONICAL_STATE_KEYS:
            if key in self.context:
                self.context["workflow_state"]["canonical_state"][key] = self.context[key]
        for key in RETRIEVED_STATE_KEYS:
            if key in self.context:
                self.context["workflow_state"]["retrieved_state"][key] = self.context[key]
        for key in RUNTIME_STATE_KEYS:
            if key in self.context:
                self.context["workflow_state"]["runtime_state"][key] = self.context[key]
        for key in ASSET_STATE_KEYS:
            if key in self.context:
                self.context["workflow_state"]["asset_state"][key] = self.context[key]

    def set_canonical_state(
        self,
        updates: Dict[str, Any],
        source: str,
        *,
        allow_overwrite: bool = False,
    ) -> Dict[str, Any]:
        allowed: Dict[str, Any] = {}
        blocked: Dict[str, Any] = {}
        can_write = allow_overwrite or source in CANONICAL_WRITE_SOURCES

        for key, value in updates.items():
            if value is None:
                continue
            existing = self.context.get(key)
            if key in CANONICAL_STATE_KEYS and existing is not None and existing != value and not can_write:
                blocked[key] = {
                    "existing": existing,
                    "attempted": value,
                    "reason": "protected_canonical_state",
                }
                continue
            self.context[key] = value
            self.context["workflow_state"]["canonical_state"][key] = value
            allowed[key] = value

        self.record_state_transition(
            source=source,
            allowed_updates=allowed,
            blocked_updates=blocked,
        )
        return {"allowed_updates": allowed, "blocked_updates": blocked}

    def merge_runtime_state(self, updates: Dict[str, Any], source: str) -> Dict[str, Any]:
        allowed: Dict[str, Any] = {}
        blocked: Dict[str, Any] = {}
        for key, value in updates.items():
            if key in CANONICAL_STATE_KEYS:
                blocked[key] = {
                    "existing": self.context.get(key),
                    "attempted": value,
                    "reason": "protected_state_requires_canonical_writer",
                }
                continue
            if key in RETRIEVED_STATE_KEYS:
                self.context[key] = value
                self.context["workflow_state"]["retrieved_state"][key] = value
                allowed[key] = value
                continue
            self.context[key] = value
            if key in RUNTIME_STATE_KEYS:
                self.context["workflow_state"]["runtime_state"][key] = value
            allowed[key] = value

        self.record_state_transition(
            source=source,
            allowed_updates=allowed,
            blocked_updates=blocked,
        )
        return {"allowed_updates": allowed, "blocked_updates": blocked}

    def set_asset_state(self, updates: Dict[str, Any], source: str) -> Dict[str, Any]:
        asset_state = self.context["workflow_state"]["asset_state"]
        applied: Dict[str, Any] = {}
        for key, value in updates.items():
            if value is None:
                continue
            if isinstance(value, list) and isinstance(asset_state.get(key), list):
                merged = list(asset_state.get(key) or [])
                for item in value:
                    if item not in merged:
                        merged.append(item)
                value = merged
            elif isinstance(value, dict) and isinstance(asset_state.get(key), dict):
                value = {**asset_state.get(key, {}), **value}
            asset_state[key] = value
            self.context[key] = value
            applied[key] = value

        self.record_state_transition(source=source, asset_updates=applied)
        return applied

    def record_node_output(self, node_id: str, output_data: Any, source: str) -> None:
        safe_output = deepcopy(output_data)
        self.context.setdefault("node_outputs", {})[node_id] = safe_output
        self.context["latest_node_output"] = safe_output
        self.record_state_transition(
            source=source,
            node_id=node_id,
            allowed_updates={"node_outputs": [node_id], "latest_node_output": True},
        )

    def record_state_transition(
        self,
        *,
        source: str,
        node_id: Optional[str] = None,
        allowed_updates: Optional[Dict[str, Any]] = None,
        blocked_updates: Optional[Dict[str, Any]] = None,
        asset_updates: Optional[Dict[str, Any]] = None,
        warnings: Optional[Iterable[str]] = None,
    ) -> None:
        transition = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "node_id": node_id,
            "allowed_updates": list((allowed_updates or {}).keys()),
            "blocked_updates": list((blocked_updates or {}).keys()),
            "asset_updates": list((asset_updates or {}).keys()),
            "warnings": list(warnings or []),
        }
        self.context.setdefault("state_transitions", []).append(transition)
        self.context["last_state_transition"] = transition
        if blocked_updates:
            self.context.setdefault("context_propagation_trace", []).append({
                "timestamp": transition["timestamp"],
                "source": source,
                "node_id": node_id,
                "blocked_updates": blocked_updates,
            })

    def get_canonical_chapter_state(self) -> Dict[str, Any]:
        return {
            key: self.context.get(key)
            for key in CANONICAL_STATE_KEYS
            if self.context.get(key) is not None
        }


def get_workflow_state(execution: WorkflowExecution) -> WorkflowStateManager:
    return WorkflowStateManager(execution)


def is_protected_context_key(key: str) -> bool:
    return key in PROTECTED_CONTEXT_KEYS
