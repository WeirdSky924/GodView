"""
角色深度 API
GodView v9: 角色深度系统

管理角色性格特质、成长弧线、关系网络等
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.models.character_depth import (
    PersonalityTrait,
    SpeakingStyle,
    GrowthArcPhase,
    GrowthArc,
    RelationshipType,
    CharacterRelationship,
    CharacterDepthProfile,
    CreateCharacterDepthDTO,
    UpdateCharacterDepthDTO,
    CreateGrowthArcDTO,
    UpdateGrowthArcDTO,
    CreateRelationshipDTO,
    UpdateRelationshipDTO,
)
from app.services.character_depth_service import CharacterDepthService

router = APIRouter(prefix="/api/character-depth", tags=["Character Depth"])

# 服务实例
_service: Optional[CharacterDepthService] = None


def get_service() -> CharacterDepthService:
    """获取服务实例"""
    global _service
    if _service is None:
        _service = CharacterDepthService()
    return _service


def set_service(service: CharacterDepthService):
    """设置服务实例"""
    global _service
    _service = service


# ==================== 角色深度档案 ====================

@router.get("/{character_id}", response_model=CharacterDepthProfile)
async def get_character_depth(character_id: str):
    """获取角色深度档案"""
    service = get_service()
    profile = await service.get_profile(character_id)
    if not profile:
        raise HTTPException(status_code=404, detail="角色深度档案不存在")
    return profile


@router.post("", response_model=CharacterDepthProfile)
async def create_character_depth(data: CreateCharacterDepthDTO):
    """创建角色深度档案"""
    service = get_service()
    profile = await service.create_profile(data)
    return profile


@router.put("/{character_id}", response_model=CharacterDepthProfile)
async def update_character_depth(character_id: str, data: UpdateCharacterDepthDTO):
    """更新角色深度档案"""
    service = get_service()
    profile = await service.update_profile(character_id, data)
    if not profile:
        raise HTTPException(status_code=404, detail="角色深度档案不存在")
    return profile


@router.post("/{character_id}/personality", response_model=CharacterDepthProfile)
async def add_personality_trait(character_id: str, trait: PersonalityTrait):
    """添加性格特质"""
    service = get_service()
    profile = await service.add_personality_trait(character_id, trait)
    if not profile:
        raise HTTPException(status_code=404, detail="角色深度档案不存在")
    return profile


@router.post("/{character_id}/speaking-style", response_model=CharacterDepthProfile)
async def set_speaking_style(character_id: str, style: SpeakingStyle):
    """设置说话风格"""
    service = get_service()
    profile = await service.set_speaking_style(character_id, style)
    if not profile:
        raise HTTPException(status_code=404, detail="角色深度档案不存在")
    return profile


@router.post("/{character_id}/secrets", response_model=CharacterDepthProfile)
async def add_secret(character_id: str, secret: str = Query(..., description="秘密内容")):
    """添加隐藏秘密"""
    service = get_service()
    profile = await service.add_secret(character_id, secret)
    if not profile:
        raise HTTPException(status_code=404, detail="角色深度档案不存在")
    return profile


# ==================== 成长弧线 ====================

@router.get("/{character_id}/growth-arcs", response_model=List[GrowthArc])
async def get_growth_arcs(character_id: str):
    """获取角色成长弧线"""
    service = get_service()
    arcs = await service.get_character_growth_arcs(character_id)
    return arcs


@router.post("/growth-arcs", response_model=GrowthArc)
async def create_growth_arc(data: CreateGrowthArcDTO):
    """创建成长弧线"""
    service = get_service()
    arc = await service.create_growth_arc(data)
    return arc


@router.get("/growth-arcs/{arc_id}", response_model=GrowthArc)
async def get_growth_arc(arc_id: str):
    """获取成长弧线详情"""
    service = get_service()
    arc = await service.get_growth_arc(arc_id)
    if not arc:
        raise HTTPException(status_code=404, detail="成长弧线不存在")
    return arc


@router.put("/growth-arcs/{arc_id}", response_model=GrowthArc)
async def update_growth_arc(arc_id: str, data: UpdateGrowthArcDTO):
    """更新成长弧线"""
    service = get_service()
    arc = await service.update_growth_arc(arc_id, data)
    if not arc:
        raise HTTPException(status_code=404, detail="成长弧线不存在")
    return arc


@router.post("/growth-arcs/{arc_id}/milestone", response_model=GrowthArc)
async def add_milestone(
    arc_id: str,
    chapter: int = Query(..., description="章节号"),
    event: str = Query(..., description="事件描述"),
    change: str = Query(..., description="变化内容")
):
    """添加成长里程碑"""
    service = get_service()
    arc = await service.add_milestone(arc_id, chapter, event, change)
    if not arc:
        raise HTTPException(status_code=404, detail="成长弧线不存在")
    return arc


@router.post("/growth-arcs/{arc_id}/turning-point", response_model=GrowthArc)
async def add_turning_point(
    arc_id: str,
    chapter: int = Query(..., description="章节号"),
    description: str = Query(..., description="转折描述"),
    impact: str = Query(..., description="影响")
):
    """添加转折点"""
    service = get_service()
    arc = await service.add_turning_point(arc_id, chapter, description, impact)
    if not arc:
        raise HTTPException(status_code=404, detail="成长弧线不存在")
    return arc


@router.post("/growth-arcs/{arc_id}/advance", response_model=GrowthArc)
async def advance_phase(arc_id: str, phase: GrowthArcPhase = Query(..., description="新阶段")):
    """推进成长阶段"""
    service = get_service()
    arc = await service.advance_phase(arc_id, phase)
    if not arc:
        raise HTTPException(status_code=404, detail="成长弧线不存在")
    return arc


# ==================== 角色关系 ====================

@router.get("/{character_id}/relationships", response_model=List[CharacterRelationship])
async def get_relationships(
    character_id: str,
    project_id: Optional[str] = Query(None, description="项目ID过滤")
):
    """获取角色关系网络"""
    service = get_service()
    relationships = await service.get_character_relationships(character_id, project_id)
    return relationships


@router.post("/relationships", response_model=CharacterRelationship)
async def create_relationship(data: CreateRelationshipDTO):
    """创建角色关系"""
    service = get_service()
    relationship = await service.create_relationship(data)
    return relationship


@router.get("/relationships/{relationship_id}", response_model=CharacterRelationship)
async def get_relationship(relationship_id: str):
    """获取关系详情"""
    service = get_service()
    relationship = await service.get_relationship(relationship_id)
    if not relationship:
        raise HTTPException(status_code=404, detail="关系不存在")
    return relationship


@router.put("/relationships/{relationship_id}", response_model=CharacterRelationship)
async def update_relationship(relationship_id: str, data: UpdateRelationshipDTO):
    """更新角色关系"""
    service = get_service()
    relationship = await service.update_relationship(relationship_id, data)
    if not relationship:
        raise HTTPException(status_code=404, detail="关系不存在")
    return relationship


@router.post("/relationships/{relationship_id}/strength", response_model=CharacterRelationship)
async def update_relationship_strength(
    relationship_id: str,
    delta: float = Query(..., description="强度变化量"),
    reason: str = Query(..., description="变化原因")
):
    """更新关系强度"""
    service = get_service()
    relationship = await service.update_relationship_strength(relationship_id, delta, reason)
    if not relationship:
        raise HTTPException(status_code=404, detail="关系不存在")
    return relationship


# ==================== 出场规则 ====================

@router.post("/{character_id}/appearance-rules", response_model=CharacterDepthProfile)
async def set_appearance_rules(
    character_id: str,
    project_id: str = Query(..., description="项目ID"),
    min_interval: int = Query(1, description="最小出场间隔"),
    max_absence: int = Query(5, description="最大缺席章数"),
    priority: int = Query(5, ge=1, le=10, description="出场优先级"),
    required_scenes: Optional[str] = Query(None, description="必须出场场景(逗号分隔)"),
    optional_scenes: Optional[str] = Query(None, description="可选出场场景(逗号分隔)")
):
    """设置出场规则"""
    service = get_service()
    profile = await service.set_appearance_rules(
        character_id,
        project_id,
        min_interval,
        max_absence,
        priority,
        required_scenes.split(",") if required_scenes else None,
        optional_scenes.split(",") if optional_scenes else None
    )
    return profile


@router.post("/{character_id}/appearance", response_model=CharacterDepthProfile)
async def record_appearance(
    character_id: str,
    chapter: int = Query(..., description="出场章节")
):
    """记录角色出场"""
    service = get_service()
    profile = await service.record_appearance(character_id, chapter)
    if not profile:
        raise HTTPException(status_code=404, detail="角色深度档案不存在")
    return profile


@router.get("/{character_id}/appearance-check", response_model=Dict[str, Any])
async def check_appearance_rules(
    character_id: str,
    current_chapter: int = Query(..., description="当前章节")
):
    """检查出场规则"""
    service = get_service()
    result = await service.check_appearance_rules(character_id, current_chapter)
    return result


# ==================== 分析功能 ====================

@router.get("/{character_id}/analyze", response_model=Dict[str, Any])
async def analyze_character_depth(character_id: str):
    """分析角色深度"""
    service = get_service()
    result = await service.analyze_character_depth(character_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
