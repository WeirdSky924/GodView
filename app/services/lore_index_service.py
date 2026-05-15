"""
设定索引服务
负责设定的向量化、索引管理和智能检索

支持三种检索模式：
1. 关键词匹配 - 基于设定的 keywords 字段
2. 语义搜索 - 基于向量相似度
3. 关联查询 - 基于 related_characters/locations/items 字段
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class LoreIndexService:
    """设定索引服务 - 管理设定的智能检索"""

    def __init__(self):
        self._embedding_service = None
        self._qdrant_db = None
        self._lore_cache: Dict[str, Dict[str, Any]] = {}  # project_id -> {lore_id: lore_data}
        self._keyword_index: Dict[str, Dict[str, Set[str]]] = {}  # project_id -> {keyword: {lore_ids}}
        self._relation_index: Dict[str, Dict[str, Set[str]]] = {}  # project_id -> {entity_id: {lore_ids}}

    def _get_embedding_service(self):
        """懒加载 Embedding 服务"""
        if self._embedding_service is None:
            from app.api.app import embedding_service
            self._embedding_service = embedding_service
        return self._embedding_service

    def _get_qdrant_db(self):
        """懒加载 Qdrant 连接"""
        if self._qdrant_db is None:
            from app.api.app import qdrant_db
            self._qdrant_db = qdrant_db
        return self._qdrant_db

    async def index_lore(
        self,
        lore_id: str,
        project_id: str,
        title: str,
        content: str,
        category: str = "custom",
        priority: str = "standard",
        keywords: Optional[List[str]] = None,
        related_characters: Optional[List[str]] = None,
        related_locations: Optional[List[str]] = None,
        related_items: Optional[List[str]] = None,
    ) -> bool:
        """
        索引单条设定（存入 Qdrant 向量库）

        Args:
            lore_id: 设定 ID
            project_id: 项目 ID
            title: 设定标题
            content: 设定内容
            category: 设定类别
            priority: 设定优先级
            keywords: 关键词列表
            related_characters: 关联角色
            related_locations: 关联地点
            related_items: 关联物品

        Returns:
            bool: 是否成功
        """
        try:
            qdrant = self._get_qdrant_db()
            if not qdrant:
                logger.warning("Qdrant 未连接，跳过向量索引")
                return False

            # 构建用于向量化的文本（标题 + 全量内容）
            text_for_embedding = f"{title}\n{content}"

            # 添加到向量库
            await qdrant.add_lore_entry(
                lore_id=lore_id,
                project_id=project_id,
                title=title,
                content=text_for_embedding,
                category=category,
                priority=priority,
                keywords=keywords or [],
            )

            # 更新内存索引
            self._update_memory_index(
                lore_id=lore_id,
                project_id=project_id,
                keywords=keywords or [],
                related_characters=related_characters or [],
                related_locations=related_locations or [],
                related_items=related_items or [],
            )

            logger.debug(f"索引设定成功: {title}")
            return True

        except Exception as e:
            logger.error(f"索引设定失败: {e}")
            return False

    def _update_memory_index(
        self,
        lore_id: str,
        project_id: str,
        keywords: List[str],
        related_characters: List[str],
        related_locations: List[str],
        related_items: List[str],
    ):
        """更新内存中的关键词和关联索引"""
        # 初始化项目索引
        if project_id not in self._keyword_index:
            self._keyword_index[project_id] = {}
        if project_id not in self._relation_index:
            self._relation_index[project_id] = {}

        # 更新关键词索引
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower not in self._keyword_index[project_id]:
                self._keyword_index[project_id][keyword_lower] = set()
            self._keyword_index[project_id][keyword_lower].add(lore_id)

        # 更新关联索引
        all_entities = related_characters + related_locations + related_items
        for entity_id in all_entities:
            if entity_id not in self._relation_index[project_id]:
                self._relation_index[project_id][entity_id] = set()
            self._relation_index[project_id][entity_id].add(lore_id)

    def remove_from_memory_index(self, project_id: str, lore_id: str):
        """从内存索引中移除设定"""
        # 从关键词索引移除
        if project_id in self._keyword_index:
            for keyword, lore_ids in self._keyword_index[project_id].items():
                lore_ids.discard(lore_id)

        # 从关联索引移除
        if project_id in self._relation_index:
            for entity_id, lore_ids in self._relation_index[project_id].items():
                lore_ids.discard(lore_id)

    async def delete_lore(self, lore_id: str, project_id: Optional[str] = None) -> bool:
        """从 Qdrant 与内存索引中移除设定索引。PostgreSQL 仍是权威数据源。"""
        try:
            qdrant = self._get_qdrant_db()
            if not qdrant:
                logger.warning("Qdrant 未连接，跳过设定向量删除")
                if project_id:
                    self.remove_from_memory_index(str(project_id), str(lore_id))
                return False

            success = await qdrant.delete_lore_entry(str(lore_id))
            if project_id:
                self.remove_from_memory_index(str(project_id), str(lore_id))
            if not success:
                logger.warning(f"删除设定向量索引未完成: lore_id={lore_id}, project_id={project_id}")
            return bool(success)
        except Exception as e:
            logger.error(f"删除设定索引失败: {e}")
            if project_id:
                self.remove_from_memory_index(str(project_id), str(lore_id))
            return False

    async def search_by_keywords(
        self,
        project_id: str,
        keywords: List[str],
        limit: int = 10,
    ) -> List[str]:
        """
        通过关键词搜索设定 ID

        Args:
            project_id: 项目 ID
            keywords: 关键词列表
            limit: 返回数量

        Returns:
            List[str]: 设定 ID 列表
        """
        if project_id not in self._keyword_index:
            return []

        matched_ids: Set[str] = set()
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in self._keyword_index[project_id]:
                matched_ids.update(self._keyword_index[project_id][keyword_lower])

        return list(matched_ids)[:limit]

    async def search_by_semantic(
        self,
        project_id: str,
        query_text: str,
        limit: int = 10,
        score_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        语义搜索设定

        Args:
            project_id: 项目 ID
            query_text: 查询文本
            limit: 返回数量
            score_threshold: 相似度阈值

        Returns:
            List[Dict]: 搜索结果 [{id, score, payload}]
        """
        try:
            qdrant = self._get_qdrant_db()
            if not qdrant:
                logger.warning("Qdrant 未连接，无法进行语义搜索")
                return []

            results = await qdrant.search_lore_by_text(
                query_text=query_text,
                project_id=project_id,
                limit=limit,
            )

            # 过滤低分结果
            return [r for r in results if r.get("score", 0) >= score_threshold]

        except Exception as e:
            logger.error(f"语义搜索失败: {e}")
            return []

    async def search_by_relation(
        self,
        project_id: str,
        entity_ids: List[str],
        limit: int = 10,
    ) -> List[str]:
        """
        通过关联关系搜索设定

        Args:
            project_id: 项目 ID
            entity_ids: 实体 ID 列表（角色/地点/物品）
            limit: 返回数量

        Returns:
            List[str]: 设定 ID 列表
        """
        if project_id not in self._relation_index:
            return []

        matched_ids: Set[str] = set()
        for entity_id in entity_ids:
            if entity_id in self._relation_index[project_id]:
                matched_ids.update(self._relation_index[project_id][entity_id])

        return list(matched_ids)[:limit]

    async def smart_search(
        self,
        project_id: str,
        query: str,
        keywords: Optional[List[str]] = None,
        related_entities: Optional[List[str]] = None,
        use_semantic: bool = True,
        use_keywords: bool = True,
        use_relations: bool = True,
        limit: int = 15,
    ) -> List[str]:
        """
        智能组合搜索 - 综合关键词、语义、关联三种方式

        Args:
            project_id: 项目 ID
            query: 用户查询文本
            keywords: 提取的关键词
            related_entities: 关联实体 ID
            use_semantic: 是否使用语义搜索
            use_keywords: 是否使用关键词搜索
            use_relations: 是否使用关联搜索
            limit: 返回数量

        Returns:
            List[str]: 设定 ID 列表（按相关性排序）
        """
        lore_scores: Dict[str, float] = {}

        # 1. 语义搜索（权重最高）
        if use_semantic and query:
            semantic_results = await self.search_by_semantic(
                project_id=project_id,
                query_text=query,
                limit=limit,
                score_threshold=0.4,
            )
            for result in semantic_results:
                lore_id = str(result.get("id", ""))
                score = result.get("score", 0)
                lore_scores[lore_id] = lore_scores.get(lore_id, 0) + score * 1.0

        # 2. 关键词搜索（中等权重）
        if use_keywords and keywords:
            keyword_ids = await self.search_by_keywords(
                project_id=project_id,
                keywords=keywords,
                limit=limit,
            )
            for lore_id in keyword_ids:
                lore_scores[lore_id] = lore_scores.get(lore_id, 0) + 0.7

        # 3. 关联搜索（较低权重，作为补充）
        if use_relations and related_entities:
            relation_ids = await self.search_by_relation(
                project_id=project_id,
                entity_ids=related_entities,
                limit=limit,
            )
            for lore_id in relation_ids:
                lore_scores[lore_id] = lore_scores.get(lore_id, 0) + 0.5

        # 按分数排序
        sorted_lores = sorted(
            lore_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [lore_id for lore_id, _ in sorted_lores[:limit]]

    async def sync_project_lores(self, project_id: str) -> int:
        """
        同步项目所有设定到向量索引

        Args:
            project_id: 项目 ID

        Returns:
            int: 成功索引数量
        """
        try:
            from app.api.app import postgres_db
            if not postgres_db:
                logger.warning("数据库未连接，无法同步设定")
                return 0

            # 获取所有设定
            lores = await postgres_db.execute_query("""
                SELECT id, title, content, category, priority, keywords,
                       related_characters, related_locations, related_items
                FROM lore_entries
                WHERE project_id = CAST(:project_id AS UUID)
            """, {"project_id": project_id})

            if not lores:
                return 0

            indexed_count = 0
            for lore in lores:
                keywords = lore.get("keywords", [])
                if isinstance(keywords, str):
                    try:
                        keywords = json.loads(keywords)
                    except:
                        keywords = []

                related_characters = lore.get("related_characters", [])
                if isinstance(related_characters, str):
                    try:
                        related_characters = json.loads(related_characters)
                    except:
                        related_characters = []

                related_locations = lore.get("related_locations", [])
                if isinstance(related_locations, str):
                    try:
                        related_locations = json.loads(related_locations)
                    except:
                        related_locations = []

                related_items = lore.get("related_items", [])
                if isinstance(related_items, str):
                    try:
                        related_items = json.loads(related_items)
                    except:
                        related_items = []

                success = await self.index_lore(
                    lore_id=str(lore["id"]),
                    project_id=project_id,
                    title=lore.get("title", ""),
                    content=lore.get("content", ""),
                    category=lore.get("category", "custom"),
                    priority=lore.get("priority", "standard"),
                    keywords=keywords,
                    related_characters=related_characters,
                    related_locations=related_locations,
                    related_items=related_items,
                )
                if success:
                    indexed_count += 1

            logger.info(f"同步项目 {project_id} 设定索引: {indexed_count}/{len(lores)}")
            return indexed_count

        except Exception as e:
            logger.error(f"同步设定索引失败: {e}")
            return 0

    async def get_constitutional_rules(self, project_id: str) -> List[Dict[str, Any]]:
        """
        获取宪法级规则（必须始终加载）

        Args:
            project_id: 项目 ID

        Returns:
            List[Dict]: 宪法级设定列表
        """
        try:
            from app.api.app import postgres_db
            if not postgres_db:
                return []

            lores = await postgres_db.execute_query("""
                SELECT id, title, content, category, keywords
                FROM lore_entries
                WHERE project_id = CAST(:project_id AS UUID)
                AND priority = 'constitutional'
                ORDER BY created_at
            """, {"project_id": project_id})

            return [dict(l) for l in (lores or [])]

        except Exception as e:
            logger.error(f"获取宪法级规则失败: {e}")
            return []

    def clear_cache(self, project_id: Optional[str] = None):
        """清除缓存"""
        if project_id:
            self._lore_cache.pop(project_id, None)
            self._keyword_index.pop(project_id, None)
            self._relation_index.pop(project_id, None)
        else:
            self._lore_cache.clear()
            self._keyword_index.clear()
            self._relation_index.clear()


# 全局单例
_lore_index_service: Optional[LoreIndexService] = None


def get_lore_index_service() -> LoreIndexService:
    """获取设定索引服务单例"""
    global _lore_index_service
    if _lore_index_service is None:
        _lore_index_service = LoreIndexService()
    return _lore_index_service
