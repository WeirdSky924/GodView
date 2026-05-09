import asyncio
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
from app.services.workflow_engine import WorkflowEngine, WorkflowOperationError

from tests.workflow_test_fakes import FakeAgentResponse


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
        assert execution.context["remediation_history"][0]["reason"] == "fix_missing_agent"
        assert execution.context["remediation_history"][0]["diff"]["after"]["agent_type"] == "plot_outline"
        assert execution.context["remediation_history"][0]["diff"]["after"]["scenario"] == "workflow_output"
        assert any(event["event_type"] == "workflow_node_remediated" for event in broadcasts)
        assert any(event["event_type"] == "workflow_recovery_started" for event in broadcasts)
        assert saved_workflows and saved_workflows[0].nodes[1].agent_type == "plot_outline"
        assert [node.id for node in saved_workflows[0].nodes] == ["start", "plotter_failure", "end"]
        assert [(edge.source, edge.target) for edge in saved_workflows[0].edges] == [("start", "plotter_failure"), ("plotter_failure", "end")]
        assert started == [{"execution_id": execution.id, "workflow_id": workflow.id}]

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
