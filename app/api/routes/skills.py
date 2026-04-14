"""
Skill API 路由
Agent Skill 管理、分配和执行

支持智能检索：Embedding + LLM 两阶段混合架构
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.models.skill import (
    Skill,
    SkillAssignment,
    SkillType,
    SkillStatus,
    SkillCategory,
    SkillLoadMode,
    CreateSkillDTO,
    UpdateSkillDTO,
    AssignSkillDTO,
    ExecuteSkillDTO,
    SkillTestResult,
    SkillExecutionLog,
)
from app.services.skill_service import get_skill_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== DTOs ====================

class SkillRetrievalRequest(BaseModel):
    """Skill 智能检索请求"""
    query: str = Field(..., description="场景描述/用户指令")
    agent_type: str = Field(..., description="Agent 类型")
    top_k: int = Field(default=5, ge=1, le=20, description="返回候选数量")
    min_similarity: float = Field(default=0.3, ge=0.0, le=1.0, description="最小相似度阈值")
    use_llm_decision: bool = Field(default=True, description="是否使用 LLM 决策")


class SkillDecisionResult(BaseModel):
    """Skill 决策结果"""
    skill_id: str
    skill_name: str
    should_activate: bool
    confidence: float
    parameters: Dict[str, Any]
    reason: str


class SkillRetrievalResponse(BaseModel):
    """Skill 智能检索响应"""
    query: str
    agent_type: str
    candidates: List[Dict[str, Any]]  # Embedding 粗筛候选
    decisions: List[SkillDecisionResult]  # LLM 决策结果
    final_skills: List[Dict[str, Any]]  # 最终激活的 Skills


# ==================== Skill CRUD ====================

@router.get("/", response_model=List[Skill])
async def list_skills(
    skill_type: Optional[SkillType] = None,
    status: Optional[SkillStatus] = None,
    category: Optional[SkillCategory] = None,
    tags: Optional[str] = None,  # 逗号分隔
    search: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """
    获取 Skill 列表

    支持按类型、状态、类别、标签过滤和搜索
    """
    service = get_skill_service()

    tag_list = tags.split(",") if tags else None

    skills = await service.get_all_skills(
        skill_type=skill_type,
        status=status,
        category=category,
        tags=tag_list,
        search=search,
        limit=limit,
        offset=offset,
    )

    return skills


@router.post("/", response_model=Skill)
async def create_skill(dto: CreateSkillDTO):
    """创建 Skill"""
    service = get_skill_service()

    try:
        skill = await service.create_skill(dto)
        return skill
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{skill_id}", response_model=Skill)
async def get_skill(skill_id: str):
    """获取 Skill 详情"""
    service = get_skill_service()
    skill = await service.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    return skill


@router.put("/{skill_id}", response_model=Skill)
async def update_skill(skill_id: str, dto: UpdateSkillDTO):
    """更新 Skill"""
    service = get_skill_service()
    skill = await service.update_skill(skill_id, dto)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    return skill


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    """删除 Skill"""
    service = get_skill_service()
    success = await service.delete_skill(skill_id)

    if not success:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    return {"success": True, "message": "Skill 已删除"}


# ==================== Skill 搜索和生成 ====================

@router.post("/search", response_model=List[Skill])
async def search_skills(query: str, limit: int = 10):
    """搜索 Skill"""
    service = get_skill_service()
    return await service.search_skills(query, limit)


@router.post("/generate", response_model=Skill)
async def generate_skill(description: str, skill_type: SkillType = SkillType.PROMPT):
    """
    AI 生成 Skill

    根据描述自动生成 Skill 内容
    """
    service = get_skill_service()
    return await service.generate_skill_from_description(description, skill_type)


# ==================== Skill 测试和执行 ====================

@router.post("/{skill_id}/test", response_model=SkillTestResult)
async def test_skill(skill_id: str, parameters: Dict[str, Any] = Body(default={})):
    """
    测试 Skill

    Args:
        skill_id: Skill ID
        parameters: 测试参数 (JSON body)

    Returns:
        SkillTestResult: 测试结果
    """
    service = get_skill_service()

    dto = ExecuteSkillDTO(
        skill_id=skill_id,
        parameters=parameters,
    )

    result = await service.execute_skill(dto)
    return result


@router.post("/{skill_id}/execute", response_model=SkillTestResult)
async def execute_skill(
    skill_id: str,
    project_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    parameters: Dict[str, Any] = Body(default={}),
):
    """
    执行 Skill

    Args:
        skill_id: Skill ID
        project_id: 项目 ID (query param)
        agent_id: Agent ID (query param)
        parameters: 执行参数 (JSON body)

    Returns:
        SkillTestResult: 执行结果
    """
    service = get_skill_service()

    dto = ExecuteSkillDTO(
        skill_id=skill_id,
        project_id=project_id,
        agent_id=agent_id,
        parameters=parameters,
    )

    result = await service.execute_skill(dto)
    return result


# ==================== Skill 分配 ====================

@router.post("/assign", response_model=SkillAssignment)
async def assign_skill(dto: AssignSkillDTO):
    """将 Skill 分配给 Agent"""
    service = get_skill_service()

    try:
        assignment = await service.assign_skill_to_agent(dto)
        return assignment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/assign")
async def unassign_skill(skill_id: str, project_id: str, agent_id: str):
    """取消 Skill 分配"""
    service = get_skill_service()
    success = await service.unassign_skill_from_agent(skill_id, project_id, agent_id)

    if not success:
        raise HTTPException(status_code=404, detail="分配关系不存在")

    return {"success": True, "message": "已取消分配"}


@router.get("/{skill_id}/assignments", response_model=List[SkillAssignment])
async def get_skill_assignments(skill_id: str):
    """获取 Skill 的所有分配"""
    service = get_skill_service()
    return await service.get_skill_assignments(skill_id)


# ==================== Agent Skills ====================

@router.get("/agent/{project_id}/{agent_id}", response_model=List[Skill])
async def get_agent_skills(project_id: str, agent_id: str):
    """获取 Agent 已分配的 Skills"""
    service = get_skill_service()
    return await service.get_agent_skills(project_id, agent_id)


# ==================== 执行日志 ====================

@router.get("/{skill_id}/logs", response_model=List[SkillExecutionLog])
async def get_skill_logs(
    skill_id: str,
    project_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 50,
):
    """获取 Skill 执行日志"""
    service = get_skill_service()
    return await service.get_execution_logs(
        skill_id=skill_id,
        project_id=project_id,
        agent_id=agent_id,
        limit=limit,
    )


@router.get("/logs/all", response_model=List[SkillExecutionLog])
async def get_all_logs(
    project_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 50,
):
    """获取所有执行日志"""
    service = get_skill_service()
    return await service.get_execution_logs(
        project_id=project_id,
        agent_id=agent_id,
        limit=limit,
    )


# ==================== 统计 ====================

@router.get("/stats/overview")
async def get_skills_stats():
    """获取 Skill 统计概览"""
    service = get_skill_service()

    # 获取所有 Skills
    skills = await service.get_all_skills(limit=1000)

    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    total_usage = 0

    for skill in skills:
        by_type[skill.skill_type.value] = by_type.get(skill.skill_type.value, 0) + 1
        by_status[skill.status.value] = by_status.get(skill.status.value, 0) + 1
        by_category[skill.category.value] = by_category.get(skill.category.value, 0) + 1
        total_usage += skill.usage_count

    # 获取分配数量
    total_assignments = 0
    try:
        # 从数据库获取分配数量
        if service._db:
            rows = await service._db.execute_query("SELECT COUNT(*) as count FROM skill_assignments")
            total_assignments = rows[0]['count'] if rows else 0
    except Exception:
        pass

    return {
        "total_skills": len(skills),
        "total_assignments": total_assignments,
        "total_usage": total_usage,
        "by_type": by_type,
        "by_status": by_status,
        "by_category": by_category,
    }


# ==================== Agent 类型 Skills ====================

@router.get("/agents/{agent_type}/skills", response_model=List[Skill])
async def get_agent_type_skills(agent_type: str):
    """
    获取 Agent 模板的所有可用 Skills

    Args:
        agent_type: Agent 类型

    Returns:
        List: Agent 可用的 Skill 列表
    """
    service = get_skill_service()
    return await service.get_skills_for_agent_type(agent_type)


# ==================== 类别和类型 ====================

@router.get("/categories", response_model=List[str])
async def get_skill_categories():
    """获取所有 Skill 类别"""
    return [c.value for c in SkillCategory]


@router.get("/types", response_model=List[str])
async def get_skill_types():
    """获取所有 Skill 类型"""
    return [t.value for t in SkillType]


# ==================== 初始化 ====================

@router.post("/initialize", response_model=Dict[str, Any])
async def initialize_default_skills():
    """
    初始化默认 Skills 到系统

    Returns:
        Dict: 初始化结果
    """
    service = get_skill_service()

    # Debug: check if database is connected
    debug_info = {
        "has_db": service._db is not None,
        "db_type": str(type(service._db)) if service._db else None,
    }

    try:
        from app.data.default_skills import initialize_default_skills
        result = await initialize_default_skills(service)
        return {
            "success": True,
            "message": "默认 Skills 初始化完成",
            "result": result,
            "debug": debug_info,
        }
    except Exception as e:
        import logging
        import traceback
        logging.error(f"初始化默认 Skills 失败: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 智能检索 API ====================

@router.post("/retrieve", response_model=SkillRetrievalResponse)
async def retrieve_skills_intelligently(request: SkillRetrievalRequest):
    """
    智能 Skill 检索（Embedding + LLM 两阶段）

    流程：
    1. Embedding 粗筛：从所有按需 Skill 中检索 Top-K 相关候选
    2. LLM 精决：让 LLM 从候选中选择最合适的并提取参数

    Args:
        request: 检索请求

    Returns:
        SkillRetrievalResponse: 检索结果
    """
    try:
        from app.services.skill_retrieval import get_skill_retrieval_service
        from app.services.skill_service import get_skill_service

        skill_service = get_skill_service()
        retrieval_service = get_skill_retrieval_service(skill_service=skill_service)

        # 执行两阶段检索
        result = await retrieval_service.retrieve_skills(
            query=request.query,
            agent_type=request.agent_type,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )

        # 构建响应
        candidates_data = []
        for candidate in result.candidates:
            candidates_data.append({
                "skill_id": candidate.skill.id,
                "skill_name": candidate.skill.name,
                "description": candidate.skill.description,
                "similarity_score": round(candidate.similarity_score, 3),
                "load_mode": candidate.skill.load_mode.value,
            })

        decisions_data = []
        for decision in result.decisions:
            decisions_data.append({
                "skill_id": decision.skill_id,
                "skill_name": decision.skill_name,
                "should_activate": decision.should_activate,
                "confidence": round(decision.confidence, 3),
                "parameters": decision.parameters,
                "reason": decision.reason,
            })

        final_skills_data = []
        for skill, params in result.final_skills:
            final_skills_data.append({
                "skill_id": skill.id,
                "skill_name": skill.name,
                "description": skill.description,
                "load_mode": skill.load_mode.value,
                "parameters": params,
            })

        return SkillRetrievalResponse(
            query=request.query,
            agent_type=request.agent_type,
            candidates=candidates_data,
            decisions=decisions_data,
            final_skills=final_skills_data,
        )

    except Exception as e:
        logger.error(f"智能检索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_type}/retrieve")
async def retrieve_skills_for_agent(
    agent_type: str,
    query: str = Query(..., description="场景描述/用户指令"),
    top_k: int = Query(default=5, ge=1, le=20),
    min_similarity: float = Query(default=0.3, ge=0.0, le=1.0),
):
    """
    为指定 Agent 智能检索 Skills

    GET 版本，便于测试

    Args:
        agent_type: Agent 类型
        query: 场景描述
        top_k: 返回候选数量
        min_similarity: 最小相似度阈值

    Returns:
        检索结果
    """
    request = SkillRetrievalRequest(
        query=query,
        agent_type=agent_type,
        top_k=top_k,
        min_similarity=min_similarity,
    )
    return await retrieve_skills_intelligently(request)


@router.post("/agents/{agent_type}/prompt")
async def build_agent_prompt_with_skills(
    agent_type: str,
    query: str = Body(..., embed=True, description="场景描述"),
    project_id: Optional[str] = Body(default=None, embed=True),
    use_intelligent_retrieval: bool = Body(default=True, embed=True),
):
    """
    构建 Agent 的完整 prompt（包含智能检索的 Skills）

    Args:
        agent_type: Agent 类型
        query: 场景描述
        project_id: 项目 ID
        use_intelligent_retrieval: 是否使用智能检索

    Returns:
        Dict: 包含 prompt 和 Skills 信息
    """
    try:
        from app.services.agent_prompt_service import get_agent_prompt_service

        prompt_service = get_agent_prompt_service()

        # 构建 prompt
        prompt = await prompt_service.build_agent_prompt(
            agent_type=agent_type,
            project_id=project_id,
            context_query=query,
            use_intelligent_retrieval=use_intelligent_retrieval,
        )

        # 获取 Skills 信息
        skills_info = await prompt_service.get_agent_skills_info(
            agent_type=agent_type,
            context_query=query,
            use_intelligent_retrieval=use_intelligent_retrieval,
        )

        return {
            "agent_type": agent_type,
            "query": query,
            "prompt": prompt,
            "prompt_length": len(prompt),
            "skills_count": len(skills_info),
            "skills": skills_info,
        }

    except Exception as e:
        logger.error(f"构建 Agent prompt 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/load-modes", response_model=List[Dict[str, str]])
async def get_skill_load_modes():
    """获取所有 Skill 加载模式"""
    return [
        {"value": mode.value, "label": _get_load_mode_label(mode)}
        for mode in SkillLoadMode
    ]


def _get_load_mode_label(mode: SkillLoadMode) -> str:
    """获取加载模式的中文标签"""
    labels = {
        SkillLoadMode.CORE: "核心层（始终加载）",
        SkillLoadMode.ON_DEMAND: "按需层（智能检索）",
    }
    return labels.get(mode, mode.value)


# ==================== Skill 编排 API ====================

class OrchestrateRequest(BaseModel):
    """编排请求"""
    goal: str = Field(..., description="任务目标描述")
    agent_type: str = Field(..., description="Agent 类型")
    initial_params: Optional[Dict[str, Any]] = Field(default=None, description="初始参数")
    max_iterations: int = Field(default=10, ge=1, le=50, description="最大迭代次数")


class OrchestrateResponse(BaseModel):
    """编排响应"""
    goal: str
    agent_type: str
    total_calls: int
    success_calls: int
    final_result: Optional[str]
    call_history: List[Dict[str, Any]]
    variables: Dict[str, Any]


@router.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate_skills(request: OrchestrateRequest):
    """
    执行 Skill 编排

    让 Agent 自主决定：
    1. 调用哪个 Skill
    2. 传递什么参数
    3. 是否需要继续调用
    4. 如何处理结果

    典型场景：
    - 章节写作：分段生成 → 合并 → 字数统计 → 续写（循环）
    - 内容生成：生成 → 检查 → 修改（循环）
    """
    try:
        from app.services.skill_orchestrator import get_skill_orchestrator
        from app.services.skill_service import get_skill_service

        skill_service = get_skill_service()
        orchestrator = get_skill_orchestrator(skill_service=skill_service)

        # 执行编排
        context = await orchestrator.orchestrate(
            agent_type=request.agent_type,
            goal=request.goal,
            initial_params=request.initial_params,
            max_iterations=request.max_iterations,
        )

        # 构建响应
        success_calls = sum(
            1 for c in context.call_history
            if c.status.value == "success"
        )

        return OrchestrateResponse(
            goal=context.initial_goal,
            agent_type=context.agent_type,
            total_calls=len(context.call_history),
            success_calls=success_calls,
            final_result=context.get_last_result(),
            call_history=[c.to_dict() for c in context.call_history],
            variables=context.variables,
        )

    except Exception as e:
        logger.error(f"Skill 编排失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/templates")
async def get_workflow_templates():
    """
    获取预定义的工作流模板

    Returns:
        List: 工作流模板列表
    """
    from app.services.skill_orchestrator import WorkflowTemplate

    templates = [
        WorkflowTemplate.chapter_writing_workflow(),
        # 可以添加更多模板
    ]

    return templates


@router.post("/workflows/chapter-writing")
async def execute_chapter_writing_workflow(
    chapter_title: str = Body(..., description="章节标题"),
    target_words: int = Body(default=3000, ge=500, le=50000, description="目标字数"),
    chapter_outline: Optional[str] = Body(default=None, description="章节大纲（可选）"),
    agent_type: str = Body(default="writer", description="Agent 类型"),
):
    """
    执行章节写作工作流

    自动编排：
    1. 生成章节大纲
    2. 分段生成内容
    3. 合并内容
    4. 检查字数
    5. 如果不足则续写

    Args:
        chapter_title: 章节标题
        target_words: 目标字数
        chapter_outline: 章节大纲（可选）
        agent_type: Agent 类型

    Returns:
        Dict: 包含完整章节内容和执行过程
    """
    try:
        from app.services.skill_orchestrator import get_skill_orchestrator
        from app.services.skill_service import get_skill_service

        skill_service = get_skill_service()
        orchestrator = get_skill_orchestrator(skill_service=skill_service)

        # 构建目标
        goal = f"""写一个章节，标题为「{chapter_title}」，目标字数 {target_words} 字。

要求：
1. 内容要完整、连贯
2. 字数尽量接近目标（误差不超过10%）
3. 按段落分段生成，最后合并

{f"参考大纲：{chapter_outline}" if chapter_outline else ""}
"""

        # 初始参数
        initial_params = {
            "chapter_title": chapter_title,
            "target_words": target_words,
        }
        if chapter_outline:
            initial_params["chapter_outline"] = chapter_outline

        # 执行编排
        context = await orchestrator.orchestrate(
            agent_type=agent_type,
            goal=goal,
            initial_params=initial_params,
            max_iterations=20,  # 章节写作可能需要更多迭代
        )

        # 获取最终内容
        final_content = context.get_last_result()
        word_count = len(final_content) if final_content else 0

        return {
            "success": word_count > 0,
            "chapter_title": chapter_title,
            "target_words": target_words,
            "actual_words": word_count,
            "completion_rate": round(word_count / target_words * 100, 1) if target_words > 0 else 0,
            "content": final_content,
            "iterations": context.current_iteration,
            "total_calls": len(context.call_history),
            "call_history": [c.to_dict() for c in context.call_history],
        }

    except Exception as e:
        logger.error(f"章节写作工作流执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== MD 文件同步 API ====================

@router.post("/sync-md-files", response_model=Dict[str, Any])
async def sync_md_files():
    """
    将 skills/ 目录下的 MD 文件同步到数据库

    这个API会：
    1. 扫描 skills/ 目录下的所有 MD 文件
    2. 提取 YAML frontmatter 作为元数据
    3. 将元数据存入数据库（内容从 MD 文件读取）

    Returns:
        Dict: 同步结果统计
    """
    try:
        from app.services.skill_service import get_skill_service
        service = get_skill_service()
        result = await service.sync_md_files_to_db()
        return {
            "success": True,
            "message": f"同步完成: {result.get('synced', 0)} 个成功",
            "result": result,
        }
    except Exception as e:
        logger.error(f"同步 MD 文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/md-stats", response_model=Dict[str, Any])
async def get_md_stats():
    """
    获取 MD 文件统计信息

    Returns:
        Dict: MD 文件统计
    """
    try:
        from app.services.md_file_service import get_md_file_service
        md_service = get_md_file_service()
        stats = md_service.get_stats()
        return stats
    except Exception as e:
        logger.error(f"获取 MD 文件统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
