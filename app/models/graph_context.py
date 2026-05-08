"""关系图上下文检索模型。"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GraphContextSource(str, Enum):
    """图上下文来源。"""

    AUTO = "auto"
    NEBULA = "nebula"
    POSTGRES = "postgres"
    MIXED = "mixed"
    UNAVAILABLE = "unavailable"


class GraphContextOptions(BaseModel):
    """图上下文检索选项。"""

    depth: int = Field(default=1, ge=1, le=2, description="图遍历深度")
    max_nodes: int = Field(default=16, ge=1, le=100, description="最多返回节点数")
    include_world: bool = Field(default=True, description="是否包含所属世界")
    include_region: bool = Field(default=True, description="是否包含当前位置/区域")
    include_hooks: bool = Field(default=True, description="是否包含相关伏笔")
    world_id: Optional[str] = Field(default=None, description="当前世界 ID，用于世界作用域过滤")
    include_inherited: bool = Field(default=True, description="是否包含父级世界/项目级继承上下文")
    allow_fallback: bool = Field(default=True, description="NebulaGraph 不可用时是否回退 Postgres")
    source: GraphContextSource = Field(default=GraphContextSource.AUTO, description="读取来源")


class GraphNode(BaseModel):
    """标准化图节点。"""

    id: str
    type: str
    name: Optional[str] = None
    summary: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """标准化图边。"""

    source: str
    target: str
    type: str
    label: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphContextResponse(BaseModel):
    """图上下文统一响应。"""

    source: GraphContextSource
    partial: bool = False
    warnings: List[str] = Field(default_factory=list)
    anchor: Optional[GraphNode] = None
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
