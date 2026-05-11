"""
设定 Agent 服务
v6 核心需求：持续设定管理、冲突检测、协商解决
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.models.agent_template import AgentType
from app.models.bootstrap import BootstrapSession, BootstrapStage, BootstrapMessage
from app.models.setting_agent import (
    SettingAgentMode,
    SettingAgentSession,
    SettingChangeRequest,
    SettingChangeType,
    SettingConflict,
    ConflictResolutionStatus,
    ConflictSeverity,
    LoreKnowledgeIndex,
    SettingSummary,
    NegotiationSession,
    NegotiationMessage,
)
from app.models.lore import LoreEntry, LorePriority, normalize_lore_category, normalize_lore_priority
from app.models.plot import HookStatus, HookType
from app.models.skill import ExecuteSkillDTO
from app.models.token_usage import UsageCategory
from app.services.conflict_detector import ConflictDetector, get_conflict_detector
from app.services.operation_lifecycle_service import OperationLifecycleService
from app.services.token_tracker import token_tracker
from app.services.trace_service import TraceService, get_trace_service

logger = logging.getLogger(__name__)


@dataclass
class SegmentedContextSynthesis:
    """设定助手长上下文分段综合结果。"""

    full_context: str
    key_info_index: str
    key_points: List[Dict[str, Any]] = field(default_factory=list)
    cross_segment_links: List[Dict[str, Any]] = field(default_factory=list)
    potential_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    resource_requirements: List[Dict[str, Any]] = field(default_factory=list)
    parse_warnings: List[Dict[str, Any]] = field(default_factory=list)

    def as_prompt_block(self) -> str:
        lines = [self.key_info_index.strip() or "（无关键信息点）"]
        if self.cross_segment_links:
            lines.append("\n### 跨段关联提示")
            for link in self.cross_segment_links[:12]:
                entities = " / ".join(str(item) for item in link.get("entities", []) if item)
                note = str(link.get("note") or link.get("reason") or "").strip()
                relation_type = str(link.get("relation_type") or link.get("type") or "关联").strip()
                lines.append(f"- [{relation_type}] {entities}: {note}" if entities else f"- [{relation_type}] {note}")
        if self.potential_conflicts:
            lines.append("\n### 潜在冲突提示")
            for conflict in self.potential_conflicts[:8]:
                entities = " / ".join(str(item) for item in conflict.get("entities", []) if item)
                note = str(conflict.get("note") or conflict.get("description") or "").strip()
                lines.append(f"- {entities}: {note}" if entities else f"- {note}")
        if self.resource_requirements:
            lines.append("\n### 资源补全提示")
            for req in self.resource_requirements[:10]:
                req_type = str(req.get("requirement_type") or req.get("type") or "lore")
                name = str(req.get("resource_name") or req.get("name") or "未命名资源")
                reason = str(req.get("reason") or req.get("usage_guidance") or "需要补全后再作为关键设定使用")
                lines.append(f"- [{req_type}] {name}: {reason}")
        if self.parse_warnings:
            lines.append("\n### 分段解析警告")
            for warning in self.parse_warnings[:6]:
                lines.append(f"- {warning.get('section', '未知分段')}: {warning.get('error', '解析失败，已保留原文上下文')}")
        return "\n".join(line for line in lines if line is not None)


class SettingAgentService:
    """设定 Agent 服务 - 持续的设定管理者"""

    SETTING_IMPROVEMENT_ANALYSIS_PROMPT_ID = "function_setting_improvement_analysis"
    SETTING_MODIFICATION_EXTRACTION_PROMPT_ID = "function_setting_modification_extraction"
    SETTING_MANAGEMENT_SYSTEM_PROMPT_ID = "function_setting_management_system_prompt"
    SETTING_LORE_EXTRACTION_PROMPT_ID = "function_setting_lore_extraction_confirmation"
    SETTING_HOOK_EXTRACTION_PROMPT_ID = "function_setting_hook_extraction_confirmation"
    SETTING_CHARACTER_EXTRACTION_PROMPT_ID = "function_setting_character_extraction_confirmation"
    SETTING_BOOTSTRAP_COLLECTION_PROMPT_ID = "function_setting_bootstrap_collection"
    SETTING_BOOTSTRAP_SEED_EXTRACTION_PROMPT_ID = "function_setting_bootstrap_seed_extraction"
    SETTING_PERSONALITY_GENERATION_PROMPT_ID = "function_setting_personality_generation"
    SETTING_WORLD_TYPE_INFERENCE_PROMPT_ID = "function_setting_world_type_inference"
    SETTING_TONE_INFERENCE_PROMPT_ID = "function_setting_tone_inference"

    def __init__(self):
        self.llm_provider = settings.llm_provider
        # 获取当前 provider 的配置
        llm_config = settings.get_llm_config(self.llm_provider)
        self.llm_api_key = llm_config.get("api_key", "")
        self.llm_base_url = llm_config.get("base_url", "")
        self.llm_model = llm_config.get("model", "")
        self.llm_temperature = llm_config.get("temperature", 0.7)
        self.llm_max_tokens = llm_config.get("max_tokens", 4096)

        # 检查 LLM 配置是否完整
        if not self.llm_api_key:
            logger.warning(f"[SettingAgent] LLM API Key 未配置！Provider: {self.llm_provider}")
        if not self.llm_model:
            logger.warning(f"[SettingAgent] LLM Model 未配置！Provider: {self.llm_provider}")
        else:
            logger.info(f"[SettingAgent] LLM 配置完成 - Provider: {self.llm_provider}, Model: {self.llm_model}")

        # 会话存储
        self._sessions: Dict[str, BootstrapSession] = {}
        self._management_sessions: Dict[str, SettingAgentSession] = {}
        self._knowledge_indices: Dict[str, LoreKnowledgeIndex] = {}

        # 冲突检测器
        self._conflict_detector = get_conflict_detector()

        # 协商会话
        self._negotiation_sessions: Dict[str, NegotiationSession] = {}

        # ========== LLM 重试保护配置 ==========
        self._max_retries = 3  # 最大重试次数
        self._retry_base_delay = 1.0  # 基础重试延迟（秒）
        self._retry_max_delay = 10.0  # 最大重试延迟（秒）
        self._consecutive_failures = 0  # 连续失败计数
        self._max_consecutive_failures = 5  # 最大连续失败次数，超过后暂停调用
        self._failure_reset_time = 60  # 失败计数重置时间（秒）
        self._last_failure_time = None  # 上次失败时间

        self._setting_config_prompt_cache: Dict[str, str] = {}
        self._setting_config_prompt_source_cache: Dict[str, str] = {}
        self._setting_config_prompt_trace_cache: Dict[str, Dict[str, Any]] = {}

    def _setting_scenario_for_mode(self, session: Optional[SettingAgentSession]) -> str:
        if session and session.mode == SettingAgentMode.MANAGEMENT:
            return "resource_management"
        return "workflow_context"

    def _build_setting_prompt_fallback_trace(
        self,
        project_id: Optional[str],
        scenario: str,
        *,
        fallback: Optional[str] = None,
        deprecated_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "agent_type": AgentType.SETTING.value,
            "scenario": scenario or "workflow_context",
            "project_id": project_id,
            "template_id": None,
            "template_scenario": None,
            "config_id": None,
            "prompt_ids": [],
            "skill_ids": [],
            "skills": None,
            "writing_rule_ids": [],
            "writing_rules": None,
            "context_blocks": [],
            "fallbacks_used": [fallback] if fallback else ["setting_missing_config_prompt"],
            "deprecated_sources_used": [deprecated_source] if deprecated_source else ([] if fallback else ["SettingAgentService._build_md_setting_fallback_prompt"]),
            "missing_prompt_ids": [] if fallback else [
                "role_setting",
                "function_setting_resource_management",
                "function_setting_segmented_context_synthesis",
                "function_setting_lore_interconnection",
                "function_setting_requirement_resolution",
            ],
        }

    async def _get_setting_config_prompt_with_trace(
        self,
        project_id: Optional[str],
        scenario: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cache_key = f"{project_id or 'global'}::{scenario or 'workflow_context'}"
        if cache_key in self._setting_config_prompt_cache and cache_key in self._setting_config_prompt_trace_cache:
            return {
                "content": self._setting_config_prompt_cache[cache_key],
                "trace": self._setting_config_prompt_trace_cache[cache_key],
                "source": self._setting_config_prompt_source_cache.get(cache_key, "missing"),
            }

        prompt = ""
        trace: Dict[str, Any] = {}
        if project_id:
            try:
                from app.services.agent_prompt_service import get_agent_prompt_service

                service = get_agent_prompt_service()
                prompt_data = await service.build_agent_prompt_with_trace(
                    agent_type=AgentType.SETTING,
                    project_id=project_id,
                    scenario=scenario,
                    variables=variables or {},
                )
                prompt = prompt_data.get("content", "")
                trace = prompt_data.get("trace", {}) or {}
            except Exception as e:
                logger.warning(f"[SettingAgent] 加载 Setting Agent Template prompt 失败: {e}")

        if prompt:
            self._setting_config_prompt_cache[cache_key] = prompt
            self._setting_config_prompt_source_cache[cache_key] = "agent_template_runtime"
            self._setting_config_prompt_trace_cache[cache_key] = trace
            return {"content": prompt, "trace": trace, "source": "agent_template_runtime"}

        fallback = self._build_md_setting_fallback_prompt()
        if fallback:
            trace = self._build_setting_prompt_fallback_trace(
                project_id,
                scenario,
                fallback="setting_md_prompt_fallback",
            )
            self._setting_config_prompt_cache[cache_key] = fallback
            self._setting_config_prompt_source_cache[cache_key] = "md_prompt_fallback"
            self._setting_config_prompt_trace_cache[cache_key] = trace
            return {"content": fallback, "trace": trace, "source": "md_prompt_fallback"}

        trace = self._build_setting_prompt_fallback_trace(project_id, scenario)
        self._setting_config_prompt_cache[cache_key] = ""
        self._setting_config_prompt_source_cache[cache_key] = "missing"
        self._setting_config_prompt_trace_cache[cache_key] = trace
        return {"content": "", "trace": trace, "source": "missing"}

    async def _get_setting_config_prompt(
        self,
        project_id: Optional[str],
        scenario: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        prompt_data = await self._get_setting_config_prompt_with_trace(project_id, scenario, variables)
        return prompt_data.get("content", "")

    def _build_md_setting_fallback_prompt(self) -> str:
        prompt_ids = [
            "role_setting",
            "function_setting_resource_management",
            "function_setting_segmented_context_synthesis",
            "function_setting_lore_interconnection",
            "function_setting_requirement_resolution",
        ]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        return "\n\n".join(parts).strip()

    def _load_md_prompt_content(self, prompt_id: str) -> str:
        try:
            from app.services.md_file_service import get_md_file_service

            md_service = get_md_file_service()
            prompt = md_service.get_prompt(prompt_id)
            if prompt:
                content = prompt.get("content") or prompt.get("raw_content") or ""
                if content:
                    return content.strip()
        except Exception as e:
            logger.warning(f"加载 {prompt_id} prompt 失败: {e}")

        return ""

    def reset_failure_state(self):
        """重置 LLM 失败状态（可由外部调用）"""
        self._consecutive_failures = 0
        self._last_failure_time = None
        logger.info("[SettingAgent] LLM 失败状态已重置")

    def is_llm_available(self) -> bool:
        """检查 LLM 是否可用（未达到失败上限）"""
        if self._consecutive_failures >= self._max_consecutive_failures:
            if self._last_failure_time:
                import time
                elapsed = time.time() - self._last_failure_time
                if elapsed < self._failure_reset_time:
                    return False
                else:
                    # 时间已过，自动重置
                    self.reset_failure_state()
                    return True
        return True

    def get_failure_status(self) -> Dict[str, Any]:
        """获取当前失败状态（用于诊断）"""
        import time
        remaining_time = 0
        if self._last_failure_time and self._consecutive_failures >= self._max_consecutive_failures:
            remaining_time = max(0, self._failure_reset_time - (time.time() - self._last_failure_time))

        return {
            "consecutive_failures": self._consecutive_failures,
            "max_consecutive_failures": self._max_consecutive_failures,
            "is_available": self.is_llm_available(),
            "remaining_cooldown_seconds": int(remaining_time),
        }

    # ==================== 会话管理 ====================

    async def get_or_create_session(
        self,
        project_id: str,
        mode: SettingAgentMode = SettingAgentMode.MANAGEMENT,
        session_id: Optional[str] = None,
    ) -> SettingAgentSession:
        """
        获取或创建 Setting Agent 会话

        Args:
            project_id: 项目 ID
            mode: 运行模式
            session_id: 可选会话 ID，用于刷新后恢复

        Returns:
            SettingAgentSession: 会话对象
        """
        from app.api.app import postgres_db

        if session_id and session_id in self._management_sessions:
            session = self._management_sessions[session_id]
            if not postgres_db:
                return session
            row = await postgres_db.get_setting_agent_session(session_id)
            if row:
                return session
            if await self._persist_session_snapshot(session):
                return session

        if session_id and postgres_db:
            row = await postgres_db.get_setting_agent_session(session_id)
            if row:
                session = self._session_from_row(row)
                self._management_sessions[session.id] = session
                await self._load_knowledge_index(project_id)
                return session

        # 检查是否已有内存会话
        for session in self._management_sessions.values():
            if session.project_id == project_id and session.mode == mode and session.is_active:
                if not postgres_db:
                    return session
                row = await postgres_db.get_setting_agent_session(session.id)
                if row:
                    return session
                if await self._persist_session_snapshot(session):
                    return session
                continue

        if postgres_db:
            row = await postgres_db.get_active_setting_agent_session(project_id, mode.value if hasattr(mode, "value") else str(mode))
            if row:
                session = self._session_from_row(row)
                self._management_sessions[session.id] = session
                await self._load_knowledge_index(project_id)
                return session

        # 创建新会话
        session = SettingAgentSession(
            project_id=project_id,
            mode=mode,
        )
        if not await self._persist_session_snapshot(session):
            raise RuntimeError("Setting Agent 会话持久化失败，无法创建可恢复会话")
        self._management_sessions[session.id] = session

        # 加载知识索引
        await self._load_knowledge_index(project_id)

        logger.info(f"创建 Setting Agent 会话: {session.id} for project {project_id}")
        return session

    async def _load_knowledge_index(self, project_id: str):
        """加载知识索引"""
        if project_id not in self._knowledge_indices:
            self._knowledge_indices[project_id] = LoreKnowledgeIndex(project_id=project_id)
            # TODO: 从数据库加载现有设定并构建索引

    async def _persist_session_snapshot(self, session: SettingAgentSession) -> bool:
        """持久化 Setting Agent 会话快照。"""
        try:
            from app.api.app import postgres_db
            if not postgres_db:
                return False
            await postgres_db.save_setting_agent_session({
                "id": session.id,
                "project_id": session.project_id,
                "mode": session.mode.value if hasattr(session.mode, "value") else str(session.mode),
                "status": "active" if session.is_active else "closed",
                "conversation_snapshot": session.conversation_history,
                "pending_conflicts": [c.model_dump(mode="json") if hasattr(c, "model_dump") else c for c in session.pending_conflicts],
                "cached_pending_lores": session.cached_pending_lores,
                "cached_pending_characters": session.cached_pending_characters,
                "cached_pending_hooks": session.cached_pending_hooks,
                "cached_context_sections": session.cached_context_sections,
                "full_context_loaded": session.full_context_loaded,
                "created_at": session.created_at,
                "updated_at": datetime.now(),
                "last_activity_at": session.last_activity_at,
            })
            return True
        except Exception as e:
            logger.warning(f"持久化 Setting Agent 会话失败: {e}")
            return False

    def _session_from_row(self, row: Dict[str, Any]) -> SettingAgentSession:
        """从数据库行恢复 SettingAgentSession。"""
        session = SettingAgentSession(
            id=row["id"],
            project_id=str(row["project_id"]),
            mode=SettingAgentMode(row.get("mode") or SettingAgentMode.MANAGEMENT.value),
            conversation_history=row.get("conversation_snapshot") or [],
            pending_conflicts=[],
            cached_pending_lores=row.get("cached_pending_lores") or [],
            cached_pending_characters=row.get("cached_pending_characters") or [],
            cached_pending_hooks=row.get("cached_pending_hooks") or [],
            full_context_loaded=bool(row.get("full_context_loaded") or False),
            cached_context_sections=row.get("cached_context_sections") or {},
            is_active=(row.get("status") or "active") == "active",
            created_at=row.get("created_at") or datetime.now(),
            updated_at=row.get("updated_at") or datetime.now(),
            last_activity_at=row.get("last_activity_at") or datetime.now(),
        )
        return session

    @staticmethod
    def _fingerprint_payload(payload: Dict[str, Any]) -> str:
        """生成 pending item 幂等指纹。"""
        scoped_payload = dict(payload or {})
        scope = scoped_payload.get("world_scope")
        if isinstance(scope, dict):
            if scope.get("world_id") and not scoped_payload.get("world_id"):
                scoped_payload["world_id"] = scope.get("world_id")
            if scope.get("scope_type") and not scoped_payload.get("scope_type"):
                scoped_payload["scope_type"] = scope.get("scope_type")
        raw = json.dumps(scoped_payload, ensure_ascii=False, sort_keys=True, default=str)
        return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))

    async def _persist_pending_items(
        self,
        session: SettingAgentSession,
        item_type: str,
        items: List[Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> None:
        """持久化待确认项，按 session/type/fingerprint 幂等。"""
        if not items:
            return
        try:
            from app.api.app import postgres_db
            if not postgres_db:
                return
            for item in items:
                await postgres_db.upsert_setting_agent_pending_item(
                    session_id=session.id,
                    item_type=item_type,
                    fingerprint=self._fingerprint_payload(item),
                    payload=item,
                    request_id=request_id,
                    status="pending",
                )
        except Exception as e:
            logger.warning(f"持久化 Setting Agent 待确认项失败: {item_type}, error={e}")

    async def get_chat_history(
        self,
        project_id: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取持久化聊天历史和 pending 快照。"""
        session = await self.get_or_create_session(project_id, session_id=session_id)
        from app.api.app import postgres_db
        messages = []
        pending_lores = session.cached_pending_lores
        pending_characters = session.cached_pending_characters
        pending_hooks = session.cached_pending_hooks
        if postgres_db:
            messages = await postgres_db.get_setting_agent_messages(session.id)
            pending_items = await postgres_db.get_setting_agent_pending_items(session.id, status="pending")
            if pending_items:
                pending_lores = [item.get("payload") or {} for item in pending_items if item.get("item_type") == "lore"]
                pending_characters = [item.get("payload") or {} for item in pending_items if item.get("item_type") == "character"]
                pending_hooks = [item.get("payload") or {} for item in pending_items if item.get("item_type") == "hook"]
        context_packet = None
        assistant_session_id = None
        if postgres_db:
            try:
                assistant_session = await postgres_db.get_active_assistant_session(
                    project_id=project_id,
                    assistant_surface="setting_agent",
                    mode=session.mode.value if hasattr(session.mode, "value") else str(session.mode),
                )
                if assistant_session:
                    assistant_session_id = assistant_session.get("id")
                    if assistant_session.get("last_packet_id"):
                        packet = await postgres_db.get_assistant_packet(str(assistant_session["last_packet_id"]))
                        if packet:
                            context_packet = {
                                "packet_id": packet.get("id"),
                                "snapshot_id": packet.get("snapshot_id"),
                                "snapshot_version": packet.get("snapshot_version"),
                                "assistant_surface": packet.get("assistant_surface"),
                                "invalidation_state": packet.get("invalidation_state") or "fresh",
                                "force_reread": bool(packet.get("force_reread")),
                                "history_reset_applied": bool(packet.get("history_reset_applied")),
                                "token_estimate": packet.get("token_estimate") or 0,
                                "selected_sections": packet.get("selected_sections") or [],
                                "omitted_sections": (packet.get("metadata") or {}).get("omitted_sections", []),
                                "delta_count": len(packet.get("delta_ids") or []),
                                "rebuilt_at": (packet.get("metadata") or {}).get("rebuilt_at"),
                            }
            except Exception as e:
                logger.debug(f"获取 Setting Agent Assistant Context 元数据失败: {e}")
        if not messages:
            messages = session.conversation_history
        return {
            "session_id": session.id,
            "assistant_session_id": assistant_session_id,
            "messages": messages,
            "pending_lores": pending_lores,
            "pending_characters": pending_characters,
            "pending_hooks": pending_hooks,
            "context_packet": context_packet,
        }

    async def process_setting_change(
        self,
        project_id: str,
        change_type: SettingChangeType,
        lore_data: Optional[Dict[str, Any]] = None,
        target_lore_id: Optional[str] = None,
        user_intent: Optional[str] = None,
    ) -> SettingChangeRequest:
        """
        处理设定变更请求

        Args:
            project_id: 项目 ID
            change_type: 变更类型
            lore_data: 设定数据
            target_lore_id: 目标设定 ID
            user_intent: 用户意图描述

        Returns:
            SettingChangeRequest: 变更请求对象
        """
        # 创建变更请求
        request = SettingChangeRequest(
            project_id=project_id,
            change_type=change_type,
            target_lore_id=target_lore_id,
            new_lore_data=lore_data,
            user_intent=user_intent,
        )

        # 如果是添加或修改，进行冲突检测
        if change_type in [SettingChangeType.ADD, SettingChangeType.MODIFY]:
            existing_lores = await self._get_existing_lores(project_id)
            conflicts = await self._detect_conflicts(lore_data, existing_lores)

            if conflicts:
                request.conflicts = conflicts
                request.has_conflicts = True
                request.status = "conflict_detected"

                # 更新会话状态
                session = await self.get_or_create_session(project_id)
                session.current_request = request
                session.pending_conflicts = conflicts

                return request

        # 无冲突，标记为可执行
        request.status = "ready_to_execute"
        return request

    async def _get_existing_lores(self, project_id: str) -> List[LoreEntry]:
        """获取现有设定列表"""
        try:
            from app.api.app import postgres_db
            if not postgres_db:
                logger.warning("数据库未连接，无法加载设定")
                return []

            rows = await postgres_db.execute_query(
                """SELECT id, project_id, title, category, priority, content, summary,
                          keywords, tags, constraints, related_characters, related_locations,
                          related_items, created_at, updated_at
                   FROM lore_entries
                   WHERE project_id = CAST(:project_id AS UUID)
                   ORDER BY priority, created_at DESC""",
                {"project_id": project_id}
            )

            lores = []
            for row in rows:
                lore = LoreEntry(
                    id=row.get("id"),
                    project_id=row.get("project_id"),
                    title=row.get("title", ""),
                    category=row.get("category", "custom"),
                    priority=normalize_lore_priority(row.get("priority", "standard")),
                    content=row.get("content", ""),
                    summary=row.get("summary", ""),
                    keywords=json.loads(row.get("keywords", "[]")) if isinstance(row.get("keywords"), str) else row.get("keywords", []),
                    tags=json.loads(row.get("tags", "[]")) if isinstance(row.get("tags"), str) else row.get("tags", []),
                    constraints=json.loads(row.get("constraints", "[]")) if isinstance(row.get("constraints"), str) else row.get("constraints", []),
                    related_characters=json.loads(row.get("related_characters", "[]")) if isinstance(row.get("related_characters"), str) else row.get("related_characters", []),
                    related_locations=json.loads(row.get("related_locations", "[]")) if isinstance(row.get("related_locations"), str) else row.get("related_locations", []),
                    related_items=json.loads(row.get("related_items", "[]")) if isinstance(row.get("related_items"), str) else row.get("related_items", []),
                    created_at=row.get("created_at"),
                    updated_at=row.get("updated_at"),
                )
                lores.append(lore)

            logger.info(f"加载 {len(lores)} 条设定用于冲突检测")
            return lores

        except Exception as e:
            logger.error(f"加载设定失败: {e}")
            return []

    async def _detect_conflicts(
        self,
        new_lore_data: Optional[Dict[str, Any]],
        existing_lores: List[LoreEntry],
    ) -> List[SettingConflict]:
        """检测冲突"""
        if not new_lore_data:
            return []

        return await self._conflict_detector.detect_conflicts(
            project_id=new_lore_data.get("project_id", ""),
            new_lore_data=new_lore_data,
            existing_lores=existing_lores,
        )

    # ==================== 冲突解决 ====================

    async def negotiate(
        self,
        project_id: str,
        conflict_id: str,
        user_response: str,
    ) -> Dict[str, Any]:
        """
        协商解决冲突

        Args:
            project_id: 项目 ID
            conflict_id: 冲突 ID
            user_response: 用户回复

        Returns:
            Dict: 协商结果
        """
        # 获取会话
        session = await self.get_or_create_session(project_id)

        # 查找冲突
        conflict = None
        for c in session.pending_conflicts:
            if c.id == conflict_id:
                conflict = c
                break

        if not conflict:
            return {"error": "Conflict not found"}

        # 分析用户意图
        user_intent = await self._analyze_user_intent(user_response)

        # 根据用户意图处理
        if user_intent == "accept_suggestion":
            # 用户接受某个建议
            suggestion_idx = await self._extract_suggestion_index(user_response)
            if suggestion_idx is not None and suggestion_idx < len(conflict.resolution_suggestions):
                conflict.selected_resolution = conflict.resolution_suggestions[suggestion_idx]
                conflict.status = ConflictResolutionStatus.RESOLVED
                conflict.resolved_at = datetime.now()
        elif user_intent == "override":
            # 用户选择覆盖
            conflict.selected_resolution = "user_override"
            conflict.status = ConflictResolutionStatus.RESOLVED
            conflict.resolved_at = datetime.now()
        elif user_intent == "cancel":
            # 用户取消变更
            conflict.selected_resolution = "cancel_change"
            conflict.status = ConflictResolutionStatus.RESOLVED
            conflict.resolved_at = datetime.now()
        else:
            # 继续协商
            return await self._generate_negotiation_response(session, conflict, user_response)

        # 检查是否所有冲突都已解决
        all_resolved = all(
            c.status == ConflictResolutionStatus.RESOLVED
            for c in session.pending_conflicts
        )

        if all_resolved and session.current_request:
            session.current_request.status = "resolved"

        return self._build_negotiation_response(
            status="resolved" if all_resolved else "negotiating",
            can_proceed=all_resolved,
            conflict=conflict,
            message="冲突已解决，可以继续后续操作。" if all_resolved else "当前冲突已处理，仍有其他冲突待解决。",
        )

    def _is_save_intent(self, message: str) -> bool:
        """检测用户消息是否为保存/确认意图（不需要调用LLM）"""
        message_lower = message.strip().lower()
        save_keywords = [
            "保存", "确认", "确定", "好的", "可以", "没问题",
            "就这样", "行", "ok", "yes", "save", "确认保存",
            "保存吧", "存一下", "存下来", "保存下来",
        ]
        # 消息较短且包含保存关键词时才判定为保存意图
        if len(message_lower) > 50:
            return False
        return any(keyword in message_lower for keyword in save_keywords)

    def _clear_cached_pending_lores(self, project_id: str):
        """清除指定项目 session 中缓存的 pending_lores"""
        for session in self._management_sessions.values():
            if session.project_id == project_id and session.is_active:
                session.cached_pending_lores = []
                break

    def _clear_cached_pending_characters(self, project_id: str):
        """清除指定项目 session 中缓存的 pending_characters"""
        for session in self._management_sessions.values():
            if session.project_id == project_id and session.is_active:
                session.cached_pending_characters = []
                break

    def _clear_cached_pending_hooks(self, project_id: str, world_id: Optional[str] = None):
        """清除指定项目 session 中缓存的 pending_hooks。传 world_id 时只清理同 scope 项。"""
        for session in self._management_sessions.values():
            if session.project_id != project_id or not session.is_active:
                continue
            if world_id:
                session.cached_pending_hooks = [
                    item for item in (session.cached_pending_hooks or [])
                    if str(item.get("world_id") or "") != str(world_id)
                ]
            else:
                session.cached_pending_hooks = []
            break

    def invalidate_context_cache(self, project_id: str):
        """失效指定项目 session 的上下文缓存"""
        for session in self._management_sessions.values():
            if session.project_id == project_id and session.is_active:
                session.cached_context_sections = {}
                session.full_context_loaded = False

    def _build_chat_response(
        self,
        session: SettingAgentSession,
        *,
        message: str,
        structured_data: Optional[Dict[str, Any]] = None,
        pending_lores: Optional[List[Dict[str, Any]]] = None,
        pending_characters: Optional[List[Dict[str, Any]]] = None,
        pending_hooks: Optional[List[Dict[str, Any]]] = None,
        improvement_suggestions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "message": message,
            "session_id": session.id,
            "mode": session.mode.value,
            "conversation_history": session.conversation_history,
            "cached_pending_lores": session.cached_pending_lores,
            "cached_pending_characters": session.cached_pending_characters,
            "cached_pending_hooks": session.cached_pending_hooks,
        }
        if structured_data is not None:
            result["structured_data"] = structured_data
        if pending_lores:
            result["pending_lores"] = pending_lores
        if pending_characters:
            result["pending_characters"] = pending_characters
        if pending_hooks:
            result["pending_hooks"] = pending_hooks
        if improvement_suggestions:
            result["improvement_suggestions"] = improvement_suggestions
        return result

    def _build_negotiation_response(
        self,
        *,
        status: str,
        can_proceed: bool,
        conflict: Optional[SettingConflict] = None,
        message: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": status,
            "can_proceed": can_proceed,
        }
        if conflict is not None:
            result["conflict"] = conflict.model_dump()
        if message:
            result["message"] = message
        if suggestions:
            result["suggestions"] = suggestions
        if error:
            result["error"] = error
        return result

    def _build_world_description_analysis_prompt(self, description: str) -> str:
        prompt_asset = self._load_md_prompt_content("function_setting_world_description_analysis")
        if not prompt_asset:
            prompt_asset = "【DEPRECATED 最小 fallback】请分析以下世界观描述，并提取结构化信息，只输出 JSON 对象。"
        return "\n\n".join([
            prompt_asset,
            f"## 世界观描述\n{description}",
        ]).strip()

    async def _analyze_world_description(
        self,
        project_id: str,
        description: str,
    ) -> Dict[str, Any]:
        prompt = self._build_world_description_analysis_prompt(description)

        response = await self._call_llm_simple(prompt, project_id=project_id)
        payload = response.strip()
        if payload.startswith("```"):
            payload = payload.strip("`")
            if payload.startswith("json"):
                payload = payload[4:]
            payload = payload.strip()

        data = json.loads(payload)
        return {
            "power_system": data.get("power_system") or "",
            "technology_level": data.get("technology_level") or "",
            "history": data.get("history") or "",
            "geography": data.get("geography") or "",
        }

    async def analyze_world_description(
        self,
        project_id: str,
        description: str,
    ) -> Dict[str, Any]:
        """公开的世界观描述结构化分析入口 (strict structured_data)."""
        return await self._analyze_world_description(project_id, description)

    async def _analyze_user_intent(self, user_response: str) -> str:
        """分析用户意图"""
        response_lower = user_response.lower()

        if any(word in response_lower for word in ["接受", "同意", "好的", "可以"]):
            return "accept_suggestion"
        if any(word in response_lower for word in ["覆盖", "强制", "忽略"]):
            return "override"
        if any(word in response_lower for word in ["取消", "放弃", "算了"]):
            return "cancel"
        return "continue"

    async def _analyze_world_description_via_chat(
        self,
        session: SettingAgentSession,
        project_id: str,
        description: str,
    ) -> Dict[str, Any]:
        structured_data = await self._analyze_world_description(project_id, description)
        return self._build_chat_response(
            session,
            message="我已经提取出这段世界观描述里的关键结构化信息，你可以直接检查并调整表单内容。",
            structured_data=structured_data,
        )

    async def _extract_suggestion_index(self, response: str) -> Optional[int]:
        """从回复中提取建议索引"""
        import re
        match = re.search(r'(\d+)', response)
        if match:
            return int(match.group(1)) - 1
        return None

    def _build_negotiation_response_prompt(self, conflict: SettingConflict, user_response: str) -> str:
        prompt_asset = self._load_md_prompt_content("function_setting_negotiation_response")
        if not prompt_asset:
            prompt_asset = "【DEPRECATED 最小 fallback】请生成一个有帮助的设定协商回复，帮助用户做出决定。"
        return "\n\n".join([
            prompt_asset,
            f"## 冲突描述\n{conflict.description}",
            f"## 严重程度\n{conflict.severity.value}",
            "## 现有建议\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(conflict.resolution_suggestions)),
            f"## 用户回复\n{user_response}",
        ]).strip()

    async def _generate_negotiation_response(
        self,
        session: SettingAgentSession,
        conflict: SettingConflict,
        user_response: str,
    ) -> Dict[str, Any]:
        """生成协商回复"""
        # 构建协商提示
        prompt = self._build_negotiation_response_prompt(conflict, user_response)

        # 调用 LLM 生成回复
        assistant_response = await self._call_llm_simple(prompt)

        # 创建协商会话
        if conflict.id not in self._negotiation_sessions:
            self._negotiation_sessions[conflict.id] = NegotiationSession(
                id=f"neg_{conflict.id}",
                conflict_id=conflict.id,
                project_id=session.project_id,
            )

        neg_session = self._negotiation_sessions[conflict.id]
        neg_session.messages.append(NegotiationMessage(
            role="user",
            content=user_response,
            conflict_id=conflict.id,
        ))
        neg_session.messages.append(NegotiationMessage(
            role="assistant",
            content=assistant_response,
            conflict_id=conflict.id,
        ))

        return self._build_negotiation_response(
            status="negotiating",
            can_proceed=False,
            conflict=conflict,
            message=assistant_response,
            suggestions=conflict.resolution_suggestions,
        )

    # ==================== 执行变更 ====================

    async def execute_change(
        self,
        project_id: str,
        request_id: str,
        override_conflicts: bool = False,
    ) -> Dict[str, Any]:
        """
        执行设定变更

        Args:
            project_id: 项目 ID
            request_id: 请求 ID
            override_conflicts: 是否覆盖冲突

        Returns:
            Dict: 执行结果
        """
        session = await self.get_or_create_session(project_id)

        if not session.current_request or session.current_request.id != request_id:
            return {"error": "Request not found"}

        request = session.current_request

        # 检查是否可以执行
        if request.has_conflicts and not override_conflicts:
            unresolved = [
                c for c in request.conflicts
                if c.status != ConflictResolutionStatus.RESOLVED
            ]
            if unresolved:
                return {
                    "error": "存在未解决的冲突",
                    "unresolved_conflicts": [c.model_dump() for c in unresolved],
                }

        # 执行变更
        try:
            result = await self._execute_change_internal(request)
            request.status = "executed"
            request.processed_at = datetime.now()

            # 更新知识索引
            await self._update_knowledge_index(project_id, request)

            return {
                "success": True,
                "result": result,
            }
        except Exception as e:
            logger.error(f"执行变更失败: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _execute_change_internal(
        self,
        request: SettingChangeRequest,
    ) -> Dict[str, Any]:
        """内部执行变更逻辑"""
        # TODO: 实际的数据库操作
        return {
            "change_type": request.change_type.value,
            "executed_at": datetime.now().isoformat(),
        }

    async def _update_knowledge_index(
        self,
        project_id: str,
        request: SettingChangeRequest,
    ):
        """更新知识索引"""
        index = self._knowledge_indices.get(project_id)
        if not index:
            return

        if request.new_lore_data:
            # 添加关键词索引
            for keyword in request.new_lore_data.get("keywords", []):
                index.add_keyword(keyword, request.new_lore_data.get("id", ""))

        index.last_updated = datetime.now()

    # ==================== 查询接口 ====================

    async def get_project_lore_summary(
        self,
        project_id: str,
    ) -> SettingSummary:
        """获取项目设定摘要"""
        # TODO: 从数据库获取实际数据
        return SettingSummary(project_id=project_id)

    async def chat(
        self,
        project_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        与 Setting Agent 聊天

        Args:
            project_id: 项目 ID
            message: 用户消息
            context: 额外上下文

        Returns:
            Dict: 响应结果
        """
        session = await self.get_or_create_session(project_id, session_id=session_id)
        from app.api.app import postgres_db
        if request_id and postgres_db:
            existing_response = await postgres_db.get_setting_agent_message_by_request(
                session.id,
                request_id,
                role="assistant",
            )
            if existing_response:
                return self._build_chat_response(
                    session,
                    message=existing_response.get("content") or "",
                    pending_lores=session.cached_pending_lores or None,
                    pending_characters=session.cached_pending_characters or None,
                    pending_hooks=session.cached_pending_hooks or None,
                )

        # 检测用户是否发送"保存"等确认性指令
        if self._is_save_intent(message) and (session.cached_pending_lores or session.cached_pending_characters or session.cached_pending_hooks):
            logger.info(f"[SettingAgent] 检测到保存意图，直接返回缓存的 pending 数据（跳过LLM调用）")

            # 添加用户消息到历史
            session.conversation_history.append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            })

            # 构建保存确认回复
            save_summary_parts = []
            if session.cached_pending_lores:
                lore_titles = [l.get("title", "未命名") for l in session.cached_pending_lores]
                save_summary_parts.append(f"{len(session.cached_pending_lores)} 条设定（{', '.join(lore_titles)}）")
            if session.cached_pending_characters:
                char_names = [c.get("name", "未命名") for c in session.cached_pending_characters]
                save_summary_parts.append(f"{len(session.cached_pending_characters)} 个角色（{', '.join(char_names)}）")
            if session.cached_pending_hooks:
                hook_titles = [h.get("title", "未命名") for h in session.cached_pending_hooks]
                save_summary_parts.append(f"{len(session.cached_pending_hooks)} 个伏笔（{', '.join(hook_titles)}）")

            response = f"好的，已为您准备保存以下内容：{'、'.join(save_summary_parts)}。请在弹窗中确认保存。"

            # 添加助手回复到历史
            session.conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat(),
            })

            session.last_activity_at = datetime.now()

            result = self._build_chat_response(
                session,
                message=response,
                pending_lores=session.cached_pending_lores or None,
                pending_characters=session.cached_pending_characters or None,
                pending_hooks=session.cached_pending_hooks or None,
            )

            if postgres_db:
                await postgres_db.append_setting_agent_message(session.id, "user", message, request_id=request_id)
                await postgres_db.append_setting_agent_message(session.id, "assistant", response, request_id=request_id)
            await self._persist_session_snapshot(session)

            return result

        # 添加用户消息到历史
        session.conversation_history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        if postgres_db:
            await postgres_db.append_setting_agent_message(session.id, "user", message, request_id=request_id)

        # 构建系统提示（异步）
        scenario = self._setting_scenario_for_mode(session)
        system_prompt = await self._build_management_system_prompt(session)
        prompt_data = await self._get_setting_config_prompt_with_trace(
            project_id,
            scenario,
            variables={"scenario": scenario, "mode": session.mode.value if hasattr(session.mode, "value") else str(session.mode)},
        )
        config_prompt = prompt_data.get("content", "")
        prompt_render_trace = prompt_data.get("trace", {}) or {}
        if config_prompt:
            system_prompt = (
                "【Setting 配置规则】\n"
                "以下内容来自 Agent Template 绑定的 md prompt / skills / writing-rules，是本次设定管理的稳定规则来源。\n"
                f"{config_prompt}\n\n"
                "【当前运行任务补充】\n"
                f"{system_prompt}"
            )


        context_packet = None
        sections = {}
        world_type = None
        if postgres_db:
            try:
                from app.services.assistant_context import get_assistant_context_fabric

                context_packet = await get_assistant_context_fabric(postgres_db).build_packet(
                    project_id=project_id,
                    assistant_surface="setting_agent",
                    task_type="chat",
                    session_id=session.id,
                    mode=session.mode.value if hasattr(session.mode, "value") else str(session.mode),
                    request_id=request_id,
                    scope={
                        "mode": session.mode.value if hasattr(session.mode, "value") else str(session.mode),
                        "needs": ["world", "lore", "characters", "plot_hooks", "chapter_outlines", "recent_deltas"],
                    },
                    user_message=message,
                )
                context_str = context_packet["prompt_context"]
                logger.info(
                    "[SettingAgent] 使用 Assistant Context Fabric packet=%s snapshot=v%s tokens=%s",
                    context_packet.get("packet_id"),
                    context_packet.get("snapshot_version"),
                    context_packet.get("metadata", {}).get("token_estimate"),
                )
            except Exception as e:
                logger.error(f"[SettingAgent] Assistant Context Fabric 构建失败: {e}")
                raise
        else:
            context_str = await self._build_chat_context(session, context)

        # 调用 LLM（传入 project_id 以记录 token）
        response = await self._call_llm(system_prompt, message, context_str, project_id=project_id)

        # 添加助手回复到历史
        session.conversation_history.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })

        session.last_activity_at = datetime.now()

        # 从对话中提取待确认的设定、伏笔和角色；用户明确修改既有设定时优先生成修改建议，避免误抽成新增资源
        lore_modification_suggestions = await self._extract_lore_modifications_from_conversation(project_id, session)
        if lore_modification_suggestions:
            pending_lores = []
            pending_hooks = []
            pending_characters = []
        else:
            pending_lores = await self._extract_lore_from_conversation(project_id, session)
            pending_hooks = await self._extract_hooks_from_conversation(project_id, session)
            pending_characters = await self._extract_characters_from_conversation(project_id, session)

        await self._persist_pending_items(session, "lore", pending_lores, request_id=request_id)
        await self._persist_pending_items(session, "hook", pending_hooks, request_id=request_id)
        await self._persist_pending_items(session, "character", pending_characters, request_id=request_id)

        # 缓存 pending 数据到 session（供下次"保存"指令跳过LLM使用）
        if pending_lores:
            session.cached_pending_lores = pending_lores
        if pending_hooks:
            session.cached_pending_hooks = pending_hooks
        if pending_characters:
            session.cached_pending_characters = pending_characters

        # 同步对话到 AgentMemoryService（与工作流 Agent 共享记忆）
        await self._sync_to_agent_memory(project_id, message, response)

        # 自动分析并更新项目元数据（每5次对话触发一次）
        if len(session.conversation_history) % 10 == 0:  # 每5次用户消息
            metadata_results = await self.analyze_and_update_project_metadata(
                project_id,
                session.conversation_history,
            )
            if metadata_results.get("updated"):
                logger.info(f"自动更新项目 {project_id} 元数据: {metadata_results}")

        # 主动分析现有设定，识别改进点（每 3 次对话触发一次），并合并用户明确提出的修改建议
        improvement_suggestions = list(lore_modification_suggestions)
        if len(session.conversation_history) % 6 == 0:  # 每 3 次用户消息
            try:
                # 构建对话上下文
                conversation_context = "\n".join([
                    f"{msg['role']}: {msg['content']}"
                    for msg in session.conversation_history[-6:]
                ])
                # 获取世界类型
                world_type = sections.get("_world_type") if 'sections' in dir() else None

                periodic_suggestions = await self.analyze_existing_lores(
                    project_id=project_id,
                    conversation_context=conversation_context,
                    world_type=world_type,
                )
                improvement_suggestions.extend(periodic_suggestions)
                if improvement_suggestions:
                    logger.info(f"[SettingAgent] 发现 {len(improvement_suggestions)} 个设定改进/修改建议")
            except Exception as e:
                logger.warning(f"[SettingAgent] 设定分析失败: {e}")

        if postgres_db:
            packet_id = context_packet.get("packet_id") if context_packet else None
            snapshot_id = context_packet.get("snapshot_id") if context_packet else None
            await postgres_db.append_setting_agent_message(session.id, "assistant", response, request_id=request_id)
            if context_packet:
                from app.services.assistant_context import get_assistant_context_fabric

                assistant_session_id = context_packet.get("session_id") or session.id
                assistant_session = await postgres_db.get_assistant_session(assistant_session_id)
                if assistant_session:
                    await get_assistant_context_fabric(postgres_db).sessions.append_message(
                        session=assistant_session,
                        role="assistant",
                        content=response,
                        request_id=request_id,
                        metadata={"setting_agent_session_id": session.id, "context_packet_id": packet_id},
                        packet_id=packet_id,
                        snapshot_id=snapshot_id,
                    )
        await self._persist_session_snapshot(session)

        result = self._build_chat_response(
            session,
            message=response,
            pending_lores=pending_lores or None,
            pending_characters=pending_characters or None,
            pending_hooks=pending_hooks or None,
            improvement_suggestions=improvement_suggestions or None,
        )
        result["prompt_render_trace"] = prompt_render_trace
        result["config_prompt_source"] = prompt_data.get("source") or "missing"
        if context_packet:
            result["assistant_session_id"] = context_packet.get("session_id")
            result["context_packet"] = {
                "packet_id": context_packet.get("packet_id"),
                "snapshot_id": context_packet.get("snapshot_id"),
                "snapshot_version": context_packet.get("snapshot_version"),
                **(context_packet.get("metadata") or {}),
            }
        return result

    async def _sync_to_agent_memory(
        self,
        project_id: str,
        user_message: str,
        assistant_response: str,
    ):
        """
        同步对话到 AgentMemoryService（只保存，不读取）

        确保工作流中的 SettingAgent 和 /lore 界面共享记忆

        Args:
            project_id: 项目 ID
            user_message: 用户消息
            assistant_response: 助手响应
        """
        try:
            from app.api.app import postgres_db
            from app.models.agent_memory import MemoryEntryCreate, MemoryType, MemoryImportance
            from app.services.agent_memory_service import get_memory_service

            if not postgres_db:
                return

            memory_service = get_memory_service(postgres_db)

            await memory_service.add_memory_entry(
                project_id=project_id,
                agent_type="setting",
                agent_id="setting_agent",
                entry=MemoryEntryCreate(
                    type=MemoryType.INTERACTION,
                    importance=MemoryImportance.MEDIUM,
                    content=f"用户: {user_message}",
                    context={"source": "lore_interface", "role": "user"},
                ),
            )
            await memory_service.add_memory_entry(
                project_id=project_id,
                agent_type="setting",
                agent_id="setting_agent",
                entry=MemoryEntryCreate(
                    type=MemoryType.INTERACTION,
                    importance=MemoryImportance.MEDIUM,
                    content=f"设定助手: {assistant_response}",
                    context={"source": "lore_interface", "role": "assistant"},
                ),
            )

            logger.debug(f"同步 Setting Agent 对话到记忆系统: project_id={project_id}")

        except Exception as e:
            logger.warning(f"同步 Setting Agent 记忆失败: {e}")

    def _append_lore_interconnection_guidance(self, prompt: str) -> str:
        """为设定抽取类 prompt 附加 Phase 4.5 互联字段要求。"""
        guidance = """

【设定互联字段要求】
- 每个设定必须尽量填写 related_characters / related_locations / related_items；如果涉及势力或组织，填写 related_factions。
- 如果该设定依赖既有设定、角色状态、地点、伏笔或章节大纲，填写 depends_on_lore，并在 usage_guidance 中说明使用边界。
- 如果该设定会支撑后续设定、伏笔或章节推进，填写 supports_lore。
- 如果发现与既有设定或大纲有潜在冲突，填写 potential_conflicts；不要直接覆盖既有设定。
- 如果需要新角色、地点、势力、道具、能力或事件规则配合，填写 resource_requirements，而不是把缺失资源硬写成已存在事实。
- resource_requirements 元素格式：{"requirement_type":"character|lore|faction|location|item|ability|relationship|event_rule|crisis_resolution","resource_name":"待补资源名","severity":"blocking|advisory|optional","reason":"为什么需要补全","suggested_payload":{}}。
"""
        return f"{prompt.rstrip()}\n{guidance}"

    def _normalize_string_list(self, value: Any) -> List[str]:
        """把 LLM/前端传入的列表字段规范为去重字符串列表。"""
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                value = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                value = re.split(r"[，,\n;；]", stripped)
        if isinstance(value, dict):
            value = list(value.values())
        if not isinstance(value, list):
            value = [value]

        result: List[str] = []
        seen = set()
        for item in value:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _normalize_lore_resource_requirements(self, value: Any) -> List[Dict[str, Any]]:
        """规范化待确认设定携带的资源补全需求。"""
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                value = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                value = [{"requirement_type": "lore", "resource_name": stripped, "severity": "advisory", "reason": stripped}]
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                name = str(item or "").strip()
                if not name:
                    continue
                item = {"requirement_type": "lore", "resource_name": name, "reason": name}
            req_type = str(item.get("requirement_type") or item.get("type") or "lore").strip() or "lore"
            resource_name = str(item.get("resource_name") or item.get("name") or item.get("title") or "").strip()
            reason = str(item.get("reason") or item.get("usage_guidance") or item.get("description") or "").strip()
            if not resource_name and not reason:
                continue
            severity = str(item.get("severity") or "advisory").strip().lower()
            if severity not in {"blocking", "advisory", "optional"}:
                severity = "advisory"
            normalized.append({
                "requirement_type": req_type,
                "resource_name": resource_name or reason[:80] or "未命名资源",
                "severity": severity,
                "reason": reason or "该设定依赖尚未补全的资源",
                "suggested_payload": item.get("suggested_payload") if isinstance(item.get("suggested_payload"), dict) else {},
            })
        return normalized

    def _normalize_lore_interconnection_payload(self, lore_data: Dict[str, Any]) -> Dict[str, Any]:
        """规范化待确认设定的互联字段，避免保存或展示时丢失上下文。"""
        normalized = dict(lore_data)
        for field_name in [
            "keywords",
            "tags",
            "constraints",
            "related_characters",
            "related_locations",
            "related_items",
            "related_factions",
            "depends_on_lore",
            "supports_lore",
            "potential_conflicts",
            "forbidden_actions",
        ]:
            normalized[field_name] = self._normalize_string_list(normalized.get(field_name))
        normalized["usage_guidance"] = str(normalized.get("usage_guidance") or "").strip()
        normalized["resource_requirements"] = self._normalize_lore_resource_requirements(normalized.get("resource_requirements"))
        return normalized

    def _build_lore_source_with_metadata(self, lore_data: Dict[str, Any]) -> str:
        """在现有 source 文本字段中保留可审计的互联元数据，避免旧表结构丢失信息。"""
        base_source = str(lore_data.get("source") or "setting_agent").strip() or "setting_agent"
        metadata = {
            "related_factions": lore_data.get("related_factions") or [],
            "depends_on_lore": lore_data.get("depends_on_lore") or [],
            "supports_lore": lore_data.get("supports_lore") or [],
            "potential_conflicts": lore_data.get("potential_conflicts") or [],
            "usage_guidance": lore_data.get("usage_guidance") or "",
            "resource_requirements": lore_data.get("resource_requirements") or [],
        }
        if not any(metadata.values()):
            return base_source
        return f"{base_source}\n[setting_agent_interconnection_metadata]\n{json.dumps(metadata, ensure_ascii=False)}"

    def _build_lore_extraction_prompt(self, history_text: str) -> str:
        prompt_asset = self._load_md_prompt_content(self.SETTING_LORE_EXTRACTION_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】分析以下对话，判断用户是否明确确认了新的世界观设定；"
                "只在用户明确确认后才提取，并只输出 JSON 数组。"
            )
        return "\n\n".join([
            prompt_asset,
            f"## 对话内容\n{history_text}",
        ]).strip()

    def _build_lore_modification_extraction_prompt(self, history_text: str, lores_summary: str) -> str:
        prompt_asset = self._load_md_prompt_content(self.SETTING_MODIFICATION_EXTRACTION_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "你是小说项目设定修改审稿人。请判断最近对话是否包含用户对既有设定的明确修改、改名、补充、纠错、合并或优先级调整请求。"
                "只对【现有设定候选】中的条目生成建议；不要把新增设定请求误判为修改；不要自动执行修改。"
                "输出 suggestions 列表，字段包括 type、target_lore_id、target_lore_title、issue、suggestion、suggested_content、"
                "suggested_title、summary、category、new_priority、keywords、tags、constraints、related_characters、related_locations、related_items、related_entities、update_payload、priority、reason。"
                "type 可用 optimize、priority、relation、rename、metadata。"
            )
        return "\n\n".join([
            prompt_asset,
            f"## 现有设定候选\n{lores_summary or '无'}",
            f"## 最近对话内容\n{history_text}",
            "## 判定边界\n- 只有用户明确要求修改/更正/补充/调整某个已有设定时才输出。\n- 如果用户只是提出新设定、新角色、新伏笔，返回空 suggestions。\n- target_lore_id 必须来自现有设定候选。\n- suggested_content 应是修改后的完整设定正文；只改标题/优先级/关联时可留空并使用对应字段。",
        ]).strip()

    async def _extract_lore_modifications_from_conversation(
        self,
        project_id: str,
        session: SettingAgentSession,
    ) -> List[Dict[str, Any]]:
        """从最近对话中提取用户明确要求的既有设定修改建议（不自动执行）。"""
        recent_messages = session.conversation_history[-6:]
        if len(recent_messages) < 2:
            return []

        latest_user_message = ""
        for msg in reversed(recent_messages):
            if msg.get("role") == "user":
                latest_user_message = str(msg.get("content") or "")
                break
        modification_keywords = [
            "修改", "改成", "改为", "更改", "调整", "更新", "补充", "修正", "纠正", "改名", "重命名",
            "rename", "modify", "update", "change", "revise", "correct",
        ]
        if not any(keyword in latest_user_message.lower() for keyword in modification_keywords):
            return []

        try:
            from app.api.app import postgres_db
            if not postgres_db:
                return []

            lores = await postgres_db.execute_query("""
                SELECT id, title, category, priority, content, summary, keywords, tags, constraints,
                       related_characters, related_locations, related_items
                FROM lore_entries
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 80
            """, {"project_id": project_id})
            if not lores:
                return []

            def _compact_lore_value(value: Any, limit: int = 360) -> str:
                if isinstance(value, (list, dict)):
                    text = json.dumps(value, ensure_ascii=False)
                else:
                    text = str(value or "")
                text = re.sub(r"\s+", " ", text).strip()
                return text[:limit] + ("..." if len(text) > limit else "")

            lores_summary = "\n".join([
                " | ".join([
                    f"ID={l.get('id')}",
                    f"标题={l.get('title')}",
                    f"分类={l.get('category')}",
                    f"优先级={l.get('priority')}",
                    f"摘要={_compact_lore_value(l.get('summary') or l.get('content'))}",
                    f"关键词={_compact_lore_value(l.get('keywords'), 180)}",
                ])
                for l in lores
            ])
            history_text = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in recent_messages
            ])
            prompt = self._build_lore_modification_extraction_prompt(history_text, lores_summary)

            from app.models.agent_output_schemas import SettingImprovementSuggestionsSchema
            from app.services.structured_llm import StructuredOutputError

            try:
                parsed = await self._call_structured(
                    SettingImprovementSuggestionsSchema,
                    prompt,
                    project_id=project_id,
                )
            except StructuredOutputError as e:
                logger.info(f"[SettingAgent] 修改建议 structured 提取失败：{e}")
                return []

            existing_by_id = {str(l.get("id")): l for l in lores if l.get("id")}
            valid_suggestions: List[Dict[str, Any]] = []
            allowed_types = {"optimize", "priority", "relation", "rename", "metadata"}
            for item in parsed.suggestions:
                suggestion = item.model_dump()
                target_id = str(suggestion.get("target_lore_id") or "").strip()
                if not target_id or target_id not in existing_by_id:
                    continue
                mod_type = str(suggestion.get("type") or "optimize").strip().lower() or "optimize"
                if mod_type not in allowed_types:
                    mod_type = "optimize"
                target_lore = existing_by_id[target_id]
                issue = str(suggestion.get("issue") or latest_user_message or "用户要求修改既有设定").strip()
                action_text = str(suggestion.get("suggestion") or "按用户最新要求修改该设定").strip()
                reason = str(suggestion.get("reason") or "来自用户在当前对话中的明确修改请求").strip()
                valid_suggestions.append({
                    "id": str(uuid.uuid4()),
                    "type": mod_type,
                    "target_lore_id": target_id,
                    "target_lore_title": suggestion.get("target_lore_title") or target_lore.get("title") or "",
                    "issue": issue,
                    "suggestion": action_text,
                    "suggested_content": suggestion.get("suggested_content"),
                    "suggested_title": suggestion.get("suggested_title"),
                    "summary": suggestion.get("summary"),
                    "category": suggestion.get("category"),
                    "new_priority": suggestion.get("new_priority"),
                    "keywords": self._normalize_string_list(suggestion.get("keywords")),
                    "tags": self._normalize_string_list(suggestion.get("tags")),
                    "constraints": self._normalize_string_list(suggestion.get("constraints")),
                    "related_characters": self._normalize_string_list(suggestion.get("related_characters")),
                    "related_locations": self._normalize_string_list(suggestion.get("related_locations")),
                    "related_items": self._normalize_string_list(suggestion.get("related_items")),
                    "related_entities": self._normalize_string_list(suggestion.get("related_entities")),
                    "update_payload": suggestion.get("update_payload") if isinstance(suggestion.get("update_payload"), dict) else {},
                    "priority": suggestion.get("priority") or "high",
                    "reason": reason,
                })

            if valid_suggestions:
                logger.info(f"[SettingAgent] 从对话中提取 {len(valid_suggestions)} 个既有设定修改建议")
            return valid_suggestions
        except Exception as e:
            logger.error(f"[SettingAgent] 提取既有设定修改建议失败: {e}")
            return []

    def _build_hook_extraction_prompt(self, history_text: str) -> str:
        prompt_asset = self._load_md_prompt_content(self.SETTING_HOOK_EXTRACTION_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】分析以下对话，判断用户是否明确确认了值得记录的伏笔；"
                "只在用户明确确认后才提取，并只输出 JSON 数组。"
            )
        return "\n\n".join([
            prompt_asset,
            f"## 对话内容\n{history_text}",
        ]).strip()

    def _build_character_extraction_prompt(self, history_text: str) -> str:
        prompt_asset = self._load_md_prompt_content(self.SETTING_CHARACTER_EXTRACTION_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】分析以下对话，判断用户是否明确确认了新的角色设定；"
                "只在用户明确确认后才提取，并只输出 JSON 数组。"
            )
        return "\n\n".join([
            prompt_asset,
            f"## 对话内容\n{history_text}",
        ]).strip()

    def _build_personality_generation_prompt_from_context(
        self,
        *,
        name: str,
        role: str,
        description: str,
        background: str,
        existing_personalities: str,
        project_context: str,
        role_descriptions: Dict[str, str],
    ) -> str:
        prompt_asset = self._load_md_prompt_content(self.SETTING_PERSONALITY_GENERATION_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】你是一个专业的小说角色设定专家。请为以下角色生成性格设定，并只输出 JSON。"
            )
        return "\n\n".join([
            prompt_asset,
            f"【项目背景】\n{project_context if project_context else '通用小说设定'}",
            "【角色信息】",
            f"- 姓名：{name}",
            f"- 定位：{role_descriptions.get(role, role)}",
            f"- 描述：{description}",
            f"- 背景：{background if background else '暂无详细背景'}",
            existing_personalities,
        ]).strip()

    async def _extract_lore_from_conversation(
        self,
        project_id: str,
        session: SettingAgentSession,
    ) -> List[Dict[str, Any]]:
        """
        从对话中提取新设定，但不自动保存（需要用户确认）

        Args:
            project_id: 项目 ID
            session: 会话对象

        Returns:
            List[Dict]: 待确认的设定列表
        """
        # 获取最近的对话
        recent_messages = session.conversation_history[-6:]  # 最近3轮对话
        if len(recent_messages) < 2:
            return []

        # 构建提取提示
        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in recent_messages
        ])

        extraction_prompt = self._build_lore_extraction_prompt(history_text)

        try:
            from app.models.agent_output_schemas import SettingPendingLoresExtractionSchema
            from app.services.structured_llm import StructuredOutputError

            extraction_prompt = self._append_lore_interconnection_guidance(extraction_prompt)

            try:
                parsed = await self._call_structured(
                    SettingPendingLoresExtractionSchema,
                    extraction_prompt,
                    project_id=project_id,
                )
                lores = [item.model_dump() for item in parsed.lores]
            except StructuredOutputError as e:
                logger.warning(f"提取设定 structured 失败：{e}")
                return []

            if not lores:
                return []

            # 返回待确认的设定（不保存到数据库）
            valid_lores = []
            for lore_data in lores:
                if not lore_data.get("title") or not lore_data.get("content"):
                    continue
                normalized_lore = self._normalize_lore_interconnection_payload(lore_data)
                valid_lores.append({
                    "title": normalized_lore.get("title", ""),
                    "category": normalize_lore_category(normalized_lore.get("category", "custom")).value,
                    "priority": normalize_lore_priority(normalized_lore.get("priority", "standard")).value,
                    "content": normalized_lore.get("content", ""),
                    "summary": normalized_lore.get("summary", ""),
                    "keywords": normalized_lore.get("keywords", []),
                    "tags": normalized_lore.get("tags", []),
                    "constraints": normalized_lore.get("constraints", []),
                    "related_characters": normalized_lore.get("related_characters", []),
                    "related_locations": normalized_lore.get("related_locations", []),
                    "related_items": normalized_lore.get("related_items", []),
                    "related_factions": normalized_lore.get("related_factions", []),
                    "depends_on_lore": normalized_lore.get("depends_on_lore", []),
                    "supports_lore": normalized_lore.get("supports_lore", []),
                    "potential_conflicts": normalized_lore.get("potential_conflicts", []),
                    "usage_guidance": normalized_lore.get("usage_guidance", ""),
                    "resource_requirements": normalized_lore.get("resource_requirements", []),
                })

            if valid_lores:
                logger.info(f"从对话中提取 {len(valid_lores)} 个待确认设定")

            return valid_lores

        except Exception as e:
            logger.error(f"提取设定失败: {e}")
            return []


    def _normalize_hook_type(self, hook_type: Any) -> str:
        """规范化 hook 类型到现有枚举值"""
        raw = str(hook_type or "").strip().lower()
        valid_types = {item.value for item in HookType}
        if raw in valid_types:
            return raw

        alias_map = {
            "foreshadow": HookType.CUSTOM.value,
            "foreshadowing": HookType.CUSTOM.value,
            "suspense": HookType.MYSTERY.value,
            "item": HookType.OBJECT.value,
            "artifact": HookType.OBJECT.value,
            "prop": HookType.OBJECT.value,
            "person": HookType.CHARACTER.value,
            "place": HookType.LOCATION.value,
            "relation": HookType.RELATIONSHIP.value,
        }
        return alias_map.get(raw, HookType.CUSTOM.value)

    def _normalize_hook_status(self, status: Any) -> str:
        """规范化 hook 状态到现有枚举值"""
        raw = str(status or "").strip().lower()
        valid_statuses = {item.value for item in HookStatus}
        if raw in valid_statuses:
            return raw
        return HookStatus.PLANTED.value

    def _normalize_hook_priority(self, priority: Any) -> int:
        """规范化 hook 优先级到 1-5"""
        try:
            value = int(priority)
        except (TypeError, ValueError):
            value = 3
        return max(1, min(5, value))

    async def _extract_hooks_from_conversation(
        self,
        project_id: str,
        session: SettingAgentSession,
    ) -> List[Dict[str, Any]]:
        """从对话中提取值得单独管理的伏笔信息（需要用户确认）"""
        recent_messages = session.conversation_history[-6:]
        if len(recent_messages) < 2:
            return []

        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in recent_messages
        ])

        extraction_prompt = self._build_hook_extraction_prompt(history_text)

        try:
            from app.models.agent_output_schemas import SettingPendingHooksExtractionSchema
            from app.services.structured_llm import StructuredOutputError

            try:
                parsed = await self._call_structured(
                    SettingPendingHooksExtractionSchema,
                    extraction_prompt,
                    project_id=project_id,
                )
                hooks = [item.model_dump() for item in parsed.hooks]
            except StructuredOutputError as e:
                logger.warning(f"提取伏笔 structured 失败：{e}")
                return []

            if not hooks:
                return []

            valid_hooks = []
            for hook_data in hooks:
                if not hook_data.get("title"):
                    continue
                valid_hooks.append({
                    "title": hook_data.get("title", ""),
                    "description": hook_data.get("description", ""),
                    "hook_type": self._normalize_hook_type(hook_data.get("hook_type")),
                    "status": self._normalize_hook_status(hook_data.get("status")),
                    "related_characters": hook_data.get("related_characters", []) or [],
                    "related_locations": hook_data.get("related_locations", []) or [],
                    "related_objects": hook_data.get("related_objects", []) or [],
                    "plant_context": hook_data.get("plant_context", ""),
                    "resolution_hint": hook_data.get("resolution_hint", ""),
                    "priority": self._normalize_hook_priority(hook_data.get("priority")),
                })

            if valid_hooks:
                logger.info(f"从对话中提取 {len(valid_hooks)} 个待确认伏笔")

            return valid_hooks

        except Exception as e:
            logger.error(f"提取伏笔失败: {e}")
            return []

    async def _begin_save_operation(
        self,
        postgres_db,
        project_id: str,
        session_id: Optional[str],
        request_id: Optional[str],
        operation_type: str,
        item_type: str,
        items: List[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
        """启动保存操作；同 request_id 重放时返回已保存数量。"""
        if not request_id:
            return None, None
        fingerprints = [self._fingerprint_payload(item) for item in items]
        lifecycle = OperationLifecycleService(db=postgres_db)
        begin = await lifecycle.begin_or_replay(
            operation_type=operation_type,
            project_id=project_id,
            resource_type="setting_agent_session",
            resource_id=session_id,
            request_payload={
                "project_id": project_id,
                "session_id": session_id,
                "item_type": item_type,
                "fingerprints": fingerprints,
                "count": len(fingerprints),
            },
            request_id=request_id,
        )
        if begin.replayed:
            payload = begin.operation.get("response_payload") or {}
            return begin.operation, int(payload.get("saved_count", 0))
        operation = await lifecycle.mark_running(begin.operation)
        return operation, None

    async def _complete_save_operation(
        self,
        postgres_db,
        operation: Optional[Dict[str, Any]],
        saved_count: int,
    ) -> None:
        """记录保存操作完成结果。"""
        if not operation:
            return
        await OperationLifecycleService(db=postgres_db).complete(
            operation,
            {"saved_count": saved_count},
        )

    async def _should_skip_saved_pending_item(
        self,
        postgres_db,
        session: Optional[SettingAgentSession],
        item_type: str,
        payload: Dict[str, Any],
    ) -> bool:
        """若待确认项已标记 saved，则跳过重复落库。"""
        if not session:
            return False
        pending_item = await postgres_db.get_setting_agent_pending_item(
            session.id,
            item_type,
            self._fingerprint_payload(payload),
        )
        return bool(pending_item and pending_item.get("status") == "saved")

    async def save_pending_lores(
        self,
        project_id: str,
        lores: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> int:
        """
        保存用户确认的设定到数据库

        Args:
            project_id: 项目 ID
            lores: 待保存的设定列表

        Returns:
            int: 保存的数量
        """
        from app.api.app import postgres_db
        if not postgres_db:
            return 0

        saved_count = 0
        session = await self.get_or_create_session(project_id, session_id=session_id) if session_id else None
        operation, replay_count = await self._begin_save_operation(
            postgres_db,
            project_id,
            session.id if session else session_id,
            request_id,
            "setting_save_lores",
            "lore",
            lores,
        )
        if replay_count is not None:
            return replay_count
        for lore_data in lores:
            if not lore_data.get("title") or not lore_data.get("content"):
                continue
            if await self._should_skip_saved_pending_item(postgres_db, session, "lore", lore_data):
                continue

            duplicate = None
            if hasattr(postgres_db, "find_duplicate_lore"):
                duplicate = await postgres_db.find_duplicate_lore(
                    project_id,
                    lore_data.get("title", ""),
                    lore_data.get("content", ""),
                )
            if duplicate:
                if session:
                    await postgres_db.mark_setting_agent_pending_item_saved(
                        session.id,
                        "lore",
                        self._fingerprint_payload(lore_data),
                        str(duplicate.get("id")),
                    )
                logger.info(f"跳过重复设定: {lore_data.get('title', '')} -> {duplicate.get('id')}")
                continue

            lore_data = self._normalize_lore_interconnection_payload(lore_data)
            lore_entry = {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "title": lore_data.get("title", ""),
                "category": normalize_lore_category(lore_data.get("category", "custom")).value,
                "priority": normalize_lore_priority(lore_data.get("priority", "standard")).value,
                "content": lore_data.get("content", ""),
                "summary": lore_data.get("summary", ""),
                "keywords": json.dumps(lore_data.get("keywords", [])),
                "tags": json.dumps(lore_data.get("tags", [])),
                "constraints": json.dumps(lore_data.get("constraints", [])),
                "related_characters": json.dumps(lore_data.get("related_characters", [])),
                "related_locations": json.dumps(lore_data.get("related_locations", [])),
                "related_items": json.dumps(lore_data.get("related_items", [])),
                "forbidden_actions": json.dumps(lore_data.get("forbidden_actions", [])),
                "source": self._build_lore_source_with_metadata(lore_data),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            try:
                await postgres_db.execute_write("""
                    INSERT INTO lore_entries (id, project_id, title, category, priority, content, summary, keywords, tags, constraints, related_characters, related_locations, related_items, forbidden_actions, source, created_at, updated_at)
                    VALUES (:id, CAST(:project_id AS UUID), :title, :category, :priority, :content, :summary, :keywords, :tags, :constraints, :related_characters, :related_locations, :related_items, :forbidden_actions, :source, :created_at, :updated_at)
                """, lore_entry)
                if session:
                    await postgres_db.mark_setting_agent_pending_item_saved(
                        session.id,
                        "lore",
                        self._fingerprint_payload(lore_data),
                        lore_entry["id"],
                    )
                saved_count += 1
                logger.info(f"保存用户确认的设定: {lore_entry['title']}")

                # 自动索引到向量库
                try:
                    from app.services.lore_index_service import get_lore_index_service
                    lore_index = get_lore_index_service()
                    await lore_index.index_lore(
                        lore_id=lore_entry["id"],
                        project_id=project_id,
                        title=lore_entry["title"],
                        content=lore_entry["content"],
                        category=lore_entry["category"],
                        priority=lore_entry["priority"],
                        keywords=lore_data.get("keywords", []),
                        related_characters=lore_data.get("related_characters", []),
                        related_locations=lore_data.get("related_locations", []),
                        related_items=lore_data.get("related_items", []),
                    )
                except Exception as idx_error:
                    logger.warning(f"索引设定失败（不影响保存）: {idx_error}")
            except Exception as e:
                logger.error(f"保存设定失败: {e}")

        # 保存成功后清除缓存，避免重复保存，并刷新上下文缓存
        if saved_count > 0:
            self._clear_cached_pending_lores(project_id)
            self.invalidate_context_cache(project_id)
        await self._complete_save_operation(postgres_db, operation, saved_count)

        return saved_count

    async def save_pending_hooks(
        self,
        project_id: str,
        hooks: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        world_id: Optional[str] = None,
        scope_type: Optional[str] = None,
    ) -> int:
        """保存用户确认的伏笔到数据库"""
        from app.api.app import postgres_db
        if not postgres_db:
            return 0

        effective_scope_type = scope_type or ("world" if world_id else "project")
        if world_id and hasattr(postgres_db, "assert_world_belongs_to_project"):
            belongs = await postgres_db.assert_world_belongs_to_project(str(world_id), str(project_id))
            if not belongs:
                raise ValueError("伏笔所属世界不属于当前项目")

        saved_count = 0
        session = await self.get_or_create_session(project_id, session_id=session_id) if session_id else None
        operation, replay_count = await self._begin_save_operation(
            postgres_db,
            project_id,
            session.id if session else session_id,
            request_id,
            "setting_save_hooks",
            "hook",
            hooks,
        )
        if replay_count is not None:
            return replay_count
        for hook_data in hooks:
            if not hook_data.get("title"):
                continue
            scoped_hook_data = {
                **hook_data,
                "world_id": hook_data.get("world_id") or world_id,
                "scope_type": hook_data.get("scope_type") or effective_scope_type,
            }
            if await self._should_skip_saved_pending_item(postgres_db, session, "hook", scoped_hook_data):
                continue

            duplicate = None
            if hasattr(postgres_db, "find_duplicate_hook"):
                duplicate = await postgres_db.find_duplicate_hook(
                    project_id,
                    scoped_hook_data.get("title", ""),
                    scoped_hook_data.get("description", ""),
                    world_id=scoped_hook_data.get("world_id"),
                    scope_type=scoped_hook_data.get("scope_type"),
                )
            if duplicate:
                if session:
                    await postgres_db.mark_setting_agent_pending_item_saved(
                        session.id,
                        "hook",
                        self._fingerprint_payload(scoped_hook_data),
                        str(duplicate.get("id")),
                    )
                logger.info(f"跳过重复伏笔: {scoped_hook_data.get('title', '')} -> {duplicate.get('id')}")
                continue

            hook_entry = {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "title": hook_data.get("title", ""),
                "description": hook_data.get("description", ""),
                "world_id": hook_data.get("world_id") or world_id,
                "scope_type": hook_data.get("scope_type") or effective_scope_type,
                "character_id": hook_data.get("character_id"),
                "parent_hook_id": hook_data.get("parent_hook_id"),
                "promoted_from_hook_id": hook_data.get("promoted_from_hook_id"),
                "visibility": hook_data.get("visibility") or "global",
                "hook_type": self._normalize_hook_type(hook_data.get("hook_type")),
                "status": self._normalize_hook_status(hook_data.get("status")),
                "related_characters": hook_data.get("related_characters", []) or [],
                "related_locations": hook_data.get("related_locations", []) or [],
                "related_objects": hook_data.get("related_objects", []) or [],
                "plant_context": hook_data.get("plant_context", ""),
                "plant_chapter": None,
                "resolution_hint": hook_data.get("resolution_hint", ""),
                "resolution_context": None,
                "resolution_chapter": None,
                "priority": self._normalize_hook_priority(hook_data.get("priority")),
                "created_at": datetime.now(),
                "resolved_at": None,
            }

            try:
                await postgres_db.save_hook(hook_entry)
                from app.services.graph_projection_service import enqueue_graph_projection_best_effort
                await enqueue_graph_projection_best_effort("hook", hook_entry)
                if session:
                    await postgres_db.mark_setting_agent_pending_item_saved(
                        session.id,
                        "hook",
                        self._fingerprint_payload(scoped_hook_data),
                        hook_entry["id"],
                    )
                saved_count += 1
                logger.info(f"保存用户确认的伏笔: {hook_entry['title']}")
            except Exception as e:
                logger.error(f"保存伏笔失败: {e}")

        if saved_count > 0:
            self._clear_cached_pending_hooks(project_id, world_id=world_id)
            self.invalidate_context_cache(project_id)
        await self._complete_save_operation(postgres_db, operation, saved_count)

        return saved_count

    def _build_deprecated_minimal_setting_improvement_analysis_prompt(self) -> str:
        logger.warning("[SettingAgent] 使用 deprecated 最小 fallback 生成设定改进分析 prompt")
        return (
            "【DEPRECATED 最小 fallback】请分析现有世界观设定，识别真正有价值的冲突、缺失、优先级、优化或关联改进建议，"
            "并只输出符合结构化契约的结果。"
        )

    def _build_setting_improvement_analysis_prompt(
        self,
        world_type_hint: str,
        lores_summary: str,
        conversation_context: str,
    ) -> str:
        prompt_asset = self._load_md_prompt_content(
            self.SETTING_IMPROVEMENT_ANALYSIS_PROMPT_ID,
        )
        if not prompt_asset:
            prompt_asset = self._build_deprecated_minimal_setting_improvement_analysis_prompt()
        return "\n\n".join([
            prompt_asset,
            f"## 世界类型\n{world_type_hint if world_type_hint else '未指定'}",
            f"## 现有设定列表\n{lores_summary}",
            f"## 最近对话上下文\n{conversation_context or '无'}",
        ]).strip()

    async def analyze_existing_lores(
        self,
        project_id: str,
        conversation_context: str,
        world_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        分析现有设定，识别可能的改进点

        Args:
            project_id: 项目 ID
            conversation_context: 对话上下文
            world_type: 世界类型

        Returns:
            List[Dict]: 改进建议列表
        """
        try:
            from app.api.app import postgres_db
            if not postgres_db:
                return []

            # 获取现有设定
            lores = await postgres_db.execute_query("""
                SELECT id, title, category, priority, content, summary, keywords
                FROM lore_entries
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY priority DESC, updated_at DESC
            """, {"project_id": project_id})

            if not lores or len(lores) < 2:
                # 设定太少，不需要分析
                return []

            # 构建设定摘要
            lores_summary = "\n".join([
                f"- [{l['priority']}] {l['title']} ({l['category']}): {l.get('summary') or l.get('content', '')}"
                for l in lores
            ])

            world_type_hint = self._get_world_type_hint(world_type) if world_type else ""

            analysis_prompt = self._build_setting_improvement_analysis_prompt(
                world_type_hint=world_type_hint,
                lores_summary=lores_summary,
                conversation_context=conversation_context,
            )

            from app.models.agent_output_schemas import SettingImprovementSuggestionsSchema
            from app.services.structured_llm import StructuredOutputError

            try:
                parsed = await self._call_structured(
                    SettingImprovementSuggestionsSchema,
                    analysis_prompt,
                    project_id=project_id,
                )
                suggestions = [item.model_dump() for item in parsed.suggestions]
            except StructuredOutputError as e:
                logger.warning(f"[SettingAgent] 改进建议 structured 失败：{e}")
                return []

            # 过滤并验证
            valid_suggestions = []
            existing_ids = {str(l.get("id")) for l in lores if l.get("id")}
            for s in suggestions:
                target_id = str(s.get("target_lore_id") or "").strip()
                if target_id and target_id not in existing_ids:
                    continue
                if s.get("type") and s.get("issue") and s.get("suggestion"):
                    valid_suggestions.append({
                        "id": str(uuid.uuid4()),
                        "type": s.get("type"),
                        "target_lore_id": s.get("target_lore_id"),
                        "target_lore_title": s.get("target_lore_title", ""),
                        "issue": s.get("issue"),
                        "suggestion": s.get("suggestion"),
                        "suggested_content": s.get("suggested_content"),
                        "suggested_title": s.get("suggested_title"),
                        "summary": s.get("summary"),
                        "category": s.get("category"),
                        "new_priority": s.get("new_priority"),
                        "keywords": self._normalize_string_list(s.get("keywords")),
                        "tags": self._normalize_string_list(s.get("tags")),
                        "constraints": self._normalize_string_list(s.get("constraints")),
                        "related_characters": self._normalize_string_list(s.get("related_characters")),
                        "related_locations": self._normalize_string_list(s.get("related_locations")),
                        "related_items": self._normalize_string_list(s.get("related_items")),
                        "related_entities": self._normalize_string_list(s.get("related_entities")),
                        "update_payload": s.get("update_payload") if isinstance(s.get("update_payload"), dict) else {},
                        "priority": s.get("priority", "medium"),
                        "reason": s.get("reason", ""),
                    })

            if valid_suggestions:
                logger.info(f"[SettingAgent] 发现 {len(valid_suggestions)} 个设定改进建议")

            return valid_suggestions

        except Exception as e:
            logger.error(f"[SettingAgent] 分析设定失败: {e}")
            return []

    async def execute_lore_modification(
        self,
        project_id: str,
        modification: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行设定修改

        Args:
            project_id: 项目 ID
            modification: 修改内容，包含 target_lore_id, type, suggested_content 等

        Returns:
            Dict: 执行结果
        """
        from app.api.app import postgres_db
        if not postgres_db:
            return {"success": False, "error": "数据库未连接"}

        mod_type = str(modification.get("type") or "").strip().lower()
        target_id = modification.get("target_lore_id")
        suggested_content = modification.get("suggested_content", "")

        try:
            if mod_type in {"optimize", "rename", "metadata"} and target_id:
                existing = await postgres_db.get_lore_entry(str(target_id)) if hasattr(postgres_db, "get_lore_entry") else None
                if not existing or str(existing.get("project_id")) != str(project_id):
                    return {"success": False, "error": "目标设定不存在或不属于当前项目"}

                update_payload = modification.get("update_payload") if isinstance(modification.get("update_payload"), dict) else {}
                fields: Dict[str, Any] = {}
                title_value = modification.get("suggested_title") or update_payload.get("title")
                if title_value:
                    fields["title"] = str(title_value).strip()
                content_value = suggested_content or update_payload.get("content")
                if content_value:
                    fields["content"] = str(content_value).strip()
                summary_value = modification.get("summary") or update_payload.get("summary")
                if summary_value is not None:
                    fields["summary"] = str(summary_value).strip()
                category_value = modification.get("category") or update_payload.get("category")
                if category_value:
                    fields["category"] = normalize_lore_category(category_value).value
                priority_value = modification.get("new_priority") or update_payload.get("priority")
                if priority_value:
                    fields["priority"] = normalize_lore_priority(priority_value).value
                for list_field in [
                    "keywords",
                    "tags",
                    "constraints",
                    "related_characters",
                    "related_locations",
                    "related_items",
                    "forbidden_actions",
                ]:
                    if list_field in modification or list_field in update_payload:
                        fields[list_field] = json.dumps(self._normalize_string_list(
                            modification.get(list_field, update_payload.get(list_field))
                        ))
                if not fields:
                    return {"success": False, "error": "修改建议缺少可执行字段"}

                set_clause = ", ".join([f"{field} = :{field}" for field in fields])
                params = {
                    **fields,
                    "id": target_id,
                    "project_id": project_id,
                    "updated_at": datetime.now(),
                }
                await postgres_db.execute_write(f"""
                    UPDATE lore_entries
                    SET {set_clause}, updated_at = :updated_at
                    WHERE id = CAST(:id AS UUID) AND project_id = CAST(:project_id AS UUID)
                """, params)
                self.invalidate_context_cache(project_id)
                return {"success": True, "message": "已更新现有设定"}

            elif mod_type == "priority" and target_id:
                # 调整优先级
                new_priority = normalize_lore_priority(modification.get("new_priority", "standard")).value
                await postgres_db.execute_write("""
                    UPDATE lore_entries
                    SET priority = :priority, updated_at = :updated_at
                    WHERE id = CAST(:id AS UUID) AND project_id = CAST(:project_id AS UUID)
                """, {
                    "id": target_id,
                    "project_id": project_id,
                    "priority": new_priority,
                    "updated_at": datetime.now(),
                })
                self.invalidate_context_cache(project_id)
                return {"success": True, "message": f"已调整设定优先级为 {new_priority}"}

            elif mod_type == "missing":
                # 添加缺失的设定
                duplicate = None
                if hasattr(postgres_db, "find_duplicate_lore"):
                    duplicate = await postgres_db.find_duplicate_lore(
                        project_id,
                        modification.get("suggested_title", "新设定"),
                        suggested_content,
                    )
                if duplicate:
                    logger.info(f"跳过重复设定: {modification.get('suggested_title', '新设定')} -> {duplicate.get('id')}")
                    return {"success": True, "message": f"设定已存在，复用现有条目: {duplicate.get('id')}"}

                modification = self._normalize_lore_interconnection_payload(modification)
                lore_entry = {
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "title": modification.get("suggested_title", "新设定"),
                    "category": normalize_lore_category(modification.get("category", "custom")).value,
                    "priority": normalize_lore_priority(modification.get("priority", "standard")).value,
                    "content": suggested_content,
                    "summary": modification.get("summary", ""),
                    "keywords": json.dumps(modification.get("keywords", [])),
                    "tags": json.dumps(modification.get("tags", [])),
                    "constraints": json.dumps(modification.get("constraints", [])),
                    "related_characters": json.dumps(modification.get("related_characters", [])),
                    "related_locations": json.dumps(modification.get("related_locations", [])),
                    "related_items": json.dumps(modification.get("related_items", [])),
                    "forbidden_actions": json.dumps(modification.get("forbidden_actions", [])),
                    "source": self._build_lore_source_with_metadata(modification),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
                await postgres_db.execute_write("""
                    INSERT INTO lore_entries (id, project_id, title, category, priority, content, summary, keywords, tags, constraints, related_characters, related_locations, related_items, forbidden_actions, source, created_at, updated_at)
                    VALUES (:id, CAST(:project_id AS UUID), :title, :category, :priority, :content, :summary, :keywords, :tags, :constraints, :related_characters, :related_locations, :related_items, :forbidden_actions, :source, :created_at, :updated_at)
                """, lore_entry)
                self.invalidate_context_cache(project_id)
                return {"success": True, "message": f"已添加新设定: {lore_entry['title']}"}

            elif mod_type == "relation" and target_id:
                # 更新关联关系
                related = modification.get("related_entities", [])
                await postgres_db.execute_write("""
                    UPDATE lore_entries
                    SET related_characters = :related, updated_at = :updated_at
                    WHERE id = CAST(:id AS UUID) AND project_id = CAST(:project_id AS UUID)
                """, {
                    "id": target_id,
                    "project_id": project_id,
                    "related": json.dumps(self._normalize_string_list(related)),
                    "updated_at": datetime.now(),
                })
                self.invalidate_context_cache(project_id)
                return {"success": True, "message": "已更新设定关联"}

            else:
                return {"success": False, "error": f"未知的修改类型: {mod_type}"}

        except Exception as e:
            logger.error(f"[SettingAgent] 执行设定修改失败: {e}")
            return {"success": False, "error": str(e)}

    def _parse_character_list_value(self, value: Any) -> List[Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                return []
        return value if isinstance(value, list) else []

    def _parse_character_dict_value(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                return {}
        return value if isinstance(value, dict) else {}

    def _has_meaningful_character_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return True

    def _merge_character_payload(
        self,
        existing_character: Optional[Dict[str, Any]],
        incoming_character: Dict[str, Any],
        project_id: str,
    ) -> Dict[str, Any]:
        merged = dict(existing_character or {})
        merged["project_id"] = project_id

        list_fields = [
            "goals",
            "relationships",
            "lexicon",
            "forbidden_words",
            "voice_samples",
            "inventory",
            "agent_goals",
            "agent_memory",
        ]
        dict_fields = ["attributes", "key_relationships"]
        scalar_fields = [
            "id",
            "name",
            "importance_tier",
            "description",
            "appearance",
            "personality",
            "background_story",
            "speech_pattern",
            "age",
            "gender",
            "narrative_weight",
            "story_arc_role",
            "plot_priority",
            "has_agent",
            "agent_enabled",
            "world_id",
            "current_location",
            "current_region_id",
            "current_location_reason",
        ]

        for field in scalar_fields:
            if field in incoming_character and self._has_meaningful_character_value(incoming_character.get(field)):
                merged[field] = incoming_character[field]

        for field in list_fields:
            if field in incoming_character:
                parsed_value = self._parse_character_list_value(incoming_character.get(field))
                if self._has_meaningful_character_value(parsed_value):
                    merged[field] = parsed_value
                elif field not in merged:
                    merged[field] = []
            elif field in merged:
                merged[field] = self._parse_character_list_value(merged.get(field))
            else:
                merged[field] = []

        for field in dict_fields:
            if field in incoming_character:
                parsed_value = self._parse_character_dict_value(incoming_character.get(field))
                if self._has_meaningful_character_value(parsed_value):
                    merged[field] = parsed_value
                elif field not in merged:
                    merged[field] = {}
            elif field in merged:
                merged[field] = self._parse_character_dict_value(merged.get(field))
            else:
                merged[field] = {}

        if "age" in incoming_character and incoming_character.get("age") is None and "age" not in merged:
            merged["age"] = None

        return merged

    async def _extract_characters_from_conversation(
        self,
        project_id: str,
        session: SettingAgentSession,
    ) -> List[Dict[str, Any]]:
        """
        从对话中提取新角色信息（需要用户确认）

        Args:
            project_id: 项目 ID
            session: 会话对象

        Returns:
            List[Dict]: 待确认的角色列表
        """
        recent_messages = session.conversation_history[-6:]
        if len(recent_messages) < 2:
            return []

        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in recent_messages
        ])

        extraction_prompt = self._build_character_extraction_prompt(history_text)

        try:
            from app.models.agent_output_schemas import SettingPendingCharactersExtractionSchema
            from app.services.structured_llm import StructuredOutputError

            try:
                parsed = await self._call_structured(
                    SettingPendingCharactersExtractionSchema,
                    extraction_prompt,
                    project_id=project_id,
                )
                characters = [item.model_dump() for item in parsed.characters]
            except StructuredOutputError as e:
                logger.warning(f"提取角色 structured 失败：{e}")
                return []

            if not characters:
                return []

            valid_characters = []
            for char_data in characters:
                if not char_data.get("name"):
                    continue
                valid_characters.append({
                    "name": char_data.get("name", ""),
                    "importance_tier": char_data.get("importance_tier", "npc"),
                    "description": char_data.get("description", ""),
                    "appearance": char_data.get("appearance", ""),
                    "personality": char_data.get("personality", ""),
                    "background_story": char_data.get("background_story", ""),
                    "speech_pattern": char_data.get("speech_pattern", ""),
                    "age": char_data.get("age"),
                    "gender": char_data.get("gender", ""),
                    "goals": self._parse_character_list_value(char_data.get("goals")),
                    "relationships": self._parse_character_list_value(char_data.get("relationships")),
                    "key_relationships": self._parse_character_dict_value(char_data.get("key_relationships")),
                    "lexicon": self._parse_character_list_value(char_data.get("lexicon")),
                    "forbidden_words": self._parse_character_list_value(char_data.get("forbidden_words")),
                    "voice_samples": self._parse_character_list_value(char_data.get("voice_samples")),
                    "attributes": self._parse_character_dict_value(char_data.get("attributes")),
                    "inventory": self._parse_character_list_value(char_data.get("inventory")),
                    "narrative_weight": char_data.get("narrative_weight"),
                    "story_arc_role": char_data.get("story_arc_role"),
                    "plot_priority": char_data.get("plot_priority"),
                    "has_agent": char_data.get("has_agent"),
                    "agent_enabled": char_data.get("agent_enabled"),
                    "agent_goals": self._parse_character_list_value(char_data.get("agent_goals")),
                    "agent_memory": self._parse_character_list_value(char_data.get("agent_memory")),
                })

            if valid_characters:
                logger.info(f"从对话中提取 {len(valid_characters)} 个待确认角色")

            return valid_characters

        except Exception as e:
            logger.error(f"提取角色失败: {e}")
            return []

    async def save_pending_characters(
        self,
        project_id: str,
        characters: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> int:
        """
        保存用户确认的角色到数据库

        Args:
            project_id: 项目 ID
            characters: 待保存的角色列表

        Returns:
            int: 保存的数量
        """
        from app.api.app import postgres_db
        from app.api.routes.characters import _auto_configure_character_agent, _derive_role_from_tier

        if not postgres_db:
            return 0

        saved_count = 0
        session = await self.get_or_create_session(project_id, session_id=session_id) if session_id else None
        operation, replay_count = await self._begin_save_operation(
            postgres_db,
            project_id,
            session.id if session else session_id,
            request_id,
            "setting_save_characters",
            "character",
            characters,
        )
        if replay_count is not None:
            return replay_count
        for char_data in characters:
            name = (char_data.get("name") or "").strip()
            if not name:
                continue
            if await self._should_skip_saved_pending_item(postgres_db, session, "character", char_data):
                continue

            try:
                existing_character = None
                existing_id = char_data.get("id")
                if existing_id:
                    existing_character = await postgres_db.get_character(existing_id)

                if not existing_character:
                    existing_character = await postgres_db.get_character_by_project_and_name(project_id, name)

                merged_character = self._merge_character_payload(existing_character, char_data, project_id)
                merged_character["name"] = name
                merged_character["status"] = merged_character.get("status") or "active"

                if existing_character:
                    merged_character["id"] = existing_character.get("id")
                    if existing_character.get("created_at"):
                        merged_character["created_at"] = existing_character.get("created_at")
                else:
                    merged_character["id"] = merged_character.get("id") or str(uuid.uuid4())
                    merged_character["created_at"] = datetime.now()

                importance_tier = merged_character.get("importance_tier") or "npc"
                merged_character["importance_tier"] = importance_tier
                merged_character["role"] = _derive_role_from_tier(importance_tier)
                merged_character["updated_at"] = datetime.now()

                merged_character = await _auto_configure_character_agent(merged_character)
                await postgres_db.save_character(merged_character)
                from app.services.graph_projection_service import enqueue_graph_projection_best_effort
                await enqueue_graph_projection_best_effort("character", merged_character)
                if session:
                    await postgres_db.mark_setting_agent_pending_item_saved(
                        session.id,
                        "character",
                        self._fingerprint_payload(char_data),
                        merged_character["id"],
                    )

                saved_count += 1
                logger.info(f"保存用户确认的角色: {name}")
            except Exception as e:
                logger.error(f"保存角色失败: {e}")

        # 保存成功后清除缓存，避免重复保存，并刷新上下文缓存
        if saved_count > 0:
            self._clear_cached_pending_characters(project_id)
            self.invalidate_context_cache(project_id)
        await self._complete_save_operation(postgres_db, operation, saved_count)

        return saved_count

    # ==================== 智能推断方法 ====================

    def _build_world_type_inference_prompt(self, history_text: str) -> str:
        prompt_asset = self._load_md_prompt_content(self.SETTING_WORLD_TYPE_INFERENCE_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】请从对话中推断故事世界类型；"
                "仅返回 fantasy、scifi、modern、historical、wuxia 或 unknown。"
            )
        return "\n\n".join([
            prompt_asset,
            f"## 对话内容\n{history_text}",
        ]).strip()

    def _build_tone_inference_prompt(self, history_text: str) -> str:
        prompt_asset = self._load_md_prompt_content(self.SETTING_TONE_INFERENCE_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】请从对话中推断故事叙事基调；"
                "仅返回 serious、lighthearted、dark、comedic、adventurous 或 unknown。"
            )
        return "\n\n".join([
            prompt_asset,
            f"## 对话内容\n{history_text}",
        ]).strip()

    async def infer_world_type(self, conversation_history: List[Dict[str, Any]]) -> Optional[str]:
        """
        从对话历史中推断世界类型

        Args:
            conversation_history: 对话历史

        Returns:
            Optional[str]: 推断的世界类型 (fantasy/scifi/modern/historical/wuxia)
        """
        if not conversation_history:
            return None

        # 构建分析提示
        recent_messages = conversation_history[-5:]  # 最近5条消息
        history_text = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in recent_messages
        ])

        prompt = self._build_world_type_inference_prompt(history_text)

        try:
            result = await self._call_llm_simple(prompt)
            result = result.strip().lower()

            valid_types = ["fantasy", "scifi", "modern", "historical", "wuxia"]
            if result in valid_types:
                logger.info(f"推断世界类型: {result}")
                return result
            return None
        except Exception as e:
            logger.error(f"推断世界类型失败: {e}")
            return None

    async def infer_tone(self, conversation_history: List[Dict[str, Any]]) -> Optional[str]:
        """
        从对话历史中推断叙事基调

        Args:
            conversation_history: 对话历史

        Returns:
            Optional[str]: 推断的叙事基调 (serious/lighthearted/dark/comedic/adventurous)
        """
        if not conversation_history:
            return None

        # 构建分析提示
        recent_messages = conversation_history[-5:]
        history_text = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in recent_messages
        ])

        prompt = self._build_tone_inference_prompt(history_text)

        try:
            result = await self._call_llm_simple(prompt)
            result = result.strip().lower()

            valid_tones = ["serious", "lighthearted", "dark", "comedic", "adventurous"]
            if result in valid_tones:
                logger.info(f"推断叙事基调: {result}")
                return result
            return None
        except Exception as e:
            logger.error(f"推断叙事基调失败: {e}")
            return None

    async def update_project_metadata(
        self,
        project_id: str,
        world_type: Optional[str] = None,
        tone: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        更新项目元数据

        Args:
            project_id: 项目 ID
            world_type: 世界类型
            tone: 叙事基调
            additional_metadata: 其他元数据

        Returns:
            bool: 是否更新成功
        """
        try:
            from app.api.app import postgres_db

            if not postgres_db:
                logger.warning("数据库未连接，无法更新项目元数据")
                return False

            if not (world_type or tone or additional_metadata):
                return True

            # 从项目元数据中获取现有值
            project = await postgres_db.get_project(project_id)
            if not project:
                logger.warning(f"项目不存在: {project_id}")
                return False

            metadata = project.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}

            if additional_metadata:
                metadata.update(additional_metadata)
            if world_type:
                metadata["world_type"] = world_type
            if tone:
                metadata["tone"] = tone

            update_data = {"metadata": metadata}
            await postgres_db.update_project(project_id, update_data)

            logger.info(f"更新项目 {project_id} 元数据: {update_data}")
            return True

        except Exception as e:
            logger.error(f"更新项目元数据失败: {e}")
            return False

    async def analyze_and_update_project_metadata(
        self,
        project_id: str,
        conversation_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        分析对话并自动更新项目元数据

        Args:
            project_id: 项目 ID
            conversation_history: 对话历史

        Returns:
            Dict: 分析和更新结果
        """
        results = {
            "world_type": None,
            "tone": None,
            "updated": False,
        }

        # 推断世界类型
        world_type = await self.infer_world_type(conversation_history)
        if world_type:
            results["world_type"] = world_type

        # 推断叙事基调
        tone = await self.infer_tone(conversation_history)
        if tone:
            results["tone"] = tone

        # 如果有推断结果，更新项目元数据
        if world_type or tone:
            success = await self.update_project_metadata(
                project_id,
                world_type=world_type,
                tone=tone,
            )
            results["updated"] = success

        return results

    # ==================== 角色性格生成 ====================

    async def generate_character_personality(
        self,
        project_id: str,
        character_data: Dict[str, Any],
        existing_characters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        为角色生成性格建议

        Args:
            project_id: 项目 ID
            character_data: 角色数据（name, role, description, background 等）
            existing_characters: 现有角色列表（用于避免重复）

        Returns:
            Dict: 生成的性格数据
        """
        # 获取项目设定作为上下文
        project_context = await self._get_project_context(project_id)

        # 构建提示
        prompt = self._build_personality_generation_prompt(character_data, existing_characters, project_context)

        try:
            from app.models.agent_output_schemas import SettingPersonalityGenerationSchema
            from app.services.structured_llm import StructuredOutputError

            try:
                parsed = await self._call_structured(
                    SettingPersonalityGenerationSchema,
                    prompt,
                    project_id=project_id,
                )
                personality_data = parsed.model_dump()
            except StructuredOutputError as e:
                logger.error(f"生成角色性格 structured 失败: {e}")
                return {
                    "success": False,
                    "error": "解析失败",
                    "personality": "",
                    "speech_pattern": "",
                }

            logger.info(
                "为角色 '%s' 生成性格: %s",
                character_data.get('name'),
                personality_data.get('personality', ''),
            )

            return {
                "success": True,
                "appearance": personality_data.get("appearance", ""),
                "personality": personality_data.get("personality", ""),
                "speech_pattern": personality_data.get("speech_pattern", ""),
                "personality_traits": personality_data.get("personality_traits", []),
                "agent_goals": personality_data.get("agent_goals", []),
                "agent_memory": personality_data.get("agent_memory", []),
            }

        except Exception as e:
            logger.error(f"生成角色性格失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "personality": "",
                "speech_pattern": "",
            }

    async def _get_project_context(self, project_id: str) -> str:
        """获取项目设定上下文"""
        try:
            from app.api.app import postgres_db
            if not postgres_db:
                return ""

            # 获取项目信息
            project = await postgres_db.get_project(project_id)
            if not project:
                return ""

            context_parts = []

            # 添加项目基本信息
            if project.get("title"):
                context_parts.append(f"作品名称：{project['title']}")
            if project.get("description"):
                context_parts.append(f"作品简介：{project['description']}")

            # 添加世界类型和基调（优先从 worlds 表读取）
            metadata = project.get("metadata", {})
            if metadata.get("world_type"):
                context_parts.append(f"世界类型：{metadata['world_type']}")
            if metadata.get("tone"):
                context_parts.append(f"叙事基调：{metadata['tone']}")

            # 从世界管理表加载世界观信息
            try:
                worlds = await postgres_db.get_all_worlds(project_id=project_id, limit=1)
                if worlds:
                    world = worlds[0]
                    if world.get("description"):
                        context_parts.append(f"\n【世界观】{world['description']}")
                    if world.get("power_system"):
                        context_parts.append(f"【力量体系】{world['power_system']}")
                    if world.get("technology_level"):
                        context_parts.append(f"【科技水平】{world['technology_level']}")
                    if world.get("history"):
                        context_parts.append(f"【世界历史】{world['history']}")
                    if world.get("geography"):
                        context_parts.append(f"【地理概况】{world['geography']}")
                    # 添加世界规则
                    rules = world.get("rules", [])
                    if rules:
                        rules_str = ", ".join([r.get("name", "") for r in rules if isinstance(r, dict)])
                        if rules_str:
                            context_parts.append(f"【核心规则】{rules_str}")
            except Exception as e:
                logger.warning(f"加载世界管理信息失败: {e}")

            # 获取关键设定
            try:
                lores = await postgres_db.execute_query(
                    "SELECT title, category, priority, summary, content FROM lore_entries WHERE project_id = CAST(:project_id AS UUID) ORDER BY priority, created_at DESC",
                    {"project_id": project_id}
                )
                if lores:
                    lore_lines = []
                    for lore in lores:
                        lore_lines.append(f"- [{lore.get('priority', 'standard')}] {lore.get('title', '')} ({lore.get('category', 'custom')})")
                        if lore.get("summary"):
                            lore_lines.append(f"  摘要：{lore['summary']}")
                        if lore.get("content"):
                            lore_lines.append(f"  内容：{lore['content']}")
                    context_parts.append("\n关键设定：\n" + "\n".join(lore_lines))
            except Exception:
                pass  # lore_entries 表可能不存在

            return "\n".join(context_parts)

        except Exception as e:
            logger.warning(f"获取项目上下文失败: {e}")
            return ""

    def _build_personality_generation_prompt(
        self,
        character_data: Dict[str, Any],
        existing_characters: Optional[List[Dict[str, Any]]] = None,
        project_context: str = "",
    ) -> str:
        """构建性格生成提示"""

        name = character_data.get("name", "")
        role = character_data.get("role", "supporting")
        description = character_data.get("description", "")
        background = character_data.get("background_story") or character_data.get("background", "")

        # 角色定位说明
        role_descriptions = {
            "main": "主角 - 故事的核心人物，需要鲜明的性格和成长空间",
            "antagonist": "反派 - 与主角对立的角色，需要有魅力的反派特质",
            "supporting": "重要配角 - 支持主线发展，有自己的人物弧光",
            "npc": "普通配角 - 丰富故事世界，性格可以相对简单",
        }

        # 现有角色性格（避免重复）
        existing_personalities = ""
        if existing_characters:
            personalities = []
            for char in existing_characters:
                if char.get("personality"):
                    personalities.append(f"- {char.get('name')}: {char.get('personality')}")
            if personalities:
                existing_personalities = f"\n\n现有角色性格（避免过于相似）：\n" + "\n".join(personalities)

        prompt = self._build_personality_generation_prompt_from_context(
            name=name,
            role=role,
            description=description,
            background=background,
            existing_personalities=existing_personalities,
            project_context=project_context,
            role_descriptions=role_descriptions,
        )
        return prompt

    async def _build_management_system_prompt(self, session: SettingAgentSession) -> str:
        """构建管理模式系统提示"""
        # 获取项目信息以构建世界类型相关的提示
        world_type_hint = ""
        tone_hint = ""

        if session.project_id:
            try:
                from app.api.app import postgres_db
                if postgres_db:
                    # 尝试从 worlds 表获取世界类型
                    worlds = await postgres_db.get_all_worlds(project_id=session.project_id, limit=1)
                    if worlds and len(worlds) > 0:
                        world = worlds[0]
                        wt = world.get("world_type", "")
                        if wt:
                            world_type_hint = self._get_world_type_hint(wt)
                        tone_hint = world.get("tone", "")
                    else:
                        # 尝试从项目 metadata 获取
                        project = await postgres_db.get_project(session.project_id)
                        if project:
                            metadata = project.get("metadata", {})
                            wt = metadata.get("world_type", "")
                            if wt:
                                world_type_hint = self._get_world_type_hint(wt)
                            tone_hint = metadata.get("tone", "")
            except Exception:
                pass  # 忽略错误，使用默认提示

        prompt_asset = self._load_md_prompt_content(self.SETTING_MANAGEMENT_SYSTEM_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】你是一个专业的长篇网络小说设定管理者（Setting Agent）。"
                "请维护世界观、角色和设定冲突，并只提供待确认建议。"
            )
        return "\n\n".join([
            prompt_asset,
            f"【世界类型提示】\n{world_type_hint or '未指定'}",
            f"【叙事基调提示】\n{tone_hint or '未指定'}",
        ]).strip()

    async def _extract_keywords_from_message(self, message: str) -> List[str]:
        """
        从用户消息中提取关键词

        Args:
            message: 用户消息

        Returns:
            List[str]: 关键词列表
        """
        import re

        # 简单的关键词提取规则
        keywords = []

        # 1. 提取引号内的内容（用户明确提到的名词）
        quoted = re.findall(r'[""「」『』]([^""「」『』]+)[""「」『』]', message)
        keywords.extend(quoted)

        # 2. 提取中文专有名词（2-6个字的词）
        # 常见设定类型关键词
        lore_patterns = [
            r'([\u4e00-\u9fa5]{2,6}(?:设定|规则|体系|系统|能力|力量|技能|功法|境界|种族|门派|势力))',
            r'(设定[：:]\s*([\u4e00-\u9fa5]{2,6}))',
            r'(关于[《【]?([\u4e00-\u9fa5]{2,6})[》】]?)',
        ]
        for pattern in lore_patterns:
            matches = re.findall(pattern, message)
            for match in matches:
                if isinstance(match, tuple):
                    keywords.extend([m for m in match if m])
                else:
                    keywords.append(match)

        # 3. 提取关键实体名词（常见的设定类别）
        entity_keywords = [
            "修真", "魔法", "功法", "境界", "灵根", "血脉", "天赋",
            "种族", "势力", "门派", "宗门", "家族", "帝国",
            "主角", "反派", "配角", "导师", "恋人",
            "武器", "法宝", "神器", "丹药", "灵石",
            "世界", "大陆", "区域", "城市", "秘境",
        ]
        for kw in entity_keywords:
            if kw in message:
                keywords.append(kw)

        # 4. 去重并返回
        unique_keywords = list(dict.fromkeys(keywords))
        return unique_keywords

    def _get_world_type_hint(self, world_type: str) -> str:
        """根据世界类型返回对应的设定要点提示"""
        hints = {
            "scifi": """【当前世界类型：科幻】
- 设定必须符合科学逻辑，可以合理推测但不能违反已知科学原理
- 科技水平要保持一致性（不要出现跨越太大代际的技术）
- 关注太空探索、人工智能、基因工程、赛博格等科幻元素
- 力量来源可以是：高科技装备、基因改造、意识上传、AI辅助等
- 避免出现魔法、灵气、修真等奇幻/玄幻元素""",

            "fantasy": """【当前世界类型：奇幻】
- 设定可以包含魔法、精灵、怪物、异世界等元素
- 力量来源可以是：魔法、元素、契约、血脉等
- 保持魔法规则的内在逻辑一致性
- 避免出现过于现代化的科技元素""",

            "modern": """【当前世界类型：现代】
- 设定必须符合当代社会现实
- 避免出现魔法、修真、超自然力量等元素
- 可以涉及都市、社会议题、职场等现实题材""",

            "historical": """【当前世界类型：历史】
- 设定必须符合历史背景，可以合理虚构但要有历史依据
- 避免出现与历史时代不符的元素
- 了解该历史时期的科技水平、社会制度、风俗习惯等""",

            "wuxia": """【当前世界类型：武侠】
- 设定要符合武侠世界的江湖规则
- 力量来源：内功、招式、兵器、暗器等
- 关注门派、江湖恩怨、武林秘籍等元素
- 避免出现魔法、灵气、仙人等超出武侠范畴的元素""",
        }
        return hints.get(world_type.lower(), "")

    def _get_tone_hint(self, tone: str) -> str:
        """根据叙事基调返回对应的风格提示"""
        hints = {
            "serious": "风格要严肃、严谨，注重逻辑合理性",
            "light": "风格可以轻松幽默，但不要过于随意",
            "dark": "风格可以黑暗、深刻，但要有积极的一面",
            "humorous": "风格可以幽默诙谐，但要注意情节推进",
            "epic": "风格要宏大、壮阔，注重史诗感",
        }
        return hints.get(tone.lower(), "")

    async def _build_chat_context(
        self,
        session: SettingAgentSession,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建聊天上下文"""
        parts = []

        # 添加项目相关信息（世界管理、角色、伏笔等）
        if session.project_id:
            logger.info(f"[SettingAgent] _build_chat_context: 开始获取项目上下文, project_id={session.project_id}")
            project_context = await self._get_comprehensive_project_context(session.project_id)
            if project_context:
                logger.info(f"[SettingAgent] _build_chat_context: 获取到项目上下文 {len(project_context)} 字符")
                parts.append(f"【项目综合信息】\n{project_context}")
            else:
                logger.warning(f"[SettingAgent] _build_chat_context: 项目上下文为空！")

        # 添加对话历史
        if session.conversation_history:
            history = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in session.conversation_history[-10:]
            ])
            parts.append(f"【最近对话】\n{history}")

        # 添加待处理冲突
        if session.pending_conflicts:
            conflicts_str = "\n".join([
                f"- {c.description} (严重程度: {c.severity.value})"
                for c in session.pending_conflicts
            ])
            parts.append(f"【待处理冲突】\n{conflicts_str}")

        # 添加额外上下文
        if extra_context:
            parts.append(f"【额外信息】\n{json.dumps(extra_context, ensure_ascii=False)}")

        return "\n\n".join(parts)

    async def _get_comprehensive_project_context(self, project_id: str) -> str:
        """获取项目综合信息（世界管理、角色、伏笔、已有设定等）- 返回字符串格式"""
        sections = await self._get_context_sections(project_id)
        return "\n\n".join([f"【{k}】\n{v}" for k, v in sections.items() if v])

    async def _get_context_sections(
        self,
        project_id: str,
        user_message: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        获取项目上下文的分段信息（智能检索版本）

        Args:
            project_id: 项目 ID
            user_message: 用户消息（用于智能检索相关设定）

        Returns:
            Dict[str, str]: 分段的上下文信息
        """
        import asyncpg
        from app.config import settings

        # 直接创建数据库连接
        try:
            db_url = settings.database_url.replace('+asyncpg', '')
            conn = await asyncpg.connect(db_url)
        except Exception as e:
            logger.warning(f"无法连接数据库: {e}")
            return {}

        sections = {}

        # 记录加载上下文
        logger.info(f"[SettingAgent] 开始为项目 {project_id} 构建智能上下文")

        try:
            # 1. 世界管理信息
            worlds = await conn.fetch('SELECT * FROM worlds WHERE project_id = $1', project_id)
            if worlds:
                logger.info(f"[SettingAgent] 加载世界管理: {len(worlds)} 个")
                world_info = []
                world_type = None
                for w in worlds:
                    info = f"世界：{w['name'] or '未命名'}"
                    if w.get('description'):
                        info += f"\n  描述：{w['description']}"
                    if w.get('world_type'):
                        info += f"\n  类型：{w['world_type']}"
                        world_type = w['world_type']
                    if w.get('tone'):
                        info += f"\n  基调：{w['tone']}"
                    # 新增：内容风格标签
                    content_styles = w.get('content_styles')
                    if content_styles:
                        if isinstance(content_styles, str):
                            try:
                                content_styles = json.loads(content_styles)
                            except:
                                content_styles = []
                        if isinstance(content_styles, list) and len(content_styles) > 0:
                            info += f"\n  内容风格：{', '.join(content_styles)}"
                    # 新增：主角类型标签
                    protagonist_types = w.get('protagonist_types')
                    if protagonist_types:
                        if isinstance(protagonist_types, str):
                            try:
                                protagonist_types = json.loads(protagonist_types)
                            except:
                                protagonist_types = []
                        if isinstance(protagonist_types, list) and len(protagonist_types) > 0:
                            info += f"\n  主角类型：{', '.join(protagonist_types)}"
                    # 新增：角色人设标签
                    character_archetypes = w.get('character_archetypes')
                    if character_archetypes:
                        if isinstance(character_archetypes, str):
                            try:
                                character_archetypes = json.loads(character_archetypes)
                            except:
                                character_archetypes = []
                        if isinstance(character_archetypes, list) and len(character_archetypes) > 0:
                            info += f"\n  角色人设模板：{', '.join(character_archetypes)}"
                    # 新增：战斗能力标签
                    power_types = w.get('power_types')
                    if power_types:
                        if isinstance(power_types, str):
                            try:
                                power_types = json.loads(power_types)
                            except:
                                power_types = []
                        if isinstance(power_types, list) and len(power_types) > 0:
                            info += f"\n  战斗能力：{', '.join(power_types)}"
                    if w.get('power_system'):
                        info += f"\n  力量体系：{w['power_system']}"
                    if w.get('technology_level'):
                        info += f"\n  科技水平：{w['technology_level']}"
                    if w.get('history'):
                        info += f"\n  历史：{w['history']}"
                    if w.get('geography'):
                        info += f"\n  地理：{w['geography']}"
                    # 加载势力信息
                    factions = w.get('factions')
                    if factions:
                        if isinstance(factions, str):
                            try:
                                factions = json.loads(factions)
                            except:
                                factions = []
                        if isinstance(factions, list) and len(factions) > 0:
                            faction_names = [f.get('name', '') for f in factions if isinstance(f, dict) and f.get('name')]
                            if faction_names:
                                info += f"\n  主要势力：{', '.join(faction_names)}"
                    # 加载世界规则
                    rules = w.get('rules')
                    if rules:
                        if isinstance(rules, str):
                            try:
                                rules = json.loads(rules)
                            except:
                                rules = []
                        if isinstance(rules, list) and len(rules) > 0:
                            rule_names = [r.get('name', '') for r in rules if isinstance(r, dict) and r.get('name')]
                            if rule_names:
                                info += f"\n  世界规则：{', '.join(rule_names)}"
                    world_info.append(info)
                if world_info:
                    sections["世界管理"] = "\n\n".join(world_info)
                    sections["_world_type"] = world_type or ""

            # 2. 设定库 - 智能检索相关设定
            try:
                # 2.1 始终加载宪法级规则（不可违反）
                constitutional_lores = await conn.fetch("""
                    SELECT id, title, category, priority, summary, content, keywords
                    FROM lore_entries
                    WHERE project_id = $1 AND priority = 'constitutional'
                    ORDER BY created_at
                """, project_id)

                # 2.2 智能检索相关设定
                relevant_lore_ids = set()
                if user_message:
                    # 从用户消息中提取关键词
                    extracted_keywords = await self._extract_keywords_from_message(user_message)

                    # 使用智能检索
                    try:
                        from app.services.lore_index_service import get_lore_index_service
                        lore_index = get_lore_index_service()
                        relevant_ids = await lore_index.smart_search(
                            project_id=project_id,
                            query=user_message,
                            keywords=extracted_keywords,
                            limit=20,
                        )
                        relevant_lore_ids.update(relevant_ids)
                        logger.info(f"[SettingAgent] 智能检索到 {len(relevant_lore_ids)} 条相关设定")
                    except Exception as e:
                        logger.warning(f"[SettingAgent] 智能检索失败，回退到关键词匹配: {e}")
                        # 回退：直接在数据库中搜索关键词
                        if extracted_keywords:
                            for kw in extracted_keywords:
                                matching = await conn.fetch("""
                                    SELECT id FROM lore_entries
                                    WHERE project_id = $1
                                    AND (keywords::text ILIKE $2 OR title ILIKE $2 OR content ILIKE $2)
                                """, project_id, f"%{kw}%")
                                for m in matching:
                                    relevant_lore_ids.add(str(m['id']))

                # 2.3 获取宪法级设定的 ID（排除重复）
                constitutional_ids = {str(l['id']) for l in constitutional_lores}

                # 2.4 获取相关设定的完整内容
                relevant_lores = []
                if relevant_lore_ids:
                    # 排除已在宪法级中出现的
                    ids_to_fetch = [lid for lid in relevant_lore_ids if lid not in constitutional_ids]
                    if ids_to_fetch:
                        # 构建查询
                        placeholders = ",".join([f"'{lid}'" for lid in ids_to_fetch])
                        relevant_lores = await conn.fetch(f"""
                            SELECT id, title, category, priority, summary, content, keywords
                            FROM lore_entries
                            WHERE id::text IN ({placeholders})
                        """)

                # 2.5 构建设定库上下文
                lore_info = []

                # 宪法级设定（完整内容）
                if constitutional_lores:
                    lore_info.append("【宪法级设定 - 不可违反】")
                    for lore in constitutional_lores:
                        content = lore.get('content') or lore.get('summary') or ''
                        lore_info.append(f"【{lore['title']}】")
                        lore_info.append(f"类别: {lore['category']}")
                        lore_info.append(f"内容: {content}")
                        if lore.get('keywords'):
                            try:
                                kw = json.loads(lore['keywords']) if isinstance(lore['keywords'], str) else lore['keywords']
                                if kw:
                                    lore_info.append(f"关键词: {', '.join(str(item) for item in kw)}")
                            except:
                                pass
                        lore_info.append("")
                    logger.info(f"[SettingAgent] 宪法级设定: {len(constitutional_lores)} 条")

                # 相关设定（根据用户问题智能检索）
                if relevant_lores:
                    lore_info.append(f"【相关设定（根据您的问题检索）】")
                    for lore in relevant_lores:
                        content = lore.get('content', '')
                        summary = lore.get('summary', '')
                        info_line = f"- {lore['title']} [{lore['priority']}] ({lore['category']})"
                        if summary:
                            info_line += f"\n  摘要: {summary}"
                        info_line += f"\n  内容: {content}"
                        lore_info.append(info_line)
                    logger.info(f"[SettingAgent] 相关设定: {len(relevant_lores)} 条")

                if lore_info:
                    sections["设定库"] = "\n".join(lore_info)

            except Exception as e:
                logger.warning(f"获取设定失败: {e}")

            # 3. 角色信息
            try:
                characters = await conn.fetch("""
                    SELECT name, role, description
                    FROM characters
                    WHERE project_id = $1
                    ORDER BY created_at DESC
                """, project_id)

                if characters:
                    char_info = []
                    for char in characters:
                        info = f"- {char['name']} ({char['role'] or '配角'})"
                        if char.get('description'):
                            info += f"：{char['description']}"
                        char_info.append(info)
                    sections["角色列表"] = "\n".join(char_info)
            except Exception as e:
                logger.warning(f"获取 characters 失败: {e}")

            # 4. 伏笔信息
            try:
                hooks = await conn.fetch("""
                    SELECT title, hook_type, status, plant_chapter, resolution_chapter
                    FROM hooks
                    WHERE project_id = $1
                    ORDER BY created_at DESC
                """, project_id)

                if hooks:
                    hook_info = []
                    for hook in hooks:
                        info = f"- {hook['title']} [{hook['hook_type'] or '未知'}]"
                        if hook.get('status'):
                            info += f" 状态：{hook['status']}"
                        hook_info.append(info)
                    sections["伏笔列表"] = "\n".join(hook_info)
            except Exception as e:
                logger.warning(f"获取 hooks 失败: {e}")

            # 5. 章节大纲信息
            try:
                outlines = await conn.fetch("""
                    SELECT chapter_number, title, summary, status
                    FROM chapter_outlines
                    WHERE project_id = $1
                    AND status IN ('draft', 'approved')
                    ORDER BY chapter_number
                """, project_id)

                if outlines:
                    outline_info = []
                    for outline in outlines:
                        info = f"- 第{outline['chapter_number']}章：{outline['title']} [{outline['status']}]"
                        if outline.get('summary'):
                            info += f"\n  摘要：{outline['summary']}"
                        outline_info.append(info)
                    sections["章节大纲"] = "\n".join(outline_info)
            except Exception as e:
                logger.warning(f"获取 chapter_outlines 失败: {e}")

        except Exception as e:
            logger.warning(f"获取项目综合信息失败: {e}")
        finally:
            await conn.close()

        # 打印完整的上下文信息
        total_length = sum(len(v) for v in sections.values() if isinstance(v, str))
        logger.info(f"[SettingAgent] 分段上下文加载完成，总长度: {total_length} 字符, 段落数: {len(sections)}")

        return sections

    async def _analyze_with_segmented_context(
        self,
        project_id: str,
        user_message: str,
        sections: Dict[str, str],
        world_type: Optional[str] = None,
    ) -> SegmentedContextSynthesis:
        """
        使用分段分析处理大量上下文（混合策略）

        策略：
        1. 分段预处理：将长上下文分段，每段提取关键信息点
        2. 返回：原始完整上下文 + 关键信息索引

        这样既保证信息不丢失，又帮助LLM快速定位关键内容。

        Args:
            project_id: 项目 ID
            user_message: 用户消息
            sections: 分段的上下文信息
            world_type: 世界类型

        Returns:
            SegmentedContextSynthesis: 完整原始上下文、关键信息索引、跨段关联、冲突、资源缺口和解析警告
        """
        logger.info(f"[分段分析] 开始: {len(sections)} 个段落")

        SEGMENT_SIZE = 1500  # 每段最大字符数
        OVERLAP_SIZE = 300   # 段落之间的重叠字符数

        # 获取世界类型提示
        world_type_hint = ""
        if world_type:
            world_type_hint = self._get_world_type_hint(world_type)
        elif sections.get("_world_type"):
            world_type_hint = self._get_world_type_hint(sections["_world_type"])

        # 存储所有段落的关键信息点和非致命解析警告
        all_key_points: List[Dict[str, Any]] = []
        parse_warnings: List[Dict[str, Any]] = []

        # 按段落类型逐个处理
        section_order = ["世界管理", "设定库", "角色列表", "伏笔列表", "章节大纲"]
        sorted_sections = []
        for key in section_order:
            if key in sections and sections[key]:
                sorted_sections.append((key, sections[key]))
        # 处理其他未在顺序中的段落
        for key, value in sections.items():
            if key not in section_order and not key.startswith("_") and value:
                sorted_sections.append((key, value))

        logger.info(f"[分段分析] 处理 {len(sorted_sections)} 个段落")

        # 第一轮：分段预处理，提取关键信息点
        failed_segments = 0  # 连续失败段落计数
        max_failed_segments = 3  # 允许的最大连续失败段落数

        for section_name, section_content in sorted_sections:
            # ========== 检查是否应该提前终止 ==========
            if self._consecutive_failures >= self._max_consecutive_failures:
                logger.warning(f"[分段分析] LLM 连续失败次数过多，提前终止分段分析")
                break

            if failed_segments >= max_failed_segments:
                logger.warning(f"[分段分析] 连续 {failed_segments} 个段落失败，提前终止")
                break

            section_length = len(section_content)

            # 如果段落较短，直接分析
            if section_length <= SEGMENT_SIZE:
                logger.info(f"[分段分析] 发送段落【{section_name}】({section_length}字符) 到 LLM")
                logger.debug(f"[分段分析] 内容全文: {section_content}")
                key_points = await self._extract_key_points(
                    section_name, section_content, user_message, world_type_hint, project_id
                )
                if key_points:
                    all_key_points.extend(key_points)
                    failed_segments = 0  # 重置连续失败计数
                else:
                    parse_warnings.append({
                        "section": section_name,
                        "error": "未能解析关键信息点，已保留原文上下文",
                    })
                    failed_segments += 1
                    logger.warning(f"[分段分析] 段落【{section_name}】提取失败 ({failed_segments}/{max_failed_segments})")
            else:
                # 长段落需要分段处理，带有重叠
                segment_start = 0
                segment_num = 0
                while segment_start < section_length:
                    # 检查是否应该终止
                    if self._consecutive_failures >= self._max_consecutive_failures:
                        logger.warning(f"[分段分析] LLM 连续失败次数过多，跳过剩余段落")
                        break

                    # 计算当前段的范围
                    if segment_start == 0:
                        segment_end = min(SEGMENT_SIZE, section_length)
                        segment_content = section_content[segment_start:segment_end]
                    else:
                        # 包含前一段的重叠部分
                        overlap_start = max(0, segment_start - OVERLAP_SIZE)
                        segment_end = min(segment_start + SEGMENT_SIZE - OVERLAP_SIZE, section_length)
                        segment_content = section_content[overlap_start:segment_end]

                    segment_num += 1
                    segment_label = f"{section_name}(第{segment_num}段)"
                    logger.info(f"[分段分析] 发送段落【{segment_label}】({len(segment_content)}字符) 到 LLM")
                    logger.debug(f"[分段分析] 内容全文: {segment_content}")

                    key_points = await self._extract_key_points(
                        segment_label, segment_content, user_message, world_type_hint, project_id
                    )
                    if key_points:
                        all_key_points.extend(key_points)
                        failed_segments = 0  # 重置连续失败计数
                    else:
                        parse_warnings.append({
                            "section": segment_label,
                            "error": "未能解析关键信息点，已保留原文上下文",
                        })
                        failed_segments += 1
                        logger.warning(f"[分段分析] 段落【{segment_label}】提取失败 ({failed_segments}/{max_failed_segments})")

                    segment_start = segment_end if segment_start == 0 else segment_start + SEGMENT_SIZE - OVERLAP_SIZE
                    if segment_start >= section_length:
                        break

                    # 检查连续失败
                    if failed_segments >= max_failed_segments:
                        logger.warning(f"[分段分析] 连续失败段落过多，跳过当前章节剩余内容")
                        break

        # 合并关键信息点（去重和整合）
        merged_key_points = self._merge_key_points(all_key_points)
        logger.info(f"[分段分析] 提取了 {len(merged_key_points)} 个关键信息点")

        # 构建完整原始上下文
        full_context = "\n\n".join([f"【{k}】\n{v}" for k, v in sorted_sections])

        cross_segment_links = self._build_cross_segment_links(merged_key_points)
        potential_conflicts = self._build_segment_potential_conflicts(merged_key_points)
        resource_requirements = self._build_segment_resource_requirements(merged_key_points)

        # 构建关键信息索引
        key_info_index = self._format_key_points_index(merged_key_points)

        return SegmentedContextSynthesis(
            full_context=full_context,
            key_info_index=key_info_index,
            key_points=merged_key_points,
            cross_segment_links=cross_segment_links,
            potential_conflicts=potential_conflicts,
            resource_requirements=resource_requirements,
            parse_warnings=parse_warnings,
        )

    def _build_segment_key_point_extraction_prompt(
        self,
        *,
        section_name: str,
        segment_content: str,
        user_question: str,
        world_type_hint: str,
    ) -> str:
        prompt_asset = self._load_md_prompt_content("function_setting_segmented_context_synthesis")
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】分析项目上下文片段，提取关键信息点；"
                "只输出 JSON 数组。"
            )
        return "\n\n".join([
            prompt_asset,
            f"## 世界类型\n{world_type_hint if world_type_hint else '未指定'}",
            f"## 片段来源\n{section_name}",
            f"## 片段内容\n{segment_content}",
            f"## 用户问题\n{user_question}",
        ]).strip()

    async def _extract_key_points(
        self,
        section_name: str,
        segment_content: str,
        user_question: str,
        world_type_hint: str,
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """
        从单个片段提取关键信息点

        关键信息点不是摘要，而是"信息索引"：
        - 记录有什么类型的信息
        - 记录关键实体和关系
        - 帮助LLM快速定位

        Args:
            section_name: 段落名称
            segment_content: 片段内容
            user_question: 用户问题
            world_type_hint: 世界类型提示
            project_id: 项目 ID

        Returns:
            List[Dict]: 关键信息点列表
        """
        prompt = self._build_segment_key_point_extraction_prompt(
            section_name=section_name,
            segment_content=segment_content,
            user_question=user_question,
            world_type_hint=world_type_hint,
        )

        try:
            result = await self._call_llm_simple(prompt)

            # 检查是否是错误响应
            if not result or "抱歉" in result or "无法处理" in result or "请稍后" in result:
                logger.warning(f"[分段分析] LLM 返回错误响应: {result if result else '空响应'}")
                return []

            # 解析JSON
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            result = result.strip()
            if not result or result == "[]":
                return []

            key_points = self._parse_segment_key_points(result)
            if key_points:
                return key_points
            logger.warning("[分段分析] 未能从 LLM 响应中解析出关键信息点")
            return []

        except Exception as e:
            logger.warning(f"[分段分析] 关键信息提取失败: {e}")
            return []

    def _parse_segment_key_points(self, result: str) -> List[Dict[str, Any]]:
        """解析分段关键信息提取结果，尽量避免单个 JSON 格式瑕疵导致整段丢失。"""
        if not result:
            return []

        candidates = self._segment_json_candidates(result)
        for candidate in candidates:
            parsed = self._load_segment_key_points_json(candidate)
            if parsed:
                return parsed

        return []

    def _segment_json_candidates(self, text: str) -> List[str]:
        """从 LLM 响应中提取可能的 JSON 数组候选。"""
        text = (text or "").strip()
        if not text:
            return []

        candidates: List[str] = []

        fenced_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
        for block in fenced_blocks:
            block = block.strip()
            if block:
                candidates.append(block)

        if text not in candidates:
            candidates.append(text)

        array_start = text.find("[")
        array_end = text.rfind("]")
        if 0 <= array_start < array_end:
            array_candidate = text[array_start:array_end + 1].strip()
            if array_candidate and array_candidate not in candidates:
                candidates.append(array_candidate)

        return candidates

    def _load_segment_key_points_json(self, candidate: str) -> List[Dict[str, Any]]:
        """加载关键信息 JSON，并对常见 LLM 格式错误做有限修复。"""
        normalized = self._normalize_segment_json(candidate)
        attempts = [normalized]
        repaired = self._repair_segment_json(normalized)
        if repaired != normalized:
            attempts.append(repaired)

        last_error: Optional[json.JSONDecodeError] = None
        for payload in attempts:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as e:
                last_error = e
                continue

            if isinstance(data, dict):
                data = data.get("key_points") or data.get("items") or data.get("data") or []

            if not isinstance(data, list):
                continue

            key_points: List[Dict[str, Any]] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                key_fact = str(item.get("key_fact") or item.get("fact") or item.get("summary") or "").strip()
                entity = str(item.get("entity") or item.get("name") or "").strip()
                category = str(item.get("category") or item.get("type") or "其他").strip()
                relevance = str(item.get("relevance") or "中").strip()
                if not key_fact and not entity:
                    continue
                key_points.append({
                    "category": category or "其他",
                    "entity": entity or "未命名实体",
                    "key_fact": key_fact or entity,
                    "relevance": relevance if relevance in {"高", "中", "低"} else "中",
                    "related_entities": self._normalize_string_list(item.get("related_entities")),
                    "relation_type": str(item.get("relation_type") or item.get("relationship") or "mentions").strip() or "mentions",
                    "potential_conflicts": self._normalize_string_list(item.get("potential_conflicts") or item.get("conflicts")),
                    "resource_requirements": self._normalize_lore_resource_requirements(item.get("resource_requirements") or item.get("requirements")),
                })
            return key_points

        if last_error:
            logger.debug(f"[分段分析] JSON解析失败，已保留原文上下文: {last_error}")
        return []

    def _normalize_segment_json(self, payload: str) -> str:
        """规范化 JSON 文本，清理常见包裹和智能标点。"""
        payload = (payload or "").strip()
        if payload.startswith("```"):
            payload = payload.strip("`").strip()
            if payload.lower().startswith("json"):
                payload = payload[4:].strip()
        return (
            payload
            .replace("\ufeff", "")
            .replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )

    def _repair_segment_json(self, payload: str) -> str:
        """对 LLM 常见 JSON 错误做保守修复。"""
        repaired = payload.strip()
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        repaired = re.sub(r"}\s*{", "}, {", repaired)
        repaired = re.sub(r'("\s*)\n\s*(")', r"\1,\n\2", repaired)
        repaired = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", lambda m: json.dumps(m.group(1), ensure_ascii=False), repaired)
        return repaired

    def _build_cross_segment_links(self, key_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从分段信息点中构造跨段关联提示，供最终设定生成综合使用。"""
        links: List[Dict[str, Any]] = []
        seen = set()
        for point in key_points:
            entity = str(point.get("entity") or "").strip()
            related_entities = self._normalize_string_list(point.get("related_entities"))
            if not entity or not related_entities:
                continue
            relation_type = str(point.get("relation_type") or "mentions").strip() or "mentions"
            key = (entity, tuple(related_entities), relation_type)
            if key in seen:
                continue
            seen.add(key)
            links.append({
                "entities": [entity, *related_entities],
                "relation_type": relation_type,
                "note": point.get("key_fact") or "跨段信息存在关联，需要综合判断",
            })
        return links

    def _build_segment_potential_conflicts(self, key_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """汇总分段中显式暴露的潜在冲突。"""
        conflicts: List[Dict[str, Any]] = []
        seen = set()
        for point in key_points:
            conflict_notes = self._normalize_string_list(point.get("potential_conflicts"))
            if not conflict_notes:
                continue
            entity = str(point.get("entity") or "").strip()
            for note in conflict_notes:
                key = (entity, note)
                if key in seen:
                    continue
                seen.add(key)
                conflicts.append({
                    "entities": [entity] if entity else [],
                    "note": note,
                    "source_fact": point.get("key_fact") or "",
                })
        return conflicts

    def _build_segment_resource_requirements(self, key_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """汇总分段中提出的资源补全需求。"""
        requirements: List[Dict[str, Any]] = []
        seen = set()
        for point in key_points:
            for requirement in self._normalize_lore_resource_requirements(point.get("resource_requirements")):
                key = (requirement.get("requirement_type"), requirement.get("resource_name"), requirement.get("reason"))
                if key in seen:
                    continue
                seen.add(key)
                requirements.append({
                    **requirement,
                    "source_entity": point.get("entity") or "",
                    "source_fact": point.get("key_fact") or "",
                })
        return requirements

    def _merge_key_points(self, all_key_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并和去重关键信息点

        Args:
            all_key_points: 所有关键信息点

        Returns:
            List[Dict]: 合并后的关键信息点
        """
        if not all_key_points:
            return []

        # 按相关性排序
        relevance_order = {"高": 0, "中": 1, "低": 2}
        sorted_points = sorted(
            all_key_points,
            key=lambda x: relevance_order.get(x.get("relevance", "低"), 2)
        )

        # 去重（基于 entity + key_fact 的组合）
        seen = set()
        unique_points = []
        for point in sorted_points:
            key = (point.get("entity", ""), point.get("key_fact", ""))  # 用完整 key_fact 判断重复
            if key not in seen:
                seen.add(key)
                unique_points.append(point)

        # 限制数量，避免索引过长
        return unique_points

    def _format_key_points_index(self, key_points: List[Dict[str, Any]]) -> str:
        """
        格式化关键信息点为索引文本

        Args:
            key_points: 关键信息点列表

        Returns:
            str: 格式化的索引文本
        """
        if not key_points:
            return "（无关键信息点）"

        # 按类别分组
        by_category = {}
        for point in key_points:
            category = point.get("category", "其他")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(point)

        # 格式化输出
        lines = ["以下是项目中的关键信息点，可以帮助你快速定位：\n"]
        for category, points in by_category.items():
            lines.append(f"### {category}")
            for point in points:
                entity = point.get("entity", "")
                key_fact = point.get("key_fact", "")
                relevance = point.get("relevance", "")
                relevance_mark = "★" if relevance == "高" else ""
                if entity:
                    lines.append(f"  • {entity}：{key_fact} {relevance_mark}")
                else:
                    lines.append(f"  • {key_fact} {relevance_mark}")
                related_entities = self._normalize_string_list(point.get("related_entities"))
                if related_entities:
                    lines.append(f"    关联：{', '.join(related_entities[:6])}")
                conflict_notes = self._normalize_string_list(point.get("potential_conflicts"))
                if conflict_notes:
                    lines.append(f"    潜在冲突：{'; '.join(conflict_notes[:2])}")
                requirements = self._normalize_lore_resource_requirements(point.get("resource_requirements"))
                if requirements:
                    req_text = "; ".join(
                        f"[{req.get('requirement_type')}] {req.get('resource_name')}" for req in requirements[:3]
                    )
                    lines.append(f"    资源缺口：{req_text}")
            lines.append("")

        return "\n".join(lines)

    # ==================== LLM 调用 ====================

    async def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
        project_id: Optional[str] = None,
        log_context: bool = True,
    ) -> str:
        """调用 LLM 生成响应（带重试保护）"""
        import asyncio
        import time

        # ========== 检查连续失败状态 ==========
        if self._consecutive_failures >= self._max_consecutive_failures:
            # 检查是否过了重置时间
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed < self._failure_reset_time:
                    remaining = int(self._failure_reset_time - elapsed)
                    logger.warning(f"[SettingAgent] LLM 连续失败次数已达上限 ({self._consecutive_failures}次)，暂停调用 {remaining}秒")
                    return "抱歉，LLM 服务暂时不可用，请稍后再试。"
                else:
                    # 重置失败计数
                    logger.info("[SettingAgent] 失败计数已重置")
                    self._consecutive_failures = 0

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"上下文信息：\n{context}"},
            {"role": "user", "content": user_message},
        ]

        if log_context and len(context) > 0:
            logger.info(f"[SettingAgent] LLM调用: 上下文 {len(context)} 字符")

        # 计算输入 token（估算）
        input_tokens = sum(len(m.get("content", "")) // 4 for m in messages)

        trace_service = get_trace_service()
        trace_tokens = TraceService.set_context(TraceService.current_trace_id(), TraceService.current_span_id())
        started_at = time.monotonic()

        last_error = None
        for attempt in range(self._max_retries):
            try:
                if self.llm_provider == "openai":
                    response, usage = await self._call_openai_with_usage(messages)
                elif self.llm_provider == "anthropic":
                    response, usage = await self._call_anthropic_with_usage(messages)
                else:
                    response, usage = await self._call_openai_with_usage(messages)

                duration_ms = int((time.monotonic() - started_at) * 1000)
                await trace_service.record_event("llm_call_completed", {
                    "agent_name": "setting_agent",
                    "agent_type": "setting_agent",
                    "project_id": project_id,
                    "provider": self.llm_provider,
                    "model": self.llm_model,
                    "category": UsageCategory.SETTING_AGENT.value,
                    "streaming": False,
                    "structured": False,
                    "message_count": len(messages),
                    "attempt": attempt + 1,
                    "prompt_chars": sum(len(m.get("content", "")) for m in messages),
                    "prompt_hash": hashlib.sha256("\n".join(m.get("content", "") for m in messages).encode("utf-8")).hexdigest(),
                    "response_chars": len(response or ""),
                    "response_hash": hashlib.sha256((response or "").encode("utf-8")).hexdigest() if response else None,
                    "input_tokens": usage.get("input_tokens", input_tokens),
                    "output_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("total_tokens", usage.get("input_tokens", input_tokens) + usage.get("output_tokens", 0)),
                    "duration_ms": duration_ms,
                })

                # 记录 token 使用
                if project_id and usage:
                    await self._record_token_usage(project_id, usage, input_tokens)

                # 成功，重置失败计数
                self._consecutive_failures = 0
                self._last_failure_time = None
                TraceService.reset_context(trace_tokens)
                return response

            except Exception as e:
                last_error = e
                self._consecutive_failures += 1
                self._last_failure_time = time.time()

                if attempt < self._max_retries - 1:
                    # 计算指数退避延迟
                    delay = min(
                        self._retry_base_delay * (2 ** attempt),
                        self._retry_max_delay
                    )
                    logger.warning(f"[SettingAgent] LLM 调用失败 (尝试 {attempt + 1}/{self._max_retries}): {e}，{delay:.1f}秒后重试")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[SettingAgent] LLM 调用失败，已达最大重试次数 ({self._max_retries}次): {e}")
                    await trace_service.record_event("llm_call_failed", {
                        "agent_name": "setting_agent",
                        "agent_type": "setting_agent",
                        "project_id": project_id,
                        "provider": self.llm_provider,
                        "model": self.llm_model,
                        "attempt": attempt + 1,
                        "error": str(e),
                    }, severity="error")

        TraceService.reset_context(trace_tokens)

        # 所有重试都失败
        logger.error(f"[SettingAgent] LLM 调用最终失败: {last_error}")
        return "抱歉，我现在无法处理你的请求。请稍后再试。"

    async def _record_token_usage(
        self,
        project_id: str,
        usage: Dict[str, Any],
        input_tokens_estimate: int,
    ):
        """记录 token 使用量"""
        try:
            # 使用实际的使用量（如果有）
            input_tokens = usage.get("input_tokens", input_tokens_estimate)
            output_tokens = usage.get("output_tokens", 0)

            await token_tracker.record_usage(
                project_id=project_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider=self.llm_provider,
                model=self.llm_model,
                category=UsageCategory.SETTING_AGENT,
                agent_name="setting_agent",
            )
        except Exception as e:
            logger.warning(f"记录 token 使用失败: {e}")

    async def _call_llm_simple(self, prompt: str) -> str:
        """简化的 LLM 调用（不显示日志）"""
        return await self._call_llm(
            system_prompt="你是一个有帮助的助手。",
            user_message=prompt,
            context="",
            log_context=False,
        )

    async def _call_structured(
        self,
        schema,
        prompt: str,
        *,
        system_prompt: str = "你是一个有帮助的助手。请严格按照指定的结构输出。",
        project_id: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        """使用 LangChain ``with_structured_output`` 进行结构化生成。

        与 ``_call_llm`` 共享 token 跟踪与 provider 配置，但绕过自定义重试，
        把校验/修复交给 :class:`StructuredLLMRunner`。
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        from app.services.model_router import create_llm
        from app.services.structured_llm import (
            StructuredOutputError,
            get_structured_llm_runner,
        )

        model = create_llm(
            provider=self.llm_provider,
            model=self.llm_model,
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            temperature=self.llm_temperature if temperature is None else temperature,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]

        runner = get_structured_llm_runner()
        trace_service = get_trace_service()
        trace_tokens = TraceService.set_context(TraceService.current_trace_id(), TraceService.current_span_id())
        import time
        started_at = time.monotonic()
        parsed, raw_text = await runner.run_structured(model, schema, messages)

        # 估算 token 用量并记录（与 _call_llm 保持一致）
        if project_id:
            try:
                input_tokens = (len(system_prompt) + len(prompt)) // 4
                output_tokens = len(raw_text or "") // 4
                await trace_service.record_event("llm_call_completed", {
                    "agent_name": "setting_agent",
                    "agent_type": "setting_agent",
                    "project_id": project_id,
                    "provider": self.llm_provider,
                    "model": self.llm_model,
                    "category": UsageCategory.SETTING_AGENT.value,
                    "streaming": False,
                    "structured": True,
                    "schema_name": getattr(schema, "__name__", str(schema)),
                    "message_count": len(messages),
                    "prompt_chars": len(system_prompt) + len(prompt),
                    "prompt_hash": hashlib.sha256(f"{system_prompt}\n{prompt}".encode("utf-8")).hexdigest(),
                    "response_chars": len(raw_text or ""),
                    "response_hash": hashlib.sha256((raw_text or "").encode("utf-8")).hexdigest() if raw_text else None,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "duration_ms": int((time.monotonic() - started_at) * 1000),
                })
                TraceService.reset_context(trace_tokens)
                await self._record_token_usage(
                    project_id,
                    {"input_tokens": input_tokens, "output_tokens": output_tokens},
                    input_tokens,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning(f"[SettingAgent] structured token 记录失败: {exc}")

        return parsed

    async def _call_openai(self, messages: List[Dict[str, Any]]) -> str:
        """调用 OpenAI API"""
        result, _ = await self._call_openai_with_usage(messages)
        return result

    async def _call_openai_with_usage(self, messages: List[Dict[str, Any]]) -> tuple:
        """调用 OpenAI API 并返回使用量"""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.error("[SettingAgent] openai 包未安装，请运行: pip install openai")
            return self._fallback_response(messages), {}

        # 检查 API Key 是否配置
        if not self.llm_api_key:
            logger.error("[SettingAgent] OpenAI API Key 未配置！请检查 .env 文件中的 LLM_OPENAI_API_KEY")
            return self._fallback_response(messages), {}

        client = AsyncOpenAI(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url or "https://api.openai.com/v1",
        )

        # 合并所有 system 消息为一个（兼容各种 OpenAI 兼容 API）
        merged_messages = []
        system_parts = []

        for m in messages:
            if m["role"] == "system":
                system_parts.append(m["content"])
            else:
                if not merged_messages and system_parts:
                    # 在第一个非 system 消息前插入合并后的 system 消息
                    merged_messages.append({"role": "system", "content": "\n\n".join(system_parts)})
                merged_messages.append(m)

        # 如果所有消息都是 system 消息
        if not merged_messages and system_parts:
            merged_messages.append({"role": "system", "content": "\n\n".join(system_parts)})

        response = await client.chat.completions.create(
            model=self.llm_model,
            messages=merged_messages,
            temperature=self.llm_temperature,
            max_tokens=self.llm_max_tokens,
        )

        # 提取 token 使用量
        usage = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens or 0,
                "output_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }

        return response.choices[0].message.content, usage

    async def _call_anthropic(self, messages: List[Dict[str, Any]]) -> str:
        """调用 Anthropic API"""
        result, _ = await self._call_anthropic_with_usage(messages)
        return result

    async def _call_anthropic_with_usage(self, messages: List[Dict[str, Any]]) -> tuple:
        """调用 Anthropic API 并返回使用量"""
        try:
            import anthropic
        except ImportError:
            logger.error("[SettingAgent] anthropic 包未安装，请运行: pip install anthropic")
            return self._fallback_response(messages), {}

        # 检查 API Key 是否配置
        if not self.llm_api_key:
            logger.error("[SettingAgent] Anthropic API Key 未配置！请检查 .env 文件中的 LLM_ANTHROPIC_API_KEY")
            return self._fallback_response(messages), {}

        client = anthropic.AsyncAnthropic(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url or "https://api.anthropic.com",
        )

        # 合并所有 system 消息为一个
        system_parts = []
        claude_messages = []

        for m in messages:
            if m["role"] == "system":
                system_parts.append(m["content"])
            else:
                claude_messages.append({"role": m["role"], "content": m["content"]})

        system_message = "\n\n".join(system_parts)

        response = await client.messages.create(
            model=self.llm_model,
            system=system_message,
            messages=claude_messages,
            temperature=self.llm_temperature,
            max_tokens=self.llm_max_tokens,
        )

        # 提取 token 使用量
        usage = {}
        if hasattr(response, 'usage') and response.usage:
            usage = {
                "input_tokens": response.usage.input_tokens or 0,
                "output_tokens": response.usage.output_tokens or 0,
                "total_tokens": (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0),
            }

        # 提取文本内容（处理 ThinkingBlock 等不同类型）
        text_content = ""
        for block in response.content:
            # 检查是否是 TextBlock（有 text 属性）
            if hasattr(block, 'text'):
                text_content += block.text
            # 检查是否是 ThinkingBlock（跳过或记录）
            elif hasattr(block, 'thinking'):
                # ThinkingBlock 包含思考过程，可以记录但不需要返回
                logger.debug(f"收到 ThinkingBlock，跳过思考内容")
            else:
                # 其他类型尝试转为字符串
                logger.warning(f"未知的响应块类型: {type(block).__name__}")
                text_content += str(block)

        return text_content, usage

    def _fallback_response(self, messages: List[Dict[str, Any]]) -> str:
        """回退响应"""
        return "我已收到你的消息。作为设定管理者，我可以帮助你维护世界观设定的一致性。请问有什么需要我帮助的吗？"

    # ==================== Bootstrap 兼容 ====================

    async def process_bootstrap_message(
        self,
        session_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """处理 Bootstrap 模式消息（兼容旧接口）"""
        # 获取 Bootstrap 会话
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 添加用户消息
        user_msg = BootstrapMessage(
            role="user",
            content=message,
            timestamp=datetime.now(),
        )
        session.setting_agent_history.append(user_msg.model_dump(mode="json"))

        # 构建提示
        system_prompt = self._build_bootstrap_prompt(session)
        context = self._build_conversation_context(session)

        # 调用 LLM（传入 project_id 以记录 token）
        response = await self._call_llm(system_prompt, message, context, project_id=session.project_id)

        # 添加助手回复
        assistant_msg = BootstrapMessage(
            role="assistant",
            content=response,
            timestamp=datetime.now(),
        )
        session.setting_agent_history.append(assistant_msg.model_dump(mode="json"))

        # 检查是否需要提取 seed
        seed_extracted = await self._check_and_extract_seed(session)

        return {
            "response": response,
            "session_id": session_id,
            "stage": session.current_stage.value,
            "seed_extracted": seed_extracted,
            "seed_data": session.extracted_seed if seed_extracted else None,
        }

    def _build_bootstrap_prompt(self, session: BootstrapSession) -> str:
        """构建 Bootstrap 提示（稳定 Bootstrap 规则来自 md prompt 资产）。"""
        prompt_asset = self._load_md_prompt_content(self.SETTING_BOOTSTRAP_COLLECTION_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】你是长篇网络小说设定专家（Setting Agent）。请通过多轮对话收集世界观、"
                "角色、主线、风格和关键设定；主动追问缺口，并保持所有内容为待确认草案。"
            )
        return prompt_asset

    def _build_conversation_context(self, session: BootstrapSession) -> str:
        """构建对话上下文"""
        if not session.setting_agent_history:
            return "这是对话的开始，用户将向你介绍他们的故事设定。"

        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in session.setting_agent_history[-10:]
        ])
        return f"最近的对话历史：\n{history_text}"

    async def _check_and_extract_seed(self, session: BootstrapSession) -> bool:
        """检查并提取 seed"""
        user_message_count = sum(
            1 for msg in session.setting_agent_history
            if msg.get("role") == "user"
        )

        if user_message_count >= 3 and not session.extracted_seed:
            extracted = await self._extract_seed_from_history(session)
            if extracted:
                session.extracted_seed = extracted
                session.current_stage = BootstrapStage.SEED_EXTRACTED
                session.progress = 0.4
                return True

        return False

    def _build_bootstrap_seed_extraction_prompt(self, history_text: str) -> str:
        prompt_asset = self._load_md_prompt_content(self.SETTING_BOOTSTRAP_SEED_EXTRACTION_PROMPT_ID)
        if not prompt_asset:
            prompt_asset = (
                "【DEPRECATED 最小 fallback】请从对话历史中提取结构化项目 seed；"
                "只输出 JSON 对象，缺失字段使用空字符串或空数组。"
            )
        return "\n\n".join([
            prompt_asset,
            f"## 对话历史\n{history_text}",
        ]).strip()

    async def _extract_seed_from_history(self, session: BootstrapSession) -> Optional[Dict[str, Any]]:
        """从历史提取 seed"""
        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in session.setting_agent_history
        ])

        extraction_prompt = self._build_bootstrap_seed_extraction_prompt(history_text)
        try:
            from app.models.agent_output_schemas import BootstrapSeedExtractionSchema

            parsed = await self._call_structured(
                BootstrapSeedExtractionSchema,
                extraction_prompt,
                project_id=session.project_id,
            )
            return parsed.model_dump()
        except Exception as e:
            logger.error(f"提取 seed 失败：{e}")
            return None

    async def create_bootstrap_session(
        self,
        project_id: str,
        initial_message: Optional[str] = None,
    ) -> BootstrapSession:
        """创建 Bootstrap 会话"""
        import uuid
        session_id = f"bootstrap_{uuid.uuid4().hex[:12]}"

        session = BootstrapSession(
            id=session_id,
            project_id=project_id,
            status=BootstrapStage.COLLECTING_SETTING,
            current_stage=BootstrapStage.COLLECTING_SETTING,
            progress=0.1,
        )

        self._sessions[session_id] = session

        if initial_message:
            await self.process_bootstrap_message(session_id, initial_message)

        return session

    async def get_bootstrap_session(self, session_id: str) -> Optional[BootstrapSession]:
        """获取 Bootstrap 会话"""
        return self._sessions.get(session_id)

    async def update_bootstrap_session(self, session: BootstrapSession):
        """更新 Bootstrap 会话"""
        self._sessions[session.id] = session


# 全局单例
_setting_agent_service: Optional[SettingAgentService] = None


def get_setting_agent_service() -> SettingAgentService:
    """获取 SettingAgentService 单例"""
    global _setting_agent_service
    if _setting_agent_service is None:
        _setting_agent_service = SettingAgentService()
    return _setting_agent_service


def set_setting_agent_service(service: SettingAgentService):
    """设置 SettingAgentService 实例"""
    global _setting_agent_service
    _setting_agent_service = service
