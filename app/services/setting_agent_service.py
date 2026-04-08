"""
设定 Agent 服务
v6 核心需求：持续设定管理、冲突检测、协商解决
"""

import json
import logging
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
from app.services.conflict_detector import ConflictDetector, get_conflict_detector

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

        # 会话存储
        self._sessions: Dict[str, BootstrapSession] = {}
        self._management_sessions: Dict[str, SettingAgentSession] = {}
        self._knowledge_indices: Dict[str, LoreKnowledgeIndex] = {}

        # 冲突检测器
        self._conflict_detector = get_conflict_detector()

        # 协商会话
        self._negotiation_sessions: Dict[str, NegotiationSession] = {}

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
        # TODO: 从数据库加载
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

        # 构建系统提示
        system_prompt = self._build_management_system_prompt(session)

        # 构建上下文
        context_str = await self._build_chat_context(session, context)

        # 调用 LLM
        response = await self._call_llm(system_prompt, message, context_str)

        # 添加助手回复到历史
        session.conversation_history.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })

        session.last_activity_at = datetime.now()

        # 自动分析并更新项目元数据（每5次对话触发一次）
        if len(session.conversation_history) % 10 == 0:  # 每5次用户消息
            metadata_results = await self.analyze_and_update_project_metadata(
                project_id,
                session.conversation_history,
            )
            if metadata_results.get("updated"):
                logger.info(f"自动更新项目 {project_id} 元数据: {metadata_results}")

        return {
            "response": response,
            "session_id": session.id,
            "mode": session.mode.value,
        }

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

    def _build_management_system_prompt(self, session: SettingAgentSession) -> str:
        """构建管理模式系统提示"""
        return """你是一个专业的小说设定管理者（Setting Agent）。你的职责是：

1. 维护项目的世界观设定，确保设定的一致性
2. 帮助用户添加、修改、删除设定
3. 检测和处理设定冲突
4. 提供设定建议和优化方案

请遵循以下原则：
- 保持设定的内在一致性
- 注意宪法级规则，任何新设定都不能违反它们
- 当发现潜在冲突时，及时提醒用户并提供解决方案
- 用清晰、结构化的方式组织信息

你可以帮助用户：
- 添加新设定（世界规则、地理、势力、种族等）
- 修改现有设定
- 解决设定冲突
- 查询和检索设定
- 分析设定的一致性
"""

    async def _build_chat_context(
        self,
        session: SettingAgentSession,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建聊天上下文"""
        parts = []

        # 添加对话历史
        if session.conversation_history:
            history = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in session.conversation_history[-10:]
            ])
            parts.append(f"最近对话：\n{history}")

        # 添加待处理冲突
        if session.pending_conflicts:
            conflicts_str = "\n".join([
                f"- {c.description} (严重程度: {c.severity.value})"
                for c in session.pending_conflicts
            ])
            parts.append(f"待处理冲突：\n{conflicts_str}")

        # 添加额外上下文
        if extra_context:
            parts.append(f"额外信息：{json.dumps(extra_context, ensure_ascii=False)}")

        return "\n\n".join(parts)

    # ==================== LLM 调用 ====================

    async def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> str:
        """调用 LLM 生成响应"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"上下文信息：\n{context}"},
            {"role": "user", "content": user_message},
        ]

        try:
            if self.llm_provider == "openai":
                return await self._call_openai(messages)
            elif self.llm_provider == "anthropic":
                return await self._call_anthropic(messages)
            else:
                return await self._call_openai(messages)
        except Exception as e:
            logger.error(f"LLM 调用失败：{e}")
            return "抱歉，我现在无法处理你的请求。请稍后再试。"

    async def _call_llm_simple(self, prompt: str) -> str:
        """简化的 LLM 调用"""
        return await self._call_llm(
            system_prompt="你是一个有帮助的助手。",
            user_message=prompt,
            context="",
        )

    async def _call_openai(self, messages: List[Dict[str, Any]]) -> str:
        """调用 OpenAI API"""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return self._fallback_response(messages)

        client = AsyncOpenAI(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url or "https://api.openai.com/v1",
        )

        response = await client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            temperature=self.llm_temperature,
            max_tokens=self.llm_max_tokens,
        )

        return response.choices[0].message.content

    async def _call_anthropic(self, messages: List[Dict[str, Any]]) -> str:
        """调用 Anthropic API"""
        try:
            import anthropic
        except ImportError:
            return self._fallback_response(messages)

        client = anthropic.AsyncAnthropic(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url or "https://api.anthropic.com",
        )

        system_message = messages[0]["content"]
        claude_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages[1:] if m["role"] != "system"
        ]

        response = await client.messages.create(
            model=self.llm_model,
            system=system_message,
            messages=claude_messages,
            temperature=self.llm_temperature,
            max_tokens=self.llm_max_tokens,
        )

        return response.content[0].text

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

        # 调用 LLM
        response = await self._call_llm(system_prompt, message, context)

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
        return """你是一个小说设定专家（Setting Agent）。你的职责是：

1. 与用户沟通，了解他们想要创作的小说世界观、主线、风格、角色等设定
2. 通过多轮对话发现信息缺口并追问用户
3. 提炼出结构化的项目 seed，为后续 bootstrap 提供可靠输入

请遵循以下原则：
- 保持友好、耐心的态度
- 每次回答后，可以主动追问用户尚未提供的关键信息
- 使用清晰的结构化格式组织信息
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
