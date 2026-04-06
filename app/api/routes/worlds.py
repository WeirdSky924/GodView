"""
世界管理 API 路由
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.world import World, Region

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[Dict[str, Any]])
async def list_worlds(limit: int = Query(default=100, le=1000)):
    """
    获取世界列表

    Args:
        limit: 返回数量限制

    Returns:
        List: 世界列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 简单实现：查询所有世界（需要根据实际表结构）
    return []


@router.get("/{world_id}", response_model=Dict[str, Any])
async def get_world(world_id: str):
    """
    获取世界详情

    Args:
        world_id: 世界 ID

    Returns:
        Dict: 世界数据
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    world = await postgres_db.get_world(world_id)

    if not world:
        raise HTTPException(status_code=404, detail="世界不存在")

    return world


@router.post("", response_model=Dict[str, Any])
async def create_world(world: World):
    """
    创建新世界

    Args:
        world: 世界数据

    Returns:
        Dict: 创建结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    world_data = world.model_dump(mode="json")

    try:
        await postgres_db.save_world(world_data)
        return {
            "success": True,
            "id": world.id,
            "message": f"世界 '{world.name}' 创建成功",
        }
    except Exception as e:
        logger.error(f"创建世界失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{world_id}/regions", response_model=List[Dict[str, Any]])
async def list_regions(world_id: str):
    """
    获取世界的所有区域

    Args:
        world_id: 世界 ID

    Returns:
        List: 区域列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    regions = await postgres_db.get_regions_by_world(world_id)
    return regions


@router.post("/{world_id}/regions", response_model=Dict[str, Any])
async def create_region(world_id: str, region: Region):
    """
    创建新区域

    Args:
        world_id: 世界 ID
        region: 区域数据

    Returns:
        Dict: 创建结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    region_data = region.model_dump(mode="json")
    region_data["world_id"] = world_id

    try:
        await postgres_db.save_region(region_data)
        return {
            "success": True,
            "id": region.id,
            "message": f"区域 '{region.name}' 创建成功",
        }
    except Exception as e:
        logger.error(f"创建区域失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{world_id}/snapshots", response_model=List[Dict[str, Any]])
async def list_snapshots(world_id: str):
    """
    获取世界的所有快照

    Args:
        world_id: 世界 ID

    Returns:
        List: 快照列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    snapshots = await postgres_db.get_snapshots_by_world(world_id)
    return snapshots


@router.post("/{world_id}/snapshots", response_model=Dict[str, Any])
async def create_snapshot(world_id: str, snapshot_data: Dict[str, Any]):
    """
    创建世界快照

    Args:
        world_id: 世界 ID
        snapshot_data: 快照数据

    Returns:
        Dict: 创建结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    snapshot_data["world_id"] = world_id

    try:
        snapshot_id = await postgres_db.save_snapshot(snapshot_data)
        return {
            "success": True,
            "id": snapshot_id,
            "message": "快照创建成功",
        }
    except Exception as e:
        logger.error(f"创建快照失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{world_id}/rollback", response_model=Dict[str, Any])
async def rollback_to_snapshot(world_id: str, snapshot_id: str):
    """
    回档到指定快照

    Args:
        world_id: 世界 ID
        snapshot_id: 快照 ID

    Returns:
        Dict: 回档结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        snapshot = await postgres_db.rollback_to_snapshot(snapshot_id)
        return {
            "success": True,
            "message": f"已回档到快照 {snapshot_id}",
            "snapshot": snapshot,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"回档失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))
