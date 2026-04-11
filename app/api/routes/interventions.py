"""
干预 API 路由
v8 Agent协作可视化工作台
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime

from app.models.intervention import (
    InterventionLog,
    InterventionCreate,
    InterventionQuery,
    InterventionSummary,
    InterventionExportFormat,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 服务实例
_intervention_service = None
_agent_communication_service = None


def get_intervention_service():
    """获取干预日志服务"""
    global _intervention_service
    if _intervention_service is None:
        from app.services.intervention_service import get_intervention_service
        _intervention_service = get_intervention_service()
    return _intervention_service


def get_agent_communication_service():
    """获取Agent通信服务"""
    global _agent_communication_service
    if _agent_communication_service is None:
        from app.services.agent_communication import get_agent_communication_service
        _agent_communication_service = get_agent_communication_service()
    return _agent_communication_service


def get_db():
    """获取数据库连接"""
    from app.api.app import postgres_db
    return postgres_db


def set_intervention_service(service):
    """设置干预日志服务"""
    global _intervention_service
    _intervention_service = service


def set_agent_communication_service(service):
    """设置Agent通信服务"""
    global _agent_communication_service
    _agent_communication_service = service


# ==================== 干预日志 API ====================

@router.get("", response_model=List[Dict[str, Any]])
async def list_interventions(
    project_id: Optional[str] = Query(None, description="项目ID"),
    workflow_execution_id: Optional[str] = Query(None, description="工作流执行ID"),
    agent_type: Optional[str] = Query(None, description="Agent类型过滤"),
    intervention_type: Optional[str] = Query(None, description="干预类型过滤"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    获取干预日志列表

    Args:
        project_id: 项目ID
        workflow_execution_id: 工作流执行ID
        agent_type: Agent类型过滤
        intervention_type: 干预类型过滤
        keyword: 关键词搜索
        limit: 返回数量
        offset: 偏移量

    Returns:
        List: 干预日志列表
    """
    service = get_intervention_service()
    db = get_db()

    query = InterventionQuery(
        project_id=project_id,
        workflow_execution_id=workflow_execution_id,
        agent_type=agent_type,
        intervention_type=intervention_type,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )

    try:
        logs = await service.get_intervention_logs(query, db)
        return [log.model_dump(mode='json') for log in logs]
    except Exception as e:
        logger.error(f"获取干预日志列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Dict[str, Any])
async def send_intervention(request: InterventionCreate):
    """
    发送干预消息

    Args:
        request: 干预请求

    Returns:
        Dict: Agent响应
    """
    comm_service = get_agent_communication_service()
    int_service = get_intervention_service()
    db = get_db()

    # 设置干预服务引用
    comm_service.set_intervention_service(int_service)

    try:
        result = await comm_service.send_agent_message(
            execution_id=request.workflow_execution_id,
            agent_type=request.agent_type,
            message=request.message,
            project_id=request.project_id,
            node_id=request.node_id,
        )

        return {
            "success": result.get("success", False),
            "message": "干预消息已发送" if result.get("success") else "干预消息发送失败",
            "agent_response": result.get("response"),
            "agent_name": result.get("agent_name"),
            "response_time_ms": result.get("response_time_ms"),
            "intervention_id": result.get("intervention_id"),
            "intervention_type": result.get("intervention_type"),
        }
    except Exception as e:
        logger.error(f"发送干预消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{intervention_id}", response_model=Dict[str, Any])
async def get_intervention(intervention_id: str):
    """
    获取干预详情

    Args:
        intervention_id: 干预日志ID

    Returns:
        Dict: 干预详情
    """
    service = get_intervention_service()
    db = get_db()

    log = await service.get_intervention(intervention_id, db)
    if not log:
        raise HTTPException(status_code=404, detail="干预日志不存在")

    return log.model_dump(mode='json')


@router.get("/summary/{project_id}", response_model=Dict[str, Any])
async def get_intervention_summary(
    project_id: str,
    execution_id: Optional[str] = Query(None, description="执行ID"),
):
    """
    获取干预摘要统计

    Args:
        project_id: 项目ID
        execution_id: 执行ID（可选）

    Returns:
        Dict: 干预摘要
    """
    service = get_intervention_service()
    db = get_db()

    try:
        summary = await service.get_intervention_summary(project_id, execution_id, db)
        return {
            "success": True,
            "summary": {
                "total_count": summary.total_count,
                "by_agent_type": summary.by_agent_type,
                "by_intervention_type": summary.by_intervention_type,
                "avg_response_time_ms": summary.avg_response_time_ms,
                "recent_interventions": [
                    log.model_dump(mode='json') for log in summary.recent_interventions
                ],
            },
        }
    except Exception as e:
        logger.error(f"获取干预摘要失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_interventions(
    project_id: str = Query(..., description="项目ID"),
    workflow_execution_id: Optional[str] = Query(None, description="执行ID"),
    format: str = Query(default="json", description="导出格式: json/csv/markdown"),
    include_context: bool = Query(default=False, description="是否包含上下文"),
):
    """
    导出干预日志

    Args:
        project_id: 项目ID
        workflow_execution_id: 执行ID
        format: 导出格式
        include_context: 是否包含上下文

    Returns:
        Dict: 导出内容
    """
    service = get_intervention_service()
    db = get_db()

    try:
        export_format = InterventionExportFormat(format)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的导出格式: {format}")

    try:
        content = await service.export_logs(
            project_id=project_id,
            execution_id=workflow_execution_id,
            format=export_format,
            include_context=include_context,
            db=db,
        )

        # 确定文件扩展名
        extensions = {
            InterventionExportFormat.JSON: "json",
            InterventionExportFormat.CSV: "csv",
            InterventionExportFormat.MARKDOWN: "md",
        }

        return {
            "success": True,
            "format": format,
            "content": content,
            "filename": f"interventions_{project_id[:8]}.{extensions[export_format]}",
        }
    except Exception as e:
        logger.error(f"导出干预日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/execution/{execution_id}", response_model=Dict[str, Any])
async def delete_interventions_by_execution(execution_id: str):
    """
    删除某次执行的所有干预日志

    Args:
        execution_id: 执行ID

    Returns:
        Dict: 删除结果
    """
    service = get_intervention_service()
    db = get_db()

    try:
        count = await service.delete_interventions_by_execution(execution_id, db)
        return {
            "success": True,
            "message": f"已删除 {count} 条干预日志",
            "deleted_count": count,
        }
    except Exception as e:
        logger.error(f"删除干预日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{intervention_id}", response_model=Dict[str, Any])
async def delete_single_intervention(intervention_id: str):
    """
    删除单个干预日志

    Args:
        intervention_id: 干预日志ID

    Returns:
        Dict: 删除结果
    """
    service = get_intervention_service()
    db = get_db()

    # 先检查是否存在
    log = await service.get_intervention(intervention_id, db)
    if not log:
        raise HTTPException(status_code=404, detail="干预日志不存在")

    try:
        success = await service.delete_intervention(intervention_id, db)
        return {
            "success": success,
            "message": "干预日志已删除",
            "deleted_id": intervention_id,
        }
    except Exception as e:
        logger.error(f"删除干预日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Agent 消息历史 API ====================

@router.get("/history/{execution_id}", response_model=List[Dict[str, Any]])
async def get_message_history(
    execution_id: str,
    agent_type: Optional[str] = Query(None, description="Agent类型过滤"),
):
    """
    获取消息历史

    Args:
        execution_id: 执行ID
        agent_type: Agent类型过滤

    Returns:
        List: 消息历史
    """
    comm_service = get_agent_communication_service()

    try:
        history = comm_service.get_message_history(execution_id, agent_type)
        return history
    except Exception as e:
        logger.error(f"获取消息历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
