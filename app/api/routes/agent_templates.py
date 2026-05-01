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
from app.services.agent_prompt_service import get_agent_prompt_service
from app.services.agent_config_service import get_agent_config_service

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
    prompt_service = get_prompt_service()

    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Agent 模板不存在")

    logger.info(f"预览 Agent 模板: {template_id}, skill_slots 数量: {len(template.skill_slots)}")

    agent_type_value = template.agent_type.value if hasattr(template.agent_type, "value") else str(template.agent_type)
    preview_variables = dict(variables or {})
    preview_variables.setdefault("scenario", template.scenario)

    agent_prompt_service = get_agent_prompt_service()
    skills_data = await agent_prompt_service.build_skills_prompt_with_trace(
        agent_type_value,
        project_id=project_id,
        variables=preview_variables,
        context_scene=template.scenario,
        scenario=template.scenario,
        use_intelligent_retrieval=False,
    )
    skills_content = skills_data.get("content", "")
    skills_trace = skills_data.get("trace", {})
    logger.info(f"resolved skills prompt 内容长度: {len(skills_content)} 字符")

    # 构建渲染结果
    rendered_prompts = []
    if skills_content:
        rendered_prompts.append({
            "slot_name": "skills",
            "description": "Skills（按 Agent Template / Skill Assignments 解析）",
            "content": skills_content,
        })
    render_trace: Dict[str, Any] = {
        "agent_type": agent_type_value,
        "scenario": template.scenario,
        "template_id": template.id,
        "prompt_ids": [],
        "skill_ids": skills_trace.get("skill_ids", []),
        "skills": skills_trace,
        "writing_rule_ids": [],
        "context_blocks": [],
        "fallbacks_used": list(skills_trace.get("fallbacks_used", [])),
        "deprecated_sources_used": list(skills_trace.get("deprecated_sources_used", [])),
        "writing_rules": None,
    }
    prompt_order = template.default_prompt_order or []
    prompt_slots_by_name = {slot.slot_name: slot for slot in template.prompt_slots}
    ordered_slots = []
    used_slot_names = set()
    for slot_name in prompt_order:
        slot = prompt_slots_by_name.get(slot_name)
        if slot and slot.is_enabled:
            ordered_slots.append((slot_name, slot))
            used_slot_names.add(slot_name)

    remaining_slots = [
        (slot.slot_name, slot)
        for slot in template.prompt_slots
        if slot.is_enabled and slot.slot_name not in used_slot_names
    ]
    remaining_slots.sort(key=lambda item: -item[1].priority)
    ordered_slots.extend(remaining_slots)

    for slot_name, slot in ordered_slots:
        prompt_content = ""

        # 特殊处理：writing_rules 插槽（动态加载）。复用 runtime 的 AgentPromptService，
        # 避免 /agent-templates preview 与实际运行时规则注入逻辑分叉。
        if slot_name == "writing_rules" and not slot.prompt_template_id:
            writing_rules_data = await agent_prompt_service.build_writing_rules_prompt_with_trace(
                project_id,
                preview_variables,
                agent_type=agent_type_value,
                scenario=template.scenario,
            )
            prompt_content = writing_rules_data.get("content", "")
            writing_rules_trace = writing_rules_data.get("trace", {})
            render_trace["writing_rules"] = writing_rules_trace
            render_trace["writing_rule_ids"] = writing_rules_trace.get("writing_rule_ids", [])
            render_trace["fallbacks_used"].extend(writing_rules_trace.get("fallbacks_used", []))
            render_trace["deprecated_sources_used"].extend(writing_rules_trace.get("deprecated_sources_used", []))
            # 替换 available_skills 占位符
            prompt_content = _inject_skills(prompt_content, skills_content)
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
                if preview_variables:
                    merged_vars.update(preview_variables)
                request = PromptRenderRequest(
                    template_id=slot.prompt_template_id,
                    variables=merged_vars,
                )
                try:
                    result = await prompt_service.render_template(request)
                    prompt_content = result.rendered_content
                    render_trace["prompt_ids"].append(slot.prompt_template_id)
                except Exception as e:
                    logger.warning(f"Failed to render prompt {slot.prompt_template_id}: {e}")
                    prompt_content = prompt_template.content
                    render_trace["prompt_ids"].append(slot.prompt_template_id)
                    render_trace["fallbacks_used"].append(f"prompt_template_raw:{slot.prompt_template_id}")

        # 替换 available_skills 占位符
        prompt_content = _inject_skills(prompt_content, skills_content)

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
        "render_trace": render_trace,
    }


def _inject_skills(content: str, skills_content: str) -> str:
    """
    将 available_skills 内容注入到 prompt 中

    Args:
        content: Prompt 内容
        skills_content: Skills 内容

    Returns:
        str: 注入后的内容
    """
    if "{{available_skills}}" in content:
        logger.debug(f"发现 {{available_skills}} 占位符，注入 {len(skills_content)} 字符内容")
        return content.replace("{{available_skills}}", skills_content)
    return content


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
