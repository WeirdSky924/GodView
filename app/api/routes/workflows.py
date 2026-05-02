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
from app.services.workflow_engine import ChapterReadinessBlockedError
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


class WorkflowExecuteRequest(BaseModel):
    """工作流执行请求，兼容旧版裸 initial_context body。"""

    initial_context: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None
    force_new: bool = False


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

    return engine._serialize_for_json(execution)




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


@router.get("/executions", response_model=List[Dict[str, Any]])
async def list_executions(
    project_id: str = Query(..., description="项目ID"),
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    获取工作流执行列表

    Args:
        project_id: 项目ID
        status: 状态过滤
        limit: 返回数量
        offset: 偏移量

    Returns:
        List: 执行列表
    """
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        conditions = ["project_id = :project_id"]
        params = {"project_id": project_id, "limit": limit, "offset": offset}

        if status:
            conditions.append("status = :status")
            params["status"] = status

        query = f"""
        SELECT * FROM workflow_executions
        WHERE {' AND '.join(conditions)}
        ORDER BY started_at DESC
        LIMIT :limit OFFSET :offset
        """

        results = await db.execute_query(query, params)

        executions = []
        for row in results:
            executions.append({
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
            })

        return executions
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
        raise HTTPException(status_code=404, detail="工作流不存在")

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

        execution_id = await engine.execute_workflow(
            workflow_id,
            project_id,
            initial_context or {},
            db,
            request_id=request_id,
            force_new=force_new,
        )
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
            "deduplicated": bool(execution and request_id and execution.request_id == request_id and execution.id == execution_id),
        }
    except ChapterReadinessBlockedError as e:
        raise HTTPException(status_code=409, detail=e.payload)
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

    success = await engine.pause_workflow(execution_id, db)
    if not success:
        raise HTTPException(status_code=400, detail="无法暂停工作流（可能不在运行状态）")

    return {
        "success": True,
        "message": f"工作流 {execution_id} 已暂停",
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

    success = await engine.resume_workflow(execution_id, db)
    if not success:
        raise HTTPException(status_code=400, detail="无法恢复工作流（可能不在暂停状态）")

    return {
        "success": True,
        "message": f"工作流 {execution_id} 已恢复",
    }


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

    success = await engine.cancel_workflow(execution_id, db)
    if not success:
        raise HTTPException(status_code=400, detail="无法取消工作流")

    return {
        "success": True,
        "message": f"工作流 {execution_id} 已取消",
    }
