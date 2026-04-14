"""
世界观层次展开 API
GodView v9: 世界观层次展开系统

管理地图升级路线、势力更迭、战力天花板等数据
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.models.world_expansion import (
    MapLevel,
    ForceStatus,
    WorldMapLevel,
    ForceFaction,
    PowerCeiling,
    InformationLevel,
    CreateWorldMapLevelDTO,
    CreateForceFactionDTO,
    UpdateForceFactionDTO,
    CreatePowerCeilingDTO,
    CreateInformationLevelDTO,
    WorldExpansionSummary,
)
from app.services.world_expansion_service import WorldExpansionService

router = APIRouter(prefix="/api/world-expansion", tags=["World Expansion"])

# 服务实例
_service: Optional[WorldExpansionService] = None


def get_service() -> WorldExpansionService:
    """获取服务实例"""
    global _service
    if _service is None:
        _service = WorldExpansionService()
    return _service


# ==================== 地图等级管理 ====================

@router.get("/maps", response_model=List[WorldMapLevel])
async def get_map_levels(project_id: str = Query(..., description="项目ID")):
    """获取地图等级列表"""
    service = get_service()
    return await service.get_map_levels(project_id)


@router.post("/maps", response_model=WorldMapLevel)
async def create_map_level(data: CreateWorldMapLevelDTO):
    """创建地图等级"""
    service = get_service()
    return await service.create_map_level(data)


@router.get("/maps/{level_id}", response_model=WorldMapLevel)
async def get_map_level(level_id: str):
    """获取地图等级详情"""
    service = get_service()
    level = await service.get_map_level(level_id)
    if not level:
        raise HTTPException(status_code=404, detail="地图等级不存在")
    return level


@router.put("/maps/{level_id}", response_model=WorldMapLevel)
async def update_map_level(level_id: str, data: Dict[str, Any]):
    """更新地图等级"""
    service = get_service()
    level = await service.update_map_level(level_id, data)
    if not level:
        raise HTTPException(status_code=404, detail="地图等级不存在")
    return level


@router.delete("/maps/{level_id}")
async def delete_map_level(level_id: str):
    """删除地图等级"""
    service = get_service()
    success = await service.delete_map_level(level_id)
    if not success:
        raise HTTPException(status_code=404, detail="地图等级不存在")
    return {"success": True}


# ==================== 势力管理 ====================

@router.get("/forces", response_model=List[ForceFaction])
async def get_forces(
    project_id: str = Query(..., description="项目ID"),
    status: Optional[ForceStatus] = Query(None, description="势力状态过滤")
):
    """获取势力列表"""
    service = get_service()
    return await service.get_forces(project_id, status)


@router.post("/forces", response_model=ForceFaction)
async def create_force(data: CreateForceFactionDTO):
    """创建势力"""
    service = get_service()
    return await service.create_force(data)


@router.get("/forces/{force_id}", response_model=ForceFaction)
async def get_force(force_id: str):
    """获取势力详情"""
    service = get_service()
    force = await service.get_force(force_id)
    if not force:
        raise HTTPException(status_code=404, detail="势力不存在")
    return force


@router.put("/forces/{force_id}", response_model=ForceFaction)
async def update_force(force_id: str, data: UpdateForceFactionDTO):
    """更新势力"""
    service = get_service()
    force = await service.update_force(force_id, data)
    if not force:
        raise HTTPException(status_code=404, detail="势力不存在")
    return force


@router.post("/forces/{force_id}/status")
async def update_force_status(
    force_id: str,
    new_status: ForceStatus = Query(..., description="新状态"),
    chapter: int = Query(..., description="发生章节")
):
    """更新势力状态"""
    service = get_service()
    force = await service.update_force_status(force_id, new_status, chapter)
    if not force:
        raise HTTPException(status_code=404, detail="势力不存在")
    return force


@router.post("/forces/{force_id}/relationship")
async def add_force_relationship(
    force_id: str,
    relationship_type: str = Query(..., description="关系类型: ally/enemy"),
    target_force_id: str = Query(..., description="目标势力ID")
):
    """添加势力关系"""
    service = get_service()
    force = await service.add_force_relationship(force_id, relationship_type, target_force_id)
    if not force:
        raise HTTPException(status_code=404, detail="势力不存在")
    return force


@router.delete("/forces/{force_id}")
async def delete_force(force_id: str):
    """删除势力"""
    service = get_service()
    success = await service.delete_force(force_id)
    if not success:
        raise HTTPException(status_code=404, detail="势力不存在")
    return {"success": True}


# ==================== 战力天花板管理 ====================

@router.get("/power-ceilings", response_model=List[PowerCeiling])
async def get_power_ceilings(project_id: str = Query(..., description="项目ID")):
    """获取战力天花板列表"""
    service = get_service()
    return await service.get_power_ceilings(project_id)


@router.get("/power-ceilings/current")
async def get_current_power_ceiling(
    project_id: str = Query(..., description="项目ID"),
    current_chapter: int = Query(1, description="当前章节")
):
    """获取当前章节的战力天花板"""
    service = get_service()
    ceiling = await service.get_current_power_ceiling(project_id, current_chapter)
    if not ceiling:
        raise HTTPException(status_code=404, detail="未找到对应战力天花板")
    return ceiling


@router.post("/power-ceilings", response_model=PowerCeiling)
async def create_power_ceiling(data: CreatePowerCeilingDTO):
    """创建战力天花板"""
    service = get_service()
    return await service.create_power_ceiling(data)


@router.put("/power-ceilings/{ceiling_id}", response_model=PowerCeiling)
async def update_power_ceiling(ceiling_id: str, data: Dict[str, Any]):
    """更新战力天花板"""
    service = get_service()
    ceiling = await service.update_power_ceiling(ceiling_id, data)
    if not ceiling:
        raise HTTPException(status_code=404, detail="战力天花板不存在")
    return ceiling


# ==================== 信息层级管理 ====================

@router.get("/information", response_model=List[InformationLevel])
async def get_information_levels(
    project_id: str = Query(..., description="项目ID"),
    info_type: Optional[str] = Query(None, description="信息类型过滤")
):
    """获取信息层级列表"""
    service = get_service()
    return await service.get_information_levels(project_id, info_type)


@router.get("/information/pending-reveals")
async def get_pending_reveals(
    project_id: str = Query(..., description="项目ID"),
    current_chapter: int = Query(1, description="当前章节")
):
    """获取当前应该揭示的信息"""
    service = get_service()
    return await service.get_pending_reveals(project_id, current_chapter)


@router.post("/information", response_model=InformationLevel)
async def create_information_level(data: CreateInformationLevelDTO):
    """创建信息层级"""
    service = get_service()
    return await service.create_information_level(data)


@router.put("/information/{info_id}", response_model=InformationLevel)
async def update_information_level(info_id: str, data: Dict[str, Any]):
    """更新信息层级"""
    service = get_service()
    info = await service.update_information_level(info_id, data)
    if not info:
        raise HTTPException(status_code=404, detail="信息层级不存在")
    return info


# ==================== 综合功能 ====================

@router.get("/summary", response_model=WorldExpansionSummary)
async def get_expansion_summary(
    project_id: str = Query(..., description="项目ID"),
    current_chapter: int = Query(1, description="当前章节")
):
    """获取世界观展开摘要"""
    service = get_service()
    return await service.get_expansion_summary(project_id, current_chapter)


@router.get("/analysis/force-changes")
async def analyze_force_changes(
    project_id: str = Query(..., description="项目ID"),
    start_chapter: int = Query(1, description="起始章节"),
    end_chapter: int = Query(10, description="结束章节")
):
    """分析章节区间的势力变化"""
    service = get_service()
    return await service.analyze_force_changes(project_id, start_chapter, end_chapter)