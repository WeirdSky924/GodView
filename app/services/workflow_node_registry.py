from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class WorkflowNodeExecutionProfile:
    agent_type: str
    kind: str
    aliases: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


_PROFILES: dict[str, WorkflowNodeExecutionProfile] = {
    "plot_outline": WorkflowNodeExecutionProfile(
        agent_type="plot_outline",
        kind="service_adapter",
    ),
    "master_plotter": WorkflowNodeExecutionProfile(
        agent_type="master_plotter",
        kind="direct_agent",
        aliases=("plotter",),
    ),
    "summarizer": WorkflowNodeExecutionProfile(
        agent_type="summarizer",
        kind="direct_agent",
    ),
    "hook_manager": WorkflowNodeExecutionProfile(
        agent_type="hook_manager",
        kind="direct_agent",
    ),
    "writer": WorkflowNodeExecutionProfile(
        agent_type="writer",
        kind="direct_agent",
    ),
    "evaluator": WorkflowNodeExecutionProfile(
        agent_type="evaluator",
        kind="direct_agent",
    ),
    "setting": WorkflowNodeExecutionProfile(
        agent_type="setting",
        kind="service_adapter",
    ),
    "event_generator": WorkflowNodeExecutionProfile(
        agent_type="event_generator",
        kind="direct_agent",
    ),
    "world_map_manager": WorkflowNodeExecutionProfile(
        agent_type="world_map_manager",
        kind="direct_agent",
    ),
    "proc_gen": WorkflowNodeExecutionProfile(
        agent_type="proc_gen",
        kind="direct_agent",
        aliases=("procgen",),
    ),
    "dungeon_generator": WorkflowNodeExecutionProfile(
        agent_type="dungeon_generator",
        kind="direct_agent",
    ),
}

_ALIAS_TO_AGENT_TYPE: dict[str, str] = {}
for profile in _PROFILES.values():
    _ALIAS_TO_AGENT_TYPE[profile.agent_type] = profile.agent_type
    for alias in profile.aliases:
        _ALIAS_TO_AGENT_TYPE[alias] = profile.agent_type


def _normalize(agent_type: str) -> str:
    return (agent_type or "").strip().lower().replace(" ", "_").replace("-", "_")


def normalize_workflow_agent_type(agent_type: str) -> str:
    normalized = _normalize(agent_type)
    return _ALIAS_TO_AGENT_TYPE.get(normalized, normalized)


def get_workflow_node_profile(agent_type: Optional[str]) -> Optional[WorkflowNodeExecutionProfile]:
    if not agent_type:
        return None
    return _PROFILES.get(normalize_workflow_agent_type(agent_type))


def get_workflow_node_adapter(agent_type: Optional[str]):
    profile = get_workflow_node_profile(agent_type)
    if not profile or profile.kind != "service_adapter":
        return None

    if profile.agent_type == "plot_outline":
        from app.services.workflow_adapters.plot_outline_adapter import (
            get_plot_outline_workflow_adapter,
        )

        return get_plot_outline_workflow_adapter()

    if profile.agent_type == "setting":
        from app.services.workflow_adapters.setting_adapter import (
            get_setting_workflow_adapter,
        )

        return get_setting_workflow_adapter()

    return None
