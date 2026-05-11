"""
Agent 通信服务
v8 Agent协作可视化工作台
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from app.models.intervention import InterventionLog, InterventionType
from app.services.md_file_service import get_md_file_service

logger = logging.getLogger(__name__)

# 干预类型说明（用于分类提示）
INTERVENTION_TYPE_DESCRIPTIONS = {
    InterventionType.GUIDANCE: "指导性干预 - 提供建议、提示或方向引导，不改变原有计划",
    InterventionType.CORRECTION: "纠正性干预 - 指出错误并要求修正，如事实错误、逻辑问题、人物性格不符",
    InterventionType.DIRECTION: "方向性干预 - 改变剧情走向或决策方向，如引入新情节、改变结局",
    InterventionType.OVERRIDE: "覆盖性干预 - 直接替换或强制指定内容，如修改对话、强制角色行为",
}


class AgentCommunicationService:
    """Agent通信服务 - 处理与Agent的交互和干预"""

    INTERVENTION_CLASSIFICATION_PROMPT_ID = "function_agent_intervention_classification"

    def __init__(self):
        # Agent 工厂回调
        self._agent_factory: Optional[Callable] = None
        # 干预日志服务
        self._intervention_service = None
        # 消息历史缓存
        self._message_history: Dict[str, list] = {}
        # 干预类型缓存（避免重复分类）
        self._type_cache: Dict[str, InterventionType] = {}

    def set_agent_factory(self, factory: Callable):
        """设置 Agent 实例工厂"""
        self._agent_factory = factory

    def set_intervention_service(self, service):
        """设置干预日志服务"""
        self._intervention_service = service

    async def classify_intervention_type(
        self,
        message: str,
        target_agent_type: str,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> InterventionType:
        """
        自动分类干预类型

        使用编剧Agent分析干预消息，判断属于哪种干预类型

        Args:
            message: 用户干预消息
            target_agent_type: 目标Agent类型
            project_id: 项目ID
            context: 上下文信息

        Returns:
            InterventionType: 分类结果
        """
        try:
            # 获取编剧 Agent
            plotter = await self._agent_factory("master_plotter", project_id)
            if not plotter:
                logger.warning("无法获取编剧Agent，使用默认干预类型")
                return InterventionType.GUIDANCE

            classification_prompt = self._build_intervention_classification_prompt(
                message=message,
                target_agent_type=target_agent_type,
                context=context,
            )

            result = await plotter._call_llm(classification_prompt)
            intervention_type = self._normalize_intervention_type_result(result or "")
            if intervention_type:
                logger.info(f"干预类型分类: {message[:30]}... -> {intervention_type.value}")
                return intervention_type

            # 默认返回指导性干预
            logger.info(f"干预类型分类失败，使用默认值: guidance")
            return InterventionType.GUIDANCE

        except Exception as e:
            logger.warning(f"干预类型分类异常: {e}，使用默认值")
            return InterventionType.GUIDANCE

    def _load_prompt_asset(self, prompt_id: str) -> str:
        """读取 md prompt 资产内容；失败时返回空字符串，由调用方决定降级策略。"""
        try:
            prompt = get_md_file_service().get_prompt(prompt_id)
        except Exception as e:
            logger.warning("读取 Agent 通信 Prompt 资产失败 %s: %s", prompt_id, e)
            return ""

        content = (prompt or {}).get("content") or (prompt or {}).get("raw_content") or ""
        return str(content).strip()

    def _build_intervention_classification_prompt(
        self,
        *,
        message: str,
        target_agent_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        prompt_asset = self._load_prompt_asset(self.INTERVENTION_CLASSIFICATION_PROMPT_ID)
        if not prompt_asset:
            logger.warning("Agent 干预分类 Prompt 资产缺失: %s", self.INTERVENTION_CLASSIFICATION_PROMPT_ID)
            prompt_asset = (
                "【DEPRECATED 最小 fallback】判断用户对 Agent 的干预类型；"
                "只能输出 guidance、correction、direction 或 override 中的一个英文枚举。"
            )

        type_descriptions = "\n".join([
            f"- {t.value}: {desc}"
            for t, desc in INTERVENTION_TYPE_DESCRIPTIONS.items()
        ])
        context_text = json.dumps(context, ensure_ascii=False, indent=2, default=str) if context else "无"

        return "\n\n".join([
            prompt_asset,
            f"## 目标 Agent\n{self._get_agent_name(target_agent_type)} ({target_agent_type})",
            f"## 干预类型定义\n{type_descriptions}",
            f"## 用户干预消息\n{message}",
            f"## 上下文信息\n{context_text}",
        ]).strip()

    def _normalize_intervention_type_result(self, result: str) -> Optional[InterventionType]:
        result_text = str(result or "").strip().lower()
        if not result_text:
            return None

        cleaned = re.sub(r"[^a-z_\-]+", " ", result_text)
        tokens = {token.replace("-", "_") for token in cleaned.split() if token}
        for int_type in InterventionType:
            if int_type.value in tokens:
                return int_type

        return None

    async def send_agent_message(
        self,
        execution_id: str,
        agent_type: str,
        message: str,
        project_id: str,
        node_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        auto_classify: bool = True,
        assistant_session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        db: Any = None,
    ) -> Dict[str, Any]:
        """
        向 Agent 发送消息并获取响应

        Args:
            execution_id: 工作流执行ID
            agent_type: Agent类型
            message: 用户消息
            project_id: 项目ID
            node_id: 关联的节点ID
            context: 上下文信息
            auto_classify: 是否自动分类干预类型
            assistant_session_id: Assistant Context 会话 ID
            request_id: 幂等请求 ID
            db: 数据库连接，用于持久化 Assistant Context 与干预日志

        Returns:
            Dict: 包含响应和相关信息
        """
        if not self._agent_factory:
            raise ValueError("Agent factory 未设置")

        start_time = time.time()

        try:
            # 自动分类干预类型
            intervention_type = InterventionType.GUIDANCE
            if auto_classify:
                intervention_type = await self.classify_intervention_type(
                    message=message,
                    target_agent_type=agent_type,
                    project_id=project_id,
                    context=context,
                )

            # 获取 Agent 实例
            agent = await self._agent_factory(agent_type, project_id)
            if not agent:
                raise ValueError(f"无法获取 Agent: {agent_type}")

            context_packet = await self._build_workflow_context_packet(
                db=db,
                project_id=project_id,
                execution_id=execution_id,
                agent_type=agent_type,
                node_id=node_id,
                message=message,
                context=context,
                assistant_session_id=assistant_session_id,
                request_id=request_id,
            )
            packet_context = context_packet.get("prompt_context") if context_packet else ""
            input_context = {
                **(context or {}),
                "assistant_context_packet_id": context_packet.get("packet_id") if context_packet else None,
                "assistant_context_snapshot_version": context_packet.get("snapshot_version") if context_packet else None,
                "assistant_context": packet_context,
            }

            # 构建输入
            input_data = {
                "user_message": message,
                "context": input_context,
                "mode": "intervention",  # 标记为干预模式
                "intervention_type": intervention_type.value,  # 传递干预类型
            }

            # 调用 Agent
            result = await agent.execute(input_data)
            agent_response = result.data if result.success else {"error": result.error}

            # 计算响应时间
            response_time_ms = int((time.time() - start_time) * 1000)

            # 记录干预日志
            intervention_id = None
            if self._intervention_service:
                intervention = InterventionLog(
                    project_id=project_id,
                    workflow_execution_id=execution_id,
                    node_id=node_id,
                    agent_type=agent_type,
                    agent_name=self._get_agent_name(agent_type),
                    intervention_type=intervention_type,
                    user_message=message,
                    agent_response=str(agent_response),
                    context_snapshot=input_context,
                    response_time_ms=response_time_ms,
                )
                intervention_id = await self._intervention_service.log_intervention(intervention, db=db)

            await self._append_workflow_assistant_response(
                db=db,
                context_packet=context_packet,
                response=str(agent_response),
                request_id=request_id,
            )

            # 缓存消息历史（仅作为无 DB 场景的临时视图；持久权威为 assistant_messages/intervention_logs）
            history_key = f"{execution_id}:{agent_type}"
            if history_key not in self._message_history:
                self._message_history[history_key] = []
            self._message_history[history_key].append({
                "timestamp": datetime.now().isoformat(),
                "user_message": message,
                "agent_response": agent_response,
                "intervention_type": intervention_type.value,
                "assistant_session_id": context_packet.get("session_id") if context_packet else assistant_session_id,
                "context_packet_id": context_packet.get("packet_id") if context_packet else None,
            })

            logger.info(f"Agent通信完成: {agent_type}, 类型: {intervention_type.value}, 响应时间: {response_time_ms}ms")

            return {
                "success": result.success,
                "agent_type": agent_type,
                "agent_name": self._get_agent_name(agent_type),
                "response": agent_response,
                "response_time_ms": response_time_ms,
                "intervention_id": intervention_id,
                "intervention_type": intervention_type.value,
                "assistant_session_id": context_packet.get("session_id") if context_packet else assistant_session_id,
                "context_packet": self._context_packet_metadata(context_packet),
            }

        except Exception as e:
            logger.error(f"Agent通信失败: {e}")
            return {
                "success": False,
                "agent_type": agent_type,
                "error": str(e),
                "response_time_ms": int((time.time() - start_time) * 1000),
            }

    async def get_agent_instance(self, agent_type: str, project_id: str):
        """获取 Agent 实例"""
        if not self._agent_factory:
            return None

        return await self._agent_factory(agent_type, project_id)

    async def broadcast_agent_status(
        self,
        execution_id: str,
        agent_type: str,
        status: str,
        message: Optional[str] = None,
        broadcast_callback: Optional[Callable] = None,
    ):
        """广播 Agent 状态"""
        if broadcast_callback:
            await broadcast_callback(execution_id, "agent_status", {
                "agent_type": agent_type,
                "status": status,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            })

    async def _build_workflow_context_packet(
        self,
        *,
        db: Any,
        project_id: str,
        execution_id: str,
        agent_type: str,
        node_id: Optional[str],
        message: str,
        context: Optional[Dict[str, Any]],
        assistant_session_id: Optional[str],
        request_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not db:
            return None
        try:
            from app.services.assistant_context import get_assistant_context_fabric

            scope = {
                "workflow_execution_id": execution_id,
                "node_id": node_id,
                "agent_type": agent_type,
                "surface_entry": "workflow_private_chat",
                "workflow_context": context or {},
                "needs": ["workflow_state", "chapter_outlines", "plot_hooks", "characters", "lore", "recent_deltas"],
            }
            packet = await get_assistant_context_fabric(db).build_packet(
                project_id=project_id,
                assistant_surface="workflow_intervention",
                task_type="private_chat",
                session_id=assistant_session_id,
                mode=f"execution:{execution_id}:agent:{agent_type}",
                request_id=request_id,
                scope=scope,
                user_message=message,
            )
            logger.info(
                "[WorkflowIntervention] 使用 Assistant Context Fabric packet=%s snapshot=v%s tokens=%s",
                packet.get("packet_id"),
                packet.get("snapshot_version"),
                packet.get("metadata", {}).get("token_estimate"),
            )
            return packet
        except Exception:
            logger.warning("构建 Workflow Intervention Assistant Context packet 失败", exc_info=True)
            return None

    def _context_packet_metadata(self, context_packet: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not context_packet:
            return None
        return {
            "packet_id": context_packet.get("packet_id"),
            "snapshot_id": context_packet.get("snapshot_id"),
            "snapshot_version": context_packet.get("snapshot_version"),
            **(context_packet.get("metadata") or {}),
        }

    async def _append_workflow_assistant_response(
        self,
        *,
        db: Any,
        context_packet: Optional[Dict[str, Any]],
        response: str,
        request_id: Optional[str],
    ) -> None:
        if not db or not context_packet:
            return
        try:
            assistant_session_id = context_packet.get("session_id")
            assistant_session = await db.get_assistant_session(assistant_session_id) if assistant_session_id else None
            if not assistant_session:
                return
            from app.services.assistant_context import get_assistant_context_fabric

            await get_assistant_context_fabric(db).sessions.append_message(
                session=assistant_session,
                role="assistant",
                content=response,
                request_id=request_id,
                metadata={"context_packet_id": context_packet.get("packet_id"), "surface_entry": "workflow_private_chat"},
                packet_id=context_packet.get("packet_id"),
                snapshot_id=context_packet.get("snapshot_id"),
            )
        except Exception:
            logger.warning("记录 Workflow Intervention Assistant Context 助手回复失败", exc_info=True)

    def get_message_history(
        self,
        execution_id: str,
        agent_type: Optional[str] = None,
    ) -> list:
        """获取消息历史"""
        if agent_type:
            key = f"{execution_id}:{agent_type}"
            return self._message_history.get(key, [])

        # 返回该执行的所有消息
        all_messages = []
        for key, messages in self._message_history.items():
            if key.startswith(f"{execution_id}:"):
                all_messages.extend(messages)
        return sorted(all_messages, key=lambda x: x["timestamp"])

    def clear_message_history(self, execution_id: str):
        """清除消息历史"""
        keys_to_remove = [k for k in self._message_history if k.startswith(f"{execution_id}:")]
        for key in keys_to_remove:
            del self._message_history[key]

    def _get_agent_name(self, agent_type: str) -> str:
        """获取 Agent 显示名称"""
        names = {
            "setting": "设定 Agent",
            "writer": "作家 Agent",
            "master_plotter": "总编剧 Agent",
            "summarizer": "摘要 Agent",
            "hook_manager": "伏笔管理 Agent",
            "evaluator": "评估 Agent",
            "character": "角色 Agent",
            "event_generator": "事件生成 Agent",
            "dungeon_generator": "副本生成 Agent",
            "world_map_manager": "世界地图 Agent",
            "proc_gen": "过程生成 Agent",
            "procgen": "过程生成 Agent",
        }
        return names.get(agent_type, agent_type)


# 全局单例
_agent_communication_service: Optional[AgentCommunicationService] = None


def get_agent_communication_service() -> AgentCommunicationService:
    """获取 Agent 通信服务单例"""
    global _agent_communication_service
    if _agent_communication_service is None:
        _agent_communication_service = AgentCommunicationService()
    return _agent_communication_service


def set_agent_communication_service(service: AgentCommunicationService):
    """设置 Agent 通信服务实例"""
    global _agent_communication_service
    _agent_communication_service = service
