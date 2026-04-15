"""
设定 Agent 服务
v6 核心需求：持续设定管理、冲突检测、协商解决
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings
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
from app.models.lore import LoreEntry, LorePriority
from app.models.skill import ExecuteSkillDTO
from app.models.token_usage import UsageCategory
from app.services.conflict_detector import ConflictDetector, get_conflict_detector
from app.services.token_tracker import token_tracker

logger = logging.getLogger(__name__)


class SettingAgentService:
    """设定 Agent 服务 - 持续的设定管理者"""

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
    ) -> SettingAgentSession:
        """
        获取或创建 Setting Agent 会话

        Args:
            project_id: 项目 ID
            mode: 运行模式

        Returns:
            SettingAgentSession: 会话对象
        """
        # 检查是否已有会话
        for session in self._management_sessions.values():
            if session.project_id == project_id and session.is_active:
                return session

        # 创建新会话
        session = SettingAgentSession(
            project_id=project_id,
            mode=mode,
        )
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

    # ==================== 设定变更处理 ====================

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
                    priority=LorePriority(row.get("priority", "standard")),
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

        return {
            "status": "resolved" if all_resolved else "negotiating",
            "conflict": conflict.model_dump(),
            "can_proceed": all_resolved,
        }

    async def _analyze_user_intent(self, user_response: str) -> str:
        """分析用户意图"""
        response_lower = user_response.lower()

        if any(word in response_lower for word in ["接受", "同意", "好的", "可以"]):
            return "accept_suggestion"
        elif any(word in response_lower for word in ["覆盖", "强制", "忽略"]):
            return "override"
        elif any(word in response_lower for word in ["取消", "放弃", "算了"]):
            return "cancel"
        else:
            return "continue"

    async def _extract_suggestion_index(self, response: str) -> Optional[int]:
        """从回复中提取建议索引"""
        import re
        match = re.search(r'(\d+)', response)
        if match:
            return int(match.group(1)) - 1
        return None

    async def _generate_negotiation_response(
        self,
        session: SettingAgentSession,
        conflict: SettingConflict,
        user_response: str,
    ) -> Dict[str, Any]:
        """生成协商回复"""
        # 构建协商提示
        prompt = f"""用户正在就设定冲突进行协商。

冲突描述：{conflict.description}
严重程度：{conflict.severity.value}

现有建议：
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(conflict.resolution_suggestions))}

用户回复：{user_response}

请生成一个有帮助的回复，帮助用户做出决定。"""

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

        return {
            "status": "negotiating",
            "response": assistant_response,
            "suggestions": conflict.resolution_suggestions,
        }

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
        session = await self.get_or_create_session(project_id)

        # 添加用户消息到历史
        session.conversation_history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })

        # 构建系统提示（异步）
        system_prompt = await self._build_management_system_prompt(session)

        # 获取分段上下文
        sections = await self._get_context_sections(project_id)
        world_type = sections.pop("_world_type", None)

        # 计算上下文总长度（包括对话历史）
        sections_length = sum(len(v) for v in sections.values() if isinstance(v, str))
        history_length = sum(len(msg.get('content', '')) for msg in session.conversation_history[-10:])
        context_length = sections_length + history_length

        # 日志：简要信息
        logger.info(f"[SettingAgent] 世界类型: {world_type or '未设置'} | sections: {sections_length} 字符 | 对话历史: {history_length} 字符")

        # 如果上下文过长（超过 4000 字符），使用分段分析
        CONTEXT_THRESHOLD = 4000
        use_segmented_analysis = context_length > CONTEXT_THRESHOLD

        logger.info(f"[SettingAgent] 总上下文: {context_length} 字符, 分段: {use_segmented_analysis}")

        if use_segmented_analysis:
            try:
                # 分段分析返回：完整原始上下文 + 关键信息索引
                full_context, key_info_index = await self._analyze_with_segmented_context(
                    project_id=project_id,
                    user_message=message,
                    sections=sections,
                    world_type=world_type,
                )
                logger.info(f"[SettingAgent] 分段分析完成: full_context长度={len(full_context)}, key_info_index长度={len(key_info_index)}")
            except Exception as e:
                logger.error(f"[SettingAgent] 分段分析失败: {e}")
                # 回退到常规方法
                full_context = "\n\n".join([f"【{k}】\n{v}" for k, v in sections.items() if v and not k.startswith("_")])
                key_info_index = "（分段分析失败，直接使用原始上下文）"

            # 构建最终上下文：关键信息索引 + 完整原始上下文 + 最近对话
            context_str = f"""【关键信息索引】
{key_info_index}

【项目完整信息】
{full_context}

【最近对话】
""" + "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in session.conversation_history[-6:]
            ])

            # 构建最终上下文：关键信息索引 + 完整原始上下文 + 最近对话
            context_str = f"""【关键信息索引】
{key_info_index}

【项目完整信息】
{full_context}

【最近对话】
""" + "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in session.conversation_history[-6:]
            ])
        else:
            # 从已加载的 sections 构建上下文
            context_parts = []
            for section_name, section_content in sections.items():
                if section_content and not section_name.startswith("_"):
                    context_parts.append(f"【{section_name}】\n{section_content}")

            # 添加最近对话
            if session.conversation_history:
                history = "\n".join([
                    f"{msg['role']}: {msg['content']}"
                    for msg in session.conversation_history[-10:]
                ])
                context_parts.append(f"【最近对话】\n{history}")

            context_str = "\n\n".join(context_parts)

            # 如果 sections 为空，回退到原始方法
            if not context_str or context_str.strip() == "":
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

        # 从对话中提取待确认的设定和角色
        pending_lores = await self._extract_lore_from_conversation(project_id, session)
        pending_characters = await self._extract_characters_from_conversation(project_id, session)

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

        result = {
            "response": response,
            "session_id": session.id,
            "mode": session.mode.value,
        }

        # 返回待确认的设定和角色，由前端显示确认弹窗
        if pending_lores:
            result["pending_lores"] = pending_lores
        if pending_characters:
            result["pending_characters"] = pending_characters

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
            from datetime import datetime
            import json
            import hashlib

            if not postgres_db:
                return

            # 生成记忆 ID
            key = f"{project_id}:setting:setting_agent"
            memory_id = f"memory_{hashlib.md5(key.encode()).hexdigest()[:12]}"

            # 创建新的记忆条目（不读取现有记忆）
            timestamp = datetime.now().isoformat()
            new_memories = [
                {
                    "id": f"mem_{hashlib.md5(f'{timestamp}_user'.encode()).hexdigest()[:8]}",
                    "type": "interaction",
                    "importance": "medium",
                    "content": f"用户: {user_message[:500]}",
                    "tags": [],
                    "context": {"source": "lore_interface", "role": "user"},
                    "created_at": timestamp,
                },
                {
                    "id": f"mem_{hashlib.md5(f'{timestamp}_assistant'.encode()).hexdigest()[:8]}",
                    "type": "interaction",
                    "importance": "medium",
                    "content": f"设定助手: {assistant_response[:500]}",
                    "tags": [],
                    "context": {"source": "lore_interface", "role": "assistant"},
                    "created_at": timestamp,
                },
            ]

            memories_json = json.dumps(new_memories)
            now = datetime.now()

            # 直接使用 SQL 追加记忆（不读取现有记忆）
            query = """
                INSERT INTO agent_memories (id, project_id, agent_type, agent_id, memories, knowledge, working_memory, total_memories, created_at, updated_at)
                VALUES (
                    :id,
                    CAST(:project_id AS UUID),
                    :agent_type,
                    :agent_id,
                    CAST(:memories AS jsonb),
                    CAST('{}' AS jsonb),
                    CAST('{}' AS jsonb),
                    :total_memories,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    memories = agent_memories.memories || CAST(:memories AS jsonb),
                    total_memories = agent_memories.total_memories + :total_memories,
                    updated_at = :updated_at
            """

            await postgres_db.execute_write(query, {
                "id": memory_id,
                "project_id": project_id,
                "agent_type": "setting",
                "agent_id": "setting_agent",
                "memories": memories_json,
                "total_memories": 2,
                "created_at": now,
                "updated_at": now,
            })

            logger.debug(f"同步 Setting Agent 对话到记忆系统: project_id={project_id}")

        except Exception as e:
            logger.warning(f"同步 Setting Agent 记忆失败: {e}")
            logger.warning(f"同步 Setting Agent 记忆失败: {e}")

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

        extraction_prompt = f"""分析以下对话，判断用户是否明确要求保存或确认了新的世界观设定。

重要规则：
- 只有当用户在对话中明确说"保存"、"确认"、"好的"、"可以"等确认性语言时，才提取设定
- 如果只是讨论或询问，不要提取
- 如果只是建议或候选方案，用户还没有确认，不要提取

如果有用户明确确认的新设定，请提取为 JSON 数组。如果没有，返回空数组 []。

输出格式：
```json
[
  {{
    "title": "设定标题",
    "category": "world_rule|geography|history|faction|culture|race|profession|item|skill|custom",
    "priority": "constitutional|core|standard|flexible",
    "content": "设定详细内容",
    "summary": "简短摘要",
    "keywords": ["关键词1", "关键词2"]
  }}
]
```

对话内容：
{history_text}

只输出 JSON 数组，不要其他内容。如果没有用户明确确认的新设定，输出 []。
"""

        try:
            response = await self._call_llm_simple(extraction_prompt)

            # 解析 JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            response = response.strip()
            if not response or response == "[]":
                return []

            lores = json.loads(response)
            if not isinstance(lores, list) or len(lores) == 0:
                return []

            # 返回待确认的设定（不保存到数据库）
            valid_lores = []
            for lore_data in lores:
                if not lore_data.get("title") or not lore_data.get("content"):
                    continue
                valid_lores.append({
                    "title": lore_data.get("title", ""),
                    "category": lore_data.get("category", "custom"),
                    "priority": lore_data.get("priority", "standard"),
                    "content": lore_data.get("content", ""),
                    "summary": lore_data.get("summary", ""),
                    "keywords": lore_data.get("keywords", []),
                    "tags": lore_data.get("tags", []),
                    "constraints": lore_data.get("constraints", []),
                    "related_characters": lore_data.get("related_characters", []),
                    "related_locations": lore_data.get("related_locations", []),
                    "related_items": lore_data.get("related_items", []),
                })

            if valid_lores:
                logger.info(f"从对话中提取 {len(valid_lores)} 个待确认设定")

            return valid_lores

        except json.JSONDecodeError:
            logger.warning("解析设定 JSON 失败")
            return []
        except Exception as e:
            logger.error(f"提取设定失败: {e}")
            return []

    async def save_pending_lores(
        self,
        project_id: str,
        lores: List[Dict[str, Any]],
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
        for lore_data in lores:
            if not lore_data.get("title") or not lore_data.get("content"):
                continue

            lore_entry = {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "title": lore_data.get("title", ""),
                "category": lore_data.get("category", "custom"),
                "priority": lore_data.get("priority", "standard"),
                "content": lore_data.get("content", ""),
                "summary": lore_data.get("summary", ""),
                "keywords": json.dumps(lore_data.get("keywords", [])),
                "tags": json.dumps(lore_data.get("tags", [])),
                "constraints": json.dumps(lore_data.get("constraints", [])),
                "related_characters": json.dumps(lore_data.get("related_characters", [])),
                "related_locations": json.dumps(lore_data.get("related_locations", [])),
                "related_items": json.dumps(lore_data.get("related_items", [])),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            try:
                await postgres_db.execute_write("""
                    INSERT INTO lore_entries (id, project_id, title, category, priority, content, summary, keywords, tags, constraints, related_characters, related_locations, related_items, created_at, updated_at)
                    VALUES (:id, CAST(:project_id AS UUID), :title, :category, :priority, :content, :summary, :keywords, :tags, :constraints, :related_characters, :related_locations, :related_items, :created_at, :updated_at)
                """, lore_entry)
                saved_count += 1
                logger.info(f"保存用户确认的设定: {lore_entry['title']}")
            except Exception as e:
                logger.error(f"保存设定失败: {e}")

        return saved_count

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

        extraction_prompt = f"""分析以下对话，判断用户是否明确要求保存或确认了新的角色设定。

重要规则：
- 只有当用户在对话中明确说"保存角色"、"确认角色"、"添加角色"等确认性语言时，才提取角色
- 如果只是讨论或询问某个角色，不要提取
- 提取的角色信息要完整，包括基本信息、外貌、性格等

如果有用户明确确认的新角色，请提取为 JSON 数组。如果没有，返回空数组 []。

输出格式：
```json
[
  {{
    "name": "角色名称",
    "importance_tier": "protagonist|co_protagonist|deuteragonist|mentor|love_interest|best_friend|archenemy|major_ally|major_antagonist|rival|family_member|guardian|arc_antagonist|arc_ally|recurring|catalyst|mystery_figure|minion|informant|mentor_figure|comic_relief|victim|npc|background|cameo",
    "description": "角色描述（一句话概括）",
    "appearance": "外貌描述",
    "personality": "性格特点",
    "background_story": "背景故事",
    "speech_pattern": "说话风格",
    "age": 年龄数字或null,
    "gender": "性别",
    "goals": ["目标1", "目标2"]
  }}
]
```

重要性层级说明：
- protagonist: 主角，故事核心
- co_protagonist: 双主角
- deuteragonist: 第二主角
- mentor: 导师/引路人
- love_interest: 恋爱对象
- best_friend: 挚友
- archenemy: 宿敌/主要反派
- major_ally: 重要盟友
- major_antagonist: 重要反派
- npc: 普通NPC

对话内容：
{history_text}

只输出 JSON 数组，不要其他内容。如果没有用户明确确认的新角色，输出 []。
"""

        try:
            response = await self._call_llm_simple(extraction_prompt)

            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            response = response.strip()
            if not response or response == "[]":
                return []

            characters = json.loads(response)
            if not isinstance(characters, list) or len(characters) == 0:
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
                    "goals": char_data.get("goals", []),
                })

            if valid_characters:
                logger.info(f"从对话中提取 {len(valid_characters)} 个待确认角色")

            return valid_characters

        except json.JSONDecodeError:
            logger.warning("解析角色 JSON 失败")
            return []
        except Exception as e:
            logger.error(f"提取角色失败: {e}")
            return []

    async def save_pending_characters(
        self,
        project_id: str,
        characters: List[Dict[str, Any]],
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
        if not postgres_db:
            return 0

        saved_count = 0
        for char_data in characters:
            if not char_data.get("name"):
                continue

            char_entry = {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "name": char_data.get("name", ""),
                "importance_tier": char_data.get("importance_tier", "npc"),
                "description": char_data.get("description", ""),
                "appearance": char_data.get("appearance", ""),
                "personality": char_data.get("personality", ""),
                "background_story": char_data.get("background_story", ""),
                "speech_pattern": char_data.get("speech_pattern", ""),
                "age": char_data.get("age"),
                "gender": char_data.get("gender", ""),
                "goals": json.dumps(char_data.get("goals", [])),
                "status": "active",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            try:
                await postgres_db.execute_write("""
                    INSERT INTO characters (id, project_id, name, importance_tier, description, appearance, personality, background_story, speech_pattern, age, gender, goals, status, created_at, updated_at)
                    VALUES (:id, CAST(:project_id AS UUID), :name, :importance_tier, :description, :appearance, :personality, :background_story, :speech_pattern, :age, :gender, :goals, :status, :created_at, :updated_at)
                """, char_entry)
                saved_count += 1
                logger.info(f"保存用户确认的角色: {char_entry['name']}")
            except Exception as e:
                logger.error(f"保存角色失败: {e}")

        return saved_count

    # ==================== 智能推断方法 ====================

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

        prompt = f"""请从以下对话中推断故事的世界类型。

可能的类型：
- fantasy (奇幻): 魔法、精灵、怪物、异世界
- scifi (科幻): 太空、未来科技、外星人、赛博朋克
- modern (现代): 当代社会、都市、现实题材
- historical (历史): 古代/近代历史背景
- wuxia (武侠): 江湖、武功、门派、恩怨

对话内容：
{history_text}

请直接返回世界类型名称（如 fantasy），如果没有足够信息推断则返回 "unknown"。
"""

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

        prompt = f"""请从以下对话中推断故事的叙事基调。

可能的基调：
- serious (严肃): 正剧、深刻主题、命运沉重
- lighthearted (轻松): 轻松幽默、日常甜蜜
- dark (暗黑): 悲剧、虐心、压抑
- comedic (喜剧): 搞笑、荒诞、无厘头
- adventurous (冒险): 热血、成长、挑战

对话内容：
{history_text}

请直接返回基调名称（如 serious），如果没有足够信息推断则返回 "unknown"。
"""

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

            # 构建更新数据
            update_data = {}
            if world_type:
                update_data["world_type"] = world_type
            if tone:
                update_data["tone"] = tone
            if additional_metadata:
                update_data["metadata"] = additional_metadata

            if not update_data:
                return True

            # 从项目元数据中获取现有值
            project = await postgres_db.get_project(project_id)
            if not project:
                logger.warning(f"项目不存在: {project_id}")
                return False

            # 更新元数据
            metadata = project.get("metadata", {})
            if "metadata" not in update_data:
                update_data["metadata"] = metadata

            # 合并世界类型和基调到元数据
            if world_type:
                update_data["world_type"] = world_type
            if tone:
                update_data["tone"] = tone

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
            response = await self._call_llm_simple(prompt)

            # 解析 JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            personality_data = json.loads(response.strip())

            logger.info(f"为角色 '{character_data.get('name')}' 生成性格: {personality_data.get('personality', '')[:50]}...")

            return {
                "success": True,
                "appearance": personality_data.get("appearance", ""),
                "personality": personality_data.get("personality", ""),
                "speech_pattern": personality_data.get("speech_pattern", ""),
                "personality_traits": personality_data.get("personality_traits", []),
                "agent_goals": personality_data.get("agent_goals", []),
                "agent_memory": personality_data.get("agent_memory", []),
            }

        except json.JSONDecodeError as e:
            logger.error(f"解析性格 JSON 失败: {e}")
            return {
                "success": False,
                "error": "解析失败",
                "personality": "",
                "speech_pattern": "",
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
                        rules_str = ", ".join([r.get("name", "") for r in rules[:5] if isinstance(r, dict)])
                        if rules_str:
                            context_parts.append(f"【核心规则】{rules_str}")
            except Exception as e:
                logger.warning(f"加载世界管理信息失败: {e}")

            # 获取关键设定
            try:
                lores = await postgres_db.execute_query(
                    "SELECT title FROM lore_entries WHERE project_id = CAST(:project_id AS UUID) ORDER BY priority, created_at DESC LIMIT 5",
                    {"project_id": project_id}
                )
                if lores:
                    lore_titles = [l.get("title", "") for l in lores]
                    context_parts.append(f"\n关键设定：{', '.join(lore_titles)}")
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
            for char in existing_characters[:5]:
                if char.get("personality"):
                    personalities.append(f"- {char.get('name')}: {char.get('personality')}")
            if personalities:
                existing_personalities = f"\n\n现有角色性格（避免过于相似）：\n" + "\n".join(personalities)

        prompt = f"""你是一个专业的小说角色设定专家。请为以下角色生成性格设定。

【项目背景】
{project_context if project_context else "通用小说设定"}

【角色信息】
- 姓名：{name}
- 定位：{role_descriptions.get(role, role)}
- 描述：{description}
- 背景：{background if background else "暂无详细背景"}
{existing_personalities}

【输出要求】
请生成以下内容，以 JSON 格式输出：

1. **appearance**: 外貌描述（2-3句话，描述外貌特征、穿着打扮、气质等）
2. **personality**: 性格描述（2-3句话，描述核心性格特点）
3. **speech_pattern**: 说话风格（如：简短凌厉、幽默风趣、文绉绉等）
4. **personality_traits**: 性格特质列表（3-5个，如["勇敢", "冲动", "正义感强"]）
5. **agent_goals**: 作为角色 Agent 的目标（2-3个，用于驱动角色行为）
6. **agent_memory**: 角色应记住的关键信息（1-2条，如重要经历、关系等）

【输出格式】
```json
{{
  "appearance": "外貌描述",
  "personality": "性格描述",
  "speech_pattern": "说话风格",
  "personality_traits": ["特质1", "特质2", "特质3"],
  "agent_goals": ["目标1", "目标2"],
  "agent_memory": ["记忆1"]
}}
```

请确保：
- 外貌描述要有辨识度，符合角色身份和世界设定
- 性格与角色定位相符
- 与现有角色有区分度
- 性格要有优缺点，避免脸谱化
- 说话风格要与身份背景匹配

只输出 JSON，不要其他内容。
"""
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

        base_prompt = f"""你是一个专业的长篇网络小说设定管理者（Setting Agent）。你的职责是：

1. 维护项目的世界观设定，确保长篇连载中设定的一致性
2. 管理项目中的角色信息，帮助用户添加、修改角色设定
3. 帮助用户添加、修改、删除世界观设定
4. 检测和处理设定冲突
5. 提供设定建议和优化方案

【核心原则】
- 严格遵循项目的世界类型设定，不要生成与项目类型不符的设定
- 保持设定的内在一致性，这对长篇连载尤为重要
- 注意宪法级规则，任何新设定都不能违反它们
- 当发现潜在冲突时，及时提醒用户并提供解决方案
- 用清晰、结构化的方式组织信息
- 考虑长篇创作的可持续性和扩展性

【重要规则 - 必须遵守】
- 永远不要自动保存设定或角色到数据库！
- 当需要保存新设定、新角色或确认修改时，你只能建议用户保存，并说明保存了什么内容
- 等待用户明确说"保存"、"确认"、"好的"等确认性语言后，才将内容标记为待保存
- 在用户确认之前，只将设定或角色以建议的形式展示给用户看

【关键要求】
- 你必须仔细阅读并使用【项目综合信息】中提供的上下文来回答用户的问题
- 如果用户询问项目信息，你必须基于提供的世界管理、角色列表、章节大纲等上下文来回答
- 不要声称"没有设定"或"没有角色"，如果上下文中已经有项目信息，你必须告诉用户这些信息的内容
- 优先使用用户提供的信息，而不是说"还没有设定"

{world_type_hint}

你可以帮助用户：
- 添加新设定（根据项目类型添加相应的设定）
- 修改现有设定（注意影响范围和连带修改）
- 添加新角色（包括姓名、外貌、性格、背景、重要性层级等）
- 修改现有角色信息
- 解决设定冲突（提供多种解决方案）
- 查询和检索设定与角色
- 分析设定的一致性
- 规划伏笔和剧情线
"""
        return base_prompt

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

    async def _get_context_sections(self, project_id: str) -> Dict[str, str]:
        """
        获取项目上下文的分段信息（用于分段分析）

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
        logger.info(f"[SettingAgent] 开始为项目 {project_id} 构建分段上下文")

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
                            info += f"\n  内容风格：{', '.join(content_styles[:5])}"
                    # 新增：主角类型标签
                    protagonist_types = w.get('protagonist_types')
                    if protagonist_types:
                        if isinstance(protagonist_types, str):
                            try:
                                protagonist_types = json.loads(protagonist_types)
                            except:
                                protagonist_types = []
                        if isinstance(protagonist_types, list) and len(protagonist_types) > 0:
                            info += f"\n  主角类型：{', '.join(protagonist_types[:3])}"
                    # 新增：角色人设标签
                    character_archetypes = w.get('character_archetypes')
                    if character_archetypes:
                        if isinstance(character_archetypes, str):
                            try:
                                character_archetypes = json.loads(character_archetypes)
                            except:
                                character_archetypes = []
                        if isinstance(character_archetypes, list) and len(character_archetypes) > 0:
                            info += f"\n  角色人设模板：{', '.join(character_archetypes[:5])}"
                    # 新增：战斗能力标签
                    power_types = w.get('power_types')
                    if power_types:
                        if isinstance(power_types, str):
                            try:
                                power_types = json.loads(power_types)
                            except:
                                power_types = []
                        if isinstance(power_types, list) and len(power_types) > 0:
                            info += f"\n  战斗能力：{', '.join(power_types[:5])}"
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
                                info += f"\n  主要势力：{', '.join(faction_names[:5])}"
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
                                info += f"\n  世界规则：{', '.join(rule_names[:5])}"
                    world_info.append(info)
                if world_info:
                    sections["世界管理"] = "\n\n".join(world_info)
                    sections["_world_type"] = world_type or ""

            # 2. 已有设定信息
            try:
                lores = await conn.fetch("""
                    SELECT title, category, priority, summary, content
                    FROM lore_entries
                    WHERE project_id = $1
                    ORDER BY priority DESC, created_at DESC
                    LIMIT 15
                """, project_id)

                if lores:
                    lore_info = []
                    for lore in lores:
                        info = f"- {lore['title']} [{lore['category']}]"
                        if lore.get('summary'):
                            info += f"：{lore['summary']}"
                        lore_info.append(info)
                    sections["已有设定"] = "\n".join(lore_info)
            except Exception as e:
                logger.warning(f"获取 lore 失败: {e}")

            # 3. 角色信息
            try:
                characters = await conn.fetch("""
                    SELECT name, role, description
                    FROM characters
                    WHERE project_id = $1
                    ORDER BY created_at DESC
                    LIMIT 15
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
                    LIMIT 15
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
                    LIMIT 15
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
    ) -> tuple[str, str]:
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
            tuple[str, str]: (完整原始上下文, 关键信息索引)
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

        # 存储所有段落的关键信息点
        all_key_points = []

        # 按段落类型逐个处理
        section_order = ["世界管理", "已有设定", "角色列表", "伏笔列表", "章节大纲"]
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
                logger.debug(f"[分段分析] 内容预览: {section_content[:200]}...")
                key_points = await self._extract_key_points(
                    section_name, section_content, user_message, world_type_hint, project_id
                )
                if key_points:
                    all_key_points.extend(key_points)
                    failed_segments = 0  # 重置连续失败计数
                else:
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
                    logger.debug(f"[分段分析] 内容预览: {segment_content[:200]}...")

                    key_points = await self._extract_key_points(
                        segment_label, segment_content, user_message, world_type_hint, project_id
                    )
                    if key_points:
                        all_key_points.extend(key_points)
                        failed_segments = 0  # 重置连续失败计数
                    else:
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

        # 构建关键信息索引
        key_info_index = self._format_key_points_index(merged_key_points)

        return full_context, key_info_index

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
        prompt = f"""分析以下项目上下文片段，提取关键信息点（信息索引）。

## 世界类型
{world_type_hint if world_type_hint else "未指定"}

## 片段来源
{section_name}

## 片段内容
{segment_content}

## 用户问题
{user_question}

## 任务
提取关键信息点，格式如下（JSON数组）：
```json
[
  {{
    "category": "信息类型（如：世界观、角色、事件、规则、时间线等）",
    "entity": "实体名称（如：具体角色名、地点名、事件名）",
    "key_fact": "关键事实（一句话描述，保留具体细节）",
    "relevance": "与用户问题的相关性（高/中/低）"
  }}
]
```

## 重要规则
1. key_fact 必须包含具体细节，不要泛泛而谈
2. 如果有时间线信息，必须记录具体时间点
3. 如果有数值信息（等级、数量等），必须记录具体数值
4. 保持信息点的独立性，每个信息点只描述一个事实

只输出JSON数组，不要其他内容。"""

        try:
            result = await self._call_llm_simple(prompt)

            # 检查是否是错误响应
            if not result or "抱歉" in result or "无法处理" in result or "请稍后" in result:
                logger.warning(f"[分段分析] LLM 返回错误响应: {result[:100] if result else '空响应'}")
                return []

            # 解析JSON
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            result = result.strip()
            if not result or result == "[]":
                return []

            key_points = json.loads(result)
            if isinstance(key_points, list):
                return key_points
            return []

        except json.JSONDecodeError as e:
            logger.warning(f"[分段分析] JSON解析失败: {e}")
            return []
        except Exception as e:
            logger.warning(f"[分段分析] 关键信息提取失败: {e}")
            return []

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
            key = (point.get("entity", ""), point.get("key_fact", "")[:50])  # 用前50字符判断重复
            if key not in seen:
                seen.add(key)
                unique_points.append(point)

        # 限制数量，避免索引过长
        return unique_points[:50]

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

        last_error = None
        for attempt in range(self._max_retries):
            try:
                if self.llm_provider == "openai":
                    response, usage = await self._call_openai_with_usage(messages)
                elif self.llm_provider == "anthropic":
                    response, usage = await self._call_anthropic_with_usage(messages)
                else:
                    response, usage = await self._call_openai_with_usage(messages)

                # 记录 token 使用
                if project_id and usage:
                    await self._record_token_usage(project_id, usage, input_tokens)

                # 成功，重置失败计数
                self._consecutive_failures = 0
                self._last_failure_time = None
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
        """构建 Bootstrap 提示"""
        return """你是一个长篇网络小说设定专家（Setting Agent）。你的职责是：

1. 与用户沟通，了解他们想要创作的长篇网络小说世界观、主线、风格、角色等设定
2. 通过多轮对话发现信息缺口并追问用户
3. 提炼出结构化的项目 seed，为后续 bootstrap 提供可靠输入

【重要：本项目定位为长篇网络小说】
- 目标篇幅：百万字以上，多卷结构
- 目标读者：网络小说读者，注重节奏感和爽点
- 创作周期：长期连载，需要完善的设定支撑

请遵循以下原则：
- 严格根据用户描述的世界类型（科幻/奇幻/现代/历史/武侠/其他）来设定，不要混入其他类型的内容
- 保持友好、耐心的态度
- 每次回答后，主动追问用户尚未提供的关键信息
- 使用清晰的结构化格式组织信息

【世界类型区分参考】
- 科幻：高科技、太空探索、人工智能、基因工程等，遵守科学逻辑
- 奇幻：魔法、精灵、怪物、异世界等
- 现代：当代都市、社会题材
- 历史：古代/近代历史背景
- 武侠：江湖、武功、门派、恩怨

【长篇网文核心设定要素】
1. 世界观：类型、规则、力量体系、势力格局（必须符合用户指定的世界类型）
2. 主角：背景、金手指、成长路线、性格
3. 配角体系：核心配角、重要NPC、对手反派
4. 剧情架构：主线、分卷规划、爽点设计、伏笔计划
5. 风格基调：热血/轻松/黑暗/爽文等
"""

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

    async def _extract_seed_from_history(self, session: BootstrapSession) -> Optional[Dict[str, Any]]:
        """从历史提取 seed"""
        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in session.setting_agent_history
        ])

        extraction_prompt = f"""请从以下对话中提取结构化的项目 seed。输出 JSON 格式：
{{
    "world_setting": {{"name": "", "description": "", "world_type": "", "tone": ""}},
    "world_rules": [],
    "power_system": "",
    "main_characters": [],
    "regions": [],
    "plot_hooks": [],
    "narrative_tone": ""
}}

对话历史：
{history_text}

只输出 JSON。
"""
        try:
            response = await self._call_llm_simple(extraction_prompt)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
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
