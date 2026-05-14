from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.plot_outline_service import get_plot_outline_service
from app.services.workflow_engine import ChapterReadinessBlockedError


class PlotOutlineWorkflowAdapter:
    async def execute(self, node, execution, db=None) -> Dict[str, Any]:
        service = get_plot_outline_service()
        context = execution.context.copy()

        chapter_number = await self._resolve_chapter_number(service, execution.project_id, context)

        outline_payload = self._normalize_outline_payload(
            context.get("chapter_outline"),
            chapter_number=chapter_number,
            context=context,
        )
        suggestions: list[str] = []
        warnings: list[str] = []
        outline_source = "context"

        if outline_payload is None:
            stored_outline = await service.get_chapter_outline_for_workflow(
                execution.project_id,
                chapter_number=chapter_number,
            )
            outline_payload = self._normalize_outline_payload(
                stored_outline,
                chapter_number=chapter_number,
                context=context,
            )
            outline_source = "database"

        if outline_payload is None:
            raise ChapterReadinessBlockedError({
                "readiness_status": "blocked",
                "block_reason": "approved_outline_missing",
                "message": "正式写作工作流必须绑定当前已审批大纲；Plot Outline 节点不会在写作流程中自动生成替代大纲。",
                "chapter_num": chapter_number,
                "chapter_outline_id": context.get("chapter_outline_id") or context.get("outline_id"),
                "blocking_requirements": [],
                "advisory_requirements": [],
            })

        scene_directions = self._build_scene_directions(outline_payload)

        return {
            "chapter_number": outline_payload.get("chapter_number", chapter_number),
            "chapter_title": outline_payload.get("title") or f"第{chapter_number}章",
            "chapter_outline": outline_payload,
            "chapter_summary": outline_payload.get("summary") or "",
            "chapter_goals": outline_payload.get("chapter_goals") or [],
            "scene_directions": scene_directions,
            "outline_id": outline_payload.get("id"),
            "saved_outline": outline_payload,
            "suggestions": suggestions,
            "warnings": warnings,
            "outline_source": outline_source,
        }

    async def _resolve_chapter_number(
        self,
        service,
        project_id: str,
        context: Dict[str, Any],
    ) -> int:
        raw_value = context.get("chapter_num", context.get("chapter_number"))
        if raw_value is not None:
            try:
                return int(raw_value)
            except (TypeError, ValueError):
                pass
        return await service.get_next_chapter_number(project_id)

    def _normalize_outline_payload(
        self,
        outline: Any,
        *,
        chapter_number: int,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if outline is None:
            return None

        if isinstance(outline, dict):
            payload = dict(outline)
        elif hasattr(outline, "model_dump"):
            payload = outline.model_dump(mode="json")
        else:
            return None

        payload["chapter_number"] = payload.get("chapter_number") or chapter_number
        payload["title"] = payload.get("title") or context.get("chapter_title") or f"第{chapter_number}章"
        payload["summary"] = payload.get("summary") or context.get("chapter_summary") or ""

        chapter_goals = payload.get("chapter_goals")
        if isinstance(chapter_goals, list):
            payload["chapter_goals"] = chapter_goals
        elif chapter_goals:
            payload["chapter_goals"] = [chapter_goals]
        else:
            payload["chapter_goals"] = list(context.get("chapter_goals") or [])

        scenes = payload.get("scenes")
        payload["scenes"] = scenes if isinstance(scenes, list) else []
        return payload

    def _build_runtime_context(self, context: Dict[str, Any], chapter_number: int) -> Optional[str]:
        parts: list[str] = [f"当前工作流目标章节：第{chapter_number}章"]

        chapter_title = context.get("chapter_title")
        if chapter_title:
            parts.append(f"预设章节标题：{chapter_title}")

        chapter_goal = context.get("chapter_goal")
        if chapter_goal:
            parts.append(f"章节目标：{chapter_goal}")

        target_word_count = context.get("target_word_count")
        if target_word_count:
            parts.append(f"目标字数：{target_word_count}")

        style_reference = context.get("style_reference")
        if style_reference:
            parts.append(f"风格参考：{style_reference}")

        user_guidance = context.get("user_guidance")
        if user_guidance:
            parts.append(f"用户补充要求：{user_guidance}")

        return "\n".join(parts) if parts else None

    def _build_previous_events(self, context: Dict[str, Any]) -> Optional[str]:
        previous_events = context.get("previous_events")
        if isinstance(previous_events, str) and previous_events.strip():
            return previous_events
        if isinstance(previous_events, list):
            normalized = [str(item).strip() for item in previous_events if str(item).strip()]
            if normalized:
                return "\n".join(f"- {item}" for item in normalized)

        previous_chapters = context.get("previous_chapters") or []
        summaries: list[str] = []
        for chapter in previous_chapters[-3:]:
            if not isinstance(chapter, dict):
                continue
            chapter_num = chapter.get("chapter_num") or chapter.get("chapter_number") or "?"
            title = chapter.get("title") or f"第{chapter_num}章"
            summary = chapter.get("summary") or ""
            if summary:
                summaries.append(f"第{chapter_num}章《{title}》：{summary}")

        if summaries:
            return "\n".join(summaries)
        return None

    def _build_scene_directions(self, outline_payload: Dict[str, Any]) -> Dict[str, Any]:
        scenes = outline_payload.get("scenes") or []
        selected_characters: list[str] = []
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            for character in scene.get("participating_characters") or []:
                if character and character not in selected_characters:
                    selected_characters.append(character)

        first_scene = scenes[0] if scenes else {}
        main_scene = first_scene.get("title") or outline_payload.get("title") or "未命名场景"

        return {
            "chapter_number": outline_payload.get("chapter_number"),
            "chapter_title": outline_payload.get("title"),
            "plot_focus": outline_payload.get("summary"),
            "chapter_goals": outline_payload.get("chapter_goals") or [],
            "main_scene": main_scene,
            "scene_type": "interactive",
            "selected_characters": selected_characters,
            "scenes": scenes,
        }


_plot_outline_workflow_adapter: Optional[PlotOutlineWorkflowAdapter] = None


def get_plot_outline_workflow_adapter() -> PlotOutlineWorkflowAdapter:
    global _plot_outline_workflow_adapter
    if _plot_outline_workflow_adapter is None:
        _plot_outline_workflow_adapter = PlotOutlineWorkflowAdapter()
    return _plot_outline_workflow_adapter
