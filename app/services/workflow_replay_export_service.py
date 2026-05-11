"""
工作流执行复盘 Markdown 导出服务
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from app.models.workflow_definition import WorkflowDefinition, WorkflowNode
from app.models.workflow_execution import WorkflowExecution, NodeExecutionState


class WorkflowReplayExportService:
    """将 workflow execution 节点输入输出导出为 Markdown。"""

    def export_markdown(
        self,
        execution: WorkflowExecution,
        workflow: WorkflowDefinition,
    ) -> str:
        lines: List[str] = [
            f"# Workflow 执行复盘 - {execution.id}",
            "",
            "## 执行概览",
            f"- **Execution ID**: `{execution.id}`",
            f"- **Workflow ID**: `{execution.workflow_id}`",
            f"- **Workflow Name**: {workflow.name}",
            f"- **Project ID**: `{execution.project_id}`",
            f"- **状态**: `{execution.status.value}`",
            f"- **当前节点**: `{execution.current_node or '-'}`",
            f"- **开始时间**: {self._format_datetime(execution.started_at)}",
            f"- **结束时间**: {self._format_datetime(execution.completed_at)}",
            f"- **总耗时**: {self._format_duration(execution.total_duration_ms)}",
        ]

        if execution.error:
            lines.append(f"- **执行错误**: {execution.error}")

        audit_lines = self._render_audit_section(execution)
        if audit_lines:
            lines.extend(["", *audit_lines])

        quality_gate_lines = self._render_quality_gate_section(execution)
        if quality_gate_lines:
            lines.extend(["", *quality_gate_lines])

        saved_chapter_lines = self._render_saved_chapter_section(execution)
        if saved_chapter_lines:
            lines.extend(["", *saved_chapter_lines])

        lines.extend([
            "",
            "## 节点复盘",
            "",
        ])

        for index, node in enumerate(workflow.nodes, 1):
            node_state = execution.node_states.get(node.id)
            lines.extend(self._render_node_section(index, node, node_state))

        return "\n".join(lines).rstrip() + "\n"

    def save_markdown(
        self,
        execution: WorkflowExecution,
        workflow: WorkflowDefinition,
        root_dir: Optional[str] = None,
    ) -> str:
        content = self.export_markdown(execution, workflow)
        file_path = self.build_file_path(execution, root_dir)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return str(file_path)

    def get_export_filename(self, execution: WorkflowExecution) -> str:
        return f"workflow_replay_{execution.id}.md"

    def build_file_path(
        self,
        execution: WorkflowExecution,
        root_dir: Optional[str] = None,
    ) -> Path:
        base_dir = Path(root_dir) if root_dir else self._get_repo_root()
        return (
            base_dir
            / "data"
            / "workflow_replay_logs"
            / execution.project_id
            / execution.workflow_id
            / f"{execution.id}.md"
        )

    def _get_repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _render_audit_section(self, execution: WorkflowExecution) -> List[str]:
        context = execution.context if isinstance(execution.context, dict) else {}
        remediation_history = context.get("remediation_history")
        recovery_history = context.get("recovery_history")
        if not isinstance(remediation_history, list):
            remediation_history = []
        if not isinstance(recovery_history, list):
            recovery_history = []
        if not remediation_history and not recovery_history:
            return []

        lines: List[str] = ["## 修复与恢复审计", ""]
        if remediation_history:
            lines.extend(["### 修复记录", ""])
            for entry in remediation_history:
                if not isinstance(entry, dict):
                    continue
                lines.extend([
                    f"#### 修复尝试 {entry.get('attempt', '-')}",
                    f"- **节点 ID**: `{entry.get('node_id') or '-'}`",
                    f"- **诊断分类**: `{entry.get('diagnosis_category') or entry.get('category') or '-'}`",
                    f"- **原因**: {entry.get('reason') or '-'}",
                    f"- **开始时间**: {entry.get('started_at') or '-'}",
                    f"- **应用时间**: {entry.get('applied_at') or entry.get('started_at') or '-'}",
                    f"- **原始错误**: {entry.get('previous_error') or '-'}",
                    "- **安全差异**:",
                    "```json",
                    self._dump_json(entry.get("diff")),
                    "```",
                    "",
                ])

        if recovery_history:
            lines.extend(["### 恢复记录", ""])
            for entry in recovery_history:
                if not isinstance(entry, dict):
                    continue
                reset_nodes = entry.get("reset_node_ids")
                if isinstance(reset_nodes, list):
                    reset_nodes_display = ", ".join(str(node_id) for node_id in reset_nodes) or "-"
                else:
                    reset_nodes_display = str(reset_nodes) if reset_nodes else "-"
                lines.extend([
                    f"#### 恢复尝试 {entry.get('attempt', '-')}",
                    f"- **模式**: `{entry.get('mode') or '-'}`",
                    f"- **目标节点**: `{entry.get('target_node_id') or '-'}`",
                    f"- **重置节点**: {reset_nodes_display}",
                    f"- **原因**: {entry.get('reason') or '-'}",
                    f"- **开始时间**: {entry.get('started_at') or '-'}",
                    f"- **原始错误**: {entry.get('previous_error') or '-'}",
                    f"- **Trace ID**: `{entry.get('trace_id') or '-'}`",
                    f"- **开始状态**: `{entry.get('status_at_start') or '-'}`",
                    "",
                ])
        return lines

    def _render_quality_gate_section(self, execution: WorkflowExecution) -> List[str]:
        context = execution.context if isinstance(execution.context, dict) else {}
        quality_gate = context.get("quality_gate") if isinstance(context.get("quality_gate"), dict) else {}
        gate_history = context.get("quality_gate_history") if isinstance(context.get("quality_gate_history"), list) else []
        revision_history = context.get("revision_history") if isinstance(context.get("revision_history"), list) else []
        if not quality_gate and not gate_history and not revision_history:
            return []

        lines: List[str] = [
            "## 质量门与修订审计",
            "",
            f"- **最终状态**: `{quality_gate.get('status') or context.get('quality_gate_status') or '-'}`",
            f"- **是否通过**: `{quality_gate.get('passed') if quality_gate.get('passed') is not None else '-'}`",
            f"- **最终分数**: {quality_gate.get('score') if quality_gate.get('score') is not None else '-'}",
            f"- **质量门尝试次数**: {len(gate_history)}",
            f"- **修订请求次数**: {len(revision_history)}",
            f"- **最终草稿尝试**: {context.get('chapter_draft_attempt') or quality_gate.get('draft_attempt') or '-'}",
            f"- **草稿校验和**: `{context.get('chapter_draft_checksum') or quality_gate.get('content_checksum') or '-'}`",
            f"- **强制通过**: `{quality_gate.get('forced_pass') if quality_gate.get('forced_pass') is not None else False}`",
            "",
        ]

        if gate_history:
            lines.extend(["### 质量门记录", ""])
            for index, entry in enumerate(gate_history, 1):
                if not isinstance(entry, dict):
                    continue
                issues = entry.get("issues") if isinstance(entry.get("issues"), list) else []
                suggestions = entry.get("suggestions") if isinstance(entry.get("suggestions"), list) else []
                lines.extend([
                    f"#### 尝试 {index}",
                    f"- **Evaluator 节点**: `{entry.get('evaluator_node_id') or '-'}` / {entry.get('evaluator_node_label') or '-'}",
                    f"- **通过**: `{entry.get('passed')}`",
                    f"- **分数**: {entry.get('score') if entry.get('score') is not None else '-'}",
                    f"- **草稿尝试**: {entry.get('draft_attempt') or '-'}",
                    f"- **正文长度**: {entry.get('content_chars') or '-'} chars",
                    f"- **内容校验和**: `{entry.get('content_checksum') or '-'}`",
                    f"- **问题数 / 建议数**: {entry.get('issues_count') or 0} / {entry.get('suggestions_count') or 0}",
                    f"- **问题摘要**: {'；'.join(str(item) for item in issues[:5]) or '-'}",
                    f"- **建议摘要**: {'；'.join(str(item) for item in suggestions[:5]) or '-'}",
                    f"- **评估时间**: {entry.get('evaluated_at') or '-'}",
                    "",
                ])

        if revision_history:
            lines.extend(["### 修订请求记录", ""])
            for index, entry in enumerate(revision_history, 1):
                if not isinstance(entry, dict):
                    continue
                summary = entry.get("quality_summary") if isinstance(entry.get("quality_summary"), dict) else {}
                lines.extend([
                    f"#### 修订 {index}",
                    f"- **Condition 节点**: `{entry.get('condition_node_id') or '-'}` / {entry.get('condition_node_label') or '-'}",
                    f"- **草稿尝试**: {entry.get('draft_attempt') or '-'}",
                    f"- **内容校验和**: `{entry.get('content_checksum') or '-'}`",
                    f"- **质量状态**: `{entry.get('quality_gate_status') or '-'}`",
                    f"- **重试计数**: {entry.get('retry_count') if entry.get('retry_count') is not None else '-'}",
                    f"- **问题数 / 建议数**: {summary.get('issues_count') or 0} / {summary.get('suggestions_count') or 0}",
                    f"- **请求时间**: {entry.get('requested_at') or '-'}",
                    "",
                ])
        return lines

    def _render_saved_chapter_section(self, execution: WorkflowExecution) -> List[str]:
        context = execution.context if isinstance(execution.context, dict) else {}
        payload = context.get("chapter_saved_payload")
        provenance = context.get("chapter_writer_provenance")
        if not isinstance(payload, dict) and not isinstance(provenance, dict):
            return []
        payload = payload if isinstance(payload, dict) else {}
        provenance = provenance if isinstance(provenance, dict) else {}

        lines: List[str] = [
            "## 保存章节",
            "",
            f"- **章节 ID**: `{payload.get('chapter_id') or context.get('chapter_id') or '-'}`",
            f"- **标题**: {payload.get('chapter_title') or payload.get('title') or '-'}",
            f"- **章节序号**: {payload.get('chapter_number') or payload.get('chapter_num') or context.get('chapter_num') or '-' }",
            f"- **大纲 ID**: `{payload.get('chapter_outline_id') or context.get('chapter_outline_id') or '-'}`",
            f"- **状态**: `{payload.get('status') or '-'}`",
            f"- **保存时间**: {payload.get('saved_at') or context.get('chapter_saved_at') or '-'}",
            f"- **存储路径**: `{payload.get('content_path') or context.get('chapter_content_path') or '-'}`",
            f"- **内容大小**: {payload.get('content_size_bytes') or context.get('chapter_content_size_bytes') or '-'} bytes",
            f"- **内容校验和**: `{payload.get('content_checksum') or context.get('chapter_content_checksum') or '-'}`",
            f"- **来源节点**: `{provenance.get('source_node_id') or payload.get('source_node_id') or '-'}` / {provenance.get('source_node_label') or payload.get('source_node_label') or '-'}",
            f"- **来源 Agent**: `{provenance.get('source_agent_type') or payload.get('source_agent_type') or '-'}` → `{provenance.get('resolved_agent_type') or payload.get('resolved_agent_type') or '-'}`",
            f"- **场景**: `{provenance.get('resolved_scenario') or payload.get('resolved_scenario') or '-'}`",
            f"- **Trace ID**: `{provenance.get('source_trace_id') or payload.get('source_trace_id') or execution.trace_id or '-'}`",
            f"- **输出契约**: `{provenance.get('source_output_contract_id') or payload.get('source_output_contract_id') or '-'}`",
            f"- **输出 Schema**: `{provenance.get('source_output_schema_name') or payload.get('source_output_schema_name') or '-'}` / `{provenance.get('source_output_schema_version') or payload.get('source_output_schema_version') or '-'}`",
            f"- **正文长度**: {provenance.get('writer_output_content_chars') or payload.get('writer_output_content_chars') or payload.get('content_chars') or '-'} chars",
            f"- **字数**: {provenance.get('writer_output_word_count') or payload.get('writer_output_word_count') or payload.get('word_count') or '-'}",
            f"- **质量门状态**: `{payload.get('quality_gate_status') or '-'}`",
            f"- **质量门通过**: `{payload.get('quality_gate_passed') if payload.get('quality_gate_passed') is not None else '-'}`",
            f"- **质量分数**: {payload.get('quality_gate_score') if payload.get('quality_gate_score') is not None else '-'}",
            f"- **质量门尝试 / 修订次数**: {payload.get('quality_gate_attempts') if payload.get('quality_gate_attempts') is not None else '-'} / {payload.get('revision_attempts') if payload.get('revision_attempts') is not None else '-'}",
        ]

        prompt_trace = provenance.get("writer_prompt_trace") or payload.get("writer_prompt_trace")
        if isinstance(prompt_trace, dict) and prompt_trace:
            lines.extend([
                "- **Prompt/配置 Trace**:",
                "```json",
                self._dump_json(prompt_trace),
                "```",
            ])
        lines.append("")
        return lines

    def _render_node_section(
        self,
        index: int,
        node: WorkflowNode,
        node_state: Optional[NodeExecutionState],
    ) -> List[str]:
        if node_state is None:
            return [
                f"### {index}. {node.label}",
                f"- **节点 ID**: `{node.id}`",
                f"- **节点类型**: `{node.node_type.value}`",
                f"- **Agent 类型**: `{node.agent_type or '-'}`",
                "- **状态**: `missing`",
                "",
            ]

        lines = [
            f"### {index}. {node.label}",
            f"- **节点 ID**: `{node.id}`",
            f"- **节点类型**: `{node.node_type.value}`",
            f"- **Agent 类型**: `{node.agent_type or '-'}`",
            f"- **状态**: `{node_state.status.value}`",
            f"- **开始时间**: {self._format_datetime(node_state.started_at)}",
            f"- **结束时间**: {self._format_datetime(node_state.completed_at)}",
            f"- **耗时**: {self._format_duration(node_state.duration_ms)}",
            f"- **重试次数**: {node_state.retry_count}",
        ]

        if node_state.error:
            lines.append(f"- **错误**: {node_state.error}")

        lines.extend([
            "",
            "#### 输入快照",
            "```json",
            self._dump_json(node_state.input_data),
            "```",
            "",
            "#### 输出快照",
            "```json",
            self._dump_json(node_state.output_data),
            "```",
            "",
        ])
        return lines

    def _dump_json(self, data: Any) -> str:
        return json.dumps(data or {}, ensure_ascii=False, indent=2, default=str)

    def _format_datetime(self, value: Optional[datetime]) -> str:
        if not value:
            return "-"
        return value.strftime("%Y-%m-%d %H:%M:%S")

    def _format_duration(self, value: Optional[int]) -> str:
        if value is None:
            return "-"
        return f"{value}ms"


_workflow_replay_export_service: Optional[WorkflowReplayExportService] = None


def get_workflow_replay_export_service() -> WorkflowReplayExportService:
    global _workflow_replay_export_service
    if _workflow_replay_export_service is None:
        _workflow_replay_export_service = WorkflowReplayExportService()
    return _workflow_replay_export_service
