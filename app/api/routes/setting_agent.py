"""
Setting Agent API 路由
设定管理、冲突检测、协商解决
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.models.setting_agent import (
    SettingAgentMode,
    SettingChangeType,
    SettingConflict,
)
from app.services.setting_agent_service import get_setting_agent_service

router = APIRouter()


# ==================== 请求模型 ====================

class ChatRequest(BaseModel):
    """聊天请求"""
    project_id: str
    message: str
    context: Optional[Dict[str, Any]] = None


class SettingChangeRequest(BaseModel):
    """设定变更请求"""
    project_id: str
    change_type: str  # add, modify, delete, merge
    lore_data: Optional[Dict[str, Any]] = None
    target_lore_id: Optional[str] = None
    user_intent: Optional[str] = None


class NegotiateRequest(BaseModel):
    """协商请求"""
    project_id: str
    conflict_id: str
    user_response: str


class ExecuteChangeRequest(BaseModel):
    """执行变更请求"""
    project_id: str
    request_id: str
    override_conflicts: bool = False


# ==================== API 端点 ====================

@router.post("/chat")
async def chat_with_setting_agent(request: ChatRequest):
    """
    与 Setting Agent 聊天

    可以用于：
    - 询问设定相关的问题
    - 请求添加/修改设定
    - 获取设定建议
    """
    service = get_setting_agent_service()

    try:
        result = await service.chat(
            project_id=request.project_id,
            message=request.message,
            context=request.context,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/change")
async def request_setting_change(request: SettingChangeRequest):
    """
    请求设定变更

    会自动进行冲突检测，返回检测结果
    """
    service = get_setting_agent_service()

    try:
        # 转换变更类型
        change_type = SettingChangeType(request.change_type)

        result = await service.process_setting_change(
            project_id=request.project_id,
            change_type=change_type,
            lore_data=request.lore_data,
            target_lore_id=request.target_lore_id,
            user_intent=request.user_intent,
        )

        return {
            "success": True,
            "request": result.model_dump(),
            "has_conflicts": result.has_conflicts,
            "conflicts": [c.model_dump() for c in result.conflicts],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid change_type: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/negotiate")
async def negotiate_conflict(request: NegotiateRequest):
    """
    协商解决冲突

    通过多轮对话与用户协商如何解决设定冲突
    """
    service = get_setting_agent_service()

    try:
        result = await service.negotiate(
            project_id=request.project_id,
            conflict_id=request.conflict_id,
            user_response=request.user_response,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_setting_change(request: ExecuteChangeRequest):
    """
    执行设定变更

    在冲突解决后（或强制覆盖）执行实际的变更
    """
    service = get_setting_agent_service()

    try:
        result = await service.execute_change(
            project_id=request.project_id,
            request_id=request.request_id,
            override_conflicts=request.override_conflicts,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/summary")
async def get_lore_summary(project_id: str):
    """
    获取项目设定摘要

    包括统计信息、宪法级规则、关键实体等
    """
    service = get_setting_agent_service()

    try:
        summary = await service.get_project_lore_summary(project_id)
        return summary.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/history")
async def get_conversation_history(project_id: str, limit: int = 50):
    """
    获取 Setting Agent 对话历史
    """
    service = get_setting_agent_service()

    try:
        session = await service.get_or_create_session(project_id)
        history = session.conversation_history[-limit:]
        return {
            "project_id": project_id,
            "session_id": session.id,
            "history": history,
            "total": len(session.conversation_history),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/conflicts")
async def get_pending_conflicts(project_id: str):
    """
    获取待处理的设定冲突
    """
    service = get_setting_agent_service()

    try:
        session = await service.get_or_create_session(project_id)
        return {
            "project_id": project_id,
            "pending_conflicts": [c.model_dump() for c in session.pending_conflicts],
            "count": len(session.pending_conflicts),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/session")
async def create_or_get_session(project_id: str, mode: str = "management"):
    """
    创建或获取 Setting Agent 会话
    """
    service = get_setting_agent_service()

    try:
        agent_mode = SettingAgentMode(mode)
        session = await service.get_or_create_session(project_id, agent_mode)
        return {
            "success": True,
            "session": session.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
