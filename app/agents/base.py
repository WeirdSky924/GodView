"""
Agent 基类
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

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

    def __init__(
        self,
        name: str,
        model: Optional[BaseLanguageModel] = None,
        system_prompt: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt or ""
        self.config = config or {}
        self.message_history: List = []
        self._lock = asyncio.Lock()

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行 Agent 任务

        Args:
            input_data: 输入数据

        Returns:
            AgentResponse: 响应结果
        """
        pass

    async def _call_llm(
        self,
        messages: List,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        调用 LLM

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            str: LLM 响应文本
        """
        if not self.model:
            raise ValueError(f"Agent {self.name} 未配置模型")

        # 添加系统提示
        if self.system_prompt:
            messages = [SystemMessage(content=self.system_prompt)] + messages

        # 调用模型
        response = await self.model.ainvoke(messages)
        return response.content

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        解析 JSON 响应

        Args:
            text: 响应文本

        Returns:
            Dict: 解析后的 JSON 数据
        """
        # 尝试提取 JSON 代码块
        import re

        json_pattern = r"```json\s*(.*?)\s*```"
        match = re.search(json_pattern, text, re.DOTALL)

        if match:
            json_str = match.group(1)
        else:
            # 尝试直接解析
            json_str = text.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败：{e}, 原始文本：{text}")
            raise ValueError(f"Agent {self.name} 返回了无效的 JSON 格式")

    def add_to_history(self, role: str, content: str):
        """
        添加消息到历史记录

        Args:
            role: 角色 (human/ai/system)
            content: 内容
        """
        if role == "human":
            self.message_history.append(HumanMessage(content=content))
        elif role == "ai":
            self.message_history.append(AIMessage(content=content))
        elif role == "system":
            self.message_history.append(SystemMessage(content=content))

    def clear_history(self):
        """清空消息历史"""
        self.message_history = []

    def get_history(self) -> List:
        """获取消息历史"""
        return self.message_history.copy()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        self._lock.release()
