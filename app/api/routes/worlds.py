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
async def list_worlds(
    project_id: Optional[str] = Query(None, description="按项目 ID 过滤"),
    limit: int = Query(default=100, le=1000),
):
    """
    获取世界列表

    Args:
        project_id: 按项目 ID 过滤
        limit: 返回数量限制

    Returns:
        List: 世界列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    worlds = await postgres_db.get_all_worlds(project_id=project_id, limit=limit)
    return worlds


@router.put("/{world_id}", response_model=Dict[str, Any])
async def update_world(world_id: str, world: World):
    """更新世界数据"""
    from app.api.app import postgres_db
    from datetime import datetime

    logger.info(f"[Worlds] 收到更新请求: world_id={world_id}")

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await postgres_db.get_world(world_id)
    if not existing:
        raise HTTPException(status_code=404, detail="世界不存在")

    world_data = world.model_dump(mode="json")
    logger.info(f"[Worlds] 更新数据: content_styles={world_data.get('content_styles')}, protagonist_types={world_data.get('protagonist_types')}, power_types={world_data.get('power_types')}")

    # 确保使用正确的 ID 和时间戳
    world_data["id"] = world_id
    world_data["updated_at"] = datetime.now()

    # 保留原有的 created_at（如果存在）
    if existing.get("created_at"):
        world_data["created_at"] = existing["created_at"]

    try:
        await postgres_db.save_world(world_data)
        logger.info(f"[Worlds] 世界 '{world.name}' 更新成功")
        return {"success": True, "id": world_id, "message": f"世界 '{world.name}' 更新成功"}
    except Exception as e:
        logger.error(f"更新世界失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{world_id}", response_model=Dict[str, Any])
async def delete_world(world_id: str):
    """删除世界"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    await postgres_db.delete_world(world_id)
    return {"success": True, "message": f"世界 {world_id} 已删除"}


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
    import uuid
    from datetime import datetime

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    world_data = world.model_dump(mode="json")

    # 自动生成 ID（如果未提供）
    if not world_data.get("id"):
        world_data["id"] = str(uuid.uuid4())

    # 设置时间戳（使用 datetime 对象，不要转换为字符串）
    now = datetime.now()
    world_data["created_at"] = now
    world_data["updated_at"] = now

    try:
        await postgres_db.save_world(world_data)
        return {
            "success": True,
            "id": world_data["id"],
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
    import uuid

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    region_data = region.model_dump(mode="json")
    region_data["world_id"] = world_id

    # 确保所有字段都有值（数据库需要）
    if region_data.get("area_size") is None:
        region_data["area_size"] = 0.0
    if region_data.get("atmosphere") is None:
        region_data["atmosphere"] = ""
    if region_data.get("coordinates") is None:
        region_data["coordinates"] = {}

    # 确保 encounters 被序列化为 JSON 字符串
    if "encounters" in region_data and isinstance(region_data["encounters"], list):
        import json
        region_data["encounters"] = json.dumps(region_data["encounters"])

    # 自动生成 ID（如果未提供）
    if not region_data.get("id"):
        region_data["id"] = str(uuid.uuid4())

    logger.info(f"Region data keys: {list(region_data.keys())}")

    try:
        await postgres_db.save_region(region_data)
        return {
            "success": True,
            "id": region_data["id"],
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
    import uuid
    from datetime import datetime
    import json

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 自动生成 ID（如果未提供）
    if not snapshot_data.get("id"):
        snapshot_data["id"] = str(uuid.uuid4())

    snapshot_data["world_id"] = world_id
    snapshot_data["created_at"] = datetime.utcnow().isoformat()

    # 设置默认值 - JSON 字段需要序列化
    snapshot_data.setdefault("chapter_id", None)
    snapshot_data.setdefault("snapshot_type", "manual")
    snapshot_data.setdefault("characters", {})
    snapshot_data.setdefault("relationships", {})
    snapshot_data.setdefault("regions", {})
    snapshot_data.setdefault("hooks", {})
    snapshot_data.setdefault("main_plot_progress", 0.0)
    snapshot_data.setdefault("completed_events", [])
    snapshot_data.setdefault("character_locations", {})
    snapshot_data.setdefault("created_by", "system")
    snapshot_data.setdefault("parent_snapshot_id", None)
    snapshot_data.setdefault("is_branch", False)
    snapshot_data.setdefault("branch_reason", None)

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
