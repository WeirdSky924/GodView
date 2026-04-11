"""
Agent 基类
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseLanguageModel

from app.models.token_usage import UsageCategory
from app.services.token_tracker import token_tracker

logger = logging.getLogger(__name__)


class AgentResponse(BaseModel):
    """Agent 响应基类"""

    success: bool = Field(default=True, description="是否成功")
    data: Optional[Any] = Field(default=None, description="响应数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    class Config:
        arbitrary_types_allowed = True


class BaseAgent(ABC):
    """Agent 基类"""

    # 类属性，子类必须覆盖
    AGENT_TYPE: Optional[str] = None

    def __init__(
        self,
        name: str,
        model: Optional[BaseLanguageModel] = None,
        system_prompt: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
    ):
        self.name = name
        self.model = model
        self.config = config or {}
        self.project_id = project_id
        self.message_history: List = []
        self._lock = asyncio.Lock()
        # 流式输出回调（由 workflow_engine 设置）
        self._stream_callback: Optional[callable] = None

        # 如果有 project_id 且没有手动指定 system_prompt，尝试从模板加载
        if project_id and not system_prompt and self.AGENT_TYPE:
            self.system_prompt = self._load_system_prompt()
        else:
            self.system_prompt = system_prompt or ""

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        pass

    @abstractmethod
    def _get_default_variables(self) -> Dict[str, Any]:
        """
        获取默认变量（子类实现）

        Returns:
            Dict: 默认变量字典，用于 Prompt 模板渲染
        """
        pass

    def _load_system_prompt(self) -> str:
        """
        从模板系统加载 system prompt

        Returns:
            str: 加载的 system prompt，如果无法加载则返回空字符串
        """
        if not self.project_id or not self.AGENT_TYPE:
            return ""

        # 尝试从 AgentPromptService 加载
        try:
            import asyncio
            from app.services.agent_prompt_service import get_agent_prompt_service

            service = get_agent_prompt_service()

            # 尝试在已有事件循环中运行
            try:
                loop = asyncio.get_running_loop()
                # 如果已有事件循环，创建一个任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        service.build_agent_prompt(
                            agent_type=self.AGENT_TYPE,
                            project_id=self.project_id,
                        )
                    )
                    prompt = future.result(timeout=5)
            except RuntimeError:
                # 没有运行中的事件循环
                prompt = asyncio.run(
                    service.build_agent_prompt(
                        agent_type=self.AGENT_TYPE,
                        project_id=self.project_id,
                    )
                )

            if prompt:
                logger.debug(f"Agent {self.name} 从模板加载 prompt 成功 (project={self.project_id}, type={self.AGENT_TYPE})")
                return prompt

        except Exception as e:
            logger.warning(f"Agent {self.name} 加载 prompt 失败: {e}")

        logger.debug(f"Agent {self.name} 尝试从模板加载 prompt (project={self.project_id}, type={self.AGENT_TYPE})")
        return ""

    async def _call_llm(
        self,
        messages: List,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        category: UsageCategory = UsageCategory.OTHER,
    ) -> str:
        if not self.model:
            raise ValueError(f"Agent {self.name} 未配置模型")

        # 如果设置了流式回调，使用流式输出
        if self._stream_callback:
            return await self._stream_llm(
                messages, temperature, max_tokens, category,
                on_chunk=self._stream_callback
            )

        if self.system_prompt:
            messages = [SystemMessage(content=self.system_prompt)] + messages

        response = await self.model.ainvoke(messages)
        content = response.content

        # 尝试从响应中获取实际 token 使用量
        input_tokens = 0
        output_tokens = 0

        # LangChain 响应对象包含 usage_metadata
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = response.usage_metadata.get('input_tokens', 0)
            output_tokens = response.usage_metadata.get('output_tokens', 0)
        elif hasattr(response, 'response_metadata') and response.response_metadata:
            # OpenAI 格式
            token_usage = response.response_metadata.get('token_usage', {})
            if token_usage:
                input_tokens = token_usage.get('prompt_tokens', 0)
                output_tokens = token_usage.get('completion_tokens', 0)

        # 如果无法获取实际值，使用估算
        if input_tokens == 0:
            input_tokens = sum(len(msg.content) // 4 for msg in messages)
        if output_tokens == 0:
            output_tokens = len(content) // 4

        self._record_token_usage(input_tokens, output_tokens, category)

        return content

    async def _stream_llm(
        self,
        messages: List,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        category: UsageCategory = UsageCategory.OTHER,
        on_chunk: Optional[callable] = None,
    ) -> str:
        """
        流式调用 LLM，支持实时输出

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            category: 使用类别
            on_chunk: 每个 chunk 的回调函数，接收 (chunk_text: str) 参数

        Returns:
            str: 完整的响应内容
        """
        if not self.model:
            raise ValueError(f"Agent {self.name} 未配置模型")

        if self.system_prompt:
            messages = [SystemMessage(content=self.system_prompt)] + messages

        full_content = ""
        last_chunk = None
        chunk_count = 0

        try:
            logger.info(f"Agent {self.name} 开始流式调用 LLM...")
            # 使用 astream 进行流式输出
            async for chunk in self.model.astream(messages):
                chunk_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_content += chunk_text
                last_chunk = chunk
                chunk_count += 1

                # 调用回调函数
                if on_chunk:
                    try:
                        await on_chunk(chunk_text) if asyncio.iscoroutinefunction(on_chunk) else on_chunk(chunk_text)
                    except Exception as e:
                        logger.warning(f"流式输出回调失败: {e}")

            logger.info(f"Agent {self.name} 流式调用完成，共 {chunk_count} 个 chunk，总长度 {len(full_content)} 字符")

        except Exception as e:
            logger.error(f"流式调用 LLM 失败: {e}")
            # 如果流式失败，回退到普通调用
            full_content = await self._call_llm(messages, temperature, max_tokens, category)
            return full_content

        # 尝试从最后一个 chunk 获取 token 使用量
        input_tokens = 0
        output_tokens = 0

        if last_chunk and hasattr(last_chunk, 'usage_metadata') and last_chunk.usage_metadata:
            input_tokens = last_chunk.usage_metadata.get('input_tokens', 0)
            output_tokens = last_chunk.usage_metadata.get('output_tokens', 0)

        # 如果无法获取实际值，使用估算
        if input_tokens == 0:
            input_tokens = sum(len(msg.content) // 4 for msg in messages)
        if output_tokens == 0:
            output_tokens = len(full_content) // 4

        self._record_token_usage(input_tokens, output_tokens, category)

        return full_content

    def _record_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        category: UsageCategory,
    ):
        """记录 token 使用量"""
        if not self.project_id:
            return

        try:
            # 从模型中提取 provider 和 model 信息
            provider = "anthropic"
            model = "claude"

            # 尝试从模型配置中获取更多信息
            if hasattr(self.model, 'model'):
                model = self.model.model
            if hasattr(self.model, 'model_name'):
                model = self.model.model_name

            # 获取 provider 信息
            model_str = str(self.model.__class__)
            if "Anthropic" in model_str:
                provider = "anthropic"
            elif "OpenAI" in model_str or "ChatOpenAI" in model_str:
                provider = "openai"

            # 异步记录 token 使用
            asyncio.create_task(
                token_tracker.record_usage(
                    project_id=self.project_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    provider=provider,
                    model=model,
                    category=category,
                    agent_name=self.name,
                )
            )
        except Exception as e:
            logger.warning(f"记录 token 使用失败: {e}")

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        import re

        json_pattern = r"```json\s*(.*?)\s*```"
        match = re.search(json_pattern, text, re.DOTALL)
        json_str = match.group(1) if match else text.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败：{e}, 原始文本：{text}")
            raise ValueError(f"Agent {self.name} 返回了无效的 JSON 格式")

    def add_to_history(self, role: str, content: str):
        if role == "human":
            self.message_history.append(HumanMessage(content=content))
        elif role == "ai":
            self.message_history.append(AIMessage(content=content))
        elif role == "system":
            self.message_history.append(SystemMessage(content=content))

    def clear_history(self):
        self.message_history = []

    def get_history(self) -> List:
        return self.message_history.copy()

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()
