"""
工作流引擎单元测试
v8 Agent协作可视化工作台
"""

import pytest
from datetime import datetime
from uuid import uuid4

from app.models.workflow_definition import (
    NodeType,
    NodeStatus,
    WorkflowNode,
    WorkflowEdge,
    WorkflowDefinition,
    WorkflowDefinitionCreate,
    WorkflowValidationResult,
)
from app.models.workflow_execution import (
    WorkflowStatus,
    NodeExecutionState,
    WorkflowExecution,
)

from app.services.workflow_adapters import plot_outline_adapter as plot_outline_adapter_module
from app.services.workflow_adapters import setting_adapter as setting_adapter_module
from app.services.director import DirectorSystem
from app.services.workflow_engine import WorkflowEngine


def test_director_character_agent_accepts_uuid_current_region_id():
    """DB rows may return UUID objects for character region references."""
    region_id = uuid4()
    director = DirectorSystem(world_data={"id": "world-1", "name": "World"}, project_id="project-1")

    agent = director._create_character_agent({
        "id": str(uuid4()),
        "name": "区域角色",
        "project_id": str(uuid4()),
        "world_id": str(uuid4()),
        "current_region_id": region_id,
        "current_location": "观测塔",
    })

    assert agent.character.current_region_id == str(region_id)

class _FakeAgentResponse:
    def __init__(self, structured_data, *, success=True, error=None, contract_id=None, schema_name=None, metadata=None):
        self.success = success
        self.error = error
        self.structured_data = structured_data
        self.text_output = None
        self.data = structured_data
        self.contract_id = contract_id
        self.schema_name = schema_name
        self.schema_version = None
        self.metadata = metadata or {}
        self.mode = None




class _FakeOutlineGenerationResult:
    def __init__(self, outline, *, suggestions=None, warnings=None):
        self.outline = outline
        self.suggestions = suggestions or []
        self.warnings = warnings or []


class _FakePlotOutlineService:
    def __init__(
        self,
        *,
        stored_outline=None,
        generated_outline=None,
        suggestions=None,
        warnings=None,
        next_chapter_number=1,
    ):
        self.stored_outline = stored_outline
        self.generated_outline = generated_outline
        self.suggestions = suggestions or []
        self.warnings = warnings or []
        self.next_chapter_number = next_chapter_number
        self.calls = {
            "get_next_chapter_number": [],
            "get_chapter_outline_for_workflow": [],
            "generate_outline": [],
        }

    async def get_next_chapter_number(self, project_id):
        self.calls["get_next_chapter_number"].append(project_id)
        return self.next_chapter_number

    async def get_chapter_outline_for_workflow(self, project_id, chapter_number):
        self.calls["get_chapter_outline_for_workflow"].append(
            {"project_id": project_id, "chapter_number": chapter_number}
        )
        return self.stored_outline

    async def generate_outline(self, **kwargs):
        self.calls["generate_outline"].append(dict(kwargs))
        return _FakeOutlineGenerationResult(
            self.generated_outline,
            suggestions=self.suggestions,
            warnings=self.warnings,
        )


class _FakeDiscussionDB:
    def __init__(self):
        self.hooks = []
        self.lores = []
        self.regions = []
        self.characters = []
        self.executions = []
        self.existing_characters = {}
        self.regions_by_id = {}
        self.hooks_by_id = {}
        self.state_changes = {}

    async def save_hook(self, hook_data):
        saved = dict(hook_data)
        hook_id = saved.get("id") or f"hook-{len(self.hooks_by_id) + 1}"
        saved["id"] = hook_id
        self.hooks.append(saved)
        self.hooks_by_id[hook_id] = saved
        return hook_id

    async def update_hook_status(self, hook_id, status):
        hook = self.hooks_by_id.get(hook_id)
        if hook:
            hook["status"] = status
        return True

    async def get_hook(self, hook_id):
        hook = self.hooks_by_id.get(hook_id)
        return dict(hook) if hook else None

    async def execute_write(self, query, params):
        if "lore_entries" in query:
            self.lores.append(dict(params))
        return None

    async def execute_query(self, query, params=None):
        if "lore_entries" in query:
            return list(self.lores)
        return []

    async def save_region(self, region_data):
        saved = dict(region_data)
        region_id = saved.get("id") or f"region-{len(self.regions_by_id) + 1}"
        saved["id"] = region_id
        self.regions.append(saved)
        self.regions_by_id[region_id] = saved
        return region_id

    async def get_character_by_project_and_name(self, project_id, name):
        for character in self.existing_characters.values():
            if character.get("project_id") == project_id and character.get("name", "").lower() == name.lower():
                return dict(character)
        return None

    async def get_character(self, character_id):
        character = self.existing_characters.get(character_id)
        return dict(character) if character else None

    async def get_all_characters(self, project_id=None, role=None, limit=100):
        characters = list(self.existing_characters.values())
        if project_id:
            characters = [character for character in characters if character.get("project_id") == project_id]
        return [dict(character) for character in characters[:limit]]

    async def get_region(self, region_id):
        region = self.regions_by_id.get(region_id)
        return dict(region) if region else None

    async def save_character(self, character_data):
        saved = dict(character_data)
        self.characters.append(saved)
        if saved.get("id"):
            self.existing_characters[saved["id"]] = saved
        return saved.get("id")

    async def save_narrative_state_change(self, change_data):
        fingerprint = change_data.get("fingerprint")
        if fingerprint:
            existing = await self.get_state_change_by_fingerprint(change_data.get("project_id"), fingerprint)
            if existing:
                return existing["id"]
        saved = dict(change_data)
        change_id = saved.get("id") or f"state-change-{len(self.state_changes) + 1}"
        saved["id"] = change_id
        self.state_changes[change_id] = saved
        return change_id

    async def get_narrative_state_change(self, change_id):
        change = self.state_changes.get(change_id)
        return dict(change) if change else None

    async def get_state_change_by_fingerprint(self, project_id, fingerprint):
        for change in self.state_changes.values():
            if change.get("project_id") == project_id and change.get("fingerprint") == fingerprint:
                return dict(change)
        return None

    async def list_narrative_state_changes(
        self,
        project_id,
        entity_type=None,
        entity_id=None,
        status=None,
        change_type=None,
        limit=100,
    ):
        changes = [change for change in self.state_changes.values() if change.get("project_id") == project_id]
        if entity_type:
            changes = [change for change in changes if change.get("entity_type") == entity_type]
        if entity_id:
            changes = [change for change in changes if change.get("entity_id") == entity_id]
        if status:
            changes = [change for change in changes if change.get("status") == status]
        if change_type:
            changes = [change for change in changes if change.get("change_type") == change_type]
        return [dict(change) for change in changes[:limit]]

    async def update_narrative_state_change_status(self, change_id, status, timestamp_field=None):
        change = self.state_changes.get(change_id)
        if not change:
            return False
        change["status"] = status
        if timestamp_field:
            change[timestamp_field] = datetime.utcnow().isoformat()
        return True

    async def mark_narrative_state_change_applied(self, change_id):
        return await self.update_narrative_state_change_status(change_id, "applied", "applied_at")




class TestPlotOutlineWorkflowAdapter:
    def setup_method(self):
        self.adapter = plot_outline_adapter_module.PlotOutlineWorkflowAdapter()

    def _make_execution(self, *, context=None):
        return WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            context=context or {},
            node_states={},
        )

    @staticmethod
    def _assert_output_shape(result):
        assert set(result.keys()) == {
            "chapter_number",
            "chapter_title",
            "chapter_outline",
            "chapter_summary",
            "chapter_goals",
            "scene_directions",
            "outline_id",
            "saved_outline",
            "suggestions",
            "warnings",
            "outline_source",
        }
        assert result["saved_outline"] == result["chapter_outline"]
        assert result["scene_directions"]["chapter_number"] == result["chapter_number"]
        assert result["scene_directions"]["chapter_title"] == result["chapter_title"]
        assert result["scene_directions"]["plot_focus"] == result["chapter_summary"]
        assert result["scene_directions"]["chapter_goals"] == result["chapter_goals"]
        assert result["scene_directions"]["scenes"] == result["chapter_outline"]["scenes"]

    @pytest.mark.asyncio
    async def test_execute_prefers_context_outline_without_querying_or_generating(self, monkeypatch):
        context_outline = {
            "id": "outline-context-1",
            "chapter_number": 7,
            "title": "潮汐裂隙",
            "summary": "主角进入潮汐裂隙核心区。",
            "chapter_goals": ["确认裂隙来源", "保护洛澜"],
            "scenes": [
                {
                    "title": "裂隙入口",
                    "participating_characters": ["林砚", "洛澜"],
                }
            ],
        }
        service = _FakePlotOutlineService(generated_outline={"id": "generated-ignored"})
        monkeypatch.setattr(plot_outline_adapter_module, "get_plot_outline_service", lambda: service)

        result = await self.adapter.execute(
            node=None,
            execution=self._make_execution(
                context={
                    "chapter_num": 7,
                    "chapter_outline": context_outline,
                }
            ),
            db=None,
        )

        self._assert_output_shape(result)
        assert result["chapter_number"] == 7
        assert result["chapter_title"] == "潮汐裂隙"
        assert result["chapter_summary"] == "主角进入潮汐裂隙核心区。"
        assert result["chapter_goals"] == ["确认裂隙来源", "保护洛澜"]
        assert result["outline_id"] == "outline-context-1"
        assert result["outline_source"] == "context"
        assert result["suggestions"] == []
        assert result["warnings"] == []
        assert result["scene_directions"]["selected_characters"] == ["林砚", "洛澜"]
        assert service.calls["get_chapter_outline_for_workflow"] == []
        assert service.calls["generate_outline"] == []

    @pytest.mark.asyncio
    async def test_execute_reads_stored_outline_before_generation(self, monkeypatch):
        stored_outline = {
            "id": "outline-db-2",
            "chapter_number": 8,
            "title": "雾港余烬",
            "summary": "众人在废墟中寻找残留线索。",
            "chapter_goals": ["确认幸存者", "回收地图残片"],
            "scenes": [
                {
                    "title": "废墟搜寻",
                    "participating_characters": ["沈夜"],
                }
            ],
        }
        service = _FakePlotOutlineService(
            stored_outline=stored_outline,
            generated_outline={"id": "generated-ignored"},
        )
        monkeypatch.setattr(plot_outline_adapter_module, "get_plot_outline_service", lambda: service)

        result = await self.adapter.execute(
            node=None,
            execution=self._make_execution(context={"chapter_num": 8}),
            db=None,
        )

        self._assert_output_shape(result)
        assert result["chapter_number"] == 8
        assert result["chapter_title"] == "雾港余烬"
        assert result["outline_id"] == "outline-db-2"
        assert result["outline_source"] == "database"
        assert result["suggestions"] == []
        assert result["warnings"] == []
        assert service.calls["get_chapter_outline_for_workflow"] == [
            {"project_id": "test-project", "chapter_number": 8}
        ]
        assert service.calls["generate_outline"] == []

    @pytest.mark.asyncio
    async def test_execute_falls_back_to_generate_when_outline_missing(self, monkeypatch):
        generated_outline = {
            "id": "outline-generated-3",
            "title": "裂钟回响",
            "summary": "守夜人从回响中拼出真相。",
            "chapter_goals": "阻止裂钟再次鸣响",
            "scenes": [
                {
                    "title": "钟楼顶层",
                    "participating_characters": ["守夜人", "洛澜", "守夜人"],
                }
            ],
        }
        service = _FakePlotOutlineService(
            stored_outline=None,
            generated_outline=generated_outline,
            suggestions=["补充钟楼结构细节"],
            warnings=["上一章摘要缺失，已按有限上下文生成"],
        )
        monkeypatch.setattr(plot_outline_adapter_module, "get_plot_outline_service", lambda: service)

        result = await self.adapter.execute(
            node=None,
            execution=self._make_execution(
                context={
                    "chapter_num": 9,
                    "chapter_title": "预设标题",
                    "chapter_summary": "预设摘要",
                    "previous_chapters": [
                        {"chapter_num": 7, "title": "潮汐裂隙", "summary": "进入裂隙"},
                        {"chapter_num": 8, "title": "雾港余烬", "summary": "搜寻残片"},
                    ],
                }
            ),
            db=None,
        )

        self._assert_output_shape(result)
        assert result["chapter_number"] == 9
        assert result["chapter_title"] == "裂钟回响"
        assert result["chapter_summary"] == "守夜人从回响中拼出真相。"
        assert result["chapter_goals"] == ["阻止裂钟再次鸣响"]
        assert result["outline_id"] == "outline-generated-3"
        assert result["outline_source"] == "generated"
        assert result["suggestions"] == ["补充钟楼结构细节"]
        assert result["warnings"] == ["上一章摘要缺失，已按有限上下文生成"]
        assert result["scene_directions"]["selected_characters"] == ["守夜人", "洛澜"]
        assert service.calls["get_chapter_outline_for_workflow"] == [
            {"project_id": "test-project", "chapter_number": 9}
        ]
        assert len(service.calls["generate_outline"]) == 1
        generate_call = service.calls["generate_outline"][0]
        assert generate_call["project_id"] == "test-project"
        assert generate_call["chapter_number"] == 9
        assert "当前工作流目标章节：第9章" in generate_call["context"]
        assert "第7章《潮汐裂隙》：进入裂隙" in generate_call["previous_events"]
        assert "第8章《雾港余烬》：搜寻残片" in generate_call["previous_events"]


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
        assert set(result.keys()) == {
            "lore_entries",
            "selected_lore_entries",
            "setting_updates",
            "new_lores",
            "updated_lores",
            "validated_lores",
            "setting_query",
            "setting_source",
            "setting_count",
            "setting_read_only",
            "warnings",
        }
        assert result["selected_lore_entries"] == result["lore_entries"]
        assert result["setting_updates"] == []
        assert result["new_lores"] == []
        assert result["updated_lores"] == []
        assert result["validated_lores"] == []
        assert result["setting_read_only"] is True
        assert result["setting_count"] == len(result["lore_entries"])

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
            return _FakeAgentResponse({"setting_read_only": True, "lore_entries": []})

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
        db=_FakeDiscussionDB(),
    )

    assert result.success is True
    assert payload == {"setting_read_only": True, "lore_entries": []}


class TestWorkflowValidation:
    def setup_method(self):
        self.engine = WorkflowEngine()

    def test_validate_empty_workflow(self):
        """测试空工作流验证"""
        workflow = WorkflowDefinition(
            project_id="test-project",
            name="空工作流",
            nodes=[],
            edges=[],
        )
        result = self.engine.validate_workflow(workflow)
        assert result.valid is False
        assert "工作流没有节点" in result.errors

    def test_validate_missing_start_node(self):
        """测试缺少开始节点"""
        workflow = WorkflowDefinition(
            project_id="test-project",
            name="无开始节点",
            nodes=[
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 0}),
            ],
            edges=[],
        )
        result = self.engine.validate_workflow(workflow)
        assert result.valid is False
        assert len(result.errors) > 0  # 应该有错误

    def test_validate_missing_end_node(self):
        """测试缺少结束节点"""
        workflow = WorkflowDefinition(
            project_id="test-project",
            name="无结束节点",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
            ],
            edges=[],
        )
        result = self.engine.validate_workflow(workflow)
        assert result.valid is False
        assert len(result.errors) > 0  # 应该有错误

    def test_validate_agent_node_missing_type(self):
        """测试Agent节点缺少类型"""
        workflow = WorkflowDefinition(
            project_id="test-project",
            name="Agent缺少类型",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                WorkflowNode(id="agent1", node_type=NodeType.AGENT, label="Agent", position={"x": 0, "y": 100}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 200}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="agent1"),
                WorkflowEdge(id="e2", source="agent1", target="end"),
            ],
        )
        result = self.engine.validate_workflow(workflow)
        assert result.valid is False
        assert any("缺少 agent_type" in e for e in result.errors)

    def test_validate_valid_workflow(self):
        """测试有效工作流"""
        workflow = WorkflowDefinition(
            project_id="test-project",
            name="有效工作流",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                WorkflowNode(id="agent1", node_type=NodeType.AGENT, label="Agent", agent_type="writer", position={"x": 0, "y": 100}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 200}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="agent1"),
                WorkflowEdge(id="e2", source="agent1", target="end"),
            ],
        )
        result = self.engine.validate_workflow(workflow)
        assert result.valid is True
        assert len(result.errors) == 0


class TestCycleDetection:
    """循环检测测试"""

    def setup_method(self):
        self.engine = WorkflowEngine()

    def test_detect_no_cycle(self):
        """测试无环工作流"""
        nodes = [
            WorkflowNode(id="a", node_type=NodeType.START, label="A", position={"x": 0, "y": 0}),
            WorkflowNode(id="b", node_type=NodeType.AGENT, label="B", position={"x": 0, "y": 100}),
            WorkflowNode(id="c", node_type=NodeType.END, label="C", position={"x": 0, "y": 200}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ]
        has_cycle, cycle_path = self.engine._detect_cycle(nodes, edges)
        assert has_cycle is False
        assert cycle_path == ""

    def test_detect_simple_cycle(self):
        """测试简单环"""
        nodes = [
            WorkflowNode(id="a", node_type=NodeType.AGENT, label="A", position={"x": 0, "y": 0}),
            WorkflowNode(id="b", node_type=NodeType.AGENT, label="B", position={"x": 0, "y": 100}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="a"),
        ]
        has_cycle, cycle_path = self.engine._detect_cycle(nodes, edges)
        assert has_cycle is True
        assert cycle_path == "a -> b -> a"

    def test_detect_self_loop(self):
        """测试自环"""
        nodes = [
            WorkflowNode(id="a", node_type=NodeType.AGENT, label="A", position={"x": 0, "y": 0}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="a", target="a"),
        ]
        has_cycle, cycle_path = self.engine._detect_cycle(nodes, edges)
        assert has_cycle is True
        assert cycle_path == "a -> a"


class TestTopologicalSort:
    """拓扑排序测试"""

    def setup_method(self):
        self.engine = WorkflowEngine()

    def test_linear_order(self):
        """测试线性顺序"""
        nodes = [
            WorkflowNode(id="start", node_type=NodeType.START, label="Start", position={"x": 0, "y": 0}),
            WorkflowNode(id="a", node_type=NodeType.AGENT, label="A", position={"x": 0, "y": 100}),
            WorkflowNode(id="b", node_type=NodeType.AGENT, label="B", position={"x": 0, "y": 200}),
            WorkflowNode(id="end", node_type=NodeType.END, label="End", position={"x": 0, "y": 300}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="start", target="a"),
            WorkflowEdge(id="e2", source="a", target="b"),
            WorkflowEdge(id="e3", source="b", target="end"),
        ]
        order = self.engine._topological_sort(nodes, edges)

        # 验证顺序
        assert order.index("start") < order.index("a")
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("end")

    def test_branching_order(self):
        """测试分支顺序"""
        nodes = [
            WorkflowNode(id="start", node_type=NodeType.START, label="Start", position={"x": 0, "y": 0}),
            WorkflowNode(id="a", node_type=NodeType.AGENT, label="A", position={"x": 0, "y": 100}),
            WorkflowNode(id="b", node_type=NodeType.AGENT, label="B", position={"x": 100, "y": 100}),
            WorkflowNode(id="end", node_type=NodeType.END, label="End", position={"x": 50, "y": 200}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="start", target="a"),
            WorkflowEdge(id="e2", source="start", target="b"),
            WorkflowEdge(id="e3", source="a", target="end"),
            WorkflowEdge(id="e4", source="b", target="end"),
        ]
        order = self.engine._topological_sort(nodes, edges)

        # start 应该在最前，end 应该在最后
        assert order[0] == "start"
        assert order[-1] == "end"


class TestConnectivity:
    """连通性测试"""

    def setup_method(self):
        self.engine = WorkflowEngine()

    def test_connected_workflow(self):
        """测试连通工作流"""
        nodes = [
            WorkflowNode(id="start", node_type=NodeType.START, label="Start", position={"x": 0, "y": 0}),
            WorkflowNode(id="a", node_type=NodeType.AGENT, label="A", position={"x": 0, "y": 100}),
            WorkflowNode(id="end", node_type=NodeType.END, label="End", position={"x": 0, "y": 200}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="start", target="a"),
            WorkflowEdge(id="e2", source="a", target="end"),
        ]
        is_connected = self.engine._check_connectivity(nodes, edges)
        assert is_connected is True

    def test_disconnected_workflow(self):
        """测试不连通工作流"""
        nodes = [
            WorkflowNode(id="start", node_type=NodeType.START, label="Start", position={"x": 0, "y": 0}),
            WorkflowNode(id="a", node_type=NodeType.AGENT, label="A", position={"x": 0, "y": 100}),
            WorkflowNode(id="b", node_type=NodeType.AGENT, label="B (孤立)", position={"x": 200, "y": 100}),
            WorkflowNode(id="end", node_type=NodeType.END, label="End", position={"x": 0, "y": 200}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="start", target="a"),
            WorkflowEdge(id="e2", source="a", target="end"),
            # B 节点没有连接
        ]
        is_connected = self.engine._check_connectivity(nodes, edges)
        assert is_connected is False


class TestWorkflowExecution:
    """工作流执行测试"""

    def setup_method(self):
        self.engine = WorkflowEngine()

    @pytest.mark.asyncio
    async def test_create_workflow(self):
        """测试创建工作流"""
        create_request = WorkflowDefinitionCreate(
            project_id="test-project",
            name="测试工作流",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 100}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="end"),
            ],
        )

        workflow = await self.engine.create_workflow(create_request)

        assert workflow.id is not None
        assert workflow.name == "测试工作流"
        assert len(workflow.nodes) == 2
        assert len(workflow.edges) == 1

    @pytest.mark.asyncio
    async def test_pause_resume_workflow(self):
        """测试暂停和恢复"""
        # 创建模拟执行
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={
                "node1": NodeExecutionState(node_id="node1"),
            },
        )
        self.engine._executions[execution.id] = execution

        # 暂停
        success = await self.engine.pause_workflow(execution.id)
        assert success is True
        assert execution.status == WorkflowStatus.PAUSED

        # 恢复
        success = await self.engine.resume_workflow(execution.id)
        assert success is True
        assert execution.status == WorkflowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_cancel_workflow(self):
        """测试取消工作流"""
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={},
        )
        self.engine._executions[execution.id] = execution

        async def _fake_broadcast(*args, **kwargs):
            return None

        self.engine._broadcast_status = _fake_broadcast

        success = await self.engine.cancel_workflow(execution.id)
        assert success is True
        assert execution.status == WorkflowStatus.CANCELLED
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_node_fails_on_strict_contract_validation(self):
        """测试 Agent 节点 strict 输出缺字段时会触发 contract 校验失败。"""
        node = WorkflowNode(
            id="plotter",
            node_type=NodeType.AGENT,
            agent_type="plot_outline",
            label="章节规划",
            outputs=[
                {
                    "name": "chapter_title",
                    "target": "context",
                    "contract_id": "plot_outline.workflow_output",
                }
            ],
            position={"x": 0, "y": 0},
        )
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={
                node.id: NodeExecutionState(node_id=node.id),
            },
        )

        async def _fake_broadcast(*args, **kwargs):
            return None

        async def _fake_execute_agent_node(*args, **kwargs):
            response = _FakeAgentResponse(
                {
                    "chapter_number": 1,
                    "chapter_title": "第一章",
                    # 故意缺少 chapter_outline / chapter_summary / scene_directions / chapter_goals
                },
                contract_id="plot_outline.workflow_output",
                schema_name="plot_outline.workflow_output",
            )
            return response.structured_data, response, None

        self.engine._broadcast_status = _fake_broadcast
        self.engine._execute_agent_node = _fake_execute_agent_node

        await self.engine._execute_node(execution, node, db=None)

        node_state = execution.node_states[node.id]
        assert node_state.status == NodeStatus.FAILED
        assert node_state.output_data == {}
        assert node_state.output_contract_id is None
        assert node_state.error is not None
        assert "plot_outline.workflow_output" in node_state.error
        assert "缺少字段" in node_state.error
        assert "chapter_outline" in node_state.error
        assert "chapter_summary" in node_state.error
        assert "scene_directions" in node_state.error
        assert "chapter_goals" in node_state.error


class TestDiscussionAssets:
    """讨论资产归一化、确认边界与持久化测试。"""

    def setup_method(self):
        self.engine = WorkflowEngine()

    def test_build_discussion_asset_bundle_classifies_regions_and_lore(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            context={"chapter_title": "第一章"},
            node_states={},
        )
        discussion_result = {
            "summary": "众人决定让旧码头成为后续追踪线索的关键地点。",
            "topic": "码头追踪线",
            "hooks": [{"title": "潮汐钟失准", "description": "钟声会暴露隐藏入口"}],
            "map_candidates": [
                {
                    "name": "旧码头",
                    "description": "被废弃的港口区域",
                    "terrain_features": ["雾", "潮汐栈桥"],
                    "connections": ["下城区"],
                },
                {
                    "name": "潮汐禁忌",
                    "history": "旧码头居民相信午夜潮声不可回应。",
                    "category": "culture",
                },
                {
                    "name": "沉钟灯塔",
                    "description": "灯塔本体可进入，内部保存失落钟声的传说。",
                    "landmarks": ["裂钟"],
                    "history": "曾是守夜人的誓约之地。",
                },
            ],
            "character_candidates": [{"name": "洛澜", "importance_tier": "major_ally", "description": "码头引路人"}],
            "state_changes": [
                {
                    "entity_type": "region",
                    "entity_id": "region-1",
                    "change_type": "region_destroyed",
                    "title": "旧码头被毁",
                    "summary": "旧码头在潮汐门崩塌后沉入海底",
                    "after_state": {"state": "destroyed"},
                }
            ],
        }

        bundle = self.engine._build_discussion_asset_bundle(
            execution,
            discussion_result,
            node_id="discussion",
            discussion_mode="meeting",
        )

        assert bundle["source_metadata"]["topic"] == "码头追踪线"
        assert bundle["persistence_preview"]["plot_update_count"] == 1
        assert bundle["persistence_preview"]["hook_count"] == 1
        assert [r["name"] for r in bundle["region_candidates"]] == ["旧码头", "沉钟灯塔"]
        lore_titles = [l["title"] for l in bundle["lore_candidates"]]
        assert "潮汐禁忌" in lore_titles
        assert "沉钟灯塔" in lore_titles
        dual_lore = next(l for l in bundle["lore_candidates"] if l["title"] == "沉钟灯塔")
        assert dual_lore["metadata"]["dual_write_region_name"] == "沉钟灯塔"
        assert bundle["persistence_preview"]["region_count"] == 2
        assert bundle["persistence_preview"]["lore_count"] == 2
        assert bundle["persistence_preview"]["state_change_count"] == 1
        assert bundle["persistence_preview"]["state_change_titles"] == ["旧码头被毁"]

    def test_extract_discussion_assets_from_fenced_json_text(self):
        discussion_result = {
            "summary": """
本次讨论决定强化旧码头线索。

```json
{
  "discussion_assets": {
    "plot_updates": [{"title": "旧码头追踪", "summary": "主角将追查潮汐门"}],
    "hooks": [{"title": "潮汐钟失准", "description": "钟声会暴露隐藏入口", "related_locations": ["旧码头"]}],
    "lore_candidates": [{"title": "潮汐禁忌", "content": "午夜潮声不可回应", "category": "culture"}],
    "region_candidates": [{"name": "旧码头", "description": "废弃港口", "landmarks": ["潮汐钟"]}],
    "character_candidates": [{"name": "洛澜", "importance_tier": "major_ally", "description": "码头引路人", "appearance": "灰蓝斗篷"}],
    "state_changes": [{
      "entity_type": "character",
      "entity_id": "char-1",
      "change_type": "death",
      "title": "林砚牺牲",
      "summary": "林砚为关闭潮汐门而死亡",
      "after_state": {"status": "dead"}
    }]
  }
}
```

请确认是否同意。
""",
            "messages": [],
        }

        extracted = self.engine._extract_discussion_assets_from_text(discussion_result)

        assert extracted["plot_updates"][0]["title"] == "旧码头追踪"
        assert extracted["hooks"][0]["title"] == "潮汐钟失准"
        assert extracted["lore_candidates"][0]["title"] == "潮汐禁忌"
        assert extracted["region_candidates"][0]["name"] == "旧码头"
        assert extracted["character_candidates"][0]["name"] == "洛澜"
        assert extracted["state_changes"][0]["title"] == "林砚牺牲"
        assert extracted["state_changes"][0]["change_type"] == "death"

    def test_apply_discussion_asset_bundle_keeps_legacy_context_fields(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            context={"chapter_title": "第一章"},
            node_states={},
        )
        discussion_result = {"summary": "确认新角色会在下一章登场", "topic": "角色登场"}
        bundle = self.engine._build_discussion_asset_bundle(execution, discussion_result, "discussion", "meeting")

        digest = self.engine._apply_discussion_asset_bundle(execution, discussion_result, bundle, "meeting")

        assert execution.context["discussion_assets"] == bundle
        assert execution.context["discussion_asset_digest"] == digest
        assert execution.context["discussion_assets_committed"] is False
        assert execution.context["discussion_summary"] == "确认新角色会在下一章登场"
        assert execution.context["last_discussion_summary"] == "确认新角色会在下一章登场"
        assert execution.context["group_discussion"]["discussion_assets"] == bundle
        assert discussion_result["discussion_asset_digest"] == digest

    @pytest.mark.asyncio
    async def test_execute_group_discussion_waits_for_confirmation_before_persistence(self):
        node = WorkflowNode(
            id="discussion",
            node_type=NodeType.GROUP_DISCUSSION,
            label="讨论",
            config={"require_user_confirmation": True, "confirmation_timeout": 999},
            position={"x": 0, "y": 0},
        )
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={},
        )
        db = _FakeDiscussionDB()

        async def _fake_discussion(*args, **kwargs):
            return {
                "status": "completed",
                "summary": "确认旧码头伏笔",
                "hooks": [{"title": "旧码头钥匙", "description": "钥匙会打开潮汐门"}],
            }

        async def _fake_broadcast(*args, **kwargs):
            return None

        self.engine._execute_meeting_discussion = _fake_discussion
        self.engine._broadcast_status = _fake_broadcast

        result = await self.engine._execute_group_discussion_node(node, execution, db=db)

        assert result["waiting_user_confirmation"] is True
        assert execution.status == WorkflowStatus.PAUSED
        assert execution.context["discussion_assets_committed"] is False
        assert execution.context["waiting_confirmation"]["discussion_assets"]["hooks"][0]["title"] == "旧码头钥匙"
        assert db.hooks == []
        assert db.lores == []
        assert db.regions == []
        assert db.characters == []

    @pytest.mark.asyncio
    async def test_persist_discussion_assets_saves_confirmed_assets_and_context_refs(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={"world_id": "22222222-2222-2222-2222-222222222222", "chapter_title": "第一章"},
            node_states={},
        )
        db = _FakeDiscussionDB()

        async def _fake_broadcast(*args, **kwargs):
            return None

        self.engine._broadcast_status = _fake_broadcast
        bundle = {
            "plot_updates": [{"summary": "新增码头追踪线"}],
            "hooks": [{"title": "旧码头钥匙", "description": "钥匙会打开潮汐门", "related_locations": ["旧码头"]}],
            "lore_candidates": [{"title": "潮汐禁忌", "content": "午夜潮声不可回应", "category": "culture"}],
            "region_candidates": [{"name": "旧码头", "description": "废弃港口", "terrain_features": ["浓雾"]}],
            "character_candidates": [
                {
                    "name": "洛澜",
                    "importance_tier": "major_ally",
                    "description": "熟悉旧码头的引路人",
                    "current_location": "旧码头",
                    "current_region_id": "region-1",
                    "arrival_reason": "受主角委托提前探查潮汐门",
                    "goals": ["帮助主角进入旧码头"],
                },
                {"name": "一个神秘商人", "description": "只被短暂提及"},
            ],
            "state_changes": [
                {
                    "entity_type": "character",
                    "entity_id": "char-death",
                    "entity_name": "林砚",
                    "change_type": "death",
                    "title": "林砚牺牲",
                    "summary": "林砚为关闭潮汐门而死亡",
                    "reason": "以自身灵力封闭潮汐门",
                    "after_state": {"status": "dead"},
                }
            ],
            "source_metadata": {"node_id": "discussion"},
        }
        db.existing_characters["char-death"] = {
            "id": "char-death",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "林砚",
            "status": "active",
            "description": "观测员",
        }

        state = await self.engine._persist_discussion_assets(execution, bundle, db=db, confirmation_mode="user_confirm")

        assert state["committed"] is True
        assert state["confirmation_mode"] == "user_confirm"
        assert len(db.hooks) == 1
        assert db.hooks[0]["related_locations"] == ["旧码头"]
        assert len(db.lores) == 1
        assert db.lores[0]["title"] == "潮汐禁忌"
        assert len(db.regions) == 1
        assert db.regions[0]["name"] == "旧码头"
        assert db.regions[0]["world_id"] == "22222222-2222-2222-2222-222222222222"
        assert len(db.characters) == 2
        assert db.characters[0]["name"] == "洛澜"
        assert db.characters[0]["role"] == "supporting"
        assert db.characters[0]["current_location"] == "旧码头"
        assert db.characters[0]["current_region_id"] == "region-1"
        assert db.characters[0]["current_location_reason"] == "受主角委托提前探查潮汐门"
        assert db.characters[0]["personality_traits"] == []
        assert db.existing_characters["char-death"]["status"] == "dead"
        assert db.existing_characters["char-death"]["death_detail"]["cause"] == "以自身灵力封闭潮汐门"
        assert state["characters"]["skipped"] == [{"name": "一个神秘商人", "reason": "角色信息不够明确，暂不提前落库"}]
        assert state["state_changes"]["created"][0]["title"] == "林砚牺牲"
        assert state["state_changes"]["applied"][0]["projection"]["projection"] == "character"
        assert execution.context["discussion_assets_committed"] is True
        assert execution.context["discussion_persistence_state"] == state
        assert execution.context["discussion_created_characters"] == state["characters"]["created"]
        assert execution.context["discussion_state_changes"] == state["state_changes"]["created"]
        assert execution.context["discussion_applied_state_changes"] == state["state_changes"]["applied"]
        assert state["persisted_asset_refs"]["hooks"]
        assert state["persisted_asset_refs"]["lores"]
        assert state["persisted_asset_refs"]["regions"]
        assert state["persisted_asset_refs"]["characters"]
        assert state["persisted_asset_refs"]["state_changes"] == ["state-change-1"]
        assert state["persisted_asset_refs"]["applied_state_changes"] == ["state-change-1"]

    @pytest.mark.asyncio
    async def test_persist_discussion_character_location_updates_existing_character_by_id(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={},
            node_states={},
        )
        db = _FakeDiscussionDB()
        db.existing_characters["char-1"] = {
            "id": "char-1",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "林砚",
            "world_id": "world-1",
            "current_location": "旧地点",
            "current_region_id": "region-old",
            "current_location_reason": "旧原因",
            "description": "观测员",
        }
        db.regions_by_id["region-1"] = {"id": "region-1", "world_id": "world-1", "name": "雾港观测塔"}

        state = await self.engine._persist_discussion_assets(
            execution,
            {
                "character_location_updates": [
                    {
                        "character_id": "char-1",
                        "current_region_id": "region-1",
                        "arrival_reason": "追查裂钟钥匙线索而返回观测塔",
                    }
                ],
            },
            db=db,
            confirmation_mode="user_confirm",
        )

        assert state["character_location_updates"]["updated"] == [
            {
                "id": "char-1",
                "name": "林砚",
                "current_region_id": "region-1",
                "current_location": "雾港观测塔",
                "current_location_reason": "追查裂钟钥匙线索而返回观测塔",
            }
        ]
        saved = db.existing_characters["char-1"]
        assert saved["description"] == "观测员"
        assert saved["current_region_id"] == "region-1"
        assert saved["current_location"] == "雾港观测塔"
        assert saved["current_location_reason"] == "追查裂钟钥匙线索而返回观测塔"
        assert execution.context["discussion_character_location_updates"] == state["character_location_updates"]["updated"]
        assert state["persisted_asset_refs"]["character_location_updates"] == ["char-1"]

    @pytest.mark.asyncio
    async def test_persist_discussion_character_location_updates_matches_by_name_and_infers_world(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={},
            node_states={},
        )
        db = _FakeDiscussionDB()
        db.existing_characters["char-2"] = {
            "id": "char-2",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "洛澜",
            "world_id": None,
            "current_location": None,
            "current_region_id": None,
            "current_location_reason": "",
        }
        db.regions_by_id["region-2"] = {"id": "region-2", "world_id": "world-2", "name": "旧码头"}

        state = await self.engine._persist_discussion_assets(
            execution,
            {
                "character_location_updates": [
                    {
                        "character_name": "洛澜",
                        "region_id": "region-2",
                        "movement_reason": "躲避追兵进入旧码头",
                    }
                ],
            },
            db=db,
            confirmation_mode="user_confirm",
        )

        saved = db.existing_characters["char-2"]
        assert state["character_location_updates"]["updated"][0]["id"] == "char-2"
        assert saved["world_id"] == "world-2"
        assert saved["current_region_id"] == "region-2"
        assert saved["current_location"] == "旧码头"
        assert saved["current_location_reason"] == "躲避追兵进入旧码头"

    @pytest.mark.asyncio
    async def test_persist_discussion_character_location_updates_skips_cross_world_region(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={},
            node_states={},
        )
        db = _FakeDiscussionDB()
        db.existing_characters["char-3"] = {
            "id": "char-3",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "跨界角色",
            "world_id": "world-1",
            "current_region_id": "region-old",
        }
        db.regions_by_id["region-3"] = {"id": "region-3", "world_id": "world-2", "name": "北境森林"}

        state = await self.engine._persist_discussion_assets(
            execution,
            {
                "character_location_updates": [
                    {
                        "character_id": "char-3",
                        "current_region_id": "region-3",
                        "current_location_reason": "错误跨世界移动",
                    }
                ],
            },
            db=db,
            confirmation_mode="user_confirm",
        )

        assert state["character_location_updates"]["updated"] == []
        assert state["character_location_updates"]["skipped"] == [
            {"id": "char-3", "name": "跨界角色", "reason": "角色所属世界与当前所在区域不一致"}
        ]
        assert db.existing_characters["char-3"]["current_region_id"] == "region-old"

    @pytest.mark.asyncio
    async def test_confirm_discussion_persists_assets_before_resuming(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={
                "waiting_confirmation": {
                    "discussion_assets": {"plot_updates": [{"summary": "用户确认后再提交"}]},
                    "auto_confirmed": True,
                    "confirmation_mode": "timeout_auto_confirm",
                },
                "group_discussion": {"leader_type": "master_plotter"},
            },
            node_states={},
        )
        self.engine._executions[execution.id] = execution

        async def _fake_broadcast(*args, **kwargs):
            return None

        async def _fake_get_agent(*args, **kwargs):
            return None

        async def _fake_get_workflow(*args, **kwargs):
            return None

        persisted = {}

        async def _fake_persist(execution, bundle, db=None, confirmation_mode="user_confirm"):
            persisted["bundle"] = bundle
            persisted["confirmation_mode"] = confirmation_mode
            state = {"committed": True, "persisted_asset_refs": {"hooks": [], "lores": [], "regions": [], "characters": []}}
            execution.context["discussion_persistence_state"] = state
            execution.context["persisted_asset_refs"] = state["persisted_asset_refs"]
            return state

        self.engine._broadcast_status = _fake_broadcast
        self.engine._get_agent_for_discussion = _fake_get_agent
        self.engine.get_workflow = _fake_get_workflow
        self.engine._persist_discussion_assets = _fake_persist

        result = await self.engine.confirm_discussion(execution.id, approved=True)

        assert result["success"] is True
        assert result["confirmation_mode"] == "timeout_auto_confirm"
        assert persisted["bundle"] == {"plot_updates": [{"summary": "用户确认后再提交"}]}
        assert persisted["confirmation_mode"] == "timeout_auto_confirm"
        assert "waiting_confirmation" not in execution.context
        assert execution.status == WorkflowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_confirm_discussion_persists_character_location_updates_before_resuming(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={
                "waiting_confirmation": {
                    "discussion_assets": {
                        "character_location_updates": [
                            {
                                "character_id": "char-confirm",
                                "current_region_id": "region-confirm",
                                "reason_for_arrival": "确认讨论后前往钟楼守夜",
                            }
                        ]
                    },
                },
                "group_discussion": {"leader_type": "master_plotter"},
            },
            node_states={},
        )
        self.engine._executions[execution.id] = execution
        db = _FakeDiscussionDB()
        db.existing_characters["char-confirm"] = {
            "id": "char-confirm",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "守夜人",
            "world_id": "world-confirm",
            "current_location": "旧钟楼外",
            "current_region_id": "region-old",
        }
        db.regions_by_id["region-confirm"] = {
            "id": "region-confirm",
            "world_id": "world-confirm",
            "name": "裂钟楼",
        }

        async def _fake_broadcast(*args, **kwargs):
            return None

        async def _fake_get_agent(*args, **kwargs):
            return None

        async def _fake_get_workflow(*args, **kwargs):
            return None

        async def _fake_save_execution(*args, **kwargs):
            return None

        self.engine._broadcast_status = _fake_broadcast
        self.engine._get_agent_for_discussion = _fake_get_agent
        self.engine.get_workflow = _fake_get_workflow
        self.engine._save_execution_to_db = _fake_save_execution

        result = await self.engine.confirm_discussion(execution.id, approved=True, db=db)

        assert result["success"] is True
        assert result["confirmation_mode"] == "user_confirm"
        assert "waiting_confirmation" not in execution.context
        assert execution.status == WorkflowStatus.RUNNING
        saved = db.existing_characters["char-confirm"]
        assert saved["current_region_id"] == "region-confirm"
        assert saved["current_location"] == "裂钟楼"
        assert saved["current_location_reason"] == "确认讨论后前往钟楼守夜"
        persistence_state = result["discussion_persistence_state"]
        assert persistence_state["character_location_updates"]["updated"][0]["id"] == "char-confirm"
        assert execution.context["persisted_asset_refs"]["character_location_updates"] == ["char-confirm"]

    @pytest.mark.asyncio
    async def test_confirm_discussion_persists_state_changes_before_resuming(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={
                "waiting_confirmation": {
                    "discussion_assets": {
                        "state_changes": [
                            {
                                "entity_type": "character",
                                "entity_id": "char-confirm-death",
                                "entity_name": "林砚",
                                "change_type": "death",
                                "title": "林砚确认牺牲",
                                "summary": "确认讨论后记录林砚为关闭裂钟门牺牲",
                                "reason": "以自身灵力封闭裂钟门",
                                "after_state": {"status": "dead"},
                            }
                        ]
                    },
                },
                "group_discussion": {"leader_type": "master_plotter"},
            },
            node_states={},
        )
        self.engine._executions[execution.id] = execution
        db = _FakeDiscussionDB()
        db.existing_characters["char-confirm-death"] = {
            "id": "char-confirm-death",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "林砚",
            "status": "active",
            "description": "裂钟门观测员",
        }

        async def _fake_broadcast(*args, **kwargs):
            return None

        async def _fake_get_agent(*args, **kwargs):
            return None

        async def _fake_get_workflow(*args, **kwargs):
            return None

        async def _fake_save_execution(*args, **kwargs):
            return None

        self.engine._broadcast_status = _fake_broadcast
        self.engine._get_agent_for_discussion = _fake_get_agent
        self.engine.get_workflow = _fake_get_workflow
        self.engine._save_execution_to_db = _fake_save_execution

        result = await self.engine.confirm_discussion(execution.id, approved=True, db=db)

        assert result["success"] is True
        assert result["confirmation_mode"] == "user_confirm"
        assert "waiting_confirmation" not in execution.context
        assert execution.status == WorkflowStatus.RUNNING
        saved = db.existing_characters["char-confirm-death"]
        assert saved["status"] == "dead"
        assert saved["death_detail"]["cause"] == "以自身灵力封闭裂钟门"
        persistence_state = result["discussion_persistence_state"]
        assert persistence_state["state_changes"]["created"][0]["title"] == "林砚确认牺牲"
        assert persistence_state["state_changes"]["applied"][0]["projection"]["projection"] == "character"
        assert execution.context["persisted_asset_refs"]["state_changes"] == ["state-change-1"]
        assert execution.context["persisted_asset_refs"]["applied_state_changes"] == ["state-change-1"]

    def test_is_persistable_discussion_character_requires_name_role_and_detail(self):
        assert self.engine._is_persistable_discussion_character({
            "name": "洛澜",
            "importance_tier": "major_ally",
            "description": "码头引路人",
        }) is True
        assert self.engine._is_persistable_discussion_character({
            "name": "一个神秘商人",
            "description": "只被短暂提及",
        }) is False
        assert self.engine._is_persistable_discussion_character({
            "name": "洛澜",
            "description": "缺少叙事定位",
        }) is False

