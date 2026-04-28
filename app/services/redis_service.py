"""
Redis 热协调服务
用于运行中操作锁、租约与短期幂等缓存。Redis 不作为事实源；不可用时返回 no-op 结果。
"""

import json
import logging
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """Redis 客户端封装，支持禁用/不可用时降级。"""

    def __init__(self, redis_url: Optional[str] = None, enabled: Optional[bool] = None):
        self.redis_url = redis_url or settings.redis_url
        self.enabled = settings.redis_enabled if enabled is None else enabled
        self._client: Any = None
        self._available = False

    @property
    def available(self) -> bool:
        return self.enabled and self._available and self._client is not None

    async def connect(self) -> None:
        if not self.enabled:
            logger.info("Redis 已禁用，使用 Postgres 幂等兜底")
            return
        try:
            from redis.asyncio import Redis

            self._client = Redis.from_url(self.redis_url, decode_responses=True)
            await self._client.ping()
            self._available = True
            logger.info("Redis 连接已建立")
        except Exception as exc:
            self._client = None
            self._available = False
            logger.warning(f"Redis 不可用，回退到 Postgres 幂等: {exc}")

    async def disconnect(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as exc:
                logger.warning(f"关闭 Redis 连接失败: {exc}")
        self._client = None
        self._available = False

    async def get(self, key: str) -> Optional[str]:
        if not self.available:
            return None
        try:
            return await self._client.get(key)
        except Exception as exc:
            self._mark_unavailable(exc)
            return None

    async def get_json(self, key: str) -> Optional[Any]:
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        if not self.available:
            return False
        try:
            result = await self._client.set(key, value, ex=ttl_seconds, nx=nx)
            return bool(result)
        except Exception as exc:
            self._mark_unavailable(exc)
            return False

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        return await self.set(key, json.dumps(value, default=str), ttl_seconds=ttl_seconds, nx=nx)

    async def delete(self, key: str) -> bool:
        if not self.available:
            return False
        try:
            return bool(await self._client.delete(key))
        except Exception as exc:
            self._mark_unavailable(exc)
            return False

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        if not self.available:
            return False
        try:
            return bool(await self._client.expire(key, ttl_seconds))
        except Exception as exc:
            self._mark_unavailable(exc)
            return False

    async def acquire_lock(self, key: str, token: str, ttl_seconds: int) -> bool:
        return await self.set(key, token, ttl_seconds=ttl_seconds, nx=True)

    async def release_lock(self, key: str, token: str) -> bool:
        if not self.available:
            return False
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        try:
            return bool(await self._client.eval(script, 1, key, token))
        except Exception as exc:
            self._mark_unavailable(exc)
            return False

    def _mark_unavailable(self, exc: Exception) -> None:
        self._available = False
        logger.warning(f"Redis 操作失败，后续回退 Postgres: {exc}")


redis_service = RedisService()
