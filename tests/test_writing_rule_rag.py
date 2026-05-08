import pytest

from app.models.writing_rule import (
    RuleSeverity,
    WritingRule,
    WritingRuleApplicationMode,
    WritingRuleCategory,
)
from app.services.writing_rule_rag import WritingRuleRAGService


class _FakeRuleService:
    SEVERITY_ORDER = {
        RuleSeverity.INFO.value: 1,
        RuleSeverity.OPTIONAL.value: 2,
        RuleSeverity.RECOMMENDED.value: 3,
        RuleSeverity.STRONG.value: 4,
        RuleSeverity.REQUIRED.value: 5,
    }

    def __init__(self, *rules: WritingRule):
        self.rules = list(rules)

    async def resolve_project_rule_scope(self, project_id: str):
        return {
            "project_id": project_id,
            "is_active": True,
            "rules": list(self.rules),
            "rule_priorities": {rule.id: 99 - idx for idx, rule in enumerate(self.rules)},
        }

    def describe_project_rule_scope(self, scope):
        return {
            "project_id": scope["project_id"],
            "is_active": scope["is_active"],
            "resolved_rule_ids": [rule.id for rule in scope["rules"]],
            "resolved_rule_count": len(scope["rules"]),
        }

    def build_retrieval_query_context(self, project_id: str, context=None) -> str:
        return f"project:{project_id}\nquery:{(context or {}).get('query', '')}"

    def has_meaningful_retrieval_context(self, context=None) -> bool:
        return True

    def build_always_rule_guidance(self, rules):
        return ""

    def build_retrieved_guidance(self, rules, limit=6):
        return "\n".join(rule.name for rule in rules)

    def _clip_text(self, text: str, limit: int) -> str:
        return text[:limit]


class _FakeQdrant:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    async def search_writing_rules_by_text(self, query_text, limit=10, score_threshold=0.45, filter_conditions=None):
        self.calls.append({
            "query_text": query_text,
            "limit": limit,
            "score_threshold": score_threshold,
            "filter_conditions": filter_conditions,
        })
        return list(self.hits)


@pytest.mark.asyncio
async def test_retrieve_for_project_filters_qdrant_by_candidate_rule_ids():
    rule = WritingRule(
        id="custom_rule_1",
        name="银蓝电弧瞳色描写",
        category=WritingRuleCategory.STYLE,
        severity=RuleSeverity.RECOMMENDED,
        application_mode=WritingRuleApplicationMode.RETRIEVE_ON_MATCH,
        tags=["电弧", "瞳色"],
        content="强调银蓝电弧与冷色高亮的眼部描写。",
    )
    fake_service = _FakeRuleService(rule)
    fake_qdrant = _FakeQdrant([
        {
            "id": "custom_rule_1",
            "score": 0.83,
            "payload": {"rule_id": "custom_rule_1"},
        }
    ])

    rag = WritingRuleRAGService()
    rag._writing_rule_service = fake_service
    rag._qdrant_db = fake_qdrant

    result = await rag.retrieve_for_project(
        "project-1",
        context={"query": "描写角色眼眸里银蓝电弧闪动的质感"},
        limit=6,
    )

    assert fake_qdrant.calls == [
        {
            "query_text": "query:描写角色眼眸里银蓝电弧闪动的质感",
            "limit": 18,
            "score_threshold": 0.45,
            "filter_conditions": {"rule_id": ["custom_rule_1"]},
        }
    ]
    assert [item["id"] for item in result["retrieved_rules"]] == ["custom_rule_1"]
    assert result["retrieved_rules"][0]["reason"] == "semantic_match"


@pytest.mark.asyncio
async def test_retrieve_on_match_rule_is_filtered_out_without_explicit_term_match():
    rule = WritingRule(
        id="custom_rule_1",
        name="银蓝电弧瞳色描写",
        category=WritingRuleCategory.STYLE,
        severity=RuleSeverity.RECOMMENDED,
        application_mode=WritingRuleApplicationMode.RETRIEVE_ON_MATCH,
        tags=["电弧", "瞳色"],
        content="强调银蓝电弧与冷色高亮的眼部描写。",
    )
    fake_service = _FakeRuleService(rule)
    fake_qdrant = _FakeQdrant([
        {
            "id": "custom_rule_1",
            "score": 0.83,
            "payload": {"rule_id": "custom_rule_1"},
        }
    ])

    rag = WritingRuleRAGService()
    rag._writing_rule_service = fake_service
    rag._qdrant_db = fake_qdrant

    result = await rag.retrieve_for_project(
        "project-1",
        context={"query": "描写月光下的静谧湖面"},
        limit=6,
    )

    assert result["retrieved_rules"] == []


@pytest.mark.asyncio
async def test_retrieve_on_match_rule_can_fallback_on_explicit_match_without_qdrant_hits():
    rule = WritingRule(
        id="custom_rule_1",
        name="银蓝电弧瞳色描写",
        category=WritingRuleCategory.STYLE,
        severity=RuleSeverity.RECOMMENDED,
        application_mode=WritingRuleApplicationMode.RETRIEVE_ON_MATCH,
        tags=["电弧", "瞳色"],
        content="强调银蓝电弧与冷色高亮的眼部描写。",
    )
    fake_service = _FakeRuleService(rule)
    fake_qdrant = _FakeQdrant([])

    rag = WritingRuleRAGService()
    rag._writing_rule_service = fake_service
    rag._qdrant_db = fake_qdrant

    result = await rag.retrieve_for_project(
        "project-1",
        context={"query": "描写角色眼眸里银蓝电弧闪动的质感"},
        limit=6,
    )

    assert [item["id"] for item in result["retrieved_rules"]] == ["custom_rule_1"]
    assert result["retrieved_rules"][0]["reason"] == "explicit_match"


def test_extract_retrieve_on_match_terms_supports_stringified_tags_from_db_rows():
    rule = WritingRule.model_construct(
        id="custom_rule_1",
        name="银蓝电弧瞳色描写",
        description="",
        category=WritingRuleCategory.STYLE,
        severity=RuleSeverity.RECOMMENDED,
        application_mode=WritingRuleApplicationMode.RETRIEVE_ON_MATCH,
        tags='["电弧", "瞳色"]',
        content="强调银蓝电弧与冷色高亮的眼部描写。",
        examples=[],
        counter_examples=None,
        conditions=[],
        exceptions=None,
        is_system=False,
        version="1.0.0",
        author=None,
        source=None,
        usage_count=0,
        last_used_at=None,
    )

    rag = WritingRuleRAGService()

    assert rag._extract_retrieve_on_match_terms(rule) == ["电弧", "瞳色"]
