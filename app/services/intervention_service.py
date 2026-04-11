"""
干预日志服务
v8 Agent协作可视化工作台
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.intervention import (
    InterventionLog,
    InterventionCreate,
    InterventionQuery,
    InterventionSummary,
    InterventionType,
    InterventionExportFormat,
)

logger = logging.getLogger(__name__)


class InterventionService:
    """干预日志服务 - 管理干预记录的存储和查询"""

    def __init__(self):
        # 内存缓存
        self._logs: Dict[str, InterventionLog] = {}
        # 按执行ID索引
        self._by_execution: Dict[str, List[str]] = {}
        # 按项目ID索引
        self._by_project: Dict[str, List[str]] = {}

    async def log_intervention(
        self,
        intervention: InterventionLog,
        db=None,
    ) -> str:
        """
        记录干预日志

        Args:
            intervention: 干预日志对象
            db: 数据库连接

        Returns:
            str: 干预日志ID
        """
        # 保存到内存
        self._logs[intervention.id] = intervention

        # 更新索引
        exec_id = intervention.workflow_execution_id
        proj_id = intervention.project_id

        if exec_id not in self._by_execution:
            self._by_execution[exec_id] = []
        self._by_execution[exec_id].append(intervention.id)

        if proj_id not in self._by_project:
            self._by_project[proj_id] = []
        self._by_project[proj_id].append(intervention.id)

        # 保存到数据库
        if db:
            await self._save_intervention_to_db(intervention, db)

        logger.info(f"记录干预日志: {intervention.id}, Agent: {intervention.agent_type}")
        return intervention.id

    async def get_intervention(
        self,
        intervention_id: str,
        db=None,
    ) -> Optional[InterventionLog]:
        """获取单个干预日志"""
        # 先查内存
        if intervention_id in self._logs:
            return self._logs[intervention_id]

        # 查数据库
        if db:
            log = await self._load_intervention_from_db(intervention_id, db)
            if log:
                self._logs[intervention_id] = log
            return log

        return None

    async def get_intervention_logs(
        self,
        query: InterventionQuery,
        db=None,
    ) -> List[InterventionLog]:
        """
        查询干预日志

        Args:
            query: 查询条件
            db: 数据库连接

        Returns:
            List[InterventionLog]: 干预日志列表
        """
        if db:
            return await self._query_interventions_from_db(query, db)

        # 内存查询
        results = []

        # 确定搜索范围
        if query.workflow_execution_id:
            ids = self._by_execution.get(query.workflow_execution_id, [])
        elif query.project_id:
            ids = self._by_project.get(query.project_id, [])
        else:
            ids = list(self._logs.keys())

        # 过滤
        for log_id in ids:
            log = self._logs.get(log_id)
            if not log:
                continue

            # Agent 类型过滤
            if query.agent_type and log.agent_type != query.agent_type:
                continue

            # 干预类型过滤
            if query.intervention_type and log.intervention_type != query.intervention_type:
                continue

            # 时间范围过滤
            if query.start_time and log.timestamp < query.start_time:
                continue
            if query.end_time and log.timestamp > query.end_time:
                continue

            # 关键词搜索
            if query.keyword:
                keyword_lower = query.keyword.lower()
                if keyword_lower not in log.user_message.lower():
                    if not log.agent_response or keyword_lower not in log.agent_response.lower():
                        continue

            results.append(log)

        # 排序（最新优先）
        results.sort(key=lambda x: x.timestamp, reverse=True)

        # 分页
        return results[query.offset:query.offset + query.limit]

    async def get_interventions_by_execution(
        self,
        execution_id: str,
        db=None,
    ) -> List[InterventionLog]:
        """获取某次执行的所有干预日志"""
        query = InterventionQuery(workflow_execution_id=execution_id, limit=1000)
        return await self.get_intervention_logs(query, db)

    async def get_intervention_summary(
        self,
        project_id: str,
        execution_id: Optional[str] = None,
        db=None,
    ) -> InterventionSummary:
        """获取干预摘要统计"""
        query = InterventionQuery(
            project_id=project_id,
            workflow_execution_id=execution_id,
            limit=1000,
        )
        logs = await self.get_intervention_logs(query, db)

        # 统计
        by_agent: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        total_response_time = 0
        response_count = 0

        for log in logs:
            # 按 Agent 统计
            if log.agent_type not in by_agent:
                by_agent[log.agent_type] = 0
            by_agent[log.agent_type] += 1

            # 按类型统计
            type_key = log.intervention_type.value
            if type_key not in by_type:
                by_type[type_key] = 0
            by_type[type_key] += 1

            # 响应时间
            if log.response_time_ms:
                total_response_time += log.response_time_ms
                response_count += 1

        avg_response_time = total_response_time / response_count if response_count > 0 else None

        return InterventionSummary(
            total_count=len(logs),
            by_agent_type=by_agent,
            by_intervention_type=by_type,
            avg_response_time_ms=avg_response_time,
            recent_interventions=logs[:5],
        )

    async def export_logs(
        self,
        project_id: str,
        execution_id: Optional[str] = None,
        format: InterventionExportFormat = InterventionExportFormat.JSON,
        include_context: bool = False,
        db=None,
    ) -> str:
        """
        导出干预日志

        Args:
            project_id: 项目ID
            execution_id: 执行ID（可选）
            format: 导出格式
            include_context: 是否包含上下文快照
            db: 数据库连接

        Returns:
            str: 导出的内容
        """
        query = InterventionQuery(
            project_id=project_id,
            workflow_execution_id=execution_id,
            limit=10000,
        )
        logs = await self.get_intervention_logs(query, db)

        if format == InterventionExportFormat.JSON:
            return self._export_json(logs, include_context)
        elif format == InterventionExportFormat.CSV:
            return self._export_csv(logs, include_context)
        elif format == InterventionExportFormat.MARKDOWN:
            return self._export_markdown(logs, include_context)

        return ""

    def _export_json(self, logs: List[InterventionLog], include_context: bool) -> str:
        """导出为 JSON"""
        data = []
        for log in logs:
            item = {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "agent_type": log.agent_type,
                "agent_name": log.agent_name,
                "intervention_type": log.intervention_type.value,
                "user_message": log.user_message,
                "agent_response": log.agent_response,
                "response_time_ms": log.response_time_ms,
            }
            if include_context:
                item["context_snapshot"] = log.context_snapshot
            data.append(item)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _export_csv(self, logs: List[InterventionLog], include_context: bool) -> str:
        """导出为 CSV"""
        output = io.StringIO()
        fieldnames = [
            "id", "timestamp", "agent_type", "agent_name",
            "intervention_type", "user_message", "agent_response",
            "response_time_ms"
        ]
        if include_context:
            fieldnames.append("context_snapshot")

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for log in logs:
            row = {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "agent_type": log.agent_type,
                "agent_name": log.agent_name,
                "intervention_type": log.intervention_type.value,
                "user_message": log.user_message,
                "agent_response": log.agent_response or "",
                "response_time_ms": log.response_time_ms or "",
            }
            if include_context:
                row["context_snapshot"] = json.dumps(log.context_snapshot, ensure_ascii=False)
            writer.writerow(row)

        return output.getvalue()

    def _export_markdown(self, logs: List[InterventionLog], include_context: bool) -> str:
        """导出为 Markdown"""
        lines = [
            "# 干预日志导出",
            f"\n导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"总记录数: {len(logs)}\n",
        ]

        for i, log in enumerate(logs, 1):
            lines.extend([
                f"## {i}. {log.agent_name} ({log.agent_type})",
                f"- **时间**: {log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                f"- **类型**: {log.intervention_type.value}",
                f"- **用户消息**: {log.user_message}",
                f"- **Agent响应**: {log.agent_response or '(无响应)'}",
            ])
            if log.response_time_ms:
                lines.append(f"- **响应时间**: {log.response_time_ms}ms")
            if include_context and log.context_snapshot:
                lines.append(f"- **上下文**: ```json\n{json.dumps(log.context_snapshot, ensure_ascii=False, indent=2)}\n```")
            lines.append("")

        return "\n".join(lines)

    async def delete_intervention(
        self,
        intervention_id: str,
        db=None,
    ) -> bool:
        """
        删除单个干预日志

        Args:
            intervention_id: 干预日志ID
            db: 数据库连接

        Returns:
            bool: 是否删除成功
        """
        # 从内存删除
        log = self._logs.get(intervention_id)
        if log:
            # 从执行索引删除
            exec_id = log.workflow_execution_id
            if exec_id in self._by_execution:
                self._by_execution[exec_id] = [
                    x for x in self._by_execution[exec_id] if x != intervention_id
                ]

            # 从项目索引删除
            proj_id = log.project_id
            if proj_id in self._by_project:
                self._by_project[proj_id] = [
                    x for x in self._by_project[proj_id] if x != intervention_id
                ]

            del self._logs[intervention_id]

        # 从数据库删除
        if db:
            await self._delete_single_intervention_from_db(intervention_id, db)

        logger.info(f"删除干预日志: {intervention_id}")
        return True

    async def delete_interventions_by_execution(
        self,
        execution_id: str,
        db=None,
    ) -> int:
        """删除某次执行的所有干预日志"""
        ids_to_delete = self._by_execution.get(execution_id, [])

        # 从内存删除
        for log_id in ids_to_delete:
            if log_id in self._logs:
                log = self._logs[log_id]
                # 从项目索引删除
                if log.project_id in self._by_project:
                    self._by_project[log.project_id] = [
                        x for x in self._by_project[log.project_id] if x != log_id
                    ]
                del self._logs[log_id]

        # 从执行索引删除
        if execution_id in self._by_execution:
            del self._by_execution[execution_id]

        # 从数据库删除
        if db:
            await self._delete_interventions_from_db(execution_id, db)

        logger.info(f"删除干预日志: {execution_id}, 数量: {len(ids_to_delete)}")
        return len(ids_to_delete)

    # ==================== 数据库操作 ====================

    async def _save_intervention_to_db(self, log: InterventionLog, db):
        """保存干预日志到数据库"""
        query = """
        INSERT INTO intervention_logs (
            id, project_id, workflow_execution_id, node_id,
            agent_type, agent_name, intervention_type,
            user_message, agent_response, context_snapshot,
            timestamp, response_time_ms
        ) VALUES (
            :id, :project_id, :workflow_execution_id, :node_id,
            :agent_type, :agent_name, :intervention_type,
            :user_message, :agent_response, :context_snapshot,
            :timestamp, :response_time_ms
        )
        """
        params = {
            "id": log.id,
            "project_id": log.project_id,
            "workflow_execution_id": log.workflow_execution_id,
            "node_id": log.node_id,
            "agent_type": log.agent_type,
            "agent_name": log.agent_name,
            "intervention_type": log.intervention_type.value,
            "user_message": log.user_message,
            "agent_response": log.agent_response,
            "context_snapshot": json.dumps(log.context_snapshot, ensure_ascii=False),
            "timestamp": log.timestamp,
            "response_time_ms": log.response_time_ms,
        }
        await db.execute_write(query, params)

    async def _load_intervention_from_db(self, log_id: str, db) -> Optional[InterventionLog]:
        """从数据库加载干预日志"""
        query = "SELECT * FROM intervention_logs WHERE id = :id"
        results = await db.execute_query(query, {"id": log_id})
        if not results:
            return None

        row = results[0]
        return InterventionLog(
            id=row["id"],
            project_id=str(row["project_id"]),
            workflow_execution_id=row["workflow_execution_id"],
            node_id=row["node_id"],
            agent_type=row["agent_type"],
            agent_name=row["agent_name"],
            intervention_type=InterventionType(row["intervention_type"]),
            user_message=row["user_message"],
            agent_response=row["agent_response"],
            context_snapshot=json.loads(row["context_snapshot"]) if row["context_snapshot"] else {},
            timestamp=row["timestamp"],
            response_time_ms=row["response_time_ms"],
        )

    async def _query_interventions_from_db(
        self,
        query: InterventionQuery,
        db,
    ) -> List[InterventionLog]:
        """从数据库查询干预日志"""
        conditions = []
        params = {}

        if query.project_id:
            conditions.append("project_id = :project_id")
            params["project_id"] = query.project_id

        if query.workflow_execution_id:
            conditions.append("workflow_execution_id = :workflow_execution_id")
            params["workflow_execution_id"] = query.workflow_execution_id

        if query.agent_type:
            conditions.append("agent_type = :agent_type")
            params["agent_type"] = query.agent_type

        if query.intervention_type:
            conditions.append("intervention_type = :intervention_type")
            params["intervention_type"] = query.intervention_type.value

        if query.start_time:
            conditions.append("timestamp >= :start_time")
            params["start_time"] = query.start_time

        if query.end_time:
            conditions.append("timestamp <= :end_time")
            params["end_time"] = query.end_time

        if query.keyword:
            conditions.append("(user_message ILIKE :keyword OR agent_response ILIKE :keyword)")
            params["keyword"] = f"%{query.keyword}%"

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
        SELECT * FROM intervention_logs
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT :limit OFFSET :offset
        """
        params["limit"] = query.limit
        params["offset"] = query.offset

        results = await db.execute_query(sql, params)

        logs = []
        for row in results:
            logs.append(InterventionLog(
                id=row["id"],
                project_id=str(row["project_id"]),
                workflow_execution_id=row["workflow_execution_id"],
                node_id=row["node_id"],
                agent_type=row["agent_type"],
                agent_name=row["agent_name"],
                intervention_type=InterventionType(row["intervention_type"]),
                user_message=row["user_message"],
                agent_response=row["agent_response"],
                context_snapshot=json.loads(row["context_snapshot"]) if row["context_snapshot"] else {},
                timestamp=row["timestamp"],
                response_time_ms=row["response_time_ms"],
            ))

        return logs

    async def _delete_single_intervention_from_db(self, intervention_id: str, db):
        """从数据库删除单个干预日志"""
        query = "DELETE FROM intervention_logs WHERE id = :id"
        await db.execute_write(query, {"id": intervention_id})

    async def _delete_interventions_from_db(self, execution_id: str, db):
        """从数据库删除干预日志"""
        query = "DELETE FROM intervention_logs WHERE workflow_execution_id = :execution_id"
        await db.execute_write(query, {"execution_id": execution_id})


# 全局单例
_intervention_service: Optional[InterventionService] = None


def get_intervention_service() -> InterventionService:
    """获取干预日志服务单例"""
    global _intervention_service
    if _intervention_service is None:
        _intervention_service = InterventionService()
    return _intervention_service


def set_intervention_service(service: InterventionService):
    """设置干预日志服务实例"""
    global _intervention_service
    _intervention_service = service
