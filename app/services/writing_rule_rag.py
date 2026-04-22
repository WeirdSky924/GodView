"""
写作规则 RAG 服务
按项目规则作用域检索当前任务相关的写作规则
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.models.writing_rule import WritingRule, WritingRuleApplicationMode
from app.services.writing_rule_service import get_writing_rule_service

logger = logging.getLogger(__name__)


class WritingRuleRAGService:
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
            self._writing_rule_service = get_writing_rule_service()
        return self._writing_rule_service

    def _normalize_match_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            text = value
        elif isinstance(value, (list, tuple, set)):
            text = " ".join(str(item) for item in value if item not in (None, ""))
        elif isinstance(value, dict):
            text = " ".join(self._normalize_match_text(v) for v in value.values())
        else:
            text = str(value)
        return re.sub(r"\s+", "", text).lower()

    def _extract_retrieve_on_match_terms(self, rule: WritingRule) -> List[str]:
        terms: List[str] = []
        raw_tags = rule.tags or []
        if isinstance(raw_tags, str):
            try:
                parsed_tags = json.loads(raw_tags)
            except (TypeError, ValueError):
                raw_tags = [raw_tags] if raw_tags else []
            else:
                if isinstance(parsed_tags, list):
                    raw_tags = parsed_tags
                elif parsed_tags in (None, ""):
                    raw_tags = []
                else:
                    raw_tags = [parsed_tags]

        for tag in raw_tags:
            normalized = self._normalize_match_text(tag)
            if len(normalized) >= 2:
                terms.append(normalized)

        if not terms:
            for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", rule.name or ""):
                normalized = self._normalize_match_text(token)
                if len(normalized) >= 2:
                    terms.append(normalized)

        deduped: List[str] = []
        seen = set()
        for term in sorted(terms, key=len, reverse=True):
            if term in seen:
                continue
            seen.add(term)
            deduped.append(term)
        return deduped

    def _matches_retrieve_on_match(self, rule: WritingRule, context: Optional[Dict[str, Any]]) -> bool:
        if rule.application_mode != WritingRuleApplicationMode.RETRIEVE_ON_MATCH:
            return True

        haystack = self._normalize_match_text(context or {})
        if not haystack:
            return False

        terms = self._extract_retrieve_on_match_terms(rule)
        if not terms:
            return False

        return any(term in haystack for term in terms)

    def _semantic_query_text(self, query: str) -> str:
        lines = [line for line in query.splitlines() if line and not line.startswith("project:")]
        return "\n".join(lines).strip() or query

    def _rerank_rules(
        self,
        rules: List[WritingRule],
        scores: Dict[str, float],
        priorities: Dict[str, int],
    ) -> List[WritingRule]:
        def sort_key(rule: WritingRule):
            return (
                -1 if rule.application_mode in {WritingRuleApplicationMode.ALWAYS, WritingRuleApplicationMode.ALWAYS_POSTCHECK} else 0,
                -int(priorities.get(rule.id, 0)),
                -scores.get(rule.id, 0.0),
                -self._get_rule_service().SEVERITY_ORDER.get(rule.severity.value, 0),
                rule.name,
            )

        return sorted(rules, key=sort_key)

    async def retrieve_for_project(
        self,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
        limit: int = 6,
    ) -> Dict[str, Any]:
        service = self._get_rule_service()
        scope = await service.resolve_project_rule_scope(project_id)
        scope_summary = service.describe_project_rule_scope(scope)
        if not scope.get("is_active"):
            return {
                "project_id": project_id,
                "query": "",
                "resolved_scope": scope_summary,
                "retrieved_rules": [],
                "always_rules": [],
                "rendered_guidance": "",
            }

        rules: List[WritingRule] = scope.get("rules", [])
        query = service.build_retrieval_query_context(project_id, context)
        semantic_query = self._semantic_query_text(query)

        always_rules = [
            rule for rule in rules
            if rule.application_mode in {WritingRuleApplicationMode.ALWAYS, WritingRuleApplicationMode.ALWAYS_POSTCHECK}
        ]
        candidate_rules = [
            rule for rule in rules
            if rule.application_mode in {
                WritingRuleApplicationMode.RETRIEVE,
                WritingRuleApplicationMode.RETRIEVE_POSTCHECK,
                WritingRuleApplicationMode.RETRIEVE_ON_MATCH,
            }
        ]
        candidate_ids = [rule.id for rule in candidate_rules]

        retrieved_rules: List[WritingRule] = []
        scores: Dict[str, float] = {}
        qdrant = self._get_qdrant_db()
        has_retrieval_context = service.has_meaningful_retrieval_context(context)
        if qdrant and candidate_ids and semantic_query and has_retrieval_context:
            raw_hits = await qdrant.search_writing_rules_by_text(
                semantic_query,
                limit=max(limit * 3, 12),
                filter_conditions={"rule_id": candidate_ids},
            )
            hit_ids = [str(hit.get("id")) for hit in raw_hits]
            for hit in raw_hits:
                hit_id = str(hit.get("id"))
                scores[hit_id] = float(hit.get("score", 0.0))
            if hit_ids:
                rule_map = {rule.id: rule for rule in rules}
                retrieved_rules = [rule_map[rule_id] for rule_id in hit_ids if rule_id in rule_map]

        retrieved_rules = [
            rule for rule in retrieved_rules
            if self._matches_retrieve_on_match(rule, context)
        ]

        retrieved_ids = {rule.id for rule in retrieved_rules}
        fallback_rules = [
            rule for rule in candidate_rules
            if rule.application_mode == WritingRuleApplicationMode.RETRIEVE_ON_MATCH
            and rule.id not in retrieved_ids
            and self._matches_retrieve_on_match(rule, context)
        ]

        reranked = self._rerank_rules(
            rules=[*always_rules, *retrieved_rules, *fallback_rules],
            scores=scores,
            priorities=scope.get("rule_priorities", {}),
        )

        deduped: List[WritingRule] = []
        seen = set()
        for rule in reranked:
            if rule.id in seen:
                continue
            seen.add(rule.id)
            deduped.append(rule)
            if len(deduped) >= limit:
                break

        always_ids = {rule.id for rule in always_rules}
        fallback_ids = {rule.id for rule in fallback_rules}
        serialized = []
        for rule in deduped:
            if rule.id in always_ids:
                reason = "always"
            elif rule.id in fallback_ids and rule.id not in scores:
                reason = "explicit_match"
            else:
                reason = "semantic_match"
            serialized.append({
                "id": rule.id,
                "name": rule.name,
                "severity": rule.severity.value,
                "application_mode": rule.application_mode.value,
                "score": scores.get(rule.id, 1.0 if rule.id in always_ids else 0.0),
                "summary": service._clip_text(rule.content, 180),
                "tags": rule.tags,
                "reason": reason,
            })

        guidance_parts = []
        always_guidance = service.build_always_rule_guidance(always_rules)
        if always_guidance:
            guidance_parts.append(always_guidance)
        retrieved_only = [rule for rule in deduped if rule.id not in always_ids]
        retrieved_guidance = service.build_retrieved_guidance(retrieved_only, limit=limit)
        if retrieved_guidance:
            guidance_parts.append(retrieved_guidance)

        return {
            "project_id": project_id,
            "query": query,
            "resolved_scope": scope_summary,
            "retrieved_rules": serialized,
            "always_rules": [rule.id for rule in always_rules],
            "rendered_guidance": "\n\n".join(guidance_parts).strip(),
        }


_writing_rule_rag_service: Optional[WritingRuleRAGService] = None


def get_writing_rule_rag_service() -> WritingRuleRAGService:
    global _writing_rule_rag_service
    if _writing_rule_rag_service is None:
        _writing_rule_rag_service = WritingRuleRAGService()
    return _writing_rule_rag_service
