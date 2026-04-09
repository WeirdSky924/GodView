"""
时间系统相关的数据模型
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class DayPhaseEnum(str, Enum):
    """一天中的时段枚举"""
    MORNING = "早晨"
    FORENOON = "上午"
    NOON = "中午"
    AFTERNOON = "下午"
    EVENING = "傍晚"
    NIGHT = "夜晚"


class SeasonEnum(str, Enum):
    """季节枚举"""
    SPRING = "春"
    SUMMER = "夏"
    AUTUMN = "秋"
    WINTER = "冬"


class TimeModeEnum(str, Enum):
    """时间模式枚举"""
    LINEAR = "linear"
    NONLINEAR = "nonlinear"
    FROZEN = "frozen"


class TimeEventModel(BaseModel):
    """时间事件模型"""
    id: str = Field(..., description="事件ID")
    event_type: str = Field(..., description="事件类型")
    trigger_time: datetime = Field(..., description="触发时间")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据")
    recurring: bool = Field(default=False, description="是否循环事件")
    recurrence_interval_minutes: Optional[int] = Field(None, description="循环间隔（分钟）")
    executed: bool = Field(default=False, description="是否已执行")
    world_id: str = Field(..., description="所属世界ID")


class TimePointModel(BaseModel):
    """时间点记录模型"""
    id: str = Field(..., description="时间点ID")
    world_id: str = Field(..., description="所属世界ID")
    time: datetime = Field(..., description="时间点")
    tick_count: int = Field(..., description="时钟周期数")
    note: str = Field(default="", description="备注说明")
    day_phase: DayPhaseEnum = Field(..., description="时段")
    season: SeasonEnum = Field(..., description="季节")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


class TimeBranchModel(BaseModel):
    """时间分支模型"""
    id: str = Field(..., description="分支ID")
    world_id: str = Field(..., description="所属世界ID")
    name: str = Field(..., description="分支名称")
    time: datetime = Field(..., description="分支时间点")
    tick_count: int = Field(..., description="时钟周期数")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    is_active: bool = Field(default=False, description="是否为当前活跃分支")


class TimeUpdateModel(BaseModel):
    """时间更新模型"""
    world_id: str = Field(..., description="世界ID")
    current_time: datetime = Field(..., description="当前时间")
    previous_time: datetime = Field(..., description="之前时间")
    time_delta_minutes: float = Field(..., description="时间增量（分钟）")
    time_scale: float = Field(..., description="时间流速")
    tick_count: int = Field(..., description="时钟周期数")
    day_of_week: int = Field(..., description="星期几（0-6）")
    day_of_week_name: str = Field(..., description="星期名称")
    hour: int = Field(..., description="小时")
    minute: int = Field(..., description="分钟")
    day_phase: DayPhaseEnum = Field(..., description="时段")
    season: SeasonEnum = Field(..., description="季节")
    triggered_events: List[Dict[str, Any]] = Field(default_factory=list, description="触发的事件列表")


class TimeSystemConfig(BaseModel):
    """时间系统配置"""
    world_id: Optional[str] = Field(None, description="世界ID")
    time_scale: float = Field(default=1.0, ge=0.1, le=100.0, description="时间流速")
    time_mode: TimeModeEnum = Field(default=TimeModeEnum.LINEAR, description="时间模式")
    day_length: int = Field(default=24, ge=1, le=48, description="一天的小时数")
    enable_recording: bool = Field(default=True, description="是否启用时间记录")
    tick_interval_seconds: float = Field(default=1.0, ge=0.1, le=60.0, description="时钟周期间隔（秒）")


class TimeJumpRequest(BaseModel):
    """时间跳跃请求"""
    world_id: str = Field(..., description="世界ID")
    jump_type: str = Field(..., description="跳跃类型：forward/backward/to_absolute/to_year")
    target_time: Optional[datetime] = Field(None, description="目标时间（to_absolute）")
    delta_minutes: Optional[float] = Field(None, description="时间增量（分钟，forward/backward）")
    target_year: Optional[int] = Field(None, description="目标年份（to_year）")
    note: str = Field(default="", description="跳跃备注")


class TimeBranchRequest(BaseModel):
    """创建时间分支请求"""
    world_id: str = Field(..., description="世界ID")
    branch_name: str = Field(..., description="分支名称")
    note: str = Field(default="", description="分支说明")


class TimeControlRequest(BaseModel):
    """时间控制请求"""
    world_id: str = Field(..., description="世界ID")
    action: str = Field(..., description="操作：freeze/unfreeze/set_scale/advance")
    time_scale: Optional[float] = Field(None, description="新的时间流速（set_scale）")
    advance_minutes: Optional[float] = Field(None, description="推进分钟数（advance）")
    mode: Optional[TimeModeEnum] = Field(None, description="时间模式（设置模式）")


class TimeRecordRequest(BaseModel):
    """时间记录请求"""
    world_id: str = Field(..., description="世界ID")
    note: str = Field(..., description="记录备注")


class TimeHistoryResponse(BaseModel):
    """时间历史响应"""
    time_points: List[TimePointModel] = Field(default_factory=list, description="时间点列表")
    branches: List[TimeBranchModel] = Field(default_factory=list, description="时间分支列表")
    current_time: datetime = Field(..., description="当前时间")
    time_mode: TimeModeEnum = Field(..., description="当前时间模式")
    tick_count: int = Field(..., description="时钟周期数")


class WorldTimeLogModel(BaseModel):
    """世界时间日志模型（数据库存储）"""
    id: int = Field(default=None, description="主键ID")
    world_id: str = Field(..., description="世界ID")
    current_time: datetime = Field(..., description="当前时间")
    tick_number: int = Field(..., description="时钟周期编号")
    time_scale: float = Field(default=1.0, description="时间流速")
    day_phase: str = Field(..., description="时段")
    season: str = Field(..., description="季节")
    event_count: int = Field(default=0, description="该周期触发的事件数量")
    time_mode: str = Field(default="linear", description="时间模式")
    log_data: Dict[str, Any] = Field(default_factory=dict, description="额外的日志数据")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="记录时间")
