"""
角色管理 API 路由
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.database.postgres import postgres_db
from app.models.character import Character, CharacterStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[Dict[str, Any]])
async def list_characters(
    status: Optional[CharacterStatus] = None,
    role: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """
    获取角色列表

    Args:
        status: 按状态过滤
        role: 按角色类型过滤
        limit: 返回数量限制

    Returns:
        List: 角色列表
    """
    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    characters = await postgres_db.get_all_characters()

    # 过滤
    if status:
        characters = [c for c in characters if c.get("status") == status.value]
    if role:
        characters = [c for c in characters if c.get("role") == role]

    return characters[:limit]


@router.get("/{character_id}", response_model=Dict[str, Any])
async def get_character(character_id: str):
    """
    获取单个角色详情

    Args:
        character_id: 角色 ID

    Returns:
        Dict: 角色数据
    """
    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    character = await postgres_db.get_character(character_id)

    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    return character


@router.post("", response_model=Dict[str, Any])
async def create_character(character: Character):
    """
    创建新角色

    Args:
        character: 角色数据

    Returns:
        Dict: 创建结果
    """
    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 转换为字典
    char_data = character.model_dump(mode="json")

    try:
        await postgres_db.save_character(char_data)
        return {
            "success": True,
            "id": character.id,
            "message": f"角色 '{character.name}' 创建成功",
        }
    except Exception as e:
        logger.error(f"创建角色失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{character_id}", response_model=Dict[str, Any])
async def update_character(character_id: str, character: Character):
    """
    更新角色数据

    Args:
        character_id: 角色 ID
        character: 新角色数据

    Returns:
        Dict: 更新结果
    """
    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 检查角色是否存在
    existing = await postgres_db.get_character(character_id)
    if not existing:
        raise HTTPException(status_code=404, detail="角色不存在")

    char_data = character.model_dump(mode="json")

    try:
        await postgres_db.save_character(char_data)
        return {
            "success": True,
            "id": character_id,
            "message": f"角色 '{character.name}' 更新成功",
        }
    except Exception as e:
        logger.error(f"更新角色失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{character_id}", response_model=Dict[str, Any])
async def delete_character(character_id: str):
    """
    删除角色

    Args:
        character_id: 角色 ID

    Returns:
        Dict: 删除结果
    """
    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        await postgres_db.delete_character(character_id)
        return {
            "success": True,
            "message": f"角色 {character_id} 已删除",
        }
    except Exception as e:
        logger.error(f"删除角色失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{character_id}/relationships", response_model=List[Dict[str, Any]])
async def get_character_relationships(character_id: str):
    """
    获取角色关系（从 NebulaGraph）

    Args:
        character_id: 角色 ID

    Returns:
        List: 关系列表
    """
    from app.api.app import nebula_db

    if not nebula_db:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    relationships = await nebula_db.get_relationships(character_id)
    return relationships


@router.post("/{character_id}/memories", response_model=Dict[str, Any])
async def add_character_memory(
    character_id: str,
    content: str,
    memory_type: str = "experience",
    importance: float = 0.5,
):
    """
    添加角色记忆

    Args:
        character_id: 角色 ID
        content: 记忆内容
        memory_type: 记忆类型
        importance: 重要程度

    Returns:
        Dict: 添加结果
    """
    from app.api.app import nebula_db

    if not nebula_db:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    try:
        success = await nebula_db.add_memory(
            character_id=character_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
        )

        if success:
            return {
                "success": True,
                "message": "记忆添加成功",
            }
        else:
            raise HTTPException(status_code=500, detail="添加失败")
    except Exception as e:
        logger.error(f"添加记忆失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{character_id}/memories", response_model=List[Dict[str, Any]])
async def get_character_memories(
    character_id: str,
    limit: int = Query(default=10, le=100),
    min_importance: float = 0.0,
):
    """
    获取角色记忆

    Args:
        character_id: 角色 ID
        limit: 返回数量
        min_importance: 最小重要性

    Returns:
        List: 记忆列表
    """
    from app.api.app import nebula_db

    if not nebula_db:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    memories = await nebula_db.get_memories(
        character_id=character_id,
        limit=limit,
        min_importance=min_importance,
    )

    return memories
