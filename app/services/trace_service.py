"""
业务级执行 Trace 服务。
Trace 是观测层：所有写入均 best-effort，失败只记录 warning，不中断主流程。
"""

import hashlib
import json
import logging
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_current_trace_id: ContextVar[Optional[str]] = ContextVar("current_trace_id", default=None)
_current_span_id: ContextVar[Optional[str]] = ContextVar("current_span_id", default=None)

_SECRET_KEYWORDS = ("api_key", "apikey", "password", "authorization", "secret", "token", "credential")
_LARGE_SKIP_KEYS = ("embedding", "embeddings", "vector", "vectors", "raw_properties", "properties")


class TraceService:
    """封装 trace/span/event/artifact 写入和上下文传播。"""

    def __init__(self, db=None):
        self.db = db

    @property
    def enabled(self) -> bool:
        return bool(settings.trace_enabled and self.db)

    @staticmethod
    def current_trace_id() -> Optional[str]:
        return _current_trace_id.get()

    @staticmethod
    def current_span_id() -> Optional[str]:
        return _current_span_id.get()

    @staticmethod
    def set_context(trace_id: Optional[str], span_id: Optional[str] = None):
        trace_token = _current_trace_id.set(trace_id)
        span_token = _current_span_id.set(span_id)
        return trace_token, span_token

    @staticmethod
    def reset_context(tokens) -> None:
        trace_token, span_token = tokens
        _current_trace_id.reset(trace_token)
        _current_span_id.reset(span_token)

    async def start_trace(
        self,
        trace_type: str,
        root_name: Optional[str] = None,
        project_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        workflow_execution_id: Optional[str] = None,
        root_input_summary: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        trace_id = trace_id or str(uuid.uuid4())
        if not self.enabled:
            return trace_id
        await self.db.create_execution_trace(
            {
                "id": trace_id,
                "project_id": project_id,
                "operation_id": operation_id,
                "request_id": request_id,
                "workflow_id": workflow_id,
                "workflow_execution_id": workflow_execution_id,
                "trace_type": trace_type,
                "root_name": root_name,
                "status": "running",
                "root_input_summary": self.sanitize(root_input_summary or {}),
                "metadata": self.sanitize(metadata or {}),
                "started_at": datetime.now(),
            }
        )
        return trace_id

    async def finish_trace(self, trace_id: Optional[str], status: str, error: Optional[str] = None) -> None:
        if not self.enabled or not trace_id:
            return
        await self.db.finish_execution_trace(trace_id, status, error=error)

    @asynccontextmanager
    async def span(
        self,
        name: str,
        kind: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AsyncIterator[Optional[str]]:
        trace_id = trace_id or self.current_trace_id()
        parent_span_id = parent_span_id if parent_span_id is not None else self.current_span_id()
        span_id = str(uuid.uuid4()) if trace_id else None
        if self.enabled and trace_id and span_id:
            await self.db.create_trace_span(
                {
                    "id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "name": name,
                    "kind": kind,
                    "status": "running",
                    "attributes": self.sanitize(attributes or {}),
                }
            )
        tokens = self.set_context(trace_id, span_id)
        try:
            yield span_id
        except Exception as e:
            if self.enabled and span_id:
                await self.db.finish_trace_span(span_id, "failed", error=str(e))
            raise
        else:
            if self.enabled and span_id:
                await self.db.finish_trace_span(span_id, "completed")
        finally:
            self.reset_context(tokens)

    async def record_event(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
    ) -> None:
        trace_id = trace_id or self.current_trace_id()
        span_id = span_id if span_id is not None else self.current_span_id()
        if not self.enabled or not trace_id:
            return
        await self.db.append_trace_event(
            {
                "trace_id": trace_id,
                "span_id": span_id,
                "event_type": event_type,
                "severity": severity,
                "payload": self.sanitize(payload or {}),
            }
        )

    async def record_artifact(
        self,
        kind: str,
        content: Any = None,
        text_content: Optional[str] = None,
        content_type: str = "json",
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
    ) -> None:
        trace_id = trace_id or self.current_trace_id()
        span_id = span_id if span_id is not None else self.current_span_id()
        if not self.enabled or not trace_id:
            return

        redaction_status = "none"
        sanitized_content = None
        sanitized_text = text_content
        if content is not None:
            sanitized_content = self.sanitize(content)
            redaction_status = "redacted" if sanitized_content != content else "none"
        if sanitized_text is not None:
            sanitized_text = self._truncate_string(str(sanitized_text))

        raw = sanitized_text if sanitized_text is not None else json.dumps(sanitized_content, ensure_ascii=False, default=str)
        content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else None
        await self.db.save_trace_artifact(
            {
                "trace_id": trace_id,
                "span_id": span_id,
                "kind": kind,
                "content_type": content_type,
                "content": sanitized_content,
                "text_content": sanitized_text,
                "content_hash": content_hash,
                "size_bytes": len(raw.encode("utf-8")) if raw else 0,
                "redaction_status": redaction_status,
            }
        )

    def sanitize(self, value: Any, *, key: Optional[str] = None) -> Any:
        """脱敏并裁剪可写入 trace 的数据。"""
        if not settings.trace_redact_secrets:
            return self._truncate(value)

        key_lower = (key or "").lower()
        if any(word in key_lower for word in _SECRET_KEYWORDS):
            return "[REDACTED]"
        if any(word == key_lower or key_lower.endswith(f"_{word}") for word in _LARGE_SKIP_KEYS):
            return "[OMITTED]"

        if isinstance(value, dict):
            return {str(k): self.sanitize(v, key=str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [self.sanitize(item, key=key) for item in value[:100]]
        return self._truncate(value)

    def _truncate(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._truncate_string(value)
        return value

    def _truncate_string(self, value: str) -> str:
        max_chars = max(1000, int(settings.trace_max_artifact_chars or 50000))
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + f"\n...[truncated {len(value) - max_chars} chars]"


def get_trace_service(db=None) -> TraceService:
    if db is None:
        try:
            from app.api.app import postgres_db
            db = postgres_db
        except Exception:
            db = None
    return TraceService(db=db)
