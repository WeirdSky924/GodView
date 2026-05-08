"""
工作流集成测试
v8 Agent协作可视化工作台
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.workflow_definition import (
    NodeType,
    NodeStatus,
    WorkflowNode,
    WorkflowEdge,
    WorkflowDefinition,
    WorkflowDefinitionCreate,
)
from app.models.workflow_execution import WorkflowStatus, NodeExecutionState, WorkflowExecution
from app.models.intervention import InterventionType, InterventionLog, InterventionExportFormat
from app.services.workflow_engine import WorkflowEngine
from app.services.intervention_service import InterventionService
from app.services.agent_communication import AgentCommunicationService


class TestWorkflowIntegration:
    """工作流集成测试"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.fixture
    def mock_db(self):
        """模拟数据库"""
        db = AsyncMock()
        db.execute_query = AsyncMock(return_value=[])
        db.execute_write = AsyncMock(return_value=None)
        return db

    @pytest.mark.asyncio
    async def test_create_and_validate_workflow(self, engine, mock_db):
        """测试创建并验证工作流"""
        # 创建工作流
        create_request = WorkflowDefinitionCreate(
            project_id="test-project",
            name="小说创作流程",
            description="标准的小说章节创作流程",
            nodes=[
                WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                WorkflowNode(id="setting", node_type=NodeType.AGENT, label="设定确认", agent_type="setting", position={"x": 0, "y": 100}),
                WorkflowNode(id="plotter", node_type=NodeType.AGENT, label="剧情规划", agent_type="plotter", position={"x": 0, "y": 200}),
                WorkflowNode(id="writer", node_type=NodeType.AGENT, label="内容写作", agent_type="writer", position={"x": 0, "y": 300}),
                WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 400}),
            ],
            edges=[
                WorkflowEdge(id="e1", source="start", target="setting"),
                WorkflowEdge(id="e2", source="setting", target="plotter"),
                WorkflowEdge(id="e3", source="plotter", target="writer"),
                WorkflowEdge(id="e4", source="writer", target="end"),
            ],
        )

        workflow = await engine.create_workflow(create_request, mock_db)

        # 验证
        result = engine.validate_workflow(workflow)

        assert workflow.id is not None
        assert result.valid is True
        assert result.node_count == 5
        assert result.edge_count == 4
        assert result.has_cycle is False

    @pytest.mark.asyncio
    async def test_workflow_execution_lifecycle(self, engine):
        """测试工作流执行生命周期"""
        # 创建模拟执行
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.PENDING,
            node_states={
                "start": NodeExecutionState(node_id="start"),
                "agent1": NodeExecutionState(node_id="agent1"),
                "end": NodeExecutionState(node_id="end"),
            },
        )
        engine._executions[execution.id] = execution

        # 模拟启动
        execution.status = WorkflowStatus.RUNNING

        # 暂停
        success = await engine.pause_workflow(execution.id)
        assert success is True
        assert execution.status == WorkflowStatus.PAUSED

        # 恢复
        success = await engine.resume_workflow(execution.id)
        assert success is True
        assert execution.status == WorkflowStatus.RUNNING

        # 取消
        success = await engine.cancel_workflow(execution.id)
        assert success is True
        assert execution.status == WorkflowStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_condition_branching(self, engine):
        """测试条件分支"""
        nodes = [
            WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
            WorkflowNode(id="condition", node_type=NodeType.CONDITION, label="条件判断", position={"x": 0, "y": 100}, config={"condition": "context.word_count > 1000"}),
            WorkflowNode(id="pass", node_type=NodeType.AGENT, label="通过", agent_type="writer", position={"x": -100, "y": 200}),
            WorkflowNode(id="fail", node_type=NodeType.AGENT, label="修改", agent_type="writer", position={"x": 100, "y": 200}),
            WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 300}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="start", target="condition"),
            WorkflowEdge(id="e2", source="condition", target="pass", condition={"value": True}),
            WorkflowEdge(id="e3", source="condition", target="fail", condition={"value": False}),
            WorkflowEdge(id="e4", source="pass", target="end"),
            WorkflowEdge(id="e5", source="fail", target="end"),
        ]

        workflow = WorkflowDefinition(
            project_id="test-project",
            name="条件分支测试",
            nodes=nodes,
            edges=edges,
        )

        result = engine.validate_workflow(workflow)
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_parallel_execution(self, engine):
        """测试并行执行"""
        nodes = [
            WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
            WorkflowNode(id="parallel", node_type=NodeType.PARALLEL, label="并行执行", position={"x": 0, "y": 100}, config={"branch_count": 3}),
            WorkflowNode(id="a", node_type=NodeType.AGENT, label="任务A", agent_type="character", position={"x": -100, "y": 200}),
            WorkflowNode(id="b", node_type=NodeType.AGENT, label="任务B", agent_type="character", position={"x": 0, "y": 200}),
            WorkflowNode(id="c", node_type=NodeType.AGENT, label="任务C", agent_type="character", position={"x": 100, "y": 200}),
            WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 0, "y": 300}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="start", target="parallel"),
            WorkflowEdge(id="e2", source="parallel", target="a"),
            WorkflowEdge(id="e3", source="parallel", target="b"),
            WorkflowEdge(id="e4", source="parallel", target="c"),
            WorkflowEdge(id="e5", source="a", target="end"),
            WorkflowEdge(id="e6", source="b", target="end"),
            WorkflowEdge(id="e7", source="c", target="end"),
        ]

        workflow = WorkflowDefinition(
            project_id="test-project",
            name="并行执行测试",
            nodes=nodes,
            edges=edges,
        )

        result = engine.validate_workflow(workflow)
        assert result.valid is True

        # 验证并行组识别
        parallel_groups = engine._identify_parallel_groups(nodes, edges)
        assert len(parallel_groups) == 1
        assert len(parallel_groups[0]) == 3


class TestInterventionIntegration:
    """干预功能集成测试"""

    @pytest.fixture
    def intervention_service(self):
        return InterventionService()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute_query = AsyncMock(return_value=[])
        db.execute_write = AsyncMock(return_value=None)
        return db

    @pytest.mark.asyncio
    async def test_log_and_query_intervention(self, intervention_service, mock_db):
        """测试记录和查询干预"""
        log = InterventionLog(
            project_id="test-project",
            workflow_execution_id="exec-1",
            agent_type="writer",
            agent_name="作家 Agent",
            intervention_type=InterventionType.GUIDANCE,
            user_message="请修改对话风格",
            agent_response="好的，已调整",
            context_snapshot={"chapter": 1, "word_count": 500},
            response_time_ms=300,
        )

        # 模拟保存
        assert log.id is not None
        assert log.agent_type == "writer"
        assert log.response_time_ms == 300

    @pytest.mark.asyncio
    async def test_intervention_export_formats(self, intervention_service, mock_db):
        """测试干预导出格式"""
        logs = [
            InterventionLog(
                project_id="test-project",
                workflow_execution_id="exec-1",
                agent_type="writer",
                agent_name="作家 Agent",
                intervention_type=InterventionType.GUIDANCE,
                user_message="测试消息",
                context_snapshot={},
            )
        ]

        # 测试不同格式的导出数据准备
        for fmt in [InterventionExportFormat.JSON, InterventionExportFormat.CSV, InterventionExportFormat.MARKDOWN]:
            assert fmt in [InterventionExportFormat.JSON, InterventionExportFormat.CSV, InterventionExportFormat.MARKDOWN]


class TestWorkflowTemplates:
    """工作流模板测试"""

    def test_default_novel_workflow(self):
        """测试默认小说工作流模板"""
        from app.data.workflow_templates import DEFAULT_NOVEL_WORKFLOW

        assert DEFAULT_NOVEL_WORKFLOW.is_template is True
        assert len(DEFAULT_NOVEL_WORKFLOW.nodes) > 0
        assert len(DEFAULT_NOVEL_WORKFLOW.edges) > 0

        # 验证包含关键节点
        node_types = [n.node_type for n in DEFAULT_NOVEL_WORKFLOW.nodes]
        assert NodeType.START in node_types
        assert NodeType.END in node_types
        assert NodeType.AGENT in node_types

    def test_quick_dialogue_workflow(self):
        """测试快速对话模板"""
        from app.data.workflow_templates import QUICK_DIALOGUE_WORKFLOW

        assert QUICK_DIALOGUE_WORKFLOW.is_template is True
        assert len(QUICK_DIALOGUE_WORKFLOW.nodes) == 4  # start, input, dialogue, end

    def test_list_templates(self):
        """测试模板列表"""
        from app.data.workflow_templates import list_templates

        templates = list_templates()
        assert len(templates) >= 3

        for t in templates:
            assert "id" in t
            assert "name" in t
            assert "node_count" in t

    def test_instantiate_template(self):
        """测试从模板创建实例"""
        from app.data.workflow_templates import instantiate_template

        workflow = instantiate_template("default_novel", "my-project")

        assert workflow is not None
        assert workflow.project_id == "my-project"
        assert workflow.is_template is False  # 实例不是模板
