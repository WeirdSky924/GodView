"""
Agent 模板管理 API 路由
v7 核心需求：Agent 模板的 CRUD 操作、Prompt 插槽管理、预览渲染
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.agent_template import (
    AgentType,
    AgentTemplate,
    AgentTemplateCreate,
    AgentTemplateUpdate,
)
from app.models.prompt_template import PromptRenderRequest

logger = logging.getLogger(__name__)

# 写作规则服务实例
_writing_rules_service = None


def get_writing_rules_service():
    """获取写作规则服务实例"""
    global _writing_rules_service
    if _writing_rules_service is None:
        from app.api.routes.writing_rules import get_writing_rules_service as get_service
        _writing_rules_service = get_service()
    return _writing_rules_service

router = APIRouter()

# 模拟服务实例
_agent_template_service = None
_prompt_service = None


def get_agent_template_service():
    """获取 Agent 模板服务实例"""
    global _agent_template_service
    if _agent_template_service is None:
        from app.services.agent_template_service import AgentTemplateService
        _agent_template_service = AgentTemplateService()
    return _agent_template_service


def set_agent_template_service(service):
    """设置 Agent 模板服务实例（用于初始化）"""
    global _agent_template_service
    _agent_template_service = service


def get_prompt_service():
    """获取 Prompt 服务实例"""
    global _prompt_service
    if _prompt_service is None:
        from app.services.prompt_template_service import PromptTemplateService
        _prompt_service = PromptTemplateService()
    return _prompt_service


def set_prompt_service(service):
    """设置 Prompt 服务实例（用于初始化）"""
    global _prompt_service
    _prompt_service = service


# ==================== Agent Template CRUD API ====================

@router.get("/agent-templates", response_model=List[Dict[str, Any]])
async def list_agent_templates(
    agent_type: Optional[str] = Query(default=None, description="按 Agent 类型过滤"),
    is_system: Optional[bool] = Query(default=None, description="是否系统内置"),
    tags: Optional[List[str]] = Query(default=None, description="按标签过滤"),
    limit: int = Query(default=50, le=500, description="返回数量限制"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
):
    """
    获取 Agent 模板列表

    Args:
        agent_type: Agent 类型过滤
        is_system: 系统内置过滤
        tags: 标签过滤
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        List: Agent 模板列表
    """
    service = get_agent_template_service()

    # 安全转换 agent_type 枚举
    agent_type_enum = None
    if agent_type:
        try:
            agent_type_enum = AgentType(agent_type)
        except ValueError:
            pass  # 忽略无效的 agent_type 值

    try:
        templates = await service.list_templates(
            agent_type=agent_type_enum,
            is_system=is_system,
            tags=tags,
            limit=limit,
            offset=offset,
        )
        return [t.dict() for t in templates]
    except Exception as e:
        logger.error(f"获取 Agent 模板列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent-templates", response_model=Dict[str, Any])
async def create_agent_template(request: AgentTemplateCreate):
    """
    创建 Agent 模板

    Args:
        request: 创建请求

    Returns:
        Dict: 创建结果
    """
    service = get_agent_template_service()

    try:
        template = await service.create_template(request)
        return {
            "success": True,
            "message": "Agent 模板创建成功",
            "template": template.dict(),
        }
    except Exception as e:
        logger.error(f"创建 Agent 模板失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent-templates/{template_id}", response_model=Dict[str, Any])
async def get_agent_template(template_id: str):
    """
    获取 Agent 模板详情

    Args:
        template_id: 模板 ID

    Returns:
        Dict: Agent 模板详情
    """
    service = get_agent_template_service()

    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Agent 模板不存在")

    return template.dict()


@router.put("/agent-templates/{template_id}", response_model=Dict[str, Any])
async def update_agent_template(template_id: str, request: AgentTemplateUpdate):
    """
    更新 Agent 模板

    Args:
        template_id: 模板 ID
        request: 更新请求

    Returns:
        Dict: 更新结果
    """
    service = get_agent_template_service()

    template = await service.update_template(template_id, request)
    if not template:
        raise HTTPException(
            status_code=404,
            detail="Agent 模板不存在或系统内置模板不可修改"
        )

    return {
        "success": True,
        "message": f"Agent 模板 {template_id} 更新成功",
        "template": template.dict(),
    }


@router.delete("/agent-templates/{template_id}", response_model=Dict[str, Any])
async def delete_agent_template(template_id: str):
    """
    删除 Agent 模板

    Args:
        template_id: 模板 ID

    Returns:
        Dict: 删除结果
    """
    service = get_agent_template_service()

    success = await service.delete_template(template_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Agent 模板不存在或系统内置模板不可删除"
        )

    return {
        "success": True,
        "message": f"Agent 模板 {template_id} 删除成功",
    }


@router.post("/agent-templates/{template_id}/preview", response_model=Dict[str, Any])
async def preview_agent_template(
    template_id: str,
    project_id: Optional[str] = Query(default=None, description="项目ID，用于加载写作规则"),
    variables: Optional[Dict[str, Any]] = None,
):
    """
    预览 Agent 模板渲染结果

    Args:
        template_id: 模板 ID
        project_id: 项目 ID（用于动态加载写作规则）
        variables: 变量值 (请求体)

    Returns:
        Dict: 预览结果
    """
    service = get_agent_template_service()
    prompt_service = get_prompt_service()

    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Agent 模板不存在")

    # 构建渲染结果
    rendered_prompts = []
    prompt_order = template.default_prompt_order

    for slot_name in prompt_order:
        # 查找插槽
        slot = None
        for s in template.prompt_slots:
            if s.slot_name == slot_name:
                slot = s
                break

        if not slot or not slot.is_enabled:
            continue

        prompt_content = ""

        # 特殊处理：writing_rules 插槽（动态加载）
        if slot_name == "writing_rules" and not slot.prompt_template_id:
            prompt_content = await _build_writing_rules_prompt(project_id)
            rendered_prompts.append({
                "slot_name": slot_name,
                "description": slot.description,
                "content": prompt_content,
            })
            continue

        # 普通 Prompt 模板
        if slot.prompt_template_id:
            prompt_template = await prompt_service.get_template(slot.prompt_template_id)
            if prompt_template:
                # 渲染变量
                merged_vars = slot.variable_overrides.copy()
                if variables:
                    merged_vars.update(variables)
                request = PromptRenderRequest(
                    template_id=slot.prompt_template_id,
                    variables=merged_vars,
                )
                try:
                    result = await prompt_service.render_template(request)
                    prompt_content = result.rendered_content
                except Exception as e:
                    logger.warning(f"Failed to render prompt {slot.prompt_template_id}: {e}")
                    prompt_content = prompt_template.content

        rendered_prompts.append({
            "slot_name": slot_name,
            "description": slot.description,
            "content": prompt_content,
        })

    return {
        "template_id": template_id,
        "template_name": template.name,
        "project_id": project_id,
        "rendered_prompts": rendered_prompts,
        "final_prompt": "\n\n".join([p["content"] for p in rendered_prompts if p["content"]]),
    }


async def _build_writing_rules_prompt(project_id: Optional[str]) -> str:
    """
    构建写作规则提示词

    Args:
        project_id: 项目 ID

    Returns:
        str: 写作规则提示词
    """
    from app.services.writing_rules_init import build_writing_prompt, get_system_rule_by_id, get_system_rule_set_by_id

    if not project_id:
        # 没有项目 ID，使用默认规则集
        return build_writing_prompt(rule_set_ids=["rule_set_web_novel_basics"])

    # 从数据库获取项目写作配置
    try:
        from app.api.routes.writing_rules import _get_db
        db = _get_db()
        if db:
            config = await db.fetchone(
                """
                SELECT enabled_rule_ids, enabled_rule_set_ids
                FROM project_writing_configs
                WHERE project_id = $1
                """,
                project_id
            )
            if config:
                enabled_rule_ids = config.get("enabled_rule_ids", []) or []
                enabled_rule_set_ids = config.get("enabled_rule_set_ids", []) or []

                if enabled_rule_ids or enabled_rule_set_ids:
                    return build_writing_prompt(
                        rule_ids=enabled_rule_ids,
                        rule_set_ids=enabled_rule_set_ids,
                    )
    except Exception as e:
        logger.warning(f"Failed to load project writing config: {e}")

    # 默认使用基础规则集
    return build_writing_prompt(rule_set_ids=["rule_set_web_novel_basics"])


@router.get("/agent-templates/by-type/{agent_type}", response_model=Dict[str, Any])
async def get_agent_template_by_type(agent_type: str):
    """
    按类型获取 Agent 模板（返回第一个匹配的系统模板）

    Args:
        agent_type: Agent 类型

    Returns:
        Dict: Agent 模板详情
    """
    service = get_agent_template_service()

    try:
        agent_type_enum = AgentType(agent_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的 Agent 类型: {agent_type}")

    template = await service.get_template_by_type(agent_type_enum)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"类型为 {agent_type} 的系统模板不存在"
        )

    return template.dict()


@router.post("/agent-templates/{template_id}/toggle", response_model=Dict[str, Any])
async def toggle_agent_template(template_id: str, enabled: bool = Query(..., description="是否启用")):
    """
    切换可选 Agent 模板的启用状态

    Args:
        template_id: 模板 ID
        enabled: 是否启用

    Returns:
        Dict: 操作结果
    """
    service = get_agent_template_service()

    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Agent 模板不存在")

    # 检查是否为可选 Agent
    if not template.is_optional:
        raise HTTPException(
            status_code=400,
            detail="核心 Agent 无法关闭"
        )

    # 更新启用状态
    template.is_enabled = enabled
    template.updated_at = datetime.now()

    return {
        "success": True,
        "message": f"Agent '{template.name}' 已{'启用' if enabled else '禁用'}",
        "template": template.dict(),
    }


@router.get("/agent-templates/core/list", response_model=List[str])
async def get_core_agent_types():
    """
    获取核心 Agent 类型列表（不可关闭）

    Returns:
        List: 核心 Agent 类型列表
    """
    return [t.value for t in AgentType.core_agents()]


@router.get("/agent-templates/optional/list", response_model=List[str])
async def get_optional_agent_types():
    """
    获取可选 Agent 类型列表（可按需启用）

    Returns:
        List: 可选 Agent 类型列表
    """
    return [t.value for t in AgentType.optional_agents()]