"""
记忆服务
GodView v9: 长篇记忆架构

负责记忆条目的创建、检索、向量嵌入和快照构建
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.models.memory import (
    MemoryEntry,
    MemoryType,
    MemoryCategory,
    MemorySnapshot,
    CharacterMemoryState,
    CreateMemoryDTO,
    UpdateMemoryDTO,
    SearchMemoryDTO,
    MemorySearchResult,
    BuildSnapshotDTO,
)

logger = logging.getLogger(__name__)


class MemoryService:
    """记忆服务"""

    def __init__(self, db=None, embedding_service=None, qdrant_client=None):
        """
        初始化记忆服务

        Args:
            db: 数据库连接
            embedding_service: 向量嵌入服务
            qdrant_client: Qdrant 向量数据库客户端
        """
        self._db = db
        self._embedding_service = embedding_service
        self._qdrant = qdrant_client

        # 内存缓存
        self._memories_cache: Dict[str, MemoryEntry] = {}
        self._snapshots_cache: Dict[str, MemorySnapshot] = {}

    async def create_memory(self, dto: CreateMemoryDTO) -> MemoryEntry:
        """
        创建记忆条目

        Args:
            dto: 创建请求

        Returns:
            MemoryEntry: 创建的记忆
        """
        memory = MemoryEntry(
            id=f"mem_{uuid.uuid4().hex[:8]}",
            project_id=dto.project_id,
            memory_type=dto.memory_type,
            category=dto.category,
            content=dto.content,
            summary=dto.summary or dto.content[:100],
            chapter_number=dto.chapter_number,
            character_ids=dto.character_ids,
            importance_score=dto.importance_score,
        )

        # 生成向量嵌入
        if self._embedding_service:
            try:
                memory.embedding = await self._embedding_service.embed(memory.content)
            except Exception as e:
                logger.warning(f"生成向量嵌入失败: {e}")

        # 设置过期时间（短期记忆）
        if memory.memory_type == MemoryType.SHORT_TERM:
            memory.expires_at = datetime.now() + timedelta(days=7)

        # 保存到数据库
        if self._db:
            try:
                await self._db.execute_query(
                    """
                    INSERT INTO memory_entries
                    (id, project_id, memory_type, category, content, summary, chapter_number,
                     character_ids, importance_score, created_at, updated_at, expires_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    memory.id, memory.project_id, memory.memory_type.value,
                    memory.category.value, memory.content, memory.summary,
                    memory.chapter_number, json.dumps(memory.character_ids),
                    memory.importance_score, memory.created_at, memory.updated_at,
                    memory.expires_at
                )
            except Exception as e:
                logger.error(f"保存记忆失败: {e}")

        self._memories_cache[memory.id] = memory
        return memory

    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """获取记忆条目"""
        if memory_id in self._memories_cache:
            return self._memories_cache[memory_id]

        if self._db:
            try:
                rows = await self._db.execute_query(
                    "SELECT * FROM memory_entries WHERE id = $1",
                    memory_id
                )
                if rows:
                    memory = self._row_to_memory(rows[0])
                    self._memories_cache[memory_id] = memory
                    return memory
            except Exception as e:
                logger.error(f"获取记忆失败: {e}")

        return None

    async def update_memory(self, memory_id: str, dto: UpdateMemoryDTO) -> Optional[MemoryEntry]:
        """更新记忆条目"""
        memory = await self.get_memory(memory_id)
        if not memory:
            return None

        if dto.content:
            memory.content = dto.content
            memory.summary = dto.content[:100]
        if dto.summary:
            memory.summary = dto.summary
        if dto.importance_score is not None:
            memory.importance_score = dto.importance_score
        if dto.memory_type:
            memory.memory_type = dto.memory_type

        memory.updated_at = datetime.now()

        if self._db:
            try:
                await self._db.execute_query(
                    """
                    UPDATE memory_entries
                    SET content = $1, summary = $2, importance_score = $3,
                        memory_type = $4, updated_at = $5
                    WHERE id = $6
                    """,
                    memory.content, memory.summary, memory.importance_score,
                    memory.memory_type.value, memory.updated_at, memory_id
                )
            except Exception as e:
                logger.error(f"更新记忆失败: {e}")

        return memory

    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆条目"""
        if memory_id in self._memories_cache:
            del self._memories_cache[memory_id]

        if self._db:
            try:
                await self._db.execute_query(
                    "DELETE FROM memory_entries WHERE id = $1",
                    memory_id
                )
                return True
            except Exception as e:
                logger.error(f"删除记忆失败: {e}")

        return True

    async def search_memories(self, dto: SearchMemoryDTO) -> List[MemorySearchResult]:
        """
        搜索记忆

        支持向量相似度搜索和条件过滤
        """
        results = []

        # 尝试向量搜索
        if self._embedding_service and self._qdrant:
            try:
                query_embedding = await self._embedding_service.embed(dto.query)
                # 使用 Qdrant 进行向量搜索
                search_results = await self._qdrant.search(
                    collection_name=f"memories_{dto.project_id}",
                    query_vector=query_embedding,
                    limit=dto.limit,
                )

                for hit in search_results:
                    memory_id = hit.payload.get("memory_id")
                    memory = await self.get_memory(memory_id)
                    if memory:
                        # 应用过滤条件
                        if dto.memory_types and memory.memory_type not in dto.memory_types:
                            continue
                        if dto.categories and memory.category not in dto.categories:
                            continue

                        results.append(MemorySearchResult(
                            memory=memory,
                            relevance_score=hit.score,
                        ))
            except Exception as e:
                logger.warning(f"向量搜索失败，回退到数据库搜索: {e}")

        # 数据库搜索（fallback 或补充）
        if not results and self._db:
            try:
                query = """
                    SELECT * FROM memory_entries
                    WHERE project_id = $1
                    AND content ILIKE $2
                    ORDER BY importance_score DESC
                    LIMIT $3
                """
                rows = await self._db.execute_query(
                    query, dto.project_id, f"%{dto.query}%", dto.limit
                )
                for row in rows:
                    memory = self._row_to_memory(row)
                    results.append(MemorySearchResult(
                        memory=memory,
                        relevance_score=0.5,  # 默认相关度
                    ))
            except Exception as e:
                logger.error(f"数据库搜索失败: {e}")

        return results

    async def get_memories_by_chapter(
        self,
        project_id: str,
        chapter_number: int,
        memory_types: Optional[List[MemoryType]] = None,
    ) -> List[MemoryEntry]:
        """获取指定章节的记忆"""
        memories = []

        if self._db:
            try:
                query = """
                    SELECT * FROM memory_entries
                    WHERE project_id = $1 AND chapter_number = $2
                """
                params = [project_id, chapter_number]

                if memory_types:
                    placeholders = ", ".join([f"${i+3}" for i in range(len(memory_types))])
                    query += f" AND memory_type IN ({placeholders})"
                    params.extend([mt.value for mt in memory_types])

                query += " ORDER BY importance_score DESC"

                rows = await self._db.execute_query(query, *params)
                for row in rows:
                    memories.append(self._row_to_memory(row))
            except Exception as e:
                logger.error(f"获取章节记忆失败: {e}")

        return memories

    async def get_recent_memories(
        self,
        project_id: str,
        chapters: int = 5,
        current_chapter: Optional[int] = None,
    ) -> List[MemoryEntry]:
        """获取最近章节的记忆"""
        memories = []

        if self._db:
            try:
                if current_chapter:
                    query = """
                        SELECT * FROM memory_entries
                        WHERE project_id = $1
                        AND chapter_number >= $2
                        AND chapter_number < $3
                        ORDER BY chapter_number DESC, importance_score DESC
                    """
                    rows = await self._db.execute_query(
                        query, project_id,
                        current_chapter - chapters,
                        current_chapter
                    )
                else:
                    query = """
                        SELECT * FROM memory_entries
                        WHERE project_id = $1
                        ORDER BY chapter_number DESC, importance_score DESC
                        LIMIT $2
                    """
                    rows = await self._db.execute_query(query, project_id, chapters * 10)

                for row in rows:
                    memories.append(self._row_to_memory(row))
            except Exception as e:
                logger.error(f"获取最近记忆失败: {e}")

        return memories

    async def build_snapshot(self, dto: BuildSnapshotDTO) -> MemorySnapshot:
        """
        构建记忆快照

        聚合角色状态、伏笔、事件等信息
        """
        snapshot = MemorySnapshot(
            project_id=dto.project_id,
            chapter_number=dto.chapter_number,
        )

        # 获取相关记忆
        memories = await self.get_recent_memories(
            dto.project_id,
            chapters=dto.medium_term_chapters,
            current_chapter=dto.chapter_number,
        )

        # 聚合角色状态
        character_states = {}
        for memory in memories:
            if memory.category == MemoryCategory.CHARACTER:
                for char_id in memory.character_ids:
                    if char_id not in character_states:
                        character_states[char_id] = {
                            "last_seen": memory.chapter_number,
                            "key_events": [],
                            "current_location": None,
                        }
                    if memory.summary:
                        character_states[char_id]["key_events"].append(memory.summary)

        snapshot.character_states = character_states

        # 获取活跃伏笔
        if self._db:
            try:
                hooks = await self._db.execute_query(
                    """
                    SELECT * FROM foreshadowings
                    WHERE project_id = $1 AND status = 'planted'
                    ORDER BY priority DESC
                    """,
                    dto.project_id
                )
                snapshot.active_hooks = hooks[:10]  # 最多保留10个
            except Exception:
                pass

        # 提取最近事件
        recent_events = [
            m.summary for m in memories
            if m.category == MemoryCategory.EVENT
        ][:20]
        snapshot.recent_events = recent_events

        # 保存快照
        if self._db:
            try:
                await self._db.execute_query(
                    """
                    INSERT INTO memory_snapshots
                    (id, project_id, chapter_number, character_states, active_hooks,
                     recent_events, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    snapshot.id, snapshot.project_id, snapshot.chapter_number,
                    json.dumps(snapshot.character_states), json.dumps(snapshot.active_hooks),
                    json.dumps(snapshot.recent_events), snapshot.created_at
                )
            except Exception as e:
                logger.warning(f"保存快照失败: {e}")

        self._snapshots_cache[f"{dto.project_id}_{dto.chapter_number}"] = snapshot
        return snapshot

    async def get_snapshot(
        self,
        project_id: str,
        chapter_number: Optional[int] = None,
    ) -> Optional[MemorySnapshot]:
        """获取记忆快照"""
        cache_key = f"{project_id}_{chapter_number}" if chapter_number else f"{project_id}_latest"

        if cache_key in self._snapshots_cache:
            return self._snapshots_cache[cache_key]

        if self._db:
            try:
                if chapter_number:
                    rows = await self._db.execute_query(
                        "SELECT * FROM memory_snapshots WHERE project_id = $1 AND chapter_number = $2",
                        project_id, chapter_number
                    )
                else:
                    rows = await self._db.execute_query(
                        "SELECT * FROM memory_snapshots WHERE project_id = $1 ORDER BY chapter_number DESC LIMIT 1",
                        project_id
                    )

                if rows:
                    row = rows[0]
                    snapshot = MemorySnapshot(
                        id=row['id'],
                        project_id=row['project_id'],
                        chapter_number=row['chapter_number'],
                        character_states=json.loads(row.get('character_states', '{}')),
                        active_hooks=json.loads(row.get('active_hooks', '[]')),
                        recent_events=json.loads(row.get('recent_events', '[]')),
                        world_state=json.loads(row.get('world_state', '{}')),
                        created_at=row.get('created_at', datetime.now()),
                    )
                    return snapshot
            except Exception as e:
                logger.error(f"获取快照失败: {e}")

        return None

    async def get_character_memory_state(
        self,
        project_id: str,
        character_id: str,
    ) -> Optional[CharacterMemoryState]:
        """获取角色的记忆状态"""
        memories = []

        if self._db:
            try:
                rows = await self._db.execute_query(
                    """
                    SELECT * FROM memory_entries
                    WHERE project_id = $1 AND $2 = ANY(character_ids)
                    ORDER BY chapter_number DESC
                    LIMIT 20
                    """,
                    project_id, character_id
                )
                memories = [self._row_to_memory(row) for row in rows]
            except Exception as e:
                logger.error(f"获取角色记忆失败: {e}")

        if not memories:
            return None

        # 构建角色状态
        state = CharacterMemoryState(
            character_id=character_id,
            character_name="",  # 需要从角色服务获取
            last_seen_chapter=memories[0].chapter_number,
            key_events=[m.summary for m in memories if m.category == MemoryCategory.EVENT],
            memory_points=[m.content for m in memories[:5]],
        )

        return state

    async def cleanup_expired_memories(self, project_id: str) -> int:
        """清理过期的短期记忆"""
        count = 0

        if self._db:
            try:
                result = await self._db.execute_query(
                    """
                    DELETE FROM memory_entries
                    WHERE project_id = $1
                    AND memory_type = 'short_term'
                    AND expires_at < NOW()
                    """,
                    project_id
                )
                count = result if isinstance(result, int) else 0
                logger.info(f"清理了 {count} 条过期记忆")
            except Exception as e:
                logger.error(f"清理过期记忆失败: {e}")

        return count

    def _row_to_memory(self, row: Dict) -> MemoryEntry:
        """将数据库行转换为记忆对象"""
        return MemoryEntry(
            id=row['id'],
            project_id=row['project_id'],
            memory_type=MemoryType(row['memory_type']),
            category=MemoryCategory(row['category']),
            content=row['content'],
            summary=row.get('summary'),
            chapter_number=row.get('chapter_number'),
            character_ids=json.loads(row.get('character_ids', '[]')),
            event_ids=json.loads(row.get('event_ids', '[]')),
            location_ids=json.loads(row.get('location_ids', '[]')),
            importance_score=row.get('importance_score', 0.5),
            access_count=row.get('access_count', 0),
            last_accessed_at=row.get('last_accessed_at'),
            expires_at=row.get('expires_at'),
            created_at=row.get('created_at', datetime.now()),
            updated_at=row.get('updated_at', datetime.now()),
            source_type=row.get('source_type'),
            source_agent=row.get('source_agent'),
        )


# 全局实例
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """获取记忆服务实例"""
    global _memory_service
    if _memory_service is None:
        from app.api.app import postgres_db, get_embedding_service
        _memory_service = MemoryService(
            db=postgres_db,
            embedding_service=get_embedding_service(),
        )
    return _memory_service


def set_memory_service(service: MemoryService):
    """设置记忆服务实例"""
    global _memory_service
    _memory_service = service
