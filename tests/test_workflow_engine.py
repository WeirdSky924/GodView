import asyncio
import json
from datetime import datetime, timedelta

import pytest

from app.models.workflow_definition import (
    NodeType,
    NodeStatus,
    WorkflowNode,
    WorkflowEdge,
    WorkflowDefinition,
    WorkflowDefinitionCreate,
)
from app.models.workflow_execution import WorkflowStatus, NodeExecutionState, WorkflowExecution
from app.services.chapter_document_storage import ChapterDocumentStorage
from app.services.workflow_engine import WorkflowEngine, WorkflowOperationError
from app.services.workflow_replay_export_service import WorkflowReplayExportService

from tests.workflow_test_fakes import FakeAgentResponse, FakeDiscussionDB


def test_workflow_resource_requirements_dedupe_same_resource_across_reasons():
    engine = WorkflowEngine()
    execution = WorkflowExecution(
        id="exec-1",
        workflow_id="workflow-1",
        project_id="project-1",
    )
    execution.context.update({"chapter_num": 2, "chapter_outline_id": "outline-1"})
    node = WorkflowNode(id="master", node_type=NodeType.AGENT, agent_type="master_plotter", label="Master")

    updates = engine._normalize_workflow_resource_requirements(
        {
            "resource_requirements": [
                {"requirement_type": "continuity", "resource_name": "连续性·林默", "severity": "blocking", "reason": "原因 A"},
                {"requirement_type": "continuity", "resource_name": "连续性·林默", "severity": "advisory", "reason": "原因 B"},
            ]
        },
        execution,
        node,
    )

    requirements = updates["pending_resource_requirements"]
    assert len(requirements) == 1
    assert requirements[0]["resource_name"] == "连续性·林默"
    assert "原因 A" in requirements[0]["reason"]
    assert "原因 B" in requirements[0]["reason"]


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


@pytest.mark.asyncio
async def test_load_agent_context_attaches_confirmed_prior_state_packet(monkeypatch):
    engine = WorkflowEngine()
    db = FakeDiscussionDB()
    project_id = "00000000-0000-0000-0000-000000000001"
    db.chapters.extend([
        {"id": "chapter-1", "project_id": project_id, "status": "saved", "chapter_number": 1, "title": "第一章", "content_checksum": "aaa"},
        {"id": "chapter-2", "project_id": project_id, "status": "saved", "chapter_number": 2, "title": "第二章", "content_checksum": "bbb"},
        {"id": "chapter-completed", "project_id": project_id, "status": "completed", "chapter_number": 2, "title": "旧完成态"},
        {"id": "chapter-3", "project_id": project_id, "status": "saved", "chapter_number": 3, "title": "第三章", "content_checksum": "ccc"},
        {"id": "draft-2", "project_id": project_id, "status": "draft", "chapter_number": 2, "title": "草稿"},
    ])
    db.state_changes["state-applied"] = {
        "id": "state-applied",
        "project_id": project_id,
        "status": "applied",
        "entity_type": "character",
        "entity_id": "char-linyan",
        "entity_name": "林砚",
        "change_type": "status_change",
        "summary": "林砚已受伤",
        "chapter_id": "chapter-1",
        "after_state": {"status": "injured"},
        "created_at": "2026-05-10T01:00:00",
        "applied_at": "2026-05-10T01:05:00",
    }
    db.state_changes["state-applied-latest"] = {
        "id": "state-applied-latest",
        "project_id": project_id,
        "status": "applied",
        "entity_type": "character",
        "entity_id": "char-linyan",
        "entity_name": "林砚",
        "change_type": "location_change",
        "summary": "林砚已抵达潮汐门",
        "chapter_id": "chapter-2",
        "after_state": {"status": "injured", "location": "潮汐门"},
        "created_at": "2026-05-10T02:00:00",
        "applied_at": "2026-05-10T02:05:00",
    }
    db.state_changes["state-confirmed"] = {
        "id": "state-confirmed",
        "project_id": project_id,
        "status": "confirmed",
        "entity_type": "plot",
        "entity_id": "plot-tide-key",
        "entity_name": "潮汐门钥匙",
        "change_type": "custom",
        "summary": "林砚已获得潮汐门钥匙",
        "chapter_id": "chapter-2",
        "after_state": {"has_key": True},
        "created_at": "2026-05-10T03:00:00",
        "confirmed_at": "2026-05-10T03:05:00",
    }
    db.state_changes["state-proposed"] = {
        "id": "state-proposed",
        "project_id": project_id,
        "status": "proposed",
        "entity_type": "plot",
        "change_type": "custom",
        "summary": "潮汐门可能通向旧案",
    }
    db.state_changes["state-rejected"] = {
        "id": "state-rejected",
        "project_id": project_id,
        "status": "rejected",
        "entity_type": "world",
        "change_type": "world_state_change",
        "summary": "废弃设定不应进入状态包",
    }
    execution = WorkflowExecution(
        workflow_id="wf-context-packet",
        project_id=project_id,
        status=WorkflowStatus.RUNNING,
        context={"chapter_num": 3, "chapter_title": "第三章"},
        node_states={},
    )
    events = []

    async def capture_broadcast(execution_id, event_type, payload):
        events.append((execution_id, event_type, payload))

    monkeypatch.setattr(engine, "_broadcast_status", capture_broadcast)

    context = await engine._load_agent_context("writer", execution, db)

    packet = context["confirmed_prior_state_packet"]
    assert [chapter["chapter_id"] for chapter in packet["prior_chapters"]] == ["chapter-1", "chapter-2"]
    confirmed_ids = [change["id"] for change in packet["confirmed_state_changes"]]
    assert confirmed_ids == ["state-confirmed", "state-applied-latest", "state-applied"]
    assert packet["confirmed_state_changes"][1]["entity_key"] == "character:char-linyan"
    assert packet["confirmed_state_changes"][1]["after_state"] == {"status": "injured", "location": "潮汐门"}
    state_summary = {item["entity_key"]: item for item in packet["confirmed_state_summary"]}
    assert state_summary["character:char-linyan"]["latest_change_id"] == "state-applied-latest"
    assert state_summary["character:char-linyan"]["change_count"] == 2
    assert state_summary["character:char-linyan"]["latest_after_state"] == {"status": "injured", "location": "潮汐门"}
    assert state_summary["plot:plot-tide-key"]["latest_change_id"] == "state-confirmed"
    assert packet["source"]["confirmed_state_total"] == 3
    assert packet["source"]["confirmed_entity_count"] == 2
    assert packet["open_proposed_changes"][0]["id"] == "state-proposed"
    serialized_packet = json.dumps(packet, ensure_ascii=False)
    assert "state-rejected" not in serialized_packet
    assert "废弃设定" not in serialized_packet
    assert "chapter-3" not in [chapter["chapter_id"] for chapter in packet["prior_chapters"]]
    assert "draft-2" not in [chapter["chapter_id"] for chapter in packet["prior_chapters"]]
    assert "chapter-completed" not in [chapter["chapter_id"] for chapter in packet["prior_chapters"]]
    assert execution.context["confirmed_prior_state_packet"] == packet
    assert execution.context["confirmed_prior_state_packet_provenance"]["confirmed_state_count"] == 3
    assert execution.context["confirmed_prior_state_packet_provenance"]["open_proposed_count"] == 1
    assert events[-1][1] == "chapter_state_handoff_loaded"
    assert events[-1][2]["confirmed_state_count"] == 3
    assert events[-1][2]["pending_count"] == 1


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

    def _remediation_workflow(self, failed_node_type=NodeType.AGENT):
        failed_node = WorkflowNode(
            id="plotter_failure",
            node_type=failed_node_type,
            agent_type="smoke_contract_failure" if failed_node_type == NodeType.AGENT else None,
            label="失败编剧",
            config={"scenario": "broken"},
            position={"x": 0, "y": 100},
        )
        return WorkflowDefinition(
            id="wf-remediation-fixture",
            project_id="test-project",
            name="修复夹具",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                failed_node,
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 200}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="plotter_failure"),
                WorkflowEdge(id="e2", source="plotter_failure", target="end"),
            ],
        )

    def _failed_remediation_execution(self, workflow_id="wf-remediation-fixture"):
        return WorkflowExecution(
            id="exec-remediation-fixture",
            workflow_id=workflow_id,
            project_id="test-project",
            status=WorkflowStatus.FAILED,
            current_node="plotter_failure",
            error="无法获取 Agent: smoke_contract_failure",
            node_states={
                "start": NodeExecutionState(node_id="start", status=NodeStatus.COMPLETED, output_data={"status": "started"}),
                "plotter_failure": NodeExecutionState(
                    node_id="plotter_failure",
                    status=NodeStatus.FAILED,
                    error="无法获取 Agent: smoke_contract_failure",
                    retry_count=2,
                    output_data={"bad": True},
                ),
                "end": NodeExecutionState(node_id="end", status=NodeStatus.COMPLETED, output_data={"status": "completed"}),
            },
            context={"node_outputs": {"start": {"status": "started"}, "plotter_failure": {"bad": True}, "end": {"status": "completed"}}},
            trace_id="trace-remediation-fixture",
        )

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
    async def test_writer_effective_input_and_saved_provenance_are_recorded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.services.chapter_document_storage.chapter_document_storage",
            ChapterDocumentStorage(str(tmp_path)),
        )
        node = WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="写作")
        execution = WorkflowExecution(
            id="exec-writer-provenance",
            workflow_id="wf-writer-provenance",
            project_id="00000000-0000-0000-0000-000000000001",
            status=WorkflowStatus.RUNNING,
            trace_id="trace-writer-provenance",
            node_states={"writer": NodeExecutionState(node_id="writer", status=NodeStatus.RUNNING)},
            context={
                "chapter_num": 9,
                "chapter_title": "第九章：实链",
                "chapter_outline_id": "outline-writer-provenance",
                "chapter_outline": {"id": "outline-writer-provenance", "target_word_count": 1200},
                "target_word_count": 1200,
                "characters": [{"name": "林岚"}],
                "lore_entries": [{"title": "潮汐城"}],
                "existing_hooks": [{"title": "铜铃"}],
                "workflow_state": {"canonical_state": {"chapter_num": 9}},
                "graph_context_summary": "核心人物关系已加载",
            },
        )
        db = FakeDiscussionDB()

        async def fake_save_workflow_execution(data):
            return data.get("id")

        db.save_workflow_execution = fake_save_workflow_execution
        broadcasts = []

        class FakeWriterAgent:
            name = "fake-writer"
            model = object()
            _stream_callback = None

            async def execute(self, context):
                assert context["target_word_count"] == 1200
                assert context["chapter_outline"]["id"] == "outline-writer-provenance"
                return FakeAgentResponse(
                    {
                        "chapter_content": "真实链路正文",
                        "word_count": 6,
                        "metadata": {},
                        "style_check": {"passed": True},
                        "hooks_embedded": [],
                        "future_setup": [],
                    },
                    contract_id="writer.workflow_output",
                    schema_name="writer.workflow_output",
                    metadata={
                        "prompt_render_trace": {
                            "template_id": "writer-template",
                            "prompt_ids": ["function_writing"],
                            "skill_ids": ["scene_pacing"],
                            "writing_rule_ids": ["long_novel_core"],
                            "prompt": "must not be persisted",
                        }
                    },
                )

        async def capture_broadcast(execution_id, event_type, payload):
            broadcasts.append((execution_id, event_type, payload))

        monkeypatch.setattr(self.engine, "_broadcast_status", capture_broadcast)
        output, response, contract = await self.engine._run_agent_execution(FakeWriterAgent(), dict(execution.context), execution, node, db)
        output, contract = self.engine._apply_node_output_contract(node, output, response=response)
        output = self.engine._attach_prompt_render_trace_metadata(
            output,
            response.metadata.get("prompt_render_trace"),
            response.metadata.get("config_prompt_source", "agent_template_runtime"),
        )

        assert output["chapter_content"] == "真实链路正文"
        input_data = execution.node_states["writer"].input_data
        assert input_data["target_word_count"] == 1200
        assert input_data["chapter_outline"]["id"] == "outline-writer-provenance"
        assert input_data["_effective_agent_input"]["resolved_agent_type"] == "writer"
        assert input_data["_effective_agent_input"]["required_context_present"]["chapter_outline"] is True
        assert input_data["_effective_agent_input"]["required_context_present"]["graph_context"] is True
        saved_payload = broadcasts[-1][2]
        assert broadcasts[-1][1] == "chapter_saved"
        assert saved_payload["source_node_id"] == "writer"
        assert saved_payload["resolved_agent_type"] == "writer"
        assert saved_payload["source_output_contract_id"] == "writer.workflow_output"
        assert saved_payload["source_output_schema_name"] == "writer.workflow_output"
        assert saved_payload["source_trace_id"] == "trace-writer-provenance"
        assert saved_payload["writer_prompt_trace"]["prompt_ids"] == ["function_writing"]
        assert "prompt" not in saved_payload["writer_prompt_trace"]
        assert "content" not in saved_payload
        assert db.chapters[0]["content"] == ""
        assert (tmp_path / db.chapters[0]["content_path"]).read_text(encoding="utf-8") == "真实链路正文"

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
        self.engine._workflows["test-wf"] = WorkflowDefinition(
            id="test-wf",
            project_id="test-project",
            name="测试工作流",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 100}),
            ],
            edges=[WorkflowEdge(id="e1", source="start", target="end")],
        )

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
    async def test_pause_rejects_non_running_execution_with_structured_error(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.COMPLETED,
            node_states={},
        )
        self.engine._executions[execution.id] = execution

        with pytest.raises(WorkflowOperationError) as exc_info:
            await self.engine.pause_workflow(execution.id)

        assert exc_info.value.code == "workflow_operation_conflict"
        assert exc_info.value.status == "completed"
        assert exc_info.value.operation == "pause"
        assert exc_info.value.to_payload()["allowed_statuses"] == ["running"]

    @pytest.mark.asyncio
    async def test_resume_rejects_paused_execution_with_active_task(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.PAUSED,
            node_states={},
        )
        self.engine._executions[execution.id] = execution
        task = asyncio.create_task(asyncio.sleep(60))
        self.engine._running_tasks[execution.id] = task

        try:
            with pytest.raises(WorkflowOperationError) as exc_info:
                await self.engine.resume_workflow(execution.id)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert exc_info.value.code == "workflow_execution_active_task_conflict"
        assert exc_info.value.status == "paused"
        assert execution.status == WorkflowStatus.PAUSED

    @pytest.mark.asyncio
    async def test_expired_running_execution_without_task_is_marked_failed_on_inspect(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={
                "writer": NodeExecutionState(node_id="writer", status=NodeStatus.RUNNING),
            },
            lease_expires_at=datetime.now() - timedelta(seconds=5),
            last_heartbeat_at=datetime.now() - timedelta(seconds=65),
        )
        self.engine._executions[execution.id] = execution

        result = await self.engine.get_execution_state(execution.id)

        assert result is execution
        assert execution.status == WorkflowStatus.FAILED
        assert "租约已过期" in execution.error
        assert execution.context["stale_execution_history"][0]["operation"] == "inspect"
        assert execution.resume_cursor["stale_operation"] == "inspect"

    def test_retry_branch_exit_does_not_block_initial_writer_path(self):
        workflow = WorkflowDefinition(
            id="wf-retry-branch",
            project_id="test-project",
            name="retry branch",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={}),
                WorkflowNode(id="master_scene_compiler", node_type=NodeType.AGENT, agent_type="master_plotter", label="Master", position={}),
                WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="Writer", position={}),
                WorkflowNode(id="evaluator", node_type=NodeType.AGENT, agent_type="evaluator", label="Evaluator", position={}),
                WorkflowNode(id="condition_quality", node_type=NodeType.CONDITION, label="质量门", position={}),
                WorkflowNode(id="master_revision_director", node_type=NodeType.AGENT, agent_type="master_plotter", label="Revision", position={}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="master_scene_compiler"),
                WorkflowEdge(id="e2", source="master_scene_compiler", target="writer"),
                WorkflowEdge(id="e3", source="writer", target="evaluator"),
                WorkflowEdge(id="e4", source="evaluator", target="condition_quality"),
                WorkflowEdge(id="e5", source="condition_quality", target="end", condition={"result": "pass"}),
                WorkflowEdge(id="e6", source="condition_quality", target="master_revision_director", condition={"result": "retry"}),
                WorkflowEdge(id="e7", source="master_revision_director", target="writer"),
            ],
        )
        execution = WorkflowExecution(workflow_id=workflow.id, project_id="test-project")
        for node in workflow.nodes:
            execution.node_states[node.id] = NodeExecutionState(node_id=node.id)
        predecessors = self.engine._build_predecessor_graph(workflow)

        assert predecessors["writer"] == ["master_scene_compiler"]
        assert self.engine._get_ready_nodes(workflow, execution, predecessors, {"start", "master_scene_compiler"}) == ["writer"]

    @pytest.mark.asyncio
    async def test_parallel_failed_node_stops_before_downstream_end(self):
        workflow = WorkflowDefinition(
            id="wf-parallel-failure",
            project_id="test-project",
            name="并行失败测试",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={}),
                WorkflowNode(id="good_agent", node_type=NodeType.AGENT, agent_type="writer", label="成功 Agent", position={}),
                WorkflowNode(id="bad_agent", node_type=NodeType.AGENT, agent_type="master_plotter", label="失败 Agent", position={}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="good_agent"),
                WorkflowEdge(id="e2", source="start", target="bad_agent"),
                WorkflowEdge(id="e3", source="good_agent", target="end"),
                WorkflowEdge(id="e4", source="bad_agent", target="end"),
            ],
        )
        execution = WorkflowExecution(
            id="exec-parallel-failure",
            workflow_id=workflow.id,
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
        )
        for node in workflow.nodes:
            execution.node_states[node.id] = NodeExecutionState(node_id=node.id)
        self.engine._executions[execution.id] = execution

        async def _fake_execute_node_with_merge(execution_arg, node, predecessors, workflow_arg, db=None):
            state = execution_arg.node_states[node.id]
            state.started_at = datetime.now()
            state.completed_at = datetime.now()
            if node.id == "bad_agent":
                state.status = NodeStatus.FAILED
                state.error = "structured contract failed"
                state.output_data = {}
            else:
                state.status = NodeStatus.COMPLETED
                state.output_data = {"node_id": node.id}

        async def _fake_broadcast(*args, **kwargs):
            pass

        async def _fake_mark_terminal(*args, **kwargs):
            pass

        async def _fake_export(*args, **kwargs):
            return None

        self.engine._execute_node_with_merge = _fake_execute_node_with_merge
        self.engine._broadcast_status = _fake_broadcast
        self.engine._mark_operation_terminal = _fake_mark_terminal
        self.engine._export_execution_replay_markdown = _fake_export

        await self.engine._run_workflow(execution.id, workflow)

        assert execution.status == WorkflowStatus.FAILED
        assert execution.error == "structured contract failed"
        assert execution.node_states["bad_agent"].status == NodeStatus.FAILED
        assert execution.node_states["good_agent"].status == NodeStatus.COMPLETED
        assert execution.node_states["end"].status == NodeStatus.PENDING

    @pytest.mark.asyncio
    async def test_failed_predecessor_blocks_linear_downstream_and_end(self):
        workflow = WorkflowDefinition(
            id="wf-linear-failure",
            project_id="test-project",
            name="线性失败阻断测试",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={}),
                WorkflowNode(id="bad_agent", node_type=NodeType.AGENT, agent_type="master_plotter", label="失败 Agent", position={}),
                WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="写作", position={}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="bad_agent"),
                WorkflowEdge(id="e2", source="bad_agent", target="writer"),
                WorkflowEdge(id="e3", source="writer", target="end"),
            ],
        )
        execution = WorkflowExecution(
            id="exec-linear-failure",
            workflow_id=workflow.id,
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
        )
        for node in workflow.nodes:
            execution.node_states[node.id] = NodeExecutionState(node_id=node.id)
        self.engine._executions[execution.id] = execution

        async def _fake_execute_node_with_merge(execution_arg, node, predecessors, workflow_arg, db=None):
            state = execution_arg.node_states[node.id]
            state.started_at = datetime.now()
            state.completed_at = datetime.now()
            if node.id == "bad_agent":
                state.status = NodeStatus.FAILED
                state.error = "provider failed"
            else:
                state.status = NodeStatus.COMPLETED
                state.output_data = {"node_id": node.id}

        async def _fake_broadcast(*args, **kwargs):
            pass

        async def _fake_mark_terminal(*args, **kwargs):
            pass

        async def _fake_export(*args, **kwargs):
            return None

        self.engine._execute_node_with_merge = _fake_execute_node_with_merge
        self.engine._broadcast_status = _fake_broadcast
        self.engine._mark_operation_terminal = _fake_mark_terminal
        self.engine._export_execution_replay_markdown = _fake_export

        await self.engine._run_workflow(execution.id, workflow)

        assert execution.status == WorkflowStatus.FAILED
        assert execution.error == "provider failed"
        assert execution.node_states["bad_agent"].status == NodeStatus.FAILED
        assert execution.node_states["writer"].status == NodeStatus.PENDING
        assert execution.node_states["end"].status == NodeStatus.PENDING

    @pytest.mark.asyncio
    async def test_running_execution_heartbeat_extends_lease_before_node_completes(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            request_id="request-1",
            node_states={"master": NodeExecutionState(node_id="master", status=NodeStatus.RUNNING)},
            lease_expires_at=datetime.now() - timedelta(seconds=5),
            last_heartbeat_at=datetime.now() - timedelta(seconds=65),
        )
        saved = []
        heartbeats = []

        class FakeDB:
            async def get_operation_request_by_request_id(self, request_id):
                return {"request_id": request_id}

        class FakeOperationService:
            async def heartbeat(self, operation):
                heartbeats.append(operation)

        async def fake_save(execution_arg, db=None):
            saved.append((execution_arg.last_heartbeat_at, execution_arg.lease_expires_at))

        self.engine._save_execution_to_db = fake_save
        before = datetime.now()
        await self.engine._heartbeat_running_execution(execution, FakeDB(), FakeOperationService(), 60)

        assert execution.last_heartbeat_at >= before
        assert execution.lease_expires_at > datetime.now() + timedelta(seconds=50)
        assert saved
        assert heartbeats == [{"request_id": "request-1"}]

    def test_inspect_execution_staleness_reports_safe_actions(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={},
            lease_expires_at=datetime.now() - timedelta(seconds=5),
            last_heartbeat_at=datetime.now() - timedelta(seconds=65),
        )

        inspection = self.engine.inspect_execution_staleness(execution)

        assert inspection["suspected_stale"] is True
        assert inspection["active_task"] is False
        assert "mark_failed" in inspection["safe_actions"]
        assert inspection["lease"]["expired"] is True

    @pytest.mark.asyncio
    async def test_resolve_stale_execution_marks_failed_with_audit(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            current_node="writer",
            node_states={"writer": NodeExecutionState(node_id="writer", status=NodeStatus.RUNNING)},
            lease_expires_at=datetime.now() - timedelta(seconds=5),
            last_heartbeat_at=datetime.now() - timedelta(seconds=65),
        )
        self.engine._executions[execution.id] = execution
        broadcasts = []

        async def _fake_broadcast(execution_id, event_type, data):
            broadcasts.append((execution_id, event_type, data))

        self.engine._broadcast_status = _fake_broadcast

        result = await self.engine.resolve_stale_execution(execution.id, action="mark_failed", reason="test stale cleanup")

        assert result["success"] is True
        assert execution.status == WorkflowStatus.FAILED
        assert execution.node_states["writer"].status == NodeStatus.FAILED
        assert execution.context["stale_execution_history"][0]["operation"] == "test stale cleanup"
        assert broadcasts == []

    @pytest.mark.asyncio
    async def test_create_runtime_fixture_requires_debug_mode(self, monkeypatch):
        monkeypatch.setattr("app.services.workflow_engine.settings.debug", False)

        with pytest.raises(WorkflowOperationError) as exc_info:
            await self.engine.create_runtime_fixture("test-project", object(), fixture_type="stale_running")

        assert exc_info.value.code == "workflow_fixture_disabled"

    @pytest.mark.asyncio
    async def test_create_runtime_fixture_builds_isolated_stale_execution(self, monkeypatch):
        monkeypatch.setattr("app.services.workflow_engine.settings.debug", True)
        saved_workflows = []
        saved_executions = []
        events = []

        class FixtureDB:
            async def execute_write(self, query, params):
                return None

            async def save_workflow_execution(self, execution_data):
                saved_executions.append(dict(execution_data))
                return execution_data["id"]

            async def append_workflow_execution_event(self, execution_id, event_type, event_data):
                events.append((execution_id, event_type, event_data))
                return len(events)

        async def fake_save_workflow(workflow, db):
            saved_workflows.append(workflow)

        monkeypatch.setattr(self.engine, "_save_workflow_to_db", fake_save_workflow)

        result = await self.engine.create_runtime_fixture("test-project", FixtureDB(), fixture_type="stale_running")

        assert result["success"] is True
        assert result["fixture_type"] == "stale_running"
        assert result["workflow"]["variables"]["runtime_fixture"] is True
        assert result["execution"]["context"]["runtime_fixture"] is True
        assert result["inspection"]["suspected_stale"] is True
        assert saved_workflows[0].id == result["workflow"]["id"]
        assert saved_executions[0]["id"] == result["execution"]["id"]
        assert events[0][1] == "workflow_runtime_fixture_created"

    @pytest.mark.asyncio
    async def test_create_runtime_fixture_builds_saved_chapter_handoff(self, tmp_path, monkeypatch):
        from app.services.chapter_document_storage import ChapterDocumentStorage

        monkeypatch.setattr("app.services.workflow_engine.settings.debug", True)
        monkeypatch.setattr(
            "app.services.chapter_document_storage.chapter_document_storage",
            ChapterDocumentStorage(str(tmp_path)),
        )
        saved_workflows = []
        saved_executions = []
        saved_chapters = []
        events = []
        broadcast_events = []

        async def capture_broadcast(execution_id, event_type, payload):
            broadcast_events.append((execution_id, event_type, payload))

        monkeypatch.setattr(self.engine, "_broadcast_status", capture_broadcast)

        class FixtureDB:
            async def execute_write(self, query, params):
                return None

            async def execute_query(self, query, params=None):
                return []

            async def save_workflow_execution(self, execution_data):
                saved_executions.append(dict(execution_data))
                return execution_data["id"]

            async def save_chapter(self, chapter_data):
                saved_chapters.append(dict(chapter_data))
                return chapter_data["id"]

            async def append_workflow_execution_event(self, execution_id, event_type, event_data):
                events.append((execution_id, event_type, event_data))
                return len(events)

        async def fake_save_workflow(workflow, db):
            saved_workflows.append(workflow)

        monkeypatch.setattr(self.engine, "_save_workflow_to_db", fake_save_workflow)

        result = await self.engine.create_runtime_fixture("00000000-0000-0000-0000-000000000001", FixtureDB(), fixture_type="saved_chapter", label="director-fixture-session")

        execution = result["execution"]
        assert result["success"] is True
        assert result["fixture_type"] == "saved_chapter"
        assert execution["status"] == "completed"
        assert execution["director_session_id"] == "director-fixture-session"
        assert execution["context"]["chapter_saved"] is True
        assert execution["context"]["chapter_saved_payload"]["runtime_fixture"] is True
        assert saved_chapters[0]["content"] == ""
        assert saved_chapters[0]["content_storage"] == "filesystem"
        assert (tmp_path / saved_chapters[0]["content_path"]).exists()
        assert any(event[1] == "chapter_saved" for event in broadcast_events)
        assert broadcast_events[-1][1] == "workflow_runtime_fixture_created"
        assert len(saved_executions) >= 2
        assert "chapter_id" not in saved_executions[0]["context"]
        assert saved_executions[-1]["context"]["chapter_id"] == saved_chapters[0]["id"]

    @pytest.mark.asyncio
    async def test_create_runtime_fixture_builds_quality_gate_revision_handoff(self, tmp_path, monkeypatch):
        from app.services.chapter_document_storage import ChapterDocumentStorage

        monkeypatch.setattr("app.services.workflow_engine.settings.debug", True)
        monkeypatch.setattr(
            "app.services.chapter_document_storage.chapter_document_storage",
            ChapterDocumentStorage(str(tmp_path)),
        )
        saved_chapters = []
        broadcast_events = []

        async def capture_broadcast(execution_id, event_type, payload):
            broadcast_events.append((event_type, payload))

        monkeypatch.setattr(self.engine, "_broadcast_status", capture_broadcast)

        class FixtureDB:
            async def execute_write(self, query, params):
                return None

            async def execute_query(self, query, params=None):
                return []

            async def save_workflow_execution(self, execution_data):
                return execution_data["id"]

            async def save_chapter(self, chapter_data):
                saved_chapters.append(dict(chapter_data))
                return chapter_data["id"]

            async def append_workflow_execution_event(self, execution_id, event_type, event_data):
                return 1

        async def fake_save_workflow(workflow, db):
            return None

        monkeypatch.setattr(self.engine, "_save_workflow_to_db", fake_save_workflow)

        result = await self.engine.create_runtime_fixture(
            "00000000-0000-0000-0000-000000000001",
            FixtureDB(),
            fixture_type="quality_gate_revision",
            label="quality-gate-fixture-session",
        )

        execution = result["execution"]
        assert result["fixture_type"] == "quality_gate_revision"
        assert execution["status"] == "completed"
        assert execution["context"]["chapter_saved"] is True
        assert execution["context"]["pending_chapter_save"] is False
        assert execution["context"]["chapter_draft_attempt"] == 2
        assert execution["context"]["quality_gate_status"] == "passed"
        assert len(execution["context"]["quality_gate_history"]) == 2
        assert len(execution["context"]["revision_history"]) == 1
        assert execution["context"]["writer_retry_contexts"][0]["is_retry"] is True
        assert execution["context"]["writer_retry_contexts"][0]["agent_scenario"] == "rewrite_by_review"
        assert execution["context"]["chapter_saved_payload"]["quality_gate_passed"] is True
        assert execution["context"]["chapter_saved_payload"]["quality_gate_attempts"] == 2
        assert len(saved_chapters) == 1
        assert (tmp_path / saved_chapters[0]["content_path"]).read_text(encoding="utf-8").startswith("质量门夹具第二版正文")
        event_types = [event for event, _ in broadcast_events]
        assert event_types.count("chapter_draft_ready") == 2
        assert "quality_gate_failed" in event_types
        assert "chapter_revision_requested" in event_types
        assert "quality_gate_passed" in event_types
        assert "chapter_finalized" in event_types
        assert event_types.count("chapter_saved") == 1

    @pytest.mark.asyncio
    async def test_create_runtime_fixture_builds_state_handoff_context_packet(self, tmp_path, monkeypatch):
        from app.services.chapter_document_storage import ChapterDocumentStorage

        monkeypatch.setattr("app.services.workflow_engine.settings.debug", True)
        monkeypatch.setattr(
            "app.services.chapter_document_storage.chapter_document_storage",
            ChapterDocumentStorage(str(tmp_path)),
        )
        db = FakeDiscussionDB()
        broadcast_events = []
        saved_executions = []

        async def capture_broadcast(execution_id, event_type, payload):
            broadcast_events.append((event_type, payload))

        async def fake_save_workflow(workflow, db):
            return None

        async def save_workflow_execution(execution_data):
            saved_executions.append(dict(execution_data))
            return execution_data["id"]

        async def append_workflow_execution_event(execution_id, event_type, event_data):
            return 1

        db.save_workflow_execution = save_workflow_execution
        db.append_workflow_execution_event = append_workflow_execution_event
        monkeypatch.setattr(self.engine, "_save_workflow_to_db", fake_save_workflow)
        monkeypatch.setattr(self.engine, "_broadcast_status", capture_broadcast)

        result = await self.engine.create_runtime_fixture(
            "00000000-0000-0000-0000-000000000001",
            db,
            fixture_type="state_handoff_context",
            label="state-handoff-fixture-session",
        )

        execution = result["execution"]
        context = execution["context"]
        writer_packet = context["fixture_writer_confirmed_prior_state_packet"]
        evaluator_packet = context["fixture_evaluator_confirmed_prior_state_packet"]
        prior_ids = set(context["fixture_prior_chapter_ids"])
        draft_ids = set(context["fixture_excluded_draft_chapter_ids"])

        assert result["fixture_type"] == "state_handoff_context"
        assert context["chapter_num"] == 3
        assert len(prior_ids) == 2
        assert len(draft_ids) == 1
        assert {chapter["chapter_id"] for chapter in writer_packet["prior_chapters"]} == prior_ids
        assert not ({chapter["chapter_id"] for chapter in writer_packet["prior_chapters"]} & draft_ids)
        assert evaluator_packet == writer_packet
        assert writer_packet["source"]["prior_chapter_count"] == 2
        assert writer_packet["source"]["confirmed_state_total"] == 3
        assert writer_packet["source"]["confirmed_entity_count"] == 2
        confirmed_ids = [change["id"] for change in writer_packet["confirmed_state_changes"]]
        assert len(confirmed_ids) == 3
        assert context["fixture_seeded_state_change_ids"][0] in confirmed_ids
        assert context["fixture_seeded_state_change_ids"][1] in confirmed_ids
        assert context["fixture_seeded_state_change_ids"][2] in confirmed_ids
        assert context["fixture_seeded_state_change_ids"][3] not in confirmed_ids
        assert context["fixture_seeded_state_change_ids"][4] not in confirmed_ids
        assert all(change["status"] in {"applied", "confirmed"} for change in writer_packet["confirmed_state_changes"])
        assert not any("废弃设定" in (change.get("summary") or "") for change in writer_packet["confirmed_state_changes"])
        state_summary = {item["entity_key"]: item for item in writer_packet["confirmed_state_summary"]}
        assert state_summary["character:00000000-0000-0000-0000-000000000101"]["latest_change_id"] == context["fixture_seeded_state_change_ids"][1]
        assert state_summary["character:00000000-0000-0000-0000-000000000101"]["change_count"] == 2
        assert state_summary["character:00000000-0000-0000-0000-000000000101"]["latest_after_state"] == {
            "status": "recovering",
            "location": "星门",
            "traits": ["wounded", "steady", "focused"],
            "notes": {"origin": "first-pass", "phase": "stable", "pace": "measured"},
        }
        assert state_summary["plot:fixture-plot-star-sand-mark"]["latest_status"] == "confirmed"
        repeated_entity_summary = self.engine._build_confirmed_state_summary(
            list(reversed([
                change for change in db.state_changes.values() if change.get("entity_id") == "00000000-0000-0000-0000-000000000101"
            ])),
            limit=10,
        )
        assert repeated_entity_summary[0]["latest_after_state"] == state_summary["character:00000000-0000-0000-0000-000000000101"]["latest_after_state"]
        assert writer_packet["open_proposed_changes"][0]["status"] == "proposed"
        assert writer_packet["open_proposed_changes"][0]["summary"].startswith("星门失稳仍是待确认提示")
        assert context["fixture_seeded_state_change_ids"][3] in [change["id"] for change in writer_packet["open_proposed_changes"]]
        assert context["fixture_seeded_state_change_ids"][4] not in [change["id"] for change in writer_packet["open_proposed_changes"]]
        assert context["fixture_writer_confirmed_prior_state_packet_provenance"]["prior_chapter_count"] == 2
        assert context["fixture_writer_confirmed_prior_state_packet_provenance"]["confirmed_state_count"] == 3
        assert context["fixture_writer_confirmed_prior_state_packet_provenance"]["open_proposed_count"] == 1
        assert context["chapter_saved"] is True
        assert context["state_writeback_counts"]["proposed"] == 1
        assert len([chapter for chapter in db.chapters if chapter.get("status") == "draft"]) == 1
        assert any(event_type == "chapter_state_handoff_loaded" for event_type, _ in broadcast_events)
        assert any(event["context"].get("fixture_writer_confirmed_prior_state_packet") for event in saved_executions)

    @pytest.mark.asyncio
    async def test_cleanup_runtime_fixture_removes_saved_chapter_payload(self, tmp_path, monkeypatch):
        from app.services.chapter_document_storage import ChapterDocumentStorage

        monkeypatch.setattr("app.services.workflow_engine.settings.debug", True)
        storage = ChapterDocumentStorage(str(tmp_path))
        metadata = storage.write_chapter("00000000-0000-0000-0000-000000000099", "00000000-0000-0000-0000-000000000001", "夹具章节", "正文")
        monkeypatch.setattr("app.services.chapter_document_storage.chapter_document_storage", storage)
        deleted_chapter_ids = []
        deleted_state_change_ids = []
        execution = WorkflowExecution(
            id="exec-fixture-saved",
            workflow_id="wf-fixture-saved",
            project_id="00000000-0000-0000-0000-000000000001",
            status=WorkflowStatus.COMPLETED,
            context={
                "runtime_fixture": True,
                "fixture_type": "saved_chapter",
                "cleanup_token": "token",
                "chapter_id": "00000000-0000-0000-0000-000000000099",
                "chapter_content_path": metadata["content_path"],
                "fixture_prior_chapter_ids": ["00000000-0000-0000-0000-000000000101"],
                "fixture_excluded_draft_chapter_ids": ["00000000-0000-0000-0000-000000000102"],
                "fixture_seeded_state_change_ids": ["00000000-0000-0000-0000-000000000103"],
            },
        )
        workflow = WorkflowDefinition(
            id="wf-fixture-saved",
            project_id="00000000-0000-0000-0000-000000000001",
            name="保存章节夹具",
            nodes=[WorkflowNode(id="start", node_type=NodeType.START, label="开始"), WorkflowNode(id="end", node_type=NodeType.END, label="结束")],
            edges=[WorkflowEdge(id="e1", source="start", target="end")],
            variables={"runtime_fixture": True, "cleanup_token": "token"},
        )
        self.engine._executions[execution.id] = execution
        self.engine._workflows[workflow.id] = workflow

        class FixtureDB:
            async def execute_write(self, query, params):
                if "DELETE FROM chapters" in query:
                    deleted_chapter_ids.append(params.get("id"))
                if "DELETE FROM narrative_state_changes" in query:
                    deleted_state_change_ids.append(params.get("id"))
                return None

        async def fake_delete_workflow(workflow_id, db):
            return True

        monkeypatch.setattr(self.engine, "_delete_workflow_from_db", fake_delete_workflow)

        result = await self.engine.cleanup_runtime_fixture(execution.id, workflow.id, "token", FixtureDB())

        assert result["success"] is True
        assert deleted_chapter_ids == [
            "00000000-0000-0000-0000-000000000099",
            "00000000-0000-0000-0000-000000000101",
            "00000000-0000-0000-0000-000000000102",
        ]
        assert deleted_state_change_ids == ["00000000-0000-0000-0000-000000000103"]
        assert not (tmp_path / metadata["content_path"]).exists()

    @pytest.mark.asyncio
    async def test_cleanup_runtime_fixture_rejects_non_fixture_data(self, monkeypatch):
        monkeypatch.setattr("app.services.workflow_engine.settings.debug", True)
        execution = WorkflowExecution(
            id="exec-real",
            workflow_id="wf-real",
            project_id="test-project",
            status=WorkflowStatus.FAILED,
            context={},
        )
        workflow = WorkflowDefinition(
            id="wf-real",
            project_id="test-project",
            name="真实工作流",
            nodes=[WorkflowNode(id="start", node_type=NodeType.START, label="开始"), WorkflowNode(id="end", node_type=NodeType.END, label="结束")],
            edges=[WorkflowEdge(id="e1", source="start", target="end")],
            variables={},
        )
        self.engine._executions[execution.id] = execution
        self.engine._workflows[workflow.id] = workflow

        with pytest.raises(WorkflowOperationError) as exc_info:
            await self.engine.cleanup_runtime_fixture("exec-real", "wf-real", "token", object())

        assert exc_info.value.code == "workflow_fixture_guard_failed"

    @pytest.mark.asyncio
    async def test_resolve_stale_execution_rejects_unexpired_lease(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={},
            lease_expires_at=datetime.now() + timedelta(seconds=60),
        )
        self.engine._executions[execution.id] = execution

        with pytest.raises(WorkflowOperationError) as exc_info:
            await self.engine.resolve_stale_execution(execution.id, action="mark_failed")

        assert exc_info.value.operation == "stale"
        assert "尚未过期" in str(exc_info.value)
        assert execution.status == WorkflowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_operation_summary_reports_capabilities_and_audit_counts(self):
        execution = self._failed_remediation_execution()
        execution.context["recovery_history"] = [{"attempt": 1, "target_node_id": "plotter_failure"}]
        execution.context["remediation_history"] = [{"attempt": 1, "node_id": "plotter_failure"}]
        execution.context["stale_execution_history"] = [{"operation": "inspect"}]
        self.engine._executions[execution.id] = execution

        summary = await self.engine.get_execution_operation_summary(execution.id)

        assert summary["execution_id"] == execution.id
        assert summary["status"] == "failed"
        assert summary["capabilities"]["recover"]["allowed"] is True
        assert summary["capabilities"]["remediate"]["allowed"] is True
        assert summary["capabilities"]["pause"]["allowed"] is False
        assert summary["node_summary"]["failed_node_id"] == "plotter_failure"
        assert summary["recovery"]["count"] == 1
        assert summary["remediation"]["count"] == 1
        assert summary["stale"]["count"] == 1
        assert any(item["type"] == "failed_node" for item in summary["attention"])

    @pytest.mark.asyncio
    async def test_active_task_prevents_stale_marking_even_if_lease_expired(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={},
            lease_expires_at=datetime.now() - timedelta(seconds=5),
        )
        self.engine._executions[execution.id] = execution
        task = asyncio.create_task(asyncio.sleep(60))
        self.engine._running_tasks[execution.id] = task

        try:
            result = await self.engine.get_execution_state(execution.id)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert result is execution
        assert execution.status == WorkflowStatus.RUNNING
        assert "stale_execution_history" not in execution.context

    @pytest.mark.asyncio
    async def test_execute_node_fails_on_strict_contract_validation(self):
        """测试 Agent 节点 strict 输出缺字段时会触发 contract 校验失败。"""
        broadcast_events = []
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

        async def _fake_broadcast(execution_id, event_type, data):
            broadcast_events.append({"execution_id": execution_id, "event_type": event_type, "data": data})

        async def _fake_execute_agent_node(*args, **kwargs):
            response = FakeAgentResponse(
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

        event_types = [event["event_type"] for event in broadcast_events]
        assert "node_failed" in event_types
        assert "node_completed" in event_types
        failed_event = next(event for event in broadcast_events if event["event_type"] == "node_failed")
        assert failed_event["execution_id"] == execution.id
        assert failed_event["data"]["node_id"] == "plotter"
        assert failed_event["data"]["node_type"] == "agent"
        assert failed_event["data"]["agent_type"] == "plot_outline"
        assert failed_event["data"]["status"] == "failed"
        assert "plot_outline.workflow_output" in failed_event["data"]["error"]
        completed_event = next(event for event in broadcast_events if event["event_type"] == "node_completed")
        assert completed_event["data"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_recover_failed_workflow_resets_failed_node_and_descendants(self):
        workflow = WorkflowDefinition(
            id="wf-recovery",
            project_id="test-project",
            name="恢复测试",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="写作", position={"x": 0, "y": 100}),
                WorkflowNode(id="evaluator", node_type=NodeType.AGENT, agent_type="evaluator", label="评估", position={"x": 0, "y": 200}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 300}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="writer"),
                WorkflowEdge(id="e2", source="writer", target="evaluator"),
                WorkflowEdge(id="e3", source="evaluator", target="end"),
            ],
        )
        execution = WorkflowExecution(
            id="exec-recovery",
            workflow_id=workflow.id,
            project_id="test-project",
            status=WorkflowStatus.FAILED,
            current_node="writer",
            error="writer failed",
            completed_at=datetime.now(),
            total_duration_ms=123,
            node_states={
                "start": NodeExecutionState(node_id="start", status=NodeStatus.COMPLETED, output_data={"status": "started"}),
                "writer": NodeExecutionState(node_id="writer", status=NodeStatus.FAILED, output_data={"bad": True}, error="writer failed", retry_count=1),
                "evaluator": NodeExecutionState(node_id="evaluator", status=NodeStatus.COMPLETED, output_data={"score": 0}),
                "end": NodeExecutionState(node_id="end", status=NodeStatus.COMPLETED, output_data={"status": "completed"}),
            },
            context={
                "node_outputs": {
                    "start": {"status": "started"},
                    "writer": {"bad": True},
                    "evaluator": {"score": 0},
                    "end": {"status": "completed"},
                },
                "latest_node_output": {"node_id": "end", "status": "completed"},
            },
            trace_id="trace-recovery",
        )
        self.engine._executions[execution.id] = execution
        broadcasts = []
        started = []

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        async def _fake_broadcast(execution_id, event_type, data):
            broadcasts.append({"execution_id": execution_id, "event_type": event_type, "data": data})

        def _fake_start(execution_id, workflow_arg, db=None):
            started.append({"execution_id": execution_id, "workflow_id": workflow_arg.id})

        self.engine.get_workflow = _fake_get_workflow
        self.engine._broadcast_status = _fake_broadcast
        self.engine._start_workflow_task = _fake_start

        result = await self.engine.recover_failed_workflow(execution.id, reason="test_retry")

        assert result["success"] is True
        assert result["status"] == "running"
        assert result["recovered_node_id"] == "writer"
        assert result["reset_node_ids"] == ["end", "evaluator", "writer"]
        assert execution.status == WorkflowStatus.RUNNING
        assert execution.error is None
        assert execution.completed_at is None
        assert execution.total_duration_ms is None
        assert execution.current_node == "writer"
        assert execution.node_states["start"].status == NodeStatus.COMPLETED
        assert execution.node_states["writer"].status == NodeStatus.PENDING
        assert execution.node_states["writer"].error is None
        assert execution.node_states["writer"].output_data == {}
        assert execution.node_states["writer"].retry_count == 2
        assert execution.node_states["evaluator"].status == NodeStatus.PENDING
        assert execution.node_states["end"].status == NodeStatus.PENDING
        assert set(execution.context["node_outputs"].keys()) == {"start"}
        assert "latest_node_output" not in execution.context
        recovery_entry = execution.context["recovery_history"][0]
        assert recovery_entry["target_node_id"] == "writer"
        assert recovery_entry["trace_id"] == "trace-recovery"
        assert recovery_entry["status_at_start"] == "failed"
        assert result["recovery_entry"] == recovery_entry
        assert execution.resume_cursor["recovered_node_id"] == "writer"
        assert broadcasts[0]["event_type"] == "workflow_recovery_started"
        assert broadcasts[0]["data"]["recovery_attempt"] == 1
        assert started == [{"execution_id": execution.id, "workflow_id": workflow.id}]

    @pytest.mark.asyncio
    async def test_recover_failed_terminal_node_retries_nearest_upstream_agent(self):
        workflow = WorkflowDefinition(
            id="wf-terminal-recovery",
            project_id="test-project",
            name="终态恢复测试",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="写作", position={"x": 0, "y": 100}),
                WorkflowNode(id="save", node_type=NodeType.END, label="保存", position={"x": 0, "y": 200}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="writer"),
                WorkflowEdge(id="e2", source="writer", target="save"),
            ],
        )
        execution = WorkflowExecution(
            id="exec-terminal-recovery",
            workflow_id=workflow.id,
            project_id="test-project",
            status=WorkflowStatus.FAILED,
            current_node="save",
            error="save failed",
            completed_at=datetime.now(),
            node_states={
                "start": NodeExecutionState(node_id="start", status=NodeStatus.COMPLETED, output_data={"status": "started"}),
                "writer": NodeExecutionState(node_id="writer", status=NodeStatus.COMPLETED, output_data={"chapter_content": "old draft"}, retry_count=0),
                "save": NodeExecutionState(node_id="save", status=NodeStatus.FAILED, output_data={"chapter_id": "old"}, error="save failed"),
            },
            context={
                "node_outputs": {
                    "start": {"status": "started"},
                    "writer": {"chapter_content": "old draft"},
                    "save": {"chapter_id": "old"},
                },
                "latest_node_output": {"node_id": "save", "chapter_id": "old"},
            },
        )
        self.engine._executions[execution.id] = execution
        started = []

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        async def _fake_broadcast(execution_id, event_type, data):
            pass

        def _fake_start(execution_id, workflow_arg, db=None):
            started.append({"execution_id": execution_id, "workflow_id": workflow_arg.id})

        self.engine.get_workflow = _fake_get_workflow
        self.engine._broadcast_status = _fake_broadcast
        self.engine._start_workflow_task = _fake_start

        result = await self.engine.recover_failed_workflow(execution.id, reason="retry_real_llm")

        assert result["recovered_node_id"] == "writer"
        assert result["reset_node_ids"] == ["save", "writer"]
        assert execution.current_node == "writer"
        assert execution.node_states["writer"].status == NodeStatus.PENDING
        assert execution.node_states["writer"].output_data == {}
        assert execution.node_states["writer"].retry_count == 1
        assert execution.node_states["save"].status == NodeStatus.PENDING
        assert set(execution.context["node_outputs"].keys()) == {"start"}
        assert "latest_node_output" not in execution.context
        assert started == [{"execution_id": execution.id, "workflow_id": workflow.id}]

    @pytest.mark.asyncio
    async def test_recovered_workflow_preserves_saved_chapter_handoff(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.services.chapter_document_storage.chapter_document_storage",
            ChapterDocumentStorage(str(tmp_path)),
        )
        workflow = WorkflowDefinition(
            id="wf-recovered-save",
            project_id="test-project",
            name="恢复后保存章节",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始"),
                WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="写作"),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束"),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="writer"),
                WorkflowEdge(id="e2", source="writer", target="end"),
            ],
        )
        execution = WorkflowExecution(
            id="exec-recovered-save",
            workflow_id=workflow.id,
            project_id="test-project",
            status=WorkflowStatus.FAILED,
            current_node="writer",
            error="writer failed before save",
            node_states={
                "start": NodeExecutionState(node_id="start", status=NodeStatus.COMPLETED, output_data={"status": "started"}),
                "writer": NodeExecutionState(node_id="writer", status=NodeStatus.FAILED, error="writer failed before save"),
                "end": NodeExecutionState(node_id="end", status=NodeStatus.PENDING),
            },
            context={
                "chapter_num": 9,
                "chapter_title": "第九章：归线",
                "chapter_outline_id": "outline-recovered-save",
                "node_outputs": {"start": {"status": "started"}, "writer": {"draft": "bad"}},
                "latest_node_output": {"node_id": "writer", "draft": "bad"},
            },
            trace_id="trace-recovered-save",
        )
        self.engine._executions[execution.id] = execution
        db = FakeDiscussionDB()
        broadcasts = []
        started = []

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        async def _fake_broadcast(execution_id, event_type, data):
            broadcasts.append({"execution_id": execution_id, "event_type": event_type, "data": data})

        def _fake_start(execution_id, workflow_arg, db=None):
            started.append({"execution_id": execution_id, "workflow_id": workflow_arg.id})

        async def _fake_save_execution(execution_arg, db=None):
            return None

        self.engine.get_workflow = _fake_get_workflow
        self.engine._broadcast_status = _fake_broadcast
        self.engine._start_workflow_task = _fake_start
        self.engine._save_execution_to_db = _fake_save_execution

        result = await self.engine.recover_failed_workflow(execution.id, db=db, reason="retry_writer_after_fix")
        await self.engine._save_chapter_from_writer(
            execution,
            {"chapter_content": "恢复后保存的正文", "word_count": 8},
            db,
        )

        assert result["success"] is True
        assert execution.context["recovery_history"][0]["reason"] == "retry_writer_after_fix"
        assert execution.context["chapter_saved"] is True
        assert execution.context["chapter_saved_payload"]["chapter_id"] == execution.context["chapter_id"]
        assert execution.context["chapter_saved_payload"]["content_path"] == db.chapters[0]["content_path"]
        assert execution.context["chapter_content_checksum"] == db.chapters[0]["content_checksum"]
        assert "writer" not in execution.context["node_outputs"]
        assert "latest_node_output" not in execution.context
        assert [event["event_type"] for event in broadcasts] == ["workflow_recovery_started", "chapter_saved"]
        saved_payload = broadcasts[-1]["data"]
        assert saved_payload["execution_id"] == execution.id
        assert saved_payload["workflow_id"] == workflow.id
        assert saved_payload["chapter_id"] == execution.context["chapter_id"]
        assert saved_payload["content_path"] == db.chapters[0]["content_path"]
        assert saved_payload["content_checksum"] == db.chapters[0]["content_checksum"]
        assert "content" not in saved_payload
        assert started == [{"execution_id": execution.id, "workflow_id": workflow.id}]

    @pytest.mark.asyncio
    async def test_diagnose_failed_workflow_node_classifies_missing_agent(self):
        workflow = WorkflowDefinition(
            id="wf-diagnosis",
            project_id="test-project",
            name="诊断测试",
            nodes=[
                WorkflowNode(
                    id="plotter_failure",
                    node_type=NodeType.AGENT,
                    agent_type="smoke_contract_failure",
                    label="失败编剧",
                    position={"x": 0, "y": 0},
                ),
            ],
            edges=[],
        )
        execution = WorkflowExecution(
            id="exec-diagnosis",
            workflow_id=workflow.id,
            project_id="test-project",
            status=WorkflowStatus.FAILED,
            current_node="plotter_failure",
            error="无法获取 Agent: smoke_contract_failure",
            node_states={
                "plotter_failure": NodeExecutionState(
                    node_id="plotter_failure",
                    status=NodeStatus.FAILED,
                    error="无法获取 Agent: smoke_contract_failure",
                ),
            },
        )
        self.engine._executions[execution.id] = execution

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        self.engine.get_workflow = _fake_get_workflow

        diagnosis = await self.engine.diagnose_failed_workflow_node(execution.id)

        assert diagnosis["category"] == "missing_agent"
        assert diagnosis["retry_without_fix_likely_to_fail"] is True
        assert diagnosis["remediable"] is True
        assert diagnosis["current_agent_type"] == "smoke_contract_failure"

    @pytest.mark.asyncio
    async def test_remediate_failed_workflow_node_patches_agent_and_recovers_same_execution(self):
        workflow = self._remediation_workflow()
        execution = self._failed_remediation_execution(workflow.id)
        self.engine._executions[execution.id] = execution
        broadcasts = []
        started = []
        saved_workflows = []

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        async def _fake_save_workflow(workflow_arg, db=None):
            saved_workflows.append(workflow_arg.model_copy(deep=True))

        async def _fake_save_execution(execution_arg, db=None):
            return None

        async def _fake_broadcast(execution_id, event_type, data):
            broadcasts.append({"execution_id": execution_id, "event_type": event_type, "data": data})

        def _fake_start(execution_id, workflow_arg, db=None):
            started.append({"execution_id": execution_id, "workflow_id": workflow_arg.id})

        self.engine.get_workflow = _fake_get_workflow
        self.engine._save_workflow_to_db = _fake_save_workflow
        self.engine._save_execution_to_db = _fake_save_execution
        self.engine._broadcast_status = _fake_broadcast
        self.engine._start_workflow_task = _fake_start

        result = await self.engine.remediate_failed_workflow_node(
            execution.id,
            db=object(),
            patch={"agent_type": "plot_outline", "scenario": "workflow_output"},
            reason="fix_missing_agent",
        )

        target_node = next(node for node in workflow.nodes if node.id == "plotter_failure")
        assert result["success"] is True
        assert result["recovery"]["recovered_node_id"] == "plotter_failure"
        assert target_node.agent_type == "plot_outline"
        assert target_node.config["scenario"] == "workflow_output"
        assert execution.status == WorkflowStatus.RUNNING
        assert execution.current_node == "plotter_failure"
        remediation_entry = execution.context["remediation_history"][0]
        assert remediation_entry["reason"] == "fix_missing_agent"
        assert remediation_entry["started_at"]
        assert remediation_entry["applied_at"] == remediation_entry["started_at"]
        assert remediation_entry["previous_error"] == "无法获取 Agent: smoke_contract_failure"
        assert remediation_entry["diff"]["after"]["agent_type"] == "plot_outline"
        assert remediation_entry["diff"]["after"]["scenario"] == "workflow_output"
        remediation_event = next(event for event in broadcasts if event["event_type"] == "workflow_node_remediated")
        assert remediation_event["data"]["status"] == "failed"
        assert remediation_event["data"]["current_node"] == "plotter_failure"
        assert remediation_event["data"]["node_id"] == "plotter_failure"
        assert remediation_event["data"]["previous_error"] == "无法获取 Agent: smoke_contract_failure"
        assert remediation_event["data"]["diagnosis_category"] == "missing_agent"
        assert remediation_event["data"]["remediation_entry"]["diff"]["after"]["agent_type"] == "plot_outline"
        assert remediation_event["data"]["remediation_entry"]["started_at"]
        assert remediation_event["data"]["remediation_entry"]["applied_at"] == remediation_event["data"]["remediation_entry"]["started_at"]
        assert any(event["event_type"] == "workflow_recovery_started" for event in broadcasts)
        assert saved_workflows and saved_workflows[0].nodes[1].agent_type == "plot_outline"
        assert [node.id for node in saved_workflows[0].nodes] == ["start", "plotter_failure", "end"]
        assert [(edge.source, edge.target) for edge in saved_workflows[0].edges] == [("start", "plotter_failure"), ("plotter_failure", "end")]
        assert started == [{"execution_id": execution.id, "workflow_id": workflow.id}]

    def test_replay_export_includes_remediation_and_recovery_audit(self):
        workflow = self._remediation_workflow()
        execution = self._failed_remediation_execution(workflow.id)
        execution.context["remediation_history"] = [
            {
                "attempt": 1,
                "node_id": "plotter_failure",
                "diagnosis_category": "missing_agent",
                "reason": "fix_missing_agent",
                "started_at": "2026-05-10T10:00:00",
                "applied_at": "2026-05-10T10:00:01",
                "previous_error": "无法获取 Agent: smoke_contract_failure",
                "diff": {
                    "before": {"agent_type": "smoke_contract_failure", "scenario": "broken"},
                    "after": {"agent_type": "plot_outline", "scenario": "workflow_output"},
                },
                "prompt": "must not be rendered outside diff",
            }
        ]
        execution.context["recovery_history"] = [
            {
                "attempt": 1,
                "mode": "from_failed_node",
                "target_node_id": "plotter_failure",
                "reset_node_ids": ["plotter_failure", "end"],
                "reason": "fix_missing_agent",
                "started_at": "2026-05-10T10:00:02",
                "previous_error": "无法获取 Agent: smoke_contract_failure",
                "trace_id": "trace-remediation-fixture",
                "status_at_start": "failed",
                "prompt": "must not be rendered",
            }
        ]

        markdown = WorkflowReplayExportService().export_markdown(execution, workflow)

        assert "## 修复与恢复审计" in markdown
        assert "### 修复记录" in markdown
        assert "#### 修复尝试 1" in markdown
        assert "- **节点 ID**: `plotter_failure`" in markdown
        assert "- **诊断分类**: `missing_agent`" in markdown
        assert "- **原因**: fix_missing_agent" in markdown
        assert "- **原始错误**: 无法获取 Agent: smoke_contract_failure" in markdown
        assert '"agent_type": "smoke_contract_failure"' in markdown
        assert '"agent_type": "plot_outline"' in markdown
        assert "### 恢复记录" in markdown
        assert "#### 恢复尝试 1" in markdown
        assert "- **模式**: `from_failed_node`" in markdown
        assert "- **重置节点**: plotter_failure, end" in markdown
        assert "- **Trace ID**: `trace-remediation-fixture`" in markdown
        assert "- **开始状态**: `failed`" in markdown
        assert markdown.index("## 修复与恢复审计") < markdown.index("## 节点复盘")
        assert "must not be rendered" not in markdown

    @pytest.mark.asyncio
    async def test_writer_evaluator_condition_revision_loop_stages_then_finalizes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.services.chapter_document_storage.chapter_document_storage",
            ChapterDocumentStorage(str(tmp_path)),
        )
        workflow = WorkflowDefinition(
            id="wf-quality-loop",
            project_id="00000000-0000-0000-0000-000000000001",
            name="质量门循环",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始"),
                WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="写作", config={"quality_gate_enabled": True}),
                WorkflowNode(id="evaluator", node_type=NodeType.AGENT, agent_type="evaluator", label="评估"),
                WorkflowNode(id="gate", node_type=NodeType.CONDITION, label="质量门"),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束"),
            ],
            edges=[
                WorkflowEdge(source="start", target="writer"),
                WorkflowEdge(source="writer", target="evaluator"),
                WorkflowEdge(source="evaluator", target="gate"),
                WorkflowEdge(source="gate", target="end", condition={"result": "pass"}),
                WorkflowEdge(source="gate", target="writer", condition={"result": "retry"}),
            ],
        )
        self.engine._workflows[workflow.id] = workflow
        db = FakeDiscussionDB()
        db.outlines["outline-quality-loop"] = {
            "id": "outline-quality-loop",
            "project_id": workflow.project_id,
            "chapter_number": 10,
            "status": "approved",
            "next_outline_id": None,
        }

        async def fake_save_workflow_execution(data):
            db.executions.append(dict(data))
            return data.get("id")

        db.save_workflow_execution = fake_save_workflow_execution
        broadcasts = []
        writer_contexts = []
        writer_attempts = {"count": 0}
        evaluator_attempts = {"count": 0}

        class FakeWriterAgent:
            name = "fake-writer"
            model = None
            _stream_callback = None

            async def execute(self, context):
                writer_contexts.append(dict(context))
                writer_attempts["count"] += 1
                if writer_attempts["count"] == 1:
                    return FakeAgentResponse({"chapter_content": "第一版正文", "word_count": 100, "hooks_embedded": [], "future_setup": [], "style_check": {"passed": True}}, contract_id="writer.workflow_output", schema_name="writer.workflow_output")
                return FakeAgentResponse({"chapter_content": "第二版正文", "word_count": 100, "hooks_embedded": [], "future_setup": [], "style_check": {"passed": True}}, contract_id="writer.workflow_output", schema_name="writer.workflow_output")

        class FakeEvaluatorAgent:
            name = "fake-evaluator"
            model = None
            _stream_callback = None

            async def execute(self, context):
                evaluator_attempts["count"] += 1
                if evaluator_attempts["count"] == 1:
                    return FakeAgentResponse({"quality_passed": False, "score": 4, "issues": ["动机断裂"], "suggestions": ["重写动机"], "word_count_check": {"passed": True}})
                return FakeAgentResponse({"quality_passed": True, "score": 8.5, "issues": [], "suggestions": ["可保存"], "summary": "质量达标", "word_count_check": {"passed": True}})

        async def fake_provider(agent_type, project_id):
            if agent_type == "writer":
                return FakeWriterAgent()
            if agent_type == "evaluator":
                return FakeEvaluatorAgent()
            raise AssertionError(agent_type)

        async def capture_broadcast(execution_id, event_type, payload):
            broadcasts.append((event_type, payload))

        self.engine.set_agent_provider(fake_provider)
        monkeypatch.setattr(self.engine, "_broadcast_status", capture_broadcast)
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            project_id=workflow.project_id,
            status=WorkflowStatus.RUNNING,
            context={
                "chapter_num": 10,
                "chapter_title": "第十章：复写",
                "chapter_outline_id": "outline-quality-loop",
                "target_word_count": 5,
            },
            node_states={node.id: NodeExecutionState(node_id=node.id, status=NodeStatus.PENDING) for node in workflow.nodes},
        )
        predecessors = self.engine._build_predecessor_graph(workflow)
        completed_nodes = set()
        for node_id in ["start", "writer", "evaluator", "gate", "writer", "evaluator", "gate", "end"]:
            node = next(item for item in workflow.nodes if item.id == node_id)
            await self.engine._execute_node_with_merge(execution, node, predecessors, workflow, db)
            completed_nodes.add(node_id)
            if node.node_type == NodeType.CONDITION:
                next_node_id = self.engine._get_next_node(node_id, execution, workflow)
                if next_node_id in completed_nodes:
                    reset_nodes = self.engine._get_goto_reset_nodes(workflow, node_id, next_node_id)
                    self.engine._reset_nodes_for_goto(execution, completed_nodes, reset_nodes, f"test goto: {node_id} -> {next_node_id}")

        assert writer_attempts["count"] == 2
        assert evaluator_attempts["count"] == 2
        assert len(db.chapters) == 1
        assert db.chapters[0]["content"] == ""
        assert (tmp_path / db.chapters[0]["content_path"]).read_text(encoding="utf-8") == "第二版正文"
        assert execution.context["chapter_saved"] is True
        assert execution.context["pending_chapter_save"] is False
        assert execution.context["chapter_draft_attempt"] == 2
        assert execution.context["quality_gate_status"] == "passed"
        assert len(execution.context["quality_gate_history"]) == 2
        assert execution.context["quality_gate_history"][0]["passed"] is False
        assert execution.context["quality_gate_history"][1]["passed"] is True
        assert len(execution.context["revision_history"]) == 1
        assert writer_contexts[1]["is_retry"] is True
        assert writer_contexts[1]["task_type"] == "rewrite_by_review"
        assert writer_contexts[1]["agent_scenario"] == "rewrite_by_review"
        assert "evaluation_feedback" in writer_contexts[1]
        assert [event for event, _ in broadcasts].count("chapter_draft_ready") == 2
        assert [event for event, _ in broadcasts].count("chapter_saved") == 1
        assert "quality_gate_failed" in [event for event, _ in broadcasts]
        assert "chapter_revision_requested" in [event for event, _ in broadcasts]
        assert "chapter_finalized" in [event for event, _ in broadcasts]
        assert db.outlines["outline-quality-loop"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_failed_quality_gate_routes_to_master_revision_director_before_writer(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.services.chapter_document_storage.chapter_document_storage",
            ChapterDocumentStorage(str(tmp_path)),
        )
        workflow = WorkflowDefinition(
            id="wf-master-quality-loop",
            project_id="00000000-0000-0000-0000-000000000001",
            name="Master质量门循环",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始"),
                WorkflowNode(id="master_scene", node_type=NodeType.AGENT, agent_type="master_plotter", label="Master场景", config={"scenario": "workflow_scene_compilation"}),
                WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="写作", config={"quality_gate_enabled": True}),
                WorkflowNode(id="evaluator", node_type=NodeType.AGENT, agent_type="evaluator", label="评估"),
                WorkflowNode(id="gate", node_type=NodeType.CONDITION, label="质量门", config={"max_retry_policy": "human_review_required"}),
                WorkflowNode(id="master_revision", node_type=NodeType.AGENT, agent_type="master_plotter", label="Master修订", config={"scenario": "workflow_revision_director"}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束"),
            ],
            edges=[
                WorkflowEdge(source="start", target="master_scene"),
                WorkflowEdge(source="master_scene", target="writer"),
                WorkflowEdge(source="writer", target="evaluator"),
                WorkflowEdge(source="evaluator", target="gate"),
                WorkflowEdge(source="gate", target="end", condition={"result": "pass"}),
                WorkflowEdge(source="gate", target="master_revision", condition={"result": "retry"}),
                WorkflowEdge(source="master_revision", target="writer"),
            ],
        )
        self.engine._workflows[workflow.id] = workflow
        db = FakeDiscussionDB()
        db.outlines["outline-master-loop"] = {"id": "outline-master-loop", "project_id": workflow.project_id, "chapter_number": 11, "status": "approved"}

        async def fake_save_workflow_execution(data):
            db.executions.append(dict(data))
            return data.get("id")

        db.save_workflow_execution = fake_save_workflow_execution
        contexts = {"master": [], "writer": [], "evaluator": []}
        counts = {"writer": 0, "evaluator": 0, "master_revision": 0}

        class FakeMasterAgent:
            name = "fake-master"
            model = None
            _stream_callback = None

            async def execute(self, context):
                contexts["master"].append(dict(context))
                if context.get("task") == "prepare_revision_directive":
                    counts["master_revision"] += 1
                    assert "quality_failure_packet" in context
                    return FakeAgentResponse({
                        "master_revision_directive": {
                            "revision_id": "rev-1",
                            "revision_attempt": 1,
                            "rewrite_strategy": "scene_rewrite",
                            "issues": [{"issue_id": "issue-1", "failure_type": "scene_plan_miss", "failed_scene_beat_ids": ["beat-1"], "required_fix": "补足可见后果"}],
                            "writer_revision_brief": {"scope": "beat-1"},
                            "evaluator_focus": ["beat-1"],
                        }
                    }, contract_id="master_plotter.revision_directive.workflow_output", schema_name="master_plotter.revision_directive.workflow_output")
                return FakeAgentResponse({
                    "master_scene_plan": {
                        "plan_id": "plan-1",
                        "plan_version": "scene_compiler_v1",
                        "scene_plan": [{"beat_id": "beat-1", "acceptance_criteria": ["可见后果"]}],
                        "writer_brief": {"must_follow": ["beat-1"]},
                        "evaluator_checklist": {"required_beat_ids": ["beat-1"]},
                    }
                }, contract_id="master_plotter.scene_plan.workflow_output", schema_name="master_plotter.scene_plan.workflow_output")

        class FakeWriterAgent:
            name = "fake-writer"
            model = None
            _stream_callback = None

            async def execute(self, context):
                contexts["writer"].append(dict(context))
                counts["writer"] += 1
                if counts["writer"] == 1:
                    assert context["scene_plan_id"] == "plan-1"
                    return FakeAgentResponse({"chapter_content": "第一版正文", "word_count": 100}, contract_id="writer.workflow_output", schema_name="writer.workflow_output")
                assert context["revision_directive_id"] == "rev-1"
                assert context["writer_revision_brief"] == {"scope": "beat-1"}
                return FakeAgentResponse({"chapter_content": "第二版正文", "word_count": 100}, contract_id="writer.workflow_output", schema_name="writer.workflow_output")

        class FakeEvaluatorAgent:
            name = "fake-evaluator"
            model = None
            _stream_callback = None

            async def execute(self, context):
                contexts["evaluator"].append(dict(context))
                counts["evaluator"] += 1
                assert context["scene_plan_id"] == "plan-1"
                if counts["evaluator"] == 1:
                    return FakeAgentResponse({"quality_passed": False, "score": 4, "issues": ["缺 beat"], "suggestions": ["修订"], "word_count_check": {"passed": True}, "scene_plan_adherence_check": {"passed": False, "missing_beat_ids": ["beat-1"], "failed_beat_ids": ["beat-1"], "issues": ["缺 beat"]}, "failed_scene_beat_ids": ["beat-1"]})
                assert context["revision_directive_id"] == "rev-1"
                return FakeAgentResponse({"quality_passed": True, "score": 8.5, "issues": [], "suggestions": [], "summary": "通过", "word_count_check": {"passed": True}, "scene_plan_adherence_check": {"passed": True, "covered_beat_ids": ["beat-1"]}, "revision_directive_adherence_check": {"passed": True, "resolved_issue_ids": ["issue-1"]}})

        async def fake_provider(agent_type, project_id):
            if agent_type == "master_plotter":
                return FakeMasterAgent()
            if agent_type == "writer":
                return FakeWriterAgent()
            if agent_type == "evaluator":
                return FakeEvaluatorAgent()
            raise AssertionError(agent_type)

        self.engine.set_agent_provider(fake_provider)
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            project_id=workflow.project_id,
            status=WorkflowStatus.RUNNING,
            context={"chapter_num": 11, "chapter_outline_id": "outline-master-loop", "chapter_outline": {"title": "测试"}, "target_word_count": 5},
            node_states={node.id: NodeExecutionState(node_id=node.id, status=NodeStatus.PENDING) for node in workflow.nodes},
        )
        predecessors = self.engine._build_predecessor_graph(workflow)
        completed_nodes = set()
        for node_id in ["start", "master_scene", "writer", "evaluator", "gate", "master_revision", "writer", "evaluator", "gate", "end"]:
            node = next(item for item in workflow.nodes if item.id == node_id)
            await self.engine._execute_node_with_merge(execution, node, predecessors, workflow, db)
            completed_nodes.add(node_id)
            if node.node_type == NodeType.CONDITION:
                next_node_id = self.engine._get_next_node(node_id, execution, workflow)
                if next_node_id in completed_nodes:
                    reset_nodes = self.engine._get_goto_reset_nodes(workflow, node_id, next_node_id)
                    self.engine._reset_nodes_for_goto(execution, completed_nodes, reset_nodes, f"test goto: {node_id} -> {next_node_id}")

        assert counts == {"writer": 2, "evaluator": 2, "master_revision": 1}
        assert execution.context["quality_failure_packet"]["failed_scene_beat_ids"] == ["beat-1"]
        assert execution.context["revision_directive_id"] == "rev-1"
        assert execution.context["chapter_saved_payload"]["scene_plan_id"] == "plan-1"
        assert execution.context["chapter_saved_payload"]["revision_directive_id"] == "rev-1"
        assert db.chapters and (tmp_path / db.chapters[0]["content_path"]).read_text(encoding="utf-8") == "第二版正文"

    def test_deterministic_chapter_style_gate_blocks_overblown_ai_prose(self):
        engine = WorkflowEngine()
        chapter_content = (
            "像是有人把恒星塞进了他的颅腔。"
            "属于另一个存在的记忆碎片呼啸着涌入——古老的代码、失落的力量、还有某个存在留下的警告符号。\n"
            "他知道，真正的危机才刚刚开始，这不仅关系到他的未来，更是命运的转折。"
        )
        evaluator_output = {"quality_passed": True, "score": 8.5, "issues": [], "suggestions": []}

        gate = engine._run_deterministic_chapter_style_gate(chapter_content, evaluator_output, {})

        assert gate["passed"] is False
        assert any("高密度 AI" in issue for issue in gate["issues"])
        assert gate["warnings"] == ["Evaluator 声称通过但 summary 与 issues 为空，质量证据不足。"]
        assert gate["version"] == "de_ai_outline_scene_v1"

    def test_deterministic_chapter_style_gate_propagates_nested_transposition_failure(self):
        engine = WorkflowEngine()
        gate = engine._run_deterministic_chapter_style_gate(
            "林墨关掉终端。",
            {
                "quality_passed": True,
                "summary": "基本覆盖大纲",
                "outline_transposition_check": {
                    "passed": False,
                    "issues": ["大纲节点被直接扩写"],
                    "rewrite_focus": ["从场景触发进入"],
                },
            },
            {},
        )

        assert gate["passed"] is False
        assert any("outline_transposition_check" in issue for issue in gate["issues"])

    def test_deterministic_chapter_style_gate_propagates_scene_and_revision_failures(self):
        engine = WorkflowEngine()
        gate = engine._run_deterministic_chapter_style_gate(
            "林墨关掉终端。",
            {
                "quality_passed": True,
                "scene_plan_adherence_check": {"passed": False, "failed_beat_ids": ["beat-1"], "issues": ["缺可见后果"]},
                "revision_directive_adherence_check": {"passed": False, "unresolved_issue_ids": ["issue-1"], "issues": ["未修订"]},
            },
            {},
        )

        assert gate["passed"] is False
        assert any("scene_plan_adherence_check" in issue for issue in gate["issues"])
        assert any("revision_directive_adherence_check" in issue for issue in gate["issues"])

    def test_replay_export_includes_quality_gate_audit_without_content(self):
        workflow = WorkflowDefinition(
            id="wf-quality-replay",
            project_id="test-project",
            name="质量门复盘",
            nodes=[
                WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="写作"),
                WorkflowNode(id="evaluator", node_type=NodeType.AGENT, agent_type="evaluator", label="评估"),
            ],
            edges=[],
        )
        execution = WorkflowExecution(
            id="exec-quality-replay",
            workflow_id=workflow.id,
            project_id="test-project",
            status=WorkflowStatus.COMPLETED,
            context={
                "chapter_content": "SENTINEL_FULL_CHAPTER_CONTENT_SHOULD_NOT_RENDER",
                "quality_gate": {"status": "passed", "passed": True, "score": 8.2, "draft_attempt": 2},
                "quality_gate_history": [
                    {
                        "evaluator_node_id": "evaluator",
                        "evaluator_node_label": "评估",
                        "passed": False,
                        "score": 4.0,
                        "draft_attempt": 1,
                        "content_chars": 1200,
                        "content_checksum": "draft-one",
                        "issues_count": 1,
                        "suggestions_count": 1,
                        "issues": ["动机断裂"],
                        "suggestions": ["重写动机"],
                        "evaluated_at": "2026-05-10T10:00:00",
                        "content": "hidden",
                    },
                    {
                        "evaluator_node_id": "evaluator",
                        "evaluator_node_label": "评估",
                        "passed": True,
                        "score": 8.2,
                        "draft_attempt": 2,
                        "content_chars": 1320,
                        "content_checksum": "draft-two",
                        "issues_count": 0,
                        "suggestions_count": 1,
                        "issues": [],
                        "suggestions": ["可保存"],
                    },
                ],
                "revision_history": [
                    {
                        "condition_node_id": "gate",
                        "condition_node_label": "质量门",
                        "draft_attempt": 1,
                        "content_checksum": "draft-one",
                        "quality_gate_status": "failed",
                        "quality_summary": {"issues_count": 1, "suggestions_count": 1},
                        "retry_count": 0,
                        "requested_at": "2026-05-10T10:01:00",
                    }
                ],
                "chapter_draft_attempt": 2,
                "chapter_draft_checksum": "draft-two",
                "chapter_saved_payload": {
                    "chapter_id": "chapter-quality",
                    "status": "saved",
                    "quality_gate_passed": True,
                    "quality_gate_status": "passed",
                    "quality_gate_score": 8.2,
                    "quality_gate_attempts": 2,
                    "revision_attempts": 1,
                },
            },
        )

        markdown = WorkflowReplayExportService().export_markdown(execution, workflow)
        quality_section = markdown.split("## 质量门与修订审计", 1)[1].split("## 保存章节", 1)[0]
        saved_section = markdown.split("## 保存章节", 1)[1].split("## 节点复盘", 1)[0]

        assert "## 质量门与修订审计" in markdown
        assert markdown.index("## 质量门与修订审计") < markdown.index("## 节点复盘")
        assert "- **最终状态**: `passed`" in quality_section
        assert "- **最终分数**: 8.2" in quality_section
        assert "draft-one" in quality_section
        assert "draft-two" in quality_section
        assert "动机断裂" in quality_section
        assert "### 修订请求记录" in quality_section
        assert "- **质量门状态**: `passed`" in saved_section
        assert "- **质量分数**: 8.2" in saved_section
        assert "SENTINEL_FULL_CHAPTER_CONTENT_SHOULD_NOT_RENDER" not in markdown
        assert "hidden" not in markdown

    def test_replay_export_includes_saved_chapter_provenance(self):
        workflow = WorkflowDefinition(
            id="wf-saved-provenance",
            project_id="test-project",
            name="保存章节溯源",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始"),
                WorkflowNode(id="writer", node_type=NodeType.AGENT, agent_type="writer", label="写作"),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束"),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="writer"),
                WorkflowEdge(id="e2", source="writer", target="end"),
            ],
        )
        execution = WorkflowExecution(
            id="exec-saved-provenance",
            workflow_id=workflow.id,
            project_id="test-project",
            status=WorkflowStatus.COMPLETED,
            trace_id="trace-saved-provenance",
            node_states={
                "writer": NodeExecutionState(
                    node_id="writer",
                    status=NodeStatus.COMPLETED,
                    input_data={"chapter_outline": {"id": "outline-1"}},
                    output_data={"chapter_content": "正文不应出现在保存章节段落", "word_count": 12},
                )
            },
            context={
                "chapter_saved_payload": {
                    "chapter_id": "chapter-1",
                    "chapter_title": "第一章",
                    "chapter_number": 1,
                    "chapter_outline_id": "outline-1",
                    "status": "saved",
                    "saved_at": "2026-05-10T10:00:00",
                    "content_path": "projects/test/chapters/chapter-1.md",
                    "content_size_bytes": 120,
                    "content_checksum": "abc123",
                    "content_chars": 12,
                    "word_count": 12,
                },
                "chapter_writer_provenance": {
                    "source_node_id": "writer",
                    "source_node_label": "写作",
                    "source_agent_type": "writer",
                    "resolved_agent_type": "writer",
                    "resolved_scenario": "workflow_chapter_generation",
                    "source_trace_id": "trace-saved-provenance",
                    "source_output_contract_id": "writer.workflow_output",
                    "source_output_schema_name": "writer.workflow_output",
                    "source_output_schema_version": "1.0.0",
                    "writer_output_content_chars": 12,
                    "writer_output_word_count": 12,
                    "writer_prompt_trace": {"prompt_ids": ["function_writing"]},
                },
            },
        )

        markdown = WorkflowReplayExportService().export_markdown(execution, workflow)
        saved_section = markdown.split("## 保存章节", 1)[1].split("## 节点复盘", 1)[0]

        assert "## 保存章节" in markdown
        assert markdown.index("## 保存章节") < markdown.index("## 节点复盘")
        assert "- **章节 ID**: `chapter-1`" in saved_section
        assert "- **存储路径**: `projects/test/chapters/chapter-1.md`" in saved_section
        assert "- **内容校验和**: `abc123`" in saved_section
        assert "- **来源节点**: `writer` / 写作" in saved_section
        assert "- **Trace ID**: `trace-saved-provenance`" in saved_section
        assert "- **输出契约**: `writer.workflow_output`" in saved_section
        assert '"prompt_ids": [' in saved_section
        assert "function_writing" in saved_section
        assert "正文不应出现在保存章节段落" not in saved_section

    @pytest.mark.asyncio
    async def test_validate_failed_node_remediation_is_preview_only(self):
        workflow = self._remediation_workflow()
        execution = self._failed_remediation_execution(workflow.id)
        self.engine._executions[execution.id] = execution
        saved_workflows = []
        saved_executions = []

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        async def _fake_save_workflow(workflow_arg, db=None):
            saved_workflows.append(workflow_arg)

        async def _fake_save_execution(execution_arg, db=None):
            saved_executions.append(execution_arg)

        self.engine.get_workflow = _fake_get_workflow
        self.engine._save_workflow_to_db = _fake_save_workflow
        self.engine._save_execution_to_db = _fake_save_execution

        result = await self.engine.validate_failed_node_remediation(
            execution.id,
            db=object(),
            patch={"agent_type": "plot_outline", "scenario": "workflow_output"},
        )

        target_node = next(node for node in workflow.nodes if node.id == "plotter_failure")
        assert result["valid"] is True
        assert result["diff"]["after"] == {"agent_type": "plot_outline", "scenario": "workflow_output"}
        assert target_node.agent_type == "smoke_contract_failure"
        assert target_node.config["scenario"] == "broken"
        assert saved_workflows == []
        assert saved_executions == []

    @pytest.mark.asyncio
    async def test_validate_failed_node_remediation_rejects_active_task(self):
        workflow = self._remediation_workflow()
        execution = self._failed_remediation_execution(workflow.id)
        self.engine._executions[execution.id] = execution
        task = asyncio.create_task(asyncio.sleep(60))
        self.engine._running_tasks[execution.id] = task

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        self.engine.get_workflow = _fake_get_workflow
        try:
            with pytest.raises(ValueError) as exc_info:
                await self.engine.validate_failed_node_remediation(execution.id, patch={"agent_type": "plot_outline"})
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert "仍在运行" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_failed_node_remediation_rejects_non_agent_target(self):
        workflow = self._remediation_workflow(failed_node_type=NodeType.CONDITION)
        execution = self._failed_remediation_execution(workflow.id)
        self.engine._executions[execution.id] = execution

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        self.engine.get_workflow = _fake_get_workflow

        with pytest.raises(ValueError) as exc_info:
            await self.engine.validate_failed_node_remediation(execution.id, patch={"agent_type": "plot_outline"})

        assert "仅支持修复 Agent 节点" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_failed_node_remediation_rejects_empty_or_noop_patch(self):
        workflow = self._remediation_workflow()
        execution = self._failed_remediation_execution(workflow.id)
        self.engine._executions[execution.id] = execution

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        self.engine.get_workflow = _fake_get_workflow

        with pytest.raises(ValueError) as empty_exc:
            await self.engine.validate_failed_node_remediation(execution.id, patch={})
        with pytest.raises(ValueError) as noop_exc:
            await self.engine.validate_failed_node_remediation(
                execution.id,
                patch={"agent_type": "smoke_contract_failure", "scenario": "broken"},
            )

        assert "没有可应用" in str(empty_exc.value)
        assert "没有可应用" in str(noop_exc.value)

    @pytest.mark.asyncio
    async def test_validate_failed_node_remediation_rejects_explicit_missing_node(self):
        workflow = self._remediation_workflow()
        execution = self._failed_remediation_execution(workflow.id)
        self.engine._executions[execution.id] = execution

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        self.engine.get_workflow = _fake_get_workflow

        with pytest.raises(ValueError) as exc_info:
            await self.engine.validate_failed_node_remediation(
                execution.id,
                node_id="missing-node",
                patch={"agent_type": "plot_outline"},
            )

        assert "恢复节点不存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_failed_node_remediation_rejects_non_failed_execution(self):
        workflow = self._remediation_workflow()
        execution = self._failed_remediation_execution(workflow.id)
        execution.status = WorkflowStatus.RUNNING
        self.engine._executions[execution.id] = execution

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        self.engine.get_workflow = _fake_get_workflow

        with pytest.raises(ValueError) as exc_info:
            await self.engine.validate_failed_node_remediation(execution.id, patch={"agent_type": "plot_outline"})

        assert "失败状态" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_failed_node_remediation_rejects_protected_context_patch(self):
        workflow = self._remediation_workflow()
        execution = self._failed_remediation_execution(workflow.id)
        self.engine._executions[execution.id] = execution

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        self.engine.get_workflow = _fake_get_workflow

        with pytest.raises(ValueError) as exc_info:
            await self.engine.validate_failed_node_remediation(
                execution.id,
                patch={"agent_type": "plot_outline"},
                context_patch={"chapter_outline": "bad"},
            )

        assert "受保护字段" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_recover_failed_workflow_rejects_saved_handoff_context_patch(self):
        workflow = self._remediation_workflow()
        execution = self._failed_remediation_execution(workflow.id)
        self.engine._executions[execution.id] = execution

        async def _fake_get_workflow(workflow_id, db=None):
            return workflow

        self.engine.get_workflow = _fake_get_workflow

        with pytest.raises(ValueError) as exc_info:
            await self.engine.recover_failed_workflow(
                execution.id,
                context_patch={"chapter_saved_payload": {"chapter_id": "forged"}},
            )

        assert "受保护字段" in str(exc_info.value)
        assert "chapter_saved_payload" in str(exc_info.value)

        with pytest.raises(ValueError) as provenance_exc:
            await self.engine.recover_failed_workflow(
                execution.id,
                context_patch={"chapter_writer_provenance": {"source_node_id": "forged"}},
            )

        assert "受保护字段" in str(provenance_exc.value)
        assert "chapter_writer_provenance" in str(provenance_exc.value)

        for protected_key, forged_value in {
            "quality_gate": {"status": "passed"},
            "quality_gate_history": [{"passed": True}],
            "revision_history": [{"attempt": 1}],
            "chapter_draft_payload": {"draft_attempt": 99},
            "pending_chapter_save": False,
        }.items():
            with pytest.raises(ValueError) as quality_exc:
                await self.engine.recover_failed_workflow(
                    execution.id,
                    context_patch={protected_key: forged_value},
                )
            assert "受保护字段" in str(quality_exc.value)
            assert protected_key in str(quality_exc.value)

    @pytest.mark.asyncio
    async def test_recover_failed_workflow_rejects_non_failed_execution(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={},
        )
        self.engine._executions[execution.id] = execution

        with pytest.raises(ValueError) as exc_info:
            await self.engine.recover_failed_workflow(execution.id)

        assert "失败状态" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_recover_failed_workflow_rejects_active_task(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.FAILED,
            node_states={"writer": NodeExecutionState(node_id="writer", status=NodeStatus.FAILED)},
        )
        self.engine._executions[execution.id] = execution
        task = asyncio.create_task(asyncio.sleep(60))
        self.engine._running_tasks[execution.id] = task

        try:
            with pytest.raises(ValueError) as exc_info:
                await self.engine.recover_failed_workflow(execution.id)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert "仍在运行" in str(exc_info.value)
