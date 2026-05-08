"""StructuredLLMRunner 单元测试。

覆盖 happy / parsing_error / repair-success / repair-fail / FAIL_FAST 路径。
"""

from __future__ import annotations

from typing import Any, List, Optional

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel

from app.models.agent_output_contract import (
    AgentOutputContract,
    OutputContractConsumer,
    OutputContractMode,
    OutputContractRetryPolicy,
    OutputContractScene,
)
from app.services.structured_llm import (
    StructuredLLMRunner,
    StructuredOutputError,
)


class _DemoSchema(BaseModel):
    answer: str = ""
    score: int = 0


class _FakeStructuredModel:
    """模拟 ``model.with_structured_output(schema, include_raw=True)`` 返回值。"""

    def __init__(self, results: List[dict]):
        self._results = list(results)
        self.calls: List[List[BaseMessage]] = []

    async def ainvoke(self, messages: List[BaseMessage]) -> dict:
        self.calls.append(messages)
        if not self._results:
            raise RuntimeError("FakeStructuredModel: results 已耗尽")
        return self._results.pop(0)


class _FakeChatModel:
    def __init__(self, structured: _FakeStructuredModel):
        self._structured = structured

    def with_structured_output(self, schema, include_raw: bool = True):
        assert include_raw is True
        return self._structured


def _contract(policy: OutputContractRetryPolicy) -> AgentOutputContract:
    return AgentOutputContract(
        contract_id="test.demo",
        surface_name="test_demo",
        scene=OutputContractScene.AGENT_CHAT,
        consumer=OutputContractConsumer.DTO_RESPONSE,
        mode=OutputContractMode.STRICT,
        schema_name="DemoSchema",
        schema_ref="tests.test_structured_llm._DemoSchema",
        retry_policy=policy,
    )


@pytest.mark.asyncio
async def test_happy_path_returns_parsed_object():
    parsed = _DemoSchema(answer="ok", score=42)
    structured = _FakeStructuredModel([
        {"raw": AIMessage(content='{"answer":"ok","score":42}'), "parsed": parsed, "parsing_error": None},
    ])
    model = _FakeChatModel(structured)

    runner = StructuredLLMRunner()
    obj, raw = await runner.run_structured(
        model, _DemoSchema, [HumanMessage(content="hi")],
        contract=_contract(OutputContractRetryPolicy.RETRY_THEN_REPAIR),
    )
    assert obj is parsed
    assert "ok" in (raw or "")


@pytest.mark.asyncio
async def test_fail_fast_raises_immediately():
    structured = _FakeStructuredModel([
        {"raw": AIMessage(content="boom"), "parsed": None, "parsing_error": ValueError("bad")},
    ])
    model = _FakeChatModel(structured)
    runner = StructuredLLMRunner()
    with pytest.raises(StructuredOutputError):
        await runner.run_structured(
            model, _DemoSchema, [HumanMessage(content="hi")],
            contract=_contract(OutputContractRetryPolicy.FAIL_FAST),
        )
    assert len(structured.calls) == 1


@pytest.mark.asyncio
async def test_retry_only_succeeds_on_second_attempt():
    parsed = _DemoSchema(answer="recovered", score=1)
    structured = _FakeStructuredModel([
        {"raw": AIMessage(content="boom"), "parsed": None, "parsing_error": ValueError("bad")},
        {"raw": AIMessage(content='{"answer":"recovered","score":1}'), "parsed": parsed, "parsing_error": None},
    ])
    model = _FakeChatModel(structured)
    runner = StructuredLLMRunner()
    obj, _ = await runner.run_structured(
        model, _DemoSchema, [HumanMessage(content="hi")],
        contract=_contract(OutputContractRetryPolicy.RETRY_ONLY),
    )
    assert obj is parsed
    assert len(structured.calls) == 2


@pytest.mark.asyncio
async def test_repair_then_succeeds():
    parsed = _DemoSchema(answer="fixed", score=2)
    structured = _FakeStructuredModel([
        {"raw": AIMessage(content="bad1"), "parsed": None, "parsing_error": ValueError("e1")},
        {"raw": AIMessage(content='{"answer":"fixed","score":2}'), "parsed": parsed, "parsing_error": None},
    ])
    model = _FakeChatModel(structured)
    runner = StructuredLLMRunner()
    obj, _ = await runner.run_structured(
        model, _DemoSchema, [HumanMessage(content="hi")],
        contract=_contract(OutputContractRetryPolicy.RETRY_THEN_REPAIR),
    )
    assert obj is parsed
    # 第一次原 messages，第二次 repair messages（多了一条 HumanMessage）
    assert len(structured.calls) == 2
    assert len(structured.calls[1]) == len(structured.calls[0]) + 1


@pytest.mark.asyncio
async def test_repair_exhausted_raises():
    structured = _FakeStructuredModel([
        {"raw": AIMessage(content="bad1"), "parsed": None, "parsing_error": ValueError("e1")},
        {"raw": AIMessage(content="bad2"), "parsed": None, "parsing_error": ValueError("e2")},
        {"raw": AIMessage(content="bad3"), "parsed": None, "parsing_error": ValueError("e3")},
    ])
    model = _FakeChatModel(structured)
    runner = StructuredLLMRunner()
    with pytest.raises(StructuredOutputError) as exc_info:
        await runner.run_structured(
            model, _DemoSchema, [HumanMessage(content="hi")],
            contract=_contract(OutputContractRetryPolicy.RETRY_THEN_REPAIR),
            max_repair=1,
        )
    err = exc_info.value
    assert err.contract_id == "test.demo"
    assert err.last_raw == "bad3"
