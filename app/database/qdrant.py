"""
Qdrant 向量数据库操作层
负责存储和检索角色台词样本、记忆嵌入、语义搜索等
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
)

logger = logging.getLogger(__name__)


class QdrantDatabase:
    """Qdrant 向量数据库操作类"""

    # 集合名称常量
    COLLECTION_MEMORY = "godview_memory"
    COLLECTION_LORE = "godview_lore"
    COLLECTION_NARRATIVE = "godview_narrative"
    COLLECTION_VOICE = "godview_voice"
    COLLECTION_WRITING_RULES = "godview_writing_rules"

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "godview_memory",
        vector_size: int = 1536,
        embedding_service=None,
    ):
        """
        初始化 Qdrant 连接

        Args:
            url: Qdrant 服务 URL
            collection_name: 集合名称（默认集合）
            vector_size: 向量维度
            embedding_service: EmbeddingService 实例（可选，用于自动嵌入文本）
        """
        self.url = url
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.embedding_service = embedding_service
        self._client: Optional[QdrantClient] = None

    async def connect(self):
        """建立数据库连接"""
        self._client = QdrantClient(url=self.url)
        logger.info(f"Qdrant 连接成功：{self.url}")

    def _check_connection_with_retry(self, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """
        带重试的连接检查

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）

        Returns:
            bool: 连接是否成功
        """
        for attempt in range(max_retries):
            try:
                # 尝试获取集合列表来验证连接
                self._client.get_collections()
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Qdrant 连接检查失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Qdrant 连接检查最终失败: {e}")
                    return False
        return False

    async def disconnect(self):
        """关闭数据库连接"""
        if self._client:
            self._client = None
        logger.info("Qdrant 连接已关闭")

    async def init_collection(self):
        """初始化向量集合"""
        if not self._client:
            await self.connect()

        # 使用重试机制检查连接
        if not self._check_connection_with_retry(max_retries=3, retry_delay=2.0):
            raise ConnectionError(f"无法连接到 Qdrant 服务：{self.url}")

        # 检查集合是否存在
        collections = self._client.get_collections().collections
        collection_exists = any(c.name == self.collection_name for c in collections)

        if not collection_exists:
            # 创建集合
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"集合 '{self.collection_name}' 创建成功（维度：{self.vector_size}）")
        else:
            logger.info(f"集合 '{self.collection_name}' 已存在")

    async def init_collections(self):
        """初始化所有向量集合（双 RAG 架构）"""
        if not self._client:
            await self.connect()

        collections_to_create = [
            self.COLLECTION_MEMORY,
            self.COLLECTION_LORE,
            self.COLLECTION_NARRATIVE,
            self.COLLECTION_VOICE,
            self.COLLECTION_WRITING_RULES,
        ]

        existing_collections = [c.name for c in self._client.get_collections().collections]

        for collection_name in collections_to_create:
            if collection_name not in existing_collections:
                self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"集合 '{collection_name}' 创建成功")
            else:
                logger.info(f"集合 '{collection_name}' 已存在")

    # ==================== 向量插入 ====================

    async def _insert_vector_to_collection(
        self,
        collection_name: str,
        vector: List[float],
        payload: Dict[str, Any],
        vector_id: Optional[str] = None,
    ) -> str:
        import uuid

        point_id = vector_id or str(uuid.uuid4())
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload=payload,
        )
        self._client.upsert(
            collection_name=collection_name,
            points=[point],
        )
        return point_id

    async def _insert_text_to_collection(
        self,
        collection_name: str,
        text: str,
        payload: Dict[str, Any],
        vector_id: Optional[str] = None,
    ) -> Optional[str]:
        if not self.embedding_service:
            logger.warning("未配置 Embedding 服务，无法插入文本")
            return None

        try:
            vector = await self.embedding_service.embed_text(text)
            return await self._insert_vector_to_collection(collection_name, vector, payload, vector_id)
        except Exception as e:
            logger.error(f"文本嵌入失败：{e}")
            return None

    async def insert_vector(
        self,
        vector: List[float],
        payload: Dict[str, Any],
        vector_id: Optional[str] = None,
    ) -> str:
        """
        插入向量

        Args:
            vector: 向量数据
            payload: 元数据
            vector_id: 向量 ID

        Returns:
            str: 向量 ID
        """
        return await self._insert_vector_to_collection(self.collection_name, vector, payload, vector_id)

    async def insert_text(
        self,
        text: str,
        payload: Dict[str, Any],
        vector_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        插入文本（自动通过 EmbeddingService 转换为向量）

        Args:
            text: 文本内容
            payload: 元数据
            vector_id: 向量 ID

        Returns:
            str: 向量 ID，失败返回 None
        """
        return await self._insert_text_to_collection(self.collection_name, text, payload, vector_id)

    async def insert_vectors_batch(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> int:
        """
        批量插入向量

        Args:
            vectors: 向量列表
            payloads: 元数据列表
            ids: ID 列表

        Returns:
            int: 插入数量
        """
        import uuid

        points = []
        for i, vector in enumerate(vectors):
            point_id = ids[i] if ids and i < len(ids) else str(uuid.uuid4())
            payload = payloads[i] if i < len(payloads) else {}
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        result = self._client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        return len(points) if result.status else 0

    async def insert_texts_batch(
        self,
        texts: List[str],
        payloads: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> int:
        """
        批量插入文本（自动转换为向量）

        Args:
            texts: 文本列表
            payloads: 元数据列表
            ids: ID 列表

        Returns:
            int: 成功插入数量
        """
        if not self.embedding_service:
            logger.warning("未配置 Embedding 服务，无法批量插入文本")
            return 0

        try:
            vectors = await self.embedding_service.embed_texts(texts)
            return await self.insert_vectors_batch(vectors, payloads, ids)
        except Exception as e:
            logger.error(f"批量文本嵌入失败：{e}")
            return 0

    # ==================== 向量搜索 ====================

    async def search_similar(
        self,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.7,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索相似向量

        Args:
            query_vector: 查询向量
            limit: 返回数量
            score_threshold: 分数阈值
            filter_conditions: 过滤条件

        Returns:
            List: 搜索结果
        """
        # 构建过滤条件
        query_filter = None
        if filter_conditions:
            must_conditions = []
            for key, value in filter_conditions.items():
                must_conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value),
                    )
                )
            if must_conditions:
                query_filter = Filter(must=must_conditions)

        # 搜索
        results = self._client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            search_params=SearchParams(
                hnsw_ef=128,
                exact=False,
            ),
        )

        # 格式化结果
        formatted_results = []
        for result in results.points:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "payload": result.payload,
            })

        return formatted_results

    async def search_by_text(
        self,
        query_text: str,
        limit: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        通过文本搜索（自动嵌入）

        Args:
            query_text: 查询文本
            limit: 返回数量
            filter_conditions: 过滤条件

        Returns:
            List: 搜索结果
        """
        if not self.embedding_service:
            logger.warning("未配置 Embedding 服务，无法通过文本搜索")
            return []

        # 生成嵌入
        embedding = await self.embedding_service.embed_text(query_text)

        return await self.search_similar(
            query_vector=embedding,
            limit=limit,
            filter_conditions=filter_conditions,
        )

    # ==================== 角色台词样本管理 ====================

    async def add_character_voice_sample(
        self,
        sample_id: str,
        character_id: str,
        text: str,
        embedding: Optional[List[float]] = None,
        context: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        添加角色台词样本

        Args:
            sample_id: 样本 ID
            character_id: 角色 ID
            text: 台词文本
            embedding: 向量嵌入（如不提供则自动通过 EmbeddingService 生成）
            context: 上下文
            project_id: 项目 ID（用于按项目过滤）

        Returns:
            str: 样本 ID
        """
        payload = {
            "type": "voice_sample",
            "character_id": character_id,
            "text": text,
            "context": context or "",
        }
        if project_id:
            payload["project_id"] = project_id

        if embedding:
            return await self.insert_vector(embedding, payload, sample_id)
        else:
            return await self.insert_text(text, payload, sample_id)

    async def get_similar_voice_samples(
        self,
        query_embedding: List[float],
        character_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        获取相似台词样本

        Args:
            query_embedding: 查询向量
            character_id: 角色 ID 过滤
            project_id: 项目 ID 过滤
            limit: 返回数量

        Returns:
            List: 台词样本列表
        """
        filter_conditions = {}
        if character_id:
            filter_conditions["character_id"] = character_id
        if project_id:
            filter_conditions["project_id"] = project_id
        filter_conditions["type"] = "voice_sample"

        return await self.search_similar(
            query_vector=query_embedding,
            limit=limit,
            filter_conditions=filter_conditions,
        )

    async def get_similar_voice_samples_by_text(
        self,
        query_text: str,
        character_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        通过文本获取相似台词样本

        Args:
            query_text: 查询文本
            character_id: 角色 ID 过滤
            project_id: 项目 ID 过滤
            limit: 返回数量

        Returns:
            List: 台词样本列表
        """
        filter_conditions = {}
        if character_id:
            filter_conditions["character_id"] = character_id
        if project_id:
            filter_conditions["project_id"] = project_id
        filter_conditions["type"] = "voice_sample"

        return await self.search_by_text(
            query_text=query_text,
            limit=limit,
            filter_conditions=filter_conditions,
        )

    async def get_character_voice_samples(
        self,
        character_id: str,
        limit: int = 10,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取角色的所有台词样本

        Args:
            character_id: 角色 ID
            limit: 返回数量
            project_id: 项目 ID 过滤

        Returns:
            List: 台词样本列表
        """
        must_conditions = [
            FieldCondition(key="character_id", match=MatchValue(value=character_id)),
            FieldCondition(key="type", match=MatchValue(value="voice_sample")),
        ]
        if project_id:
            must_conditions.append(FieldCondition(key="project_id", match=MatchValue(value=project_id)))

        all_points, _ = self._client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(must=must_conditions),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return [
            {
                "id": point.id,
                "score": 1.0,
                "payload": point.payload,
            }
            for point in all_points
        ]

    # ==================== 记忆嵌入管理 ====================

    async def add_memory_embedding(
        self,
        memory_id: str,
        character_id: str,
        content: str,
        embedding: Optional[List[float]] = None,
        memory_type: str = "experience",
        importance: float = 0.5,
    ) -> Optional[str]:
        """
        添加记忆嵌入

        Args:
            memory_id: 记忆 ID
            character_id: 角色 ID
            content: 记忆内容
            embedding: 向量嵌入（如不提供则自动生成）
            memory_type: 记忆类型
            importance: 重要程度

        Returns:
            str: 记忆 ID
        """
        payload = {
            "type": "memory",
            "character_id": character_id,
            "content": content,
            "memory_type": memory_type,
            "importance": importance,
        }

        if embedding:
            return await self.insert_vector(embedding, payload, memory_id)
        else:
            return await self.insert_text(content, payload, memory_id)

    async def search_character_memories(
        self,
        character_id: str,
        query_embedding: List[float],
        limit: int = 5,
        min_importance: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        搜索角色记忆

        Args:
            character_id: 角色 ID
            query_embedding: 查询向量
            limit: 返回数量
            min_importance: 最小重要性

        Returns:
            List: 记忆列表
        """
        filter_conditions = {
            "type": "memory",
            "character_id": character_id,
        }

        results = await self.search_similar(
            query_vector=query_embedding,
            limit=limit,
            filter_conditions=filter_conditions,
        )

        # 过滤重要性
        if min_importance > 0:
            results = [
                r for r in results
                if r.get("payload", {}).get("importance", 0) >= min_importance
            ]

        return results

    async def search_character_memories_by_text(
        self,
        character_id: str,
        query_text: str,
        limit: int = 5,
        min_importance: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        通过文本搜索角色记忆

        Args:
            character_id: 角色 ID
            query_text: 查询文本
            limit: 返回数量
            min_importance: 最小重要性

        Returns:
            List: 记忆列表
        """
        filter_conditions = {
            "type": "memory",
            "character_id": character_id,
        }

        results = await self.search_by_text(
            query_text=query_text,
            limit=limit,
            filter_conditions=filter_conditions,
        )

        # 过滤重要性
        if min_importance > 0:
            results = [
                r for r in results
                if r.get("payload", {}).get("importance", 0) >= min_importance
            ]

        return results

    # ==================== 删除操作 ====================

    async def delete_vector(self, vector_id: str) -> bool:
        """删除向量"""
        result = self._client.delete(
            collection_name=self.collection_name,
            points_selector=[vector_id],
        )
        return result.status == "completed"

    async def delete_by_character(
        self,
        character_id: str,
        vector_type: Optional[str] = None,
    ) -> int:
        """
        删除角色的所有向量

        Args:
            character_id: 角色 ID
            vector_type: 向量类型过滤

        Returns:
            int: 删除数量
        """
        # 先获取所有匹配的向量 ID
        filter_cond = {"character_id": character_id}
        if vector_type:
            filter_cond["type"] = vector_type

        # Qdrant 需要通过 scroll 获取 ID 再删除
        all_points, _ = self._client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filter_cond.items()
                ]
            ),
            limit=1000,
        )

        if not all_points:
            return 0

        point_ids = [p.id for p in all_points]
        result = self._client.delete(
            collection_name=self.collection_name,
            points_selector=point_ids,
        )

        return len(point_ids) if result.status == "completed" else 0

    # ==================== 统计信息 ====================

    async def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息"""
        info = self._client.get_collection(self.collection_name)
        return {
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.value if hasattr(info.status, 'value') else str(info.status),
        }

    # ==================== 静态设定 (Lore) RAG 操作 ====================

    async def add_lore_entry(
        self,
        lore_id: str,
        project_id: str,
        title: str,
        content: str,
        category: str = "custom",
        priority: str = "standard",
        keywords: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
    ) -> Optional[str]:
        """
        添加静态设定条目

        Args:
            lore_id: 设定 ID
            project_id: 项目 ID
            title: 设定标题
            content: 设定内容
            category: 设定类别
            priority: 设定优先级
            keywords: 关键词列表
            embedding: 向量嵌入（如不提供则自动生成）

        Returns:
            str: 设定 ID
        """
        payload = {
            "type": "lore",
            "project_id": project_id,
            "title": title,
            "category": category,
            "priority": priority,
            "keywords": keywords or [],
        }

        if embedding:
            return await self.insert_vector(embedding, payload, lore_id)
        else:
            return await self.insert_text(content, payload, lore_id)

    async def search_lore(
        self,
        query_embedding: List[float],
        project_id: str,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 10,
        score_threshold: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """
        搜索静态设定

        Args:
            query_embedding: 查询向量
            project_id: 项目 ID
            category: 类别过滤
            priority: 优先级过滤
            limit: 返回数量
            score_threshold: 分数阈值

        Returns:
            List: 搜索结果
        """
        filter_conditions = {
            "type": "lore",
            "project_id": project_id,
        }
        if category:
            filter_conditions["category"] = category
        if priority:
            filter_conditions["priority"] = priority

        return await self.search_similar(
            query_vector=query_embedding,
            limit=limit,
            filter_conditions=filter_conditions,
            score_threshold=score_threshold,
        )

    async def search_lore_by_text(
        self,
        query_text: str,
        project_id: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        通过文本搜索静态设定

        Args:
            query_text: 查询文本
            project_id: 项目 ID
            category: 类别过滤
            limit: 返回数量

        Returns:
            List: 搜索结果
        """
        filter_conditions = {
            "type": "lore",
            "project_id": project_id,
        }
        if category:
            filter_conditions["category"] = category

        return await self.search_by_text(
            query_text=query_text,
            limit=limit,
            filter_conditions=filter_conditions,
        )

    async def get_lore_by_keywords(
        self,
        project_id: str,
        keywords: List[str],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        通过关键词获取设定

        Args:
            project_id: 项目 ID
            keywords: 关键词列表
            limit: 返回数量

        Returns:
            List: 设定列表
        """
        # 获取项目所有设定，然后按关键词过滤
        all_points, _ = self._client.scroll(
            collection_name=self.COLLECTION_LORE,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="type", match=MatchValue(value="lore")),
                    FieldCondition(key="project_id", match=MatchValue(value=project_id)),
                ]
            ),
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )

        results = []
        for point in all_points:
            point_keywords = point.payload.get("keywords", [])
            # 检查是否有任何关键词匹配
            if any(kw in point_keywords for kw in keywords):
                results.append({
                    "id": point.id,
                    "score": 1.0,
                    "payload": point.payload,
                })
                if len(results) >= limit:
                    break

        return results

    async def delete_lore_entry(self, lore_id: str) -> bool:
        """删除设定条目"""
        result = self._client.delete(
            collection_name=self.COLLECTION_LORE,
            points_selector=[lore_id],
        )
        return result.status == "completed"

    async def get_constitutional_rules(
        self,
        project_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        获取宪法级规则（不可违反的核心设定）

        Args:
            project_id: 项目 ID
            limit: 返回数量

        Returns:
            List: 宪法级规则列表
        """
        all_points, _ = self._client.scroll(
            collection_name=self.COLLECTION_LORE,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="type", match=MatchValue(value="lore")),
                    FieldCondition(key="project_id", match=MatchValue(value=project_id)),
                    FieldCondition(key="priority", match=MatchValue(value="constitutional")),
                ]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return [
            {
                "id": point.id,
                "score": 1.0,
                "payload": point.payload,
            }
            for point in all_points
        ]

    # ==================== 写作规则 (Writing Rules) RAG 操作 ====================

    async def add_writing_rule_entry(
        self,
        rule_id: str,
        title: str,
        content: str,
        category: str,
        severity: str,
        application_mode: str,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        is_system: bool = False,
        embedding: Optional[List[float]] = None,
    ) -> Optional[str]:
        payload = {
            "type": "writing_rule",
            "rule_id": rule_id,
            "title": title,
            "category": category,
            "severity": severity,
            "application_mode": application_mode,
            "tags": tags or [],
            "source": source or "",
            "is_system": is_system,
        }
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"writing_rule:{rule_id}"))

        if embedding:
            return await self._insert_vector_to_collection(
                self.COLLECTION_WRITING_RULES,
                embedding,
                payload,
                point_id,
            )
        return await self._insert_text_to_collection(
            self.COLLECTION_WRITING_RULES,
            content,
            payload,
            point_id,
        )

    async def search_writing_rules_by_text(
        self,
        query_text: str,
        limit: int = 10,
        score_threshold: float = 0.45,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.embedding_service:
            logger.warning("未配置 Embedding 服务，无法通过文本搜索写作规则")
            return []

        embedding = await self.embedding_service.embed_text(query_text)
        conditions = {"type": "writing_rule"}
        if filter_conditions:
            conditions.update(filter_conditions)

        query_filter = None
        if conditions:
            query_filter = Filter(
                must=[
                    FieldCondition(key=key, match=MatchValue(value=value))
                    for key, value in conditions.items()
                ]
            )

        results = self._client.query_points(
            collection_name=self.COLLECTION_WRITING_RULES,
            query=embedding,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            search_params=SearchParams(hnsw_ef=128, exact=False),
        )

        return [
            {
                "id": result.payload.get("rule_id") or str(result.id),
                "score": result.score,
                "payload": result.payload,
            }
            for result in results.points
        ]

    async def delete_writing_rule_entry(self, rule_id: str) -> bool:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"writing_rule:{rule_id}"))
        result = self._client.delete(
            collection_name=self.COLLECTION_WRITING_RULES,
            points_selector=[point_id],
        )
        return result.status == "completed"

    async def get_writing_rules_by_ids(self, rule_ids: List[str]) -> List[Dict[str, Any]]:
        if not rule_ids:
            return []

        point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"writing_rule:{rule_id}")) for rule_id in rule_ids]
        records = self._client.retrieve(
            collection_name=self.COLLECTION_WRITING_RULES,
            ids=point_ids,
            with_payload=True,
            with_vectors=False,
        )
        return [
            {
                "id": record.payload.get("rule_id") or str(record.id),
                "score": 1.0,
                "payload": record.payload,
            }
            for record in records
        ]


    async def add_narrative_entry(
        self,
        narrative_id: str,
        project_id: str,
        title: str,
        summary: str,
        entry_type: str = "event",
        chapter_id: Optional[str] = None,
        participants: Optional[List[str]] = None,
        importance: float = 0.5,
        embedding: Optional[List[float]] = None,
    ) -> Optional[str]:
        """
        添加动态剧情条目

        Args:
            narrative_id: 叙事 ID
            project_id: 项目 ID
            title: 叙事标题
            summary: 叙事摘要
            entry_type: 条目类型
            chapter_id: 所属章节
            participants: 参与角色
            importance: 重要程度
            embedding: 向量嵌入

        Returns:
            str: 叙事 ID
        """
        payload = {
            "type": "narrative",
            "project_id": project_id,
            "title": title,
            "summary": summary,
            "entry_type": entry_type,
            "chapter_id": chapter_id,
            "participants": participants or [],
            "importance": importance,
        }

        if embedding:
            return await self.insert_vector(embedding, payload, narrative_id)
        else:
            return await self.insert_text(summary, payload, narrative_id)

    async def search_narrative(
        self,
        query_embedding: List[float],
        project_id: str,
        entry_type: Optional[str] = None,
        chapter_id: Optional[str] = None,
        limit: int = 10,
        score_threshold: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """
        搜索动态剧情

        Args:
            query_embedding: 查询向量
            project_id: 项目 ID
            entry_type: 条目类型过滤
            chapter_id: 章节过滤
            limit: 返回数量
            score_threshold: 分数阈值

        Returns:
            List: 搜索结果
        """
        filter_conditions = {
            "type": "narrative",
            "project_id": project_id,
        }
        if entry_type:
            filter_conditions["entry_type"] = entry_type
        if chapter_id:
            filter_conditions["chapter_id"] = chapter_id

        return await self.search_similar(
            query_vector=query_embedding,
            limit=limit,
            filter_conditions=filter_conditions,
            score_threshold=score_threshold,
        )

    async def search_narrative_by_text(
        self,
        query_text: str,
        project_id: str,
        entry_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        通过文本搜索动态剧情

        Args:
            query_text: 查询文本
            project_id: 项目 ID
            entry_type: 条目类型过滤
            limit: 返回数量

        Returns:
            List: 搜索结果
        """
        filter_conditions = {
            "type": "narrative",
            "project_id": project_id,
        }
        if entry_type:
            filter_conditions["entry_type"] = entry_type

        return await self.search_by_text(
            query_text=query_text,
            limit=limit,
            filter_conditions=filter_conditions,
        )

    async def get_recent_narratives(
        self,
        project_id: str,
        limit: int = 20,
        min_importance: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        获取最近的剧情条目

        Args:
            project_id: 项目 ID
            limit: 返回数量
            min_importance: 最小重要性

        Returns:
            List: 剧情条目列表
        """
        all_points, _ = self._client.scroll(
            collection_name=self.COLLECTION_NARRATIVE,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="type", match=MatchValue(value="narrative")),
                    FieldCondition(key="project_id", match=MatchValue(value=project_id)),
                ]
            ),
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )

        results = []
        for point in all_points:
            importance = point.payload.get("importance", 0)
            if importance >= min_importance:
                results.append({
                    "id": point.id,
                    "score": 1.0,
                    "payload": point.payload,
                })
                if len(results) >= limit:
                    break

        return results

    async def get_narrative_by_character(
        self,
        project_id: str,
        character_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        获取角色相关的剧情

        Args:
            project_id: 项目 ID
            character_id: 角色 ID
            limit: 返回数量

        Returns:
            List: 剧情条目列表
        """
        all_points, _ = self._client.scroll(
            collection_name=self.COLLECTION_NARRATIVE,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="type", match=MatchValue(value="narrative")),
                    FieldCondition(key="project_id", match=MatchValue(value=project_id)),
                ]
            ),
            limit=500,
            with_payload=True,
            with_vectors=False,
        )

        results = []
        for point in all_points:
            participants = point.payload.get("participants", [])
            if character_id in participants:
                results.append({
                    "id": point.id,
                    "score": 1.0,
                    "payload": point.payload,
                })
                if len(results) >= limit:
                    break

        return results

    async def delete_narrative_entry(self, narrative_id: str) -> bool:
        """删除剧情条目"""
        result = self._client.delete(
            collection_name=self.COLLECTION_NARRATIVE,
            points_selector=[narrative_id],
        )
        return result.status == "completed"