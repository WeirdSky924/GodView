"""
动态剧情 RAG 服务
负责管理和检索剧情发展、角色状态变化等"现在进行时"信息
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database.qdrant import QdrantDatabase
from app.models.narrative import (
    CharacterState,
    NarrativeEntry,
    NarrativeEntryType,
    NarrativeSearchResult,
    NarrativeContext,
    TemporalScope,
)

logger = logging.getLogger(__name__)


class NarrativeRAGService:
    """动态剧情 RAG 服务类"""

    def __init__(self, qdrant_db: QdrantDatabase):
        """
        初始化服务

        Args:
            qdrant_db: Qdrant 数据库实例
        """
        self.qdrant = qdrant_db
        self._narrative_cache: Dict[str, NarrativeEntry] = {}
        self._character_states: Dict[str, CharacterState] = {}

    async def record_event(
        self,
        narrative: NarrativeEntry,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """
        记录事件

        Args:
            narrative: 叙事条目
            embedding: 向量嵌入

        Returns:
            str: 叙事 ID
        """
        # 存储到 Qdrant
        embedding_id = await self.qdrant.add_narrative_entry(
            narrative_id=narrative.id,
            project_id=narrative.project_id,
            title=narrative.title,
            summary=narrative.summary,
            entry_type=narrative.entry_type.value,
            chapter_id=narrative.chapter_id,
            participants=narrative.participants,
            importance=narrative.importance,
            embedding=embedding,
        )

        if embedding_id:
            narrative.embedding_id = embedding_id

        # 缓存
        self._narrative_cache[narrative.id] = narrative

        # 更新角色状态
        for participant in narrative.participants:
            await self._update_character_state(participant, narrative)

        logger.info(f"记录事件: {narrative.title} (ID: {narrative.id})")
        return narrative.id

    async def search_narrative(
        self,
        project_id: str,
        query: str,
        entry_type: Optional[NarrativeEntryType] = None,
        chapter_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[NarrativeSearchResult]:
        """
        搜索剧情

        Args:
            project_id: 项目 ID
            query: 查询文本
            entry_type: 条目类型过滤
            chapter_id: 章节过滤
            limit: 返回数量

        Returns:
            List: 搜索结果
        """
        results = await self.qdrant.search_narrative_by_text(
            query_text=query,
            project_id=project_id,
            entry_type=entry_type.value if entry_type else None,
            limit=limit,
        )

        return [
            NarrativeSearchResult(
                id=r["id"],
                title=r["payload"].get("title", ""),
                entry_type=NarrativeEntryType(r["payload"].get("entry_type", "event")),
                summary=r["payload"].get("summary", ""),
                chapter_id=r["payload"].get("chapter_id"),
                score=r["score"],
                participants=r["payload"].get("participants", []),
            )
            for r in results
        ]

    async def get_character_state(
        self,
        character_id: str,
        project_id: str,
    ) -> Optional[CharacterState]:
        """
        获取角色当前状态

        Args:
            character_id: 角色 ID
            project_id: 项目 ID

        Returns:
            Optional[CharacterState]: 角色状态
        """
        # 先检查缓存
        cache_key = f"{project_id}_{character_id}"
        if cache_key in self._character_states:
            return self._character_states[cache_key]

        # 获取角色相关的最新事件
        events = await self.qdrant.get_narrative_by_character(
            project_id=project_id,
            character_id=character_id,
            limit=10,
        )

        if not events:
            return None

        # 从事件中构建状态
        state = CharacterState(
            id=f"state_{character_id}_{datetime.utcnow().timestamp()}",
            character_id=character_id,
            project_id=project_id,
        )

        # 应用状态变化
        for event in reversed(events):
            state_changes = event.get("payload", {}).get("state_changes", [])
            for change in state_changes:
                if change.get("character_id") == character_id:
                    state.attribute_changes.update(change.get("changes", {}))

        self._character_states[cache_key] = state
        return state

    async def get_narrative_context(
        self,
        project_id: str,
        chapter_id: Optional[str] = None,
        characters: Optional[List[str]] = None,
        limit: int = 10,
    ) -> NarrativeContext:
        """
        获取叙事上下文

        Args:
            project_id: 项目 ID
            chapter_id: 章节 ID
            characters: 相关角色
            limit: 返回数量

        Returns:
            NarrativeContext: 叙事上下文
        """
        # 获取最近事件
        recent_events_data = await self.qdrant.get_recent_narratives(
            project_id=project_id,
            limit=limit,
        )

        recent_events = [
            NarrativeEntry(
                id=e["id"],
                project_id=project_id,
                title=e["payload"].get("title", ""),
                summary=e["payload"].get("summary", ""),
                entry_type=NarrativeEntryType(e["payload"].get("entry_type", "event")),
                participants=e["payload"].get("participants", []),
                importance=e["payload"].get("importance", 0.5),
            )
            for e in recent_events_data
        ]

        # 获取角色状态
        character_states = {}
        if characters:
            for char_id in characters:
                state = await self.get_character_state(char_id, project_id)
                if state:
                    character_states[char_id] = state

        return NarrativeContext(
            project_id=project_id,
            recent_events=recent_events,
            character_states=character_states,
            focus_characters=characters or [],
        )

    async def get_recent_events(
        self,
        project_id: str,
        limit: int = 20,
        min_importance: float = 0.0,
        entry_types: Optional[List[NarrativeEntryType]] = None,
    ) -> List[NarrativeEntry]:
        """
        获取最近事件

        Args:
            project_id: 项目 ID
            limit: 返回数量
            min_importance: 最小重要性
            entry_types: 条目类型过滤

        Returns:
            List: 事件列表
        """
        results = await self.qdrant.get_recent_narratives(
            project_id=project_id,
            limit=limit * 2,  # 获取更多以便过滤
            min_importance=min_importance,
        )

        events = []
        for r in results:
            entry_type = NarrativeEntryType(r["payload"].get("entry_type", "event"))

            # 类型过滤
            if entry_types and entry_type not in entry_types:
                continue

            events.append(NarrativeEntry(
                id=r["id"],
                project_id=project_id,
                title=r["payload"].get("title", ""),
                summary=r["payload"].get("summary", ""),
                entry_type=entry_type,
                participants=r["payload"].get("participants", []),
                importance=r["payload"].get("importance", 0.5),
                chapter_id=r["payload"].get("chapter_id"),
            ))

            if len(events) >= limit:
                break

        return events

    async def get_events_by_chapter(
        self,
        project_id: str,
        chapter_id: str,
    ) -> List[NarrativeEntry]:
        """
        获取章节的所有事件

        Args:
            project_id: 项目 ID
            chapter_id: 章节 ID

        Returns:
            List: 事件列表
        """
        # TODO: 实现按章节精确查询
        results = await self.qdrant.search_narrative_by_text(
            query_text="",  # 空查询
            project_id=project_id,
            limit=100,
        )

        events = []
        for r in results:
            if r["payload"].get("chapter_id") == chapter_id:
                events.append(NarrativeEntry(
                    id=r["id"],
                    project_id=project_id,
                    title=r["payload"].get("title", ""),
                    summary=r["payload"].get("summary", ""),
                    entry_type=NarrativeEntryType(r["payload"].get("entry_type", "event")),
                    chapter_id=chapter_id,
                    participants=r["payload"].get("participants", []),
                ))

        return events

    async def delete_narrative(self, narrative_id: str) -> bool:
        """
        删除叙事条目

        Args:
            narrative_id: 叙事 ID

        Returns:
            bool: 是否成功
        """
        # 从缓存移除
        if narrative_id in self._narrative_cache:
            del self._narrative_cache[narrative_id]

        # 从 Qdrant 删除
        return await self.qdrant.delete_narrative_entry(narrative_id)

    async def _update_character_state(
        self,
        character_id: str,
        narrative: NarrativeEntry,
    ) -> None:
        """
        更新角色状态（内部方法）

        Args:
            character_id: 角色 ID
            narrative: 相关叙事
        """
        # 获取或创建状态
        cache_key = f"{narrative.project_id}_{character_id}"
        if cache_key not in self._character_states:
            self._character_states[cache_key] = CharacterState(
                id=f"state_{character_id}_{datetime.utcnow().timestamp()}",
                character_id=character_id,
                project_id=narrative.project_id,
            )

        state = self._character_states[cache_key]

        # 应用状态变化
        for change in narrative.state_changes:
            if change.get("character_id") == character_id:
                state.attribute_changes.update(change.get("changes", {}))

        # 更新位置
        if narrative.location_id and narrative.primary_character == character_id:
            state.location_id = narrative.location_id

        state.recorded_at = datetime.utcnow()
