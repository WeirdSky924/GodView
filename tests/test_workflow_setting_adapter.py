import pytest

from app.models.workflow_definition import NodeType, WorkflowNode
from app.models.workflow_execution import WorkflowExecution, WorkflowStatus
from app.services.workflow_adapters import setting_adapter as setting_adapter_module
from app.services.workflow_engine import WorkflowEngine

from tests.workflow_test_fakes import FakeAgentResponse, FakeDiscussionDB


class _FakeSettingIndexService:
    def __init__(self, lore_ids=None, *, fail=False):
        self.lore_ids = lore_ids or []
        self.fail = fail
        self.calls = []

    async def smart_search(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.fail:
            raise RuntimeError("index unavailable")
        return self.lore_ids


class _FakeSettingDB:
    def __init__(self, rows_by_id=None, keyword_rows=None):
        self.rows_by_id = rows_by_id or {}
        self.keyword_rows = keyword_rows or []
        self.queries = []

    async def execute_query(self, query, params=None):
        params = params or {}
        self.queries.append({"query": query, "params": dict(params)})
        if "id = CAST(:id AS UUID)" in query:
            row = self.rows_by_id.get(params.get("id"))
            return [dict(row)] if row else []
        if "ILIKE :query" in query:
            return [dict(row) for row in self.keyword_rows[: params.get("limit", 10)]]
        return []


class TestSettingWorkflowAdapter:
    def setup_method(self):
        self.adapter = setting_adapter_module.SettingWorkflowAdapter()

    def _make_execution(self, *, context=None):
        return WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            context=context or {},
            node_states={},
        )

    def _make_node(self, *, config=None):
        return WorkflowNode(
            id="setting",
            node_type=NodeType.AGENT,
            agent_type="setting",
            label="设定 Agent",
            config=config or {},
        )

    @staticmethod
    def _assert_read_only_shape(result):
        required_keys = {
            "lore_entries",
            "fixed_lore_entries",
            "dynamic_lore_entries",
            "selected_lore_entries",
            "setting_updates",
            "new_lores",
            "updated_lores",
            "validated_lores",
            "setting_query",
            "setting_source",
            "setting_count",
            "fixed_lore_count",
            "dynamic_lore_count",
            "setting_context_summary",
            "setting_conflict_warnings",
            "setting_read_only",
            "warnings",
        }
        assert required_keys <= set(result.keys())
        assert result["selected_lore_entries"] == result["lore_entries"]
        assert result["setting_updates"] == []
        assert result["new_lores"] == []
        assert result["updated_lores"] == []
        assert result["validated_lores"] == []
        assert result["setting_read_only"] is True
        assert result["setting_count"] == len(result["lore_entries"])
        assert result["fixed_lore_count"] == len(result["fixed_lore_entries"])
        assert result["dynamic_lore_count"] == len(result["dynamic_lore_entries"])
        assert result["setting_conflict_warnings"] == result["warnings"]
        assert result["setting_context_summary"] == {
            "fixed_priorities": ["constitutional", "core"],
            "dynamic_source": result["setting_source"],
            "query": result["setting_query"],
        }

    @pytest.mark.asyncio
    async def test_filters_context_lore_entries_without_returning_all(self):
        result = await self.adapter.execute(
            node=self._make_node(config={"setting_limit": 5}),
            execution=self._make_execution(
                context={
                    "chapter_outline": {
                        "title": "雾港追踪",
                        "summary": "林砚在雾港调查潮汐裂隙。",
                    },
                    "selected_characters": ["林砚"],
                    "lore_entries": [
                        {
                            "id": "lore-1",
                            "title": "雾港潮汐规则",
                            "summary": "潮汐裂隙会在雾港夜间扩张。",
                            "content": "林砚曾在雾港记录裂隙。",
                            "keywords": ["雾港", "潮汐裂隙"],
                            "related_characters": ["林砚"],
                        },
                        {
                            "id": "lore-2",
                            "title": "沙漠商路",
                            "summary": "远方沙漠的贸易路线。",
                            "content": "与当前章节无关。",
                            "keywords": ["沙漠"],
                        },
                        {
                            "id": "lore-3",
                            "title": "海港税则",
                            "summary": "商会按货物重量收税。",
                            "content": "这条设定和雾港、潮汐裂隙、林砚无关。",
                            "keywords": ["海港", "商会", "货税"],
                        },
                    ],
                }
            ),
            db=None,
        )

        self._assert_read_only_shape(result)
        assert [entry["id"] for entry in result["lore_entries"]] == ["lore-1"]
        assert result["fixed_lore_entries"] == []
        assert [entry["id"] for entry in result["dynamic_lore_entries"]] == ["lore-1"]
        assert result["setting_source"] == "context_filtered"
        assert "雾港追踪" in result["setting_query"]

    @pytest.mark.asyncio
    async def test_searches_existing_lore_by_query_when_context_pool_missing(self, monkeypatch):
        index_service = _FakeSettingIndexService(lore_ids=["lore-db-1"])
        monkeypatch.setattr(setting_adapter_module, "get_lore_index_service", lambda: index_service)
        db = _FakeSettingDB(
            rows_by_id={
                "lore-db-1": {
                    "id": "lore-db-1",
                    "title": "裂钟禁令",
                    "summary": "裂钟响起时禁止穿越钟楼。",
                    "content": "守夜人必须封锁钟楼。",
                    "keywords": ["裂钟", "钟楼"],
                }
            }
        )

        result = await self.adapter.execute(
            node=self._make_node(config={"setting_limit": 3}),
            execution=self._make_execution(
                context={
                    "chapter_outline": {
                        "title": "裂钟回响",
                        "summary": "守夜人登上钟楼阻止裂钟再次鸣响。",
                    }
                }
            ),
            db=db,
        )

        self._assert_read_only_shape(result)
        assert result["setting_source"] == "semantic_index"
        assert result["fixed_lore_entries"] == []
        assert [entry["id"] for entry in result["dynamic_lore_entries"]] == ["lore-db-1"]
        assert [entry["id"] for entry in result["lore_entries"]] == ["lore-db-1"]
        assert index_service.calls[0]["project_id"] == "test-project"
        assert "裂钟回响" in index_service.calls[0]["query"]
        assert index_service.calls[0]["limit"] == 3

    @pytest.mark.asyncio
    async def test_empty_query_returns_no_lore_without_db_search(self):
        db = _FakeSettingDB(keyword_rows=[{"id": "should-not-load", "title": "不应全量加载"}])

        result = await self.adapter.execute(
            node=self._make_node(),
            execution=self._make_execution(context={}),
            db=db,
        )

        self._assert_read_only_shape(result)
        assert result["lore_entries"] == []
        assert result["fixed_lore_entries"] == []
        assert result["dynamic_lore_entries"] == []
        assert result["setting_source"] == "empty"
        assert result["warnings"]
        assert db.queries == []

    @pytest.mark.asyncio
    async def test_index_failure_uses_limited_keyword_search(self, monkeypatch):
        index_service = _FakeSettingIndexService(fail=True)
        monkeypatch.setattr(setting_adapter_module, "get_lore_index_service", lambda: index_service)
        db = _FakeSettingDB(
            keyword_rows=[
                {
                    "id": "keyword-1",
                    "title": "雾港旧约",
                    "summary": "雾港居民遵守旧约。",
                    "content": "旧约约束潮汐夜行动。",
                    "keywords": ["雾港"],
                }
            ]
        )

        result = await self.adapter.execute(
            node=self._make_node(config={"setting_limit": 1}),
            execution=self._make_execution(context={"chapter_summary": "雾港潮汐夜"}),
            db=db,
        )

        self._assert_read_only_shape(result)
        assert result["setting_source"] == "keyword_db"
        assert result["fixed_lore_entries"] == []
        assert [entry["id"] for entry in result["dynamic_lore_entries"]] == ["keyword-1"]
        assert [entry["id"] for entry in result["lore_entries"]] == ["keyword-1"]
        assert db.queries[-1]["params"]["limit"] == 1
        assert any("设定索引检索失败" in warning for warning in result["warnings"])


def test_setting_workflow_node_registry_uses_service_adapter():
    from app.services.workflow_node_registry import get_workflow_node_adapter, get_workflow_node_profile

    profile = get_workflow_node_profile("setting")
    assert profile is not None
    assert profile.kind == "service_adapter"
    assert get_workflow_node_adapter("setting") is not None


@pytest.mark.asyncio
async def test_read_only_setting_output_does_not_trigger_lore_save(monkeypatch):
    engine = WorkflowEngine()

    async def fail_save(*args, **kwargs):
        raise AssertionError("read-only setting output must not be saved")

    monkeypatch.setattr(engine, "_save_lore_from_setting", fail_save)

    class ReadOnlySettingAgent:
        _stream_callback = None
        _memory = None
        name = "read-only-setting-agent"
        model = None

        async def execute(self, context):
            return FakeAgentResponse({"setting_read_only": True, "lore_entries": []})

    node = WorkflowNode(
        id="setting",
        node_type=NodeType.AGENT,
        agent_type="setting",
        label="设定 Agent",
    )
    execution = WorkflowExecution(
        workflow_id="test-wf",
        project_id="test-project",
        status=WorkflowStatus.RUNNING,
        context={},
        node_states={},
    )

    payload, result, _ = await engine._run_agent_execution(
        agent=ReadOnlySettingAgent(),
        context={},
        execution=execution,
        node=node,
        db=FakeDiscussionDB(),
    )

    assert result.success is True
    assert payload == {"setting_read_only": True, "lore_entries": []}
