"""
设定 Agent 服务
v4 核心需求：与用户多轮沟通、追问补全设定、提炼结构化 seed
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.bootstrap import BootstrapSession, BootstrapStage, BootstrapMessage
from app.services.md_file_service import get_md_file_service

logger = logging.getLogger(__name__)


class SettingAgent:
    """设定 Agent - 负责与用户沟通项目设定，提炼结构化 seed"""

    BOOTSTRAP_COLLECTION_PROMPT_ID = "function_setting_bootstrap_collection"
    BOOTSTRAP_SEED_EXTRACTION_PROMPT_ID = "function_setting_bootstrap_seed_extraction"

    def __init__(self):
        self.llm_provider = settings.llm_provider
        # 获取当前 provider 的配置
        llm_config = settings.get_llm_config(self.llm_provider)
        self.llm_api_key = llm_config.get("api_key", "")
        self.llm_base_url = llm_config.get("base_url", "")
        self.llm_model = llm_config.get("model", "")
        self.llm_temperature = llm_config.get("temperature", 0.7)
        self.llm_max_tokens = llm_config.get("max_tokens", 4096)
        self._sessions: Dict[str, BootstrapSession] = {}

    async def process_message(self, session_id: str, message: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        处理用户消息，与用户多轮对话并提炼设定

        Args:
            session_id: Bootstrap 会话 ID
            message: 用户消息
            project_id: 项目 ID（可选，用于会话恢复）

        Returns:
            Dict: Agent 响应
        """
        # 始终从 BootstrapOrchestrator 获取会话（确保单例一致性）
        from app.services.bootstrap_orchestrator import get_bootstrap_orchestrator
        orchestrator = get_bootstrap_orchestrator()
        session = await orchestrator.get_session(session_id)

        if not session:
            logger.warning(f"Session {session_id} not found in orchestrator. Available sessions: {list(orchestrator._sessions.keys())}")
            # 尝试恢复会话（服务重启后内存会话丢失）
            if project_id:
                logger.info(f"Attempting to recover session {session_id} with project_id {project_id}")
                session = BootstrapSession(
                    id=session_id,
                    project_id=project_id,
                    status=BootstrapStage.COLLECTING_SETTING,
                    current_stage=BootstrapStage.COLLECTING_SETTING,
                    progress=0.1,
                )
                # 保存恢复的会话
                orchestrator._sessions[session_id] = session
                logger.info(f"Session {session_id} recovered")
            else:
                raise ValueError(f"Session {session_id} not found and no project_id provided for recovery")

        # 添加用户消息到历史
        user_msg = BootstrapMessage(
            role="user",
            content=message,
            timestamp=datetime.now(),
        )
        session.setting_agent_history.append(user_msg.model_dump(mode="json"))

        # 构建提示词
        system_prompt = self._build_system_prompt(session)
        conversation_context = self._build_conversation_context(session)

        # 调用 LLM
        response_content = await self._call_llm(
            system_prompt=system_prompt,
            user_message=message,
            context=conversation_context,
        )

        # 添加助手回复到历史
        assistant_msg = BootstrapMessage(
            role="assistant",
            content=response_content,
            timestamp=datetime.now(),
        )
        session.setting_agent_history.append(assistant_msg.model_dump(mode="json"))

        # 检查是否需要提取 seed
        seed_extracted = await self._check_and_extract_seed(session)
        await orchestrator._persist_session(session)

        return {
            "response": response_content,
            "session_id": session_id,
            "stage": session.current_stage.value,
            "seed_extracted": seed_extracted,
            "seed_data": session.extracted_seed if seed_extracted else None,
        }

    def _build_system_prompt(self, session: BootstrapSession) -> str:
        """构建系统提示词（稳定 Bootstrap 规则来自 md prompt 资产）。"""
        return self._load_prompt_asset(
            self.BOOTSTRAP_COLLECTION_PROMPT_ID,
            fallback=(
                "【DEPRECATED 最小 fallback】你是长篇网络小说设定专家（Setting Agent）。请通过多轮对话收集世界观、"
                "角色、主线、风格和关键设定；主动追问缺口，并保持所有内容为待确认草案。"
            ),
        )

    def _load_prompt_asset(self, prompt_id: str, fallback: str = "") -> str:
        """读取 md prompt 资产内容；失败时返回调用方提供的极简兼容降级。"""
        try:
            prompt = get_md_file_service().get_prompt(prompt_id)
        except Exception as e:
            logger.warning("读取 Setting Prompt 资产失败 %s: %s", prompt_id, e)
            prompt = None

        content = (prompt or {}).get("content") or (prompt or {}).get("raw_content") or ""
        content = str(content).strip()
        if content:
            return content

        logger.warning("Setting Prompt 资产缺失: %s", prompt_id)
        return fallback

    def _build_conversation_context(self, session: BootstrapSession) -> str:
        """构建对话上下文"""
        if not session.setting_agent_history:
            return "这是对话的开始，用户将向你介绍他们的故事设定。"

        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in session.setting_agent_history[-10:]  # 最近 10 条
        ])
        return f"最近的对话历史：\n{history_text}"

    async def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> str:
        """调用 LLM 生成响应"""
        # 构建消息列表
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"上下文信息：\n{context}"},
            {"role": "user", "content": user_message},
        ]

        try:
            # 根据不同的 LLM 提供商调用
            if self.llm_provider == "openai":
                return await self._call_openai(messages)
            elif self.llm_provider == "anthropic":
                return await self._call_anthropic(messages)
            else:
                # 默认使用 OpenAI 兼容接口
                return await self._call_openai(messages)
        except Exception as e:
            logger.error(f"LLM 调用失败：{e}")
            return "抱歉，我现在无法处理你的请求。请稍后再试。"

    async def _call_openai(self, messages: List[Dict[str, Any]]) -> str:
        """调用 OpenAI API"""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.error("[SettingAgent] openai 包未安装，请运行: pip install openai")
            return self._fallback_response(messages)

        # 检查 API Key 是否配置
        if not self.llm_api_key:
            logger.error("[SettingAgent] OpenAI API Key 未配置！请检查 .env 文件中的 LLM_OPENAI_API_KEY")
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
            logger.error("[SettingAgent] anthropic 包未安装，请运行: pip install anthropic")
            return self._fallback_response(messages)

        # 检查 API Key 是否配置
        if not self.llm_api_key:
            logger.error("[SettingAgent] Anthropic API Key 未配置！请检查 .env 文件中的 LLM_ANTHROPIC_API_KEY")
            return self._fallback_response(messages)

        client = anthropic.AsyncAnthropic(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url or "https://api.anthropic.com",
        )

        # 转换消息格式
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

        # 提取文本内容（处理 ThinkingBlock 等不同类型）
        text_content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                text_content += block.text
            elif hasattr(block, 'thinking'):
                # ThinkingBlock 跳过
                pass
            else:
                text_content += str(block)

        return text_content

    def _fallback_response(self, messages: List[Dict[str, Any]]) -> str:
        """回退响应（当没有 LLM 可用时）"""
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        return f"我收到了你的消息：'{last_user_msg}'。\n\n为了继续完善故事设定，请告诉我更多关于：\n- 故事的背景时代\n- 主要角色的性格特点\n- 你希望故事传达的主题"

    async def _check_and_extract_seed(self, session: BootstrapSession) -> bool:
        """
        检查是否需要提取 seed

        当对话达到一定轮数或用户明确要求时，提取结构化 seed
        """
        # 检查对话轮数（用户消息数量）
        user_message_count = sum(
            1 for msg in session.setting_agent_history
            if msg.get("role") == "user"
        )

        # 对话超过 3 轮且尚未提取 seed，可以尝试提取
        if user_message_count >= 3 and not session.extracted_seed:
            # 尝试从历史对话中提取 seed
            extracted = await self.extract_seed_from_history(session)
            if extracted:
                session.extracted_seed = extracted
                session.current_stage = BootstrapStage.SEED_EXTRACTED
                session.progress = 0.4
                return True

        return False

    async def extract_seed_from_history(self, session: BootstrapSession) -> Optional[Dict[str, Any]]:
        """
        从对话历史中提取结构化 seed（公共方法）

        Args:
            session: Bootstrap 会话

        Returns:
            Optional[Dict]: 提取的 seed 数据，失败返回 None
        """
        # 构建提取 prompt
        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in session.setting_agent_history
        ])

        extraction_prompt = f"## 对话历史\n{history_text}".strip()

        try:
            response = await self._call_llm(
                system_prompt=self._load_prompt_asset(
                    self.BOOTSTRAP_SEED_EXTRACTION_PROMPT_ID,
                    fallback="【DEPRECATED 最小 fallback】请从对话历史中提取结构化项目 seed，只输出 JSON 对象，不要输出其他内容。",
                ),
                user_message=extraction_prompt,
                context="",
            )

            # 解析 JSON
            # 尝试找到 JSON 块
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            seed_data = json.loads(response.strip())
            return seed_data

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"提取 seed 失败：{e}")
            return None

    async def create_session(self, project_id: str, initial_message: Optional[str] = None) -> BootstrapSession:
        """
        创建新的 SettingAgent 会话

        Args:
            project_id: 项目 ID
            initial_message: 可选的初始消息

        Returns:
            BootstrapSession: Bootstrap 会话
        """
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

        # 如果有初始消息，自动处理
        if initial_message:
            await self.process_message(session_id, initial_message)

        return session

    async def get_session(self, session_id: str) -> Optional[BootstrapSession]:
        """获取会话"""
        return self._sessions.get(session_id)

    async def update_session(self, session: BootstrapSession):
        """更新会话"""
        self._sessions[session.id] = session


# 全局单例
_setting_agent: Optional[SettingAgent] = None


def get_setting_agent() -> SettingAgent:
    """获取 SettingAgent 单例"""
    global _setting_agent
    if _setting_agent is None:
        _setting_agent = SettingAgent()
    return _setting_agent


def set_setting_agent(agent: SettingAgent):
    """设置 SettingAgent 实例（用于测试）"""
    global _setting_agent
    _setting_agent = agent