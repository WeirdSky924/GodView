"""
世界模拟相关的数据模型
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class SimulationStatusEnum(str, Enum):
    """模拟状态枚举"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class WorldSimulationModel(BaseModel):
    """世界模拟模型"""
    world_id: str = Field(..., description="世界ID")
    status: SimulationStatusEnum = Field(default=SimulationStatusEnum.STOPPED, description="模拟状态")
    current_tick: int = Field(default=0, description="当前时钟周期")
    total_ticks: int = Field(default=0, description="总时钟周期数")
    error_count: int = Field(default=0, description="错误计数")
    tick_interval: float = Field(default=1.0, ge=0.1, le=60.0, description="时钟周期间隔（秒）")
    is_running: bool = Field(default=False, description="是否正在运行")
    is_paused: bool = Field(default=False, description="是否暂停")
    last_tick_time: Optional[datetime] = Field(None, description="最后tick时间")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


class WorldStateSnapshot(BaseModel):
    """世界状态快照"""
    world_id: str = Field(..., description="世界ID")
    snapshot_id: str = Field(..., description="快照ID")
    timestamp: datetime = Field(..., description="快照时间")
    time_system: Optional[Dict[str, Any]] = Field(None, description="时间系统状态")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="实体列表")
    locations: List[Dict[str, Any]] = Field(default_factory=list, description="位置列表")
    active_events: List[Dict[str, Any]] = Field(default_factory=list, description="活跃事件列表")
    memory_snapshots: Dict[str, Any] = Field(default_factory=dict, description="记忆快照")
    performance: Dict[str, Any] = Field(default_factory=dict, description="性能数据")


class PerformanceStats(BaseModel):
    """性能统计数据"""
    average_tick_duration: float = Field(..., description="平均时钟周期时长（秒）")
    max_tick_duration: float = Field(..., description="最大时钟周期时长（秒）")
    total_ticks: int = Field(..., description="总时钟周期数")
    error_count: int = Field(..., description="错误计数")
    current_tick: int = Field(..., description="当前时钟周期")
    status: str = Field(..., description="状态")
    is_running: bool = Field(..., description="是否运行中")
    is_paused: bool = Field(..., description="是否暂停")
    last_tick_time: Optional[str] = Field(None, description="最后tick时间")


class SimulationControlRequest(BaseModel):
    """模拟控制请求"""
    world_id: str = Field(..., description="世界ID")
    action: str = Field(..., description="操作：start/stop/pause/resume/manual_tick/set_interval")
    tick_interval: Optional[float] = Field(None, description="新的时钟周期间隔（秒）")


class SimulationInitializeRequest(BaseModel):
    """模拟初始化请求"""
    world_id: str = Field(..., description="世界ID")
    time_config: Optional[Dict[str, Any]] = Field(None, description="时间系统配置")
    entities: Optional[List[Dict[str, Any]]] = Field(None, description="初始实体列表")
    locations: Optional[List[Dict[str, Any]]] = Field(None, description="初始位置列表")


class SimulationStatusResponse(BaseModel):
    """模拟状态响应"""
    world_id: str = Field(..., description="世界ID")
    status: SimulationStatusEnum = Field(..., description="模拟状态")
    performance: PerformanceStats = Field(..., description="性能统计")
    current_time: Optional[str] = Field(None, description="当前时间")
    entity_count: int = Field(default=0, description="实体数量")
    active_events: int = Field(default=0, description="活跃事件数量")
    last_update: datetime = Field(..., description="最后更新时间")