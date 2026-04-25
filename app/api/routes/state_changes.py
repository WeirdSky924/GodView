"""剧情状态变更 API 路由。"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.narrative import NarrativeStateChange
from app.services.narrative_state_change_service import NarrativeStateChangeService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service(postgres_db: Any) -> NarrativeStateChangeService:
    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")
    return NarrativeStateChangeService(postgres_db)


def _to_http_error(error: Exception) -> HTTPException:
    message = str(error)
    if "不存在" in message:
        return HTTPException(status_code=404, detail=message)
    if "不能" in message or "缺少" in message or "尚未确认" in message:
        return HTTPException(status_code=400, detail=message)
    logger.exception("剧情状态变更操作失败")
    return HTTPException(status_code=500, detail=message)


@router.get("", response_model=List[Dict[str, Any]])
async def list_state_changes(
    project_id: str = Query(..., description="项目 ID"),
    entity_type: Optional[str] = Query(None, description="实体类型"),
    entity_id: Optional[str] = Query(None, description="实体 ID"),
    status: Optional[str] = Query(None, description="变更状态"),
    change_type: Optional[str] = Query(None, description="变更类型"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """列出项目剧情状态变更。"""
    from app.api.app import postgres_db

    service = _get_service(postgres_db)
    return await service.list_changes(
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        status=status,
        change_type=change_type,
        limit=limit,
    )


@router.get("/{change_id}", response_model=Dict[str, Any])
async def get_state_change(change_id: str):
    """获取单条剧情状态变更。"""
    from app.api.app import postgres_db

    service = _get_service(postgres_db)
    try:
        return await service.get_change(change_id)
    except Exception as e:
        raise _to_http_error(e)


@router.post("", response_model=Dict[str, Any])
async def create_state_change(change: NarrativeStateChange):
    """手动创建剧情状态变更。"""
    from app.api.app import postgres_db

    service = _get_service(postgres_db)
    try:
        return await service.create_change(change.model_dump(mode="json"))
    except Exception as e:
        raise _to_http_error(e)


@router.post("/{change_id}/confirm", response_model=Dict[str, Any])
async def confirm_state_change(change_id: str):
    """确认剧情状态变更。"""
    from app.api.app import postgres_db

    service = _get_service(postgres_db)
    try:
        return await service.confirm_change(change_id)
    except Exception as e:
        raise _to_http_error(e)


@router.post("/{change_id}/apply", response_model=Dict[str, Any])
async def apply_state_change(change_id: str):
    """应用剧情状态变更到当前状态表。"""
    from app.api.app import postgres_db

    service = _get_service(postgres_db)
    try:
        return await service.apply_change(change_id)
    except Exception as e:
        raise _to_http_error(e)


@router.post("/{change_id}/reject", response_model=Dict[str, Any])
async def reject_state_change(change_id: str):
    """拒绝剧情状态变更。"""
    from app.api.app import postgres_db

    service = _get_service(postgres_db)
    try:
        return await service.reject_change(change_id)
    except Exception as e:
        raise _to_http_error(e)
