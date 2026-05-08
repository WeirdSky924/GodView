"""Agent output contract 注册表与 schema 绑定一致性测试。"""

from __future__ import annotations

from pydantic import BaseModel

from app.models.agent_output_contract import (
    DEFAULT_AGENT_OUTPUT_CONTRACT_REGISTRY,
    OutputContractMode,
)


def test_default_registry_strict_and_hybrid_have_resolvable_schema():
    """所有 strict / hybrid 契约若声明了 schema_ref，必须能成功解析为 Pydantic 类。"""
    for contract in DEFAULT_AGENT_OUTPUT_CONTRACT_REGISTRY.contracts:
        if contract.mode not in {
            OutputContractMode.STRICT,
            OutputContractMode.HYBRID,
        }:
            continue
        if not contract.schema_ref:
            # 允许部分契约暂未绑定 schema，但若绑定了必须能解析
            continue
        cls = contract.resolve_schema()
        assert cls is not None, (
            f"contract {contract.contract_id} 的 schema_ref={contract.schema_ref} 无法解析"
        )
        assert issubclass(cls, BaseModel)


def test_registry_contract_ids_unique():
    seen = set()
    for contract in DEFAULT_AGENT_OUTPUT_CONTRACT_REGISTRY.contracts:
        assert contract.contract_id not in seen, (
            f"重复的 contract_id: {contract.contract_id}"
        )
        seen.add(contract.contract_id)
