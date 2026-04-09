"""
静态设定 (Lore) API 路由
"""

import json
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
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 构建查询
    conditions = ["project_id = CAST(:project_id AS UUID)"]
    params: Dict[str, Any] = {"project_id": project_id, "limit": limit}

    if category:
        conditions.append("category = :category")
        params["category"] = category.value

    if priority:
        conditions.append("priority = :priority")
        params["priority"] = priority.value

    if search:
        conditions.append("(title ILIKE :search OR content ILIKE :search)")
        params["search"] = f"%{search}%"

    where_clause = f"WHERE {' AND '.join(conditions)}"
    query = f"""
        SELECT * FROM lore_entries
        {where_clause}
        ORDER BY
            CASE priority
                WHEN 'constitutional' THEN 0
                WHEN 'core' THEN 1
                WHEN 'standard' THEN 2
                WHEN 'flexible' THEN 3
                ELSE 99
            END,
            created_at DESC
        LIMIT :limit
    """

    results = await postgres_db.execute_query(query, params)
    return results


@router.post("", response_model=Dict[str, Any])
async def create_lore(lore: LoreEntry):
    """
    创建设定

    Args:
        lore: 设定数据

    Returns:
        Dict: 创建结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 始终生成新的 UUID（忽略前端传入的 ID）
    lore_id = str(uuid.uuid4())

    # 设置创建时间
    now = datetime.now()

    params = {
        "id": lore_id,
        "project_id": lore.project_id,
        "title": lore.title,
        "category": lore.category.value if isinstance(lore.category, LoreCategory) else lore.category,
        "priority": lore.priority.value if isinstance(lore.priority, LorePriority) else lore.priority,
        "content": lore.content,
        "summary": lore.summary or "",
        "keywords": json.dumps(lore.keywords) if lore.keywords else "[]",
        "tags": json.dumps(lore.tags) if lore.tags else "[]",
        "constraints": json.dumps(lore.constraints) if lore.constraints else "[]",
        "related_characters": json.dumps(lore.related_characters) if lore.related_characters else "[]",
        "related_locations": json.dumps(lore.related_locations) if lore.related_locations else "[]",
        "related_items": json.dumps(lore.related_items) if lore.related_items else "[]",
        "created_at": now,
        "updated_at": now,
    }

    try:
        await postgres_db.execute_write("""
            INSERT INTO lore_entries (
                id, project_id, title, category, priority, content, summary,
                keywords, tags, constraints, related_characters, related_locations, related_items,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS UUID), CAST(:project_id AS UUID), :title, :category, :priority, :content, :summary,
                :keywords, :tags, :constraints, :related_characters, :related_locations, :related_items,
                :created_at, :updated_at
            )
        """, params)

        return {
            "success": True,
            "id": lore_id,
            "message": f"设定 '{lore.title}' 创建成功",
        }
    except Exception as e:
        logger.error(f"创建设定失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{lore_id}", response_model=Dict[str, Any])
async def get_lore(lore_id: str):
    """
    获取设定详情

    Args:
        lore_id: 设定 ID

    Returns:
        Dict: 设定数据
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    query = "SELECT * FROM lore_entries WHERE id = CAST(:id AS UUID)"
    results = await postgres_db.execute_query(query, {"id": lore_id})

    if not results:
        raise HTTPException(status_code=404, detail="设定不存在")

    return results[0]


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
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 检查设定是否存在
    existing = await postgres_db.execute_query(
        "SELECT id FROM lore_entries WHERE id = CAST(:id AS UUID)",
        {"id": lore_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="设定不存在")

    # 构建更新语句
    update_fields = []
    params: Dict[str, Any] = {"id": lore_id}

    update_data = lore_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            if key in ["category", "priority"]:
                update_fields.append(f"{key} = :{key}")
                params[key] = value.value if hasattr(value, 'value') else value
            else:
                update_fields.append(f"{key} = :{key}")
                params[key] = value

    if not update_fields:
        return {"success": True, "id": lore_id, "message": "没有需要更新的字段"}

    update_fields.append("updated_at = NOW()")

    query = f"UPDATE lore_entries SET {', '.join(update_fields)} WHERE id = CAST(:id AS UUID)"
    await postgres_db.execute_write(query, params)

    return {
        "success": True,
        "id": lore_id,
        "message": "设定更新成功",
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
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    await postgres_db.execute_write(
        "DELETE FROM lore_entries WHERE id = CAST(:id AS UUID)",
        {"id": lore_id}
    )

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
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    conditions = ["project_id = CAST(:project_id AS UUID)"]
    params: Dict[str, Any] = {"project_id": project_id, "limit": limit}

    if category:
        conditions.append("category = :category")
        params["category"] = category.value

    # 简单的关键词匹配
    conditions.append("(title ILIKE :query OR content ILIKE :query)")
    params["query"] = f"%{query}%"

    where_clause = f"WHERE {' AND '.join(conditions)}"
    sql = f"""
        SELECT id, title, category, priority, summary, keywords
        FROM lore_entries
        {where_clause}
        LIMIT :limit
    """

    results = await postgres_db.execute_query(sql, params)

    return [
        LoreSearchResult(
            id=row.get("id", ""),
            title=row.get("title", ""),
            category=row.get("category", "custom"),
            priority=row.get("priority", "standard"),
            summary=row.get("summary"),
            score=0.8,  # 简单的固定分数
            keywords=row.get("keywords", []),
        )
        for row in results
    ]


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
    from app.api.app import postgres_db

    conflicts = []
    warnings = []
    suggestions = []

    if not postgres_db:
        return LoreValidationResult(valid=True, conflicts=[], warnings=[], suggestions=[])

    # 检查宪法级规则
    if check_constitutional:
        lores = await postgres_db.execute_query(
            "SELECT title, constraints FROM lore_entries WHERE project_id = CAST(:project_id AS UUID) AND priority = 'constitutional'",
            {"project_id": project_id}
        )

        for lore in lores:
            for constraint in lore.get("constraints", []):
                if constraint.lower() in content.lower():
                    warnings.append(f"可能违反宪法级规则 '{lore['title']}': {constraint}")

    return LoreValidationResult(
        valid=len(conflicts) == 0,
        conflicts=conflicts,
        warnings=warnings,
        suggestions=suggestions,
    )
