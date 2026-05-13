"""
工作流 API 路由
v8 Agent协作可视化工作台
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings

from app.models.workflow_definition import (
    WorkflowDefinition,
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowValidationResult,
)
from app.models.workflow_execution import (
    WorkflowExecution,
    WorkflowExecutionCreate,
    WorkflowStatus,
)
from app.services.workflow_node_catalog import (
    resolve_disabled_agent_types,
    resolve_workflow_node_types_payload,
)
from app.services.workflow_engine import ChapterReadinessBlockedError, WorkflowOperationError
from app.services.workflow_replay_export_service import (
    get_workflow_replay_export_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 服务实例（由 app.py 初始化时设置）
_workflow_engine = None


def get_workflow_engine():
    """获取工作流引擎"""
    global _workflow_engine
    if _workflow_engine is None:
        from app.services.workflow_engine import get_workflow_engine
        _workflow_engine = get_workflow_engine()
    return _workflow_engine


def get_db():
    """获取数据库连接"""
    from app.api.app import postgres_db
    return postgres_db




def set_workflow_engine(engine):
    """设置工作流引擎实例"""
    global _workflow_engine
    _workflow_engine = engine


def _raise_workflow_operation_http_error(exc: WorkflowOperationError):
    raise HTTPException(status_code=exc.http_status, detail=exc.to_payload())


def _safe_event_data(raw_event_data: Any) -> Dict[str, Any]:
    if isinstance(raw_event_data, str):
        try:
            raw_event_data = json.loads(raw_event_data)
        except json.JSONDecodeError:
            raw_event_data = {"raw": raw_event_data[:500]}
    if not isinstance(raw_event_data, dict):
        return {}

    allowed_keys = {
        "status",
        "current_node",
        "node_id",
        "node_type",
        "label",
        "agent_type",
        "phase",
        "error",
        "retry_count",
        "duration_ms",
        "completed_at",
        "started_at",
        "total_duration_ms",
        "failed_node_id",
        "failed_node_error",
        "recovered_node_id",
        "reset_node_ids",
        "recovery_attempt",
        "recovery_entry",
        "remediation_entry",
        "stale_entry",
        "diagnosis_category",
        "previous_error",
        "trace_id",
        "operation_id",
        "request_id",
        "cancel_requested",
        "chapter_num",
        "chapter_number",
        "chapter_outline_id",
        "draft_attempt",
        "quality_passed",
        "passed",
        "score",
        "issues_count",
        "suggestions_count",
        "issues",
        "suggestions",
        "word_count_check",
        "revision_attempt",
        "attempt",
        "content_chars",
        "content_checksum",
        "source_node_id",
        "evaluator_node_id",
        "condition_node_id",
        "source_output_contract_id",
        "source_output_schema_name",
        "source_output_schema_version",
        "chapter_id",
        "workflow_id",
        "execution_id",
        "proposed_count",
        "applied_count",
        "pending_count",
        "error_count",
        "entity_type_counts",
        "state_change_ids",
        "prior_chapter_count",
        "confirmed_state_count",
    }
    safe = {key: raw_event_data.get(key) for key in allowed_keys if key in raw_event_data}
    if isinstance(safe.get("state_change_ids"), list):
        safe["state_change_ids"] = [str(item) for item in safe["state_change_ids"][:20] if item]
    if isinstance(safe.get("entity_type_counts"), dict):
        safe["entity_type_counts"] = {
            str(key)[:40]: int(value) if isinstance(value, (int, float)) else value
            for key, value in list(safe["entity_type_counts"].items())[:20]
        }
    if isinstance(safe.get("recovery_entry"), dict):
        entry = safe["recovery_entry"]
        safe["recovery_entry"] = {
            key: entry.get(key)
            for key in ["attempt", "mode", "target_node_id", "reset_node_ids", "reason", "started_at", "previous_error", "trace_id", "status_at_start"]
            if key in entry
        }
    if isinstance(safe.get("remediation_entry"), dict):
        entry = safe["remediation_entry"]
        safe["remediation_entry"] = {
            key: entry.get(key)
            for key in [
                "attempt",
                "node_id",
                "category",
                "diagnosis_category",
                "reason",
                "started_at",
                "applied_at",
                "previous_error",
                "diff",
            ]
            if key in entry
        }
    if isinstance(safe.get("stale_entry"), dict):
        entry = safe["stale_entry"]
        safe["stale_entry"] = {
            key: entry.get(key)
            for key in ["detected_at", "operation", "previous_status", "lease_expires_at", "last_heartbeat_at", "reason"]
            if key in entry
        }
    return safe


def _operation_event_summary(event_type: str, data: Dict[str, Any]) -> str:
    if event_type == "chapter_draft_ready":
        return f"Writer 草稿已进入质量门：第 {data.get('chapter_number') or data.get('chapter_num') or '-'} 章，草稿尝试 {data.get('draft_attempt') or '-'}"
    if event_type == "quality_gate_passed":
        return f"质量门通过：分数 {data.get('score') if data.get('score') is not None else '-'}，草稿尝试 {data.get('draft_attempt') or '-'}"
    if event_type == "quality_gate_failed":
        return f"质量门未通过：{data.get('issues_count') or 0} 个问题，{data.get('suggestions_count') or 0} 条建议"
    if event_type == "chapter_revision_requested":
        return f"已请求章节修订：第 {data.get('attempt') or data.get('revision_attempt') or '-'} 次修订"
    if event_type == "chapter_finalized":
        return f"章节通过质量门并已保存：第 {data.get('chapter_number') or data.get('chapter_num') or '-'} 章"
    if event_type == "chapter_state_writeback_proposed":
        return f"章节状态写回已提案：{data.get('proposed_count') or 0} 条，待确认 {data.get('pending_count') or 0} 条"
    if event_type == "chapter_state_writeback_applied":
        return f"章节状态写回已应用：{data.get('applied_count') or 0} 条"
    if event_type == "chapter_state_writeback_failed":
        return f"章节状态写回异常：{data.get('error_count') or 0} 个错误"
    if event_type == "chapter_state_handoff_loaded":
        return f"已加载前文状态交接：前文章节 {data.get('prior_chapter_count') or 0}，确认状态 {data.get('confirmed_state_count') or 0}"
    if event_type == "workflow_recovery_started":
        return f"从 {data.get('recovered_node_id') or data.get('current_node') or '-'} 开始恢复"
    if event_type == "workflow_node_remediated":
        entry = data.get("remediation_entry") if isinstance(data.get("remediation_entry"), dict) else {}
        return f"修复节点 {entry.get('node_id') or data.get('node_id') or '-'}"
    if event_type == "workflow_execution_stale":
        return "执行租约过期并被标记为失败"
    if event_type == "node_failed":
        return f"节点失败：{data.get('node_id') or '-'}"
    if event_type == "workflow_failed":
        return "工作流失败"
    if event_type == "workflow_paused":
        return "工作流已暂停"
    if event_type == "workflow_resumed":
        return "工作流已恢复运行"
    if event_type == "workflow_cancelled":
        return "工作流已取消"
    if event_type == "workflow_completed":
        return "工作流已完成"
    if event_type == "workflow_started":
        return "工作流已启动"
    return event_type


_OPERATION_TIMELINE_EVENT_TYPES = {
    "workflow_started",
    "workflow_completed",
    "workflow_failed",
    "workflow_paused",
    "workflow_resumed",
    "workflow_cancelled",
    "workflow_recovery_started",
    "workflow_node_remediated",
    "workflow_execution_stale",
    "node_failed",
    "chapter_draft_ready",
    "quality_gate_passed",
    "quality_gate_failed",
    "chapter_revision_requested",
    "chapter_finalized",
    "chapter_state_writeback_proposed",
    "chapter_state_writeback_applied",
    "chapter_state_writeback_failed",
    "chapter_state_handoff_loaded",
}


class WorkflowExecuteRequest(BaseModel):
    """工作流执行请求，兼容旧版裸 initial_context body。"""

    initial_context: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None
    force_new: bool = False


class WorkflowRecoveryRequest(BaseModel):
    """失败工作流恢复请求。"""

    mode: str = "retry_failed"
    node_id: Optional[str] = None
    reason: Optional[str] = None
    context_patch: Dict[str, Any] = Field(default_factory=dict)
    reset_downstream: bool = True


class WorkflowNodeRemediationPatch(BaseModel):
    """失败节点安全修复补丁。"""

    agent_type: Optional[str] = None
    scenario: Optional[str] = None


class WorkflowRemediationRequest(BaseModel):
    """失败节点修复并恢复请求。"""

    node_id: Optional[str] = None
    reason: Optional[str] = None
    patch: WorkflowNodeRemediationPatch = Field(default_factory=WorkflowNodeRemediationPatch)
    context_patch: Dict[str, Any] = Field(default_factory=dict)
    reset_downstream: bool = True


class WorkflowStaleResolutionRequest(BaseModel):
    """陈旧执行治理请求。"""

    action: str = "mark_failed"
    reason: Optional[str] = None


class WorkflowRuntimeFixtureRequest(BaseModel):
    """开发/测试用受控运行时夹具请求。"""

    project_id: str
    fixture_type: str = "stale_running"
    label: Optional[str] = None


class WorkflowRuntimeFixtureCleanupRequest(BaseModel):
    """开发/测试用受控运行时夹具清理请求。"""

    execution_id: str
    workflow_id: str
    cleanup_token: str


def _format_sse(event_name: str, payload: Dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


from fastapi import Response

@router.get("/node-types", response_model=Dict[str, Any])
async def get_node_types(
    project_id: Optional[str] = Query(None, description="项目ID（用于获取角色Agent）"),
):
    """
    获取工作流节点类型列表

    返回所有可用的节点类型，包括：
    - 系统 Agent 节点（根据模板启用状态过滤）
    - 角色 Agent 节点（如果提供了 project_id）
    - 交互节点
    - 控制节点
    """
    db = get_db()
    disabled_agent_types = await resolve_disabled_agent_types(project_id, db)
    if disabled_agent_types:
        logger.info(f"已禁用的 Agent 类型: {disabled_agent_types}")

    result = await resolve_workflow_node_types_payload(project_id, db, disabled_agent_types)
    logger.info(f"返回节点类型: {len(result['agent_nodes'])} 个 Agent 节点")
    return result


@router.get("", response_model=List[Dict[str, Any]])
async def list_workflows(
    project_id: str = Query(..., description="项目ID"),
    include_templates: bool = Query(default=False, description="是否包含模板"),
):
    """
    获取工作流列表

    Args:
        project_id: 项目ID
        include_templates: 是否包含预设模板

    Returns:
        List: 工作流定义列表
    """
    engine = get_workflow_engine()
    db = get_db()

    try:
        workflows = await engine.list_workflows(project_id, include_templates, db)
        return [wf.model_dump() for wf in workflows]
    except Exception as e:
        logger.error(f"获取工作流列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Dict[str, Any])
async def create_workflow(request: WorkflowDefinitionCreate):
    """
    创建工作流

    Args:
        request: 创建请求

    Returns:
        Dict: 创建结果
    """
    engine = get_workflow_engine()
    db = get_db()

    # 调试日志：输出接收到的节点类型
    logger.info(f"创建工作流请求: name={request.name}, nodes={len(request.nodes)}")
    for node in request.nodes:
        logger.info(f"  节点: id={node.id}, node_type={node.node_type}, label={node.label}, agent_type={node.agent_type}")

    try:
        workflow = await engine.create_workflow(request, db)
        return {
            "success": True,
            "message": "工作流创建成功",
            "workflow": workflow.model_dump(),
        }
    except Exception as e:
        logger.error(f"创建工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/active", response_model=Dict[str, Any])
async def get_active_execution(
    project_id: str = Query(..., description="项目ID"),
    workflow_id: Optional[str] = Query(None, description="工作流ID"),
    director_session_id: Optional[str] = Query(None, description="Director 界面会话ID"),
):
    """获取项目/工作流当前活跃执行，用于前端刷新恢复。"""
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="数据库未连接")
    row = await db.get_active_workflow_execution(
        project_id=project_id,
        workflow_id=workflow_id,
        director_session_id=director_session_id,
    )
    if not row:
        return {"success": True, "execution": None}
    return {"success": True, "execution": row}


@router.get("/executions/{execution_id}", response_model=Dict[str, Any])
async def get_execution(execution_id: str):
    """
    获取工作流执行状态

    Args:
        execution_id: 执行ID

    Returns:
        Dict: 执行状态
    """
    engine = get_workflow_engine()
    db = get_db()

    execution = await engine.get_execution_state(execution_id, db)
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    execution_payload = engine._serialize_for_json(execution)
    execution_payload["operation_summary"] = engine.build_execution_operation_summary(execution)
    return execution_payload


@router.get("/executions/{execution_id}/operation-summary", response_model=Dict[str, Any])
async def get_execution_operation_summary(execution_id: str):
    """获取执行生命周期摘要和后端判定的操作能力。"""
    engine = get_workflow_engine()
    db = get_db()
    summary = await engine.get_execution_operation_summary(execution_id, db)
    if not summary:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return {"success": True, "summary": summary}


@router.post("/runtime-fixtures", response_model=Dict[str, Any])
async def create_runtime_fixture(request: WorkflowRuntimeFixtureRequest):
    """创建 DEBUG-only 运行时夹具，用于隔离验证工作流治理链路。"""
    if not settings.debug:
        raise HTTPException(status_code=403, detail="运行时夹具只能在 DEBUG 模式下创建")
    engine = get_workflow_engine()
    db = get_db()
    try:
        return await engine.create_runtime_fixture(
            request.project_id,
            db,
            fixture_type=request.fixture_type,
            label=request.label,
        )
    except WorkflowOperationError as exc:
        _raise_workflow_operation_http_error(exc)


@router.post("/runtime-fixtures/cleanup", response_model=Dict[str, Any])
async def cleanup_runtime_fixture(request: WorkflowRuntimeFixtureCleanupRequest):
    """按 cleanup token 清理 DEBUG-only 运行时夹具，拒绝清理真实数据。"""
    if not settings.debug:
        raise HTTPException(status_code=403, detail="运行时夹具只能在 DEBUG 模式下清理")
    engine = get_workflow_engine()
    db = get_db()
    try:
        return await engine.cleanup_runtime_fixture(
            request.execution_id,
            request.workflow_id,
            request.cleanup_token,
            db,
        )
    except WorkflowOperationError as exc:
        _raise_workflow_operation_http_error(exc)


@router.get("/executions/{execution_id}/stale-inspection", response_model=Dict[str, Any])
async def inspect_stale_execution(execution_id: str):
    """检查执行是否疑似陈旧，仅读取状态，不改写执行。"""
    engine = get_workflow_engine()
    db = get_db()
    inspection = await engine.inspect_execution_staleness_state(execution_id, db)
    if not inspection:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return {"success": True, "inspection": inspection}


@router.post("/executions/{execution_id}/resolve-stale", response_model=Dict[str, Any])
async def resolve_stale_execution(execution_id: str, request: WorkflowStaleResolutionRequest):
    """安全治理疑似陈旧的 running 执行。"""
    engine = get_workflow_engine()
    db = get_db()
    try:
        return await engine.resolve_stale_execution(
            execution_id,
            db,
            action=request.action,
            reason=request.reason,
        )
    except WorkflowOperationError as exc:
        _raise_workflow_operation_http_error(exc)


@router.get("/executions/{execution_id}/operation-events", response_model=Dict[str, Any])
async def get_execution_operation_events(
    execution_id: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    """获取面向操作台展示的精简执行事件时间线。"""
    engine = get_workflow_engine()
    db = get_db()
    execution = await engine.get_execution_state(execution_id, db)
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    if not db or not hasattr(db, "get_workflow_execution_events_since"):
        return {"success": True, "events": []}

    try:
        normalized_limit = int(limit)
    except (TypeError, ValueError):
        normalized_limit = 50
    normalized_limit = max(1, min(normalized_limit, 200))

    rows = await db.get_workflow_execution_events_since(execution_id, sequence_no=0, limit=500)
    events = []
    for row in rows:
        event_type = row.get("event_type")
        if event_type not in _OPERATION_TIMELINE_EVENT_TYPES:
            continue
        data = _safe_event_data(row.get("event_data") or {})
        event = {
            "sequence_no": row.get("sequence_no"),
            "event_type": event_type,
            "created_at": row.get("created_at"),
            "summary": _operation_event_summary(event_type, data),
            "node_id": data.get("node_id") or data.get("failed_node_id") or data.get("recovered_node_id") or data.get("source_node_id") or data.get("evaluator_node_id") or data.get("condition_node_id"),
            "status": data.get("status"),
            "severity": "error" if event_type in {"workflow_failed", "node_failed", "workflow_execution_stale"} else "warning" if event_type in {"quality_gate_failed", "chapter_revision_requested"} else "info",
            "data": data,
        }
        events.append(engine._serialize_for_json(event))
    return {"success": True, "events": events[-normalized_limit:]}


@router.get("/executions/{execution_id}/events")
async def stream_execution_events(request: Request, execution_id: str):
    """以 SSE 形式订阅工作流执行事件。"""
    engine = get_workflow_engine()
    db = get_db()

    execution = await engine.get_execution_state(execution_id, db)
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    queue = engine.subscribe_execution_events(execution_id)

    async def event_generator():
        try:
            initial_event = {
                "type": "execution_snapshot",
                "execution_id": execution_id,
                "data": engine._serialize_for_json(execution),
            }
            yield _format_sse("workflow_event", initial_event)

            latest_replayed_sequence_no = 0
            if db and hasattr(db, "get_workflow_execution_events_since"):
                try:
                    historical_events = await db.get_workflow_execution_events_since(
                        execution_id,
                        sequence_no=0,
                        limit=200,
                    )
                    for row in historical_events:
                        raw_event_data = row.get("event_data") or {}
                        if isinstance(raw_event_data, str):
                            try:
                                event_data = json.loads(raw_event_data)
                            except json.JSONDecodeError:
                                event_data = {"raw": raw_event_data}
                        else:
                            event_data = raw_event_data

                        try:
                            sequence_no = int(row.get("sequence_no") or 0)
                        except (TypeError, ValueError):
                            sequence_no = 0
                        latest_replayed_sequence_no = max(latest_replayed_sequence_no, sequence_no)

                        replay_event = {
                            "type": row.get("event_type"),
                            "execution_id": execution_id,
                            "data": engine._serialize_for_json(event_data),
                            "sequence_no": sequence_no,
                            "replayed": True,
                        }
                        yield _format_sse("workflow_event", replay_event)
                except Exception as e:
                    logger.warning(f"回放工作流执行历史事件失败: {execution_id}, error={e}")

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    try:
                        event_sequence_no = int(event.get("sequence_no") or 0)
                    except (TypeError, ValueError, AttributeError):
                        event_sequence_no = 0
                    if event_sequence_no and event_sequence_no <= latest_replayed_sequence_no:
                        continue
                    yield _format_sse("workflow_event", event)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            engine.unsubscribe_execution_events(execution_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



@router.get("/executions/{execution_id}/trace", response_model=Dict[str, Any])
async def get_execution_trace(execution_id: str):
    """获取指定 workflow execution 的完整 Trace 摘要。"""
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    trace = await db.get_trace_by_execution(execution_id)
    if not trace:
        return {"success": True, "trace": None, "spans": [], "events": [], "artifacts": []}

    trace_id = str(trace["id"])
    spans = await db.get_trace_spans(trace_id)
    events = await db.get_trace_events(trace_id, limit=200)
    artifacts = await db.get_trace_artifacts(trace_id)
    return {
        "success": True,
        "trace": trace,
        "spans": spans,
        "events": events,
        "artifacts": artifacts,
    }


@router.get("/traces/{trace_id}", response_model=Dict[str, Any])
async def get_trace(trace_id: str):
    """获取 Trace 基本信息。"""
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="数据库未连接")
    trace = await db.get_execution_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace 不存在")
    return {"success": True, "trace": trace}


@router.get("/traces/{trace_id}/spans", response_model=Dict[str, Any])
async def get_trace_spans(trace_id: str):
    """获取 Trace spans。"""
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="数据库未连接")
    return {"success": True, "spans": await db.get_trace_spans(trace_id)}


@router.get("/traces/{trace_id}/events", response_model=Dict[str, Any])
async def get_trace_events(
    trace_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
):
    """获取 Trace events。"""
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="数据库未连接")
    return {"success": True, "events": await db.get_trace_events(trace_id, limit=limit)}


@router.get("/traces/{trace_id}/artifacts", response_model=Dict[str, Any])
async def get_trace_artifacts(
    trace_id: str,
    span_id: Optional[str] = Query(None),
):
    """获取 Trace artifacts。"""
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="数据库未连接")
    return {"success": True, "artifacts": await db.get_trace_artifacts(trace_id, span_id=span_id)}


@router.get("/executions/{execution_id}/export-markdown", response_model=Dict[str, Any])
async def export_execution_markdown(execution_id: str):
    """
    导出工作流执行复盘 Markdown

    Args:
        execution_id: 执行ID

    Returns:
        Dict: markdown 内容和文件名
    """
    engine = get_workflow_engine()
    db = get_db()

    execution = await engine.get_execution_state(execution_id, db)
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    workflow = await engine.get_workflow(execution.workflow_id, db)
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流定义不存在")

    export_service = get_workflow_replay_export_service()
    content = export_service.export_markdown(execution, workflow)
    file_path = export_service.save_markdown(execution, workflow)
    execution.context["replay_markdown_path"] = file_path

    if db:
        await engine._save_execution_to_db(execution, db)

    return {
        "success": True,
        "format": "markdown",
        "content": content,
        "filename": export_service.get_export_filename(execution),
        "file_path": file_path,
    }


def _parse_jsonish(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _summarize_execution_row(row: Dict[str, Any]) -> Dict[str, Any]:
    node_states = _parse_jsonish(row.get("node_states"), {})
    if not isinstance(node_states, dict):
        node_states = {}

    context = _parse_jsonish(row.get("context"), {})
    if not isinstance(context, dict):
        context = {}

    resume_cursor = _parse_jsonish(row.get("resume_cursor"), None)
    if resume_cursor is not None and not isinstance(resume_cursor, dict):
        resume_cursor = None

    node_count = len(node_states)
    completed_node_count = 0
    failed_node_id = None
    for node_id, state in node_states.items():
        if not isinstance(state, dict):
            continue
        if state.get("status") == "completed":
            completed_node_count += 1
        if failed_node_id is None and state.get("status") == "failed":
            failed_node_id = node_id

    recovery_history = context.get("recovery_history")
    if not isinstance(recovery_history, list):
        recovery_history = []
    latest_recovery = recovery_history[-1] if recovery_history and isinstance(recovery_history[-1], dict) else None

    return {
        "id": row["id"],
        "workflow_id": row["workflow_id"],
        "project_id": str(row["project_id"]),
        "status": row["status"],
        "current_node": row["current_node"],
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        "total_duration_ms": row["total_duration_ms"],
        "trace_id": str(row.get("trace_id")) if row.get("trace_id") else None,
        "error": row["error"],
        "node_count": node_count,
        "completed_node_count": completed_node_count,
        "failed_node_id": failed_node_id,
        "recovery_count": len(recovery_history),
        "latest_recovery": latest_recovery,
        "resume_cursor": resume_cursor,
    }


@router.get("/executions", response_model=List[Dict[str, Any]])
async def list_executions(
    project_id: str = Query(..., description="项目ID"),
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    workflow_id: Optional[str] = Query(None, description="工作流ID过滤"),
):
    """获取工作流执行历史摘要列表。"""
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        conditions = ["project_id = :project_id"]
        params = {"project_id": project_id, "limit": limit, "offset": offset}

        if status:
            conditions.append("status = :status")
            params["status"] = status
        if workflow_id:
            conditions.append("workflow_id = :workflow_id")
            params["workflow_id"] = workflow_id

        query = f"""
        SELECT * FROM workflow_executions
        WHERE {' AND '.join(conditions)}
        ORDER BY started_at DESC
        LIMIT :limit OFFSET :offset
        """

        results = await db.execute_query(query, params)
        return [_summarize_execution_row(row) for row in results]
    except Exception as e:
        logger.error(f"获取执行列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow(workflow_id: str):
    """
    获取工作流详情

    Args:
        workflow_id: 工作流ID

    Returns:
        Dict: 工作流详情
    """
    engine = get_workflow_engine()
    db = get_db()

    workflow = await engine.get_workflow(workflow_id, db)
    if not workflow:
        active_execution = None
        if db and hasattr(db, "execute_query"):
            try:
                rows = await db.execute_query(
                    """
                    SELECT id, status, current_node, started_at, updated_at
                    FROM workflow_executions
                    WHERE workflow_id = :workflow_id
                      AND status IN ('running', 'paused', 'pending')
                    ORDER BY updated_at DESC NULLS LAST, started_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    {"workflow_id": workflow_id},
                )
                if rows:
                    active_execution = {key: rows[0].get(key) for key in ("id", "status", "current_node", "started_at", "updated_at")}
                    logger.warning(
                        "工作流定义缺失但存在活跃执行: workflow_id=%s execution_id=%s status=%s",
                        workflow_id,
                        active_execution.get("id"),
                        active_execution.get("status"),
                    )
            except Exception as exc:
                logger.warning("检查缺失工作流定义的活跃执行失败: workflow_id=%s error=%s", workflow_id, exc)
        detail: Dict[str, Any] = {
            "code": "workflow_definition_not_found",
            "message": "工作流定义不存在或已被删除；如果执行仍在运行，请以执行状态为准。",
            "workflow_id": workflow_id,
            "recoverable_from_execution": bool(active_execution),
        }
        if active_execution:
            detail["active_execution"] = active_execution
        raise HTTPException(status_code=404, detail=detail)

    return workflow.model_dump()


@router.put("/{workflow_id}", response_model=Dict[str, Any])
async def update_workflow(workflow_id: str, request: WorkflowDefinitionUpdate):
    """
    更新工作流

    Args:
        workflow_id: 工作流ID
        request: 更新请求

    Returns:
        Dict: 更新结果
    """
    engine = get_workflow_engine()
    db = get_db()

    try:
        workflow = await engine.update_workflow(workflow_id, request, db)
        if not workflow:
            raise HTTPException(status_code=404, detail="工作流不存在")

        return {
            "success": True,
            "message": "工作流更新成功",
            "workflow": workflow.model_dump(),
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workflow_id}", response_model=Dict[str, Any])
async def delete_workflow(workflow_id: str):
    """
    删除工作流

    Args:
        workflow_id: 工作流ID

    Returns:
        Dict: 删除结果
    """
    engine = get_workflow_engine()
    db = get_db()

    try:
        success = await engine.delete_workflow(workflow_id, db)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not success:
        raise HTTPException(status_code=404, detail="工作流不存在")

    return {
        "success": True,
        "message": f"工作流 {workflow_id} 已删除",
    }


@router.post("/{workflow_id}/validate", response_model=WorkflowValidationResult)
async def validate_workflow(workflow_id: str):
    """
    验证工作流有效性

    Args:
        workflow_id: 工作流ID

    Returns:
        WorkflowValidationResult: 验证结果
    """
    engine = get_workflow_engine()
    db = get_db()

    workflow = await engine.get_workflow(workflow_id, db)
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    return engine.validate_workflow(workflow)


# ==================== 工作流执行 API ====================

async def _setup_agent_provider_for_execution(project_id: str):
    """
    为工作流执行设置 Agent provider

    创建 DirectorSystem 实例并设置 Agent provider 回调
    """
    from app.services.workflow_engine import get_workflow_engine
    from app.services.director import DirectorSystem
    from app.config import settings
    from app.api.app import postgres_db

    # 创建 DirectorSystem 实例
    director = DirectorSystem(
        world_data={"id": f"world_workflow_{project_id}", "name": "Workflow World", "regions": [], "relationships": {}},
        config={
            "max_turns_threshold": settings.max_turns_threshold,
            "target_word_count_per_intent": settings.target_word_count_per_intent,
        },
        project_id=project_id,
    )

    # 初始化 DirectorSystem
    from app.services.model_router import create_model_factory
    model_factory = create_model_factory()

    # 加载角色
    characters = []
    if postgres_db:
        try:
            characters = await postgres_db.get_all_characters(project_id)
        except Exception as e:
            logger.warning(f"加载角色失败: {e}")

    await director.initialize(model_factory, characters=characters)
    logger.info(f"DirectorSystem 已为工作流初始化: project_id={project_id}, characters={len(characters)}")

    # 设置 Agent provider
    engine = get_workflow_engine()

    async def _agent_provider_wrapper(agent_type: str, proj_id: str):
        """Agent provider 包装器"""
        from app.api.routes.websocket import create_agent_provider
        provider = await create_agent_provider(director)
        return await provider(agent_type, proj_id)

    engine.set_agent_provider(_agent_provider_wrapper)

    return director


@router.post("/{workflow_id}/execute", response_model=Dict[str, Any])
async def execute_workflow(
    workflow_id: str,
    project_id: str = Query(..., description="项目ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    执行工作流

    Args:
        workflow_id: 工作流ID
        project_id: 项目ID
        body: 支持 {initial_context, request_id, force_new}，也兼容旧版裸 initial_context

    Returns:
        Dict: 执行ID和初始状态
    """
    engine = get_workflow_engine()
    db = get_db()

    request_id = None
    force_new = False
    initial_context: Dict[str, Any] = {}
    if body:
        if any(key in body for key in ("initial_context", "request_id", "force_new")):
            initial_context = body.get("initial_context") or {}
            request_id = body.get("request_id")
            force_new = bool(body.get("force_new", False))
        else:
            initial_context = body

    try:
        # 初始化 Agent provider
        await _setup_agent_provider_for_execution(project_id)

        if hasattr(engine, "start_workflow_execution"):
            start_result = await engine.start_workflow_execution(
                workflow_id,
                project_id,
                initial_context or {},
                db,
                request_id=request_id,
                force_new=force_new,
            )
            execution_id = start_result.execution_id
            deduplicated = bool(start_result.deduplicated or start_result.replayed)
            replayed = bool(start_result.replayed)
        else:
            execution_id = await engine.execute_workflow(
                workflow_id,
                project_id,
                initial_context or {},
                db,
                request_id=request_id,
                force_new=force_new,
            )
            deduplicated = False
            replayed = False
        execution = await engine.get_execution_state(execution_id, db)

        return {
            "success": True,
            "message": "工作流已启动" if not force_new else "工作流已强制新建并启动",
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "request_id": execution.request_id if execution else request_id,
            "status": execution.status.value if execution else None,
            "trace_id": execution.trace_id if execution else None,
            "world_id": (execution.context or {}).get("world_id") if execution else (initial_context or {}).get("world_id"),
            "deduplicated": deduplicated,
            "replayed": replayed,
        }
    except ChapterReadinessBlockedError as e:
        raise HTTPException(status_code=409, detail=engine._serialize_for_json(e.payload))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"执行工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/executions/{execution_id}/pause", response_model=Dict[str, Any])
async def pause_execution(execution_id: str):
    """
    暂停工作流执行

    Args:
        execution_id: 执行ID

    Returns:
        Dict: 操作结果
    """
    engine = get_workflow_engine()
    db = get_db()

    try:
        success = await engine.pause_workflow(execution_id, db)
    except WorkflowOperationError as exc:
        _raise_workflow_operation_http_error(exc)
    if not success:
        raise HTTPException(status_code=400, detail="无法暂停工作流（可能不在运行状态）")

    execution = await engine.get_execution_state(execution_id, db)
    return {
        "success": True,
        "message": f"工作流 {execution_id} 已暂停",
        "execution": engine._serialize_for_json(execution) if execution else None,
    }


@router.post("/executions/{execution_id}/resume", response_model=Dict[str, Any])
async def resume_execution(execution_id: str):
    """
    恢复工作流执行

    Args:
        execution_id: 执行ID

    Returns:
        Dict: 操作结果
    """
    engine = get_workflow_engine()
    db = get_db()

    execution = await engine.get_execution_state(execution_id, db)
    if execution:
        await _setup_agent_provider_for_execution(execution.project_id)

    try:
        success = await engine.resume_workflow(execution_id, db)
    except WorkflowOperationError as exc:
        _raise_workflow_operation_http_error(exc)
    if not success:
        raise HTTPException(status_code=400, detail="无法恢复工作流（可能不在暂停状态）")

    execution = await engine.get_execution_state(execution_id, db)
    return {
        "success": True,
        "message": f"工作流 {execution_id} 已恢复",
        "execution": engine._serialize_for_json(execution) if execution else None,
    }


@router.get("/executions/{execution_id}/failed-node-diagnosis", response_model=Dict[str, Any])
async def diagnose_failed_execution_node(
    execution_id: str,
    node_id: Optional[str] = Query(None, description="失败节点ID"),
):
    """获取失败节点诊断摘要。"""
    engine = get_workflow_engine()
    db = get_db()
    try:
        return await engine.diagnose_failed_workflow_node(execution_id, db, node_id=node_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("诊断失败节点失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"诊断失败：{exc}")


@router.post("/executions/{execution_id}/remediations/validate", response_model=Dict[str, Any])
async def validate_failed_execution_remediation(execution_id: str, request: WorkflowRemediationRequest):
    """验证失败节点安全修复补丁。"""
    engine = get_workflow_engine()
    db = get_db()
    try:
        return await engine.validate_failed_node_remediation(
            execution_id,
            db,
            node_id=request.node_id,
            patch=request.patch.model_dump(exclude_none=True),
            context_patch=request.context_patch,
        )
    except WorkflowOperationError as exc:
        _raise_workflow_operation_http_error(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("验证失败节点修复失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"验证失败：{exc}")


@router.post("/executions/{execution_id}/remediate-and-recover", response_model=Dict[str, Any])
async def remediate_and_recover_execution(execution_id: str, request: WorkflowRemediationRequest):
    """应用失败节点安全修复并恢复同一执行。"""
    engine = get_workflow_engine()
    db = get_db()
    try:
        return await engine.remediate_failed_workflow_node(
            execution_id,
            db,
            node_id=request.node_id,
            patch=request.patch.model_dump(exclude_none=True),
            reason=request.reason,
            context_patch=request.context_patch,
            reset_downstream=request.reset_downstream,
        )
    except WorkflowOperationError as exc:
        _raise_workflow_operation_http_error(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("修复并恢复失败节点失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"修复恢复失败：{exc}")


@router.post("/executions/{execution_id}/recover", response_model=Dict[str, Any])
async def recover_execution(execution_id: str, request: WorkflowRecoveryRequest):
    """从失败节点恢复工作流执行。"""
    engine = get_workflow_engine()
    db = get_db()

    execution = await engine.get_execution_state(execution_id, db)
    if not execution:
        raise HTTPException(status_code=404, detail="工作流执行不存在")
    await _setup_agent_provider_for_execution(execution.project_id)

    try:
        return await engine.recover_failed_workflow(
            execution_id,
            db,
            mode=request.mode,
            node_id=request.node_id,
            reason=request.reason,
            context_patch=request.context_patch,
            reset_downstream=request.reset_downstream,
        )
    except WorkflowOperationError as exc:
        _raise_workflow_operation_http_error(exc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/executions/{execution_id}/confirm-discussion", response_model=Dict[str, Any])
async def confirm_discussion(execution_id: str, approved: bool = Query(...), feedback: Optional[str] = Query(None)):
    """
    确认集体讨论结果

    用户可以选择：
    - 同意（approved=true）：工作流继续执行
    - 不同意（approved=false）：提供反馈意见，工作流重新开始

    Args:
        execution_id: 执行ID
        approved: 是否同意讨论结果
        feedback: 用户反馈意见（不同意时必填）

    Returns:
        Dict: 操作结果
    """
    engine = get_workflow_engine()
    db = get_db()

    execution = await engine.get_execution_state(execution_id, db)
    if execution:
        await _setup_agent_provider_for_execution(execution.project_id)

    if not approved and not feedback:
        raise HTTPException(status_code=400, detail="不同意讨论结果时必须提供反馈意见（feedback 参数）")

    result = await engine.confirm_discussion(
        execution_id=execution_id,
        approved=approved,
        feedback=feedback,
        db=db,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "确认失败"))

    return result


@router.post("/executions/{execution_id}/cancel", response_model=Dict[str, Any])
async def cancel_execution(execution_id: str):
    """
    取消工作流执行

    Args:
        execution_id: 执行ID

    Returns:
        Dict: 操作结果
    """
    engine = get_workflow_engine()
    db = get_db()

    try:
        success = await engine.cancel_workflow(execution_id, db)
    except WorkflowOperationError as exc:
        _raise_workflow_operation_http_error(exc)
    if not success:
        raise HTTPException(status_code=400, detail="无法取消工作流")

    execution = await engine.get_execution_state(execution_id, db)
    return {
        "success": True,
        "message": f"工作流 {execution_id} 已取消",
        "execution": engine._serialize_for_json(execution) if execution else None,
    }
