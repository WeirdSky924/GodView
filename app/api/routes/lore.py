"""
静态设定 (Lore) API 路由
"""

import json
import logging
import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.character import Character, CharacterImportanceTier
from app.models.lore import (
    LoreCategory,
    LoreEntry,
    LorePriority,
    LoreSearchResult,
    LoreValidationResult,
    normalize_lore_category,
    normalize_lore_priority,
)
from app.services.character_reference_resolver import get_character_reference_resolver
from app.services.plot_outline_service import get_plot_outline_service


class BindLoreCharacterReferenceAction(str, Enum):
    """设定角色引用绑定动作。"""

    BIND_EXISTING = "bind_existing"
    CREATE_CHARACTER = "create_character"


class BindLoreCharacterReferenceDTO(BaseModel):
    """绑定/创建并绑定设定中的未解析角色引用。"""

    project_id: str
    source_text: str = Field(..., min_length=1)
    action: BindLoreCharacterReferenceAction
    character_id: Optional[str] = None
    character: Optional[Character] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_action_payload(self):
        if self.action == BindLoreCharacterReferenceAction.BIND_EXISTING and not self.character_id:
            raise ValueError("绑定已有角色时必须提供 character_id")
        if self.action == BindLoreCharacterReferenceAction.CREATE_CHARACTER:
            if self.character is None:
                self.character = Character(
                    name=self.source_text.strip(),
                    project_id=self.project_id,
                    description="",
                    importance_tier=CharacterImportanceTier.NPC,
                )
            elif not self.character.name.strip():
                self.character.name = self.source_text.strip()
        return self


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
    related_character_refs: Optional[List[Dict[str, Any]]] = None
    unresolved_character_refs: Optional[List[Dict[str, Any]]] = None
    related_locations: Optional[List[str]] = None
    related_items: Optional[List[str]] = None
    constraints: Optional[List[str]] = None
    forbidden_actions: Optional[List[str]] = None
    source: Optional[str] = None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: Any) -> Optional[LoreCategory]:
        if value is None:
            return None
        return normalize_lore_category(value)

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value: Any) -> Optional[LorePriority]:
        if value is None:
            return None
        return normalize_lore_priority(value)


logger = logging.getLogger(__name__)

router = APIRouter()

_lore_entry_columns_cache: Optional[set[str]] = None


async def _get_lore_entry_columns(postgres_db, force_refresh: bool = False) -> set[str]:
    global _lore_entry_columns_cache
    if _lore_entry_columns_cache is not None and not force_refresh:
        return _lore_entry_columns_cache

    rows = await postgres_db.execute_query(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'lore_entries'
        """
    )
    _lore_entry_columns_cache = {row.get("column_name") for row in rows if row.get("column_name")}
    return _lore_entry_columns_cache


def _parse_json_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _reference_match_key(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().casefold())


def _serialize_lore_row(row: Dict[str, Any]) -> Dict[str, Any]:
    serialized = dict(row)
    serialized["category"] = normalize_lore_category(row.get("category", "custom")).value
    serialized["priority"] = normalize_lore_priority(row.get("priority", "standard")).value
    serialized["related_characters"] = _parse_json_list(serialized.get("related_characters"))
    serialized["related_character_refs"] = _parse_json_list(serialized.get("related_character_refs"))
    serialized["unresolved_character_refs"] = _parse_json_list(serialized.get("unresolved_character_refs"))
    serialized["forbidden_actions"] = _parse_json_list(serialized.get("forbidden_actions"))
    return serialized


def _invalidate_plot_outline_context(project_id: Optional[str]):
    if not project_id:
        return
    try:
        get_plot_outline_service().invalidate_project_context(project_id)
    except Exception as e:
        logger.warning(f"Plot Outline 缓存失效失败: {e}")


async def _build_lore_reference_character_data(postgres_db: Any, request: BindLoreCharacterReferenceDTO) -> Dict[str, Any]:
    from app.api.routes.characters import (
        _auto_configure_character_agent,
        _derive_role_from_tier,
        _validate_character_region_link,
    )
    from app.services.graph_projection_service import get_graph_projection_service

    character = request.character or Character(
        name=request.source_text.strip(),
        project_id=request.project_id,
        description="",
        importance_tier=CharacterImportanceTier.NPC,
    )
    char_data = character.model_dump(mode="json")
    char_data["project_id"] = request.project_id
    char_data["name"] = (char_data.get("name") or request.source_text).strip()
    if not char_data["name"]:
        raise HTTPException(status_code=400, detail="角色名称不能为空")
    if not char_data.get("id"):
        char_data["id"] = str(uuid.uuid4())
    now = datetime.now()
    char_data["created_at"] = now
    char_data["updated_at"] = now
    if not char_data.get("status"):
        char_data["status"] = "active"
    if not char_data.get("importance_tier"):
        char_data["importance_tier"] = CharacterImportanceTier.NPC.value
    char_data["role"] = _derive_role_from_tier(char_data["importance_tier"])
    for field in [
        "personality_traits",
        "lexicon",
        "voice_samples",
        "attributes",
        "goals",
        "inventory",
        "agent_goals",
        "agent_memory",
        "aliases",
    ]:
        if char_data.get(field) is None:
            char_data[field] = [] if field in ["lexicon", "voice_samples", "goals", "inventory", "agent_goals", "agent_memory", "aliases"] else {}
    if char_data.get("has_agent") is None:
        char_data["has_agent"] = False
    if char_data.get("agent_enabled") is None:
        char_data["agent_enabled"] = True

    char_data = await _validate_character_region_link(postgres_db, char_data)
    char_data = await _auto_configure_character_agent(char_data)
    await postgres_db.save_character(char_data)

    try:
        graph_projection_service = get_graph_projection_service()
        if graph_projection_service:
            projection_result = await graph_projection_service.enqueue_character_projection(char_data)
            if projection_result.get("status") == "failed":
                logger.warning(f"角色关系图投影任务入队失败: {projection_result.get('reason')}")
    except Exception as e:
        logger.warning(f"角色引用绑定后的关系图投影入队失败: {e}")
    return char_data


async def _record_lore_reference_delta(
    postgres_db,
    *,
    project_id: str,
    lore_id: str,
    operation: str,
    resolution: Dict[str, Any],
) -> None:
    try:
        from app.services.assistant_context import get_assistant_context_fabric

        fabric = get_assistant_context_fabric(postgres_db)
        await fabric.deltas.record_entity_change(
            project_id=project_id,
            entity_type="lore_character_reference",
            entity_id=lore_id,
            operation=operation,
            after=resolution,
            payload_summary={
                "title": resolution.get("delta_title") or "设定角色引用解析更新",
                "source_text": resolution.get("delta_source_text"),
                "character_id": resolution.get("delta_character_id"),
                "character_name": resolution.get("delta_character_name"),
                "resolution_method": resolution.get("delta_resolution_method"),
                "resolved_count": len(resolution.get("related_character_refs") or []),
                "unresolved_count": len(resolution.get("unresolved_character_refs") or []),
            },
            source_table="lore_entries",
        )
    except Exception as e:
        logger.warning(f"记录设定角色引用 Assistant Context delta 失败: {e}")


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
        {"value": "character_setting", "label": "角色设定"},
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
    return [_serialize_lore_row(row) for row in results]


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

    duplicate = None
    if hasattr(postgres_db, "find_duplicate_lore"):
        duplicate = await postgres_db.find_duplicate_lore(lore.project_id, lore.title, lore.content)
    if duplicate:
        return {
            "success": True,
            "id": str(duplicate.get("id")),
            "duplicate": True,
            "message": f"设定 '{lore.title}' 已存在，已复用现有条目",
        }

    # 始终生成新的 UUID（忽略前端传入的 ID）
    lore_id = str(uuid.uuid4())

    resolver = get_character_reference_resolver(postgres_db)
    reference_resolution = await resolver.resolve_for_lore(
        project_id=lore.project_id,
        references=lore.related_characters,
        provenance={"surface": "lore_api", "operation": "create_lore", "lore_id": lore_id},
    )

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
        "related_characters": json.dumps(reference_resolution.related_characters, ensure_ascii=False),
        "related_character_refs": json.dumps(reference_resolution.related_character_refs, ensure_ascii=False),
        "unresolved_character_refs": json.dumps(reference_resolution.unresolved_character_refs, ensure_ascii=False),
        "related_locations": json.dumps(lore.related_locations) if lore.related_locations else "[]",
        "related_items": json.dumps(lore.related_items) if lore.related_items else "[]",
        "forbidden_actions": json.dumps(lore.forbidden_actions) if lore.forbidden_actions else "[]",
        "source": lore.source or "",
        "created_at": now,
        "updated_at": now,
    }

    try:
        await postgres_db.execute_write("""
            INSERT INTO lore_entries (
                id, project_id, title, category, priority, content, summary,
                keywords, tags, constraints, related_characters, related_character_refs,
                unresolved_character_refs, related_locations, related_items,
                forbidden_actions, source, created_at, updated_at
            ) VALUES (
                CAST(:id AS UUID), CAST(:project_id AS UUID), :title, :category, :priority, :content, :summary,
                :keywords, :tags, :constraints, CAST(:related_characters AS jsonb), CAST(:related_character_refs AS jsonb),
                CAST(:unresolved_character_refs AS jsonb), :related_locations, :related_items,
                :forbidden_actions, :source, :created_at, :updated_at
            )
        """, params)

        await resolver.persist_lore_resolution(
            lore_id=lore_id,
            project_id=lore.project_id,
            resolution=reference_resolution,
        )
        await _record_lore_reference_delta(
            postgres_db,
            project_id=lore.project_id,
            lore_id=lore_id,
            operation="create_lore_reference_resolution",
            resolution=reference_resolution.to_dict(),
        )
        _invalidate_plot_outline_context(lore.project_id)
        return {
            "success": True,
            "id": lore_id,
            "message": f"设定 '{lore.title}' 创建成功",
            "character_reference_resolution": reference_resolution.to_dict(),
        }
    except Exception as e:
        logger.error(f"创建设定失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lore_id}/character-references/bind", response_model=Dict[str, Any])
async def bind_lore_character_reference(lore_id: str, request: BindLoreCharacterReferenceDTO):
    """将设定中的未解析/歧义角色引用绑定到已有角色，或创建新角色后绑定。"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    lore_rows = await postgres_db.execute_query(
        "SELECT * FROM lore_entries WHERE id = CAST(:id AS UUID) AND project_id = CAST(:project_id AS UUID)",
        {"id": lore_id, "project_id": request.project_id},
    )
    if not lore_rows:
        raise HTTPException(status_code=404, detail="设定不存在或不属于当前项目")

    lore_row = _serialize_lore_row(lore_rows[0])
    source_text = request.source_text.strip()
    source_key = _reference_match_key(source_text)
    unresolved_refs = lore_row.get("unresolved_character_refs") or []
    matching_unresolved = [
        item for item in unresolved_refs
        if _reference_match_key(item.get("source_text") if isinstance(item, dict) else item) == source_key
    ]
    if not matching_unresolved:
        raise HTTPException(status_code=409, detail="该角色引用已被处理或不存在，请刷新后重试")

    action = request.action.value
    if request.action == BindLoreCharacterReferenceAction.BIND_EXISTING:
        character = await postgres_db.get_character(request.character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        if str(character.get("project_id")) != request.project_id:
            raise HTTPException(status_code=409, detail="不能绑定其他项目的角色")
        character_id = str(character.get("id"))
        character_name = character.get("name") or character_id
        resolution_method = "user_bind_existing"
    else:
        character = await _build_lore_reference_character_data(postgres_db, request)
        character_id = str(character.get("id"))
        character_name = character.get("name") or source_text
        resolution_method = "user_create_character"

    now = datetime.now().isoformat()
    provenance = {
        **(request.provenance or {}),
        "surface": (request.provenance or {}).get("surface", "lore_reference_bind"),
        "operation": action,
        "lore_id": lore_id,
        "source_text": source_text,
        "bound_character_id": character_id,
        "bound_at": now,
    }
    related_characters = list(dict.fromkeys([*(lore_row.get("related_characters") or []), character_id]))
    related_character_refs = [
        item for item in (lore_row.get("related_character_refs") or [])
        if not (
            isinstance(item, dict)
            and _reference_match_key(item.get("source_text")) == source_key
            and str(item.get("character_id")) == character_id
        )
    ]
    related_character_refs.append({
        "status": "resolved",
        "source_text": source_text,
        "source_payload": source_text,
        "character_id": character_id,
        "character_name": character_name,
        "confidence": 1.0,
        "resolution_method": resolution_method,
        "provenance": provenance,
    })
    remaining_unresolved_refs = [
        item for item in unresolved_refs
        if not (isinstance(item, dict) and _reference_match_key(item.get("source_text")) == source_key)
    ]

    resolver = get_character_reference_resolver(postgres_db)
    from app.services.character_reference_resolver import CharacterReferenceResolution

    reference_resolution = CharacterReferenceResolution(
        related_characters=related_characters,
        related_character_refs=related_character_refs,
        unresolved_character_refs=remaining_unresolved_refs,
    )
    await resolver.persist_lore_resolution(
        lore_id=lore_id,
        project_id=request.project_id,
        resolution=reference_resolution,
    )
    delta_payload = {
        **reference_resolution.to_dict(),
        "delta_title": "设定角色引用绑定更新",
        "delta_source_text": source_text,
        "delta_character_id": character_id,
        "delta_character_name": character_name,
        "delta_resolution_method": resolution_method,
    }
    await _record_lore_reference_delta(
        postgres_db,
        project_id=request.project_id,
        lore_id=lore_id,
        operation="bind_lore_character_reference",
        resolution=delta_payload,
    )
    _invalidate_plot_outline_context(request.project_id)

    return {
        "success": True,
        "lore_id": lore_id,
        "project_id": request.project_id,
        "action": action,
        "character": {
            "id": character_id,
            "name": character_name,
            "role": character.get("role"),
            "importance_tier": character.get("importance_tier"),
        },
        "character_reference_resolution": reference_resolution.to_dict(),
        "message": f"已将角色引用 '{source_text}' 绑定到角色 '{character_name}'",
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
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    query = "SELECT * FROM lore_entries WHERE id = CAST(:id AS UUID)"
    results = await postgres_db.execute_query(query, {"id": lore_id})

    if not results:
        raise HTTPException(status_code=404, detail="设定不存在")

    return _serialize_lore_row(results[0])


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

    project_id_result = await postgres_db.execute_query(
        "SELECT project_id FROM lore_entries WHERE id = CAST(:id AS UUID)",
        {"id": lore_id}
    )
    if not project_id_result:
        raise HTTPException(status_code=404, detail="设定不存在")
    project_id = project_id_result[0].get("project_id")

    resolver = get_character_reference_resolver(postgres_db)
    reference_resolution = None

    available_columns = await _get_lore_entry_columns(postgres_db)

    # 如果运行时刚执行过迁移，旧缓存可能仍缺少新列，这里主动刷新一次
    update_data = lore_update.model_dump(exclude_unset=True)
    if "related_characters" in update_data:
        reference_resolution = await resolver.resolve_for_lore(
            project_id=str(project_id),
            references=update_data.get("related_characters") or [],
            provenance={"surface": "lore_api", "operation": "update_lore", "lore_id": lore_id},
        )
        update_data["related_characters"] = reference_resolution.related_characters
        update_data["related_character_refs"] = reference_resolution.related_character_refs
        update_data["unresolved_character_refs"] = reference_resolution.unresolved_character_refs
    missing_requested_columns = [key for key in update_data if key not in available_columns]
    if missing_requested_columns:
        available_columns = await _get_lore_entry_columns(postgres_db, force_refresh=True)

    # 构建更新语句
    update_fields = []
    params: Dict[str, Any] = {"id": lore_id}

    for key, value in update_data.items():
        if key not in available_columns:
            logger.warning(f"Lore 更新跳过不存在的列: {key}")
            continue
        if value is not None:
            if key in ["category", "priority"]:
                update_fields.append(f"{key} = :{key}")
                params[key] = value.value if hasattr(value, 'value') else value
            elif key in [
                "keywords",
                "tags",
                "constraints",
                "related_characters",
                "related_character_refs",
                "unresolved_character_refs",
                "related_locations",
                "related_items",
                "forbidden_actions",
            ]:
                # JSON/JSONB 字段需要转换为 JSON 字符串
                import json
                update_fields.append(f"{key} = CAST(:{key} AS jsonb)")
                params[key] = json.dumps(value, ensure_ascii=False)
            else:
                update_fields.append(f"{key} = :{key}")
                params[key] = value

    if not update_fields:
        return {"success": True, "id": lore_id, "message": "没有需要更新的字段"}

    update_fields.append("updated_at = NOW()")

    query = f"UPDATE lore_entries SET {', '.join(update_fields)} WHERE id = CAST(:id AS UUID)"
    await postgres_db.execute_write(query, params)
    if reference_resolution:
        await resolver.persist_lore_resolution(
            lore_id=lore_id,
            project_id=str(project_id),
            resolution=reference_resolution,
        )
        await _record_lore_reference_delta(
            postgres_db,
            project_id=str(project_id),
            lore_id=lore_id,
            operation="update_lore_reference_resolution",
            resolution=reference_resolution.to_dict(),
        )
    _invalidate_plot_outline_context(project_id)

    response = {
        "success": True,
        "id": lore_id,
        "message": "设定更新成功",
    }
    if reference_resolution:
        response["character_reference_resolution"] = reference_resolution.to_dict()
    return response


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

    project_row = await postgres_db.execute_query(
        "SELECT project_id FROM lore_entries WHERE id = CAST(:id AS UUID)",
        {"id": lore_id}
    )
    if not project_row:
        raise HTTPException(status_code=404, detail="设定不存在")

    await postgres_db.execute_write(
        "DELETE FROM lore_entries WHERE id = CAST(:id AS UUID)",
        {"id": lore_id}
    )
    _invalidate_plot_outline_context(project_row[0].get("project_id"))

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
            category=normalize_lore_category(row.get("category", "custom")),
            priority=normalize_lore_priority(row.get("priority", "standard")),
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
