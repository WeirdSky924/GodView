"""Deterministic section retrieval for Assistant Context Fabric."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

CONSTITUTIONAL_PRIORITY_MARKERS = (
    "priority: constitutional",
    "priority：constitutional",
    "priority:宪法",
    "priority：宪法",
    "优先级: constitutional",
    "优先级：constitutional",
    "宪法级",
)


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
            if section_type == "project_brief":
                required_rank = 0
            elif self._is_constitutional_lore(section, text):
                required_rank = 1
            else:
                required_rank = 2
            scope_hit = 0 if any(term in text for term in scope_terms) else 1
            return (required_rank, scope_hit, preference_index, int(section.get("priority") or 100), str(section.get("title") or ""))

        return sorted(sections, key=score)

    def _is_constitutional_lore(self, section: Dict[str, Any], text: str) -> bool:
        if section.get("section_type") != "lore":
            return False
        payload = section.get("structured_payload") or {}
        if str(payload.get("priority") or "").lower() == "constitutional":
            return True
        return any(marker in text for marker in CONSTITUTIONAL_PRIORITY_MARKERS)

    def _scope_terms(self, scope: Dict[str, Any]) -> List[str]:
        terms: List[str] = []
        for value in scope.values():
            if value in (None, "", [], {}):
                continue
            if isinstance(value, str):
                normalized = value.lower()
                terms.append(normalized)
                terms.extend(part for part in normalized.replace("，", " ").replace("。", " ").replace("；", " ").split() if part)
                if any("\u4e00" <= char <= "\u9fff" for char in normalized):
                    terms.extend(normalized[index:index + 2] for index in range(0, max(len(normalized) - 1, 0)))
            elif isinstance(value, (int, float)):
                terms.append(str(value).lower())
            elif isinstance(value, dict):
                terms.extend(self._scope_terms(value))
            elif isinstance(value, Iterable):
                for item in value:
                    if isinstance(item, str):
                        normalized = item.lower()
                        terms.append(normalized)
                        terms.extend(part for part in normalized.replace("，", " ").replace("。", " ").replace("；", " ").split() if part)
                        if any("\u4e00" <= char <= "\u9fff" for char in normalized):
                            terms.extend(normalized[index:index + 2] for index in range(0, max(len(normalized) - 1, 0)))
                    elif isinstance(item, (int, float)):
                        terms.append(str(item).lower())
        return [term for term in terms if len(term) >= 2]
