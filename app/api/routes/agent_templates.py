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
from app.services.agent_prompt_service import get_agent_prompt_service
from app.services.agent_config_service import get_agent_config_service

logger = logging.getLogger(__name__)

router = APIRouter()

# 模拟服务实例
_agent_template_service = None


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


# ==================== Agent Template CRUD API ====================

@router.get("/agent-templates", response_model=List[Dict[str, Any]])
async def list_agent_templates(
    agent_type: Optional[str] = Query(default=None, description="按 Agent 类型过滤"),
    scenario: Optional[str] = Query(default=None, description="按 Agent 使用场景过滤"),
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
            scenario=scenario,
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

    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Agent 模板不存在")

    logger.info(f"预览 Agent 模板: {template_id}, skill_slots 数量: {len(template.skill_slots)}")

    agent_type_value = template.agent_type.value if hasattr(template.agent_type, "value") else str(template.agent_type)
    preview_variables = dict(variables or {})
    preview_variables.setdefault("scenario", template.scenario)
    preview_project_id = project_id

    agent_prompt_service = get_agent_prompt_service()

    prompt_data = await agent_prompt_service.build_agent_prompt_with_trace(
        agent_type=agent_type_value,
        project_id=preview_project_id,
        variables=preview_variables,
        include_skills=True,
        context_scene=template.scenario,
        scenario=template.scenario,
        use_intelligent_retrieval=False,
        use_project_config=False,
        resolved_template=template,
    )

    final_prompt = prompt_data.get("content", "")
    render_trace = prompt_data.get("trace", {})
    render_trace["config_id"] = render_trace.get("config_id") or f"preview_{preview_project_id}_{agent_type_value}_{template.scenario}_{template.id}"
    render_trace["template_id"] = template.id
    render_trace["template_scenario"] = template.scenario

    rendered_prompts = []
    if final_prompt:
        rendered_prompts.append({
            "slot_name": "final_prompt",
            "description": "Agent Template preview rendered by unified runtime builder",
            "content": final_prompt,
        })

    return {
        "template_id": template_id,
        "template_name": template.name,
        "project_id": project_id,
        "rendered_prompts": rendered_prompts,
        "final_prompt": final_prompt,
        "render_trace": render_trace,
    }


async def _build_available_skills_content(template: AgentTemplate) -> str:
    """
    构建可用 Skills 列表

    从模板的 skill_slots 加载 Skills 并构建简洁的列表，
    让 Agent 知道自己有哪些技能可用，而不是注入完整内容。

    Agent 在执行时会根据需要自主调用这些 skills。

    Args:
        template: Agent 模板

    Returns:
        str: Skills 列表（名称 + 用途说明）
    """
    if not template.skill_slots:
        logger.debug(f"模板 {template.id} 没有配置 skill_slots")
        return ""

    try:
        from app.services.skill_service import get_skill_service
        skill_service = get_skill_service()

        skill_items = []
        for slot in template.skill_slots:
            logger.debug(f"处理 skill_slot: {slot.slot_name}, skill_id={slot.skill_id}, is_enabled={slot.is_enabled}")

            if not slot.is_enabled or not slot.skill_id:
                logger.debug(f"跳过插槽 {slot.slot_name}: is_enabled={slot.is_enabled}, skill_id={slot.skill_id}")
                continue

            skill = await skill_service.get_skill(slot.skill_id)
            if not skill:
                logger.warning(f"未找到 Skill: {slot.skill_id}")
                continue

            if not skill.is_enabled:
                logger.debug(f"Skill {slot.skill_id} 已禁用")
                continue

            # 只收集名称和描述，不注入完整内容
            skill_items.append({
                "name": skill.name,
                "id": skill.id,
                "description": skill.description,
                "skill_type": skill.skill_type.value,
                "load_mode": skill.load_mode.value,
            })
            logger.debug(f"Skill {slot.skill_id}: 已添加到可用列表")

        if skill_items:
            # 构建简洁的技能列表（不包含标题，标题在prompt模板中已定义）
            lines = ["\n你可以使用以下技能来完成任务：\n"]

            for i, item in enumerate(skill_items, 1):
                skill_type_label = {
                    "knowledge": "知识",
                    "prompt": "提示词",
                    "function": "函数",
                    "workflow": "工作流",
                }.get(item["skill_type"], item["skill_type"])

                load_mode_label = "核心" if item["load_mode"] == "core" else "按需"

                lines.append(
                    f"{i}. **{item['name']}** (`{item['id']}`) [{skill_type_label}/{load_mode_label}]"
                )
                if item["description"]:
                    lines.append(f"   - {item['description']}")

            lines.append("\n**使用方式**：根据任务需要，调用对应的 skill 来辅助完成工作。")

            result = "\n".join(lines)
            logger.info(f"为模板 {template.id} 构建了 {len(skill_items)} 个 Skills 列表")
            return result
        else:
            logger.warning(f"模板 {template.id} 没有找到任何有效的 Skills")

    except Exception as e:
        logger.warning(f"Failed to build available_skills content: {e}")

    return ""


@router.get("/agent-templates/by-type/{agent_type}", response_model=Dict[str, Any])
async def get_agent_template_by_type(
    agent_type: str,
    scenario: Optional[str] = Query(default=None, description="Agent 使用场景"),
):
    """
    按类型获取 Agent 模板（返回匹配 agent_type + scenario 的可用模板，数据库配置优先）

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

    template = await service.get_template_by_type(agent_type_enum, scenario)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"类型为 {agent_type} 的系统模板不存在"
        )

    return template.dict()


@router.post("/agent-templates/{template_id}/toggle", response_model=Dict[str, Any])
async def toggle_agent_template(
    template_id: str,
    enabled: bool = Query(..., description="是否启用"),
    project_id: Optional[str] = Query(default=None, description="项目 ID，不传则修改全局模板默认值"),
):
    """
    切换 Agent 模板的启用状态。

    - 传 project_id：写入项目级 AgentConfig.is_active，影响该项目 runtime。
    - 不传 project_id：修改全局模板默认启用状态，影响未覆盖的默认行为。
    """
    service = get_agent_template_service()

    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Agent 模板不存在")

    if not template.is_optional:
        raise HTTPException(
            status_code=400,
            detail="核心 Agent 无法关闭"
        )

    if project_id:
        config_service = get_agent_config_service()
        config = await config_service.get_config_by_project_agent(
            project_id,
            template.agent_type.value,
            template.scenario,
        )
        if not config:
            config = await config_service.get_or_create_config(
                project_id=project_id,
                agent_type=template.agent_type.value,
                template_id=template.id,
                scenario=template.scenario,
            )

        from app.models.agent_config import AgentConfigUpdate

        updated_config = await config_service.update_config(
            config.id,
            AgentConfigUpdate(is_active=enabled),
        )
        if not updated_config:
            raise HTTPException(status_code=500, detail="项目级 Agent 配置更新失败")

        refreshed_template = await service.get_template(template_id)
        return {
            "success": True,
            "message": f"项目 Agent '{template.name}' 已{'启用' if enabled else '禁用'}",
            "template": refreshed_template.dict() if refreshed_template else template.dict(),
            "project_config": updated_config.dict(),
        }

    template.is_enabled = enabled
    template.updated_at = datetime.now()

    if service._db:
        try:
            await service._db.execute_write(
                """
                UPDATE agent_templates
                SET is_enabled = :is_enabled, updated_at = :updated_at
                WHERE id = :id
                """,
                {
                    "id": template.id,
                    "is_enabled": enabled,
                    "updated_at": template.updated_at,
                },
            )
            service.invalidate_cache()
            template = await service.get_template(template_id) or template
        except Exception as e:
            logger.error(f"更新 Agent 模板启用状态失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

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
        AgentType.HOOK_MANAGER: "伏笔 Agent",
        AgentType.WRITER: "作家 Agent",
        AgentType.EVALUATOR: "评估 Agent",
        AgentType.PROC_GEN: "过程生成 Agent",
        AgentType.SCENE_COORDINATOR: "场景协调 Agent",
        AgentType.PLOT_OUTLINE: "章节大纲 Agent",
        AgentType.EVENT_GENERATOR: "事件 Agent",
        AgentType.DUNGEON_GENERATOR: "副本生成 Agent",
        AgentType.WORLD_MAP_MANAGER: "地图 Agent",
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
        AgentType.PLOT_OUTLINE: "规划当前章节目标、标题与分场大纲",
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
        AgentType.PLOT_OUTLINE: "BookOpen",
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
    1. Agent 节点 - 系统 Agent（根据模板启用状态过滤）
    2. 交互节点 - 场景演绎、集体讨论
    3. 控制节点 - 开始、结束、条件、并行等

    Args:
        project_id: 项目 ID，如果提供则返回该项目的角色 Agent

    Returns:
        Dict: 按类别分组的节点类型
    """
    from app.api.app import postgres_db
    from app.services.workflow_node_catalog import (
        resolve_disabled_agent_types,
        resolve_workflow_node_types_payload,
    )

    disabled_agent_types = await resolve_disabled_agent_types(project_id, postgres_db)
    if disabled_agent_types:
        logger.info(f"已禁用的 Agent 类型: {disabled_agent_types}")

    result = await resolve_workflow_node_types_payload(project_id, postgres_db, disabled_agent_types)
    logger.info(f"返回 {len(result['agent_nodes'])} 个 Agent 节点")
    return result
