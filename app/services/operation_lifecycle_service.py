"""
操作生命周期与幂等服务
Postgres 是事实源；Redis 仅用于热锁、租约和短期结果缓存。
"""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.config import settings
from app.database.postgres import PostgresDatabase
from app.services.redis_service import RedisService, redis_service

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_STATUSES = {"pending", "running", "paused"}


@dataclass
class OperationBeginResult:
    operation: Dict[str, Any]
    replayed: bool = False
    deduplicated: bool = False
    lock_token: Optional[str] = None


class OperationLifecycleService:
    """统一封装长任务/副作用操作的 request_id、hash、状态和租约。"""

    def __init__(self, db: PostgresDatabase, redis: Optional[RedisService] = None):
        self.db = db
        self.redis = redis or redis_service

    @staticmethod
    def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """递归规范化请求体，避免字段顺序影响 request_hash。"""
        def normalize(value: Any) -> Any:
            if isinstance(value, dict):
                return {str(k): normalize(value[k]) for k in sorted(value.keys(), key=str)}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, datetime):
                return value.isoformat()
            return value

        return normalize(payload or {})

    @classmethod
    def build_request_hash(cls, payload: Dict[str, Any]) -> str:
        normalized = cls.normalize_payload(payload)
        raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def begin_or_replay(
        self,
        operation_type: str,
        project_id: Optional[str],
        resource_type: Optional[str],
        resource_id: Optional[str],
        request_payload: Dict[str, Any],
        request_id: Optional[str] = None,
        force_new: bool = False,
    ) -> OperationBeginResult:
        """开始操作；同 request_id 回放，同活跃语义 hash 去重。"""
        request_id = request_id or f"req_{uuid.uuid4().hex}"
        request_hash = self.build_request_hash(request_payload)
        cached = await self.redis.get_json(self._operation_cache_key(request_id))
        if cached and not force_new:
            return OperationBeginResult(operation=cached, replayed=cached.get("status") in TERMINAL_STATUSES)

        existing = await self.db.get_operation_request_by_request_id(request_id)
        if existing and not force_new:
            await self.redis.set_json(
                self._operation_cache_key(request_id),
                existing,
                ttl_seconds=settings.operation_cache_ttl_seconds,
            )
            return OperationBeginResult(
                operation=existing,
                replayed=existing.get("status") in TERMINAL_STATUSES,
                deduplicated=existing.get("status") in ACTIVE_STATUSES,
            )

        if not force_new and project_id:
            active = await self.db.get_active_operation_request(
                operation_type=operation_type,
                project_id=project_id,
                resource_id=resource_id,
                request_hash=request_hash,
            )
            if active:
                return OperationBeginResult(operation=active, deduplicated=True)

        lock_token = uuid.uuid4().hex
        await self.redis.acquire_lock(
            self._semantic_lock_key(operation_type, project_id, resource_id, request_hash),
            lock_token,
            settings.operation_lease_ttl_seconds,
        )
        operation_id = await self.db.save_operation_request(
            {
                "request_id": request_id,
                "operation_type": operation_type,
                "project_id": project_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "request_hash": request_hash,
                "status": "pending",
                "response_payload": {},
                "lease_token": lock_token,
                "lease_expires_at": datetime.now() + timedelta(seconds=settings.operation_lease_ttl_seconds),
                "last_heartbeat_at": datetime.now(),
            }
        )
        operation = await self.db.get_operation_request_by_request_id(request_id) or {
            "id": operation_id,
            "request_id": request_id,
            "operation_type": operation_type,
            "project_id": project_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "request_hash": request_hash,
            "status": "pending",
            "response_payload": {},
            "lease_token": lock_token,
        }
        await self.redis.set_json(
            self._operation_cache_key(request_id),
            operation,
            ttl_seconds=settings.operation_cache_ttl_seconds,
        )
        return OperationBeginResult(operation=operation, lock_token=lock_token)

    async def mark_running(self, operation: Dict[str, Any], response_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._update_operation(operation, "running", response_payload=response_payload)

    async def heartbeat(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        return await self._update_operation(operation, operation.get("status") or "running")

    async def complete(self, operation: Dict[str, Any], response_payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._update_operation(operation, "completed", response_payload=response_payload, completed=True)

    async def fail(self, operation: Dict[str, Any], error: str, response_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._update_operation(
            operation,
            "failed",
            response_payload=response_payload,
            error=error,
            completed=True,
        )

    async def cancel_requested(self, operation: Dict[str, Any], response_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._update_operation(
            operation,
            "cancelled",
            response_payload=response_payload,
            completed=True,
        )

    async def _update_operation(
        self,
        operation: Dict[str, Any],
        status: str,
        response_payload: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        completed: bool = False,
    ) -> Dict[str, Any]:
        now = datetime.now()
        data = dict(operation)
        data.update(
            {
                "status": status,
                "response_payload": response_payload if response_payload is not None else data.get("response_payload") or {},
                "error": error,
                "lease_expires_at": now + timedelta(seconds=settings.operation_lease_ttl_seconds),
                "last_heartbeat_at": now,
                "completed_at": now if completed else data.get("completed_at"),
            }
        )
        operation_id = await self.db.save_operation_request(data)
        data["id"] = operation_id or data.get("id")
        await self.redis.set_json(
            self._operation_cache_key(data["request_id"]),
            data,
            ttl_seconds=settings.operation_cache_ttl_seconds,
        )
        if completed:
            await self.redis.release_lock(
                self._semantic_lock_key(
                    data.get("operation_type"),
                    data.get("project_id"),
                    data.get("resource_id"),
                    data.get("request_hash"),
                ),
                data.get("lease_token") or "",
            )
        else:
            await self.redis.expire(
                self._semantic_lock_key(
                    data.get("operation_type"),
                    data.get("project_id"),
                    data.get("resource_id"),
                    data.get("request_hash"),
                ),
                settings.operation_lease_ttl_seconds,
            )
        return data

    @staticmethod
    def _operation_cache_key(request_id: str) -> str:
        return f"operation:request:{request_id}"

    @staticmethod
    def _semantic_lock_key(
        operation_type: Optional[str],
        project_id: Optional[str],
        resource_id: Optional[str],
        request_hash: Optional[str],
    ) -> str:
        return f"operation:lock:{operation_type or ''}:{project_id or ''}:{resource_id or ''}:{request_hash or ''}"


def create_operation_lifecycle_service(db: PostgresDatabase) -> OperationLifecycleService:
    return OperationLifecycleService(db=db, redis=redis_service)
