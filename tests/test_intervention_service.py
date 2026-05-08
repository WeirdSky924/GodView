"""
干预日志服务测试
v8 Agent协作可视化工作台
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.models.intervention import (
    InterventionType,
    InterventionLog,
    InterventionCreate,
    InterventionQuery,
    InterventionSummary,
    InterventionExportFormat,
)
from app.services.intervention_service import InterventionService


class TestInterventionService:
    """干预日志服务测试"""

    def setup_method(self):
        self.service = InterventionService()

    def test_intervention_log_creation(self):
        """测试干预日志创建"""
        log = InterventionLog(
            project_id="test-project",
            workflow_execution_id="exec-123",
            agent_type="writer",
            agent_name="作家 Agent",
            intervention_type=InterventionType.GUIDANCE,
            user_message="请修改这段对话",
            agent_response="好的，我来修改",
            context_snapshot={"chapter": 1},
            response_time_ms=500,
        )

        assert log.id is not None
        assert log.project_id == "test-project"
        assert log.agent_type == "writer"
        assert log.intervention_type == InterventionType.GUIDANCE
        assert log.response_time_ms == 500

    def test_intervention_query_filters(self):
        """测试干预查询过滤"""
        query = InterventionQuery(
            project_id="test-project",
            agent_type="writer",
            intervention_type=InterventionType.GUIDANCE,
            keyword="修改",
            limit=20,
            offset=0,
        )

        assert query.project_id == "test-project"
        assert query.agent_type == "writer"
        assert query.keyword == "修改"
        assert query.limit == 20

    def test_intervention_summary(self):
        """测试干预摘要"""
        summary = InterventionSummary(
            total_count=10,
            by_agent_type={"writer": 5, "plotter": 3, "character": 2},
            by_intervention_type={"message": 8, "command": 2},
            avg_response_time_ms=450,
            recent_interventions=[],
        )

        assert summary.total_count == 10
        assert summary.by_agent_type["writer"] == 5
        assert summary.avg_response_time_ms == 450


class TestInterventionExport:
    """干预日志导出测试"""

    def setup_method(self):
        self.service = InterventionService()

    def test_export_json_format(self):
        """测试JSON导出格式"""
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

        # 模拟导出
        export_data = [log.model_dump() for log in logs]
        assert len(export_data) == 1
        assert export_data[0]["agent_type"] == "writer"

    def test_export_csv_format(self):
        """测试CSV导出格式"""
        logs = [
            InterventionLog(
                project_id="test-project",
                workflow_execution_id="exec-1",
                agent_type="writer",
                agent_name="作家 Agent",
                intervention_type=InterventionType.GUIDANCE,
                user_message="测试消息1",
                context_snapshot={},
            ),
            InterventionLog(
                project_id="test-project",
                workflow_execution_id="exec-1",
                agent_type="plotter",
                agent_name="编剧 Agent",
                intervention_type=InterventionType.CORRECTION,
                user_message="测试消息2",
                context_snapshot={},
            )
        ]

        # 构建CSV行
        headers = ["id", "agent_type", "intervention_type", "user_message", "timestamp"]
        rows = []
        for log in logs:
            rows.append([
                log.id,
                log.agent_type,
                log.intervention_type.value,
                log.user_message,
                log.timestamp.isoformat() if log.timestamp else "",
            ])

        assert len(rows) == 2
        assert rows[0][1] == "writer"
        assert rows[1][1] == "plotter"


class TestInterventionCreate:
    """干预创建测试"""

    def test_intervention_create_validation(self):
        """测试干预创建验证"""
        # 有效创建
        create = InterventionCreate(
            project_id="test-project",
            workflow_execution_id="exec-1",
            agent_type="writer",
            message="请修改这段内容",
        )

        assert create.project_id == "test-project"
        assert create.agent_type == "writer"
        assert create.message == "请修改这段内容"

    def test_intervention_create_with_node(self):
        """测试带节点ID的干预创建"""
        create = InterventionCreate(
            project_id="test-project",
            workflow_execution_id="exec-1",
            node_id="node-123",
            agent_type="character",
            message="调整角色行为",
        )

        assert create.node_id == "node-123"
        assert create.agent_type == "character"
