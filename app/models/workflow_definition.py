"""
工作流定义模型
v8 Agent协作可视化工作台
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field
import uuid


class NodeType(str, Enum):
    """节点类型枚举"""

    AGENT = "agent"           # Agent节点（单个Agent）
    CONDITION = "condition"   # 条件分支节点
    GROUP_DISCUSSION = "group_discussion"  # 集体讨论节点（创作会议）
    SCENE_PERFORMANCE = "scene_performance"  # 场景演绎节点（多角色同台）
    PARALLEL = "parallel"     # 并行执行节点
    START = "start"           # 开始节点
    END = "end"               # 结束节点
    INPUT = "input"           # 用户输入节点


class NodeStatus(str, Enum):
    """节点执行状态"""

    PENDING = "pending"       # 等待执行
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 执行失败
    SKIPPED = "skipped"       # 已跳过


class DataInputSource(str, Enum):
    """数据输入来源"""
    DATABASE = "database"      # 从数据库加载
    CONTEXT = "context"        # 从全局上下文获取
    UPSTREAM = "upstream"      # 从上游节点获取
    VARIABLE = "variable"      # 从工作流变量获取
    USER_INPUT = "user_input"  # 用户运行时输入


class DataOutputTarget(str, Enum):
    """数据输出目标"""
    CONTEXT = "context"        # 输出到全局上下文
    DOWNSTREAM = "downstream"  # 输出给下游节点
    DATABASE = "database"      # 保存到数据库


class NodeInputConfig(BaseModel):
    """节点输入配置"""
    name: str = Field(..., description="输入数据名称（将作为 context 中的 key）")
    source: DataInputSource = Field(..., description="数据来源")
    data_type: Optional[str] = Field(None, description="数据类型（source=database 时需要，如 characters, world_info, hooks, chapters）")
    key: Optional[str] = Field(None, description="上下文/变量中的 key（source=context/variable 时需要）")
    upstream_node: Optional[str] = Field(None, description="上游节点 ID（source=upstream 时需要）")
    upstream_field: Optional[str] = Field(None, description="上游节点输出的字段名（source=upstream 时需要）")
    required: bool = Field(True, description="是否必需")
    default: Optional[Any] = Field(None, description="默认值（数据不存在时使用）")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "characters",
                "source": "database",
                "data_type": "characters",
                "required": True
            }
        }
    )


class NodeOutputConfig(BaseModel):
    """节点输出配置"""
    name: str = Field(..., description="输出数据名称")
    target: DataOutputTarget = Field(DataOutputTarget.CONTEXT, description="输出目标")
    key: Optional[str] = Field(None, description="输出到上下文的 key（默认使用 name）")
    contract_id: Optional[str] = Field(None, description="输出契约 ID（用于声明预期输出结构）")
    save_to_db: bool = Field(False, description="是否同时保存到数据库")
    db_table: Optional[str] = Field(None, description="数据库表名（save_to_db=True 时需要）")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "chapter_goals",
                "target": "context",
                "key": "chapter_goals"
            }
        }
    )


class WorkflowNode(BaseModel):
    """工作流节点"""

    id: str = Field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    node_type: NodeType = Field(..., description="节点类型")
    agent_type: Optional[str] = Field(None, description="Agent类型（仅AGENT节点需要）")
    label: str = Field(..., description="节点标签")
    description: Optional[str] = Field(None, description="节点描述")
    config: Dict[str, Any] = Field(default_factory=dict, description="节点配置参数")
    # 数据传递配置
    inputs: List[NodeInputConfig] = Field(default_factory=list, description="输入数据配置")
    outputs: List[NodeOutputConfig] = Field(default_factory=list, description="输出数据配置")
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0}, description="画布位置")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "node_abc123",
                    "node_type": "agent",
                    "agent_type": "master_plotter",
                    "label": "总编剧",
                    "description": "规划章节大纲",
                    "config": {"temperature": 0.7},
                    "inputs": [
                        {"name": "characters", "source": "database", "data_type": "characters"},
                        {"name": "world_info", "source": "database", "data_type": "world"},
                    ],
                    "outputs": [
                        {"name": "chapter_goals", "target": "context"},
                        {"name": "scene_directions", "target": "context"}
                    ],
                    "position": {"x": 100, "y": 200}
                },
                {
                    "id": "node_scene001",
                    "node_type": "scene_performance",
                    "label": "客栈对决",
                    "description": "多角色同台演绎客栈对决场景",
                    "config": {
                        "scene_mode": "interactive",
                        "required_characters": ["李明", "王芳"],
                        "need_background_characters": True,
                        "background_character_count": 3
                    },
                    "inputs": [
                        {"name": "scene_directions", "source": "context", "key": "scene_directions"},
                        {"name": "characters", "source": "database", "data_type": "characters"}
                    ],
                    "outputs": [
                        {"name": "performance_result", "target": "context"},
                        {"name": "dialogues", "target": "context"}
                    ],
                    "position": {"x": 300, "y": 200}
                }
            ]
        }
    )


class WorkflowEdge(BaseModel):
    """工作流边（节点连接）"""

    id: str = Field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    label: Optional[str] = Field(None, description="边标签")
    condition: Optional[Dict[str, Any]] = Field(None, description="条件表达式（仅CONDITION节点的输出边）")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "edge_xyz789",
                "source": "node_1",
                "target": "node_2",
                "label": "通过",
                "condition": {"field": "quality_passed", "operator": "==", "value": True}
            }
        }
    )


class WorkflowDefinition(BaseModel):
    """工作流定义"""

    id: str = Field(default_factory=lambda: f"workflow_{uuid.uuid4().hex[:8]}")
    project_id: Optional[str] = Field(None, description="所属项目ID；全局模板可为空")
    name: str = Field(..., description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    nodes: List[WorkflowNode] = Field(default_factory=list, description="节点列表")
    edges: List[WorkflowEdge] = Field(default_factory=list, description="边列表")
    variables: Dict[str, Any] = Field(default_factory=dict, description="工作流变量")
    is_template: bool = Field(default=False, description="是否为模板")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "workflow_abc123",
                "project_id": "proj_001",
                "name": "小说创作标准流程",
                "description": "完整的小说章节生成流程",
                "nodes": [
                    {"id": "start", "node_type": "start", "label": "开始"},
                    {"id": "plotter", "node_type": "agent", "agent_type": "MasterPlotterAgent", "label": "总编剧"},
                    {"id": "end", "node_type": "end", "label": "结束"}
                ],
                "edges": [
                    {"source": "start", "target": "plotter"},
                    {"source": "plotter", "target": "end"}
                ],
                "variables": {"chapter_count": 3},
                "is_template": False
            }
        }
    )


class WorkflowDefinitionCreate(BaseModel):
    """创建工作流请求"""

    name: str = Field(..., description="工作流名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="工作流描述")
    project_id: str = Field(..., description="所属项目ID")
    nodes: List[WorkflowNode] = Field(default_factory=list, description="节点列表")
    edges: List[WorkflowEdge] = Field(default_factory=list, description="边列表")
    variables: Dict[str, Any] = Field(default_factory=dict, description="工作流变量")
    is_template: bool = Field(default=False, description="是否为模板")


class WorkflowDefinitionUpdate(BaseModel):
    """更新工作流请求"""

    name: Optional[str] = Field(None, description="工作流名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="工作流描述")
    nodes: Optional[List[WorkflowNode]] = Field(None, description="节点列表")
    edges: Optional[List[WorkflowEdge]] = Field(None, description="边列表")
    variables: Optional[Dict[str, Any]] = Field(None, description="工作流变量")
    is_template: Optional[bool] = Field(None, description="是否为模板")


class WorkflowValidationResult(BaseModel):
    """工作流验证结果"""

    valid: bool = Field(..., description="是否有效")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    warnings: List[str] = Field(default_factory=list, description="警告列表")
    node_count: int = Field(default=0, description="节点数量")
    edge_count: int = Field(default=0, description="边数量")
    has_cycle: bool = Field(default=False, description="是否存在环")
    is_connected: bool = Field(default=True, description="是否连通")
