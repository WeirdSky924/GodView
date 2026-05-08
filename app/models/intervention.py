"""
干预日志模型
v8 Agent协作可视化工作台
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class InterventionType(str, Enum):
    """干预类型"""

    GUIDANCE = "guidance"       # 指导性干预
    CORRECTION = "correction"   # 纠正性干预
    DIRECTION = "direction"     # 方向性干预
    OVERRIDE = "override"       # 覆盖性干预


class InterventionLog(BaseModel):
    """干预日志"""

    id: str = Field(default_factory=lambda: f"int_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="所属项目ID")
    workflow_execution_id: str = Field(..., description="工作流执行ID")
    node_id: Optional[str] = Field(None, description="关联的节点ID")
    agent_type: str = Field(..., description="干预的Agent类型")
    agent_name: str = Field(..., description="Agent名称")
    intervention_type: InterventionType = Field(default=InterventionType.GUIDANCE, description="干预类型")
    user_message: str = Field(..., description="用户干预内容")
    agent_response: Optional[str] = Field(None, description="Agent响应")
    context_snapshot: Dict[str, Any] = Field(default_factory=dict, description="干预时的上下文快照")
    timestamp: datetime = Field(default_factory=datetime.now, description="干预时间")
    response_time_ms: Optional[int] = Field(None, description="响应耗时（毫秒）")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "int_abc123",
                "project_id": "proj_001",
                "workflow_execution_id": "exec_xyz789",
                "node_id": "node_plotter",
                "agent_type": "MasterPlotterAgent",
                "agent_name": "总编剧",
                "intervention_type": "guidance",
                "user_message": "请让主角在这一章遇到一个重要的转折点",
                "agent_response": "好的，我会在这一章安排主角发现一本神秘书籍...",
                "context_snapshot": {"chapter": 1, "current_plot": "..."},
                "timestamp": "2026-04-10T10:35:00Z",
                "response_time_ms": 2500
            }
        }
    )


class InterventionCreate(BaseModel):
    """创建干预请求"""

    workflow_execution_id: str = Field(..., description="工作流执行ID")
    project_id: str = Field(..., description="项目ID")
    node_id: Optional[str] = Field(None, description="节点ID")
    agent_type: str = Field(..., description="Agent类型")
    message: str = Field(..., description="干预消息", min_length=1)
    intervention_type: InterventionType = Field(default=InterventionType.GUIDANCE, description="干预类型")


class InterventionQuery(BaseModel):
    """干预日志查询条件"""

    project_id: Optional[str] = None
    workflow_execution_id: Optional[str] = None
    agent_type: Optional[str] = None
    intervention_type: Optional[InterventionType] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    keyword: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class InterventionExportFormat(str, Enum):
    """导出格式"""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


class InterventionExportRequest(BaseModel):
    """导出请求"""

    project_id: str
    workflow_execution_id: Optional[str] = None
    format: InterventionExportFormat = Field(default=InterventionExportFormat.JSON)
    include_context: bool = Field(default=False, description="是否包含上下文快照")


class InterventionSummary(BaseModel):
    """干预摘要（用于统计）"""

    total_count: int = 0
    by_agent_type: Dict[str, int] = Field(default_factory=dict)
    by_intervention_type: Dict[str, int] = Field(default_factory=dict)
    avg_response_time_ms: Optional[float] = None
    recent_interventions: List[InterventionLog] = Field(default_factory=list)
