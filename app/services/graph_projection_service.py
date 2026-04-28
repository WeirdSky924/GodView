"""
关系图投影服务。

第一阶段只负责把业务实体变化写入 Postgres outbox，不直接写 NebulaGraph。
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_graph_projection_service: Optional["GraphProjectionService"] = None


def set_graph_projection_service(service: Optional["GraphProjectionService"]) -> None:
    """设置全局关系图投影服务实例。"""
    global _graph_projection_service
    _graph_projection_service = service


def get_graph_projection_service() -> Optional["GraphProjectionService"]:
    """获取全局关系图投影服务实例。"""
    return _graph_projection_service


async def enqueue_graph_projection_best_effort(
    entity_type: str,
    data: Dict[str, Any],
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """以 best-effort 方式入队关系图投影任务。"""
    service = get_graph_projection_service()
    if not service:
        return {"status": "skipped", "reason": "service_unavailable"}
    return await service.enqueue_best_effort(entity_type, data, request_id=request_id)


class GraphProjectionService:
    """关系图投影 outbox 入队服务。"""

    def __init__(self, postgres_db: Any):
        self.postgres_db = postgres_db

    @staticmethod
    def _content_hash(payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _projection_scope(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "world_id": data.get("world_id"),
            "scope_type": data.get("scope_type"),
            "parent_world_id": data.get("parent_world_id"),
        }

    @staticmethod
    def _scope_key(payload: Dict[str, Any]) -> str:
        scope = payload.get("projection_scope") or {}
        world_id = scope.get("world_id")
        scope_type = scope.get("scope_type")
        if world_id:
            return f"world:{world_id}"
        if scope_type:
            return f"scope:{scope_type}"
        return "project"

    async def enqueue_projection_job(
        self,
        *,
        project_id: Optional[str],
        source_entity_type: str,
        source_entity_id: str,
        projection_type: str,
        payload: Dict[str, Any],
        operation: str = "upsert",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """将实体投影任务写入 graph_projection_jobs。"""
        if not settings.graph_projection_enabled:
            return {"status": "skipped", "reason": "disabled"}
        if not settings.graph_projection_outbox_enabled:
            return {"status": "skipped", "reason": "outbox_disabled"}
        if not self.postgres_db:
            logger.warning("关系图投影任务入队失败: PostgreSQL 未连接")
            return {"status": "failed", "reason": "postgres_unavailable"}
        if not source_entity_id:
            logger.warning("关系图投影任务入队失败: source_entity_id 为空")
            return {"status": "failed", "reason": "missing_source_entity_id"}

        job_payload = dict(payload or {})
        scope_key = self._scope_key(job_payload)
        idempotency_key = f"{source_entity_type}:{source_entity_id}:{scope_key}:{projection_type}:{operation}"
        if request_id:
            job_payload.setdefault("request_id", request_id)
        content_hash = self._content_hash(job_payload)

        try:
            job_id = await self.postgres_db.upsert_graph_projection_job(
                {
                    "idempotency_key": idempotency_key,
                    "project_id": project_id,
                    "source_entity_type": source_entity_type,
                    "source_entity_id": source_entity_id,
                    "projection_type": projection_type,
                    "operation": operation,
                    "payload": job_payload,
                    "content_hash": content_hash,
                    "status": "queued",
                }
            )
            return {
                "status": "queued",
                "job_id": job_id,
                "idempotency_key": idempotency_key,
                "content_hash": content_hash,
            }
        except Exception as e:
            logger.warning(f"关系图投影任务入队失败: {e}")
            return {"status": "failed", "reason": str(e)}

    async def enqueue_best_effort(
        self,
        entity_type: str,
        data: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """以 best-effort 方式入队实体投影，绝不向调用方抛异常。"""
        try:
            if entity_type == "character":
                return await self.enqueue_character_projection(data, request_id=request_id)
            if entity_type == "world":
                return await self.enqueue_world_projection(data, request_id=request_id)
            if entity_type == "region":
                return await self.enqueue_region_projection(data, request_id=request_id)
            if entity_type == "hook":
                return await self.enqueue_hook_projection(data, request_id=request_id)
            return {"status": "failed", "reason": f"unsupported_entity_type:{entity_type}"}
        except Exception as e:
            logger.warning(f"关系图投影 best-effort 入队失败: {e}")
            return {"status": "failed", "reason": str(e)}

    async def enqueue_character_projection(
        self,
        character_data: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """入队角色关系图投影任务。"""
        character_id = str(character_data.get("id") or "")
        project_id = character_data.get("project_id")
        payload = {
            "character": character_data,
            "projection_schema_version": 2,
            "projection_scope": self._projection_scope(character_data),
        }
        return await self.enqueue_projection_job(
            project_id=project_id,
            source_entity_type="character",
            source_entity_id=character_id,
            projection_type="character_profile",
            operation="upsert",
            payload=payload,
            request_id=request_id,
        )

    async def enqueue_world_projection(
        self,
        world_data: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """入队世界关系图投影任务。"""
        world_id = str(world_data.get("id") or "")
        return await self.enqueue_projection_job(
            project_id=world_data.get("project_id"),
            source_entity_type="world",
            source_entity_id=world_id,
            projection_type="world_profile",
            operation="upsert",
            payload={
                "world": world_data,
                "projection_schema_version": 2,
                "projection_scope": self._projection_scope(world_data),
            },
            request_id=request_id,
        )

    async def enqueue_region_projection(
        self,
        region_data: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """入队区域关系图投影任务。"""
        region_id = str(region_data.get("id") or "")
        return await self.enqueue_projection_job(
            project_id=region_data.get("project_id"),
            source_entity_type="region",
            source_entity_id=region_id,
            projection_type="region_profile",
            operation="upsert",
            payload={
                "region": region_data,
                "projection_schema_version": 2,
                "projection_scope": self._projection_scope(region_data),
            },
            request_id=request_id,
        )

    async def enqueue_hook_projection(
        self,
        hook_data: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """入队伏笔关系图投影任务。"""
        hook_id = str(hook_data.get("id") or "")
        return await self.enqueue_projection_job(
            project_id=hook_data.get("project_id"),
            source_entity_type="hook",
            source_entity_id=hook_id,
            projection_type="hook_profile",
            operation="upsert",
            payload={
                "hook": hook_data,
                "projection_schema_version": 2,
                "projection_scope": self._projection_scope(hook_data),
            },
            request_id=request_id,
        )
