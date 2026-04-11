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

    template, error = await service.update_template(template_id, request)
    if error == 'not_found':
        raise HTTPException(status_code=404, detail="Agent 模板不存在")
    if error == 'is_system':
        raise HTTPException(status_code=403, detail="系统内置模板不可修改")

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

    success, error = await service.delete_template(template_id)
    if error == 'not_found':
        raise HTTPException(status_code=404, detail="Agent 模板不存在")
    if error == 'is_system':
        raise HTTPException(status_code=403, detail="系统内置模板不可删除")

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


@router.get("/agent-templates/types/metadata", response_model=List[Dict[str, Any]])
async def get_agent_types_metadata():
    """
    获取所有 Agent 类型的元数据（用于动态生成 UI）

    Returns:
        List: Agent 类型元数据列表，包含类型、标签、是否核心等信息
    """
    core_types = [t.value for t in AgentType.core_agents()]
    optional_types = [t.value for t in AgentType.optional_agents()]

    # Agent 类型的中文标签
    type_labels = {
        AgentType.CHARACTER: "角色 Agent",
        AgentType.SETTING: "设定 Agent",
        AgentType.SUMMARIZER: "摘要 Agent",
        AgentType.MASTER_PLOTTER: "总编剧 Agent",
        AgentType.HOOK_MANAGER: "伏笔管理 Agent",
        AgentType.WRITER: "作家 Agent",
        AgentType.EVALUATOR: "评估 Agent",
        AgentType.PROC_GEN: "过程生成 Agent",
        AgentType.SCENE_COORDINATOR: "场景协调 Agent",
        AgentType.EVENT_GENERATOR: "事件生成 Agent",
        AgentType.DUNGEON_GENERATOR: "副本生成 Agent",
        AgentType.WORLD_MAP_MANAGER: "世界地图 Agent",
    }

    # Agent 类型的描述
    type_descriptions = {
        AgentType.CHARACTER: "扮演小说中的角色，进行对话和互动",
        AgentType.SETTING: "管理和维护世界观设定",
        AgentType.SUMMARIZER: "生成内容摘要和关键信息提取",
        AgentType.MASTER_PLOTTER: "规划剧情大纲和章节结构",
        AgentType.HOOK_MANAGER: "管理伏笔的埋设和回收",
        AgentType.WRITER: "执行章节内容写作",
        AgentType.EVALUATOR: "评估内容质量和一致性",
        AgentType.PROC_GEN: "过程化内容生成（随机事件等）",
        AgentType.SCENE_COORDINATOR: "统筹多角色演绎场景，协调信息分配",
        AgentType.EVENT_GENERATOR: "生成故事事件、转折和随机变数",
        AgentType.DUNGEON_GENERATOR: "生成故事副本、挑战和任务",
        AgentType.WORLD_MAP_MANAGER: "管理世界地图、地点和空间关系",
    }

    # Agent 类型的图标建议
    type_icons = {
        AgentType.CHARACTER: "User",
        AgentType.SETTING: "Settings",
        AgentType.SUMMARIZER: "FileText",
        AgentType.MASTER_PLOTTER: "GitBranch",
        AgentType.HOOK_MANAGER: "Link",
        AgentType.WRITER: "PenTool",
        AgentType.EVALUATOR: "CheckCircle",
        AgentType.PROC_GEN: "Shuffle",
        AgentType.SCENE_COORDINATOR: "Users",
        AgentType.EVENT_GENERATOR: "Zap",
        AgentType.DUNGEON_GENERATOR: "Map",
        AgentType.WORLD_MAP_MANAGER: "Globe",
    }

    result = []
    for agent_type in AgentType:
        type_value = agent_type.value
        result.append({
            "type": type_value,
            "label": type_labels.get(agent_type, type_value),
            "description": type_descriptions.get(agent_type, ""),
            "icon": type_icons.get(agent_type, "Bot"),
            "is_core": type_value in core_types,
            "is_optional": type_value in optional_types,
        })

    return result


@router.get("/workflow/node-types", response_model=Dict[str, Any])
async def get_workflow_node_types(project_id: Optional[str] = Query(default=None, description="项目ID，用于获取项目角色")):
    """
    获取工作流节点类型（用于可视化工作台）

    返回三类节点：
    1. Agent 节点 - 系统 Agent
    2. 交互节点 - 场景演绎、集体讨论
    3. 控制节点 - 开始、结束、条件、并行等

    Args:
        project_id: 项目 ID，如果提供则返回该项目的角色 Agent

    Returns:
        Dict: 按类别分组的节点类型
    """
    from app.models.node_types import (
        NodeCategory,
        SYSTEM_AGENT_NODES,
        INTERACTION_NODES,
        CONTROL_NODES,
        NodeTypeInfo,
    )

    def serialize_node(node: NodeTypeInfo) -> Dict[str, Any]:
        """序列化节点，确保枚举转换为字符串"""
        data = node.dict()
        data["category"] = node.category.value  # 枚举转字符串
        return data

    result = {
        "agent_nodes": [],
        "interaction_nodes": [],
        "control_nodes": [],
        "character_nodes": [],  # 项目角色 Agent
    }

    # 系统 Agent 节点
    for node in SYSTEM_AGENT_NODES:
        result["agent_nodes"].append(serialize_node(node))

    # 交互节点
    for node in INTERACTION_NODES:
        result["interaction_nodes"].append(serialize_node(node))

    # 控制节点
    for node in CONTROL_NODES:
        result["control_nodes"].append(serialize_node(node))

    # 如果有项目 ID，获取项目角色
    if project_id:
        try:
            from app.database.postgres import PostgresDatabase
            db = PostgresDatabase()
            characters = await db.fetchall(
                """
                SELECT id, name, role, importance_tier, has_agent, agent_enabled
                FROM characters
                WHERE project_id = $1 AND has_agent = true
                ORDER BY importance_tier, name
                """,
                project_id
            )
            for char in characters or []:
                result["character_nodes"].append({
                    "type": "agent",
                    "agent_type": f"character:{char['id']}",
                    "label": f"{char['name']} (角色)",
                    "description": f"角色 Agent - {char['role']}",
                    "category": "agent",
                    "icon": "User",
                    "color": "orange",
                    "is_system": False,
                    "character_id": char["id"],
                    "character_name": char["name"],
                    "importance_tier": char["importance_tier"],
                })
        except Exception as e:
            logger.warning(f"Failed to load characters for project {project_id}: {e}")

    return result