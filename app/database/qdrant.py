"""
Qdrant 向量数据库操作层
负责存储和检索角色台词样本、记忆嵌入、语义搜索等
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

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

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "godview_memory",
        vector_size: int = 1536,
    ):
        """
        初始化 Qdrant 连接

        Args:
            url: Qdrant 服务 URL
            collection_name: 集合名称
            vector_size: 向量维度
        """
        self.url = url
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._client: Optional[QdrantClient] = None

    async def connect(self):
        """建立数据库连接"""
        self._client = QdrantClient(url=self.url)
        logger.info(f"Qdrant 连接成功：{self.url}")

    async def disconnect(self):
        """关闭数据库连接"""
        if self._client:
            self._client = None
        logger.info("Qdrant 连接已关闭")

    async def init_collection(self):
        """初始化向量集合"""
        if not self._client:
            await self.connect()

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
            # 创建索引
            self._client.create_payload_index(
                collection_name=self.collection_name,
                field_name="type",
                field_schema="keyword",
            )
            self._client.create_payload_index(
                collection_name=self.collection_name,
                field_name="character_id",
                field_schema="keyword",
            )
            logger.info(f"集合 '{self.collection_name}' 创建成功")
        else:
            logger.info(f"集合 '{self.collection_name}' 已存在")

    # ==================== 向量插入 ====================

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
        import uuid

        point_id = vector_id or str(uuid.uuid4())

        point = PointStruct(
            id=point_id,
            vector=vector,
            payload=payload,
        )

        self._client.upsert(
            collection_name=self.collection_name,
            points=[point],
        )

        return point_id

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
        results = self._client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
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
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "payload": result.payload,
            })

        return formatted_results

    async def search_by_text(
        self,
        query_text: str,
        embedding_model: Any,
        limit: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        通过文本搜索（自动嵌入）

        Args:
            query_text: 查询文本
            embedding_model: 嵌入模型
            limit: 返回数量
            filter_conditions: 过滤条件

        Returns:
            List: 搜索结果
        """
        # 生成嵌入
        embedding = await self._generate_embedding(query_text, embedding_model)

        return await self.search_similar(
            query_vector=embedding,
            limit=limit,
            filter_conditions=filter_conditions,
        )

    async def _generate_embedding(
        self, text: str, embedding_model: Any
    ) -> List[float]:
        """生成文本嵌入"""
        # 假设使用 LangChain 的嵌入模型
        if hasattr(embedding_model, "embed_query"):
            return embedding_model.embed_query(text)
        else:
            # Fallback: 返回零向量
            logger.warning("嵌入模型不可用，返回零向量")
            return [0.0] * self.vector_size

    # ==================== 角色台词样本管理 ====================

    async def add_character_voice_sample(
        self,
        sample_id: str,
        character_id: str,
        text: str,
        embedding: List[float],
        context: Optional[str] = None,
    ) -> str:
        """
        添加角色台词样本

        Args:
            sample_id: 样本 ID
            character_id: 角色 ID
            text: 台词文本
            embedding: 向量嵌入
            context: 上下文

        Returns:
            str: 样本 ID
        """
        payload = {
            "type": "voice_sample",
            "character_id": character_id,
            "text": text,
            "context": context or "",
        }

        return await self.insert_vector(
            vector=embedding,
            payload=payload,
            vector_id=sample_id,
        )

    async def get_similar_voice_samples(
        self,
        query_embedding: List[float],
        character_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        获取相似台词样本

        Args:
            query_embedding: 查询向量
            character_id: 角色 ID 过滤
            limit: 返回数量

        Returns:
            List: 台词样本列表
        """
        filter_conditions = {}
        if character_id:
            filter_conditions["character_id"] = character_id
        filter_conditions["type"] = "voice_sample"

        return await self.search_similar(
            query_vector=query_embedding,
            limit=limit,
            filter_conditions=filter_conditions,
        )

    async def get_character_voice_samples(
        self,
        character_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        获取角色的所有台词样本

        Args:
            character_id: 角色 ID
            limit: 返回数量

        Returns:
            List: 台词样本列表
        """
        # Qdrant 不支持直接按字段查询所有记录，需要搜索
        # 使用零向量作为占位符搜索
        dummy_vector = [0.0] * self.vector_size

        results = await self.search_similar(
            query_vector=dummy_vector,
            limit=limit,
            filter_conditions={"character_id": character_id, "type": "voice_sample"},
        )

        return results

    # ==================== 记忆嵌入管理 ====================

    async def add_memory_embedding(
        self,
        memory_id: str,
        character_id: str,
        content: str,
        embedding: List[float],
        memory_type: str = "experience",
        importance: float = 0.5,
    ) -> str:
        """
        添加记忆嵌入

        Args:
            memory_id: 记忆 ID
            character_id: 角色 ID
            content: 记忆内容
            embedding: 向量嵌入
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

        return await self.insert_vector(
            vector=embedding,
            payload=payload,
            vector_id=memory_id,
        )

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

    # ==================== 删除操作 ====================

    async def delete_vector(self, vector_id: str) -> bool:
        """删除向量"""
        result = self._client.delete(
            collection_name=self.collection_name,
            points_selector=[vector_id],
        )
        return result.status

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
        # Qdrant 需要通过 scroll 先获取 ID 再删除
        # 这里简化处理
        return 0

    # ==================== 统计信息 ====================

    async def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息"""
        info = self._client.get_collection(self.collection_name)
        return {
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status,
        }
