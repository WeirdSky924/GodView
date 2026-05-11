"""Context budget policies for assistant surfaces."""

from __future__ import annotations

from typing import Dict

from app.models.assistant_context import AssistantContextBudget


SURFACE_BUDGETS: Dict[str, AssistantContextBudget] = {
    "setting_agent": AssistantContextBudget(max_context_tokens=16000, snapshot_tokens=9000, delta_tokens=1800, retrieval_tokens=3200),
    "bootstrap_setting_agent": AssistantContextBudget(max_context_tokens=12000, snapshot_tokens=5000, delta_tokens=1200, retrieval_tokens=2500),
    "plot_outline_agent": AssistantContextBudget(max_context_tokens=18000, snapshot_tokens=10000, delta_tokens=1800, retrieval_tokens=4000),
    "workflow_intervention": AssistantContextBudget(max_context_tokens=14000, snapshot_tokens=6000, delta_tokens=1500, retrieval_tokens=3500),
    "world_map_agent": AssistantContextBudget(max_context_tokens=14000, snapshot_tokens=7000, delta_tokens=1500, retrieval_tokens=3500),
    "volume_planning": AssistantContextBudget(max_context_tokens=18000, snapshot_tokens=10000, delta_tokens=1500, retrieval_tokens=4000),
    "outline_generation": AssistantContextBudget(max_context_tokens=18000, snapshot_tokens=10000, delta_tokens=1800, retrieval_tokens=4000),
}


def budget_for_surface(surface: str, override: AssistantContextBudget | None = None) -> AssistantContextBudget:
    if override:
        return override
    return SURFACE_BUDGETS.get(surface, AssistantContextBudget())
