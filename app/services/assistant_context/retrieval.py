"""Deterministic section retrieval for Assistant Context Fabric."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set


SURFACE_SECTION_PREFERENCES = {
    "setting_agent": ["project_brief", "world", "lore", "characters", "plot_hooks", "chapter_outlines"],
    "bootstrap_setting_agent": ["project_brief", "world", "lore", "characters", "plot_hooks"],
    "plot_outline_agent": ["project_brief", "chapter_outlines", "plot_hooks", "characters", "lore", "world"],
    "outline_generation": ["project_brief", "chapter_outlines", "plot_hooks", "characters", "lore", "world"],
    "workflow_intervention": ["project_brief", "workflow_state", "chapter_outlines", "characters", "plot_hooks", "lore", "world"],
    "world_map_agent": ["project_brief", "world", "map_regions", "characters", "lore", "plot_hooks"],
    "volume_planning": ["project_brief", "chapter_outlines", "plot_hooks", "characters", "lore", "world"],
}


class ContextRetrievalService:
    def select_sections(self, *, assistant_surface: str, scope: Dict[str, Any], sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        preferred = SURFACE_SECTION_PREFERENCES.get(assistant_surface, [])
        preferred_set: Set[str] = set(preferred)
        scope_terms = self._scope_terms(scope)

        def score(section: Dict[str, Any]) -> tuple:
            section_type = section.get("section_type")
            preference_index = preferred.index(section_type) if section_type in preferred_set else 99
            text = f"{section.get('scope_key') or ''} {section.get('title') or ''} {section.get('content') or ''}".lower()
            scope_hit = 0 if any(term in text for term in scope_terms) else 1
            return (preference_index, scope_hit, int(section.get("priority") or 100), str(section.get("title") or ""))

        return sorted(sections, key=score)

    def _scope_terms(self, scope: Dict[str, Any]) -> List[str]:
        terms: List[str] = []
        for value in scope.values():
            if value in (None, "", [], {}):
                continue
            if isinstance(value, (str, int, float)):
                terms.append(str(value).lower())
            elif isinstance(value, dict):
                terms.extend(self._scope_terms(value))
            elif isinstance(value, Iterable):
                for item in value:
                    if isinstance(item, (str, int, float)):
                        terms.append(str(item).lower())
        return [term for term in terms if len(term) >= 2]
