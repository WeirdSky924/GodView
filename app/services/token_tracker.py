"""
Token 追踪服务

记录和统计项目的 Token 消耗
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid

from app.models.token_usage import (
    TokenUsageRecord,
    TokenUsageSummary,
    ProjectTokenStats,
    DailyTokenStats,
    UsageCategory,
    calculate_cost,
)

logger = logging.getLogger(__name__)


class TokenTracker:
    """Token 追踪服务"""

    def __init__(self):
        self._db = None

    def set_db(self, db):
        """设置数据库实例"""
        self._db = db

    @property
    def db(self):
        """获取数据库实例"""
        if self._db is None:
            from app.api.app import postgres_db
            self._db = postgres_db
        return self._db

    async def record_usage(
        self,
        project_id: str,
        input_tokens: int,
        output_tokens: int,
        provider: str,
        model: str,
        category: UsageCategory,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
        character_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TokenUsageRecord:
        """
        记录 Token 使用

        Args:
            project_id: 项目 ID
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            provider: LLM 提供商
            model: 模型名称
            category: 使用场景
            agent_name: Agent 名称
            session_id: 会话 ID
            chapter_id: 章节 ID
            character_id: 角色 ID
            metadata: 额外元数据

        Returns:
            Token 使用记录
        """
        total_tokens = input_tokens + output_tokens
        estimated_cost = calculate_cost(model, input_tokens, output_tokens)

        record = TokenUsageRecord(
            id=str(uuid.uuid4()),
            project_id=project_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            provider=provider,
            model=model,
            category=category,
            agent_name=agent_name,
            session_id=session_id,
            chapter_id=chapter_id,
            character_id=character_id,
            estimated_cost=estimated_cost,
            metadata=metadata or {},
        )

        # 保存到数据库
        if self.db:
            try:
                await self.db.save_token_usage({
                    "id": record.id,
                    "project_id": record.project_id,
                    "input_tokens": record.input_tokens,
                    "output_tokens": record.output_tokens,
                    "total_tokens": record.total_tokens,
                    "provider": record.provider,
                    "model": record.model,
                    "category": record.category,
                    "agent_name": record.agent_name,
                    "session_id": record.session_id,
                    "chapter_id": record.chapter_id,
                    "character_id": record.character_id,
                    "estimated_cost": record.estimated_cost,
                    "metadata": record.metadata,
                    "created_at": record.created_at,
                })

                # 更新项目统计
                await self.db._update_project_token_stats(project_id, total_tokens, estimated_cost)

                logger.info(
                    f"Token usage recorded: project={project_id}, "
                    f"tokens={total_tokens}, cost=${estimated_cost:.6f}"
                )
            except Exception as e:
                logger.error(f"Failed to save token usage: {e}")
        else:
            logger.warning("Database not available, token usage not saved")

        return record

    async def get_project_summary(
        self,
        project_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> TokenUsageSummary:
        """
        获取项目 Token 使用摘要

        Args:
            project_id: 项目 ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Token 使用摘要
        """
        if not self.db:
            return TokenUsageSummary()

        try:
            stats = await self.db.get_token_stats_by_project(project_id)

            # 获取按场景和模型分组
            by_category_list = await self.db.get_token_stats_by_category(project_id)
            by_model_list = await self.db.get_token_stats_by_model(project_id)

            by_category = {item["category"]: item["tokens"] for item in by_category_list}
            by_model = {item["model"]: item["tokens"] for item in by_model_list}

            return TokenUsageSummary(
                total_tokens=stats.get("total_tokens", 0) or 0,
                total_input_tokens=stats.get("input_tokens", 0) or 0,
                total_output_tokens=stats.get("output_tokens", 0) or 0,
                total_cost=float(stats.get("total_cost", 0) or 0),
                record_count=stats.get("record_count", 0) or 0,
                by_category=by_category,
                by_model=by_model,
            )
        except Exception as e:
            logger.error(f"Failed to get token summary: {e}")
            return TokenUsageSummary()

    async def get_project_stats(self, project_id: str) -> ProjectTokenStats:
        """
        获取项目 Token 统计

        包括今日、本周、本月统计
        """
        if not self.db:
            raise ValueError("Database not available")

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        try:
            # 获取项目信息
            project = await self.db.get_project(project_id)
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # 获取每日统计用于计算今日、本周、本月
            daily_stats = await self.db.get_daily_token_stats(project_id, 31)

            today_tokens = 0
            today_cost = 0.0
            week_tokens = 0
            week_cost = 0.0
            month_tokens = 0
            month_cost = 0.0

            today_str = today_start.strftime("%Y-%m-%d")
            week_str = week_start.strftime("%Y-%m-%d")
            month_str = month_start.strftime("%Y-%m-%d")

            for stat in daily_stats:
                date_str = stat.get("date", "")
                if hasattr(date_str, 'strftime'):
                    date_str = date_str.strftime("%Y-%m-%d")

                tokens = stat.get("total_tokens", 0) or 0
                cost = float(stat.get("cost", 0) or 0)

                if date_str == today_str:
                    today_tokens = tokens
                    today_cost = cost

                if date_str >= week_str:
                    week_tokens += tokens
                    week_cost += cost

                if date_str >= month_str:
                    month_tokens += tokens
                    month_cost += cost

            return ProjectTokenStats(
                project_id=project_id,
                project_name=project.get("name", ""),
                total_tokens=project.get("total_tokens", 0) or 0,
                total_cost=float(project.get("total_cost", 0) or 0),
                today_tokens=today_tokens,
                today_cost=today_cost,
                week_tokens=week_tokens,
                week_cost=week_cost,
                month_tokens=month_tokens,
                month_cost=month_cost,
            )
        except Exception as e:
            logger.error(f"Failed to get project stats: {e}")
            raise

    async def get_all_project_stats(self) -> List[ProjectTokenStats]:
        """获取所有项目的 Token 统计"""
        if not self.db:
            return []

        try:
            projects = await self.db.get_all_project_token_stats()
            stats_list = []

            for project in projects:
                stats = await self.get_project_stats(project["project_id"])
                stats_list.append(stats)

            return stats_list
        except Exception as e:
            logger.error(f"Failed to get all project stats: {e}")
            return []

    async def get_daily_stats(
        self,
        project_id: str,
        days: int = 7,
    ) -> List[DailyTokenStats]:
        """
        获取每日 Token 统计

        Args:
            project_id: 项目 ID
            days: 天数

        Returns:
            每日统计列表
        """
        if not self.db:
            return []

        try:
            rows = await self.db.get_daily_token_stats(project_id, days)

            return [
                DailyTokenStats(
                    date=str(row.get("date", "")),
                    total_tokens=row.get("total_tokens", 0) or 0,
                    input_tokens=row.get("input_tokens", 0) or 0,
                    output_tokens=row.get("output_tokens", 0) or 0,
                    cost=float(row.get("cost", 0) or 0),
                    record_count=row.get("record_count", 0) or 0,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get daily stats: {e}")
            return []


# 全局实例
token_tracker = TokenTracker()
