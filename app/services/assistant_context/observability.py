"""Trace observability hooks for Assistant Context Fabric."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class AssistantContextObservability:
    async def record_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        try:
            from app.services.trace_service import get_trace_service

            trace_service = get_trace_service()
            await trace_service.record_event(event_name, payload)
        except Exception as exc:
            logger.debug("assistant context trace event skipped: %s", exc)

    async def record_packet_built(self, packet_id: str, metadata: Dict[str, Any]) -> None:
        await self.record_event("assistant_context.packet.built", {"packet_id": packet_id, **metadata})

    async def record_history_reset(self, payload: Dict[str, Any]) -> None:
        await self.record_event("assistant_context.history.reset", payload)

    async def record_force_reread(self, payload: Dict[str, Any]) -> None:
        await self.record_event("assistant_context.force_reread.completed", payload)
