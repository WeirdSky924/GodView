"""
工作流 API 路由
v8 Agent协作可视化工作台
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

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


# ==================== 工作流定义 API ====================

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

    success = await engine.delete_workflow(workflow_id, db)
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

@router.post("/{workflow_id}/execute", response_model=Dict[str, Any])
async def execute_workflow(
    workflow_id: str,
    project_id: str = Query(..., description="项目ID"),
    initial_context: Optional[Dict[str, Any]] = None,
):
    """
    执行工作流

    Args:
        workflow_id: 工作流ID
        project_id: 项目ID
        initial_context: 初始上下文

    Returns:
        Dict: 执行ID和初始状态
    """
    engine = get_workflow_engine()
    db = get_db()

    try:
        execution_id = await engine.execute_workflow(
            workflow_id,
            project_id,
            initial_context or {},
            db,
        )

        return {
            "success": True,
            "message": "工作流已启动",
            "execution_id": execution_id,
            "workflow_id": workflow_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"执行工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

    return execution.model_dump()


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
                "error": row["error"],
            })

        return executions
    except Exception as e:
        logger.error(f"获取执行列表失败: {e}")
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
