"""
卷规划 API 路由
GodView v9: 卷级规划系统专用接口
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.skill import SkillTestResult
from app.services.skill_service import get_skill_service, ExecuteSkillDTO

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_structured_dict(result: SkillTestResult, error_detail: str) -> Dict[str, Any]:
    try:
        return result.require_structured_dict()
    except ValueError:
        text = result.output or result.text_output or ""
        candidates = re.findall(r"```json\s*([\s\S]*?)\s*```", text)
        candidates.append(text.strip())
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except (TypeError, json.JSONDecodeError):
                continue
        logger.warning("卷规划 Skill 返回了无效结构化输出: %s", text[:300])
        raise HTTPException(status_code=500, detail=error_detail)


def _context_packet_metadata(context_packet: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not context_packet:
        return None
    return {
        "packet_id": context_packet.get("packet_id"),
        "snapshot_id": context_packet.get("snapshot_id"),
        "snapshot_version": context_packet.get("snapshot_version"),
        **(context_packet.get("metadata") or {}),
    }


async def _build_volume_context_packet(
    *,
    project_id: str,
    volume_number: int,
    task_type: str,
    assistant_session_id: Optional[str],
    request_id: Optional[str],
    user_message: str,
    extra_scope: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    try:
        from app.api.app import postgres_db

        if not postgres_db:
            return None

        from app.services.assistant_context import get_assistant_context_fabric

        scope = {
            "volume_number": volume_number,
            "surface_entry": "volume_planning",
            "needs": ["project_brief", "chapter_outlines", "plot_hooks", "characters", "lore", "recent_deltas"],
            **(extra_scope or {}),
        }
        packet = await get_assistant_context_fabric(postgres_db).build_packet(
            project_id=project_id,
            assistant_surface="volume_planning",
            task_type=task_type,
            session_id=assistant_session_id,
            mode=f"volume:{volume_number}",
            request_id=request_id,
            scope=scope,
            user_message=user_message,
        )
        logger.info(
            "[VolumePlanning] 使用 Assistant Context Fabric packet=%s snapshot=v%s tokens=%s",
            packet.get("packet_id"),
            packet.get("snapshot_version"),
            packet.get("metadata", {}).get("token_estimate"),
        )
        return packet
    except Exception:
        logger.warning("构建 Volume Planning Assistant Context packet 失败", exc_info=True)
        return None


# ==================== 数据模型 ====================

class VolumeStatus(str):
    """卷状态"""
    DRAFT = "draft"
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"


# ==================== 请求/响应模型 ====================

class CreateVolumeRequest(BaseModel):
    """创建卷请求"""
    project_id: str
    volume_number: int = Field(..., ge=1)
    title: str
    summary: Optional[str] = None
    start_chapter: Optional[int] = None
    end_chapter: Optional[int] = None
    target_word_count: int = Field(default=50000)


class VolumeResponse(BaseModel):
    """卷响应"""
    success: bool
    volume: Dict[str, Any]
    suggestions: List[str]


class UpdateVolumeRequest(BaseModel):
    """更新卷请求"""
    title: Optional[str] = None
    summary: Optional[str] = None
    theme: Optional[str] = None
    start_chapter: Optional[int] = None
    end_chapter: Optional[int] = None
    target_word_count: Optional[int] = None
    status: Optional[str] = None


class VolumePlanRequest(BaseModel):
    """卷规划请求"""
    project_id: str
    volume_number: int
    book_outline: Optional[str] = None
    previous_volume_summary: Optional[str] = None
    target_words: int = Field(default=50000)
    assistant_session_id: Optional[str] = None
    request_id: Optional[str] = None


class VolumePlanResponse(BaseModel):
    """卷规划响应"""
    success: bool
    volume_info: Dict[str, Any]
    emotional_arc: Dict[str, Any]
    climax_design: Dict[str, Any]
    chapter_plan: List[Dict[str, Any]]
    transitions: Dict[str, Any]
    word_distribution: Dict[str, Any]
    assistant_session_id: Optional[str] = None
    context_packet: Optional[Dict[str, Any]] = None


class DesignClimaxRequest(BaseModel):
    """设计卷高潮请求"""
    project_id: Optional[str] = None
    volume_id: str
    climax_event: str
    emotional_peak: str
    participating_characters: List[str] = Field(default_factory=list)
    assistant_session_id: Optional[str] = None
    request_id: Optional[str] = None


class ClimaxDesignResponse(BaseModel):
    """卷高潮设计响应"""
    success: bool
    climax_chapter: int
    climax_description: str
    buildup_scenes: List[Dict[str, Any]]
    aftermath_scenes: List[Dict[str, Any]]
    assistant_session_id: Optional[str] = None
    context_packet: Optional[Dict[str, Any]] = None


class VolumeListResponse(BaseModel):
    """卷列表响应"""
    volumes: List[Dict[str, Any]]
    total: int


# ==================== 卷 API ====================

@router.post("/plan", response_model=VolumePlanResponse)
async def plan_volume(request: VolumePlanRequest):
    """
    规划卷大纲

    使用 AI 生成完整的卷规划
    """
    skill_service = get_skill_service()
    context_packet = await _build_volume_context_packet(
        project_id=request.project_id,
        volume_number=request.volume_number,
        task_type="plan_volume",
        assistant_session_id=request.assistant_session_id,
        request_id=request.request_id,
        user_message=f"规划第 {request.volume_number} 卷大纲",
        extra_scope={"target_words": request.target_words},
    )

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_volume_planning",
        project_id=request.project_id,
        parameters={
            "volume_number": request.volume_number,
            "book_outline": request.book_outline or "",
            "previous_volume": request.previous_volume_summary or "",
            "target_words": request.target_words,
            "assistant_context": context_packet.get("prompt_context") if context_packet else "",
            "assistant_context_packet_id": context_packet.get("packet_id") if context_packet else None,
            "assistant_context_snapshot_version": context_packet.get("snapshot_version") if context_packet else None,
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    data = _require_structured_dict(result, "解析规划结果失败")
    selected_volume = next(
        (volume for volume in data.get("volumes", []) if int(volume.get("number") or 0) == request.volume_number),
        (data.get("volumes") or [{}])[0] if isinstance(data.get("volumes"), list) and data.get("volumes") else {},
    ) if isinstance(data.get("volumes"), list) else {}
    volume_info = data.get("volume_info") or {
        "volume_number": selected_volume.get("number") or request.volume_number,
        "title": selected_volume.get("title") or f"第{request.volume_number}卷",
        "theme": selected_volume.get("theme") or "",
        "summary": selected_volume.get("summary") or data.get("main_arc", ""),
        "target_word_count": selected_volume.get("target_words") or request.target_words,
    }
    climax_design = data.get("climax_design") or {
        "climax_description": selected_volume.get("climax") or "",
    }
    return VolumePlanResponse(
        success=True,
        volume_info=volume_info,
        emotional_arc=data.get("emotional_arc", {}),
        climax_design=climax_design,
        chapter_plan=data.get("chapter_plan", []),
        transitions=data.get("transitions", {}),
        word_distribution=data.get("word_distribution", {}),
        assistant_session_id=context_packet.get("session_id") if context_packet else request.assistant_session_id,
        context_packet=_context_packet_metadata(context_packet),
    )


@router.post("", response_model=VolumeResponse)
async def create_volume(request: CreateVolumeRequest):
    """
    创建卷

    创建新的卷大纲
    """
    # TODO: 实现数据库存储
    volume_id = f"vol_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    volume = {
        "id": volume_id,
        "project_id": request.project_id,
        "volume_number": request.volume_number,
        "title": request.title,
        "summary": request.summary or "",
        "start_chapter": request.start_chapter,
        "end_chapter": request.end_chapter,
        "target_word_count": request.target_word_count,
        "status": "draft",
        "created_at": datetime.now().isoformat(),
    }

    return VolumeResponse(
        success=True,
        volume=volume,
        suggestions=[
            f"建议为第{request.volume_number}卷设计明确的主题",
            "考虑与前后卷的衔接和过渡",
        ]
    )


@router.get("", response_model=VolumeListResponse)
async def list_volumes(project_id: str):
    """
    获取卷列表

    返回项目的所有卷
    """
    # TODO: 从数据库获取
    return {
        "volumes": [],
        "total": 0,
    }


@router.get("/{volume_number}")
async def get_volume(project_id: str, volume_number: int):
    """
    获取卷详情
    """
    # TODO: 从数据库获取
    raise HTTPException(status_code=404, detail="卷不存在")


@router.put("/{volume_number}")
async def update_volume(project_id: str, volume_number: int, request: UpdateVolumeRequest):
    """
    更新卷信息
    """
    # TODO: 实现数据库更新
    return {"success": True, "message": f"卷 {volume_number} 已更新"}


@router.post("/{volume_number}/climax", response_model=ClimaxDesignResponse)
async def design_volume_climax(
    volume_number: int,
    request: DesignClimaxRequest,
    project_id: Optional[str] = None,
):
    """
    设计卷高潮

    为卷设计高潮场景和情绪峰值
    """
    request_project_id = project_id or request.project_id
    if not request_project_id:
        raise HTTPException(status_code=400, detail="project_id 是必填项")

    skill_service = get_skill_service()
    context_packet = await _build_volume_context_packet(
        project_id=request_project_id,
        volume_number=volume_number,
        task_type="design_climax",
        assistant_session_id=request.assistant_session_id,
        request_id=request.request_id,
        user_message=f"设计第 {volume_number} 卷高潮：{request.climax_event}",
        extra_scope={"volume_id": request.volume_id, "climax_event": request.climax_event},
    )

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_volume_planning",
        project_id=request_project_id,
        parameters={
            "task": "climax_design",
            "volume_number": volume_number,
            "climax_event": request.climax_event,
            "emotional_peak": request.emotional_peak,
            "participating_characters": request.participating_characters,
            "assistant_context": context_packet.get("prompt_context") if context_packet else "",
            "assistant_context_packet_id": context_packet.get("packet_id") if context_packet else None,
            "assistant_context_snapshot_version": context_packet.get("snapshot_version") if context_packet else None,
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    data = _require_structured_dict(result, "解析设计结果失败")
    return ClimaxDesignResponse(
        success=True,
        climax_chapter=data.get("climax_chapter", 0),
        climax_description=data.get("climax_description", ""),
        buildup_scenes=data.get("buildup_scenes", []),
        aftermath_scenes=data.get("aftermath_scenes", []),
        assistant_session_id=context_packet.get("session_id") if context_packet else request.assistant_session_id,
        context_packet=_context_packet_metadata(context_packet),
    )


@router.get("/{volume_number}/emotional-arc")
async def get_emotional_arc(project_id: str, volume_number: int):
    """
    获取卷情绪曲线

    返回卷的情绪起伏设计
    """
    # TODO: 从数据库获取
    return {
        "volume_number": volume_number,
        "arc_points": [
            {"chapter": 1, "emotion": "平静", "intensity": 0.3},
            {"chapter": 5, "emotion": "紧张", "intensity": 0.5},
            {"chapter": 10, "emotion": "高潮", "intensity": 0.9},
            {"chapter": 15, "emotion": "释然", "intensity": 0.4},
        ],
        "dominant_emotion": "紧张",
        "pacing_type": "渐进式",
    }


@router.post("/{volume_number}/activate")
async def activate_volume(project_id: str, volume_number: int):
    """
    激活卷

    将卷状态设为活跃（正在创作）
    """
    # TODO: 实现数据库更新
    return {
        "success": True,
        "volume_number": volume_number,
        "status": "active",
        "activated_at": datetime.now().isoformat(),
    }


@router.post("/{volume_number}/complete")
async def complete_volume(project_id: str, volume_number: int, actual_word_count: int):
    """
    完成卷

    标记卷为已完成
    """
    # TODO: 实现数据库更新
    return {
        "success": True,
        "volume_number": volume_number,
        "status": "completed",
        "completed_at": datetime.now().isoformat(),
        "actual_word_count": actual_word_count,
    }
