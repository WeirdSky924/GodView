"""Build scoped Assistant Context packets from snapshots, deltas, and sessions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.assistant_context import AssistantContextBudget
from app.services.assistant_context.retrieval import ContextRetrievalService
from app.services.assistant_context.utils import estimate_tokens, hash_text


class ContextPacketBuilder:
    def __init__(self):
        self.retrieval = ContextRetrievalService()

    def build(
        self,
        *,
        project_id: str,
        assistant_surface: str,
        task_type: str,
        snapshot: Dict[str, Any],
        sections: List[Dict[str, Any]],
        deltas: List[Dict[str, Any]],
        session: Optional[Dict[str, Any]],
        scope: Dict[str, Any],
        budget: AssistantContextBudget,
        force_reread: bool = False,
        history_reset_applied: bool = False,
    ) -> Dict[str, Any]:
        ordered_sections = self.retrieval.select_sections(assistant_surface=assistant_surface, scope=scope, sections=sections)
        selected_sections: List[Dict[str, Any]] = []
        omitted_sections: List[Dict[str, Any]] = []
        section_blocks: List[str] = []
        used_tokens = 0
        snapshot_budget = budget.snapshot_tokens

        for section in ordered_sections:
            section_tokens = int(section.get("token_estimate") or estimate_tokens(section.get("content") or ""))
            summary = self._section_summary(section, section_tokens)
            must_include = self._must_include_section(assistant_surface, section)
            if used_tokens + section_tokens <= snapshot_budget or must_include:
                if must_include and used_tokens + section_tokens > snapshot_budget:
                    summary["reason"] = "required_over_budget"
                selected_sections.append(summary)
                section_blocks.append(f"## {section.get('title') or section.get('section_type')}\n{section.get('content') or ''}")
                used_tokens += section_tokens
            else:
                summary["reason"] = "budget"
                omitted_sections.append(summary)

        delta_blocks: List[str] = []
        delta_tokens = 0
        for delta in deltas[:30]:
            line = self._delta_line(delta)
            tokens = estimate_tokens(line)
            if delta_tokens + tokens > budget.delta_tokens:
                break
            delta_blocks.append(line)
            delta_tokens += tokens

        history_summary = (session or {}).get("history_summary") or ""
        history_window = (session or {}).get("history_window") or []
        history_text = self._history_text(history_summary, history_window, budget.history_tokens)

        parts = [
            f"# Assistant Context Packet\nSurface: {assistant_surface}\nTask: {task_type}\nSnapshot: v{snapshot.get('snapshot_version')} ({snapshot.get('id')})",
            f"## Project Snapshot Summary\n{snapshot.get('summary') or ''}",
        ]
        if delta_blocks:
            parts.append("## Recent Project Deltas\n" + "\n".join(delta_blocks))
        if history_text:
            parts.append("## Assistant Session History\n" + history_text)
        if section_blocks:
            parts.append("## Retrieved Project Sections\n" + "\n\n".join(section_blocks))
        prompt_context = "\n\n".join(parts)
        total_tokens = estimate_tokens(prompt_context)
        truncated = bool(omitted_sections)
        invalidation_state = "force_rebuilt" if force_reread else ("delta_applied" if delta_blocks else "fresh")
        return {
            "prompt_context": prompt_context,
            "packet_data": {
                "project_id": project_id,
                "session_id": (session or {}).get("id"),
                "assistant_surface": assistant_surface,
                "snapshot_id": str(snapshot.get("id")),
                "snapshot_version": snapshot.get("snapshot_version"),
                "packet_scope": {"task_type": task_type, **(scope or {})},
                "budget": budget.model_dump(mode="json"),
                "selected_sections": selected_sections,
                "delta_ids": [str(delta.get("id")) for delta in deltas[:30] if delta.get("id")],
                "retrieval_manifest": {
                    "selected_count": len(selected_sections),
                    "omitted_count": len(omitted_sections),
                    "omitted_sections": omitted_sections,
                    "history_window_count": len(history_window),
                },
                "token_estimate": total_tokens,
                "truncated": truncated,
                "invalidation_state": invalidation_state,
                "force_reread": force_reread,
                "history_reset_applied": history_reset_applied,
                "metadata": {
                    "delta_count": len(deltas),
                    "used_snapshot_tokens": used_tokens,
                    "used_delta_tokens": delta_tokens,
                    "omitted_sections": omitted_sections,
                },
                "content_hash": hash_text(prompt_context),
            },
            "metadata": {
                "assistant_surface": assistant_surface,
                "task_type": task_type,
                "force_reread": force_reread,
                "history_reset_applied": history_reset_applied,
                "invalidation_state": invalidation_state,
                "token_estimate": total_tokens,
                "selected_sections": selected_sections,
                "omitted_sections": omitted_sections,
                "delta_count": len(deltas),
            },
            "history_window": history_window,
            "history_summary": history_summary,
        }

    def _must_include_section(self, assistant_surface: str, section: Dict[str, Any]) -> bool:
        if assistant_surface not in {"plot_outline_agent", "outline_generation"}:
            return False
        if section.get("section_type") == "project_brief":
            return True
        if section.get("section_type") != "lore":
            return False
        payload = section.get("structured_payload") or {}
        if str(payload.get("priority") or "").lower() == "constitutional":
            return True
        content = str(section.get("content") or "").lower()
        return "priority: constitutional" in content or "宪法级" in content

    def _section_summary(self, section: Dict[str, Any], tokens: int) -> Dict[str, Any]:
        return {
            "section_id": str(section.get("id")) if section.get("id") else None,
            "section_type": section.get("section_type"),
            "scope_key": section.get("scope_key"),
            "title": section.get("title"),
            "token_estimate": tokens,
            "entity_refs": section.get("entity_refs") or [],
        }

    def _delta_line(self, delta: Dict[str, Any]) -> str:
        summary = delta.get("payload_summary") or {}
        return (
            f"- {delta.get('operation')} {delta.get('entity_type')}:{delta.get('entity_id')} "
            f"{summary.get('title') or ''}".strip()
        )

    def _history_text(self, summary: str, window: List[Dict[str, Any]], max_tokens: int) -> str:
        lines: List[str] = []
        if summary:
            lines.append("历史摘要：" + summary)
        for message in window[-12:]:
            lines.append(f"{message.get('role')}: {message.get('content')}")
        text = "\n".join(lines)
        if estimate_tokens(text) <= max_tokens:
            return text
        return text[: max_tokens * 2]
