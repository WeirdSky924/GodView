"""
Token 使用统计 API 路由
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.token_tracker import token_tracker
from app.models.token_usage import (
    TokenUsageSummary,
    ProjectTokenStats,
    DailyTokenStats,
    UsageCategory,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class TokenUsageResponse(BaseModel):
    """Token 使用响应"""
    success: bool
    message: str
    data: Optional[dict] = None


@router.get("/projects/{project_id}/summary", response_model=TokenUsageSummary)
async def get_project_token_summary(
    project_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> TokenUsageSummary:
    """
    获取项目 Token 使用摘要

    Args:
        project_id: 项目 ID
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）

    Returns:
        Token 使用摘要
    """
    try:
        return await token_tracker.get_project_summary(
            project_id, start_date, end_date
        )
    except Exception as e:
        logger.error(f"Failed to get token summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/stats", response_model=ProjectTokenStats)
async def get_project_token_stats(project_id: str) -> ProjectTokenStats:
    """
    获取项目 Token 统计

    包括总量、今日、本周、本月统计
    """
    try:
        return await token_tracker.get_project_stats(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get token stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/daily", response_model=List[DailyTokenStats])
async def get_project_daily_stats(
    project_id: str,
    days: int = Query(default=7, ge=1, le=30),
) -> List[DailyTokenStats]:
    """
    获取项目每日 Token 统计

    Args:
        project_id: 项目 ID
        days: 天数（默认 7 天，最多 30 天）

    Returns:
        每日统计列表
    """
    try:
        return await token_tracker.get_daily_stats(project_id, days)
    except Exception as e:
        logger.error(f"Failed to get daily stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=List[ProjectTokenStats])
async def get_all_token_stats() -> List[ProjectTokenStats]:
    """
    获取所有项目的 Token 统计

    按总 Token 量降序排列
    """
    try:
        return await token_tracker.get_all_project_stats()
    except Exception as e:
        logger.error(f"Failed to get all token stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/by-category")
async def get_token_by_category(
    project_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    获取按场景分组的 Token 统计
    """
    try:
        summary = await token_tracker.get_project_summary(
            project_id, start_date, end_date
        )
        return {
            "project_id": project_id,
            "by_category": summary.by_category,
            "total_tokens": summary.total_tokens,
        }
    except Exception as e:
        logger.error(f"Failed to get category stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/by-model")
async def get_token_by_model(
    project_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    获取按模型分组的 Token 统计
    """
    try:
        summary = await token_tracker.get_project_summary(
            project_id, start_date, end_date
        )
        return {
            "project_id": project_id,
            "by_model": summary.by_model,
            "total_tokens": summary.total_tokens,
        }
    except Exception as e:
        logger.error(f"Failed to get model stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
