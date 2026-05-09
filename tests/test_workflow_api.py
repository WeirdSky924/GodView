from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.api.routes.workflows as workflow_routes
from app.models.workflow_execution import WorkflowExecution, WorkflowStatus
from app.services.workflow_engine import ChapterReadinessBlockedError, WorkflowEngine, WorkflowOperationError


class _FakeWorkflowEngine:
    def __init__(self, *, control_result=True, blocked_payload=None, recovery_error=None, operation_error=None):
        self.control_result = control_result
        self.blocked_payload = blocked_payload
        self.recovery_error = recovery_error
        self.operation_error = operation_error
        self.calls = []

    def _serialize_for_json(self, obj):
        return WorkflowEngine()._serialize_for_json(obj)

    async def execute_workflow(self, workflow_id, project_id, initial_context, db, request_id=None, force_new=False):
        self.calls.append({
            "method": "execute_workflow",
            "workflow_id": workflow_id,
            "project_id": project_id,
            "initial_context": initial_context,
            "request_id": request_id,
            "force_new": force_new,
        })
        if self.blocked_payload is not None:
            raise ChapterReadinessBlockedError(self.blocked_payload)
        return "exec-1"

    async def get_execution_state(self, execution_id, db=None):
        self.calls.append({"method": "get_execution_state", "execution_id": execution_id})
        return WorkflowExecution(
            id=execution_id,
            workflow_id="wf-1",
            project_id="project-1",
            status=WorkflowStatus.RUNNING,
            node_states={},
            context={"world_id": "world-1"},
            trace_id="trace-1",
            request_id="request-1",
        )

    def build_execution_operation_summary(self, execution):
        return {
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "project_id": execution.project_id,
            "status": execution.status.value,
            "active_task": False,
            "terminal": False,
            "capabilities": {
                "pause": {"allowed": True, "label": "暂停", "reason": None},
                "resume": {"allowed": False, "label": "恢复", "reason": "仅暂停中的执行可恢复"},
                "cancel": {"allowed": True, "label": "取消", "reason": None},
                "recover": {"allowed": False, "label": "从失败节点重试", "reason": "仅失败状态可恢复"},
                "remediate": {"allowed": False, "label": "修复并恢复", "reason": "仅失败状态可修复"},
            },
            "node_summary": {"total": 0, "counts": {}, "failed_node_id": None, "failed_node_error": None, "failed_nodes": []},
            "lease": {"expired": False, "seconds_remaining": None, "cancel_requested": False},
            "recovery": {"count": 0, "latest": None, "resume_cursor": None},
            "remediation": {"count": 0, "latest": None},
            "stale": {"count": 0, "latest": None},
            "attention": [],
        }

    async def get_execution_operation_summary(self, execution_id, db=None):
        self.calls.append({"method": "get_execution_operation_summary", "execution_id": execution_id})
        execution = await self.get_execution_state(execution_id, db)
        return self.build_execution_operation_summary(execution)

    def _maybe_raise_operation_error(self, operation, execution_id):
        if self.operation_error == operation:
            raise WorkflowOperationError(
                f"{operation} blocked",
                code="workflow_operation_conflict",
                operation=operation,
                execution_id=execution_id,
                status="completed",
                payload={"allowed_statuses": ["running"]},
            )

    async def pause_workflow(self, execution_id, db=None):
        self.calls.append({"method": "pause_workflow", "execution_id": execution_id})
        self._maybe_raise_operation_error("pause", execution_id)
        return self.control_result

    async def resume_workflow(self, execution_id, db=None):
        self.calls.append({"method": "resume_workflow", "execution_id": execution_id})
        self._maybe_raise_operation_error("resume", execution_id)
        return self.control_result

    async def cancel_workflow(self, execution_id, db=None):
        self.calls.append({"method": "cancel_workflow", "execution_id": execution_id})
        self._maybe_raise_operation_error("cancel", execution_id)
        return self.control_result

    async def recover_failed_workflow(
        self,
        execution_id,
        db=None,
        *,
        mode="retry_failed",
        node_id=None,
        reason=None,
        context_patch=None,
        reset_downstream=True,
    ):
        self.calls.append({
            "method": "recover_failed_workflow",
            "execution_id": execution_id,
            "mode": mode,
            "node_id": node_id,
            "reason": reason,
            "context_patch": context_patch,
            "reset_downstream": reset_downstream,
        })
        self._maybe_raise_operation_error("recover", execution_id)
        if self.recovery_error:
            raise ValueError(self.recovery_error)
        return {
            "success": True,
            "message": "工作流已从失败节点恢复",
            "execution_id": execution_id,
            "status": "running",
            "recovered_node_id": node_id or "writer",
            "reset_node_ids": [node_id or "writer", "end"],
            "recovery_attempt": 1,
            "trace_id": "trace-1",
            "recovery_entry": {
                "attempt": 1,
                "mode": mode,
                "target_node_id": node_id or "writer",
                "reset_node_ids": [node_id or "writer", "end"],
                "reason": reason,
                "started_at": "2026-05-09T12:00:00",
                "previous_error": "writer failed",
                "previous_completed_at": "2026-05-09T11:59:00",
                "trace_id": "trace-1",
                "status_at_start": "failed",
            },
        }

    async def diagnose_failed_workflow_node(self, execution_id, db=None, *, node_id=None):
        self.calls.append({"method": "diagnose_failed_workflow_node", "execution_id": execution_id, "node_id": node_id})
        return {
            "execution_id": execution_id,
            "workflow_id": "wf-1",
            "failed_node_id": node_id or "writer",
            "failed_node_label": "写作",
            "category": "missing_agent",
            "severity": "blocking",
            "recoverable": True,
            "retry_without_fix_likely_to_fail": True,
            "remediable": True,
            "summary": "节点请求的 Agent 类型不可用：missing",
            "evidence": ["无法获取 Agent: missing"],
            "current_agent_type": "missing",
            "current_scenario": "broken",
            "suggested_actions": [{"type": "edit_agent_type", "label": "修改失败节点的 Agent 类型", "fields": ["agent_type"]}],
        }

    async def validate_failed_node_remediation(self, execution_id, db=None, *, node_id=None, patch=None, context_patch=None):
        self.calls.append({
            "method": "validate_failed_node_remediation",
            "execution_id": execution_id,
            "node_id": node_id,
            "patch": patch,
            "context_patch": context_patch,
        })
        self._maybe_raise_operation_error("remediate", execution_id)
        return {"valid": True, "execution_id": execution_id, "node_id": node_id or "writer", "diff": {"after": patch or {}}}

    async def remediate_failed_workflow_node(
        self,
        execution_id,
        db=None,
        *,
        node_id=None,
        patch=None,
        reason=None,
        context_patch=None,
        reset_downstream=True,
    ):
        self.calls.append({
            "method": "remediate_failed_workflow_node",
            "execution_id": execution_id,
            "node_id": node_id,
            "patch": patch,
            "reason": reason,
            "context_patch": context_patch,
            "reset_downstream": reset_downstream,
        })
        self._maybe_raise_operation_error("remediate", execution_id)
        return {
            "success": True,
            "message": "失败节点已修复并开始恢复",
            "diagnosis": await self.diagnose_failed_workflow_node(execution_id, db, node_id=node_id),
            "remediation_entry": {"node_id": node_id or "writer", "reason": reason, "diff": {"after": patch or {}}},
            "recovery": await self.recover_failed_workflow(
                execution_id,
                db,
                mode="retry_from_node",
                node_id=node_id or "writer",
                reason=reason,
                context_patch=context_patch,
                reset_downstream=reset_downstream,
            ),
        }


class _FakeWorkflowListDB:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def execute_query(self, query, params=None):
        self.calls.append({"query": query, "params": params or {}})
        return self.rows


class _FakeWorkflowEventDB:
    async def get_workflow_execution_events_since(self, execution_id, sequence_no=0, limit=200):
        return [
            {
                "event_type": "node_completed",
                "event_data": {"node_id": "start", "large_output": "not exposed"},
                "sequence_no": 1,
                "created_at": datetime(2026, 5, 9, 11, 0, 0),
            },
            {
                "event_type": "node_failed",
                "event_data": {"node_id": "writer", "error": "boom", "output": {"secret": "hidden"}},
                "sequence_no": 2,
                "created_at": datetime(2026, 5, 9, 11, 1, 0),
            },
            {
                "event_type": "workflow_recovery_started",
                "event_data": {
                    "recovered_node_id": "writer",
                    "reset_node_ids": ["writer", "end"],
                    "recovery_entry": {"attempt": 1, "target_node_id": "writer", "previous_error": "boom", "prompt": "hidden"},
                },
                "sequence_no": 3,
                "created_at": datetime(2026, 5, 9, 11, 2, 0),
            },
        ]


@pytest.fixture(autouse=True)
def route_dependencies(monkeypatch):
    async def noop_setup(project_id):
        return None

    monkeypatch.setattr(workflow_routes, "get_db", lambda: None)
    monkeypatch.setattr(workflow_routes, "_setup_agent_provider_for_execution", noop_setup)
    yield
    workflow_routes.set_workflow_engine(None)


@pytest.mark.asyncio
async def test_execute_workflow_returns_structured_readiness_409():
    outline_id = uuid4()
    requirement_id = uuid4()
    blocked_payload = {
        "code": "chapter_resource_readiness_blocked",
        "readiness_status": "blocked",
        "chapter_num": 3,
        "chapter_outline_id": outline_id,
        "checked_at": datetime(2026, 5, 9, 12, 0, 0),
        "blocking_requirements": [
            {
                "id": requirement_id,
                "requirement_type": "character",
                "severity": "blocking",
                "status": "pending",
            }
        ],
    }
    engine = _FakeWorkflowEngine(blocked_payload=blocked_payload)
    workflow_routes.set_workflow_engine(engine)

    with pytest.raises(HTTPException) as exc_info:
        await workflow_routes.execute_workflow(
            "wf-1",
            project_id="project-1",
            body={"initial_context": {"chapter_num": 3}, "request_id": "request-1"},
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "chapter_resource_readiness_blocked"
    assert exc_info.value.detail["chapter_outline_id"] == str(outline_id)
    assert exc_info.value.detail["checked_at"] == "2026-05-09T12:00:00"
    assert exc_info.value.detail["blocking_requirements"][0]["id"] == str(requirement_id)
    assert engine.calls[0]["request_id"] == "request-1"


@pytest.mark.asyncio
async def test_get_execution_includes_operation_summary():
    engine = _FakeWorkflowEngine(control_result=True)
    workflow_routes.set_workflow_engine(engine)

    result = await workflow_routes.get_execution("exec-1")

    assert result["id"] == "exec-1"
    assert result["operation_summary"]["execution_id"] == "exec-1"
    assert result["operation_summary"]["capabilities"]["pause"]["allowed"] is True


@pytest.mark.asyncio
async def test_get_execution_operation_summary_route_returns_summary():
    engine = _FakeWorkflowEngine(control_result=True)
    workflow_routes.set_workflow_engine(engine)

    result = await workflow_routes.get_execution_operation_summary("exec-1")

    assert result["success"] is True
    assert result["summary"]["execution_id"] == "exec-1"
    assert any(call["method"] == "get_execution_operation_summary" for call in engine.calls)


@pytest.mark.asyncio
async def test_operation_events_route_returns_sanitized_timeline(monkeypatch):
    engine = _FakeWorkflowEngine(control_result=True)
    workflow_routes.set_workflow_engine(engine)
    monkeypatch.setattr(workflow_routes, "get_db", lambda: _FakeWorkflowEventDB())

    result = await workflow_routes.get_execution_operation_events("exec-1")

    assert result["success"] is True
    assert [event["event_type"] for event in result["events"]] == ["node_failed", "workflow_recovery_started"]
    assert result["events"][0]["summary"] == "节点失败：writer"
    assert result["events"][0]["severity"] == "error"
    assert "output" not in result["events"][0]["data"]
    assert "prompt" not in result["events"][1]["data"]["recovery_entry"]
    assert result["events"][1]["data"]["recovery_entry"]["target_node_id"] == "writer"


@pytest.mark.asyncio
async def test_pause_resume_cancel_routes_return_success():
    for route_func, expected_method in [
        (workflow_routes.pause_execution, "pause_workflow"),
        (workflow_routes.resume_execution, "resume_workflow"),
        (workflow_routes.cancel_execution, "cancel_workflow"),
    ]:
        engine = _FakeWorkflowEngine(control_result=True)
        workflow_routes.set_workflow_engine(engine)

        result = await route_func("exec-1")

        assert result["success"] is True
        assert result["execution"]["id"] == "exec-1"
        assert any(call["method"] == expected_method for call in engine.calls)


@pytest.mark.asyncio
async def test_control_route_returns_structured_conflict_for_operation_error():
    engine = _FakeWorkflowEngine(operation_error="pause")
    workflow_routes.set_workflow_engine(engine)

    with pytest.raises(HTTPException) as exc_info:
        await workflow_routes.pause_execution("exec-1")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "workflow_operation_conflict"
    assert exc_info.value.detail["operation"] == "pause"
    assert exc_info.value.detail["status"] == "completed"
    assert exc_info.value.detail["allowed_statuses"] == ["running"]


@pytest.mark.asyncio
async def test_recover_route_returns_structured_conflict_for_operation_error():
    engine = _FakeWorkflowEngine(operation_error="recover")
    workflow_routes.set_workflow_engine(engine)

    with pytest.raises(HTTPException) as exc_info:
        await workflow_routes.recover_execution("exec-1", workflow_routes.WorkflowRecoveryRequest())

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["operation"] == "recover"
    assert exc_info.value.detail["code"] == "workflow_operation_conflict"


@pytest.mark.asyncio
async def test_recover_execution_route_passes_request_to_engine():
    engine = _FakeWorkflowEngine(control_result=True)
    workflow_routes.set_workflow_engine(engine)

    result = await workflow_routes.recover_execution(
        "exec-1",
        workflow_routes.WorkflowRecoveryRequest(
            mode="retry_from_node",
            node_id="writer",
            reason="test_retry",
            context_patch={"manual_note": "fixed config"},
            reset_downstream=False,
        ),
    )

    assert result["success"] is True
    assert result["status"] == "running"
    assert result["recovery_entry"]["target_node_id"] == "writer"
    assert result["recovery_entry"]["status_at_start"] == "failed"
    recover_call = next(call for call in engine.calls if call["method"] == "recover_failed_workflow")
    assert recover_call == {
        "method": "recover_failed_workflow",
        "execution_id": "exec-1",
        "mode": "retry_from_node",
        "node_id": "writer",
        "reason": "test_retry",
        "context_patch": {"manual_note": "fixed config"},
        "reset_downstream": False,
    }
    assert any(call["method"] == "get_execution_state" for call in engine.calls)


@pytest.mark.asyncio
async def test_failed_node_diagnosis_route_passes_node_id_to_engine():
    engine = _FakeWorkflowEngine()
    workflow_routes.set_workflow_engine(engine)

    result = await workflow_routes.diagnose_failed_execution_node("exec-1", node_id="writer")

    assert result["category"] == "missing_agent"
    assert result["failed_node_id"] == "writer"
    assert {"method": "diagnose_failed_workflow_node", "execution_id": "exec-1", "node_id": "writer"} in engine.calls


@pytest.mark.asyncio
async def test_validate_remediation_route_passes_patch_to_engine():
    engine = _FakeWorkflowEngine()
    workflow_routes.set_workflow_engine(engine)

    result = await workflow_routes.validate_failed_execution_remediation(
        "exec-1",
        workflow_routes.WorkflowRemediationRequest(
            node_id="writer",
            reason="fix",
            patch=workflow_routes.WorkflowNodeRemediationPatch(agent_type="plot_outline", scenario="workflow_output"),
            context_patch={"manual_note": "fixed"},
            reset_downstream=False,
        ),
    )

    assert result["valid"] is True
    call = next(call for call in engine.calls if call["method"] == "validate_failed_node_remediation")
    assert call["node_id"] == "writer"
    assert call["patch"] == {"agent_type": "plot_outline", "scenario": "workflow_output"}
    assert call["context_patch"] == {"manual_note": "fixed"}


@pytest.mark.asyncio
async def test_remediate_and_recover_route_passes_request_to_engine():
    engine = _FakeWorkflowEngine()
    workflow_routes.set_workflow_engine(engine)

    result = await workflow_routes.remediate_and_recover_execution(
        "exec-1",
        workflow_routes.WorkflowRemediationRequest(
            node_id="writer",
            reason="fix_missing_agent",
            patch=workflow_routes.WorkflowNodeRemediationPatch(agent_type="plot_outline"),
            context_patch={"manual_note": "fixed"},
            reset_downstream=False,
        ),
    )

    assert result["success"] is True
    assert result["recovery"]["status"] == "running"
    call = next(call for call in engine.calls if call["method"] == "remediate_failed_workflow_node")
    assert call["node_id"] == "writer"
    assert call["patch"] == {"agent_type": "plot_outline"}
    assert call["reason"] == "fix_missing_agent"
    assert call["context_patch"] == {"manual_note": "fixed"}
    assert call["reset_downstream"] is False


@pytest.mark.asyncio
async def test_recover_execution_route_returns_400_for_engine_value_error():
    engine = _FakeWorkflowEngine(recovery_error="只有失败状态的工作流执行可以恢复")
    workflow_routes.set_workflow_engine(engine)

    with pytest.raises(HTTPException) as exc_info:
        await workflow_routes.recover_execution("exec-1", workflow_routes.WorkflowRecoveryRequest())

    assert exc_info.value.status_code == 400
    assert "失败状态" in exc_info.value.detail


@pytest.mark.asyncio
async def test_list_executions_returns_compact_recovery_summary(monkeypatch):
    recovery_entry = {
        "attempt": 2,
        "mode": "retry_failed",
        "target_node_id": "writer",
        "reset_node_ids": ["writer", "end"],
        "reason": "manual retry",
        "started_at": "2026-05-09T12:00:00",
        "previous_error": "writer failed",
    }
    db = _FakeWorkflowListDB([
        {
            "id": "exec-1",
            "workflow_id": "wf-1",
            "project_id": "project-1",
            "status": "failed",
            "current_node": "writer",
            "started_at": datetime(2026, 5, 9, 11, 0, 0),
            "completed_at": datetime(2026, 5, 9, 11, 5, 0),
            "total_duration_ms": 300000,
            "trace_id": "trace-1",
            "error": "writer failed",
            "node_states": {
                "start": {"status": "completed"},
                "writer": {"status": "failed"},
                "end": {"status": "pending"},
            },
            "context": {"recovery_history": [{"attempt": 1}, recovery_entry]},
            "resume_cursor": {"recovery_attempt": 2, "recovered_node_id": "writer"},
        }
    ])
    monkeypatch.setattr(workflow_routes, "get_db", lambda: db)

    result = await workflow_routes.list_executions(
        project_id="project-1",
        status="failed",
        workflow_id="wf-1",
    )

    assert result == [
        {
            "id": "exec-1",
            "workflow_id": "wf-1",
            "project_id": "project-1",
            "status": "failed",
            "current_node": "writer",
            "started_at": "2026-05-09T11:00:00",
            "completed_at": "2026-05-09T11:05:00",
            "total_duration_ms": 300000,
            "trace_id": "trace-1",
            "error": "writer failed",
            "node_count": 3,
            "completed_node_count": 1,
            "failed_node_id": "writer",
            "recovery_count": 2,
            "latest_recovery": recovery_entry,
            "resume_cursor": {"recovery_attempt": 2, "recovered_node_id": "writer"},
        }
    ]
    assert "workflow_id = :workflow_id" in db.calls[0]["query"]
    assert db.calls[0]["params"]["workflow_id"] == "wf-1"


@pytest.mark.asyncio
async def test_list_executions_tolerates_missing_recovery_history(monkeypatch):
    db = _FakeWorkflowListDB([
        {
            "id": "exec-1",
            "workflow_id": "wf-1",
            "project_id": "project-1",
            "status": "completed",
            "current_node": None,
            "started_at": None,
            "completed_at": None,
            "total_duration_ms": None,
            "trace_id": None,
            "error": None,
            "node_states": '{"start": {"status": "completed"}}',
            "context": '{"recovery_history": "bad"}',
            "resume_cursor": "not-json",
        }
    ])
    monkeypatch.setattr(workflow_routes, "get_db", lambda: db)

    result = await workflow_routes.list_executions(project_id="project-1")

    assert result[0]["node_count"] == 1
    assert result[0]["completed_node_count"] == 1
    assert result[0]["failed_node_id"] is None
    assert result[0]["recovery_count"] == 0
    assert result[0]["latest_recovery"] is None
    assert result[0]["resume_cursor"] is None


@pytest.mark.asyncio
async def test_pause_route_returns_400_when_engine_rejects_transition():
    engine = _FakeWorkflowEngine(control_result=False)
    workflow_routes.set_workflow_engine(engine)

    with pytest.raises(HTTPException) as exc_info:
        await workflow_routes.pause_execution("exec-1")

    assert exc_info.value.status_code == 400
    assert "无法暂停工作流" in exc_info.value.detail
