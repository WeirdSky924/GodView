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
