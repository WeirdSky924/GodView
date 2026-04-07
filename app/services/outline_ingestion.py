"""
大纲输入服务
v4 核心需求：接收文本输入或上传文件，统一抽取纯文本，切块，存储，建立检索索引
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.outline import (
    OutlineSource,
    OutlineChunk,
    SourceType,
)

logger = logging.getLogger(__name__)


class OutlineIngestionService:
    """大纲输入服务 - 负责接收、处理和存储大纲文本"""

    def __init__(self):
        self._outline_sources: Dict[str, OutlineSource] = {}
        self.chunk_size = 1000  # 字符数
        self.chunk_overlap = 200  # 重叠字符数

    async def ingest_outline(
        self,
        content: str,
        source_type: str = "pasted_text",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        接收并处理大纲文本

        Args:
            content: 大纲文本内容
            source_type: 来源类型（pasted_text/file_txt/file_md）
            session_id: 关联的 Bootstrap 会话 ID

        Returns:
            Dict: 处理结果
        """
        # 生成大纲源 ID
        outline_id = f"outline_{uuid.uuid4().hex[:12]}"

        # 提取纯文本（去除 markdown 格式等）
        processed_content = self._process_content(content, source_type)

        # 文本分块
        chunks = self._chunk_text(processed_content)

        # 创建大纲源对象
        outline_source = OutlineSource(
            id=outline_id,
            project_id=session_id or "",
            session_id=session_id,
            source_type=SourceType(source_type),
            original_content=content,
            processed_content=processed_content,
            chunks=chunks,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            file_name=self._extract_file_name(content, source_type),
        )

        # 存储
        self._outline_sources[outline_id] = outline_source

        # 生成向量嵌入（如果有 embedding service）
        await self._generate_embeddings(outline_source)

        return {
            "outline_id": outline_id,
            "chunk_count": len(chunks),
            "word_count": len(processed_content),
            "source_type": source_type,
        }

    def _process_content(self, content: str, source_type: str) -> str:
        """
        处理内容，提取纯文本

        Args:
            content: 原始内容
            source_type: 来源类型

        Returns:
            str: 处理后的纯文本
        """
        import re

        processed = content

        # 如果是 markdown，尝试提取纯文本
        if source_type in ["file_md", "pasted_text"]:
            # 移除代码块
            processed = re.sub(r'```[\s\S]*?```', '', processed)
            # 移除行内代码
            processed = re.sub(r'`[^`]+`', '', processed)
            # 移除图片链接
            processed = re.sub(r'!\[.*?\]\(.*?\)', '', processed)
            # 移除链接但保留文字
            processed = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', processed)
            # 移除标题标记但保留文字
            processed = re.sub(r'^#{1,6}\s+', '', processed, flags=re.MULTILINE)
            # 移除加粗/斜体标记
            processed = re.sub(r'\*\*([^*]+)\*\*', r'\1', processed)
            processed = re.sub(r'\*([^*]+)\*', r'\1', processed)
            processed = re.sub(r'__([^_]+)__', r'\1', processed)
            processed = re.sub(r'_([^_]+)_', r'\1', processed)

        # 规范化空白字符
        processed = re.sub(r'\n{3,}', '\n\n', processed)
        processed = re.sub(r' {2,}', ' ', processed)

        return processed.strip()

    def _chunk_text(self, text: str) -> List[OutlineChunk]:
        """
        将文本分块

        Args:
            text: 处理后的文本

        Returns:
            List[OutlineChunk]: 分块列表
        """
        if len(text) <= self.chunk_size:
            # 文本较短，无需分块
            return [
                OutlineChunk(
                    id=f"chunk_{uuid.uuid4().hex[:8]}",
                    content=text,
                    chunk_index=0,
                    start_char=0,
                    end_char=len(text),
                )
            ]

        chunks = []
        start = 0
        index = 0

        while start < len(text):
            end = start + self.chunk_size

            # 尽量在句子边界切割
            if end < len(text):
                # 向前查找最后一个标点符号
                punct = max(
                    text.rfind('。', start, end),
                    text.rfind('！', start, end),
                    text.rfind('？', start, end),
                    text.rfind('\n', start, end),
                )
                if punct > start:
                    end = punct + 1

            chunk = OutlineChunk(
                id=f"chunk_{uuid.uuid4().hex[:8]}",
                content=text[start:end],
                chunk_index=index,
                start_char=start,
                end_char=end,
            )
            chunks.append(chunk)

            # 移动起始位置（考虑重叠）
            start = end - self.chunk_overlap
            index += 1

        return chunks

    async def _generate_embeddings(self, outline_source: OutlineSource):
        """为大纲分块生成向量嵌入"""
        try:
            from app.api.app import get_embedding_service
        except ImportError:
            logger.warning("无法导入 embedding service，跳过向量生成")
            return

        embedding_service = get_embedding_service()
        if not embedding_service:
            logger.warning("Embedding service 未初始化，跳过向量生成")
            return

        try:
            # 为每个 chunk 生成嵌入
            for chunk in outline_source.chunks:
                embedding = await embedding_service.create_embedding(chunk.content)
                chunk.embedding = embedding

            outline_source.embedding_ready = True
            outline_source.embedding_model = settings.embedding_model

        except Exception as e:
            logger.error(f"生成大纲向量嵌入失败：{e}")

    def _extract_file_name(self, content: str, source_type: str) -> Optional[str]:
        """提取文件名（如果有）"""
        # 这个方法可以从上传的文件中提取文件名
        # 目前简单返回 None，因为 paste 没有文件名
        return None

    async def get_outline(self, outline_id: str) -> Optional[OutlineSource]:
        """获取大纲源"""
        return self._outline_sources.get(outline_id)

    async def search_outline(
        self,
        query_text: str,
        outline_id: str,
        limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        检索大纲内容

        Args:
            query_text: 查询文本
            outline_id: 大纲源 ID
            limit: 返回结果数量
            similarity_threshold: 相似度阈值

        Returns:
            List: 检索结果列表
        """
        outline = self._outline_sources.get(outline_id)
        if not outline:
            raise ValueError(f"Outline {outline_id} not found")

        if not outline.embedding_ready:
            # 如果没有生成嵌入，返回文本匹配
            return self._text_search(query_text, outline, limit)

        # 向量检索
        try:
            from app.api.app import get_embedding_service
        except ImportError:
            return self._text_search(query_text, outline, limit)

        embedding_service = get_embedding_service()
        if not embedding_service:
            return self._text_search(query_text, outline, limit)

        try:
            query_embedding = await embedding_service.create_embedding(query_text)

            # 计算每个 chunk 的相似度
            results = []
            for chunk in outline.chunks:
                if chunk.embedding:
                    similarity = self._cosine_similarity(query_embedding, chunk.embedding)
                    if similarity >= similarity_threshold:
                        results.append({
                            "chunk_id": chunk.id,
                            "content": chunk.content,
                            "similarity": similarity,
                            "chunk_index": chunk.chunk_index,
                        })

            # 按相似度排序
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"检索大纲失败：{e}")
            return self._text_search(query_text, outline, limit)

    def _text_search(
        self,
        query_text: str,
        outline: OutlineSource,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """简单的文本搜索（当向量检索不可用时）"""
        # 简单的关键词匹配
        query_keywords = query_text.lower().split()
        results = []

        for chunk in outline.chunks:
            content_lower = chunk.content.lower()
            match_count = sum(1 for kw in query_keywords if kw in content_lower)
            if match_count > 0:
                results.append({
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "similarity": match_count / len(query_keywords),
                    "chunk_index": chunk.chunk_index,
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


# 全局单例
_outline_service: Optional[OutlineIngestionService] = None


def get_outline_ingestion_service() -> OutlineIngestionService:
    """获取大纲输入服务单例"""
    global _outline_service
    if _outline_service is None:
        _outline_service = OutlineIngestionService()
    return _outline_service


def set_outline_ingestion_service(service: OutlineIngestionService):
    """设置大纲输入服务实例（用于测试）"""
    global _outline_service
    _outline_service = service