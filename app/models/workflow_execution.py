"""
工作流执行模型
v8 Agent协作可视化工作台
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid

from app.models.agent_output_contract import OutputContractMode
from app.models.workflow_definition import NodeStatus


class WorkflowStatus(str, Enum):
    """工作流执行状态"""

    PENDING = "pending"       # 等待执行
    RUNNING = "running"       # 执行中
    PAUSED = "paused"         # 已暂停（等待干预）
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 执行失败
    CANCELLED = "cancelled"   # 已取消


class NodeExecutionState(BaseModel):
    """节点执行状态"""

    node_id: str = Field(..., description="节点ID")
    status: NodeStatus = Field(default=NodeStatus.PENDING, description="执行状态")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    output_data: Dict[str, Any] = Field(default_factory=dict, description="输出数据")
    output_contract_id: Optional[str] = Field(None, description="输出契约 ID")
    output_mode: Optional[OutputContractMode] = Field(None, description="输出模式")
    output_schema_name: Optional[str] = Field(None, description="输出 schema 名称")
    output_schema_version: Optional[str] = Field(None, description="输出 schema 版本")
    error: Optional[str] = Field(None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")
    duration_ms: Optional[int] = Field(None, description="执行耗时（毫秒）")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "node_id": "node_abc123",
                "status": "completed",
                "started_at": "2026-04-10T10:30:00Z",
                "completed_at": "2026-04-10T10:30:05Z",
                "input_data": {"chapter": 1},
                "output_data": {"outline": "章节大纲内容..."},
                "error": None,
                "retry_count": 0,
                "duration_ms": 5000
            }
        }
    )


class WorkflowExecution(BaseModel):
    """工作流执行记录"""

    id: str = Field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:8]}")
    workflow_id: str = Field(..., description="工作流定义ID")
    project_id: str = Field(..., description="所属项目ID")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING, description="执行状态")
    current_node: Optional[str] = Field(None, description="当前执行节点ID")
    node_states: Dict[str, NodeExecutionState] = Field(default_factory=dict, description="节点状态映射")
    context: Dict[str, Any] = Field(default_factory=dict, description="工作流上下文")
    intervention_ids: List[str] = Field(default_factory=list, description="干预日志ID列表")
    started_at: datetime = Field(default_factory=datetime.now, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    total_duration_ms: Optional[int] = Field(None, description="总耗时（毫秒）")
    error: Optional[str] = Field(None, description="错误信息")
    operation_id: Optional[str] = Field(None, description="关联操作请求ID")
    request_id: Optional[str] = Field(None, description="幂等请求ID")
    request_hash: Optional[str] = Field(None, description="幂等请求内容哈希")
    director_session_id: Optional[str] = Field(None, description="Director 界面会话ID")
    trace_id: Optional[str] = Field(None, description="关联 Trace ID")
    lease_token: Optional[str] = Field(None, description="运行租约令牌")
    lease_expires_at: Optional[datetime] = Field(None, description="运行租约过期时间")
    last_heartbeat_at: Optional[datetime] = Field(None, description="最后心跳时间")
    cancel_requested: bool = Field(False, description="是否已请求取消")
    resume_cursor: Dict[str, Any] = Field(default_factory=dict, description="恢复游标")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "exec_xyz789",
                "workflow_id": "workflow_abc123",
                "project_id": "proj_001",
                "status": "running",
                "current_node": "node_plotter",
                "node_states": {
                    "node_start": {"status": "completed"},
                    "node_plotter": {"status": "running"}
                },
                "context": {"chapter": 1, "style": "wuxia"},
                "intervention_ids": [],
                "started_at": "2026-04-10T10:30:00Z"
            }
        }
    )


class WorkflowExecutionCreate(BaseModel):
    """创建执行请求"""

    workflow_id: str = Field(..., description="工作流定义ID")
    project_id: str = Field(..., description="项目ID")
    initial_context: Dict[str, Any] = Field(default_factory=dict, description="初始上下文")


class WorkflowExecutionSummary(BaseModel):
    """执行摘要（用于列表显示）"""

    id: str
    workflow_id: str
    workflow_name: Optional[str] = None
    project_id: str
    status: WorkflowStatus
    current_node: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    total_duration_ms: Optional[int]
    node_count: int = 0
    completed_node_count: int = 0
    intervention_count: int = 0


class NodeExecutionUpdate(BaseModel):
    """节点执行更新"""

    node_id: str
    status: Optional[NodeStatus] = None
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowContextUpdate(BaseModel):
    """工作流上下文更新"""

    context: Dict[str, Any] = Field(..., description="要更新的上下文")
    merge: bool = Field(default=True, description="是否合并（False则覆盖）")
