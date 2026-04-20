"""
写作规则向量索引服务
负责将写作规则同步到 Qdrant，并提供初始化入口
"""

import logging
from typing import Optional

from app.models.writing_rule import WritingRule

logger = logging.getLogger(__name__)


class WritingRuleIndexService:
    def __init__(self):
        self._qdrant_db = None
        self._writing_rule_service = None

    def _get_qdrant_db(self):
        if self._qdrant_db is None:
            from app.api.app import qdrant_db
            self._qdrant_db = qdrant_db
        return self._qdrant_db

    def _get_rule_service(self):
        if self._writing_rule_service is None:
            from app.services.writing_rule_service import get_writing_rule_service
            self._writing_rule_service = get_writing_rule_service()
        return self._writing_rule_service

    def _build_index_text(self, rule: WritingRule) -> str:
        parts = [
            rule.name,
            rule.description,
            rule.content,
            f"category:{rule.category.value}",
            f"severity:{rule.severity.value}",
            f"application_mode:{rule.application_mode.value}",
        ]
        if rule.tags:
            parts.append("tags:" + ", ".join(rule.tags))
        if rule.examples:
            parts.append("examples:\n" + "\n".join(rule.examples[:3]))
        if rule.counter_examples:
            parts.append("counter_examples:\n" + "\n".join(rule.counter_examples[:2]))
        if rule.exceptions:
            parts.append("exceptions:\n" + "\n".join(rule.exceptions[:2]))
        return "\n\n".join([part for part in parts if part])

    async def index_rule(self, rule: WritingRule) -> bool:
        qdrant = self._get_qdrant_db()
        if not qdrant:
            logger.warning("Qdrant 未连接，跳过写作规则索引")
            return False

        text = self._build_index_text(rule)
        result = await qdrant.add_writing_rule_entry(
            rule_id=rule.id,
            title=rule.name,
            content=text,
            category=rule.category.value,
            severity=rule.severity.value,
            application_mode=rule.application_mode.value,
            tags=rule.tags,
            source=rule.source,
            is_system=rule.is_system,
        )
        return bool(result)

    async def delete_rule(self, rule_id: str) -> bool:
        qdrant = self._get_qdrant_db()
        if not qdrant:
            return False
        return await qdrant.delete_writing_rule_entry(rule_id)

    async def sync_all_rules(self) -> int:
        service = self._get_rule_service()
        rules = await service.list_rules_merged(limit=1000, offset=0)
        synced = 0
        for rule in rules:
            try:
                success = await self.index_rule(rule)
            except Exception as e:
                logger.warning("写作规则索引同步中止，首个失败规则=%s, error=%s", rule.id, e)
                break

            if success:
                synced += 1
            else:
                logger.warning("写作规则索引同步中止，规则未写入: %s", rule.id)
                break

        logger.info("写作规则索引同步完成: %s 条", synced)
        return synced


_writing_rule_index_service: Optional[WritingRuleIndexService] = None


def get_writing_rule_index_service() -> WritingRuleIndexService:
    global _writing_rule_index_service
    if _writing_rule_index_service is None:
        _writing_rule_index_service = WritingRuleIndexService()
    return _writing_rule_index_service
