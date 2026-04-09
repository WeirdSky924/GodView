"""
写作规则管理 API 路由
v7 核心需求：写作规则、规则集、项目写作配置的管理
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.writing_rule import (
    WritingRule,
    WritingRuleCreate,
    WritingRuleUpdate,
    WritingRuleSet,
    WritingRuleSetCreate,
    WritingRuleSetUpdate,
    ProjectWritingConfig,
    ProjectWritingConfigUpdate,
)
from app.services.writing_rules_init import (
    get_system_writing_rules,
    get_system_rule_sets,
    get_system_rule_by_id,
    get_system_rule_set_by_id,
    build_writing_prompt,
    get_writing_rules_stats,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db():
    """获取数据库实例"""
    from app.api.app import postgres_db
    return postgres_db


def _json_to_str(value: Any) -> str:
    """将值转换为 JSON 字符串"""
    if value is None:
        return '[]'
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _str_to_json(value: str, default: Any = None) -> Any:
    """将 JSON 字符串转换为 Python 对象"""
    if not value:
        return default or []
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default or []


# ==================== WritingRule API ====================

@router.get("/writing-rules", response_model=List[Dict[str, Any]])
async def list_writing_rules(
    category: Optional[str] = Query(default=None, description="规则分类过滤"),
    severity: Optional[str] = Query(default=None, description="严重程度过滤"),
    tags: Optional[List[str]] = Query(default=None, description="标签过滤"),
    is_system: Optional[bool] = Query(default=None, description="是否系统内置过滤"),
    search: Optional[str] = Query(default=None, description="搜索关键词"),
    source: Optional[str] = Query(default=None, description="来源过滤 (fanqie/web_novel)"),
    limit: int = Query(default=50, le=500, description="返回数量限制"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
):
    """
    获取写作规则列表

    Args:
        category: 规则分类过滤 (dialogue/structure/style/character/plot/pacing/format)
        severity: 严重程度过滤 (required/strong/recommended/optional/info)
        tags: 标签过滤
        is_system: 是否系统内置过滤
        search: 搜索关键词
        source: 来源过滤 (fanqie/web_novel)
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        List: 写作规则列表
    """
    # 获取系统规则
    rules = get_system_writing_rules(
        category=category,
        severity=severity,
        tags=tags,
        search=search,
        source=source,
    )

    # 标记为系统规则
    for rule in rules:
        rule["is_system"] = True

    # 应用分页
    total = len(rules)
    rules = rules[offset:offset + limit]

    return rules


@router.post("/writing-rules", response_model=Dict[str, Any])
async def create_writing_rule(request: WritingRuleCreate):
    """
    创建写作规则（自定义规则）

    Args:
        request: 创建规则请求

    Returns:
        Dict: 创建结果
    """
    # TODO: 实现数据库持久化
    # 目前返回模拟数据
    import uuid
    rule_id = f"custom_{uuid.uuid4().hex[:8]}"

    return {
        "success": True,
        "message": "写作规则创建成功",
        "rule": {
            "id": rule_id,
            **request.dict(),
            "is_system": False,
        },
    }


@router.get("/writing-rules/{rule_id}", response_model=Dict[str, Any])
async def get_writing_rule(rule_id: str):
    """
    获取写作规则详情

    Args:
        rule_id: 规则ID

    Returns:
        Dict: 规则详情
    """
    # 先查找系统规则
    rule = get_system_rule_by_id(rule_id)
    if rule:
        rule["is_system"] = True
        return rule

    # TODO: 查找自定义规则

    raise HTTPException(status_code=404, detail=f"规则 {rule_id} 不存在")


@router.put("/writing-rules/{rule_id}", response_model=Dict[str, Any])
async def update_writing_rule(rule_id: str, request: WritingRuleUpdate):
    """
    更新写作规则

    Args:
        rule_id: 规则ID
        request: 更新规则请求

    Returns:
        Dict: 更新结果
    """
    # 检查是否为系统规则
    rule = get_system_rule_by_id(rule_id)
    if rule:
        raise HTTPException(status_code=400, detail="系统规则不可修改")

    # TODO: 实现自定义规则的更新
    return {
        "success": True,
        "message": f"规则 {rule_id} 更新成功",
        "rule_id": rule_id,
    }


@router.delete("/writing-rules/{rule_id}", response_model=Dict[str, Any])
async def delete_writing_rule(rule_id: str):
    """
    删除写作规则

    Args:
        rule_id: 规则ID

    Returns:
        Dict: 删除结果
    """
    # 检查是否为系统规则
    rule = get_system_rule_by_id(rule_id)
    if rule:
        raise HTTPException(status_code=400, detail="系统规则不可删除")

    # TODO: 实现自定义规则的删除
    return {
        "success": True,
        "message": f"规则 {rule_id} 删除成功",
        "rule_id": rule_id,
    }


@router.get("/writing-rules/categories/list", response_model=Dict[str, Any])
async def list_writing_rule_categories():
    """
    获取写作规则分类统计

    Returns:
        Dict: 分类统计
    """
    rules = get_system_writing_rules()

    categories = {}
    for rule in rules:
        cat = rule.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1

    category_labels = {
        "dialogue": "对话类",
        "structure": "结构类",
        "style": "风格类",
        "character": "角色塑造类",
        "plot": "剧情类",
        "pacing": "节奏类",
        "format": "格式类",
        "grammar": "语法类",
    }

    return {
        "categories": {
            key: {
                "label": category_labels.get(key, key),
                "count": count
            }
            for key, count in categories.items()
        }
    }


# ==================== WritingRuleSet API ====================

@router.get("/writing-rule-sets", response_model=List[Dict[str, Any]])
async def list_writing_rule_sets(
    category: Optional[str] = Query(default=None, description="规则集分类过滤"),
    tags: Optional[List[str]] = Query(default=None, description="标签过滤"),
    target_genre: Optional[str] = Query(default=None, description="目标体裁过滤"),
    is_system: Optional[bool] = Query(default=None, description="是否系统内置过滤"),
    limit: int = Query(default=50, le=500, description="返回数量限制"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
):
    """
    获取写作规则集列表

    Args:
        category: 规则集分类过滤
        tags: 标签过滤
        target_genre: 目标体裁过滤
        is_system: 是否系统内置过滤
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        List: 规则集列表
    """
    rule_sets = get_system_rule_sets(
        category=category,
        tags=tags,
        target_genre=target_genre,
    )

    for rs in rule_sets:
        rs["is_system"] = True

    total = len(rule_sets)
    rule_sets = rule_sets[offset:offset + limit]

    return rule_sets


@router.post("/writing-rule-sets", response_model=Dict[str, Any])
async def create_writing_rule_set(request: WritingRuleSetCreate):
    """
    创建写作规则集

    Args:
        request: 创建规则集请求

    Returns:
        Dict: 创建结果
    """
    import uuid
    rule_set_id = f"ruleset_{uuid.uuid4().hex[:8]}"

    return {
        "success": True,
        "message": "写作规则集创建成功",
        "rule_set": {
            "id": rule_set_id,
            **request.dict(),
            "is_system": False,
        },
    }


@router.get("/writing-rule-sets/{rule_set_id}", response_model=Dict[str, Any])
async def get_writing_rule_set(rule_set_id: str):
    """
    获取写作规则集详情

    Args:
        rule_set_id: 规则集ID

    Returns:
        Dict: 规则集详情
    """
    rule_set = get_system_rule_set_by_id(rule_set_id)
    if rule_set:
        rule_set["is_system"] = True

        # 展开规则详情
        rule_details = []
        for rule_id in rule_set.get("rule_ids", []):
            rule = get_system_rule_by_id(rule_id)
            if rule:
                rule_details.append({
                    "id": rule["id"],
                    "name": rule["name"],
                    "category": rule["category"],
                    "severity": rule["severity"],
                })
        rule_set["rules"] = rule_details

        return rule_set

    raise HTTPException(status_code=404, detail=f"规则集 {rule_set_id} 不存在")


@router.put("/writing-rule-sets/{rule_set_id}", response_model=Dict[str, Any])
async def update_writing_rule_set(rule_set_id: str, request: WritingRuleSetUpdate):
    """
    更新写作规则集

    Args:
        rule_set_id: 规则集ID
        request: 更新规则集请求

    Returns:
        Dict: 更新结果
    """
    # 检查是否为系统规则集
    rule_set = get_system_rule_set_by_id(rule_set_id)
    if rule_set:
        raise HTTPException(status_code=400, detail="系统规则集不可修改")

    # TODO: 实现自定义规则集的更新
    return {
        "success": True,
        "message": f"规则集 {rule_set_id} 更新成功",
        "rule_set_id": rule_set_id,
    }


@router.delete("/writing-rule-sets/{rule_set_id}", response_model=Dict[str, Any])
async def delete_writing_rule_set(rule_set_id: str):
    """
    删除写作规则集

    Args:
        rule_set_id: 规则集ID

    Returns:
        Dict: 删除结果
    """
    # 检查是否为系统规则集
    rule_set = get_system_rule_set_by_id(rule_set_id)
    if rule_set:
        raise HTTPException(status_code=400, detail="系统规则集不可删除")

    # TODO: 实现自定义规则集的删除
    return {
        "success": True,
        "message": f"规则集 {rule_set_id} 删除成功",
        "rule_set_id": rule_set_id,
    }


# ==================== ProjectWritingConfig API ====================

@router.get("/projects/{project_id}/writing-config", response_model=Dict[str, Any])
async def get_project_writing_config(project_id: str):
    """
    获取项目写作配置

    Args:
        project_id: 项目ID

    Returns:
        Dict: 项目写作配置
    """
    db = _get_db()

    # 默认配置
    default_config = {
        "project_id": project_id,
        "enabled_rule_ids": [],
        "enabled_rule_set_ids": ["rule_set_web_novel_basics"],
        "rule_overrides": {},
        "rule_priorities": {},
        "default_severity": "recommended",
        "apply_to_chapters": True,
        "apply_to_characters": True,
        "apply_to_descriptions": True,
        "apply_to_narration": True,
        "is_active": True,
    }

    if db is None:
        logger.warning("数据库未连接，返回默认配置")
        return default_config

    try:
        rows = await db.execute_query(
            "SELECT * FROM project_writing_configs WHERE project_id = :project_id",
            {"project_id": project_id}
        )

        if rows:
            row = rows[0]
            config = {
                "project_id": project_id,
                "enabled_rule_ids": _str_to_json(row.get("enabled_rule_ids"), []),
                "enabled_rule_set_ids": _str_to_json(row.get("enabled_rule_set_ids"), []),
                "rule_overrides": _str_to_json(row.get("rule_overrides"), {}),
                "rule_priorities": _str_to_json(row.get("rule_priorities"), {}),
                "default_severity": row.get("default_severity", "recommended"),
                "apply_to_chapters": row.get("apply_to_chapters", True),
                "apply_to_characters": row.get("apply_to_characters", True),
                "apply_to_descriptions": row.get("apply_to_descriptions", True),
                "apply_to_narration": row.get("apply_to_narration", True),
                "is_active": row.get("is_active", True),
            }

            # 同步到 AgentPromptService
            try:
                from app.services.agent_prompt_service import get_agent_prompt_service
                service = get_agent_prompt_service()
                service.update_project_writing_config(
                    project_id=project_id,
                    enabled_rule_ids=config["enabled_rule_ids"],
                    enabled_rule_set_ids=config["enabled_rule_set_ids"],
                )
            except Exception as e:
                logger.warning(f"同步 AgentPromptService 失败: {e}")

            return config

        # 数据库中没有配置，返回默认配置
        return default_config

    except Exception as e:
        logger.error(f"获取项目写作配置失败: {e}")
        return default_config


@router.put("/projects/{project_id}/writing-config", response_model=Dict[str, Any])
async def update_project_writing_config(project_id: str, request: ProjectWritingConfigUpdate):
    """
    更新项目写作配置

    Args:
        project_id: 项目ID
        request: 更新配置请求

    Returns:
        Dict: 更新结果
    """
    db = _get_db()

    # 更新数据
    update_data = request.dict(exclude_unset=True)

    if db is None:
        logger.warning("数据库未连接，配置仅保存在内存中")
        # 同步更新 AgentPromptService
        try:
            from app.services.agent_prompt_service import get_agent_prompt_service
            service = get_agent_prompt_service()
            service.update_project_writing_config(
                project_id=project_id,
                enabled_rule_ids=update_data.get("enabled_rule_ids", []),
                enabled_rule_set_ids=update_data.get("enabled_rule_set_ids", []),
            )
        except Exception as e:
            logger.warning(f"同步 AgentPromptService 失败: {e}")

        return {
            "success": True,
            "message": f"项目 {project_id} 写作配置更新成功（仅内存）",
            "config": {"project_id": project_id, **update_data},
        }

    try:
        # 检查是否存在配置
        existing = await db.execute_query(
            "SELECT id FROM project_writing_configs WHERE project_id = :project_id",
            {"project_id": project_id}
        )

        config_id = str(uuid.uuid4()) if not existing else existing[0]["id"]

        # 准备 JSON 字段
        enabled_rule_ids = _json_to_str(update_data.get("enabled_rule_ids", []))
        enabled_rule_set_ids = _json_to_str(update_data.get("enabled_rule_set_ids", []))
        rule_overrides = _json_to_str(update_data.get("rule_overrides", {}))
        rule_priorities = _json_to_str(update_data.get("rule_priorities", {}))
        default_severity = update_data.get("default_severity", "recommended")
        is_active = update_data.get("is_active", True)

        if existing:
            # 更新现有配置
            await db.execute_write(
                """
                UPDATE project_writing_configs
                SET enabled_rule_ids = :enabled_rule_ids,
                    enabled_rule_set_ids = :enabled_rule_set_ids,
                    rule_overrides = :rule_overrides,
                    rule_priorities = :rule_priorities,
                    default_severity = :default_severity,
                    is_active = :is_active,
                    updated_at = NOW()
                WHERE project_id = :project_id
                """,
                {
                    "project_id": project_id,
                    "enabled_rule_ids": enabled_rule_ids,
                    "enabled_rule_set_ids": enabled_rule_set_ids,
                    "rule_overrides": rule_overrides,
                    "rule_priorities": rule_priorities,
                    "default_severity": default_severity,
                    "is_active": is_active,
                }
            )
        else:
            # 创建新配置
            await db.execute_write(
                """
                INSERT INTO project_writing_configs
                (id, project_id, enabled_rule_ids, enabled_rule_set_ids, rule_overrides,
                 rule_priorities, default_severity, is_active)
                VALUES
                (:id, :project_id, :enabled_rule_ids, :enabled_rule_set_ids, :rule_overrides,
                 :rule_priorities, :default_severity, :is_active)
                """,
                {
                    "id": config_id,
                    "project_id": project_id,
                    "enabled_rule_ids": enabled_rule_ids,
                    "enabled_rule_set_ids": enabled_rule_set_ids,
                    "rule_overrides": rule_overrides,
                    "rule_priorities": rule_priorities,
                    "default_severity": default_severity,
                    "is_active": is_active,
                }
            )

        # 同步更新 AgentPromptService
        try:
            from app.services.agent_prompt_service import get_agent_prompt_service
            service = get_agent_prompt_service()
            service.update_project_writing_config(
                project_id=project_id,
                enabled_rule_ids=update_data.get("enabled_rule_ids", []),
                enabled_rule_set_ids=update_data.get("enabled_rule_set_ids", []),
            )
            logger.info(f"已同步更新 AgentPromptService 中项目 {project_id} 的写作规则配置")
        except Exception as e:
            logger.warning(f"同步更新 AgentPromptService 失败: {e}")

        # 构建返回配置
        config = {
            "project_id": project_id,
            "enabled_rule_ids": _str_to_json(enabled_rule_ids, []),
            "enabled_rule_set_ids": _str_to_json(enabled_rule_set_ids, []),
            "rule_overrides": _str_to_json(rule_overrides, {}),
            "rule_priorities": _str_to_json(rule_priorities, {}),
            "default_severity": default_severity,
            "is_active": is_active,
        }

        return {
            "success": True,
            "message": f"项目 {project_id} 写作配置更新成功",
            "config": config,
        }

    except Exception as e:
        logger.error(f"更新项目写作配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/writing-config/preview", response_model=Dict[str, Any])
async def preview_writing_prompt(project_id: str, context: Optional[Dict[str, Any]] = None):
    """
    预览写作规则 prompt

    Args:
        project_id: 项目ID
        context: 上下文变量

    Returns:
        Dict: 预览结果
    """
    db = _get_db()

    # 默认配置
    enabled_rule_ids = []
    enabled_rule_set_ids = ["rule_set_web_novel_basics"]

    if db:
        try:
            rows = await db.execute_query(
                "SELECT enabled_rule_ids, enabled_rule_set_ids FROM project_writing_configs WHERE project_id = :project_id",
                {"project_id": project_id}
            )
            if rows:
                enabled_rule_ids = _str_to_json(rows[0].get("enabled_rule_ids"), [])
                enabled_rule_set_ids = _str_to_json(rows[0].get("enabled_rule_set_ids"), enabled_rule_set_ids)
        except Exception as e:
            logger.warning(f"获取项目配置失败，使用默认配置: {e}")

    # 构建提示词
    prompt = build_writing_prompt(
        rule_ids=enabled_rule_ids,
        rule_set_ids=enabled_rule_set_ids,
    )

    return {
        "project_id": project_id,
        "prompt": prompt,
        "context": context or {},
        "rule_count": len(enabled_rule_ids) +
                     sum(len(get_system_rule_set_by_id(rs_id).get("rule_ids", []))
                         for rs_id in enabled_rule_set_ids
                         if get_system_rule_set_by_id(rs_id)),
    }


@router.post("/writing-rules/build-prompt", response_model=Dict[str, Any])
async def build_custom_prompt(
    rule_ids: Optional[List[str]] = None,
    rule_set_ids: Optional[List[str]] = None,
    category: Optional[str] = None,
    severity_min: Optional[str] = "recommended",
):
    """
    构建自定义写作规则提示词

    Args:
        rule_ids: 规则ID列表
        rule_set_ids: 规则集ID列表
        category: 只包含指定分类
        severity_min: 最低严重程度

    Returns:
        Dict: 提示词结果
    """
    prompt = build_writing_prompt(
        rule_ids=rule_ids,
        rule_set_ids=rule_set_ids,
        category=category,
        severity_min=severity_min,
    )

    return {
        "prompt": prompt,
        "rule_ids": rule_ids or [],
        "rule_set_ids": rule_set_ids or [],
    }


@router.get("/writing-rules/stats", response_model=Dict[str, Any])
async def get_writing_rules_statistics():
    """
    获取写作规则统计信息

    Returns:
        Dict: 统计信息
    """
    return get_writing_rules_stats()


# ==================== Agent Prompt API ====================

@router.get("/agent-prompts", response_model=Dict[str, Any])
async def list_agent_prompts():
    """
    获取所有 Agent Prompt 模板列表

    Returns:
        Dict: 模板列表
    """
    from app.services.agent_prompt_service import get_agent_prompt_service
    service = get_agent_prompt_service()
    return {
        "templates": service.get_template_summary(),
    }


@router.post("/agent-prompts/{agent_type}/preview", response_model=Dict[str, Any])
async def preview_agent_prompt(
    agent_type: str,
    project_id: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
):
    """
    预览 Agent 的完整 system prompt

    Args:
        agent_type: Agent 类型 (summarizer, master_plotter, hook_manager, writer, evaluator, proc_gen, character, setting)
        project_id: 项目ID（可选，用于加载写作规则）
        variables: 模板变量（可选）

    Returns:
        Dict: 预览结果
    """
    from app.services.agent_prompt_service import get_agent_prompt_service
    service = get_agent_prompt_service()

    prompt = await service.build_agent_prompt(
        agent_type=agent_type,
        project_id=project_id,
        variables=variables,
    )

    return {
        "agent_type": agent_type,
        "project_id": project_id,
        "prompt": prompt,
        "prompt_length": len(prompt),
    }
