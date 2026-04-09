"""
静态设定 (Lore) API 路由
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.lore import (
    LoreCategory,
    LoreEntry,
    LorePriority,
    LoreSearchResult,
    LoreValidationResult,
)


class UpdateLoreDTO(BaseModel):
    """更新设定的数据传输对象（所有字段可选）"""
    title: Optional[str] = None
    category: Optional[LoreCategory] = None
    priority: Optional[LorePriority] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    related_characters: Optional[List[str]] = None
    related_locations: Optional[List[str]] = None
    related_items: Optional[List[str]] = None
    constraints: Optional[List[str]] = None
    forbidden_actions: Optional[List[str]] = None
    source: Optional[str] = None

logger = logging.getLogger(__name__)

router = APIRouter()


# 模拟数据库（实际应用中应该使用真实数据库）
_lore_store: Dict[str, LoreEntry] = {}


# ==================== 静态路由（必须在动态路由之前） ====================

@router.get("/categories", response_model=List[Dict[str, str]])
async def get_lore_categories():
    """
    获取设定类别列表

    Returns:
        List: 类别列表
    """
    return [
        {"value": "world_rule", "label": "世界规则"},
        {"value": "geography", "label": "地理设定"},
        {"value": "history", "label": "历史背景"},
        {"value": "faction", "label": "势力体系"},
        {"value": "culture", "label": "文化习俗"},
        {"value": "race", "label": "种族设定"},
        {"value": "profession", "label": "职业/阶层"},
        {"value": "item", "label": "物品/装备"},
        {"value": "skill", "label": "技能/能力"},
        {"value": "custom", "label": "自定义"},
    ]


@router.get("/priorities", response_model=List[Dict[str, str]])
async def get_lore_priorities():
    """
    获取设定优先级列表

    Returns:
        List: 优先级列表
    """
    return [
        {"value": "constitutional", "label": "宪法级（不可违反）"},
        {"value": "core", "label": "核心设定"},
        {"value": "standard", "label": "标准设定"},
        {"value": "flexible", "label": "灵活设定"},
    ]


# ==================== 动态路由 ====================

@router.get("", response_model=List[Dict[str, Any]])
async def list_lore(
    project_id: str = Query(..., description="项目 ID"),
    category: Optional[LoreCategory] = None,
    priority: Optional[LorePriority] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=200),
):
    """
    获取设定列表

    Args:
        project_id: 项目 ID
        category: 类别过滤
        priority: 优先级过滤
        search: 搜索关键词
        limit: 返回数量限制

    Returns:
        List: 设定列表
    """
    results = []

    for lore in _lore_store.values():
        if lore.project_id != project_id:
            continue

        if category and lore.category != category:
            continue

        if priority and lore.priority != priority:
            continue

        if search and search.lower() not in lore.title.lower() and search.lower() not in lore.content.lower():
            continue

        results.append(lore.model_dump(mode="json"))

    # 按优先级和创建时间排序
    priority_order = {
        LorePriority.CONSTITUTIONAL: 0,
        LorePriority.CORE: 1,
        LorePriority.STANDARD: 2,
        LorePriority.FLEXIBLE: 3,
    }
    results.sort(key=lambda x: (priority_order.get(x.get("priority"), 99), x.get("created_at", "")))

    return results[:limit]


@router.post("", response_model=Dict[str, Any])
async def create_lore(lore: LoreEntry):
    """
    创建设定

    Args:
        lore: 设定数据

    Returns:
        Dict: 创建结果
    """
    # 自动生成 ID（如果未提供）
    lore_id = lore.id or str(uuid.uuid4())

    if lore_id in _lore_store:
        raise HTTPException(status_code=400, detail="设定 ID 已存在")

    # 更新 lore 对象的 ID
    lore.id = lore_id

    # 设置创建时间
    if not hasattr(lore, 'created_at') or lore.created_at is None:
        lore.created_at = datetime.now()

    _lore_store[lore_id] = lore

    return {
        "success": True,
        "id": lore_id,
        "message": f"设定 '{lore.title}' 创建成功",
    }


@router.get("/{lore_id}", response_model=Dict[str, Any])
async def get_lore(lore_id: str):
    """
    获取设定详情

    Args:
        lore_id: 设定 ID

    Returns:
        Dict: 设定数据
    """
    if lore_id not in _lore_store:
        raise HTTPException(status_code=404, detail="设定不存在")

    return _lore_store[lore_id].model_dump(mode="json")


@router.put("/{lore_id}", response_model=Dict[str, Any])
async def update_lore(lore_id: str, lore_update: UpdateLoreDTO):
    """
    更新设定（支持部分更新）

    Args:
        lore_id: 设定 ID
        lore_update: 更新数据

    Returns:
        Dict: 更新结果
    """
    if lore_id not in _lore_store:
        raise HTTPException(status_code=404, detail="设定不存在")

    # 获取现有设定
    existing = _lore_store[lore_id]

    # 应用部分更新
    update_data = lore_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(existing, key, value)

    # 更新时间戳
    existing.updated_at = datetime.now()

    _lore_store[lore_id] = existing

    return {
        "success": True,
        "id": lore_id,
        "message": f"设定 '{existing.title}' 更新成功",
    }


@router.delete("/{lore_id}", response_model=Dict[str, Any])
async def delete_lore(lore_id: str):
    """
    删除设定

    Args:
        lore_id: 设定 ID

    Returns:
        Dict: 删除结果
    """
    if lore_id not in _lore_store:
        raise HTTPException(status_code=404, detail="设定不存在")

    del _lore_store[lore_id]

    return {
        "success": True,
        "message": f"设定 {lore_id} 已删除",
    }


@router.post("/search", response_model=List[LoreSearchResult])
async def search_lore(
    project_id: str = Query(..., description="项目 ID"),
    query: str = Query(..., description="搜索查询"),
    category: Optional[LoreCategory] = Query(None, description="类别过滤"),
    limit: int = Query(default=10, le=50),
):
    """
    搜索设定

    Args:
        project_id: 项目 ID
        query: 搜索查询
        category: 类别过滤
        limit: 返回数量

    Returns:
        List: 搜索结果
    """
    results = []

    for lore in _lore_store.values():
        if lore.project_id != project_id:
            continue

        if category and lore.category != category:
            continue

        # 简单的关键词匹配
        query_lower = query.lower()
        score = 0.0

        if query_lower in lore.title.lower():
            score = 0.9
        elif query_lower in lore.content.lower():
            score = 0.7
        elif any(query_lower in kw.lower() for kw in lore.keywords):
            score = 0.8

        if score > 0:
            results.append(LoreSearchResult(
                id=lore.id,
                title=lore.title,
                category=lore.category,
                priority=lore.priority,
                summary=lore.summary,
                score=score,
                keywords=lore.keywords,
            ))

    # 按分数排序
    results.sort(key=lambda x: x.score, reverse=True)

    return results[:limit]


@router.post("/validate", response_model=LoreValidationResult)
async def validate_content(
    project_id: str,
    content: str,
    check_constitutional: bool = True,
):
    """
    验证内容是否符合设定

    Args:
        project_id: 项目 ID
        content: 要验证的内容
        check_constitutional: 是否检查宪法级规则

    Returns:
        LoreValidationResult: 验证结果
    """
    conflicts = []
    warnings = []
    suggestions = []

    # 检查宪法级规则
    if check_constitutional:
        for lore in _lore_store.values():
            if lore.project_id != project_id:
                continue
            if lore.priority != LorePriority.CONSTITUTIONAL:
                continue

            # 简单的约束检查
            for constraint in lore.constraints:
                if constraint.lower() in content.lower():
                    warnings.append(f"可能违反宪法级规则 '{lore.title}': {constraint}")

    return LoreValidationResult(
        valid=len(conflicts) == 0,
        conflicts=conflicts,
        warnings=warnings,
        suggestions=suggestions,
    )
