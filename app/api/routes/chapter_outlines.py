"""
章节大纲 API 路由
GodView v9: PlotOutlineAgent 专用接口
"""

import json
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


class UpdateResourceRequirementStatusRequest(BaseModel):
    """更新资源需求状态请求"""
    status: str = Field(..., description="pending/in_progress/resolved/ignored/superseded")
    matched_resource_id: Optional[str] = Field(None, description="绑定的资源 ID")
    matched_resource_type: Optional[str] = Field(None, description="绑定的资源类型")


class GenerateResourceSupplementDraftsRequest(BaseModel):
    """生成资源补全草案请求"""
    project_id: str = Field(..., description="项目ID")
    requirement_ids: Optional[List[str]] = Field(None, description="指定资源需求 ID；为空则按过滤条件生成")
    outline_id: Optional[str] = Field(None, description="大纲 ID")
    chapter_num: Optional[int] = Field(None, description="章节号")
    include_advisory: bool = Field(False, description="是否包含 advisory 需求")


class ConfirmResourceSupplementDraft(BaseModel):
    """确认创建的资源补全草案"""
    requirement_id: str
    resource_type: str
    draft_payload: Dict[str, Any]


class ConfirmResourceSupplementDraftsRequest(BaseModel):
    """确认资源补全草案请求"""
    project_id: str = Field(..., description="项目ID")
    drafts: List[ConfirmResourceSupplementDraft]


# ==================== API 端点 ====================


def _build_resource_supplement_draft(requirement: Dict[str, Any]) -> Dict[str, Any]:
    """把资源需求转换成可审查的补全草案；不直接创建资源。"""
    requirement_type = str(requirement.get("requirement_type") or "lore").strip().lower()
    resource_name = str(requirement.get("resource_name") or "未命名资源").strip()
    reason = str(requirement.get("reason") or requirement.get("source_excerpt") or "").strip()
    suggested_payload = requirement.get("suggested_payload") if isinstance(requirement.get("suggested_payload"), dict) else {}
    base_payload = {
        "name": resource_name,
        "title": resource_name,
        "project_id": str(requirement.get("project_id")),
        "description": reason or f"由第 {requirement.get('chapter_num') or '未知'} 章大纲资源需求生成的补全草案。",
        "source_requirement_id": str(requirement.get("id")),
        "source_chapter_num": requirement.get("chapter_num"),
        "source_outline_id": requirement.get("outline_id"),
        "usage_guidance": reason,
        **suggested_payload,
    }

    if requirement_type in {"character", "role", "人物", "角色"}:
        resource_type = "character"
        payload = {
            **base_payload,
            "role": suggested_payload.get("role") or "supporting",
            "status": suggested_payload.get("status") or "active",
            "background": suggested_payload.get("background") or reason,
            "personality": suggested_payload.get("personality") or "待用户确认",
            "importance_tier": suggested_payload.get("importance_tier") or "supporting",
        }
    elif requirement_type in {"location", "place", "地点", "场景地点"}:
        resource_type = "location"
        payload = {
            **base_payload,
            "location_type": suggested_payload.get("location_type") or "story_location",
            "summary": suggested_payload.get("summary") or reason,
            "visibility": suggested_payload.get("visibility") or "draft",
        }
    elif requirement_type in {"faction", "organization", "势力", "组织"}:
        resource_type = "faction"
        payload = {
            **base_payload,
            "faction_type": suggested_payload.get("faction_type") or "organization",
            "tier": suggested_payload.get("tier") or "local",
            "public_knowledge": suggested_payload.get("public_knowledge") or reason,
            "current_visibility": suggested_payload.get("current_visibility") or "mentioned_only",
        }
    elif requirement_type in {"item", "ability", "道具", "能力"}:
        resource_type = requirement_type if requirement_type in {"item", "ability"} else "item"
        payload = {
            **base_payload,
            "category": suggested_payload.get("category") or resource_type,
            "constraints": suggested_payload.get("constraints") or "不得越级解决关键危机，需由用户确认使用边界。",
        }
    else:
        resource_type = "lore"
        payload = {
            **base_payload,
            "category": suggested_payload.get("category") or requirement_type or "general",
            "content": suggested_payload.get("content") or reason or f"补全资源：{resource_name}",
            "priority": suggested_payload.get("priority") or "medium",
        }

    return {
        "requirement_id": str(requirement.get("id")),
        "requirement_type": requirement_type,
        "resource_type": resource_type,
        "resource_name": resource_name,
        "severity": requirement.get("severity"),
        "chapter_num": requirement.get("chapter_num"),
        "reason": reason,
        "draft_payload": payload,
        "side_effect": "draft_only",
    }



def _normalize_character_importance_tier(value: Any) -> str:
    tier = str(value or "supporting").strip().lower()
    if tier in {"protagonist", "main", "主角"}:
        return "protagonist"
    if tier in {"main_support", "supporting", "配角"}:
        return "main_support"
    if tier in {"supporting", "minor", "npc", "临时角色"}:
        return "supporting"
    if tier in {"background", "mentioned_only", "背景"}:
        return "background"
    return "supporting"


def _normalize_lore_category(value: Any) -> str:
    category = str(value or "custom").strip().lower()
    aliases = {
        "faction": "organization",
        "organization": "organization",
        "location": "location",
        "place": "location",
        "item": "item",
        "ability": "magic_system",
        "lore": "custom",
        "general": "custom",
    }
    return aliases.get(category, category or "custom")


def _normalize_lore_priority(value: Any) -> str:
    priority = str(value or "standard").strip().lower()
    if priority in {"critical", "high", "core"}:
        return "core"
    if priority in {"medium", "standard", "normal"}:
        return "standard"
    if priority in {"low", "reference"}:
        return "reference"
    return "standard"


async def _create_confirmed_resource(postgres_db, project_id: str, draft: ConfirmResourceSupplementDraft) -> Dict[str, Any]:
    """根据用户确认的草案创建最小资源；仅支持 lore / character。"""
    import uuid
    from app.models.character import Character
    from app.models.lore import LoreEntry

    payload = dict(draft.draft_payload or {})
    payload["project_id"] = project_id
    resource_type = str(draft.resource_type or "").strip().lower()

    if resource_type == "character":
        payload.setdefault("name", payload.get("title") or "未命名角色")
        payload.setdefault("description", payload.get("description") or payload.get("usage_guidance") or "由大纲资源需求补全创建。")
        payload["importance_tier"] = _normalize_character_importance_tier(payload.get("importance_tier"))
        character = Character(**payload)
        character_data = character.model_dump(mode="json")
        resource_id = await postgres_db.save_character(character_data)
        return {"resource_type": "character", "resource_id": resource_id, "resource": character_data}

    if resource_type == "lore":
        payload.setdefault("title", payload.get("name") or "未命名设定")
        payload.setdefault("content", payload.get("content") or payload.get("description") or "由大纲资源需求补全创建。")
        payload["category"] = _normalize_lore_category(payload.get("category"))
        payload["priority"] = _normalize_lore_priority(payload.get("priority"))
        lore = LoreEntry(**payload)
        lore_id = str(uuid.uuid4())
        params = lore.model_dump(mode="json")
        params["id"] = lore_id
        await postgres_db.execute_write(
            """
            INSERT INTO lore_entries (
                id, project_id, title, category, priority, content, summary,
                keywords, tags, constraints, related_characters, related_locations, related_items,
                forbidden_actions, source, created_at, updated_at
            ) VALUES (
                CAST(:id AS UUID), CAST(:project_id AS UUID), :title, :category, :priority, :content, :summary,
                :keywords, :tags, :constraints, :related_characters, :related_locations, :related_items,
                :forbidden_actions, :source, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            {
                **params,
                "keywords": json.dumps(params.get("keywords") or [], ensure_ascii=False),
                "tags": json.dumps(params.get("tags") or [], ensure_ascii=False),
                "constraints": json.dumps(params.get("constraints") or [], ensure_ascii=False),
                "related_characters": json.dumps(params.get("related_characters") or [], ensure_ascii=False),
                "related_locations": json.dumps(params.get("related_locations") or [], ensure_ascii=False),
                "related_items": json.dumps(params.get("related_items") or [], ensure_ascii=False),
                "forbidden_actions": json.dumps(params.get("forbidden_actions") or [], ensure_ascii=False),
                "summary": params.get("summary") or "",
                "source": params.get("source") or "resource_requirement_supplement",
            },
        )
        return {"resource_type": "lore", "resource_id": lore_id, "resource": params}

    raise ValueError(f"暂不支持确认创建资源类型: {draft.resource_type}")


@router.post("/resource-requirements/supplement-drafts", response_model=Dict[str, Any])
async def generate_resource_supplement_drafts(request: GenerateResourceSupplementDraftsRequest):
    """按资源需求生成一键补全草案；只返回草案，不落库创建资源。"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    severities = ["blocking"] if not request.include_advisory else ["blocking", "advisory"]
    requirements: List[Dict[str, Any]] = []
    if request.requirement_ids:
        for requirement_id in request.requirement_ids:
            rows = await postgres_db.execute_query(
                """
                SELECT * FROM outline_resource_requirements
                WHERE id = CAST(:id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                """,
                {"id": requirement_id, "project_id": request.project_id},
            )
            requirements.extend(rows)
    else:
        for severity in severities:
            requirements.extend(await postgres_db.get_outline_resource_requirements(
                project_id=request.project_id,
                outline_id=request.outline_id,
                chapter_num=request.chapter_num,
                status="pending",
                severity=severity,
            ))
            requirements.extend(await postgres_db.get_outline_resource_requirements(
                project_id=request.project_id,
                outline_id=request.outline_id,
                chapter_num=request.chapter_num,
                status="in_progress",
                severity=severity,
            ))

    seen: set[str] = set()
    drafts: List[Dict[str, Any]] = []
    for requirement in requirements:
        requirement_id = str(requirement.get("id"))
        if not requirement_id or requirement_id in seen:
            continue
        seen.add(requirement_id)
        if str(requirement.get("status") or "pending") not in {"pending", "in_progress"}:
            continue
        drafts.append(_build_resource_supplement_draft(requirement))

    return {
        "drafts": drafts,
        "total": len(drafts),
        "side_effect": "draft_only",
        "message": "已生成资源补全草案，需用户确认后再创建资源并标记需求已解决",
    }


@router.post("/resource-requirements/confirm-supplements", response_model=Dict[str, Any])
async def confirm_resource_supplements(request: ConfirmResourceSupplementDraftsRequest):
    """确认资源补全草案，创建最小资源并解决对应 requirement。"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    created: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    readiness_by_chapter: Dict[str, Any] = {}

    for draft in request.drafts:
        try:
            created_resource = await _create_confirmed_resource(postgres_db, request.project_id, draft)
            updated_requirement = await postgres_db.update_outline_resource_requirement_status(
                requirement_id=draft.requirement_id,
                status="resolved",
                matched_resource_id=created_resource["resource_id"],
                matched_resource_type=created_resource["resource_type"],
            )
            readiness = None
            if updated_requirement and updated_requirement.get("chapter_num") is not None:
                readiness = await postgres_db.update_chapter_resource_readiness(
                    project_id=str(updated_requirement.get("project_id")),
                    outline_id=str(updated_requirement.get("outline_id")) if updated_requirement.get("outline_id") else None,
                    chapter_num=int(updated_requirement.get("chapter_num")),
                )
                readiness_by_chapter[f"{updated_requirement.get('outline_id') or 'none'}:{updated_requirement.get('chapter_num')}"] = readiness
            created.append({
                **created_resource,
                "requirement": updated_requirement,
                "readiness": readiness,
            })
        except Exception as exc:
            failed.append({
                "requirement_id": draft.requirement_id,
                "resource_type": draft.resource_type,
                "error": str(exc),
            })

    return {
        "created": created,
        "failed": failed,
        "readiness_by_chapter": readiness_by_chapter,
        "success": len(failed) == 0,
        "message": f"已创建 {len(created)} 个资源，失败 {len(failed)} 个",
    }


@router.get("/resource-requirements", response_model=Dict[str, Any])
async def list_resource_requirements(
    project_id: str = Query(..., description="项目ID"),
    outline_id: Optional[str] = Query(None, description="大纲 ID"),
    chapter_num: Optional[int] = Query(None, description="章节号"),
    status: Optional[str] = Query(None, description="需求状态"),
    severity: Optional[str] = Query(None, description="blocking/advisory/optional"),
    requirement_type: Optional[str] = Query(None, description="资源类型"),
):
    """查询大纲资源需求。"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    requirements = await postgres_db.get_outline_resource_requirements(
        project_id=project_id,
        outline_id=outline_id,
        chapter_num=chapter_num,
        status=status,
        severity=severity,
        requirement_type=requirement_type,
    )
    return {"requirements": requirements, "total": len(requirements)}


@router.get("/resource-readiness", response_model=Dict[str, Any])
async def list_resource_readiness(
    project_id: str = Query(..., description="项目ID"),
    outline_id: Optional[str] = Query(None, description="大纲 ID"),
    chapter_num: Optional[int] = Query(None, description="章节号"),
    refresh: bool = Query(False, description="是否先刷新指定章节 readiness"),
):
    """查询章节资源 readiness 汇总。"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    if refresh and chapter_num is not None:
        await postgres_db.update_chapter_resource_readiness(
            project_id=project_id,
            outline_id=outline_id,
            chapter_num=chapter_num,
        )
    readiness = await postgres_db.get_chapter_resource_readiness(
        project_id=project_id,
        outline_id=outline_id,
        chapter_num=chapter_num,
    )
    return {"readiness": readiness, "total": len(readiness)}


@router.patch("/resource-requirements/{requirement_id}", response_model=Dict[str, Any])
async def update_resource_requirement_status(
    requirement_id: str,
    request: UpdateResourceRequirementStatusRequest,
):
    """更新大纲资源需求状态。"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        updated = await postgres_db.update_outline_resource_requirement_status(
            requirement_id=requirement_id,
            status=request.status,
            matched_resource_id=request.matched_resource_id,
            matched_resource_type=request.matched_resource_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="资源需求不存在")

    if updated.get("chapter_num") is not None:
        readiness = await postgres_db.update_chapter_resource_readiness(
            project_id=str(updated.get("project_id")),
            outline_id=str(updated.get("outline_id")) if updated.get("outline_id") else None,
            chapter_num=int(updated.get("chapter_num")),
        )
    else:
        readiness = None
    return {"requirement": updated, "readiness": readiness}


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
async def delete_outline(
    project_id: str,
    chapter_number: int,
    soft_delete_generated_chapters: bool = Query(False, description="是否同步软删除该大纲生成的小说正文"),
):
    """
    删除章节大纲

    默认只删除指定章节大纲并保留已生成正文；如显式传入
    soft_delete_generated_chapters=true，则软删除该大纲关联生成的章节。
    """
    service = get_plot_outline_service()
    outline = await service.get_outline(project_id, chapter_number)

    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    result = await service.delete_outline(
        outline.id,
        soft_delete_generated_chapters=soft_delete_generated_chapters,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail="删除失败")

    soft_deleted_chapters = int(result.get("soft_deleted_chapters", 0))
    if soft_delete_generated_chapters:
        message = f"第{chapter_number}章大纲已删除，已软删除 {soft_deleted_chapters} 个关联生成章节"
    else:
        message = f"第{chapter_number}章大纲已删除，已生成正文已保留"

    return {
        "success": True,
        "message": message,
        "soft_deleted_chapters": soft_deleted_chapters,
    }


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
