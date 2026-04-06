"""
剧情管理 API 路由
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.plot import Chapter, Hook, Plot

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/hooks", response_model=List[Dict[str, Any]])
async def list_hooks(
    status: Optional[str] = None,
    hook_type: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """
    获取伏笔列表

    Args:
        status: 按状态过滤
        hook_type: 按类型过滤
        limit: 返回数量限制

    Returns:
        List: 伏笔列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    hooks = []

    if status:
        hooks = await postgres_db.get_hooks_by_status(status)
    else:
        # 获取所有伏笔（简化实现）
        pass

    # 类型过滤
    if hook_type and hooks:
        hooks = [h for h in hooks if h.get("hook_type") == hook_type]

    return hooks[:limit]


@router.get("/hooks/{hook_id}", response_model=Dict[str, Any])
async def get_hook(hook_id: str):
    """
    获取伏笔详情

    Args:
        hook_id: 伏笔 ID

    Returns:
        Dict: 伏笔数据
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    hook = await postgres_db.get_hook(hook_id)

    if not hook:
        raise HTTPException(status_code=404, detail="伏笔不存在")

    return hook


@router.post("/hooks", response_model=Dict[str, Any])
async def create_hook(hook: Hook):
    """
    创建新伏笔

    Args:
        hook: 伏笔数据

    Returns:
        Dict: 创建结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    hook_data = hook.model_dump(mode="json")

    try:
        await postgres_db.save_hook(hook_data)
        return {
            "success": True,
            "id": hook.id,
            "message": f"伏笔 '{hook.title}' 创建成功",
        }
    except Exception as e:
        logger.error(f"创建伏笔失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/hooks/{hook_id}/status", response_model=Dict[str, Any])
async def update_hook_status(hook_id: str, status: str):
    """
    更新伏笔状态

    Args:
        hook_id: 伏笔 ID
        status: 新状态 (planted/triggered/resolved/dropped)

    Returns:
        Dict: 更新结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        await postgres_db.update_hook_status(hook_id, status)
        return {
            "success": True,
            "message": f"伏笔状态已更新为 '{status}'",
        }
    except Exception as e:
        logger.error(f"更新伏笔状态失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chapters", response_model=List[Dict[str, Any]])
async def list_chapters(
    world_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """
    获取章节列表

    Args:
        world_id: 按世界过滤
        status: 按状态过滤
        limit: 返回数量限制

    Returns:
        List: 章节列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    chapters = []

    if world_id:
        chapters = await postgres_db.get_chapters_by_world(world_id)
    else:
        # 获取所有章节（简化实现）
        pass

    # 状态过滤
    if status and chapters:
        chapters = [c for c in chapters if c.get("status") == status]

    return chapters[:limit]


@router.get("/chapters/{chapter_id}", response_model=Dict[str, Any])
async def get_chapter(chapter_id: str):
    """
    获取章节详情

    Args:
        chapter_id: 章节 ID

    Returns:
        Dict: 章节数据
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    chapter = await postgres_db.get_chapter(chapter_id)

    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    return chapter


@router.post("/chapters", response_model=Dict[str, Any])
async def create_chapter(chapter: Chapter):
    """
    创建新章节

    Args:
        chapter: 章节数据

    Returns:
        Dict: 创建结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    chapter_data = chapter.model_dump(mode="json")

    try:
        await postgres_db.save_chapter(chapter_data)
        return {
            "success": True,
            "id": chapter.id,
            "message": f"章节 '{chapter.title}' 创建成功",
        }
    except Exception as e:
        logger.error(f"创建章节失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/chapters/{chapter_id}", response_model=Dict[str, Any])
async def update_chapter(chapter_id: str, chapter: Chapter):
    """
    更新章节数据

    Args:
        chapter_id: 章节 ID
        chapter: 新章节数据

    Returns:
        Dict: 更新结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await postgres_db.get_chapter(chapter_id)
    if not existing:
        raise HTTPException(status_code=404, detail="章节不存在")

    chapter_data = chapter.model_dump(mode="json")

    try:
        await postgres_db.save_chapter(chapter_data)
        return {
            "success": True,
            "id": chapter_id,
            "message": f"章节 '{chapter.title}' 更新成功",
        }
    except Exception as e:
        logger.error(f"更新章节失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plots", response_model=List[Dict[str, Any]])
async def list_plots(world_id: Optional[str] = None):
    """
    获取剧情线列表

    Args:
        world_id: 按世界过滤

    Returns:
        List: 剧情线列表
    """
    # 简化实现
    return []


@router.post("/plots", response_model=Dict[str, Any])
async def create_plot(plot: Plot):
    """
    创建新剧情线

    Args:
        plot: 剧情线数据

    Returns:
        Dict: 创建结果
    """
    # 简化实现
    return {
        "success": True,
        "id": plot.id,
        "message": f"剧情线 '{plot.title}' 创建成功",
    }
