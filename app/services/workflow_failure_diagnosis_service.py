"""Rule-based workflow failure diagnosis for recovery remediation."""

from typing import Any, Dict, List, Optional

from app.models.workflow_definition import WorkflowDefinition, WorkflowNode
from app.models.workflow_execution import NodeExecutionState, WorkflowExecution


class WorkflowFailureDiagnosisService:
    """Classifies failed workflow nodes using deterministic, auditable rules."""

    def diagnose(
        self,
        execution: WorkflowExecution,
        workflow: WorkflowDefinition,
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        failed_node_id, failed_state = self._select_failed_node(execution, node_id)
        failed_node = next((node for node in workflow.nodes if node.id == failed_node_id), None)
        error = (failed_state.error if failed_state else None) or execution.error or ""
        category = self._classify(error)
        current_agent_type = failed_node.agent_type if failed_node else None

        summary = self._summary(category, error, current_agent_type)
        retry_without_fix = category in {"missing_agent", "node_config_invalid", "resource_not_ready", "output_contract_failed"}
        remediable = category in {"missing_agent", "node_config_invalid"} and bool(failed_node)
        suggested_actions = self._suggested_actions(category, failed_node)

        return {
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "failed_node_id": failed_node_id,
            "failed_node_label": failed_node.label if failed_node else failed_node_id,
            "category": category,
            "severity": "blocking" if retry_without_fix else "transient_or_unknown",
            "recoverable": True,
            "retry_without_fix_likely_to_fail": retry_without_fix,
            "remediable": remediable,
            "summary": summary,
            "evidence": [error] if error else [],
            "current_agent_type": current_agent_type,
            "current_scenario": (failed_node.config or {}).get("scenario") if failed_node else None,
            "suggested_actions": suggested_actions,
        }

    def _select_failed_node(
        self,
        execution: WorkflowExecution,
        node_id: Optional[str],
    ) -> tuple[str, Optional[NodeExecutionState]]:
        if node_id:
            return node_id, execution.node_states.get(node_id)
        for candidate_id, state in execution.node_states.items():
            if getattr(state, "status", None) and state.status.value == "failed":
                return candidate_id, state
        return execution.current_node or "", None

    def _classify(self, error: str) -> str:
        lowered = (error or "").lower()
        if "无法获取 agent" in lowered or "unknown agent" in lowered or "未知的 agent" in lowered:
            return "missing_agent"
        if "readiness" in lowered or "资源" in lowered or "未就绪" in lowered:
            return "resource_not_ready"
        if "contract" in lowered or "required" in lowered or "缺少" in lowered:
            return "output_contract_failed"
        if "timeout" in lowered or "timed out" in lowered or "超时" in lowered:
            return "timeout"
        if "api" in lowered or "rate limit" in lowered or "provider" in lowered or "llm" in lowered:
            return "llm_provider_error"
        if "config" in lowered or "配置" in lowered or "scenario" in lowered:
            return "node_config_invalid"
        if error:
            return "runtime_exception"
        return "unknown"

    def _summary(self, category: str, error: str, agent_type: Optional[str]) -> str:
        if category == "missing_agent":
            return f"节点请求的 Agent 类型不可用：{agent_type or '未知'}"
        if category == "node_config_invalid":
            return "节点配置可能不完整或不合法，需要修正后再恢复。"
        if category == "resource_not_ready":
            return "执行依赖的章节/资源未就绪，需要补齐资源后再恢复。"
        if category == "output_contract_failed":
            return "节点输出不满足下游契约，直接重试可能再次失败。"
        if category == "timeout":
            return "节点执行超时，可能是临时服务问题或任务过重。"
        if category == "llm_provider_error":
            return "LLM Provider/API 调用失败，可能需要检查模型配置或服务状态。"
        if error:
            return "节点运行时失败，建议查看 Trace 和错误证据。"
        return "未找到明确失败证据。"

    def _suggested_actions(self, category: str, node: Optional[WorkflowNode]) -> List[Dict[str, Any]]:
        if category == "missing_agent":
            return [
                {
                    "type": "edit_agent_type",
                    "label": "修改失败节点的 Agent 类型",
                    "fields": ["agent_type"],
                },
                {
                    "type": "edit_scenario",
                    "label": "调整 Agent 场景",
                    "fields": ["config.scenario"],
                },
            ]
        if category == "node_config_invalid":
            return [
                {
                    "type": "edit_scenario",
                    "label": "修正节点场景配置",
                    "fields": ["config.scenario"],
                }
            ]
        return []


workflow_failure_diagnosis_service = WorkflowFailureDiagnosisService()
