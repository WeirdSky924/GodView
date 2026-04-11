"""
角色管理 API 路由
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.character import (
    Character,
    CharacterStatus,
    CharacterVoiceSample,
    CharacterImportanceTier,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _derive_role_from_tier(importance_tier: str) -> str:
    """
    从重要性层级推导角色类型（向后兼容）

    Args:
        importance_tier: 角色重要性层级

    Returns:
        str: 角色类型 (main/antagonist/supporting/npc)
    """
    # 主角层
    if importance_tier in [
        CharacterImportanceTier.PROTAGONIST.value,
        CharacterImportanceTier.CO_PROTAGONIST.value,
        CharacterImportanceTier.DEUTERAGONIST.value,
    ]:
        return "main"

    # 反派
    if importance_tier in [
        CharacterImportanceTier.ARCHENEMY.value,
        CharacterImportanceTier.MAJOR_ANTAGONIST.value,
        CharacterImportanceTier.ARC_ANtagonist.value,
    ]:
        return "antagonist"

    # NPC / 背景
    if importance_tier in [
        CharacterImportanceTier.NPC.value,
        CharacterImportanceTier.BACKGROUND.value,
        CharacterImportanceTier.CAMEO.value,
        CharacterImportanceTier.MINION.value,
    ]:
        return "npc"

    # 其他都是配角
    return "supporting"


@router.get("", response_model=List[Dict[str, Any]])
async def list_characters(
    project_id: Optional[str] = Query(None, description="按项目 ID 过滤"),
    role: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """
    获取角色列表

    Args:
        project_id: 按项目 ID 过滤
        role: 按角色类型过滤
        limit: 返回数量限制

    Returns:
        List: 角色列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    characters = await postgres_db.get_all_characters(
        project_id=project_id,
        role=role,
        limit=limit,
    )

    return characters


@router.get("/{character_id}", response_model=Dict[str, Any])
async def get_character(character_id: str):
    """
    获取单个角色详情

    Args:
        character_id: 角色 ID

    Returns:
        Dict: 角色数据
    """
    from app.api.app import postgres_db

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
    from app.api.app import postgres_db, nebula_db
    import uuid
    from datetime import datetime

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 转换为字典
    char_data = character.model_dump(mode="json")

    # 自动生成 ID（如果未提供）
    if not char_data.get("id"):
        char_data["id"] = str(uuid.uuid4())

    # 设置默认值和时间戳（使用 datetime 对象）
    now = datetime.now()
    if not char_data.get("status"):
        char_data["status"] = "active"
    char_data["created_at"] = now
    char_data["updated_at"] = now

    # 确保 importance_tier 有默认值
    if not char_data.get("importance_tier"):
        char_data["importance_tier"] = CharacterImportanceTier.NPC.value

    # 从 importance_tier 推导 role（向后兼容数据库）
    char_data["role"] = _derive_role_from_tier(char_data["importance_tier"])

    # 确保 JSON 字段有默认值
    for field in ['personality_traits', 'lexicon', 'voice_samples', 'attributes', 'goals', 'inventory', 'agent_goals', 'agent_memory']:
        if char_data.get(field) is None:
            char_data[field] = [] if field in ['lexicon', 'voice_samples', 'goals', 'inventory', 'agent_goals', 'agent_memory'] else {}

    # 确保 Agent 布尔字段有默认值
    if char_data.get('has_agent') is None:
        char_data['has_agent'] = False
    if char_data.get('agent_enabled') is None:
        char_data['agent_enabled'] = True

    # 自动配置角色 Agent（基于 importance_tier）
    char_data = await _auto_configure_character_agent(char_data)

    try:
        await postgres_db.save_character(char_data)

        # 同步到 NebulaGraph（如果已连接）
        if nebula_db:
            try:
                import json
                nebula_props = {
                    "name": char_data.get("name", ""),
                    "description": char_data.get("description", ""),
                    "role": char_data.get("role", "supporting"),
                    "importance_tier": char_data.get("importance_tier", "npc"),
                    "status": char_data.get("status", "active"),
                    "personality_traits": json.dumps(char_data.get("personality_traits", [])),
                    "created_at": char_data["created_at"].isoformat() if hasattr(char_data["created_at"], 'isoformat') else str(char_data["created_at"]),
                }
                await nebula_db.insert_character(char_data["id"], nebula_props)
                logger.info(f"角色 {char_data['id']} 已同步到 NebulaGraph")
            except Exception as e:
                logger.warning(f"角色同步到 NebulaGraph 失败: {e}")

        return {
            "success": True,
            "id": char_data["id"],
            "message": f"角色 '{character.name}' 创建成功",
            "has_agent": char_data.get("has_agent"),
        }
    except Exception as e:
        logger.error(f"创建角色失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _auto_configure_character_agent(char_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    为角色自动配置 Agent（包括调用 Setting Agent 生成性格）

    基于 importance_tier（角色重要性层级）决定是否启用 Agent：
    - Tier 1-3（主角层、核心配角层、重要配角层）：自动启用 Agent
    - Tier 4（阶段性角色层）：根据具体类型决定
    - Tier 5-6（功能性角色层、背景层）：不启用 Agent

    Args:
        char_data: 角色数据字典

    Returns:
        Dict: 更新后的角色数据
    """
    from app.api.app import postgres_db
    from app.models.character import CharacterImportanceTier

    importance_tier = char_data.get("importance_tier", CharacterImportanceTier.NPC.value)
    role = char_data.get("role", "supporting")
    name = char_data.get("name", "")
    description = char_data.get("description", "")
    personality = char_data.get("personality", "")
    background = char_data.get("background_story") or char_data.get("background", "")
    existing_goals = char_data.get("goals", [])
    project_id = char_data.get("project_id")

    # ========== 基于重要性层级决定是否启用 Agent ==========
    # Tier 1-3: 必须启用 Agent
    tier_1_3 = [
        CharacterImportanceTier.PROTAGONIST.value,
        CharacterImportanceTier.CO_PROTAGONIST.value,
        CharacterImportanceTier.DEUTERAGONIST.value,
        CharacterImportanceTier.MENTOR.value,
        CharacterImportanceTier.LOVE_INTEREST.value,
        CharacterImportanceTier.BEST_FRIEND.value,
        CharacterImportanceTier.ARCHENEMY.value,
        CharacterImportanceTier.MAJOR_ALLY.value,
        CharacterImportanceTier.MAJOR_ANTAGONIST.value,
        CharacterImportanceTier.RIVAL.value,
        CharacterImportanceTier.FAMILY_MEMBER.value,
        CharacterImportanceTier.GUARDIAN.value,
    ]

    # Tier 4: 部分启用
    tier_4_enable = [
        CharacterImportanceTier.ARC_ALLY.value,
        CharacterImportanceTier.ARC_ANtagonist.value,
        CharacterImportanceTier.MYSTERY_FIGURE.value,
        CharacterImportanceTier.CATALYST.value,
    ]
    tier_4_disable = [
        CharacterImportanceTier.RECURRING.value,  # 常驻配角可以不启用
    ]

    # Tier 5-6: 不启用
    tier_5_6 = [
        CharacterImportanceTier.MINION.value,
        CharacterImportanceTier.INFORMANT.value,
        CharacterImportanceTier.MENTOR_FIGURE.value,
        CharacterImportanceTier.COMIC_RELIEF.value,
        CharacterImportanceTier.VICTIM.value,
        CharacterImportanceTier.NPC.value,
        CharacterImportanceTier.BACKGROUND.value,
        CharacterImportanceTier.CAMEO.value,
    ]

    # 决定是否启用 Agent
    if importance_tier in tier_1_3:
        char_data["has_agent"] = True
        char_data["agent_enabled"] = True
    elif importance_tier in tier_4_enable:
        char_data["has_agent"] = True
        char_data["agent_enabled"] = True
    elif importance_tier in tier_4_disable:
        # 阶段性配角可以选择性启用
        char_data["has_agent"] = True
        char_data["agent_enabled"] = True
    elif importance_tier in tier_5_6:
        char_data["has_agent"] = False
        char_data["agent_enabled"] = False
        return char_data
    else:
        # 兜底：根据 role 判断
        if role in ["main", "antagonist"]:
            char_data["has_agent"] = True
            char_data["agent_enabled"] = True
        else:
            char_data["has_agent"] = False
            char_data["agent_enabled"] = False
            return char_data

    # ========== 调用 Setting Agent 生成性格设定 ==========
    # 只有重要角色才生成性格
    should_generate_personality = importance_tier in tier_1_3 or importance_tier in tier_4_enable

    if not personality and project_id and should_generate_personality:
        try:
            from app.services.setting_agent_service import get_setting_agent_service

            setting_agent = get_setting_agent_service()

            # 获取现有角色（避免性格重复）
            existing_characters = []
            if postgres_db:
                existing_characters = await postgres_db.get_all_characters(project_id=project_id, limit=10)

            # 调用 Setting Agent 生成性格
            personality_result = await setting_agent.generate_character_personality(
                project_id=project_id,
                character_data=char_data,
                existing_characters=existing_characters,
            )

            if personality_result.get("success"):
                # 更新性格相关字段
                if personality_result.get("personality"):
                    char_data["personality"] = personality_result["personality"]
                if personality_result.get("speech_pattern"):
                    char_data["speech_pattern"] = personality_result["speech_pattern"]
                if personality_result.get("agent_goals"):
                    char_data["agent_goals"] = personality_result["agent_goals"]
                if personality_result.get("agent_memory"):
                    char_data["agent_memory"] = personality_result["agent_memory"]

                logger.info(f"Setting Agent 为角色 '{name}' 生成了性格设定")

        except Exception as e:
            logger.warning(f"调用 Setting Agent 生成性格失败: {e}")
            # 继续使用默认配置

    # ========== 如果还没有 Agent 目标，根据层级生成默认目标 ==========
    if not char_data.get("agent_goals"):
        agent_goals = list(existing_goals) if existing_goals else []

        # 根据重要性层级添加默认目标
        tier_goals = {
            # Tier 1: 主角层
            CharacterImportanceTier.PROTAGONIST.value: [
                "推动故事主线发展",
                "展现人物成长与变化",
                "追求角色的核心目标",
            ],
            CharacterImportanceTier.CO_PROTAGONIST.value: [
                "与主角共同推动剧情",
                "展现独立的人物弧光",
                "在关键时刻发挥作用",
            ],
            # Tier 2: 核心配角层
            CharacterImportanceTier.DEUTERAGONIST.value: [
                "辅助主线发展",
                "展现自身的成长故事",
                "与主角形成互动张力",
            ],
            CharacterImportanceTier.MENTOR.value: [
                "引导主角成长",
                "在关键时刻提供指导",
                "传承知识或力量",
            ],
            CharacterImportanceTier.LOVE_INTEREST.value: [
                "推动感情线发展",
                "与主角形成情感纽带",
                "影响主角的决策",
            ],
            CharacterImportanceTier.BEST_FRIEND.value: [
                "陪伴主角成长",
                "提供支持和帮助",
                "增加故事的温暖感",
            ],
            CharacterImportanceTier.ARCHENEMY.value: [
                "制造故事冲突",
                "推动剧情走向高潮",
                "与主角形成对立",
            ],
            # Tier 3: 重要配角层
            CharacterImportanceTier.MAJOR_ALLY.value: [
                "在关键时刻帮助主角",
                "展现自身的故事线",
                "丰富故事的层次",
            ],
            CharacterImportanceTier.MAJOR_ANTAGONIST.value: [
                "制造阶段性冲突",
                "推动特定篇章的发展",
                "给主角带来挑战",
            ],
            CharacterImportanceTier.RIVAL.value: [
                "与主角形成竞争关系",
                "推动主角进步",
                "增加故事张力",
            ],
            CharacterImportanceTier.FAMILY_MEMBER.value: [
                "展现主角的背景",
                "提供情感支持或冲突",
                "丰富主角的人物形象",
            ],
            CharacterImportanceTier.GUARDIAN.value: [
                "保护主角",
                "在危急时刻出现",
                "传递重要信息",
            ],
            # Tier 4: 阶段性角色层
            CharacterImportanceTier.ARC_ANtagonist.value: [
                "制造篇章冲突",
                "推动篇章剧情发展",
                "给主角带来阶段性挑战",
            ],
            CharacterImportanceTier.ARC_ALLY.value: [
                "帮助主角完成篇章目标",
                "丰富篇章内容",
            ],
            CharacterImportanceTier.CATALYST.value: [
                "推动剧情转折",
                "引发重要事件",
            ],
            CharacterImportanceTier.MYSTERY_FIGURE.value: [
                "保持神秘感",
                "在关键时刻揭示身份",
            ],
        }

        default_goals = tier_goals.get(importance_tier, [
            "参与故事发展",
            "保持角色一致性",
        ])

        agent_goals.extend(default_goals)
        char_data["agent_goals"] = agent_goals

    return char_data


def _extract_goals_from_description(description: str, name: str) -> List[str]:
    """从描述中提取目标关键词"""
    goals = []

    # 常见目标关键词
    goal_keywords = [
        ("寻找", "寻找"),
        ("追求", "追求"),
        ("保护", "保护"),
        ("复仇", "复仇"),
        ("探索", "探索"),
        ("征服", "征服"),
        ("拯救", "拯救"),
        ("发现", "发现"),
        ("击败", "击败"),
        ("成为", "成为"),
        ("获得", "获得"),
        ("建立", "建立"),
        ("摧毁", "摧毁"),
        ("阻止", "阻止"),
        ("完成", "完成"),
    ]

    for keyword, goal_prefix in goal_keywords:
        if keyword in description:
            # 提取包含关键词的句子片段
            idx = description.find(keyword)
            # 提取关键词后面的内容（最多20个字）
            end_idx = min(idx + 30, len(description))
            fragment = description[idx:end_idx].strip()
            if fragment:
                goals.append(fragment)

    return goals[:5]


def _extract_memory_from_background(background: str) -> List[str]:
    """从背景中提取记忆要点"""
    memories = []

    # 按句子分割
    sentences = background.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n").split("\n")

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 5:
            continue

        # 检查是否是重要的记忆信息
        important_patterns = [
            "曾经", "以前", "过去", "小时候", "多年前",
            "因为", "由于", "所以", "导致",
            "经历了", "遭遇了", "失去了", "获得了",
            "家族", "亲人", "朋友", "敌人", "师父", "徒弟",
        ]

        for pattern in important_patterns:
            if pattern in sentence:
                memories.append(sentence[:100])  # 限制长度
                break

    return memories[:5]


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
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 检查角色是否存在
    existing = await postgres_db.get_character(character_id)
    if not existing:
        raise HTTPException(status_code=404, detail="角色不存在")

    char_data = character.model_dump(mode="json")

    # 确保使用正确的 ID 和时间戳
    char_data["id"] = character_id
    char_data["updated_at"] = datetime.now()

    # 保留原有的 created_at（如果存在）
    if existing.get("created_at"):
        char_data["created_at"] = existing["created_at"]

    # 确保 JSON 字段有默认值
    for field in ['personality_traits', 'lexicon', 'voice_samples', 'attributes', 'goals', 'inventory', 'agent_goals', 'agent_memory']:
        if char_data.get(field) is None:
            char_data[field] = [] if field in ['lexicon', 'voice_samples', 'goals', 'inventory', 'agent_goals', 'agent_memory'] else {}

    # 确保 Agent 布尔字段有默认值
    if char_data.get('has_agent') is None:
        char_data['has_agent'] = existing.get('has_agent', False)
    if char_data.get('agent_enabled') is None:
        char_data['agent_enabled'] = existing.get('agent_enabled', True)

    # 如果用户手动设置了 Agent 配置，保留用户设置
    # 否则自动配置
    if not char_data.get("agent_goals") and not char_data.get("agent_memory"):
        role = char_data.get("role", "supporting")
        if role in ["main", "antagonist", "supporting"] and char_data.get("has_agent"):
            char_data = await _auto_configure_character_agent(char_data)

    try:
        await postgres_db.save_character(char_data)
        return {
            "success": True,
            "id": character_id,
            "message": f"角色 '{character.name}' 更新成功",
            "has_agent": char_data.get("has_agent"),
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
    from app.api.app import postgres_db

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
    content: str = Query(..., description="记忆内容"),
    memory_type: str = Query(default="experience", description="记忆类型"),
    importance: float = Query(default=0.5, description="重要程度"),
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加记忆失败：{e}", exc_info=True)
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


@router.post("/{character_id}/voice-samples", response_model=Dict[str, Any])
async def add_character_voice_sample(character_id: str, sample: CharacterVoiceSample):
    from app.api.app import get_embedding_service, postgres_db, qdrant_db
    import logging
    logger = logging.getLogger(__name__)

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        character = await postgres_db.get_character(character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")

        if character_id != sample.character_id:
            raise HTTPException(status_code=400, detail="character_id 不匹配")

        updated_samples = list(character.get("voice_samples", []))
        if sample.text not in updated_samples:
            updated_samples.append(sample.text)

        character["voice_samples"] = updated_samples
        character["updated_at"] = datetime.utcnow().isoformat()
        await postgres_db.save_character(character)

        # 获取角色的 project_id
        project_id = character.get("project_id") or sample.project_id
        if project_id and hasattr(project_id, '__str__'):
            project_id = str(project_id)

        vector_id = None
        if qdrant_db:
            try:
                embedding = sample.embedding
                if embedding is None:
                    embedding_service = get_embedding_service()
                    if embedding_service:
                        embedding = await embedding_service.embed_text(sample.text)
                vector_id = await qdrant_db.add_character_voice_sample(
                    sample_id=sample.id,
                    character_id=character_id,
                    text=sample.text,
                    embedding=embedding,
                    context=sample.context,
                    project_id=project_id,
                )
            except Exception as e:
                logger.warning(f"Qdrant 添加失败: {e}")

        return {
            "success": True,
            "id": sample.id,
            "vector_id": vector_id,
            "project_id": project_id,
            "message": "角色声音样本添加成功",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加声音样本失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{character_id}/voice-samples/sync", response_model=Dict[str, Any])
async def sync_character_voice_samples(character_id: str):
    from app.api.app import postgres_db, qdrant_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    character = await postgres_db.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    if not qdrant_db:
        raise HTTPException(status_code=503, detail="Qdrant 未连接")

    deleted = await qdrant_db.delete_by_character(character_id, vector_type="voice_sample")

    # 获取 project_id
    project_id = character.get("project_id")
    if project_id and hasattr(project_id, '__str__'):
        project_id = str(project_id)

    inserted = 0
    for index, text in enumerate(character.get("voice_samples", [])):
        sample_id = f"{character_id}_voice_{index}"
        result = await qdrant_db.add_character_voice_sample(
            sample_id=sample_id,
            character_id=character_id,
            text=text,
            context=f"sync:{character_id}:{index}",
            project_id=project_id,
        )
        if result:
            inserted += 1

    return {
        "success": True,
        "deleted": deleted,
        "inserted": inserted,
        "message": "角色声音样本同步完成",
    }


@router.get("/{character_id}/voice-samples", response_model=List[Dict[str, Any]])
async def get_character_voice_samples(
    character_id: str,
    limit: int = Query(default=10, le=100),
    project_id: Optional[str] = Query(None, description="项目 ID 过滤"),
):
    from app.api.app import postgres_db, qdrant_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    character = await postgres_db.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 如果未传入 project_id，使用角色自身的 project_id
    effective_project_id = project_id or character.get("project_id")
    if effective_project_id and hasattr(effective_project_id, '__str__'):
        effective_project_id = str(effective_project_id)

    if qdrant_db:
        samples = await qdrant_db.get_character_voice_samples(
            character_id=character_id,
            limit=limit,
            project_id=effective_project_id,
        )
        if samples:
            return samples

    return [
        {
            "id": f"{character_id}_voice_{index}",
            "score": 1.0,
            "payload": {
                "type": "voice_sample",
                "character_id": character_id,
                "text": text,
                "context": "",
            },
        }
        for index, text in enumerate(character.get("voice_samples", [])[:limit])
    ]


@router.post("/{character_id}/voice-samples/search", response_model=List[Dict[str, Any]])
async def search_character_voice_samples(
    character_id: str,
    query_text: str,
    limit: int = Query(default=5, le=20),
    project_id: Optional[str] = Query(None, description="项目 ID 过滤"),
):
    from app.api.app import postgres_db, qdrant_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    character = await postgres_db.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    if not qdrant_db:
        raise HTTPException(status_code=503, detail="Qdrant 未连接")

    # 如果未传入 project_id，使用角色自身的 project_id
    effective_project_id = project_id or character.get("project_id")
    if effective_project_id and hasattr(effective_project_id, '__str__'):
        effective_project_id = str(effective_project_id)

    return await qdrant_db.get_similar_voice_samples_by_text(
        query_text=query_text,
        character_id=character_id,
        project_id=effective_project_id,
        limit=limit,
    )


@router.get("/{character_id}/agent-prompt", response_model=Dict[str, Any])
async def get_character_agent_prompt(character_id: str):
    """
    获取角色 Agent 的 Prompt 预览

    Args:
        character_id: 角色 ID

    Returns:
        Dict: Agent Prompt 预览
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    character = await postgres_db.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    if not character.get("has_agent"):
        return {
            "has_agent": False,
            "message": "该角色未启用 Agent"
        }

    # 构建角色 Agent 的 Prompt
    from app.services.agent_prompt_service import get_agent_prompt_service

    service = get_agent_prompt_service()

    # 准备变量
    variables = {
        "character_background": character.get("background_story") or character.get("background") or character.get("description") or "一个神秘的角色",
        "character_personality": character.get("personality") or character.get("speech_pattern") or "性格未知",
        "character_goals": "\n".join(character.get("agent_goals") or character.get("goals") or []),
    }

    # 构建完整 prompt
    prompt = await service.build_agent_prompt(
        agent_type="character",
        project_id=character.get("project_id"),
        variables=variables,
    )

    return {
        "has_agent": True,
        "agent_enabled": character.get("agent_enabled", True),
        "character_id": character_id,
        "character_name": character.get("name"),
        "variables": variables,
        "prompt": prompt,
        "prompt_length": len(prompt),
        "agent_goals": character.get("agent_goals", []),
        "agent_memory": character.get("agent_memory", []),
    }


@router.post("/batch-enable-agents", response_model=Dict[str, Any])
async def batch_enable_character_agents(
    project_id: str = Query(..., description="项目 ID"),
    roles: Optional[str] = Query(default="main,antagonist,supporting", description="要启用 Agent 的角色类型，逗号分隔"),
):
    """
    批量为项目中的角色启用 Agent

    Args:
        project_id: 项目 ID
        roles: 要启用 Agent 的角色类型

    Returns:
        Dict: 批量启用结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 解析角色类型
    role_list = [r.strip() for r in roles.split(",")] if roles else ["main", "antagonist", "supporting"]

    # 获取项目中的角色
    characters = await postgres_db.get_all_characters(project_id=project_id, limit=500)

    updated_count = 0
    skipped_count = 0
    errors = []

    for char in characters:
        char_role = char.get("role", "")

        # 检查是否在目标角色类型中
        if char_role not in role_list:
            continue

        # 如果已经有 Agent，跳过
        if char.get("has_agent") and char.get("agent_goals"):
            skipped_count += 1
            continue

        try:
            # 自动配置 Agent
            char["has_agent"] = True
            char["agent_enabled"] = True
            char = await _auto_configure_character_agent(char)

            await postgres_db.save_character(char)
            updated_count += 1
            logger.info(f"为角色 '{char.get('name')}' 启用 Agent")
        except Exception as e:
            errors.append(f"{char.get('name')}: {str(e)}")
            logger.error(f"为角色 '{char.get('name')}' 启用 Agent 失败: {e}")

    return {
        "success": True,
        "message": f"批量启用 Agent 完成",
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "error_count": len(errors),
        "errors": errors[:10],  # 只返回前10个错误
    }


@router.post("/{character_id}/generate-personality", response_model=Dict[str, Any])
async def generate_character_personality(character_id: str):
    """
    为角色生成性格设定（调用 Setting Agent）

    Args:
        character_id: 角色 ID

    Returns:
        Dict: 生成的性格数据
    """
    from app.api.app import postgres_db
    from app.services.setting_agent_service import get_setting_agent_service

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 获取角色数据
    character = await postgres_db.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    project_id = character.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="角色没有关联项目")

    try:
        setting_agent = get_setting_agent_service()

        # 获取现有角色（避免性格重复）
        existing_characters = await postgres_db.get_all_characters(project_id=project_id, limit=10)

        # 调用 Setting Agent 生成性格
        personality_result = await setting_agent.generate_character_personality(
            project_id=project_id,
            character_data=character,
            existing_characters=existing_characters,
        )

        if not personality_result.get("success"):
            return {
                "success": False,
                "message": personality_result.get("error", "生成失败"),
            }

        # 更新角色数据
        if personality_result.get("appearance"):
            character["appearance"] = personality_result["appearance"]
        if personality_result.get("personality"):
            character["personality"] = personality_result["personality"]
        if personality_result.get("speech_pattern"):
            character["speech_pattern"] = personality_result["speech_pattern"]
        if personality_result.get("agent_goals"):
            character["agent_goals"] = personality_result["agent_goals"]
        if personality_result.get("agent_memory"):
            character["agent_memory"] = personality_result["agent_memory"]

        # 启用 Agent
        character["has_agent"] = True
        character["agent_enabled"] = True
        character["updated_at"] = datetime.now()

        # 保存到数据库
        await postgres_db.save_character(character)

        return {
            "success": True,
            "message": f"已为角色 '{character['name']}' 生成性格设定",
            "appearance": personality_result.get("appearance", ""),
            "personality": personality_result.get("personality", ""),
            "speech_pattern": personality_result.get("speech_pattern", ""),
            "agent_goals": personality_result.get("agent_goals", []),
            "agent_memory": personality_result.get("agent_memory", []),
        }

    except Exception as e:
        logger.error(f"生成角色性格失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
