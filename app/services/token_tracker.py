"""
Token 追踪服务

记录和统计项目的 Token 消耗
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.models.token_usage import (
    TokenUsageRecord,
    TokenUsageSummary,
    ProjectTokenStats,
    DailyTokenStats,
    UsageCategory,
    calculate_cost,
)
from app.database.postgres import get_connection

logger = logging.getLogger(__name__)


class TokenTracker:
    """Token 追踪服务"""

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
        await self._save_record(record)

        # 更新项目统计
        await self._update_project_stats(project_id, total_tokens, estimated_cost)

        logger.info(
            f"Token usage recorded: project={project_id}, "
            f"tokens={total_tokens}, cost=${estimated_cost:.6f}"
        )

        return record

    async def _save_record(self, record: TokenUsageRecord) -> str:
        """保存记录到数据库"""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO token_usage (
                    project_id, input_tokens, output_tokens, total_tokens,
                    provider, model, category, agent_name, session_id,
                    chapter_id, character_id, estimated_cost, metadata, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING id
                """,
                record.project_id,
                record.input_tokens,
                record.output_tokens,
                record.total_tokens,
                record.provider,
                record.model,
                record.category,
                record.agent_name,
                record.session_id,
                record.chapter_id,
                record.character_id,
                record.estimated_cost,
                record.metadata,
                record.created_at,
            )
            record.id = str(row["id"])
            return record.id

    async def _update_project_stats(
        self,
        project_id: str,
        tokens: int,
        cost: float
    ) -> None:
        """更新项目统计"""
        async with get_connection() as conn:
            await conn.execute(
                """
                UPDATE projects
                SET total_tokens = COALESCE(total_tokens, 0) + $1,
                    total_cost = COALESCE(total_cost, 0) + $2,
                    updated_at = NOW()
                WHERE id = $3
                """,
                tokens,
                cost,
                project_id,
            )

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
        async with get_connection() as conn:
            conditions = ["project_id = $1"]
            params = [project_id]
            param_idx = 2

            if start_date:
                conditions.append(f"created_at >= ${param_idx}")
                params.append(start_date)
                param_idx += 1

            if end_date:
                conditions.append(f"created_at <= ${param_idx}")
                params.append(end_date)
                param_idx += 1

            where_clause = " AND ".join(conditions)

            # 总计
            total_row = await conn.fetchrow(
                f"""
                SELECT
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(input_tokens), 0) as input_tokens,
                    COALESCE(SUM(output_tokens), 0) as output_tokens,
                    COALESCE(SUM(estimated_cost), 0) as total_cost,
                    COUNT(*) as record_count
                FROM token_usage
                WHERE {where_clause}
                """,
                *params,
            )

            # 按场景分组
            category_rows = await conn.fetch(
                f"""
                SELECT category, SUM(total_tokens) as tokens
                FROM token_usage
                WHERE {where_clause}
                GROUP BY category
                """,
                *params,
            )

            # 按模型分组
            model_rows = await conn.fetch(
                f"""
                SELECT model, SUM(total_tokens) as tokens
                FROM token_usage
                WHERE {where_clause}
                GROUP BY model
                """,
                *params,
            )

            return TokenUsageSummary(
                total_tokens=total_row["total_tokens"] or 0,
                total_input_tokens=total_row["input_tokens"] or 0,
                total_output_tokens=total_row["output_tokens"] or 0,
                total_cost=float(total_row["total_cost"] or 0),
                record_count=total_row["record_count"] or 0,
                by_category={row["category"]: row["tokens"] for row in category_rows},
                by_model={row["model"]: row["tokens"] for row in model_rows},
            )

    async def get_project_stats(self, project_id: str) -> ProjectTokenStats:
        """
        获取项目 Token 统计

        包括今日、本周、本月统计
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        async with get_connection() as conn:
            # 获取项目信息
            project_row = await conn.fetchrow(
                "SELECT name, total_tokens, total_cost FROM projects WHERE id = $1",
                project_id,
            )

            if not project_row:
                raise ValueError(f"Project not found: {project_id}")

            # 今日统计
            today_row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(total_tokens), 0) as tokens,
                    COALESCE(SUM(estimated_cost), 0) as cost
                FROM token_usage
                WHERE project_id = $1 AND created_at >= $2
                """,
                project_id,
                today_start,
            )

            # 本周统计
            week_row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(total_tokens), 0) as tokens,
                    COALESCE(SUM(estimated_cost), 0) as cost
                FROM token_usage
                WHERE project_id = $1 AND created_at >= $2
                """,
                project_id,
                week_start,
            )

            # 本月统计
            month_row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(total_tokens), 0) as tokens,
                    COALESCE(SUM(estimated_cost), 0) as cost
                FROM token_usage
                WHERE project_id = $1 AND created_at >= $2
                """,
                project_id,
                month_start,
            )

            return ProjectTokenStats(
                project_id=project_id,
                project_name=project_row["name"],
                total_tokens=project_row["total_tokens"] or 0,
                total_cost=float(project_row["total_cost"] or 0),
                today_tokens=today_row["tokens"] or 0,
                today_cost=float(today_row["cost"] or 0),
                week_tokens=week_row["tokens"] or 0,
                week_cost=float(week_row["cost"] or 0),
                month_tokens=month_row["tokens"] or 0,
                month_cost=float(month_row["cost"] or 0),
            )

    async def get_all_project_stats(self) -> List[ProjectTokenStats]:
        """获取所有项目的 Token 统计"""
        async with get_connection() as conn:
            projects = await conn.fetch(
                """
                SELECT id, name, total_tokens, total_cost
                FROM projects
                ORDER BY total_tokens DESC NULLS LAST
                """
            )

            stats_list = []
            for project in projects:
                stats = await self.get_project_stats(str(project["id"]))
                stats_list.append(stats)

            return stats_list

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
        start_date = datetime.now() - timedelta(days=days)

        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    DATE(created_at) as date,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(input_tokens), 0) as input_tokens,
                    COALESCE(SUM(output_tokens), 0) as output_tokens,
                    COALESCE(SUM(estimated_cost), 0) as cost,
                    COUNT(*) as record_count
                FROM token_usage
                WHERE project_id = $1 AND created_at >= $2
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                """,
                project_id,
                start_date,
            )

            return [
                DailyTokenStats(
                    date=str(row["date"]),
                    total_tokens=row["total_tokens"] or 0,
                    input_tokens=row["input_tokens"] or 0,
                    output_tokens=row["output_tokens"] or 0,
                    cost=float(row["cost"] or 0),
                    record_count=row["record_count"] or 0,
                )
                for row in rows
            ]


# 全局实例
token_tracker = TokenTracker()
