"""
写作规则管理 API 路由
v7 核心需求：写作规则、规则集、项目写作配置的管理
"""

import json
import logging
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
from app.services.writing_rule_service import get_writing_rule_service
from app.services.writing_rule_rag import get_writing_rule_rag_service
from app.services.writing_rules_init import get_system_writing_rules, get_writing_rules_stats

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_rule_service():
    return get_writing_rule_service()


def get_writing_rules_service():
    return _get_rule_service()


def _normalize_project_config(config: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(config)
    data.pop("custom_rules", None)
    return data


def _normalize_rule_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    anti_patterns = data.pop("anti_patterns", None)
    if anti_patterns is not None and data.get("counter_examples") is None:
        data["counter_examples"] = anti_patterns
    return data


def _serialize_rule(rule: WritingRule) -> Dict[str, Any]:
    data = rule.dict()
    data["anti_patterns"] = data.get("counter_examples") or []
    return data


def _normalize_rule_set_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    target_genre = data.pop("target_genre", None)
    if target_genre is not None and data.get("target_genres") is None:
        data["target_genres"] = [target_genre] if target_genre else []
    return data


def _serialize_rule_set(rule_set: WritingRuleSet) -> Dict[str, Any]:
    data = rule_set.dict()
    target_genres = data.get("target_genres") or []
    data["target_genre"] = target_genres[0] if target_genres else ""
    return data


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
    service = _get_rule_service()
    rules = await service.list_rules_merged(
        category=category,
        severity=severity,
        tags=tags,
        is_system=is_system,
        search=search,
        source=source,
        limit=limit,
        offset=offset,
    )
    return [_serialize_rule(rule) for rule in rules]


@router.post("/writing-rules", response_model=Dict[str, Any])
async def create_writing_rule(request: WritingRuleCreate):
    service = _get_rule_service()
    payload = _normalize_rule_payload(request.dict())
    rule = await service.create_rule(WritingRuleCreate(**payload))
    return {
        "success": True,
        "message": "写作规则创建成功",
        "rule": _serialize_rule(rule),
    }


@router.get("/writing-rules/{rule_id}", response_model=Dict[str, Any])
async def get_writing_rule(rule_id: str):
    service = _get_rule_service()
    rule = await service.get_rule_merged(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"规则 {rule_id} 不存在")
    return _serialize_rule(rule)


@router.put("/writing-rules/{rule_id}", response_model=Dict[str, Any])
async def update_writing_rule(rule_id: str, request: WritingRuleUpdate):
    service = _get_rule_service()
    payload = _normalize_rule_payload(request.dict(exclude_unset=True))
    rule, error = await service.update_rule(rule_id, WritingRuleUpdate(**payload))

    if error == "is_system":
        raise HTTPException(status_code=403, detail="系统内置规则不可修改")
    if error == "not_found" or not rule:
        raise HTTPException(status_code=404, detail=f"规则 {rule_id} 不存在")

    return {
        "success": True,
        "message": f"规则 {rule_id} 更新成功",
        "rule": _serialize_rule(rule),
    }


@router.delete("/writing-rules/{rule_id}", response_model=Dict[str, Any])
async def delete_writing_rule(rule_id: str):
    service = _get_rule_service()
    success, error = await service.delete_rule(rule_id)

    if error == "is_system":
        raise HTTPException(status_code=403, detail="系统内置规则不可删除")
    if error == "in_use":
        raise HTTPException(status_code=400, detail="规则仍被规则集引用，无法删除")
    if error == "not_found" or not success:
        raise HTTPException(status_code=404, detail=f"规则 {rule_id} 不存在")
    return {
        "success": True,
        "message": f"规则 {rule_id} 删除成功",
        "rule_id": rule_id,
    }


@router.get("/writing-rules/categories/list", response_model=Dict[str, Any])
async def list_writing_rule_categories():
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
                "count": count,
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
    service = _get_rule_service()
    rule_sets = await service.list_rule_sets_merged(
        category=category,
        tags=tags,
        target_genre=target_genre,
        is_system=is_system,
        limit=limit,
        offset=offset,
    )
    return [_serialize_rule_set(rule_set) for rule_set in rule_sets]


@router.post("/writing-rule-sets", response_model=Dict[str, Any])
async def create_writing_rule_set(request: WritingRuleSetCreate):
    service = _get_rule_service()
    payload = _normalize_rule_set_payload(request.dict())
    rule_set = await service.create_rule_set(WritingRuleSetCreate(**payload))
    return {
        "success": True,
        "message": "写作规则集创建成功",
        "rule_set": _serialize_rule_set(rule_set),
    }


@router.get("/writing-rule-sets/{rule_set_id}", response_model=Dict[str, Any])
async def get_writing_rule_set(rule_set_id: str):
    service = _get_rule_service()
    rule_set = await service.get_rule_set_merged(rule_set_id)
    if not rule_set:
        raise HTTPException(status_code=404, detail=f"规则集 {rule_set_id} 不存在")

    rules = []
    for rule_id in rule_set.rule_ids:
        rule = await service.get_rule_merged(rule_id)
        if rule:
            rules.append(_serialize_rule(rule))

    data = _serialize_rule_set(rule_set)
    data["rules"] = rules
    return data


@router.put("/writing-rule-sets/{rule_set_id}", response_model=Dict[str, Any])
async def update_writing_rule_set(rule_set_id: str, request: WritingRuleSetUpdate):
    service = _get_rule_service()
    payload = _normalize_rule_set_payload(request.dict(exclude_unset=True))
    rule_set, error = await service.update_rule_set(rule_set_id, WritingRuleSetUpdate(**payload))

    if error == "is_system":
        raise HTTPException(status_code=403, detail="系统内置规则集不可修改")
    if error == "not_found" or not rule_set:
        raise HTTPException(status_code=404, detail=f"规则集 {rule_set_id} 不存在")

    return {
        "success": True,
        "message": f"规则集 {rule_set_id} 更新成功",
        "rule_set": _serialize_rule_set(rule_set),
    }


@router.delete("/writing-rule-sets/{rule_set_id}", response_model=Dict[str, Any])
async def delete_writing_rule_set(rule_set_id: str):
    service = _get_rule_service()
    success, error = await service.delete_rule_set(rule_set_id)

    if error == "is_system":
        raise HTTPException(status_code=403, detail="系统内置规则集不可删除")
    if error == "not_found" or not success:
        raise HTTPException(status_code=404, detail=f"规则集 {rule_set_id} 不存在")

    return {
        "success": True,
        "message": f"规则集 {rule_set_id} 删除成功",
        "rule_set_id": rule_set_id,
    }


# ==================== ProjectWritingConfig API ====================

@router.get("/projects/{project_id}/writing-config", response_model=Dict[str, Any])
async def get_project_writing_config(project_id: str):
    service = _get_rule_service()
    config = await service.get_project_writing_config(project_id)
    config_dict = _normalize_project_config(config.dict())

    try:
        from app.services.agent_prompt_service import get_agent_prompt_service
        prompt_service = get_agent_prompt_service()
        prompt_service.update_project_writing_config(
            project_id=project_id,
            enabled_rule_ids=config_dict.get("enabled_rule_ids", []),
            enabled_rule_set_ids=config_dict.get("enabled_rule_set_ids", []),
        )
    except Exception as e:
        logger.warning(f"同步 AgentPromptService 失败: {e}")

    return config_dict


@router.put("/projects/{project_id}/writing-config", response_model=Dict[str, Any])
async def update_project_writing_config(project_id: str, request: ProjectWritingConfigUpdate):
    service = _get_rule_service()
    config = await service.update_project_writing_config(project_id, request)
    if not config:
        raise HTTPException(status_code=500, detail="更新项目写作配置失败")

    config_dict = _normalize_project_config(config.dict())

    try:
        from app.services.agent_prompt_service import get_agent_prompt_service
        prompt_service = get_agent_prompt_service()
        prompt_service.update_project_writing_config(
            project_id=project_id,
            enabled_rule_ids=config_dict.get("enabled_rule_ids", []),
            enabled_rule_set_ids=config_dict.get("enabled_rule_set_ids", []),
        )
    except Exception as e:
        logger.warning(f"同步更新 AgentPromptService 失败: {e}")

    return {
        "success": True,
        "message": f"项目 {project_id} 写作配置更新成功",
        "config": config_dict,
    }


@router.post("/projects/{project_id}/writing-config/preview", response_model=Dict[str, Any])
async def preview_writing_prompt(project_id: str, context: Optional[Dict[str, Any]] = None):
    rag_service = get_writing_rule_rag_service()
    result = await rag_service.retrieve_for_project(project_id, context=context, limit=6)
    result["context"] = context or {}
    return result


@router.post("/writing-rules/build-prompt", response_model=Dict[str, Any])
async def build_custom_prompt(
    rule_ids: Optional[List[str]] = None,
    rule_set_ids: Optional[List[str]] = None,
    category: Optional[str] = None,
    severity_min: Optional[str] = "recommended",
):
    service = _get_rule_service()
    prompt = await service.build_prompt(
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
    return get_writing_rules_stats()

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

    response = {
        "agent_type": agent_type,
        "project_id": project_id,
        "prompt": prompt,
        "prompt_length": len(prompt),
    }

    if project_id:
        try:
            rule_service = get_writing_rule_service()
            scope = await rule_service.resolve_project_rule_scope(project_id)
            response["writing_rule_scope"] = rule_service.describe_project_rule_scope(scope)
            response["writing_rule_preview"] = await get_writing_rule_rag_service().retrieve_for_project(
                project_id,
                context=variables or {},
                limit=4,
            )
        except Exception as e:
            logger.warning(f"构建 Agent prompt 写作规则预览失败: {e}")

    return response
