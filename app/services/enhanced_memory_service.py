"""
增强的记忆服务 - 支持语义检索、上下文感知选择、使用追踪、衰减机制

核心改进：
1. 语义记忆检索：使用向量嵌入进行相似度搜索
2. 上下文感知选择：根据当前任务类型选择相关记忆
3. 记忆使用追踪：记录哪些记忆被实际使用
4. 记忆衰减机制：自动降低不重要记忆的权重
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.models.agent_memory import (
    AgentMemory,
    MemoryEntry,
    MemoryType,
    MemoryImportance,
)
from app.services.agent_memory_service import AgentMemoryService, get_memory_service

logger = logging.getLogger(__name__)


class MemorySelectionStrategy:
    """记忆选择策略"""
    RECENT = "recent"        # 最近记忆
    IMPORTANT = "important"  # 重要记忆
    RELEVANT = "relevant"    # 相关记忆（语义相似）
    HYBRID = "hybrid"        # 混合策略


class EnhancedMemoryService:
    """增强的记忆服务"""

    def __init__(self, db=None, embedding_service=None, qdrant_db=None):
        self._db = db
        self._embedding_service = embedding_service
        self._qdrant_db = qdrant_db
        self._base_memory_service: Optional[AgentMemoryService] = None
        self._config_cache: Dict[str, Dict] = {}

    @property
    def base_service(self) -> AgentMemoryService:
        """获取基础记忆服务"""
        if self._base_memory_service is None:
            self._base_memory_service = get_memory_service(self._db)
        return self._base_memory_service

    def _get_embedding_service(self):
        """获取嵌入服务实例（延迟加载）"""
        if self._embedding_service:
            return self._embedding_service

        # 尝试从全局获取
        try:
            from app.api.app import get_embedding_service
            self._embedding_service = get_embedding_service()
            return self._embedding_service
        except ImportError:
            return None

    def _agent_id_filter_sql(self) -> str:
        return "AND (agent_id = :agent_id OR (agent_id IS NULL AND :agent_id IS NULL))"

    # ==================== 语义记忆检索 ====================

    async def get_semantic_memories(
        self,
        project_id: str,
        agent_type: str,
        query_text: str,
        limit: int = 10,
        min_similarity: float = 0.5,
        agent_id: Optional[str] = None,
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        语义记忆检索 - 使用向量嵌入进行相似度搜索

        Args:
            project_id: 项目 ID
            agent_type: Agent 类型
            query_text: 查询文本
            limit: 返回数量限制
            min_similarity: 最小相似度阈值
            agent_id: Agent 实例 ID

        Returns:
            List[Tuple[MemoryEntry, float]]: (记忆条目, 相似度分数) 列表
        """
        # 尝试获取嵌入服务
        embedding_service = self._get_embedding_service()

        if not embedding_service or not self._db:
            # 降级为关键词匹配
            return await self._fallback_keyword_search(
                project_id, agent_type, query_text, limit, agent_id=agent_id
            )

        try:
            # 1. 生成查询向量
            query_embedding = await embedding_service.embed_text(query_text)

            # 2. 从数据库检索相似记忆
            memories = await self._search_similar_embeddings(
                project_id, agent_type, query_embedding, limit * 2, agent_id=agent_id
            )

            # 3. 过滤低相似度结果
            filtered = [(m, s) for m, s in memories if s >= min_similarity]

            # 4. 记录使用
            for memory, score in filtered[:limit]:
                await self._log_memory_usage(
                    memory_id=memory.id,
                    project_id=project_id,
                    agent_type=agent_type,
                    agent_id=agent_id,
                    usage_context="semantic_search",
                    relevance_score=score,
                )

            return filtered[:limit]

        except Exception as e:
            logger.error(f"语义记忆检索失败: {e}")
            return await self._fallback_keyword_search(
                project_id, agent_type, query_text, limit, agent_id=agent_id
            )

    async def _search_similar_embeddings(
        self,
        project_id: str,
        agent_type: str,
        query_embedding: List[float],
        limit: int,
        agent_id: Optional[str] = None,
    ) -> List[Tuple[MemoryEntry, float]]:
        """从数据库搜索相似嵌入"""
        if not self._db:
            return []

        try:
            # 首先尝试使用 pgvector（如果可用）
            use_pgvector = await self._check_pgvector_available()

            if use_pgvector:
                # 使用 pgvector 的余弦相似度搜索
                query = f"""
                    SELECT memory_id, content, memory_type, importance, tags,
                           1 - (embedding_vec <=> :embedding::vector) as similarity
                    FROM memory_embeddings
                    WHERE project_id = CAST(:project_id AS UUID)
                      AND agent_type = :agent_type
                      {self._agent_id_filter_sql()}
                      AND decay_factor > 0.1
                      AND embedding_vec IS NOT NULL
                    ORDER BY embedding_vec <=> :embedding::vector
                    LIMIT :limit
                """
            else:
                # 降级到关键词搜索（JSONB 模式不支持向量搜索）
                logger.info("pgvector 不可用，降级到关键词搜索")
                return await self._fallback_keyword_search(
                    project_id, agent_type, "", limit, agent_id=agent_id
                )

            results = await self._db.execute_query(
                query,
                {
                    "project_id": project_id,
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                    "embedding": str(query_embedding),
                    "limit": limit,
                },
            )

            memories = []
            for row in (results or []):
                entry = MemoryEntry(
                    id=row.get("memory_id", ""),
                    type=MemoryType(row.get("memory_type", "observation")),
                    importance=MemoryImportance(row.get("importance", "medium")),
                    content=row.get("content", ""),
                    tags=row.get("tags", []),
                    timestamp=datetime.now(),
                )
                similarity = row.get("similarity", 0.0)
                memories.append((entry, similarity))

            return memories

        except Exception as e:
            logger.error(f"嵌入搜索失败: {e}")
            return []

    async def _check_pgvector_available(self) -> bool:
        """检查 pgvector 是否可用"""
        if hasattr(self, '_pgvector_available'):
            return self._pgvector_available

        if not self._db:
            self._pgvector_available = False
            return False

        try:
            # 检查 embedding_vec 列是否存在且为 vector 类型
            result = await self._db.execute_query("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'memory_embeddings'
                    AND column_name = 'embedding_vec'
                    AND data_type = 'USER-DEFINED'
                    AND udt_name = 'vector'
                )
            """)

            self._pgvector_available = bool(result and result[0].get("exists", False))
            return self._pgvector_available

        except Exception:
            self._pgvector_available = False
            return False

    async def _fallback_keyword_search(
        self,
        project_id: str,
        agent_type: str,
        query_text: str,
        limit: int,
        agent_id: Optional[str] = None,
    ) -> List[Tuple[MemoryEntry, float]]:
        """降级为关键词搜索"""
        memory = await self.base_service.get_memory(project_id, agent_type, agent_id)
        query_words = set(query_text.lower().split())

        scored = []
        for entry in memory.memories:
            content_words = set(entry.content.lower().split())
            tag_words = set(t.lower() for t in entry.tags)

            score = len(query_words & content_words) + len(query_words & tag_words) * 2

            # 重要性加权
            weights = {
                MemoryImportance.CRITICAL: 3,
                MemoryImportance.HIGH: 2,
                MemoryImportance.MEDIUM: 1,
                MemoryImportance.LOW: 0.5,
                MemoryImportance.EPHEMERAL: 0.1,
            }
            score *= weights.get(entry.importance, 1)

            if score > 0:
                # 归一化分数到 0-1
                normalized_score = min(score / 10, 1.0)
                scored.append((entry, normalized_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    # ==================== 上下文感知选择 ====================

    async def get_context_aware_memories(
        self,
        project_id: str,
        agent_type: str,
        task_type: str,
        current_context: Optional[Dict[str, Any]] = None,
        query_text: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """
        上下文感知记忆选择

        根据任务类型和当前上下文，智能选择最相关的记忆。

        Args:
            project_id: 项目 ID
            agent_type: Agent 类型
            task_type: 任务类型（如 "outline_generation", "chapter_writing"）
            current_context: 当前上下文（章节号、角色等）
            query_text: 可选的查询文本
            agent_id: Agent 实例 ID

        Returns:
            List[MemoryEntry]: 选中的记忆列表
        """
        # 1. 加载上下文配置
        config = await self._load_context_config(task_type, agent_type)

        if not config:
            # 无配置，使用默认策略
            return await self._default_memory_selection(project_id, agent_type, agent_id=agent_id)

        strategy = config.get("selection_strategy", MemorySelectionStrategy.HYBRID)
        max_memories = config.get("max_memories", 10)
        type_weights = config.get("type_weights", {})
        required_tags = config.get("required_tags", [])
        excluded_tags = config.get("excluded_tags", [])

        # 2. 获取基础记忆
        memory = await self.base_service.get_memory(project_id, agent_type, agent_id)

        # 3. 根据策略选择记忆
        if strategy == MemorySelectionStrategy.RECENT:
            selected = memory.get_recent_memories(max_memories)

        elif strategy == MemorySelectionStrategy.IMPORTANT:
            selected = memory.get_important_memories()[:max_memories]

        elif strategy == MemorySelectionStrategy.RELEVANT and query_text:
            results = await self.get_semantic_memories(
                project_id, agent_type, query_text, max_memories, agent_id=agent_id
            )
            selected = [entry for entry, _ in results]

        else:  # HYBRID
            selected = await self._hybrid_selection(
                memory, query_text, type_weights, required_tags, excluded_tags, max_memories
            )

        # 4. 应用时间衰减
        time_decay_days = config.get("time_decay_days", 30)
        time_decay_factor = config.get("time_decay_factor", 0.5)
        selected = self._apply_time_decay(selected, time_decay_days, time_decay_factor)

        # 5. 记录使用
        for entry in selected:
            await self._log_memory_usage(
                memory_id=entry.id,
                project_id=project_id,
                agent_type=agent_type,
                agent_id=agent_id,
                usage_context=task_type,
                chapter_number=current_context.get("chapter_number") if current_context else None,
            )

        logger.info(
            f"上下文感知记忆选择: task={task_type}, agent={agent_type}, "
            f"agent_id={agent_id or 'default'}, strategy={strategy}, selected={len(selected)}"
        )

        return selected

    async def _load_context_config(
        self,
        task_type: str,
        agent_type: str,
    ) -> Optional[Dict[str, Any]]:
        """加载上下文配置"""
        cache_key = f"{task_type}:{agent_type}"

        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        if not self._db:
            return None

        try:
            query = """
                SELECT * FROM memory_context_configs
                WHERE is_active = TRUE
                  AND (task_types::jsonb ? :task_type OR task_types = '[]'::jsonb)
                  AND (agent_types::jsonb ? :agent_type OR agent_types = '[]'::jsonb)
                LIMIT 1
            """
            results = await self._db.execute_query(
                query, {"task_type": task_type, "agent_type": agent_type}
            )

            if results:
                config = dict(results[0])
                self._config_cache[cache_key] = config
                return config

        except Exception as e:
            logger.warning(f"加载上下文配置失败: {e}")

        return None

    async def _hybrid_selection(
        self,
        memory: AgentMemory,
        query_text: Optional[str],
        type_weights: Dict[str, float],
        required_tags: List[str],
        excluded_tags: List[str],
        max_memories: int,
    ) -> List[MemoryEntry]:
        """混合选择策略"""
        scored_memories = []

        for entry in memory.memories:
            # 检查必需标签
            if required_tags and not any(t in entry.tags for t in required_tags):
                continue

            # 检查排除标签
            if excluded_tags and any(t in entry.tags for t in excluded_tags):
                continue

            # 计算分数
            score = 0.0

            # 类型权重
            type_weight = type_weights.get(entry.type.value, 1.0)
            score += type_weight

            # 重要性权重
            importance_weights = {
                MemoryImportance.CRITICAL: 3.0,
                MemoryImportance.HIGH: 2.0,
                MemoryImportance.MEDIUM: 1.0,
                MemoryImportance.LOW: 0.5,
                MemoryImportance.EPHEMERAL: 0.2,
            }
            score += importance_weights.get(entry.importance, 1.0)

            # 时间新鲜度
            if entry.timestamp:
                days_old = (datetime.now() - entry.timestamp).days
                recency_bonus = max(0, 1.0 - days_old / 30)  # 30天内递减
                score += recency_bonus

            # 访问频率
            score += entry.access_count * 0.1

            scored_memories.append((score, entry))

        # 排序并返回
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored_memories[:max_memories]]

    async def _default_memory_selection(
        self,
        project_id: str,
        agent_type: str,
        agent_id: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """默认记忆选择"""
        memory = await self.base_service.get_memory(project_id, agent_type, agent_id)

        # 默认：最近5条 + 重要3条
        recent = memory.get_recent_memories(5)
        important = memory.get_important_memories()[:3]

        # 合并去重
        seen_ids = set()
        result = []
        for entry in recent + important:
            if entry.id not in seen_ids:
                seen_ids.add(entry.id)
                result.append(entry)

        return result

    def _apply_time_decay(
        self,
        memories: List[MemoryEntry],
        decay_days: int,
        decay_factor: float,
    ) -> List[MemoryEntry]:
        """应用时间衰减"""
        cutoff = datetime.now() - timedelta(days=decay_days)

        result = []
        for entry in memories:
            if entry.timestamp and entry.timestamp < cutoff:
                # 老记忆，降低权重但仍可能包含
                # 这里简单处理：仍然返回，但调用者可以据此调整
                result.append(entry)
            else:
                result.append(entry)

        return result

    # ==================== 记忆使用追踪 ====================

    async def _log_memory_usage(
        self,
        memory_id: str,
        project_id: str,
        agent_type: str,
        usage_context: str,
        relevance_score: Optional[float] = None,
        chapter_number: Optional[int] = None,
        workflow_execution_id: Optional[str] = None,
        workflow_node_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        """记录记忆使用"""
        if not self._db:
            return

        try:
            # 更新访问计数
            query = """
                INSERT INTO memory_usage_logs (
                    memory_id, project_id, agent_type, agent_id,
                    usage_context, relevance_score, chapter_number,
                    workflow_execution_id, workflow_node_id
                ) VALUES (
                    :memory_id, CAST(:project_id AS UUID), :agent_type, :agent_id,
                    :usage_context, :relevance_score, :chapter_number,
                    :workflow_execution_id, :workflow_node_id
                )
            """
            await self._db.execute_write(
                query,
                {
                    "memory_id": memory_id,
                    "project_id": project_id,
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                    "usage_context": usage_context,
                    "relevance_score": relevance_score,
                    "chapter_number": chapter_number,
                    "workflow_execution_id": workflow_execution_id,
                    "workflow_node_id": workflow_node_id,
                },
            )

            # 更新嵌入表的访问计数
            update_query = f"""
                UPDATE memory_embeddings
                SET access_count = access_count + 1,
                    last_accessed_at = NOW(),
                    last_used_context = :context,
                    last_used_in_chapter = COALESCE(:chapter, last_used_in_chapter)
                WHERE memory_id = :memory_id
                  AND project_id = CAST(:project_id AS UUID)
                  AND agent_type = :agent_type
                  {self._agent_id_filter_sql()}
            """
            await self._db.execute_write(
                update_query,
                {
                    "memory_id": memory_id,
                    "project_id": project_id,
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                    "context": usage_context,
                    "chapter": chapter_number,
                },
            )

        except Exception as e:
            logger.warning(f"记录记忆使用失败: {e}")

    async def get_memory_usage_stats(
        self,
        project_id: str,
        agent_type: Optional[str] = None,
        days: int = 30,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取记忆使用统计"""
        if not self._db:
            return {}

        try:
            agent_filter = "AND agent_type = :agent_type" if agent_type else ""
            agent_id_filter = self._agent_id_filter_sql() if agent_type else ""
            query = f"""
                SELECT
                    usage_context,
                    COUNT(*) as usage_count,
                    AVG(relevance_score) as avg_relevance,
                    COUNT(DISTINCT memory_id) as unique_memories
                FROM memory_usage_logs
                WHERE project_id = CAST(:project_id AS UUID)
                  AND created_at > NOW() - (:days * INTERVAL '1 day')
                  {agent_filter}
                  {agent_id_filter}
                GROUP BY usage_context
                ORDER BY usage_count DESC
            """

            params = {"project_id": project_id, "days": days, "agent_id": agent_id}
            if agent_type:
                params["agent_type"] = agent_type

            results = await self._db.execute_query(query, params)

            return {
                "period_days": days,
                "contexts": [
                    {
                        "context": row.get("usage_context"),
                        "usage_count": row.get("usage_count"),
                        "avg_relevance": row.get("avg_relevance"),
                        "unique_memories": row.get("unique_memories"),
                    }
                    for row in (results or [])
                ],
            }

        except Exception as e:
            logger.error(f"获取记忆使用统计失败: {e}")
            return {}

    # ==================== 记忆衰减机制 ====================

    async def apply_memory_decay(
        self,
        project_id: str,
        agent_type: str,
        agent_id: Optional[str] = None,
    ) -> int:
        """
        应用记忆衰减

        根据衰减规则降低不活跃记忆的权重。

        Returns:
            int: 更新的记忆数量
        """
        if not self._db:
            return 0

        try:
            # 获取衰减规则
            rules = await self._get_decay_rules()

            # 获取记忆
            memory = await self.base_service.get_memory(project_id, agent_type, agent_id)

            updated_count = 0
            now = datetime.now()

            for entry in memory.memories:
                old_factor = entry.context.get("decay_factor", 1.0)
                if old_factor <= 0.1:
                    continue  # 已经衰减到最小

                # 计算衰减
                new_factor = self._calculate_decay(entry, rules, now)

                if new_factor < old_factor:
                    # 更新衰减因子
                    entry.context["decay_factor"] = new_factor
                    updated_count += 1

            if updated_count > 0:
                await self.base_service.save_memory(memory)
                logger.info(
                    f"记忆衰减完成: {agent_type}, agent_id={agent_id or 'default'}, 更新 {updated_count} 条"
                )

            return updated_count

        except Exception as e:
            logger.error(f"应用记忆衰减失败: {e}")
            return 0

    async def _get_decay_rules(self) -> List[Dict[str, Any]]:
        """获取衰减规则"""
        if not self._db:
            return []

        try:
            query = "SELECT * FROM memory_decay_rules WHERE is_active = TRUE"
            results = await self._db.execute_query(query)
            return [dict(r) for r in (results or [])]
        except Exception:
            return []

    def _calculate_decay(
        self,
        entry: MemoryEntry,
        rules: List[Dict[str, Any]],
        now: datetime,
    ) -> float:
        """计算单个记忆的衰减因子"""
        current_factor = entry.context.get("decay_factor", 1.0)

        # 查找匹配的规则
        matching_rules = []
        for rule in rules:
            type_match = not rule.get("memory_type") or rule.get("memory_type") == entry.type.value
            importance_match = not rule.get("importance") or rule.get("importance") == entry.importance.value

            if type_match and importance_match:
                matching_rules.append(rule)

        if not matching_rules:
            return current_factor

        # 应用最严格的规则
        max_decay_rate = max(r.get("decay_rate", 0.1) for r in matching_rules)
        min_weight = max(r.get("min_weight", 0.1) for r in matching_rules)

        # 计算天数
        if entry.timestamp:
            days_old = (now - entry.timestamp).days
        else:
            days_old = 0

        # 应用衰减
        if days_old > 7:  # 超过7天才开始衰减
            decay = max_decay_rate * (days_old / 30)  # 每月衰减
            new_factor = max(current_factor - decay, min_weight)

            # 访问补偿
            access_boost = entry.access_count * 0.05
            new_factor = min(new_factor + access_boost, 1.0)

            return new_factor

        return current_factor

    # ==================== 嵌入管理 ====================

    async def store_memory_embedding(
        self,
        entry: MemoryEntry,
        project_id: str,
        agent_type: str,
        agent_id: Optional[str] = None,
    ):
        """存储记忆的向量嵌入"""
        # 尝试获取嵌入服务
        embedding_service = self._get_embedding_service()

        if not embedding_service or not self._db:
            return

        try:
            # 生成嵌入
            embedding = await embedding_service.embed_text(entry.content)

            # 计算内容哈希
            content_hash = hashlib.sha256(entry.content.encode()).hexdigest()

            # 检查 pgvector 是否可用
            use_pgvector = await self._check_pgvector_available()

            if use_pgvector:
                # 使用 pgvector 存储
                query = """
                    INSERT INTO memory_embeddings (
                        memory_id, project_id, agent_type, agent_id,
                        content, content_hash, embedding, embedding_vec,
                        memory_type, importance, tags
                    ) VALUES (
                        :memory_id, CAST(:project_id AS UUID), :agent_type, :agent_id,
                        :content, :content_hash, :embedding::jsonb, :embedding_vec::vector,
                        :memory_type, :importance, :tags::jsonb
                    )
                    ON CONFLICT (memory_id, project_id, agent_type, agent_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        embedding_vec = EXCLUDED.embedding_vec,
                        updated_at = NOW()
                """
                params = {
                    "memory_id": entry.id,
                    "project_id": project_id,
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                    "content": entry.content,
                    "content_hash": content_hash,
                    "embedding": json.dumps(embedding),
                    "embedding_vec": str(embedding),
                    "memory_type": entry.type.value,
                    "importance": entry.importance.value,
                    "tags": json.dumps(entry.tags),
                }
            else:
                # 使用 JSONB 存储（无向量搜索能力）
                query = """
                    INSERT INTO memory_embeddings (
                        memory_id, project_id, agent_type, agent_id,
                        content, content_hash, embedding,
                        memory_type, importance, tags
                    ) VALUES (
                        :memory_id, CAST(:project_id AS UUID), :agent_type, :agent_id,
                        :content, :content_hash, :embedding::jsonb,
                        :memory_type, :importance, :tags::jsonb
                    )
                    ON CONFLICT (memory_id, project_id, agent_type, agent_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """
                params = {
                    "memory_id": entry.id,
                    "project_id": project_id,
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                    "content": entry.content,
                    "content_hash": content_hash,
                    "embedding": json.dumps(embedding),
                    "memory_type": entry.type.value,
                    "importance": entry.importance.value,
                    "tags": json.dumps(entry.tags),
                }

            await self._db.execute_write(query, params)

        except Exception as e:
            logger.warning(f"存储记忆嵌入失败: {e}")

    async def sync_memory_embeddings(
        self,
        project_id: str,
        agent_type: str,
        agent_id: Optional[str] = None,
    ):
        """同步记忆嵌入（批量）"""
        memory = await self.base_service.get_memory(project_id, agent_type, agent_id)

        synced = 0
        for entry in memory.memories:
            await self.store_memory_embedding(entry, project_id, agent_type, agent_id=agent_id)
            synced += 1

        logger.info(f"同步记忆嵌入: {agent_type}, agent_id={agent_id or 'default'}, {synced} 条")
        return synced


# 单例
_enhanced_memory_service: Optional[EnhancedMemoryService] = None


def get_enhanced_memory_service(
    db=None,
    embedding_service=None,
    qdrant_db=None,
) -> EnhancedMemoryService:
    """获取增强记忆服务单例"""
    global _enhanced_memory_service
    if _enhanced_memory_service is None:
        _enhanced_memory_service = EnhancedMemoryService(db, embedding_service, qdrant_db)
    else:
        if db is not None:
            _enhanced_memory_service._db = db
        if embedding_service is not None:
            _enhanced_memory_service._embedding_service = embedding_service
        if qdrant_db is not None:
            _enhanced_memory_service._qdrant_db = qdrant_db
    return _enhanced_memory_service
