"""
Skill API 路由
Agent Skill 管理、分配和执行
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.skill import (
    Skill,
    SkillAssignment,
    SkillType,
    SkillStatus,
    CreateSkillDTO,
    UpdateSkillDTO,
    AssignSkillDTO,
    ExecuteSkillDTO,
    SkillTestResult,
    SkillExecutionLog,
)
from app.services.skill_service import get_skill_service

router = APIRouter()


# ==================== Skill CRUD ====================

@router.get("/", response_model=List[Skill])
async def list_skills(
    skill_type: Optional[SkillType] = None,
    status: Optional[SkillStatus] = None,
    tags: Optional[str] = None,  # 逗号分隔
    search: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """
    获取 Skill 列表

    支持按类型、状态、标签过滤和搜索
    """
    service = get_skill_service()

    tag_list = tags.split(",") if tags else None

    skills = await service.get_all_skills(
        skill_type=skill_type,
        status=status,
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
async def test_skill(skill_id: str, parameters: Dict[str, Any] = {}):
    """测试 Skill"""
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
    parameters: Dict[str, Any] = {},
):
    """执行 Skill"""
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
    skills = list(service._skills.values())

    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    total_usage = 0

    for skill in skills:
        by_type[skill.skill_type.value] = by_type.get(skill.skill_type.value, 0) + 1
        by_status[skill.status.value] = by_status.get(skill.status.value, 0) + 1
        total_usage += skill.usage_count

    return {
        "total_skills": len(skills),
        "total_assignments": len(service._assignments),
        "total_usage": total_usage,
        "by_type": by_type,
        "by_status": by_status,
    }
