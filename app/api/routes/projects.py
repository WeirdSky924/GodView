"""
项目管理 API 路由
v4 核心需求：项目创建、列表、详情、更新、删除、摘要
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.project import (
    Project,
    ProjectSummary,
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=Dict[str, Any])
async def create_project(request: CreateProjectRequest):
    """
    创建新项目

    Args:
        request: 创建项目请求

    Returns:
        Dict: 创建结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 生成项目 ID (UUID)
    import uuid
    project_id = str(uuid.uuid4())

    # 创建项目对象
    project = Project(
        id=project_id,
        name=request.name,
        description=request.description,
        user_id=request.user_id,
        status=ProjectStatus.DRAFT,
        metadata=request.metadata or {},
    )

    project_data = project.model_dump(mode="json")

    try:
        await postgres_db.save_project(project_data)
        return {
            "success": True,
            "id": project.id,
            "message": f"项目 '{project.name}' 创建成功",
            "project": project_data,
        }
    except Exception as e:
        logger.error(f"创建项目失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[Dict[str, Any]])
async def list_projects(
    status: Optional[ProjectStatus] = Query(default=None, description="项目状态过滤"),
    limit: int = Query(default=100, le=1000, description="返回数量限制"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
):
    """
    获取项目列表

    Args:
        status: 项目状态过滤
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        List: 项目列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        projects = await postgres_db.get_all_projects(status=status, limit=limit, offset=offset)
        return projects
    except Exception as e:
        logger.error(f"获取项目列表失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=List[Dict[str, Any]])
async def list_project_summaries(
    status: Optional[ProjectStatus] = Query(default=None, description="项目状态过滤"),
    limit: int = Query(default=100, le=1000, description="返回数量限制"),
):
    """
    获取项目摘要列表

    Args:
        status: 项目状态过滤
        limit: 返回数量限制

    Returns:
        List: 项目摘要列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        summaries = await postgres_db.get_project_summaries(status=status, limit=limit)
        return summaries
    except Exception as e:
        logger.error(f"获取项目摘要列表失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}", response_model=Dict[str, Any])
async def get_project(project_id: str):
    """
    获取项目详情

    Args:
        project_id: 项目 ID

    Returns:
        Dict: 项目数据
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    project = await postgres_db.get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    return project


@router.put("/{project_id}", response_model=Dict[str, Any])
async def update_project(project_id: str, request: UpdateProjectRequest):
    """
    更新项目

    Args:
        project_id: 项目 ID
        request: 更新项目请求

    Returns:
        Dict: 更新结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await postgres_db.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 构建更新数据
    update_data = {}
    if request.name is not None:
        update_data["name"] = request.name
    if request.description is not None:
        update_data["description"] = request.description
    if request.status is not None:
        update_data["status"] = request.status.value
    if request.metadata is not None:
        update_data["metadata"] = request.metadata

    if not update_data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    try:
        await postgres_db.update_project(project_id, update_data)
        updated = await postgres_db.get_project(project_id)
        return {
            "success": True,
            "message": f"项目 {project_id} 更新成功",
            "project": updated,
        }
    except Exception as e:
        logger.error(f"更新项目失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}", response_model=Dict[str, Any])
async def delete_project(project_id: str):
    """
    删除项目

    Args:
        project_id: 项目 ID

    Returns:
        Dict: 删除结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await postgres_db.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        await postgres_db.delete_project(project_id)
        return {"success": True, "message": f"项目 {project_id} 已删除"}
    except Exception as e:
        logger.error(f"删除项目失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/summary", response_model=Dict[str, Any])
async def get_project_summary(project_id: str):
    """
    获取项目摘要信息

    Args:
        project_id: 项目 ID

    Returns:
        Dict: 项目摘要
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    summary = await postgres_db.get_project_summary(project_id)

    if not summary:
        raise HTTPException(status_code=404, detail="项目不存在")

    return summary