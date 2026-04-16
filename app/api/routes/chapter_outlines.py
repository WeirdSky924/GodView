"""
章节大纲 API 路由
GodView v9: PlotOutlineAgent 专用接口
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.chapter_outline import (
    ChapterOutline,
    ChapterOutlineStatus,
    CreateChapterOutlineDTO,
    UpdateChapterOutlineDTO,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    ValidateOutlineRequest,
    ValidateOutlineResponse,
    SceneOutline,
    EmotionCurve,
)
from app.services.plot_outline_service import get_plot_outline_service, set_plot_outline_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class GenerateOutlineRequestAPI(BaseModel):
    """生成大纲请求"""
    project_id: str
    chapter_number: int = Field(..., ge=1, description="章节号")
    context: Optional[str] = Field(None, description="上下文信息")
    previous_events: Optional[str] = Field(None, description="前文事件")
    special_requirements: Optional[List[str]] = Field(None, description="特殊要求")


class CreateOutlineRequest(BaseModel):
    """创建大纲请求"""
    project_id: str
    chapter_number: int = Field(..., ge=1)
    title: str
    summary: str
    chapter_goals: List[str] = Field(default_factory=list)
    target_word_count: int = Field(default=3000)


class UpdateOutlineRequest(BaseModel):
    """更新大纲请求"""
    title: Optional[str] = None
    summary: Optional[str] = None
    chapter_goals: Optional[List[str]] = None
    status: Optional[str] = None
    target_word_count: Optional[int] = None


class OutlineListResponse(BaseModel):
    """大纲列表响应"""
    outlines: List[ChapterOutline]
    total: int


class OutlineStatisticsResponse(BaseModel):
    """大纲统计响应"""
    total_outlines: int
    total_target_words: int
    status_distribution: Dict[str, int]
    average_scenes_per_chapter: float
    hooks_planned: int
    hooks_resolved: int


class ApproveOutlineRequest(BaseModel):
    """审批大纲请求"""
    approved_by: str


class PendingOutline(BaseModel):
    """待确认的大纲数据"""
    chapter_number: int = Field(..., description="章节号")
    title: str = Field(..., description="章节标题")
    summary: str = Field(..., description="章节摘要")
    scenes: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="场景列表")
    emotion_curve: Optional[Dict[str, Any]] = Field(None, description="情绪曲线")
    chapter_goals: Optional[List[str]] = Field(default_factory=list, description="章节目标")
    hooks_planted: Optional[List[str]] = Field(default_factory=list, description="本章埋设的伏笔")
    hooks_resolved: Optional[List[str]] = Field(default_factory=list, description="本章回收的伏笔")
    target_word_count: Optional[int] = Field(default=3000, description="目标字数")
    character_arcs: Optional[Dict[str, str]] = Field(default_factory=dict, description="角色发展")


class ChatRequest(BaseModel):
    """与 Agent 聊天请求"""
    message: str
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Agent 聊天响应"""
    message: str
    outline_updates: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    pending_outlines: Optional[List[PendingOutline]] = None
    saved_outline: Optional[Dict[str, Any]] = None
    saved_outlines: Optional[List[Dict[str, Any]]] = None  # 多章大纲保存


class SavePendingOutlinesRequest(BaseModel):
    """保存待确认大纲请求"""
    outlines: List[PendingOutline]


class SavePendingOutlinesResponse(BaseModel):
    """保存待确认大纲响应"""
    success: bool
    saved_count: int
    message: str


# ==================== API 端点 ====================

@router.get("", response_model=OutlineListResponse)
async def list_outlines(project_id: str):
    """
    获取章节大纲列表

    返回项目下所有章节大纲
    """
    service = get_plot_outline_service()
    outlines = await service.get_outlines_by_project(project_id)
    return OutlineListResponse(
        outlines=outlines,
        total=len(outlines),
    )


@router.get("/statistics", response_model=OutlineStatisticsResponse)
async def get_statistics(project_id: str):
    """
    获取大纲统计信息

    返回项目的章节大纲统计数据
    """
    service = get_plot_outline_service()
    stats = await service.get_outline_statistics(project_id)
    return OutlineStatisticsResponse(**stats)


@router.get("/{chapter_number}")
async def get_outline(project_id: str, chapter_number: int):
    """
    获取指定章节的大纲

    Args:
        project_id: 项目ID
        chapter_number: 章节号
    """
    service = get_plot_outline_service()
    outline = await service.get_outline(project_id, chapter_number)

    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    return outline


@router.post("/{chapter_number}/generate", response_model=GenerateOutlineResponse)
async def generate_outline(project_id: str, chapter_number: int, request: GenerateOutlineRequestAPI):
    """
    生成章节大纲

    使用 AI 自动生成章节大纲
    """
    service = get_plot_outline_service()
    result = await service.generate_outline(
        project_id=project_id,
        chapter_number=chapter_number,
        context=request.context,
        previous_events=request.previous_events,
    )
    return result


@router.post("/{chapter_number}")
async def create_outline(project_id: str, chapter_number: int, request: CreateOutlineRequest):
    """
    创建章节大纲

    手动创建新的章节大纲
    """
    service = get_plot_outline_service()

    # 检查是否已存在
    existing = await service.get_outline(project_id, chapter_number)
    if existing:
        raise HTTPException(status_code=400, detail="该章节大纲已存在")

    outline = await service.create_outline(CreateChapterOutlineDTO(
        project_id=project_id,
        chapter_number=chapter_number,
        title=request.title,
        summary=request.summary,
        chapter_goals=request.chapter_goals,
        target_word_count=request.target_word_count,
    ))

    return outline


@router.put("/{chapter_number}")
async def update_outline(project_id: str, chapter_number: int, request: UpdateOutlineRequest):
    """
    更新章节大纲

    更新现有的章节大纲
    """
    service = get_plot_outline_service()
    outline = await service.get_outline(project_id, chapter_number)

    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    update_dto = UpdateChapterOutlineDTO()
    if request.title:
        update_dto.title = request.title
    if request.summary:
        update_dto.summary = request.summary
    if request.chapter_goals:
        update_dto.chapter_goals = request.chapter_goals
    if request.status:
        try:
            update_dto.status = ChapterOutlineStatus(request.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的状态: {request.status}")
    if request.target_word_count:
        update_dto.target_word_count = request.target_word_count

    updated = await service.update_outline(outline.id, update_dto)
    return updated


@router.post("/{chapter_number}/validate", response_model=ValidateOutlineResponse)
async def validate_outline(project_id: str, chapter_number: int):
    """
    验证章节大纲

    检查大纲的完整性和合理性
    """
    service = get_plot_outline_service()
    outline = await service.get_outline(project_id, chapter_number)

    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    result = await service.validate_outline(project_id, outline)
    return result


@router.post("/{chapter_number}/approve")
async def approve_outline(project_id: str, chapter_number: int, request: ApproveOutlineRequest):
    """
    审批章节大纲

    将大纲状态更新为已审批
    """
    service = get_plot_outline_service()
    outline = await service.get_outline(project_id, chapter_number)

    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    updated = await service.approve_outline(outline.id, request.approved_by)
    return updated


@router.delete("/{chapter_number}")
async def delete_outline(project_id: str, chapter_number: int):
    """
    删除章节大纲

    删除指定的章节大纲
    """
    service = get_plot_outline_service()
    outline = await service.get_outline(project_id, chapter_number)

    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    success = await service.delete_outline(outline.id)

    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    return {"success": True, "message": f"第{chapter_number}章大纲已删除"}


@router.post("/{chapter_number}/chat", response_model=ChatResponse)
async def chat_with_agent(project_id: str, chapter_number: int, request: ChatRequest):
    """
    与 Plot Outline Agent 聊天

    协作生成或修改章节大纲
    """
    service = get_plot_outline_service()

    # 获取现有大纲作为上下文
    existing_outline = await service.get_outline(project_id, chapter_number)

    # 调用 Agent 进行协作
    response = await service.chat_with_agent(
        project_id=project_id,
        chapter_number=chapter_number,
        message=request.message,
        existing_outline=existing_outline,
        context=request.context,
    )

    # 处理 pending_outlines
    pending_outlines = None
    if response.get("pending_outlines"):
        pending_outlines = [PendingOutline(**o) for o in response["pending_outlines"]]

    return ChatResponse(
        message=response.get("message", ""),
        outline_updates=response.get("outline_updates"),
        suggestions=response.get("suggestions"),
        pending_outlines=pending_outlines,
        saved_outline=response.get("saved_outline"),
        saved_outlines=response.get("saved_outlines"),
    )


@router.post("/save-outlines", response_model=SavePendingOutlinesResponse)
async def save_pending_outlines(
    project_id: str = Query(..., description="项目ID"),
    request: SavePendingOutlinesRequest = None,
):
    """
    保存待确认的大纲

    将用户确认的大纲保存到数据库
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    if not request or not request.outlines:
        return SavePendingOutlinesResponse(
            success=True,
            saved_count=0,
            message="没有需要保存的大纲"
        )

    service = get_plot_outline_service()
    saved_count = 0

    for pending in request.outlines:
        try:
            # 检查是否已存在该章节大纲
            existing = await service.get_outline(project_id, pending.chapter_number)

            if existing:
                # 更新现有大纲
                update_data = {
                    "title": pending.title,
                    "summary": pending.summary,
                    "scenes": [SceneOutline(**s) for s in pending.scenes] if pending.scenes else [],
                    "emotion_curve": EmotionCurve(**pending.emotion_curve) if pending.emotion_curve else None,
                    "chapter_goals": pending.chapter_goals or [],
                    "hooks_planted": pending.hooks_planted or [],
                    "hooks_resolved": pending.hooks_resolved or [],
                    "target_word_count": pending.target_word_count or 3000,
                    "character_arcs": pending.character_arcs or {},
                    "status": ChapterOutlineStatus.DRAFT,
                }
                await service.update_outline(existing.id, UpdateChapterOutlineDTO(**update_data))
            else:
                # 创建新大纲
                outline = ChapterOutline(
                    project_id=project_id,
                    chapter_number=pending.chapter_number,
                    title=pending.title,
                    summary=pending.summary,
                    scenes=[SceneOutline(**s) for s in pending.scenes] if pending.scenes else [],
                    emotion_curve=EmotionCurve(**pending.emotion_curve) if pending.emotion_curve else None,
                    chapter_goals=pending.chapter_goals or [],
                    hooks_planted=pending.hooks_planted or [],
                    hooks_resolved=pending.hooks_resolved or [],
                    target_word_count=pending.target_word_count or 3000,
                    character_arcs=pending.character_arcs or {},
                    status=ChapterOutlineStatus.DRAFT,
                )
                await service.create_outline(outline)
            saved_count += 1
        except Exception as e:
            logger.error(f"保存大纲失败 (章节 {pending.chapter_number}): {e}")

    return SavePendingOutlinesResponse(
        success=True,
        saved_count=saved_count,
        message=f"成功保存 {saved_count} 个大纲" if saved_count > 0 else "没有保存任何大纲"
    )


# ==================== 服务注入 ====================

def set_service(service):
    """设置服务实例（用于依赖注入）"""
    set_plot_outline_service(service)
