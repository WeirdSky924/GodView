"""
Agent 模板管理 API 路由
v7 核心需求：Agent 模板的 CRUD 操作、Prompt 插槽管理、预览渲染
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.agent_template import (
    AgentType,
    AgentTemplate,
    AgentTemplateCreate,
    AgentTemplateUpdate,
)

logger = logging.getLogger(__name__)

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


def get_prompt_service():
    """获取 Prompt 服务实例"""
    global _prompt_service
    if _prompt_service is None:
        from app.services.prompt_template_service import PromptTemplateService
        _prompt_service = PromptTemplateService()
    return _prompt_service


# ==================== Agent Template CRUD API ====================

@router.get("/agent-templates", response_model=List[Dict[str, Any]])
async def list_agent_templates(
    agent_type: Optional[str] = Query(default=None, description="按 Agent 类型过滤"),
    is_system: Optional[bool] = Query(default=None, description="是否系统内置"),
    tags: Optional[List[str]] = Query(default=None, description="按标签过滤"),
    limit: int = Query(default=50, le=100, description="返回数量限制"),
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

    agent_type_enum = AgentType(agent_type) if agent_type else None

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
    variables: Optional[Dict[str, Any]] = None,
):
    """
    预览 Agent 模板渲染结果

    Args:
        template_id: 模板 ID
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

        # 获取关联的 PromptTemplate
        prompt_content = ""
        if slot.prompt_template_id:
            prompt_template = await prompt_service.get_template(slot.prompt_template_id)
            if prompt_template:
                # 渲染变量
                merged_vars = slot.variable_overrides.copy()
                merged_vars.update(variables)
                request = PromptRenderRequest(
                    template_id=slot.prompt_template_id,
                    variables=merged_vars,
                )
                try:
                    result = await prompt_service.render_template(request)
                    prompt_content = result.rendered_content
                except:
                    prompt_content = prompt_template.content

        rendered_prompts.append({
            "slot_name": slot_name,
            "description": slot.description,
            "content": prompt_content,
        })

    return {
        "template_id": template_id,
        "template_name": template.name,
        "rendered_prompts": rendered_prompts,
        "final_prompt": "\n\n".join([p["content"] for p in rendered_prompts]),
    }


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