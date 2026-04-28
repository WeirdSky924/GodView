"""关系图投影后台 worker。"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class GraphProjectionPayloadError(ValueError):
    """投影 payload 不可处理。"""


class GraphProjectionWorker:
    """消费 Postgres outbox 并投影到 NebulaGraph。"""

    def __init__(
        self,
        postgres_db: Any,
        nebula_db: Any,
        worker_id: Optional[str] = None,
    ):
        self.postgres_db = postgres_db
        self.nebula_db = nebula_db
        self.worker_id = worker_id or f"graph_projection_worker_{uuid.uuid4().hex[:12]}"
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """启动后台 worker。"""
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self.run())
        logger.info(f"关系图投影 worker 已启动: {self.worker_id}")

    async def stop(self) -> None:
        """停止后台 worker。"""
        self._running = False
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        logger.info(f"关系图投影 worker 已停止: {self.worker_id}")

    async def run(self) -> None:
        """持续轮询并消费 outbox。"""
        try:
            while self._running:
                try:
                    processed = await self.poll_once()
                    if processed == 0:
                        await asyncio.sleep(settings.graph_projection_poll_interval_seconds)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"关系图投影 worker 轮询失败: {e}")
                    await asyncio.sleep(settings.graph_projection_poll_interval_seconds)
        except asyncio.CancelledError:
            logger.info(f"关系图投影 worker 循环取消: {self.worker_id}")
            raise

    async def poll_once(self) -> int:
        """领取并处理一批任务，返回领取数量。"""
        if not self.postgres_db:
            return 0
        jobs = await self.postgres_db.claim_graph_projection_jobs(
            worker_id=self.worker_id,
            limit=settings.graph_projection_batch_size,
            lease_seconds=settings.graph_projection_lease_seconds,
        )
        for job in jobs:
            await self.process_job(job)
        return len(jobs)

    async def process_job(self, job: Dict[str, Any]) -> None:
        """处理单个投影任务。"""
        job_id = str(job.get("id") or "")
        try:
            if not self.nebula_db:
                raise RuntimeError("NebulaGraph 未连接")
            payload = job.get("payload") or {}
            source_entity_type = job.get("source_entity_type")
            if source_entity_type == "character":
                await self._project_character(payload)
            elif source_entity_type == "world":
                await self._project_world(payload)
            elif source_entity_type == "region":
                await self._project_region(payload)
            elif source_entity_type == "hook":
                await self._project_hook(payload)
            else:
                raise GraphProjectionPayloadError(f"不支持的关系图投影实体类型: {source_entity_type}")
            await self.postgres_db.mark_graph_projection_job_completed(job_id, self.worker_id)
        except GraphProjectionPayloadError as e:
            await self.postgres_db.mark_graph_projection_job_failed(job_id, self.worker_id, str(e))
        except Exception as e:
            await self._handle_retry(job, str(e))

    async def _handle_retry(self, job: Dict[str, Any], error: str) -> None:
        job_id = str(job.get("id") or "")
        attempt_count = int(job.get("attempt_count") or 0)
        if attempt_count + 1 >= settings.graph_projection_retry_limit:
            await self.postgres_db.mark_graph_projection_job_failed(job_id, self.worker_id, error)
            return
        retry_in_seconds = min(
            settings.graph_projection_retry_base_seconds * (2 ** attempt_count),
            300,
        )
        await self.postgres_db.mark_graph_projection_job_retry(
            job_id,
            self.worker_id,
            error,
            retry_in_seconds,
        )

    async def _project_character(self, payload: Dict[str, Any]) -> None:
        character = payload.get("character") or payload
        character_id = str(character.get("id") or "")
        if not character_id:
            raise GraphProjectionPayloadError("角色投影缺少 id")

        await self._require_graph_write(await self.nebula_db.upsert_vertex(
            "character",
            character_id,
            {
                "name": character.get("name", ""),
                "description": character.get("description") or character.get("background_story") or "",
                "role": character.get("role") or "supporting",
                "status": character.get("status") or "active",
                "personality_traits": character.get("personality_traits") or [],
                "created_at": character.get("created_at") or datetime.utcnow(),
                "updated_at": character.get("updated_at") or datetime.utcnow(),
            },
        ))

        world_id = character.get("world_id")
        if world_id:
            await self._require_graph_write(await self.nebula_db.upsert_edge(
                "belongs_to",
                character_id,
                str(world_id),
                {"since": datetime.utcnow()},
            ))

        current_region_id = character.get("current_region_id")
        if current_region_id:
            await self._require_graph_write(await self.nebula_db.upsert_edge(
                "located_in",
                character_id,
                str(current_region_id),
                {"since": datetime.utcnow()},
            ))

        key_relationships = character.get("key_relationships") or {}
        if isinstance(key_relationships, dict):
            for related_character_id, relationship_type in key_relationships.items():
                if related_character_id:
                    await self._require_graph_write(await self.nebula_db.upsert_edge(
                        "knows",
                        character_id,
                        str(related_character_id),
                        {
                            "relationship_type": str(relationship_type or "related"),
                            "strength": 0.5,
                            "since": datetime.utcnow(),
                        },
                    ))

    async def _project_world(self, payload: Dict[str, Any]) -> None:
        world = payload.get("world") or payload
        world_id = str(world.get("id") or "")
        if not world_id:
            raise GraphProjectionPayloadError("世界投影缺少 id")
        await self._require_graph_write(await self.nebula_db.upsert_vertex(
            "world",
            world_id,
            {
                "name": world.get("name", ""),
                "world_type": world.get("world_type") or "fantasy",
                "description": world.get("description") or "",
                "created_at": world.get("created_at") or datetime.utcnow(),
            },
        ))

    async def _project_region(self, payload: Dict[str, Any]) -> None:
        region = payload.get("region") or payload
        region_id = str(region.get("id") or "")
        if not region_id:
            raise GraphProjectionPayloadError("区域投影缺少 id")
        await self._require_graph_write(await self.nebula_db.upsert_vertex(
            "region",
            region_id,
            {
                "name": region.get("name", ""),
                "region_type": region.get("region_type") or region.get("terrain_type") or "custom",
                "description": region.get("description") or "",
                "world_id": str(region.get("world_id") or ""),
            },
        ))
        world_id = region.get("world_id")
        if world_id:
            await self._require_graph_write(await self.nebula_db.upsert_edge(
                "belongs_to",
                region_id,
                str(world_id),
                {"since": datetime.utcnow()},
            ))

    async def _project_hook(self, payload: Dict[str, Any]) -> None:
        hook = payload.get("hook") or payload
        hook_id = str(hook.get("id") or "")
        if not hook_id:
            raise GraphProjectionPayloadError("伏笔投影缺少 id")
        await self._require_graph_write(await self.nebula_db.upsert_vertex(
            "hook",
            hook_id,
            {
                "title": hook.get("title") or hook.get("name") or "",
                "hook_type": hook.get("hook_type") or hook.get("type") or "custom",
                "status": hook.get("status") or "planted",
                "priority": int(hook.get("priority") or 1),
                "created_at": hook.get("created_at") or datetime.utcnow(),
            },
        ))

        for character_id in hook.get("related_characters") or []:
            await self._require_graph_write(await self.nebula_db.upsert_edge(
                "involves_character",
                hook_id,
                str(character_id),
                {"role": "related"},
            ))
        for region_id in hook.get("related_locations") or []:
            await self._require_graph_write(await self.nebula_db.upsert_edge(
                "involves_location",
                hook_id,
                str(region_id),
                {"context": "related"},
            ))

    async def _require_graph_write(self, success: bool) -> None:
        if not success:
            raise RuntimeError("NebulaGraph 写入返回失败")
