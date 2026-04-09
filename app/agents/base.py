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

        # TODO: 调用 AgentConfigService 获取最终 prompt
        # 目前返回空字符串，等待服务注入
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

        if self.system_prompt:
            messages = [SystemMessage(content=self.system_prompt)] + messages

        # 记录输入 token 数（估算）
        input_tokens = sum(len(msg.content) // 4 for msg in messages)

        response = await self.model.ainvoke(messages)
        content = response.content

        # 尝试获取实际 token 使用量
        output_tokens = len(content) // 4  # 估算输出 token
        self._record_token_usage(input_tokens, output_tokens, category)

        return content

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
