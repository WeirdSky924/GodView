"""
工作流 API 路由
v8 Agent协作可视化工作台
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.workflow_definition import (
    WorkflowDefinition,
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowValidationResult,
)
from app.models.workflow_execution import (
    WorkflowExecution,
    WorkflowExecutionCreate,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 服务实例（由 app.py 初始化时设置）
_workflow_engine = None


def get_workflow_engine():
    """获取工作流引擎"""
    global _workflow_engine
    if _workflow_engine is None:
        from app.services.workflow_engine import get_workflow_engine
        _workflow_engine = get_workflow_engine()
    return _workflow_engine


def get_db():
    """获取数据库连接"""
    from app.api.app import postgres_db
    return postgres_db


def set_workflow_engine(engine):
    """设置工作流引擎实例"""
    global _workflow_engine
    _workflow_engine = engine


# ==================== 节点类型 API ====================

from fastapi import Response

@router.get("/node-types", response_model=Dict[str, Any])
async def get_node_types(
    project_id: Optional[str] = Query(None, description="项目ID（用于获取角色Agent）"),
):
    """
    获取工作流节点类型列表

    返回所有可用的节点类型，包括：
    - 系统 Agent 节点（根据模板启用状态过滤）
    - 角色 Agent 节点（如果提供了 project_id）
    - 交互节点
    - 控制节点
    """
    from app.models.agent_template import AgentType
    from app.services.agent_template_service import AgentTemplateService

    # 所有系统 Agent 节点定义
    all_agent_nodes = [
        {
            "type": "agent",
            "agent_type": AgentType.SETTING.value,
            "label": "设定 Agent",
            "description": "管理世界观、设定条目",
            "category": "agent",
            "icon": "Settings",
            "color": "blue",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.WRITER.value,
            "label": "作家 Agent",
            "description": "生成小说内容",
            "category": "agent",
            "icon": "PenTool",
            "color": "purple",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.MASTER_PLOTTER.value,
            "label": "总编剧 Agent",
            "description": "规划整体剧情结构",
            "category": "agent",
            "icon": "GitBranch",
            "color": "indigo",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.SUMMARIZER.value,
            "label": "摘要 Agent",
            "description": "生成内容摘要",
            "category": "agent",
            "icon": "BookOpen",
            "color": "amber",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.EVALUATOR.value,
            "label": "评估 Agent",
            "description": "评估内容质量",
            "category": "agent",
            "icon": "Search",
            "color": "orange",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.HOOK_MANAGER.value,
            "label": "伏笔 Agent",
            "description": "管理伏笔和悬念",
            "category": "agent",
            "icon": "Link",
            "color": "cyan",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.EVENT_GENERATOR.value,
            "label": "事件 Agent",
            "description": "生成随机事件",
            "category": "agent",
            "icon": "Dices",
            "color": "pink",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.WORLD_MAP_MANAGER.value,
            "label": "地图 Agent",
            "description": "管理世界地图和地点",
            "category": "agent",
            "icon": "Map",
            "color": "teal",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.PROC_GEN.value,
            "label": "过程生成 Agent",
            "description": "过程化生成内容",
            "category": "agent",
            "icon": "Zap",
            "color": "yellow",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.DUNGEON_GENERATOR.value,
            "label": "副本生成 Agent",
            "description": "生成副本和关卡",
            "category": "agent",
            "icon": "Globe",
            "color": "emerald",
            "is_system": True,
        },
        {
            "type": "agent",
            "agent_type": AgentType.PLOT_OUTLINE.value,
            "label": "章节大纲 Agent",
            "description": "规划章节大纲",
            "category": "agent",
            "icon": "BookOpen",
            "color": "rose",
            "is_system": True,
        },
    ]

    # 获取 Agent 模板的启用状态
    # 逻辑：只有当模板存在且 is_enabled=False 时才禁用
    # 如果模板不存在，则默认启用
    disabled_agent_types = set()
    db = get_db()
    if db:
        try:
            template_service = AgentTemplateService(db)
            templates = await template_service.list_templates(limit=100)

            # 只记录被明确禁用的 Agent 类型
            for template in templates:
                if not template.is_enabled:
                    disabled_agent_types.add(template.agent_type.value)

            logger.info(f"已禁用的 Agent 类型: {disabled_agent_types}")
        except Exception as e:
            logger.warning(f"获取 Agent 模板启用状态失败: {e}")

    # 过滤掉被禁用的 Agent 节点
    agent_nodes = [
        node for node in all_agent_nodes
        if node.get("agent_type") not in disabled_agent_types
    ]

    logger.info(f"返回 {len(agent_nodes)} 个 Agent 节点")

    # 角色 Agent 节点（从项目角色生成）
    character_nodes = []
    if project_id:
        if db:
            try:
                characters = await db.execute_query(
                    "SELECT id, name, importance_tier FROM characters WHERE project_id = :project_id ORDER BY importance_tier DESC, name",
                    {"project_id": project_id}
                )
                for char in characters:
                    character_nodes.append({
                        "type": "agent",
                        "agent_type": "character",
                        "label": f"{char['name']} Agent",
                        "description": f"角色 {char['name']} 的专属 Agent",
                        "category": "agent",
                        "icon": "User",
                        "color": "green",
                        "is_system": False,
                        "character_id": str(char["id"]),
                        "character_name": char["name"],
                        "importance_tier": char.get("importance_tier", 1),
                    })
            except Exception as e:
                logger.warning(f"获取项目角色失败: {e}")

    # 交互节点
    interaction_nodes = [
        {
            "type": "input",
            "label": "用户输入",
            "description": "暂停等待用户输入",
            "category": "interaction",
            "icon": "MessageSquare",
            "color": "blue",
            "is_system": True,
            "config_hints": {
                "prompt": {"type": "string", "default": "请输入内容", "description": "提示语"}
            }
        },
        {
            "type": "group_discussion",
            "label": "集体讨论",
            "description": "多个Agent进行创作会议",
            "category": "interaction",
            "icon": "MessageCircle",
            "color": "purple",
            "is_system": True,
            "supports_multiple": True,
        },
        {
            "type": "scene_performance",
            "label": "场景演绎",
            "description": "多角色同台飙戏",
            "category": "interaction",
            "icon": "Users",
            "color": "green",
            "is_system": True,
            "supports_multiple": True,
        },
    ]

    # 控制节点
    control_nodes = [
        {
            "type": "start",
            "label": "开始",
            "description": "工作流起点",
            "category": "control",
            "icon": "Play",
            "color": "green",
            "is_system": True,
        },
        {
            "type": "end",
            "label": "结束",
            "description": "工作流终点",
            "category": "control",
            "icon": "Square",
            "color": "red",
            "is_system": True,
        },
        {
            "type": "condition",
            "label": "条件分支",
            "description": "根据条件选择分支",
            "category": "control",
            "icon": "GitBranch",
            "color": "amber",
            "is_system": True,
            "config_hints": {
                "condition": {"type": "string", "default": "", "description": "条件表达式"}
            }
        },
        {
            "type": "parallel",
            "label": "并行执行",
            "description": "同时执行多个分支",
            "category": "control",
            "icon": "Layers",
            "color": "indigo",
            "is_system": True,
        },
    ]

    # 返回数据（添加版本号便于调试）
    result = {
        "version": "v9.0",
        "agent_nodes": agent_nodes,
        "character_nodes": character_nodes,
        "interaction_nodes": interaction_nodes,
        "control_nodes": control_nodes,
    }

    logger.info(f"返回节点类型: {len(agent_nodes)} 个 Agent 节点")
    return result


# ==================== 工作流定义 API ====================

@router.get("", response_model=List[Dict[str, Any]])
async def list_workflows(
    project_id: str = Query(..., description="项目ID"),
    include_templates: bool = Query(default=False, description="是否包含模板"),
):
    """
    获取工作流列表

    Args:
        project_id: 项目ID
        include_templates: 是否包含预设模板

    Returns:
        List: 工作流定义列表
    """
    engine = get_workflow_engine()
    db = get_db()

    try:
        workflows = await engine.list_workflows(project_id, include_templates, db)
        return [wf.model_dump() for wf in workflows]
    except Exception as e:
        logger.error(f"获取工作流列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Dict[str, Any])
async def create_workflow(request: WorkflowDefinitionCreate):
    """
    创建工作流

    Args:
        request: 创建请求

    Returns:
        Dict: 创建结果
    """
    engine = get_workflow_engine()
    db = get_db()

    # 调试日志：输出接收到的节点类型
    logger.info(f"创建工作流请求: name={request.name}, nodes={len(request.nodes)}")
    for node in request.nodes:
        logger.info(f"  节点: id={node.id}, node_type={node.node_type}, label={node.label}, agent_type={node.agent_type}")

    try:
        workflow = await engine.create_workflow(request, db)
        return {
            "success": True,
            "message": "工作流创建成功",
            "workflow": workflow.model_dump(),
        }
    except Exception as e:
        logger.error(f"创建工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow(workflow_id: str):
    """
    获取工作流详情

    Args:
        workflow_id: 工作流ID

    Returns:
        Dict: 工作流详情
    """
    engine = get_workflow_engine()
    db = get_db()

    workflow = await engine.get_workflow(workflow_id, db)
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    return workflow.model_dump()


@router.put("/{workflow_id}", response_model=Dict[str, Any])
async def update_workflow(workflow_id: str, request: WorkflowDefinitionUpdate):
    """
    更新工作流

    Args:
        workflow_id: 工作流ID
        request: 更新请求

    Returns:
        Dict: 更新结果
    """
    engine = get_workflow_engine()
    db = get_db()

    try:
        workflow = await engine.update_workflow(workflow_id, request, db)
        if not workflow:
            raise HTTPException(status_code=404, detail="工作流不存在")

        return {
            "success": True,
            "message": "工作流更新成功",
            "workflow": workflow.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workflow_id}", response_model=Dict[str, Any])
async def delete_workflow(workflow_id: str):
    """
    删除工作流

    Args:
        workflow_id: 工作流ID

    Returns:
        Dict: 删除结果
    """
    engine = get_workflow_engine()
    db = get_db()

    success = await engine.delete_workflow(workflow_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="工作流不存在")

    return {
        "success": True,
        "message": f"工作流 {workflow_id} 已删除",
    }


@router.post("/{workflow_id}/validate", response_model=WorkflowValidationResult)
async def validate_workflow(workflow_id: str):
    """
    验证工作流有效性

    Args:
        workflow_id: 工作流ID

    Returns:
        WorkflowValidationResult: 验证结果
    """
    engine = get_workflow_engine()
    db = get_db()

    workflow = await engine.get_workflow(workflow_id, db)
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    return engine.validate_workflow(workflow)


# ==================== 工作流执行 API ====================

async def _setup_agent_provider_for_execution(project_id: str):
    """
    为工作流执行设置 Agent provider

    创建 DirectorSystem 实例并设置 Agent provider 回调
    """
    from app.services.workflow_engine import get_workflow_engine
    from app.services.director import DirectorSystem
    from app.config import settings
    from app.api.app import postgres_db

    # 创建 DirectorSystem 实例
    director = DirectorSystem(
        world_data={"id": f"world_workflow_{project_id}", "name": "Workflow World", "regions": [], "relationships": {}},
        config={
            "max_turns_threshold": settings.max_turns_threshold,
            "target_word_count_per_intent": settings.target_word_count_per_intent,
        },
        project_id=project_id,
    )

    # 初始化 DirectorSystem
    from app.services.model_router import create_model_factory
    model_factory = create_model_factory()

    # 加载角色
    characters = []
    if postgres_db:
        try:
            characters = await postgres_db.get_all_characters(project_id)
        except Exception as e:
            logger.warning(f"加载角色失败: {e}")

    await director.initialize(model_factory, characters=characters)
    logger.info(f"DirectorSystem 已为工作流初始化: project_id={project_id}, characters={len(characters)}")

    # 设置 Agent provider
    engine = get_workflow_engine()

    async def _agent_provider_wrapper(agent_type: str, proj_id: str):
        """Agent provider 包装器"""
        from app.api.routes.websocket import create_agent_provider
        provider = await create_agent_provider(director)
        return await provider(agent_type, proj_id)

    engine.set_agent_provider(_agent_provider_wrapper)

    return director


@router.post("/{workflow_id}/execute", response_model=Dict[str, Any])
async def execute_workflow(
    workflow_id: str,
    project_id: str = Query(..., description="项目ID"),
    initial_context: Optional[Dict[str, Any]] = None,
):
    """
    执行工作流

    Args:
        workflow_id: 工作流ID
        project_id: 项目ID
        initial_context: 初始上下文

    Returns:
        Dict: 执行ID和初始状态
    """
    engine = get_workflow_engine()
    db = get_db()

    try:
        # 初始化 Agent provider
        await _setup_agent_provider_for_execution(project_id)

        execution_id = await engine.execute_workflow(
            workflow_id,
            project_id,
            initial_context or {},
            db,
        )

        return {
            "success": True,
            "message": "工作流已启动",
            "execution_id": execution_id,
            "workflow_id": workflow_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"执行工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{execution_id}", response_model=Dict[str, Any])
async def get_execution(execution_id: str):
    """
    获取工作流执行状态

    Args:
        execution_id: 执行ID

    Returns:
        Dict: 执行状态
    """
    engine = get_workflow_engine()
    db = get_db()

    execution = await engine.get_execution_state(execution_id, db)
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    return execution.model_dump()


@router.get("/executions", response_model=List[Dict[str, Any]])
async def list_executions(
    project_id: str = Query(..., description="项目ID"),
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    获取工作流执行列表

    Args:
        project_id: 项目ID
        status: 状态过滤
        limit: 返回数量
        offset: 偏移量

    Returns:
        List: 执行列表
    """
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        conditions = ["project_id = :project_id"]
        params = {"project_id": project_id, "limit": limit, "offset": offset}

        if status:
            conditions.append("status = :status")
            params["status"] = status

        query = f"""
        SELECT * FROM workflow_executions
        WHERE {' AND '.join(conditions)}
        ORDER BY started_at DESC
        LIMIT :limit OFFSET :offset
        """

        results = await db.execute_query(query, params)

        executions = []
        for row in results:
            executions.append({
                "id": row["id"],
                "workflow_id": row["workflow_id"],
                "project_id": str(row["project_id"]),
                "status": row["status"],
                "current_node": row["current_node"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                "total_duration_ms": row["total_duration_ms"],
                "error": row["error"],
            })

        return executions
    except Exception as e:
        logger.error(f"获取执行列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/executions/{execution_id}/pause", response_model=Dict[str, Any])
async def pause_execution(execution_id: str):
    """
    暂停工作流执行

    Args:
        execution_id: 执行ID

    Returns:
        Dict: 操作结果
    """
    engine = get_workflow_engine()
    db = get_db()

    success = await engine.pause_workflow(execution_id, db)
    if not success:
        raise HTTPException(status_code=400, detail="无法暂停工作流（可能不在运行状态）")

    return {
        "success": True,
        "message": f"工作流 {execution_id} 已暂停",
    }


@router.post("/executions/{execution_id}/resume", response_model=Dict[str, Any])
async def resume_execution(execution_id: str):
    """
    恢复工作流执行

    Args:
        execution_id: 执行ID

    Returns:
        Dict: 操作结果
    """
    engine = get_workflow_engine()
    db = get_db()

    success = await engine.resume_workflow(execution_id, db)
    if not success:
        raise HTTPException(status_code=400, detail="无法恢复工作流（可能不在暂停状态）")

    return {
        "success": True,
        "message": f"工作流 {execution_id} 已恢复",
    }


@router.post("/executions/{execution_id}/confirm-discussion", response_model=Dict[str, Any])
async def confirm_discussion(execution_id: str, approved: bool = Query(...), feedback: Optional[str] = Query(None)):
    """
    确认集体讨论结果

    用户可以选择：
    - 同意（approved=true）：工作流继续执行
    - 不同意（approved=false）：提供反馈意见，工作流重新开始

    Args:
        execution_id: 执行ID
        approved: 是否同意讨论结果
        feedback: 用户反馈意见（不同意时必填）

    Returns:
        Dict: 操作结果
    """
    engine = get_workflow_engine()
    db = get_db()

    if not approved and not feedback:
        raise HTTPException(status_code=400, detail="不同意讨论结果时必须提供反馈意见（feedback 参数）")

    result = await engine.confirm_discussion(
        execution_id=execution_id,
        approved=approved,
        feedback=feedback,
        db=db,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "确认失败"))

    return result


@router.post("/executions/{execution_id}/cancel", response_model=Dict[str, Any])
async def cancel_execution(execution_id: str):
    """
    取消工作流执行

    Args:
        execution_id: 执行ID

    Returns:
        Dict: 操作结果
    """
    engine = get_workflow_engine()
    db = get_db()

    success = await engine.cancel_workflow(execution_id, db)
    if not success:
        raise HTTPException(status_code=400, detail="无法取消工作流")

    return {
        "success": True,
        "message": f"工作流 {execution_id} 已取消",
    }
