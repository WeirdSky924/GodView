"""
世界管理 API 路由
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.world import Region, RegionType, TerrainType, World

logger = logging.getLogger(__name__)

router = APIRouter()


class WorldMapAgentGenerateRequest(BaseModel):
    """地图管理页调用 WorldMapManagerAgent 生成区域草稿的请求。"""

    project_id: str = Field(..., min_length=1)
    world_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=2, max_length=4000)
    task: str = Field(default="create_draft", pattern="^create_draft$")
    selected_region_id: Optional[str] = None
    generation_count: int = Field(default=3, ge=1, le=8)
    include_existing_regions: bool = True
    assistant_session_id: Optional[str] = None
    request_id: Optional[str] = None


VALID_REGION_TYPES = {item.value for item in RegionType}
VALID_TERRAIN_TYPES = {item.value for item in TerrainType}


def _normalize_region_data(region: Region, world_id: str, region_id: Optional[str] = None) -> Dict[str, Any]:
    """转换区域模型为数据库保存格式。"""
    import uuid

    region_data = region.model_dump(mode="json")
    region_data["world_id"] = world_id

    if region_id:
        region_data["id"] = region_id
    elif not region_data.get("id"):
        region_data["id"] = str(uuid.uuid4())

    if region_data.get("area_size") is None:
        region_data["area_size"] = 0.0
    if region_data.get("atmosphere") is None:
        region_data["atmosphere"] = ""
    if region_data.get("coordinates") is None:
        region_data["coordinates"] = {}

    return region_data


async def _get_region_for_world(postgres_db: Any, world_id: str, region_id: str) -> Dict[str, Any]:
    """获取区域并校验归属世界。"""
    region = await postgres_db.get_region(region_id)
    if not region or str(region.get("world_id")) != world_id:
        raise HTTPException(status_code=404, detail="区域不存在")
    return region


async def _record_region_delta(
    postgres_db: Any,
    *,
    project_id: Optional[str],
    region_data: Dict[str, Any],
    operation: str,
    before: Optional[Dict[str, Any]] = None,
) -> None:
    if not project_id:
        return
    try:
        from app.services.assistant_context import get_assistant_context_fabric

        await get_assistant_context_fabric(postgres_db).deltas.record_entity_change(
            project_id=str(project_id),
            entity_type="map_region",
            entity_id=str(region_data.get("id")),
            operation=operation,
            before=before,
            after=region_data if operation != "delete" else None,
            payload_summary={
                "title": region_data.get("name"),
                "world_id": region_data.get("world_id"),
                "region_type": region_data.get("region_type"),
                "terrain_type": region_data.get("terrain_type"),
            },
            source_table="regions",
            source_updated_at=region_data.get("updated_at") or region_data.get("created_at"),
        )
    except Exception:
        logger.warning("记录地图区域 Assistant Context delta 失败", exc_info=True)


def _normalize_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_object_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            normalized.append(dict(item))
        elif str(item).strip():
            normalized.append({"name": str(item).strip()})
    return normalized


def _normalize_coordinates(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    coordinates: Dict[str, float] = {}
    for key in ("x", "y"):
        raw_value = value.get(key)
        if isinstance(raw_value, (int, float)):
            coordinates[key] = float(raw_value)
    return coordinates


def _normalize_agent_draft_regions(
    agent_data: Dict[str, Any],
    existing_regions: List[Dict[str, Any]],
    generation_count: int,
) -> Dict[str, Any]:
    """把 Agent 输出规整为前端可编辑草稿；不做持久化。"""
    existing_by_id = {str(region.get("id")): region for region in existing_regions if region.get("id")}
    existing_name_to_ids: Dict[str, List[str]] = {}
    for region in existing_regions:
        name = str(region.get("name") or "").strip()
        region_id = str(region.get("id") or "").strip()
        if name and region_id:
            existing_name_to_ids.setdefault(name, []).append(region_id)

    draft_regions: List[Dict[str, Any]] = []
    for index, raw_region in enumerate((agent_data.get("regions") or [])[:generation_count], start=1):
        if not isinstance(raw_region, dict):
            continue

        name = str(raw_region.get("region_name") or raw_region.get("name") or "").strip()
        if not name:
            name = f"地图草稿 {index}"

        region_type = str(raw_region.get("region_type") or "custom").strip() or "custom"
        terrain_type = str(raw_region.get("terrain_type") or "custom").strip() or "custom"
        warnings = _normalize_string_list(raw_region.get("validation_warnings"))
        warnings.extend(_normalize_string_list(raw_region.get("validation_notes")))

        if region_type not in VALID_REGION_TYPES:
            warnings.append(f"未知区域类型 {region_type}，已按 custom 处理")
            region_type = "custom"
        if terrain_type not in VALID_TERRAIN_TYPES:
            warnings.append(f"未知地形类型 {terrain_type}，已按 custom 处理")
            terrain_type = "custom"

        connections: List[str] = []
        for connection in _normalize_string_list(raw_region.get("suggested_connections") or raw_region.get("connections")):
            if connection in existing_by_id:
                connections.append(connection)
                continue
            matched_ids = existing_name_to_ids.get(connection, [])
            if len(matched_ids) == 1:
                connections.append(matched_ids[0])
            elif len(matched_ids) > 1:
                warnings.append(f"连接「{connection}」匹配到多个区域，请手动选择")
            else:
                warnings.append(f"连接「{connection}」未匹配到现有区域，已保留为提示")

        draft_regions.append({
            "client_id": f"draft-{index}",
            "name": name,
            "region_type": region_type,
            "terrain_type": terrain_type,
            "description": str(raw_region.get("description") or "").strip(),
            "atmosphere": str(raw_region.get("atmosphere") or "").strip(),
            "coordinates": _normalize_coordinates(raw_region.get("coordinates")),
            "area_size": 0,
            "terrain_features": _normalize_object_list(raw_region.get("terrain_features")),
            "landmarks": _normalize_object_list(raw_region.get("landmarks")),
            "encounters": _normalize_object_list(raw_region.get("encounters")),
            "connections": list(dict.fromkeys(connections)),
            "local_rules": _normalize_string_list(raw_region.get("local_rules")),
            "importance": str(raw_region.get("importance") or "").strip(),
            "validation_warnings": list(dict.fromkeys(warnings)),
        })

    return {
        "overview": str(agent_data.get("overview") or "").strip(),
        "suggested_starting_location": str(agent_data.get("suggested_starting_location") or "").strip(),
        "draft_regions": draft_regions,
    }


async def _validate_world_parent(postgres_db: Any, world_data: Dict[str, Any], world_id: Optional[str] = None) -> None:
    """校验父级世界归属，避免跨项目和自引用。"""
    parent_world_id = world_data.get("parent_world_id")
    project_id = world_data.get("project_id")
    if not parent_world_id:
        return
    if world_id and str(parent_world_id) == str(world_id):
        raise HTTPException(status_code=400, detail="父级世界不能是自身")
    parent = await postgres_db.get_world(str(parent_world_id))
    if not parent:
        raise HTTPException(status_code=404, detail="父级世界不存在")
    if project_id and parent.get("project_id") and str(parent.get("project_id")) != str(project_id):
        raise HTTPException(status_code=400, detail="父级世界必须属于同一项目")


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
    from app.services.graph_projection_service import enqueue_graph_projection_best_effort
    from datetime import datetime

    logger.info(f"[Worlds] 收到更新请求: world_id={world_id}")

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await postgres_db.get_world(world_id)
    if not existing:
        raise HTTPException(status_code=404, detail="世界不存在")

    world_data = world.model_dump(mode="json")
    logger.info(f"[Worlds] 更新数据: content_styles={world_data.get('content_styles')}, protagonist_types={world_data.get('protagonist_types')}, power_types={world_data.get('power_types')}")

    await _validate_world_parent(postgres_db, world_data, world_id)

    # 确保使用正确的 ID 和时间戳
    world_data["id"] = world_id
    world_data["updated_at"] = datetime.now()

    # 保留原有的 created_at（如果存在）
    if existing.get("created_at"):
        world_data["created_at"] = existing["created_at"]

    try:
        await postgres_db.save_world(world_data)
        await enqueue_graph_projection_best_effort("world", world_data)
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
    from app.services.graph_projection_service import enqueue_graph_projection_best_effort
    import uuid
    from datetime import datetime

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    world_data = world.model_dump(mode="json")
    await _validate_world_parent(postgres_db, world_data)

    # 自动生成 ID（如果未提供）
    if not world_data.get("id"):
        world_data["id"] = str(uuid.uuid4())

    # 设置时间戳（使用 datetime 对象，不要转换为字符串）
    now = datetime.now()
    world_data["created_at"] = now
    world_data["updated_at"] = now

    try:
        await postgres_db.save_world(world_data)
        await enqueue_graph_projection_best_effort("world", world_data)
        return {
            "success": True,
            "id": world_data["id"],
            "message": f"世界 '{world.name}' 创建成功",
        }
    except Exception as e:
        logger.error(f"创建世界失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{world_id}/agent/generate", response_model=Dict[str, Any])
async def generate_world_map_drafts(world_id: str, request: WorldMapAgentGenerateRequest):
    """调用同一个 WorldMapManagerAgent 的地图页草稿场景，返回待用户确认的区域草稿。"""
    from app.api.app import postgres_db
    from app.agents.world_map_manager import WorldMapManagerAgent
    from app.services.model_router import create_model_factory

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")
    if str(request.world_id) != str(world_id):
        raise HTTPException(status_code=400, detail="请求 world_id 与路径不一致")

    world = await postgres_db.get_world(world_id)
    if not world:
        raise HTTPException(status_code=404, detail="世界不存在")
    if world.get("project_id") and str(world.get("project_id")) != str(request.project_id):
        raise HTTPException(status_code=400, detail="世界必须属于当前项目")

    existing_regions = await postgres_db.get_regions_by_world(world_id) if request.include_existing_regions else []
    selected_region = None
    if request.selected_region_id:
        selected_region = await _get_region_for_world(postgres_db, world_id, request.selected_region_id)

    context_packet = None
    try:
        from app.services.assistant_context import get_assistant_context_fabric

        context_packet = await get_assistant_context_fabric(postgres_db).build_packet(
            project_id=request.project_id,
            assistant_surface="world_map_agent",
            task_type="create_draft",
            session_id=request.assistant_session_id,
            mode=f"world:{world_id}",
            request_id=request.request_id,
            scope={
                "world_id": world_id,
                "selected_region_id": request.selected_region_id,
                "surface_entry": "world_map",
                "needs": ["map_regions", "world", "lore", "characters", "chapter_outlines", "recent_deltas"],
            },
            user_message=request.message,
        )
        logger.info(
            "[WorldMapAgent] 使用 Assistant Context Fabric packet=%s snapshot=v%s tokens=%s",
            context_packet.get("packet_id"),
            context_packet.get("snapshot_version"),
            context_packet.get("metadata", {}).get("token_estimate"),
        )
    except Exception:
        logger.warning("构建 World Map Assistant Context packet 失败", exc_info=True)

    try:
        model = create_model_factory(max_tokens=3000, temperature=0.65)()
        agent = WorldMapManagerAgent(
            model=model,
            project_id=request.project_id,
            agent_id="world_map_manager_page",
            scenario="world_map_draft_generation",
        )
        await agent.load_memory(postgres_db)
        result = await agent.execute({
            "task": request.task or "create_draft",
            "world_info": {
                **world,
                "user_request": request.message,
                "selected_region": selected_region,
                "requested_region_count": request.generation_count,
                "generation_count": request.generation_count,
                "assistant_context": context_packet.get("prompt_context") if context_packet else "",
                "assistant_context_packet_id": context_packet.get("packet_id") if context_packet else None,
            },
            "chapter_outline": request.message,
            "existing_regions": existing_regions,
        })
    except Exception as e:
        logger.error("地图 Agent 草稿生成失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "地图 Agent 草稿生成失败")

    if context_packet:
        try:
            from app.services.assistant_context import get_assistant_context_fabric

            assistant_session = await postgres_db.get_assistant_session(context_packet.get("session_id"))
            if assistant_session:
                await get_assistant_context_fabric(postgres_db).sessions.append_message(
                    session=assistant_session,
                    role="assistant",
                    content=str(result.data or {}),
                    request_id=request.request_id,
                    metadata={"context_packet_id": context_packet.get("packet_id"), "surface_entry": "world_map"},
                    packet_id=context_packet.get("packet_id"),
                    snapshot_id=context_packet.get("snapshot_id"),
                )
        except Exception:
            logger.warning("记录 World Map Assistant Context 助手回复失败", exc_info=True)

    normalized = _normalize_agent_draft_regions(result.data or {}, existing_regions, request.generation_count)
    return {
        "success": True,
        "message": "地图 Agent 已生成区域草稿，保存前不会修改地图",
        **normalized,
        "matched_existing_region_ids": sorted({connection for draft in normalized["draft_regions"] for connection in draft.get("connections", [])}),
        "assistant_session_id": context_packet.get("session_id") if context_packet else None,
        "context_packet": {
            "packet_id": context_packet.get("packet_id"),
            "snapshot_id": context_packet.get("snapshot_id"),
            "snapshot_version": context_packet.get("snapshot_version"),
            **(context_packet.get("metadata") or {}),
        } if context_packet else None,
        "metadata": {
            **(result.metadata or {}),
            "agent_type": "world_map_manager",
            "scenario": "world_map_draft_generation",
            "template_id": (result.metadata or {}).get("prompt_render_trace", {}).get("template_id"),
            "context_packet_id": context_packet.get("packet_id") if context_packet else None,
        },
    }


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
    from app.services.graph_projection_service import enqueue_graph_projection_best_effort

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    region_data = _normalize_region_data(region, world_id)

    logger.info(f"Region data keys: {list(region_data.keys())}")

    try:
        await postgres_db.save_region(region_data)
        await enqueue_graph_projection_best_effort("region", region_data)
        world = await postgres_db.get_world(world_id)
        await _record_region_delta(postgres_db, project_id=str(world.get("project_id")) if world else None, region_data=region_data, operation="create")
        return {
            "success": True,
            "id": region_data["id"],
            "message": f"区域 '{region.name}' 创建成功",
        }
    except Exception as e:
        logger.error(f"创建区域失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{world_id}/regions/{region_id}", response_model=Dict[str, Any])
async def get_region(world_id: str, region_id: str):
    """获取区域详情"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    return await _get_region_for_world(postgres_db, world_id, region_id)


@router.put("/{world_id}/regions/{region_id}", response_model=Dict[str, Any])
async def update_region(world_id: str, region_id: str, region: Region):
    """更新区域"""
    from app.api.app import postgres_db
    from app.services.graph_projection_service import enqueue_graph_projection_best_effort
    from datetime import datetime

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await _get_region_for_world(postgres_db, world_id, region_id)
    region_data = _normalize_region_data(region, world_id, region_id)

    if existing.get("created_at"):
        region_data["created_at"] = existing["created_at"]
    region_data["updated_at"] = datetime.now()

    try:
        await postgres_db.save_region(region_data)
        await enqueue_graph_projection_best_effort("region", region_data)
        world = await postgres_db.get_world(world_id)
        await _record_region_delta(postgres_db, project_id=str(world.get("project_id")) if world else None, region_data=region_data, operation="update", before=existing)
        return {"success": True, "id": region_id, "message": f"区域 '{region.name}' 更新成功"}
    except Exception as e:
        logger.error(f"更新区域失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{world_id}/regions/{region_id}", response_model=Dict[str, Any])
async def delete_region(world_id: str, region_id: str):
    """删除区域"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await _get_region_for_world(postgres_db, world_id, region_id)
    deleted = await postgres_db.delete_region(region_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="区域不存在")
    world = await postgres_db.get_world(world_id)
    await _record_region_delta(postgres_db, project_id=str(world.get("project_id")) if world else None, region_data=existing, operation="delete", before=existing)
    return {"success": True, "id": region_id, "message": f"区域 {region_id} 已删除"}


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
