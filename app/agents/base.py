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
    ) -> str:
        if not self.model:
            raise ValueError(f"Agent {self.name} 未配置模型")

        if self.system_prompt:
            messages = [SystemMessage(content=self.system_prompt)] + messages

        response = await self.model.ainvoke(messages)
        return response.content

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
