"""
Bootstrap 流程 API 路由
v4 核心需求：项目初始化流程的状态机管理
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.models.bootstrap import (
    BootstrapSession,
    BootstrapStage,
    BootstrapMessage,
    StartBootstrapRequest,
    SendMessageRequest,
    UploadOutlineRequest,
    ConfirmSeedRequest,
    RunBootstrapRequest,
    ReviseSeedRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 启动 Bootstrap ====================

@router.post("/start", response_model=Dict[str, Any])
async def start_bootstrap(request: StartBootstrapRequest):
    """
    启动 Bootstrap 流程

    Args:
        request: 启动请求，包含项目 ID 和可选的初始消息

    Returns:
        Dict: Bootstrap 会话信息
    """
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 验证项目存在
    project = await postgres_db.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        orchestrator = get_bootstrap_orchestrator()
        session = await orchestrator.create_session(
            project_id=request.project_id,
            initial_message=request.initial_message,
        )
        return {
            "success": True,
            "session": session.model_dump(mode="json"),
            "message": "Bootstrap 会话已创建",
        }
    except Exception as e:
        logger.error(f"启动 Bootstrap 失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 获取 Bootstrap 会话 ====================

@router.get("/{session_id}", response_model=Dict[str, Any])
async def get_bootstrap_session(session_id: str):
    """
    获取 Bootstrap 会话详情

    Args:
        session_id: 会话 ID

    Returns:
        Dict: 会话信息
    """
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator

    try:
        orchestrator = get_bootstrap_orchestrator()
        session = await orchestrator.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Bootstrap 会话不存在")

        return session.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Bootstrap 会话失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/status", response_model=Dict[str, Any])
async def get_bootstrap_status(session_id: str):
    """
    获取 Bootstrap 状态

    Args:
        session_id: 会话 ID

    Returns:
        Dict: 状态信息
    """
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator

    try:
        orchestrator = get_bootstrap_orchestrator()
        session = await orchestrator.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Bootstrap 会话不存在")

        return {
            "session_id": session.id,
            "project_id": session.project_id,
            "status": session.status.value,
            "current_stage": session.current_stage.value,
            "progress": session.progress,
            "error_message": session.error_message,
            "retry_count": session.retry_count,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Bootstrap 状态失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 与 SettingAgent 对话 ====================

@router.post("/message", response_model=Dict[str, Any])
async def send_message(request: SendMessageRequest):
    """
    发送消息到 SettingAgent

    Args:
        request: 消息请求

    Returns:
        Dict: Agent 响应
    """
    from app.services.setting_agent import get_setting_agent

    try:
        agent = get_setting_agent()
        response = await agent.process_message(
            session_id=request.session_id,
            message=request.message,
        )
        return {
            "success": True,
            "response": response,
        }
    except Exception as e:
        logger.error(f"发送消息失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 大纲输入 ====================

@router.post("/outline", response_model=Dict[str, Any])
async def upload_outline(request: UploadOutlineRequest):
    """
    上传大纲文本

    Args:
        request: 大纲上传请求

    Returns:
        Dict: 处理结果
    """
    from app.services.outline_ingestion import get_outline_ingestion_service
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator

    try:
        # 获取大纲输入服务
        outline_service = get_outline_ingestion_service()
        result = await outline_service.ingest_outline(
            content=request.content,
            source_type=request.source_type,
            session_id=request.session_id,
        )

        # 更新 Bootstrap 会话状态
        orchestrator = get_bootstrap_orchestrator()
        await orchestrator.update_session_stage(
            session_id=request.session_id,
            stage=BootstrapStage.OUTLINE_INGESTED,
        )

        return {
            "success": True,
            "outline_id": result.get("outline_id"),
            "chunk_count": result.get("chunk_count"),
            "message": "大纲已上传并处理完成",
        }
    except Exception as e:
        logger.error(f"上传大纲失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 确认 Seed ====================

@router.post("/{session_id}/confirm", response_model=Dict[str, Any])
async def confirm_seed(session_id: str, request: ConfirmSeedRequest):
    """
    确认结构化 Seed

    Args:
        session_id: 会话 ID
        request: 确认请求

    Returns:
        Dict: 确认结果
    """
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator

    try:
        orchestrator = get_bootstrap_orchestrator()
        session = await orchestrator.confirm_seed(
            session_id=session_id,
            seed_data=request.seed_data,
        )
        return {
            "success": True,
            "message": "Seed 已确认，等待执行 Bootstrap",
            "session": session.model_dump(mode="json"),
        }
    except Exception as e:
        logger.error(f"确认 Seed 失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 修订 Seed ====================

@router.post("/{session_id}/revise", response_model=Dict[str, Any])
async def revise_seed(session_id: str, request: ReviseSeedRequest):
    """
    修订 Seed

    Args:
        session_id: 会话 ID
        request: 修订请求

    Returns:
        Dict: 修订结果
    """
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator

    try:
        orchestrator = get_bootstrap_orchestrator()
        session = await orchestrator.revise_seed(
            session_id=session_id,
            feedback=request.feedback,
        )
        return {
            "success": True,
            "message": "Seed 修订已提交，等待重新生成",
            "session": session.model_dump(mode="json"),
        }
    except Exception as e:
        logger.error(f"修订 Seed 失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 执行 Bootstrap ====================

@router.post("/{session_id}/run", response_model=Dict[str, Any])
async def run_bootstrap(session_id: str):
    """
    执行 Bootstrap

    Args:
        session_id: 会话 ID

    Returns:
        Dict: 执行结果
    """
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator

    try:
        orchestrator = get_bootstrap_orchestrator()
        result = await orchestrator.run_bootstrap(session_id)

        return {
            "success": True,
            "message": "Bootstrap 执行完成",
            "result": result,
        }
    except Exception as e:
        logger.error(f"执行 Bootstrap 失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 获取 Seed 详情 ====================

@router.get("/{session_id}/seed", response_model=Dict[str, Any])
async def get_seed(session_id: str):
    """
    获取当前 Seed 数据

    Args:
        session_id: 会话 ID

    Returns:
        Dict: Seed 数据
    """
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator

    try:
        orchestrator = get_bootstrap_orchestrator()
        session = await orchestrator.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Bootstrap 会话不存在")

        # 返回提取的 seed 或确认的 seed
        seed_data = session.confirmed_seed if session.confirmed_seed else session.extracted_seed

        return {
            "session_id": session.id,
            "project_id": session.project_id,
            "seed_type": session.extracted_seed.get("seed_type", "initial"),
            "seed_data": seed_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Seed 失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 获取对话历史 ====================

@router.get("/{session_id}/messages", response_model=List[Dict[str, Any]])
async def get_messages(session_id: str, limit: int = Query(default=50, le=200)):
    """
    获取 SettingAgent 对话历史

    Args:
        session_id: 会话 ID
        limit: 返回数量限制

    Returns:
        List: 消息列表
    """
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator

    try:
        orchestrator = get_bootstrap_orchestrator()
        session = await orchestrator.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Bootstrap 会话不存在")

        messages = session.setting_agent_history[-limit:]
        return messages
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取消息历史失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 结束设定并提取 Seed ====================

@router.post("/{session_id}/finalize-setting", response_model=Dict[str, Any])
async def finalize_setting(session_id: str):
    """
    结束设定阶段并强制提取 Seed

    不依赖对话轮数阈值，直接从当前对话历史中提取结构化 seed

    Args:
        session_id: 会话 ID

    Returns:
        Dict: 提取结果，包含 seed 数据
    """
    from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator

    try:
        orchestrator = get_bootstrap_orchestrator()
        result = await orchestrator.finalize_setting(session_id)

        return {
            "success": True,
            "message": "设定阶段结束，Seed 已提取",
            "seed_data": result.get("seed_data"),
            "session": result.get("session"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"结束设定阶段失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))