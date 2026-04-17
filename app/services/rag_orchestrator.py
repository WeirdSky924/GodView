"""
RAG 协调服务
整合静态设定 (Lore) 和动态剧情 (Narrative) 的 RAG 系统
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.lore_rag import LoreRAGService
from app.services.narrative_rag import NarrativeRAGService
from app.models.lore import LoreValidationResult
from app.models.narrative import NarrativeContext

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """RAG 协调服务类"""

    def __init__(
        self,
        lore_service: LoreRAGService,
        narrative_service: NarrativeRAGService,
    ):
        """
        初始化服务

        Args:
            lore_service: 静态设定 RAG 服务
            narrative_service: 动态剧情 RAG 服务
        """
        self.lore_service = lore_service
        self.narrative_service = narrative_service

    async def get_full_context(
        self,
        project_id: str,
        topic: str,
        characters: Optional[List[str]] = None,
        location: Optional[str] = None,
        chapter_id: Optional[str] = None,
        include_constitutional: bool = True,
        recent_event_limit: int = 10,
    ) -> Dict[str, Any]:
        """
        获取完整上下文（静态 + 动态）

        Args:
            project_id: 项目 ID
            topic: 主题
            characters: 相关角色
            location: 相关地点
            chapter_id: 章节 ID
            include_constitutional: 是否包含宪法级规则
            recent_event_limit: 最近事件数量限制

        Returns:
            Dict: 完整上下文
        """
        # 并行获取静态和动态上下文
        lore_context = await self.lore_service.get_lore_context_for_generation(
            project_id=project_id,
            topic=topic,
            characters=characters,
            location=location,
            limit=5,
        )

        narrative_context = await self.narrative_service.get_narrative_context(
            project_id=project_id,
            chapter_id=chapter_id,
            characters=characters,
            limit=recent_event_limit,
        )

        # 构建完整上下文
        full_context = {
            "project_id": project_id,
            "topic": topic,
            "static_lore": lore_context,
            "dynamic_narrative": self._format_narrative_context(narrative_context),
            "characters": characters or [],
            "location": location,
            "chapter_id": chapter_id,
        }

        # 添加宪法级规则
        if include_constitutional:
            constitutional = await self.lore_service.get_constitutional_rules(project_id)
            full_context["constitutional_rules"] = [
                {"title": r.title, "content": r.content}
                for r in constitutional
            ]

        return full_context

    async def validate_generation(
        self,
        project_id: str,
        content: str,
        check_constitutional: bool = True,
        check_consistency: bool = True,
    ) -> Dict[str, Any]:
        """
        验证生成内容

        Args:
            project_id: 项目 ID
            content: 生成的内容
            check_constitutional: 是否检查宪法级规则
            check_consistency: 是否检查一致性

        Returns:
            Dict: 验证结果
        """
        result = {
            "valid": True,
            "violations": [],
            "warnings": [],
            "suggestions": [],
        }

        # 检查设定合规性
        lore_result = await self.lore_service.validate_against_lore(
            project_id=project_id,
            content=content,
            check_constitutional=check_constitutional,
        )

        if not lore_result.valid:
            result["valid"] = False
            result["violations"].extend([
                {"type": "lore_conflict", "detail": str(c)}
                for c in lore_result.conflicts
            ])

        result["warnings"].extend(lore_result.warnings)
        result["suggestions"].extend(lore_result.suggestions)

        # 检查与动态剧情的一致性
        if check_consistency:
            consistency_issues = await self._check_narrative_consistency(
                project_id=project_id,
                content=content,
            )
            result["warnings"].extend(consistency_issues)

        return result

    async def _check_narrative_consistency(
        self,
        project_id: str,
        content: str,
    ) -> List[str]:
        """
        检查内容与动态剧情的一致性

        Args:
            project_id: 项目 ID
            content: 内容

        Returns:
            List: 一致性问题列表
        """
        issues = []

        # 搜索相关剧情
        relevant_narratives = await self.narrative_service.search_narrative(
            project_id=project_id,
            query=content,
            limit=5,
        )

        # 检查是否有矛盾
        # TODO: 使用 LLM 进行更智能的一致性检查
        for narrative in relevant_narratives:
            if narrative.score > 0.9:
                # 高相关性，可能需要检查一致性
                issues.append(
                    f"内容与已有剧情 '{narrative.title}' 高度相关，请确保一致性"
                )

        return issues

    def _format_narrative_context(self, context: NarrativeContext) -> str:
        """
        格式化叙事上下文为字符串

        Args:
            context: 叙事上下文

        Returns:
            str: 格式化后的字符串
        """
        parts = []

        # 最近事件
        if context.recent_events:
            parts.append("## 最近发生的事件\n")
            for i, event in enumerate(context.recent_events, 1):
                parts.append(f"{i}. {event.title}")
                parts.append(f"   类型: {event.entry_type.value}")
                if event.summary:
                    parts.append(f"   摘要: {event.summary}")
                parts.append("")

        # 角色状态
        if context.character_states:
            parts.append("## 角色当前状态\n")
            for char_id, state in context.character_states.items():
                parts.append(f"角色 {char_id}:")
                if state.location_id:
                    parts.append(f"  位置: {state.location_id}")
                if state.mood:
                    parts.append(f"  情绪: {state.mood}")
                parts.append("")

        # 活跃伏笔
        if context.active_hooks:
            parts.append("## 活跃伏笔\n")
            for hook in context.active_hooks:
                parts.append(f"- {hook}")

        return "\n".join(parts)

    async def get_context_for_dialogue(
        self,
        project_id: str,
        character_id: str,
        other_characters: Optional[List[str]] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取对话生成所需的上下文

        Args:
            project_id: 项目 ID
            character_id: 对话角色 ID
            other_characters: 其他在场角色
            location: 当前位置

        Returns:
            Dict: 对话上下文
        """
        all_characters = [character_id]
        if other_characters:
            all_characters.extend(other_characters)

        # 获取角色相关的设定
        lore_context = await self.lore_service.search_lore(
            project_id=project_id,
            query=f"角色 {character_id}",
            limit=5,
        )

        # 获取最近的剧情
        recent_events = await self.narrative_service.get_recent_events(
            project_id=project_id,
            limit=5,
        )

        # 获取角色状态
        character_state = await self.narrative_service.get_character_state(
            character_id=character_id,
            project_id=project_id,
        )

        return {
            "project_id": project_id,
            "character_id": character_id,
            "other_characters": other_characters or [],
            "location": location,
            "character_lore": [
                {"title": l.title, "summary": l.summary}
                for l in lore_context
            ],
            "recent_events": [
                {"title": e.title, "summary": e.summary}
                for e in recent_events
            ],
            "character_state": {
                "mood": character_state.mood if character_state else None,
                "location": character_state.location_id if character_state else None,
                "goals": character_state.current_goals if character_state else [],
            },
        }

    async def get_context_for_narration(
        self,
        project_id: str,
        chapter_id: Optional[str] = None,
        focus_characters: Optional[List[str]] = None,
        plot_goals: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        获取叙事生成所需的上下文

        Args:
            project_id: 项目 ID
            chapter_id: 章节 ID
            focus_characters: 焦点角色
            plot_goals: 剧情目标

        Returns:
            Dict: 叙事上下文
        """
        # 获取世界观设定
        world_lore = await self.lore_service.search_lore(
            project_id=project_id,
            query="世界观 设定",
            category=None,
            limit=10,
        )

        # 获取角色相关设定
        character_lore = []
        if focus_characters:
            for char_id in focus_characters:
                lore = await self.lore_service.search_lore(
                    project_id=project_id,
                    query=f"角色 {char_id}",
                    limit=3,
                )
                character_lore.extend(lore)

        # 获取章节前情
        chapter_events = []
        if chapter_id:
            chapter_events = await self.narrative_service.get_events_by_chapter(
                project_id=project_id,
                chapter_id=chapter_id,
            )

        # 获取整体剧情进度
        narrative_context = await self.narrative_service.get_narrative_context(
            project_id=project_id,
            chapter_id=chapter_id,
            characters=focus_characters,
            limit=10,
        )

        return {
            "project_id": project_id,
            "chapter_id": chapter_id,
            "world_lore": [
                {"title": l.title, "priority": l.priority.value, "summary": l.summary}
                for l in world_lore
            ],
            "character_lore": [
                {"title": l.title, "summary": l.summary}
                for l in character_lore
            ],
            "chapter_events": [
                {"title": e.title, "summary": e.summary}
                for e in chapter_events
            ],
            "recent_context": self._format_narrative_context(narrative_context),
            "plot_goals": plot_goals or [],
        }
