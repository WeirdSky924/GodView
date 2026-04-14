"""
记忆 API 路由
GodView v9: 长篇记忆架构专用接口
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.memory import (
    MemoryEntry,
    MemoryType,
    MemoryCategory,
    MemorySnapshot,
    CharacterMemoryState,
    CreateMemoryDTO,
    UpdateMemoryDTO,
    SearchMemoryDTO,
    MemorySearchResult,
    BuildSnapshotDTO,
)
from app.services.memory_service import get_memory_service, set_memory_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class CreateMemoryRequest(BaseModel):
    """创建记忆请求"""
    project_id: str
    memory_type: str = Field(default="medium_term", description="记忆类型：short_term/medium_term/long_term")
    category: str = Field(default="event", description="记忆分类")
    content: str
    summary: Optional[str] = None
    chapter_number: Optional[int] = None
    character_ids: List[str] = Field(default_factory=list)
    importance_score: float = Field(default=0.5, ge=0, le=1)


class UpdateMemoryRequest(BaseModel):
    """更新记忆请求"""
    content: Optional[str] = None
    summary: Optional[str] = None
    importance_score: Optional[float] = None
    memory_type: Optional[str] = None


class SearchMemoryRequest(BaseModel):
    """搜索记忆请求"""
    project_id: str
    query: str
    memory_types: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    chapter_from: Optional[int] = None
    chapter_to: Optional[int] = None
    character_ids: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=50)


class MemoryListResponse(BaseModel):
    """记忆列表响应"""
    memories: List[MemoryEntry]
    total: int


class MemorySearchResponse(BaseModel):
    """记忆搜索响应"""
    results: List[Dict[str, Any]]
    total: int


class BuildSnapshotRequest(BaseModel):
    """构建快照请求"""
    project_id: str
    chapter_number: int
    include_long_term: bool = True
    include_medium_term: bool = True
    medium_term_chapters: int = Field(default=5)


# ==================== 记忆 API ====================

@router.post("", response_model=MemoryEntry)
async def create_memory(request: CreateMemoryRequest):
    """
    创建记忆条目

    创建新的记忆条目，支持向量嵌入
    """
    service = get_memory_service()

    try:
        memory_type = MemoryType(request.memory_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的记忆类型: {request.memory_type}")

    try:
        category = MemoryCategory(request.category)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的记忆分类: {request.category}")

    memory = await service.create_memory(CreateMemoryDTO(
        project_id=request.project_id,
        memory_type=memory_type,
        category=category,
        content=request.content,
        summary=request.summary,
        chapter_number=request.chapter_number,
        character_ids=request.character_ids,
        importance_score=request.importance_score,
    ))

    return memory


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    project_id: str,
    chapter_number: Optional[int] = None,
    memory_type: Optional[str] = None,
    limit: int = 20,
):
    """
    获取记忆列表

    按条件筛选记忆条目
    """
    service = get_memory_service()

    memories = []
    if chapter_number:
        types = [MemoryType(memory_type)] if memory_type else None
        memories = await service.get_memories_by_chapter(project_id, chapter_number, types)
    else:
        memories = await service.get_recent_memories(project_id, chapters=limit)

    return MemoryListResponse(
        memories=memories[:limit],
        total=len(memories),
    )


@router.get("/{memory_id}")
async def get_memory(memory_id: str):
    """
    获取记忆详情
    """
    service = get_memory_service()
    memory = await service.get_memory(memory_id)

    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")

    return memory


@router.put("/{memory_id}")
async def update_memory(memory_id: str, request: UpdateMemoryRequest):
    """
    更新记忆条目
    """
    service = get_memory_service()

    dto = UpdateMemoryDTO()
    if request.content:
        dto.content = request.content
    if request.summary:
        dto.summary = request.summary
    if request.importance_score is not None:
        dto.importance_score = request.importance_score
    if request.memory_type:
        try:
            dto.memory_type = MemoryType(request.memory_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的记忆类型: {request.memory_type}")

    memory = await service.update_memory(memory_id, dto)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")

    return memory


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """
    删除记忆条目
    """
    service = get_memory_service()
    success = await service.delete_memory(memory_id)

    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    return {"success": True, "message": f"记忆 {memory_id} 已删除"}


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(request: SearchMemoryRequest):
    """
    搜索记忆

    支持向量相似度搜索和条件过滤
    """
    service = get_memory_service()

    memory_types = None
    if request.memory_types:
        try:
            memory_types = [MemoryType(t) for t in request.memory_types]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的记忆类型: {e}")

    categories = None
    if request.categories:
        try:
            categories = [MemoryCategory(c) for c in request.categories]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的记忆分类: {e}")

    results = await service.search_memories(SearchMemoryDTO(
        project_id=request.project_id,
        query=request.query,
        memory_types=memory_types,
        categories=categories,
        character_ids=request.character_ids,
        limit=request.limit,
    ))

    return MemorySearchResponse(
        results=[
            {
                "memory": r.memory.model_dump(),
                "relevance_score": r.relevance_score,
            }
            for r in results
        ],
        total=len(results),
    )


# ==================== 快照 API ====================

@router.get("/snapshot")
async def get_snapshot(project_id: str, chapter_number: Optional[int] = None):
    """
    获取记忆快照

    获取指定章节或最新的记忆快照
    """
    service = get_memory_service()
    snapshot = await service.get_snapshot(project_id, chapter_number)

    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")

    return snapshot


@router.post("/snapshot/build")
async def build_snapshot(request: BuildSnapshotRequest):
    """
    构建记忆快照

    聚合角色状态、伏笔、事件等信息
    """
    service = get_memory_service()
    snapshot = await service.build_snapshot(BuildSnapshotDTO(
        project_id=request.project_id,
        chapter_number=request.chapter_number,
        include_long_term=request.include_long_term,
        include_medium_term=request.include_medium_term,
        medium_term_chapters=request.medium_term_chapters,
    ))

    return snapshot


# ==================== 角色记忆状态 API ====================

@router.get("/character/{character_id}")
async def get_character_memory_state(project_id: str, character_id: str):
    """
    获取角色记忆状态

    获取指定角色的记忆聚合状态
    """
    service = get_memory_service()
    state = await service.get_character_memory_state(project_id, character_id)

    if not state:
        raise HTTPException(status_code=404, detail="角色记忆状态不存在")

    return state


# ==================== 伏笔 API ====================

@router.get("/foreshadowing")
async def get_pending_foreshadowing(project_id: str):
    """
    获取待回收伏笔

    返回所有已埋设但未回收的伏笔
    """
    # TODO: 从数据库获取
    return {
        "foreshadowings": [],
        "total": 0,
        "high_priority": [],
    }


@router.post("/foreshadowing/{foreshadowing_id}/reveal")
async def mark_foreshadowing_revealed(
    foreshadowing_id: str,
    chapter_number: int,
    reveal_context: Optional[str] = None,
):
    """
    标记伏笔已揭示

    更新伏笔状态为已回收
    """
    # TODO: 实现数据库更新
    return {
        "success": True,
        "foreshadowing_id": foreshadowing_id,
        "status": "resolved",
        "revealed_at": datetime.now().isoformat(),
        "reveal_chapter": chapter_number,
    }


# ==================== 服务注入 ====================

def set_service(service):
    """设置服务实例"""
    set_memory_service(service)
