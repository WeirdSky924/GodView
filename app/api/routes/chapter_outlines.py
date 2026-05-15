"""
章节大纲 API 路由
GodView v9: PlotOutlineAgent 专用接口
"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError, model_validator

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
    EmotionType,
    SceneType,
    ConflictLevel,
)
from app.services.plot_outline_service import get_plot_outline_service, set_plot_outline_service

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_RESOURCE_REQUIREMENT_STATUSES = {"pending", "in_progress", "resolved", "ignored", "superseded"}
_ALLOWED_RESOURCE_REQUIREMENT_SEVERITIES = {"blocking", "advisory", "optional"}


def _validate_uuid(value: Optional[str], field_name: str, *, required: bool = False) -> Optional[str]:
    """Validate external ID parameters before they reach UUID-casting SQL paths."""
    normalized = _validate_text_id(value, field_name, required=required)
    if normalized is None:
        return None
    try:
        UUID(normalized)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} 不是有效 UUID")
    return normalized


def _validate_text_id(value: Optional[str], field_name: str, *, required: bool = False) -> Optional[str]:
    if value is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} 不能为空")
        return None
    normalized = str(value).strip()
    if not normalized:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} 不能为空")
        return None
    if any(char.isspace() for char in normalized):
        raise HTTPException(status_code=400, detail=f"{field_name} 不能包含空白字符")
    if len(normalized) > 128:
        raise HTTPException(status_code=400, detail=f"{field_name} 过长")
    return normalized


def _validate_resource_requirement_status(status: Optional[str], *, required: bool = False) -> Optional[str]:
    if status is None:
        if required:
            raise HTTPException(status_code=400, detail="资源需求状态不能为空")
        return None
    normalized = status.strip().lower()
    if normalized not in _ALLOWED_RESOURCE_REQUIREMENT_STATUSES:
        raise HTTPException(status_code=400, detail="无效的资源需求状态")
    return normalized


def _validate_resource_requirement_severity(severity: Optional[str], *, default: Optional[str] = None) -> Optional[str]:
    if severity is None:
        return default
    normalized = severity.strip().lower()
    if normalized not in _ALLOWED_RESOURCE_REQUIREMENT_SEVERITIES:
        raise HTTPException(status_code=400, detail="无效的资源需求严重级别")
    return normalized


def _normalize_emotion_value(emotion: Any) -> str:
    value = str(emotion or "neutral").strip().lower()
    aliases = {
        "震惊": "surprise",
        "惊讶": "surprise",
        "恐惧": "fear",
        "害怕": "fear",
        "紧张": "tension",
        "悬疑": "tension",
        "平静": "neutral",
        "希望": "anticipation",
        "期待": "anticipation",
        "放松": "relief",
    }
    normalized = aliases.get(value, value)
    try:
        return EmotionType(normalized).value
    except ValueError:
        return EmotionType.NEUTRAL.value


def _normalize_scene_type_value(scene_type: Any) -> str:
    value = str(scene_type or "dialogue").strip().lower()
    aliases = {
        "对话": "dialogue",
        "对白": "dialogue",
        "交谈": "dialogue",
        "行动": "action",
        "动作": "action",
        "战斗": "action",
        "描写": "description",
        "描述": "description",
        "环境": "description",
        "转场": "transition",
        "过渡": "transition",
        "高潮": "climax",
        "收束": "resolution",
        "解决": "resolution",
        "回忆": "flashback",
        "闪回": "flashback",
        "伏笔": "foreshadow",
        "铺垫": "foreshadow",
    }
    normalized = aliases.get(value, value)
    try:
        return SceneType(normalized).value
    except ValueError:
        return SceneType.DIALOGUE.value


def _normalize_conflict_level_value(conflict_level: Any) -> str:
    value = str(conflict_level or "low").strip().lower()
    aliases = {
        "低": "low",
        "轻微": "low",
        "中": "medium",
        "中等": "medium",
        "高": "high",
        "强": "high",
        "激烈": "high",
        "危急": "critical",
        "关键": "critical",
        "致命": "critical",
    }
    normalized = aliases.get(value, value)
    try:
        return ConflictLevel(normalized).value
    except ValueError:
        return ConflictLevel.LOW.value


def _normalize_pending_scene(scene: Dict[str, Any], index: int) -> Dict[str, Any]:
    data = dict(scene)
    data["scene_number"] = data.get("scene_number") or index + 1
    data["title"] = str(data.get("title") or f"场景{index + 1}").strip() or f"场景{index + 1}"
    data["summary"] = str(data.get("summary") or data.get("description") or data["title"]).strip()
    data["scene_type"] = _normalize_scene_type_value(data.get("scene_type", "dialogue"))
    data["conflict_level"] = _normalize_conflict_level_value(data.get("conflict_level", "low"))
    data["emotion_start"] = _normalize_emotion_value(data.get("emotion_start", "neutral"))
    data["emotion_end"] = _normalize_emotion_value(data.get("emotion_end", "neutral"))
    data["emotion_arc"] = [_normalize_emotion_value(item) for item in data.get("emotion_arc") or []]
    return data


# ==================== 请求/响应模型 ====================

class GenerateOutlineRequestAPI(BaseModel):
    """生成大纲请求"""
    project_id: str
    chapter_number: int = Field(..., ge=1, description="章节号")
    context: Optional[str] = Field(None, description="上下文信息")
    previous_events: Optional[str] = Field(None, description="前文事件")
    special_requirements: Optional[List[str]] = Field(None, description="特殊要求")
    session_id: Optional[str] = Field(None, description="Assistant Context 会话 ID")
    request_id: Optional[str] = Field(None, description="幂等请求 ID")
    auto_save: bool = Field(False, description="是否生成后自动保存为草稿/修订提案")
    auto_approve: bool = Field(False, description="是否在自动保存后立即审批")
    approved_by: Optional[str] = Field(None, description="自动审批人")


class BatchGenerateOutlineRequest(BaseModel):
    """批量/多章大纲生成请求。"""
    project_id: str
    start_chapter: Optional[int] = Field(None, ge=1, description="起始章节号")
    end_chapter: Optional[int] = Field(None, ge=1, description="结束章节号")
    chapter_numbers: Optional[List[int]] = Field(None, description="指定章节号列表")
    context: Optional[str] = Field(None, description="额外上下文")
    previous_events: Optional[str] = Field(None, description="前文事件")
    special_requirements: Optional[List[str]] = Field(None, description="特殊要求")
    session_id: Optional[str] = Field(None, description="Assistant Context 会话 ID")
    request_id: Optional[str] = Field(None, description="幂等请求 ID")
    scope: str = Field("selected", description="current/selected/all")
    operation: str = Field("generate", description="generate/audit/revise")
    auto_save: bool = Field(False, description="是否生成后自动保存")
    auto_approve: bool = Field(False, description="是否保存后自动审批")
    approved_by: Optional[str] = Field(None, description="自动审批人")

    @model_validator(mode="after")
    def validate_generation_policy(self):
        if self.auto_approve and not self.auto_save:
            raise ValueError("auto_approve 需要同时开启 auto_save")
        if self.auto_approve and not (self.approved_by or "").strip():
            raise ValueError("auto_approve 需要提供 approved_by")
        if self.chapter_numbers:
            self.chapter_numbers = sorted({int(chapter) for chapter in self.chapter_numbers if int(chapter) > 0})
        elif self.start_chapter is not None and self.end_chapter is not None:
            if self.end_chapter < self.start_chapter:
                raise ValueError("end_chapter 不能小于 start_chapter")
        else:
            raise ValueError("必须提供 chapter_numbers 或 start_chapter/end_chapter")
        return self


class BatchGenerateOutlineResult(BaseModel):
    chapter_number: int
    status: str
    outline: Optional[ChapterOutline] = None
    saved_outline: Optional[ChapterOutline] = None
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    context_packet: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BatchGenerateOutlineResponse(BaseModel):
    success: bool
    mode: str = "multi"
    scope: str = "selected"
    auto_save: bool = False
    auto_approve: bool = False
    results: List[BatchGenerateOutlineResult] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)
    message: str = ""


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


class OutlineVersionsResponse(BaseModel):
    """章节大纲版本列表响应"""
    chapter_number: int
    current_approved: Optional[ChapterOutline] = None
    pending_revisions: List[ChapterOutline] = Field(default_factory=list)
    rejected_revisions: List[ChapterOutline] = Field(default_factory=list)
    versions: List[ChapterOutline] = Field(default_factory=list)
    total: int


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
    session_id: Optional[str] = Field(None, description="Assistant Context 会话 ID")
    request_id: Optional[str] = Field(None, description="幂等请求 ID")
    auto_save: bool = Field(False, description="是否自动保存 Agent 输出的大纲 JSON；默认仅预览/待确认")


class ChatResponse(BaseModel):
    """Agent 聊天响应"""
    message: str
    outline_updates: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    pending_outlines: Optional[List[PendingOutline]] = None
    saved_outline: Optional[Dict[str, Any]] = None
    saved_outlines: Optional[List[Dict[str, Any]]] = None  # 多章大纲保存
    prompt_render_trace: Optional[Dict[str, Any]] = None
    assistant_session_id: Optional[str] = None
    context_packet: Optional[Dict[str, Any]] = None
    parse_status: Optional[str] = None


class SavePendingOutlinesRequest(BaseModel):
    """保存待确认大纲请求"""
    outlines: List[PendingOutline]


class SavePendingOutlineResult(BaseModel):
    """单个待确认大纲保存结果"""
    chapter_number: Optional[int] = None
    status: str = Field(..., description="saved/failed")
    action: Optional[str] = Field(None, description="created/updated")
    outline_id: Optional[str] = None
    error_type: Optional[str] = None
    error: Optional[str] = None


class SavePendingOutlinesResponse(BaseModel):
    """保存待确认大纲响应"""
    success: bool
    saved_count: int
    message: str
    failed_count: int = 0
    results: List[SavePendingOutlineResult] = Field(default_factory=list)


class UpdateResourceRequirementStatusRequest(BaseModel):
    """更新资源需求状态请求"""
    status: str = Field(..., description="pending/in_progress/resolved/ignored/superseded")
    matched_resource_id: Optional[str] = Field(None, description="绑定的资源 ID")
    matched_resource_type: Optional[str] = Field(None, description="绑定的资源类型")
    resolution_method: Optional[str] = Field(None, description="bind_existing/create_resource/manual_resolved/ignored")


class CreateResourceRequirementRequest(BaseModel):
    """创建大纲资源需求请求；用于开发/测试环境构造可复现 readiness 状态。"""
    project_id: str = Field(..., description="项目ID")
    outline_id: str = Field(..., description="大纲 ID")
    chapter_num: int = Field(..., ge=1, description="章节号")
    requirement_type: str = Field(..., description="character/lore/location 等资源类型")
    resource_name: str = Field(..., min_length=1, description="资源名称")
    severity: str = Field("blocking", description="blocking/advisory/optional")
    status: str = Field("pending", description="pending/in_progress/resolved/ignored/superseded")
    reason: Optional[str] = Field(None, description="需求原因")
    suggested_payload: Dict[str, Any] = Field(default_factory=dict, description="建议创建资源 payload")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    source_agent: Optional[str] = Field("readiness_smoke_fixture", description="来源 Agent/工具标识")
    source_node_id: Optional[str] = Field(None, description="来源节点 ID")
    source_execution_id: Optional[str] = Field(None, description="来源执行 ID")


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
    original_resource_type = requirement_type
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
        "original_resource_type": original_resource_type,
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
    elif requirement_type in {"hook", "foreshadowing", "plot_hook", "伏笔"}:
        resource_type = "hook"
        payload = {
            **base_payload,
            "title": resource_name,
            "description": suggested_payload.get("description") or reason or f"伏笔补全：{resource_name}",
            "hook_type": suggested_payload.get("hook_type") or "mystery",
            "status": suggested_payload.get("status") or "planted",
            "priority": suggested_payload.get("priority") or 3,
            "plant_context": suggested_payload.get("plant_context") or reason,
            "resolution_hint": suggested_payload.get("resolution_hint") or "待后续章节回收",
        }
    elif requirement_type in {"faction", "organization", "势力", "组织"}:
        resource_type = "lore"
        payload = {
            **base_payload,
            "title": resource_name,
            "category": suggested_payload.get("category") or "faction",
            "content": suggested_payload.get("content") or suggested_payload.get("public_knowledge") or reason or f"势力/组织补全：{resource_name}",
            "summary": suggested_payload.get("summary") or reason,
            "tags": suggested_payload.get("tags") or ["outline_requirement", "faction"],
            "constraints": suggested_payload.get("constraints") or ["当前阶段不得越级揭示高阶势力核心信息。"],
            "source": suggested_payload.get("source") or "resource_requirement_supplement",
            "original_resource_type": original_resource_type,
            "resource_mapping_reason": "mapped_to_lore",
            "faction_type": suggested_payload.get("faction_type") or "organization",
            "tier": suggested_payload.get("tier") or "local",
            "current_visibility": suggested_payload.get("current_visibility") or "mentioned_only",
        }
    elif requirement_type in {"item", "ability", "道具", "能力"}:
        original_resource_type = "ability" if requirement_type in {"ability", "能力"} else "item"
        resource_type = "lore"
        payload = {
            **base_payload,
            "title": resource_name,
            "category": suggested_payload.get("category") or ("skill" if original_resource_type == "ability" else "item"),
            "content": suggested_payload.get("content") or reason or f"{('能力' if original_resource_type == 'ability' else '道具')}补全：{resource_name}",
            "summary": suggested_payload.get("summary") or reason,
            "tags": suggested_payload.get("tags") or ["outline_requirement", original_resource_type],
            "constraints": suggested_payload.get("constraints") or ["不得越级解决关键危机，需由用户确认使用边界。"],
            "source": suggested_payload.get("source") or "resource_requirement_supplement",
            "original_resource_type": original_resource_type,
            "resource_mapping_reason": "mapped_to_lore",
        }
    elif requirement_type in {"relationship", "event_rule", "crisis_resolution", "character_state", "continuity", "关系", "事件规则", "危机解决"}:
        resource_type = "lore"
        payload = {
            **base_payload,
            "title": resource_name,
            "category": suggested_payload.get("category") or "custom",
            "content": suggested_payload.get("content") or reason or f"剧情规则/关系补全：{resource_name}",
            "summary": suggested_payload.get("summary") or reason,
            "tags": suggested_payload.get("tags") or ["outline_requirement", requirement_type],
            "constraints": suggested_payload.get("constraints") or ["需与已审批大纲、角色状态和长篇节奏保持一致。"],
            "source": suggested_payload.get("source") or "resource_requirement_supplement",
            "original_resource_type": requirement_type,
            "resource_mapping_reason": "mapped_to_lore",
        }
    else:
        resource_type = "lore"
        payload = {
            **base_payload,
            "category": suggested_payload.get("category") or requirement_type or "general",
            "content": suggested_payload.get("content") or reason or f"补全资源：{resource_name}",
            "priority": suggested_payload.get("priority") or "medium",
            "original_resource_type": original_resource_type,
            "resource_mapping_reason": "mapped_to_lore",
        }

    return {
        "requirement_id": str(requirement.get("id")),
        "requirement_type": requirement_type,
        "original_resource_type": original_resource_type,
        "resource_type": resource_type,
        "resource_name": resource_name,
        "severity": requirement.get("severity"),
        "chapter_num": requirement.get("chapter_num"),
        "reason": reason,
        "draft_payload": payload,
        "side_effect": "draft_only",
    }



def _normalize_character_importance_tier(value: Any) -> str:
    tier = str(value or "npc").strip().lower()
    if tier in {"protagonist", "main", "主角"}:
        return "protagonist"
    if tier in {"main_support", "supporting", "配角"}:
        return "major_ally"
    if tier in {"minor", "npc", "临时角色"}:
        return "npc"
    if tier in {"background", "mentioned_only", "背景"}:
        return "background"
    return "npc"


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


def _normalize_region_type(value: Any) -> str:
    region_type = str(value or "custom").strip().lower()
    aliases = {
        "location": "custom",
        "story_location": "custom",
        "place": "custom",
        "地点": "custom",
        "场景地点": "custom",
        "city": "city",
        "城市": "city",
        "village": "village",
        "村庄": "village",
        "wilderness": "wilderness",
        "荒野": "wilderness",
        "dungeon": "dungeon",
        "秘境": "dungeon",
        "副本": "dungeon",
        "building": "building",
        "建筑": "building",
        "water": "water",
        "水域": "water",
        "mountain": "mountain",
        "山脉": "mountain",
        "forest": "forest",
        "森林": "forest",
        "custom": "custom",
    }
    return aliases.get(region_type, "custom")


def _normalize_terrain_type(value: Any) -> str:
    terrain_type = str(value or "custom").strip().lower()
    aliases = {
        "plain": "plain",
        "平原": "plain",
        "hill": "hill",
        "丘陵": "hill",
        "mountain": "mountain",
        "山地": "mountain",
        "desert": "desert",
        "沙漠": "desert",
        "swamp": "swamp",
        "沼泽": "swamp",
        "ice": "ice",
        "冰原": "ice",
        "volcano": "volcano",
        "火山": "volcano",
        "custom": "custom",
    }
    return aliases.get(terrain_type, "custom")


async def _create_confirmed_resource(postgres_db, project_id: str, draft: ConfirmResourceSupplementDraft) -> Dict[str, Any]:
    """根据用户确认的草案创建最小资源；支持 character / lore / location / hook。"""
    import uuid
    from app.models.character import Character
    from app.models.lore import LoreEntry
    from app.models.world import Region

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

    if resource_type == "location":
        worlds = await postgres_db.get_all_worlds(project_id=project_id, limit=1)
        world_id = str((worlds or [{}])[0].get("id") or "")
        if not world_id:
            raise ValueError("项目尚无世界，无法创建地点区域")

        region_payload = {
            "id": payload.get("id") or str(uuid.uuid4()),
            "name": payload.get("name") or payload.get("title") or "未命名地点",
            "world_id": world_id,
            "region_type": _normalize_region_type(payload.get("region_type") or payload.get("location_type")),
            "terrain_type": _normalize_terrain_type(payload.get("terrain_type")),
            "description": payload.get("description") or payload.get("summary") or payload.get("usage_guidance") or "由大纲资源需求补全创建。",
            "atmosphere": payload.get("atmosphere") or "",
            "coordinates": payload.get("coordinates") or {},
            "area_size": payload.get("area_size") or 0,
            "terrain_features": payload.get("terrain_features") or [],
            "landmarks": payload.get("landmarks") or [],
            "encounters": payload.get("encounters") or [],
            "connections": payload.get("connections") or [],
            "local_rules": payload.get("local_rules") or [],
            "state": payload.get("state") or "normal",
            "state_summary": payload.get("state_summary"),
            "is_generated": bool(payload.get("is_generated", True)),
            "visit_count": payload.get("visit_count") or 0,
        }
        region = Region(**region_payload)
        region_data = region.model_dump(mode="json")
        resource_id = await postgres_db.save_region(region_data)
        try:
            from app.services.graph_projection_service import enqueue_graph_projection_best_effort
            await enqueue_graph_projection_best_effort("region", region_data)
        except Exception:
            logger.warning("确认创建 location 资源后图谱投影入队失败", exc_info=True)
        return {"resource_type": "location", "resource_id": resource_id, "resource": region_data}

    if resource_type == "hook":
        hook_payload = {
            "id": payload.get("id") or str(uuid.uuid4()),
            "project_id": project_id,
            "world_id": payload.get("world_id"),
            "scope_type": payload.get("scope_type") or "project",
            "title": payload.get("title") or payload.get("name") or "未命名伏笔",
            "description": payload.get("description") or payload.get("usage_guidance") or "由大纲资源需求补全创建。",
            "hook_type": payload.get("hook_type") or "mystery",
            "status": payload.get("status") or "planted",
            "priority": payload.get("priority") or 3,
            "related_characters": payload.get("related_characters") or [],
            "related_locations": payload.get("related_locations") or [],
            "related_objects": payload.get("related_objects") or [],
            "plant_context": payload.get("plant_context") or payload.get("description") or payload.get("usage_guidance") or "",
            "resolution_hint": payload.get("resolution_hint") or "待后续章节回收",
        }
        resource_id = await postgres_db.save_hook(hook_payload)
        hook_payload["id"] = resource_id
        return {"resource_type": "hook", "resource_id": resource_id, "resource": hook_payload}

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
            requirement_rows = await postgres_db.execute_query(
                """
                SELECT id FROM outline_resource_requirements
                WHERE id = CAST(:id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                """,
                {"id": draft.requirement_id, "project_id": request.project_id},
            )
            if not requirement_rows:
                raise ValueError("资源需求不存在或不属于当前项目")

            created_resource = await _create_confirmed_resource(postgres_db, request.project_id, draft)
            updated_requirement = await postgres_db.update_outline_resource_requirement_status(
                requirement_id=draft.requirement_id,
                status="resolved",
                matched_resource_id=created_resource["resource_id"],
                matched_resource_type=created_resource["resource_type"],
                resolution_method="create_resource",
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


@router.post("/resource-requirements", response_model=Dict[str, Any])
async def create_resource_requirement(request: CreateResourceRequirementRequest):
    """创建单条大纲资源需求，并刷新对应章节 readiness。仅在 DEBUG 环境开放，用于可复现 runtime smoke。"""
    from app.api.app import postgres_db
    from app.config import settings

    if not settings.debug:
        raise HTTPException(status_code=404, detail="资源需求创建接口仅在 DEBUG 环境可用")
    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    project_id = _validate_uuid(request.project_id, "项目 ID", required=True)
    outline_id = _validate_text_id(request.outline_id, "大纲 ID", required=True)
    normalized_severity = _validate_resource_requirement_severity(request.severity, default="blocking")
    normalized_status = _validate_resource_requirement_status(request.status, required=True)

    requirement_id = await postgres_db.save_outline_resource_requirement({
        "project_id": project_id,
        "outline_id": outline_id,
        "chapter_num": request.chapter_num,
        "requirement_type": request.requirement_type,
        "resource_name": request.resource_name,
        "severity": normalized_severity,
        "status": normalized_status,
        "reason": request.reason or "",
        "suggested_payload": request.suggested_payload,
        "metadata": {
            **request.metadata,
            "created_by": "debug_resource_requirement_api",
            "debug_only": True,
        },
        "source_agent": request.source_agent,
        "source_node_id": request.source_node_id or "debug_resource_requirement_api",
        "source_execution_id": request.source_execution_id,
    })
    rows = await postgres_db.execute_query(
        "SELECT * FROM outline_resource_requirements WHERE id = CAST(:id AS UUID)",
        {"id": requirement_id},
    )
    requirement = rows[0] if rows else None
    readiness = await postgres_db.update_chapter_resource_readiness(
        project_id=project_id,
        outline_id=outline_id,
        chapter_num=request.chapter_num,
    )
    return {
        "requirement": requirement,
        "readiness": readiness,
        "message": "已创建资源需求并刷新章节 readiness",
    }


@router.get("/resource-requirements", response_model=Dict[str, Any])
async def list_resource_requirements(
    project_id: str = Query(..., description="项目ID"),
    outline_id: Optional[str] = Query(None, description="大纲 ID"),
    chapter_num: Optional[int] = Query(None, description="章节号"),
    status: Optional[str] = Query(None, description="需求状态"),
    severity: Optional[str] = Query(None, description="blocking/advisory/optional"),
    requirement_type: Optional[str] = Query(None, description="资源类型"),
    active_outlines_only: bool = True,
):
    """查询大纲资源需求。"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    project_id = _validate_uuid(project_id, "项目 ID", required=True)
    outline_id = _validate_text_id(outline_id, "大纲 ID")
    status = _validate_resource_requirement_status(status)
    severity = _validate_resource_requirement_severity(severity)

    requirements = await postgres_db.get_outline_resource_requirements(
        project_id=project_id,
        outline_id=outline_id,
        chapter_num=chapter_num,
        status=status,
        severity=severity,
        requirement_type=requirement_type,
        active_outlines_only=active_outlines_only,
    )
    return {"requirements": requirements, "total": len(requirements)}


@router.post("/resource-requirements/cleanup-orphans", response_model=Dict[str, Any])
async def cleanup_orphaned_resource_requirements(
    project_id: str = Query(..., description="项目ID"),
):
    """清理已删除/不存在大纲残留的资源需求与 readiness。"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    project_id = _validate_uuid(project_id, "项目 ID", required=True)
    if not hasattr(postgres_db, "cleanup_orphaned_outline_resource_requirements"):
        raise HTTPException(status_code=501, detail="当前数据库适配器不支持资源需求清理")

    result = await postgres_db.cleanup_orphaned_outline_resource_requirements(project_id)
    return {
        "success": True,
        "project_id": project_id,
        **result,
        "message": f"已清理 {result.get('superseded_resource_requirements', 0)} 条孤儿资源需求，删除 {result.get('deleted_resource_readiness', 0)} 条失效 readiness",
    }


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

    project_id = _validate_uuid(project_id, "项目 ID", required=True)
    outline_id = _validate_text_id(outline_id, "大纲 ID")

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

    requirement_id = _validate_uuid(requirement_id, "资源需求 ID", required=True)
    matched_resource_id = _validate_uuid(request.matched_resource_id, "绑定资源 ID")
    status = _validate_resource_requirement_status(request.status, required=True)

    try:
        updated = await postgres_db.update_outline_resource_requirement_status(
            requirement_id=requirement_id,
            status=status,
            matched_resource_id=matched_resource_id,
            matched_resource_type=request.matched_resource_type,
            resolution_method=request.resolution_method,
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
            failed_count=0,
            results=[],
            message="没有需要保存的大纲",
        )

    service = get_plot_outline_service()
    results: List[SavePendingOutlineResult] = []

    for pending in request.outlines:
        chapter_number = pending.chapter_number
        try:
            scenes = [
                SceneOutline(**_normalize_pending_scene(s, i))
                for i, s in enumerate(pending.scenes or [])
                if isinstance(s, dict)
            ]
            emotion_curve_payload = dict(pending.emotion_curve or {})
            if emotion_curve_payload:
                emotion_curve_payload.setdefault("chapter_number", chapter_number)
            if emotion_curve_payload.get("dominant_emotion"):
                emotion_curve_payload["dominant_emotion"] = _normalize_emotion_value(
                    emotion_curve_payload.get("dominant_emotion")
                )
            if emotion_curve_payload.get("points"):
                normalized_points = []
                for point in emotion_curve_payload.get("points") or []:
                    if isinstance(point, dict):
                        point_data = dict(point)
                        point_data["emotion"] = _normalize_emotion_value(point_data.get("emotion"))
                        normalized_points.append(point_data)
                emotion_curve_payload["points"] = normalized_points
            emotion_curve = EmotionCurve(**emotion_curve_payload) if emotion_curve_payload else None

            # 检查是否已存在该章节大纲
            existing = await service.get_outline(project_id, chapter_number)

            if existing:
                # 更新现有大纲
                update_data = {
                    "title": pending.title,
                    "summary": pending.summary,
                    "scenes": scenes,
                    "emotion_curve": emotion_curve,
                    "chapter_goals": pending.chapter_goals or [],
                    "hooks_planted": pending.hooks_planted or [],
                    "hooks_resolved": pending.hooks_resolved or [],
                    "target_word_count": pending.target_word_count or 3000,
                    "status": ChapterOutlineStatus.DRAFT,
                }
                updated_outline = await service.update_outline(existing.id, UpdateChapterOutlineDTO(**update_data))
                if not updated_outline:
                    raise RuntimeError("大纲更新失败，未返回更新后的大纲")
                if pending.character_arcs:
                    updated_outline.character_arcs = pending.character_arcs
                    await service.persist_outline_resource_audit(updated_outline)
                results.append(SavePendingOutlineResult(
                    chapter_number=chapter_number,
                    status="saved",
                    action="updated",
                    outline_id=updated_outline.id,
                ))
            else:
                # 创建新大纲
                create_dto = CreateChapterOutlineDTO(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    title=pending.title,
                    summary=pending.summary,
                    scenes=scenes,
                    chapter_goals=pending.chapter_goals or [],
                    hooks_planted=pending.hooks_planted or [],
                    hooks_resolved=pending.hooks_resolved or [],
                    target_word_count=pending.target_word_count or 3000,
                )
                created = await service.create_outline(create_dto)
                if pending.character_arcs:
                    created.character_arcs = pending.character_arcs
                    await service.persist_outline_resource_audit(created)
                results.append(SavePendingOutlineResult(
                    chapter_number=chapter_number,
                    status="saved",
                    action="created",
                    outline_id=created.id,
                ))
        except ValidationError as e:
            logger.warning("保存大纲校验失败 (章节 %s): %s", chapter_number, e)
            results.append(SavePendingOutlineResult(
                chapter_number=chapter_number,
                status="failed",
                error_type="validation_error",
                error=str(e),
            ))
        except Exception as e:
            logger.exception("保存大纲失败 (章节 %s)", chapter_number)
            results.append(SavePendingOutlineResult(
                chapter_number=chapter_number,
                status="failed",
                error_type="save_error",
                error=str(e),
            ))

    saved_count = sum(1 for result in results if result.status == "saved")
    failed_count = sum(1 for result in results if result.status == "failed")

    if failed_count == 0:
        response = SavePendingOutlinesResponse(
            success=True,
            saved_count=saved_count,
            failed_count=0,
            results=results,
            message=f"成功保存 {saved_count} 个大纲",
        )
    elif saved_count == 0:
        response = SavePendingOutlinesResponse(
            success=False,
            saved_count=0,
            failed_count=failed_count,
            results=results,
            message=f"{failed_count} 个大纲保存失败，请根据 results 查看具体原因",
        )
        raise HTTPException(status_code=422, detail=response.model_dump(mode="json"))
    else:
        response = SavePendingOutlinesResponse(
            success=False,
            saved_count=saved_count,
            failed_count=failed_count,
            results=results,
            message=f"已保存 {saved_count} 个大纲，{failed_count} 个大纲保存失败，请检查失败项",
        )

    return response


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


@router.get("/by-id/{outline_id}", response_model=ChapterOutline)
async def get_outline_by_id(project_id: str, outline_id: str):
    """按 outline ID 精确获取大纲版本。"""
    service = get_plot_outline_service()
    outline = await service.get_outline_by_id(project_id, outline_id)
    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲版本不存在")
    return outline


@router.get("/{chapter_number}/versions", response_model=OutlineVersionsResponse)
async def get_outline_versions(project_id: str, chapter_number: int):
    """获取某章节的所有大纲版本。"""
    service = get_plot_outline_service()
    versions = await service.get_outline_versions(project_id, chapter_number)
    if versions["total"] == 0:
        raise HTTPException(status_code=404, detail="章节大纲不存在")
    return OutlineVersionsResponse(**versions)


@router.post("/by-id/{outline_id}/approve", response_model=ChapterOutline)
async def approve_outline_by_id(project_id: str, outline_id: str, request: ApproveOutlineRequest):
    """按 outline ID 审批指定大纲版本，避免同章多版本误审批。"""
    service = get_plot_outline_service()
    outline = await service.get_outline_by_id(project_id, outline_id)
    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲版本不存在")

    updated = await service.approve_outline(outline.id, request.approved_by)
    if not updated:
        raise HTTPException(status_code=400, detail="该大纲版本无法审批")
    return updated


@router.post("/by-id/{outline_id}/reject", response_model=ChapterOutline)
async def reject_outline_revision_by_id(project_id: str, outline_id: str):
    """拒绝指定修订提案，保留原 approved 版本不变。"""
    service = get_plot_outline_service()
    outline = await service.get_outline_by_id(project_id, outline_id)
    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲版本不存在")

    rejected = await service.reject_outline_revision(outline.id)
    if not rejected:
        raise HTTPException(status_code=400, detail="只有 revision 状态的大纲可以被拒绝")
    return rejected


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


async def _persist_generated_outline_if_requested(
    service,
    *,
    project_id: str,
    chapter_number: int,
    generated: GenerateOutlineResponse,
    auto_save: bool,
    auto_approve: bool,
    approved_by: Optional[str],
) -> Optional[ChapterOutline]:
    if not auto_save:
        return None
    saved_outline, _ = await service._save_outline_updates(
        project_id=project_id,
        default_chapter_number=chapter_number,
        outline_updates=generated.outline.model_dump(mode="json"),
    )
    if auto_approve and saved_outline:
        approved = await service.approve_outline(saved_outline.id, approved_by or "outline_agent")
        return approved or saved_outline
    return saved_outline


@router.post("/batch-generate", response_model=BatchGenerateOutlineResponse)
async def batch_generate_outlines(request: BatchGenerateOutlineRequest):
    """批量生成/预览章节大纲；默认不写库，写库/审批必须显式开启。"""
    service = get_plot_outline_service()
    if request.chapter_numbers:
        chapter_numbers = request.chapter_numbers
    else:
        chapter_numbers = list(range(int(request.start_chapter or 1), int(request.end_chapter or request.start_chapter or 1) + 1))

    results: List[BatchGenerateOutlineResult] = []
    generated_count = saved_count = approved_count = failed_count = 0
    for chapter_number in chapter_numbers:
        try:
            generated = await service.generate_outline(
                project_id=request.project_id,
                chapter_number=chapter_number,
                context=request.context,
                previous_events=request.previous_events,
                session_id=request.session_id,
                request_id=f"{request.request_id}:{chapter_number}" if request.request_id else None,
            )
            generated_count += 1
            saved_outline = await _persist_generated_outline_if_requested(
                service,
                project_id=request.project_id,
                chapter_number=chapter_number,
                generated=generated,
                auto_save=request.auto_save,
                auto_approve=request.auto_approve,
                approved_by=request.approved_by,
            )
            status = "generated"
            if saved_outline:
                saved_count += 1
                status = "approved" if saved_outline.status == ChapterOutlineStatus.APPROVED else "saved"
                if saved_outline.status == ChapterOutlineStatus.APPROVED:
                    approved_count += 1
            results.append(BatchGenerateOutlineResult(
                chapter_number=chapter_number,
                status=status,
                outline=generated.outline,
                saved_outline=saved_outline,
                warnings=generated.warnings,
                suggestions=generated.suggestions,
                context_packet=generated.context_packet,
            ))
        except Exception as exc:
            logger.exception("批量生成第 %s 章大纲失败", chapter_number)
            failed_count += 1
            results.append(BatchGenerateOutlineResult(
                chapter_number=chapter_number,
                status="failed",
                error=str(exc),
            ))

    return BatchGenerateOutlineResponse(
        success=failed_count == 0,
        scope=request.scope,
        auto_save=request.auto_save,
        auto_approve=request.auto_approve,
        results=results,
        summary={
            "generated": generated_count,
            "saved": saved_count,
            "approved": approved_count,
            "failed": failed_count,
        },
        message=f"已处理 {len(chapter_numbers)} 章：生成 {generated_count}，保存 {saved_count}，审批 {approved_count}，失败 {failed_count}",
    )


@router.post("/{chapter_number}/generate", response_model=GenerateOutlineResponse)
async def generate_outline(project_id: str, chapter_number: int, request: GenerateOutlineRequestAPI):
    """
    生成章节大纲

    使用 AI 自动生成章节大纲；默认只返回预览，不直接保存。
    """
    service = get_plot_outline_service()
    result = await service.generate_outline(
        project_id=project_id,
        chapter_number=chapter_number,
        context=request.context,
        previous_events=request.previous_events,
        session_id=request.session_id,
        request_id=request.request_id,
    )
    await _persist_generated_outline_if_requested(
        service,
        project_id=project_id,
        chapter_number=chapter_number,
        generated=result,
        auto_save=request.auto_save,
        auto_approve=request.auto_approve,
        approved_by=request.approved_by,
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
    if not updated:
        raise HTTPException(status_code=500, detail="更新章节大纲失败")
    if updated.id != outline.id and updated.previous_outline_id == outline.id:
        return {
            "outline": updated,
            "revision_proposal": True,
            "approved_outline_id": outline.id,
            "message": "原已审批大纲保持不变，已创建修订提案。",
        }
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

    兼容旧的章节号审批入口。若同章存在 revision，前端/新调用方应使用
    /by-id/{outline_id}/approve，避免误审批。
    """
    service = get_plot_outline_service()
    outline = await service.get_outline(project_id, chapter_number)

    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    versions = await service.get_outline_versions(project_id, chapter_number)
    if versions["pending_revisions"]:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "outline_revision_selection_required",
                "message": "该章节存在待审批修订，请按 outline_id 审批指定版本。",
                "chapter_number": chapter_number,
                "pending_revision_ids": [outline.id for outline in versions["pending_revisions"]],
                "current_approved_id": versions["current_approved"].id if versions["current_approved"] else None,
            },
        )

    updated = await service.approve_outline(outline.id, request.approved_by)
    if not updated:
        raise HTTPException(status_code=400, detail="该大纲版本无法审批")
    return updated


@router.delete("/by-id/{outline_id}")
async def delete_outline_by_id(
    project_id: str,
    outline_id: str,
    soft_delete_generated_chapters: bool = Query(False, description="是否同步软删除该大纲生成的小说正文"),
):
    """按 outline ID 精确删除一个大纲版本。"""
    service = get_plot_outline_service()
    outline = await service.get_outline_by_id(project_id, outline_id)
    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲版本不存在")

    result = await service.delete_outline(
        outline.id,
        soft_delete_generated_chapters=soft_delete_generated_chapters,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail="删除失败")

    versions = await service.get_outline_versions(project_id, outline.chapter_number)
    soft_deleted_chapters = int(result.get("soft_deleted_chapters", 0))
    return {
        "success": True,
        "message": f"第{outline.chapter_number}章大纲版本已删除，剩余 {versions['total']} 个版本",
        "outline_id": outline.id,
        "chapter_number": outline.chapter_number,
        "remaining_versions": versions["total"],
        "soft_deleted_chapters": soft_deleted_chapters,
        "superseded_resource_requirements": int(result.get("superseded_resource_requirements", 0)),
        "deleted_resource_readiness": int(result.get("deleted_resource_readiness", 0)),
    }


@router.delete("/{chapter_number}")
async def delete_outline(
    project_id: str,
    chapter_number: int,
    soft_delete_generated_chapters: bool = Query(False, description="是否同步软删除该大纲生成的小说正文"),
    delete_all_versions: bool = Query(False, description="是否删除该章节的全部大纲版本"),
):
    """
    删除章节大纲

    默认只删除指定章节大纲并保留已生成正文；如显式传入
    soft_delete_generated_chapters=true，则软删除该大纲关联生成的章节。
    """
    service = get_plot_outline_service()
    versions = await service.get_outline_versions(project_id, chapter_number)
    if versions["total"] == 0:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    targets = list(versions["versions"]) if delete_all_versions else [await service.get_outline(project_id, chapter_number)]
    targets = [outline for outline in targets if outline]
    if not targets:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    soft_deleted_chapters = 0
    superseded_resource_requirements = 0
    deleted_resource_readiness = 0
    deleted_ids: List[str] = []
    for outline in targets:
        result = await service.delete_outline(
            outline.id,
            soft_delete_generated_chapters=soft_delete_generated_chapters,
        )
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="删除失败")
        deleted_ids.append(outline.id)
        soft_deleted_chapters += int(result.get("soft_deleted_chapters", 0))
        superseded_resource_requirements += int(result.get("superseded_resource_requirements", 0))
        deleted_resource_readiness += int(result.get("deleted_resource_readiness", 0))

    remaining = await service.get_outline_versions(project_id, chapter_number)
    if soft_delete_generated_chapters:
        message = f"第{chapter_number}章已删除 {len(deleted_ids)} 个大纲版本，已软删除 {soft_deleted_chapters} 个关联生成章节"
    else:
        message = f"第{chapter_number}章已删除 {len(deleted_ids)} 个大纲版本，已生成正文已保留"

    return {
        "success": True,
        "message": message,
        "deleted_outline_ids": deleted_ids,
        "deleted_versions": len(deleted_ids),
        "remaining_versions": remaining["total"],
        "soft_deleted_chapters": soft_deleted_chapters,
        "superseded_resource_requirements": superseded_resource_requirements,
        "deleted_resource_readiness": deleted_resource_readiness,
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
        session_id=request.session_id,
        request_id=request.request_id,
        auto_save=request.auto_save,
    )

    # 处理 pending_outlines；逐条容错，避免单个格式问题让整轮聊天失败。
    pending_outlines = None
    if response.get("pending_outlines"):
        pending_outlines = []
        for index, outline in enumerate(response["pending_outlines"]):
            try:
                outline_payload = dict(outline)
                if not outline_payload.get("chapter_number"):
                    outline_payload["chapter_number"] = chapter_number + index
                outline_payload["title"] = str(outline_payload.get("title") or f"第{outline_payload['chapter_number']}章")
                outline_payload["summary"] = str(outline_payload.get("summary") or outline_payload["title"])
                outline_payload["scenes"] = [
                    _normalize_pending_scene(scene, scene_index)
                    for scene_index, scene in enumerate(outline_payload.get("scenes") or [])
                    if isinstance(scene, dict)
                ]
                pending_outlines.append(PendingOutline(**outline_payload))
            except Exception:
                logger.warning("跳过无法转换为待保存大纲的 Agent 输出项: index=%s payload=%s", index, outline, exc_info=True)

    return ChatResponse(
        message=response.get("message", ""),
        outline_updates=response.get("outline_updates"),
        suggestions=response.get("suggestions"),
        warnings=response.get("warnings"),
        pending_outlines=pending_outlines,
        saved_outline=response.get("saved_outline"),
        saved_outlines=response.get("saved_outlines"),
        prompt_render_trace=response.get("prompt_render_trace"),
        assistant_session_id=response.get("assistant_session_id"),
        context_packet=response.get("context_packet"),
        parse_status=response.get("parse_status"),
    )


# ==================== 服务注入 ====================

def set_service(service):
    """设置服务实例（用于依赖注入）"""
    set_plot_outline_service(service)
