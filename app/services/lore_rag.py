"""
静态设定 RAG 服务
负责管理和检索世界观、历史、势力等"世界宪法"级设定
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database.qdrant import QdrantDatabase
from app.models.lore import (
    LoreCategory,
    LoreConflict,
    LoreEntry,
    LorePriority,
    LoreSearchResult,
    LoreValidationResult,
)

logger = logging.getLogger(__name__)


class LoreRAGService:
    """静态设定 RAG 服务类"""

    def __init__(self, qdrant_db: QdrantDatabase):
        """
        初始化服务

        Args:
            qdrant_db: Qdrant 数据库实例
        """
        self.qdrant = qdrant_db
        self._lore_cache: Dict[str, LoreEntry] = {}

    async def add_lore(
        self,
        lore: LoreEntry,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """
        添加设定条目

        Args:
            lore: 设定条目
            embedding: 向量嵌入（如不提供则自动生成）

        Returns:
            str: 设定 ID
        """
        # 存储到 Qdrant
        embedding_id = await self.qdrant.add_lore_entry(
            lore_id=lore.id,
            project_id=lore.project_id,
            title=lore.title,
            content=lore.content,
            category=lore.category.value,
            priority=lore.priority.value,
            keywords=lore.keywords,
            embedding=embedding,
        )

        if embedding_id:
            lore.embedding_id = embedding_id

        # 缓存
        self._lore_cache[lore.id] = lore

        logger.info(f"添加设定: {lore.title} (ID: {lore.id})")
        return lore.id

    async def search_lore(
        self,
        project_id: str,
        query: str,
        category: Optional[LoreCategory] = None,
        priority: Optional[LorePriority] = None,
        limit: int = 10,
    ) -> List[LoreSearchResult]:
        """
        搜索设定

        Args:
            project_id: 项目 ID
            query: 查询文本
            category: 类别过滤
            priority: 优先级过滤
            limit: 返回数量

        Returns:
            List: 搜索结果
        """
        results = await self.qdrant.search_lore_by_text(
            query_text=query,
            project_id=project_id,
            category=category.value if category else None,
            limit=limit,
        )

        return [
            LoreSearchResult(
                id=r["id"],
                title=r["payload"].get("title", ""),
                category=LoreCategory(r["payload"].get("category", "custom")),
                priority=LorePriority(r["payload"].get("priority", "standard")),
                summary=r["payload"].get("summary"),
                score=r["score"],
                keywords=r["payload"].get("keywords", []),
            )
            for r in results
        ]

    async def get_lore(self, lore_id: str) -> Optional[LoreEntry]:
        """
        获取设定详情

        Args:
            lore_id: 设定 ID

        Returns:
            Optional[LoreEntry]: 设定条目
        """
        # 先检查缓存
        if lore_id in self._lore_cache:
            return self._lore_cache[lore_id]

        # 从 Qdrant 获取
        # TODO: 实现从 Qdrant 获取单个条目的逻辑
        return None

    async def get_constitutional_rules(
        self,
        project_id: str,
    ) -> List[LoreEntry]:
        """
        获取宪法级规则（不可违反的核心设定）

        Args:
            project_id: 项目 ID

        Returns:
            List: 宪法级规则列表
        """
        results = await self.qdrant.get_constitutional_rules(project_id)

        return [
            LoreEntry(
                id=r["id"],
                project_id=r["payload"].get("project_id", project_id),
                title=r["payload"].get("title", ""),
                category=LoreCategory(r["payload"].get("category", "custom")),
                priority=LorePriority.CONSTITUTIONAL,
                content=r["payload"].get("content", ""),
                keywords=r["payload"].get("keywords", []),
            )
            for r in results
        ]

    async def validate_against_lore(
        self,
        project_id: str,
        content: str,
        check_constitutional: bool = True,
    ) -> LoreValidationResult:
        """
        验证内容是否符合设定

        Args:
            project_id: 项目 ID
            content: 要验证的内容
            check_constitutional: 是否检查宪法级规则

        Returns:
            LoreValidationResult: 验证结果
        """
        conflicts = []
        warnings = []
        suggestions = []

        # 搜索相关设定
        relevant_lore = await self.search_lore(
            project_id=project_id,
            query=content,
            limit=10,
        )

        # 检查宪法级规则
        if check_constitutional:
            constitutional_rules = await self.get_constitutional_rules(project_id)

            for rule in constitutional_rules:
                # 简单的关键词检查（实际应用中可以使用 LLM 进行更复杂的检查）
                for constraint in rule.constraints:
                    if constraint.lower() in content.lower():
                        warnings.append(f"可能违反宪法级规则 '{rule.title}': {constraint}")

        # 检查关键词冲突
        # TODO: 实现更复杂的冲突检测逻辑

        return LoreValidationResult(
            valid=len(conflicts) == 0,
            conflicts=conflicts,
            warnings=warnings,
            suggestions=suggestions,
        )

    async def get_lore_context_for_generation(
        self,
        project_id: str,
        topic: str,
        characters: Optional[List[str]] = None,
        location: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """
        获取生成上下文（用于 AI 生成时提供设定背景）

        Args:
            project_id: 项目 ID
            topic: 主题
            characters: 相关角色
            location: 相关地点
            limit: 返回数量

        Returns:
            str: 上下文字符串
        """
        # 搜索相关设定
        results = await self.search_lore(
            project_id=project_id,
            query=topic,
            limit=limit,
        )

        # 构建上下文
        context_parts = ["## 相关设定\n"]

        for i, lore in enumerate(results, 1):
            context_parts.append(f"### {i}. {lore.title}")
            context_parts.append(f"类别: {lore.category.value} | 优先级: {lore.priority.value}")
            if lore.summary:
                context_parts.append(f"摘要: {lore.summary}")
            context_parts.append("")

        # 添加宪法级规则
        constitutional = await self.get_constitutional_rules(project_id)
        if constitutional:
            context_parts.append("## 核心规则（不可违反）\n")
            for rule in constitutional[:3]:
                context_parts.append(f"- {rule.title}: {rule.content[:200]}...")

        return "\n".join(context_parts)

    async def update_lore(
        self,
        lore_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """
        更新设定

        Args:
            lore_id: 设定 ID
            updates: 更新内容

        Returns:
            bool: 是否成功
        """
        if lore_id in self._lore_cache:
            lore = self._lore_cache[lore_id]
            for key, value in updates.items():
                if hasattr(lore, key):
                    setattr(lore, key, value)
            lore.updated_at = datetime.utcnow()

            # 更新 Qdrant
            # TODO: 实现更新向量数据的逻辑
            return True
        return False

    async def delete_lore(self, lore_id: str) -> bool:
        """
        删除设定

        Args:
            lore_id: 设定 ID

        Returns:
            bool: 是否成功
        """
        # 从缓存移除
        if lore_id in self._lore_cache:
            del self._lore_cache[lore_id]

        # 从 Qdrant 删除
        return await self.qdrant.delete_lore_entry(lore_id)

    async def get_lore_by_category(
        self,
        project_id: str,
        category: LoreCategory,
        limit: int = 50,
    ) -> List[LoreEntry]:
        """
        按类别获取设定

        Args:
            project_id: 项目 ID
            category: 设定类别
            limit: 返回数量

        Returns:
            List: 设定列表
        """
        # 搜索该类别下的所有设定
        results = await self.qdrant.search_lore_by_text(
            query_text="",  # 空查询以获取所有
            project_id=project_id,
            category=category.value,
            limit=limit,
        )

        return [
            LoreEntry(
                id=r["id"],
                project_id=r["payload"].get("project_id", project_id),
                title=r["payload"].get("title", ""),
                category=category,
                priority=LorePriority(r["payload"].get("priority", "standard")),
                content=r["payload"].get("content", ""),
                keywords=r["payload"].get("keywords", []),
            )
            for r in results
        ]
