"""Structured LLM 运行器。

把"生成 → schema 校验 → 重试 / 修复 → 失败"这一链路集中在一个地方，
让 strict / hybrid Agent 在生成侧就拿到已校验的 Pydantic 对象，而不是
继续依赖 prompt 自觉 + ``_parse_json_response`` 的正则抽取。

核心入口 :class:`StructuredLLMRunner.run_structured`：

1. 调 ``model.with_structured_output(schema, include_raw=True).ainvoke(messages)``
2. 拿到 ``{"raw": AIMessage, "parsed": BaseModel | None, "parsing_error": ...}``
3. ``parsed`` 非空且无 ``parsing_error`` → 返回 ``(parsed, raw_text)``
4. 否则按 ``contract.retry_policy`` 处理：

   - ``NONE`` / ``FAIL_FAST`` → 立刻 raise :class:`StructuredOutputError`
   - ``RETRY_ONLY`` → 原 messages 重试一次
   - ``RETRY_THEN_REPAIR`` → 把 raw 输出 + 校验错误塞进 follow-up message 让模型修复

5. 仍失败 → raise :class:`StructuredOutputError`

注意：本 runner **不**记录 token 用量。token 记录由 ``BaseAgent._call_structured``
或 ``SettingAgentService._call_structured`` 在外层接管，与现有 ``_call_llm``
保持一致。
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple, Type

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel

from app.models.agent_output_contract import (
    AgentOutputContract,
    OutputContractRetryPolicy,
)

logger = logging.getLogger(__name__)


class StructuredOutputError(RuntimeError):
    """structured output 生成或校验失败。"""

    def __init__(
        self,
        message: str,
        *,
        contract_id: Optional[str] = None,
        schema_name: Optional[str] = None,
        last_raw: Optional[str] = None,
        validation_errors: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.contract_id = contract_id
        self.schema_name = schema_name
        self.last_raw = last_raw
        self.validation_errors = validation_errors


def _extract_text(message: Any) -> str:
    """从 LangChain AIMessage 中提取纯文本（兼容 Anthropic content blocks）。"""
    if message is None:
        return ""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return str(content)


class StructuredLLMRunner:
    """生成 → 校验 → 修复 → 失败 的统一执行器。"""

    DEFAULT_MAX_REPAIR = 1

    async def run_structured(
        self,
        model: BaseLanguageModel,
        schema: Type[BaseModel],
        messages: List[BaseMessage],
        *,
        contract: Optional[AgentOutputContract] = None,
        max_repair: Optional[int] = None,
    ) -> Tuple[BaseModel, Optional[str]]:
        """生成并校验 structured output。

        Args:
            model: LangChain ChatModel（必须支持 ``with_structured_output``）
            schema: 期望输出对应的 Pydantic 类
            messages: 调用消息（不含 system prompt 注入；调用方需自行处理）
            contract: 关联输出契约，用于决定 retry 策略
            max_repair: 修复轮数上限（默认 1）

        Returns:
            ``(validated_object, raw_text_or_none)``

        Raises:
            StructuredOutputError: 校验最终失败
        """
        retry_policy = (
            contract.retry_policy if contract else OutputContractRetryPolicy.RETRY_THEN_REPAIR
        )
        repair_budget = self.DEFAULT_MAX_REPAIR if max_repair is None else max(0, int(max_repair))

        try:
            structured_model = model.with_structured_output(schema, include_raw=True)
        except Exception as exc:  # pragma: no cover - 模型未配置时
            raise StructuredOutputError(
                f"模型不支持 with_structured_output: {exc}",
                contract_id=getattr(contract, "contract_id", None),
                schema_name=getattr(contract, "schema_name", None),
            ) from exc

        last_raw_text: Optional[str] = None
        last_error: Optional[BaseException] = None
        current_messages: List[BaseMessage] = list(messages)

        # 第一次正常调用
        parsed, raw_text, parse_error = await self._invoke_once(structured_model, current_messages)
        last_raw_text = raw_text
        last_error = parse_error
        if parsed is not None and parse_error is None:
            return parsed, raw_text

        # FAIL_FAST / NONE：直接失败
        if retry_policy in {OutputContractRetryPolicy.NONE, OutputContractRetryPolicy.FAIL_FAST}:
            raise StructuredOutputError(
                f"structured output 校验失败（policy={retry_policy.value}）：{last_error}",
                contract_id=getattr(contract, "contract_id", None),
                schema_name=getattr(contract, "schema_name", None),
                last_raw=last_raw_text,
                validation_errors=last_error,
            )

        # RETRY_ONLY：原 messages 重试一次
        if retry_policy == OutputContractRetryPolicy.RETRY_ONLY:
            parsed, raw_text, parse_error = await self._invoke_once(structured_model, current_messages)
            last_raw_text = raw_text
            last_error = parse_error
            if parsed is not None and parse_error is None:
                return parsed, raw_text
            raise StructuredOutputError(
                f"structured output 重试后仍失败：{last_error}",
                contract_id=getattr(contract, "contract_id", None),
                schema_name=getattr(contract, "schema_name", None),
                last_raw=last_raw_text,
                validation_errors=last_error,
            )

        # RETRY_THEN_REPAIR：把上次失败 raw + 错误塞回去让模型自修
        for attempt in range(repair_budget + 1):
            repair_messages = current_messages + [
                HumanMessage(
                    content=(
                        "上一次输出未通过结构化校验。\n"
                        f"上次输出原文：\n{last_raw_text or '(空)'}\n\n"
                        f"校验错误：{last_error}\n\n"
                        "请严格按指定 schema 重新输出，不要包含解释或 markdown 包裹。"
                    )
                )
            ]
            parsed, raw_text, parse_error = await self._invoke_once(structured_model, repair_messages)
            last_raw_text = raw_text
            last_error = parse_error
            if parsed is not None and parse_error is None:
                return parsed, raw_text
            logger.info(
                "structured output repair attempt %s failed: %s", attempt + 1, parse_error
            )

        raise StructuredOutputError(
            f"structured output 多轮修复后仍失败：{last_error}",
            contract_id=getattr(contract, "contract_id", None),
            schema_name=getattr(contract, "schema_name", None),
            last_raw=last_raw_text,
            validation_errors=last_error,
        )

    async def _invoke_once(
        self,
        structured_model: Any,
        messages: List[BaseMessage],
    ) -> Tuple[Optional[BaseModel], Optional[str], Optional[BaseException]]:
        """单次调用 structured model，返回 ``(parsed, raw_text, parse_error)``。"""
        try:
            result = await structured_model.ainvoke(messages)
        except Exception as exc:  # 网络 / API / 其他
            return None, None, exc

        # ``include_raw=True`` 返回 dict
        if isinstance(result, dict):
            parsed = result.get("parsed")
            raw_msg = result.get("raw")
            parse_error = result.get("parsing_error")
            raw_text = _extract_text(raw_msg)
            if parsed is not None and parse_error is None:
                return parsed, raw_text, None
            return None, raw_text, parse_error or ValueError("未拿到 parsed 对象")

        # 某些模型未必返回 dict；直接尝试当作 BaseModel
        if isinstance(result, BaseModel):
            return result, None, None

        return None, str(result), ValueError(f"意料外的 structured output 返回：{type(result).__name__}")


# 模块级单例，供调用方复用
_default_runner: Optional[StructuredLLMRunner] = None


def get_structured_llm_runner() -> StructuredLLMRunner:
    """获取默认 :class:`StructuredLLMRunner` 单例。"""
    global _default_runner
    if _default_runner is None:
        _default_runner = StructuredLLMRunner()
    return _default_runner


__all__ = [
    "StructuredLLMRunner",
    "StructuredOutputError",
    "get_structured_llm_runner",
]
