"""
Agent 配置管理 API 路由
v7 核心需求：项目级别的 Agent 配置管理
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.agent_config import (
    AgentConfig,
    AgentConfigCreate,
    AgentConfigUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 模拟服务实例
_agent_config_service = None


def get_agent_config_service():
    """获取 Agent 配置服务实例"""
    global _agent_config_service
    if _agent_config_service is None:
        from app.services.agent_config_service import AgentConfigService
        from app.services.agent_template_service import AgentTemplateService
        template_service = AgentTemplateService()
        _agent_config_service = AgentConfigService(agent_template_service=template_service)
    return _agent_config_service


# ==================== Agent 配置 API ====================

@router.get("/projects/{project_id}/agents", response_model=List[Dict[str, Any]])
async def list_agent_configs(
    project_id: str,
    agent_type: Optional[str] = Query(default=None, description="按 Agent 类型过滤"),
    is_active: Optional[bool] = Query(default=None, description="按激活状态过滤"),
    limit: int = Query(default=50, le=100, description="返回数量限制"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
):
    """
    获取项目的所有 Agent 配置

    Args:
        project_id: 项目 ID
        agent_type: Agent 类型过滤
        is_active: 激活状态过滤
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        List: Agent 配置列表
    """
    service = get_agent_config_service()

    try:
        configs = await service.get_all_configs(
            project_id=project_id,
            agent_type=agent_type,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
        return [c.dict() for c in configs]
    except Exception as e:
        logger.error(f"获取项目 {project_id} 的 Agent 配置列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/agents", response_model=Dict[str, Any])
async def create_agent_config(
    project_id: str,
    request: AgentConfigCreate,
):
    """
    创建项目的 Agent 配置

    Args:
        project_id: 项目 ID
        request: 创建请求

    Returns:
        Dict: 创建结果
    """
    # 确保项目 ID 一致
    if request.project_id != project_id:
        raise HTTPException(status_code=400, detail="请求中的项目 ID 与路径参数不匹配")

    service = get_agent_config_service()

    try:
        # 使用 get_or_create_config 创建配置
        config = await service.get_or_create_config(
            project_id=request.project_id,
            agent_type=request.agent_type,
            template_id=request.template_id,
        )

        # 更新其他字段
        update_data = request.dict(exclude={"project_id", "agent_type", "template_id"})
        for field, value in update_data.items():
            if value is not None:
                setattr(config, field, value)

        return {
            "success": True,
            "message": "Agent 配置创建成功",
            "config": config.dict(),
        }
    except Exception as e:
        logger.error(f"创建 Agent 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/agents/{agent_type}", response_model=Dict[str, Any])
async def get_agent_config(
    project_id: str,
    agent_type: str,
):
    """
    获取项目特定 Agent 类型的配置

    Args:
        project_id: 项目 ID
        agent_type: Agent 类型

    Returns:
        Dict: Agent 配置详情
    """
    service = get_agent_config_service()

    try:
        config = await service.get_config_by_project_agent(project_id, agent_type)
        if not config:
            # 如果不存在，创建默认配置
            config = await service.get_or_create_config(
                project_id=project_id,
                agent_type=agent_type,
            )

        return config.dict()
    except Exception as e:
        logger.error(f"获取项目 {project_id} 的 {agent_type} 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/agents/{agent_type}", response_model=Dict[str, Any])
async def update_agent_config(
    project_id: str,
    agent_type: str,
    request: AgentConfigUpdate,
):
    """
    更新项目特定 Agent 类型的配置

    Args:
        project_id: 项目 ID
        agent_type: Agent 类型
        request: 更新请求

    Returns:
        Dict: 更新结果
    """
    service = get_agent_config_service()

    # 先获取配置
    config = await service.get_config_by_project_agent(project_id, agent_type)
    if not config:
        # 如果不存在，创建默认配置
        config = await service.get_or_create_config(
            project_id=project_id,
            agent_type=agent_type,
        )

    try:
        # 更新配置
        updated_config = await service.update_config(config.id, request)
        if not updated_config:
            raise HTTPException(status_code=404, detail="配置更新失败")

        return {
            "success": True,
            "message": f"Agent 配置 {config.id} 更新成功",
            "config": updated_config.dict(),
        }
    except Exception as e:
        logger.error(f"更新 Agent 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/agents/{agent_type}/preview", response_model=Dict[str, Any])
async def preview_agent_config(
    project_id: str,
    agent_type: str,
    variables: Optional[Dict[str, Any]] = None,
):
    """
    预览最终 prompt

    Args:
        project_id: 项目 ID
        agent_type: Agent 类型
        variables: 变量值 (请求体)

    Returns:
        Dict: 预览结果
    """
    service = get_agent_config_service()

    # 获取配置
    config = await service.get_config_by_project_agent(project_id, agent_type)
    if not config:
        # 如果不存在，创建默认配置
        config = await service.get_or_create_config(
            project_id=project_id,
            agent_type=agent_type,
        )

    try:
        result = await service.preview_prompt(config.id, variables)
        return result
    except Exception as e:
        logger.error(f"预览 Agent 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/agents/reset", response_model=Dict[str, Any])
async def reset_agent_configs(
    project_id: str,
    agent_type: Optional[str] = Query(default=None, description="要重置的 Agent 类型，为空则重置所有"),
):
    """
    重置为模板默认

    Args:
        project_id: 项目 ID
        agent_type: 要重置的 Agent 类型

    Returns:
        Dict: 重置结果
    """
    service = get_agent_config_service()

    try:
        # 获取要重置的配置
        configs = await service.get_all_configs(project_id=project_id, agent_type=agent_type)

        if not configs:
            raise HTTPException(status_code=404, detail="未找到符合条件的配置")

        reset_results = []
        for config in configs:
            try:
                reset_config = await service.reset_config(config.id)
                if reset_config:
                    reset_results.append({
                        "config_id": config.id,
                        "agent_type": config.agent_type,
                        "success": True,
                        "message": f"配置 {config.id} 重置成功",
                    })
                else:
                    reset_results.append({
                        "config_id": config.id,
                        "agent_type": config.agent_type,
                        "success": False,
                        "message": f"配置 {config.id} 重置失败（可能没有关联模板）",
                    })
            except Exception as e:
                reset_results.append({
                    "config_id": config.id,
                    "agent_type": config.agent_type,
                    "success": False,
                    "message": str(e),
                })

        success_count = sum(1 for r in reset_results if r["success"])

        return {
            "success": success_count > 0,
            "message": f"重置完成，成功 {success_count}/{len(reset_results)} 个配置",
            "results": reset_results,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置 Agent 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))