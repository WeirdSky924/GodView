"""
时间流逝系统 - GodView v5 核心组件
管理连续时间轴、时间流速、定时事件和时间段计算
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class DayPhase(Enum):
    """一天中的时段"""
    MORNING = "早晨"
    FORENOON = "上午"
    NOON = "中午"
    AFTERNOON = "下午"
    EVENING = "傍晚"
    NIGHT = "夜晚"


class Season(Enum):
    """季节"""
    SPRING = "春"
    SUMMER = "夏"
    AUTUMN = "秋"
    WINTER = "冬"


@dataclass
class TimeEvent:
    """时间事件"""
    trigger_time: datetime
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    callback: Optional[Callable] = None
    executed: bool = False
    recurring: bool = False
    recurrence_interval: Optional[timedelta] = None


@dataclass
class TimeUpdateResult:
    """时间更新结果"""
    current_time: datetime
    previous_time: datetime
    time_delta: timedelta
    day_of_week: int
    day_phase: DayPhase
    hour: int
    season: Season
    triggered_events: List[Dict[str, Any]]
    time_scale: float
    tick_count: int


class TimeSystem:
    """时间流逝系统

    管理连续时间轴，支持时间推进、定时事件调度、时间段计算等核心功能
    """

    def __init__(self, world_config: Optional[Dict[str, Any]] = None):
        """初始化时间系统

        Args:
            world_config: 世界配置，包含时间相关参数
        """
        self.world_config = world_config or {}

        # 时间状态
        self.current_time = datetime.utcnow()
        self.time_scale = self.world_config.get("time_scale", 1.0)  # 时间流速
        self.day_length = self.world_config.get("day_length", 24)  # 一天的小时数

        # 季节配置
        self.seasons_config = self.world_config.get("seasons", {
            "spring": {"months": [3, 4, 5], "name": "春"},
            "summer": {"months": [6, 7, 8], "name": "夏"},
            "autumn": {"months": [9, 10, 11], "name": "秋"},
            "winter": {"months": [12, 1, 2], "name": "冬"},
        })

        # 定时事件
        self.scheduled_events: List[TimeEvent] = []

        # 时钟周期计数
        self.tick_count = 0

        # 回调函数注册
        self.time_update_callbacks: List[Callable[[TimeUpdateResult], None]] = []

    async def advance(self, minutes: int = 10) -> TimeUpdateResult:
        """推进时间

        Args:
            minutes: 要推进的分钟数（实际会乘以 time_scale）

        Returns:
            TimeUpdateResult: 时间更新结果
        """
        # 计算实际推进时间
        actual_minutes = minutes * self.time_scale
        previous_time = self.current_time
        self.current_time += timedelta(minutes=actual_minutes)

        # 增加时钟周期计数
        self.tick_count += 1

        # 触发定时事件
        triggered = await self._check_scheduled_events()

        # 构建更新结果
        result = TimeUpdateResult(
            current_time=self.current_time,
            previous_time=previous_time,
            time_delta=self.current_time - previous_time,
            day_of_week=self.current_time.weekday(),
            day_phase=self._get_day_phase(),
            hour=self.current_time.hour,
            season=self._get_season(),
            triggered_events=triggered,
            time_scale=self.time_scale,
            tick_count=self.tick_count
        )

        # 通知注册的回调函数
        for callback in self.time_update_callbacks:
            try:
                callback(result)
            except Exception as e:
                print(f"时间更新回调执行失败: {e}")

        return result

    def schedule_event(
        self,
        trigger_time: datetime,
        event_type: str,
        data: Dict[str, Any],
        callback: Optional[Callable] = None,
        recurring: bool = False,
        recurrence_interval: Optional[timedelta] = None
    ) -> str:
        """安排定时事件

        Args:
            trigger_time: 触发时间
            event_type: 事件类型
            data: 事件数据
            callback: 回调函数
            recurring: 是否循环事件
            recurrence_interval: 循环间隔

        Returns:
            str: 事件ID
        """
        event_id = f"event_{hash(trigger_time)}_{event_type}"
        event = TimeEvent(
            trigger_time=trigger_time,
            event_type=event_type,
            data=data,
            callback=callback,
            recurring=recurring,
            recurrence_interval=recurrence_interval
        )
        self.scheduled_events.append(event)
        return event_id

    def schedule_after(
        self,
        delay: timedelta,
        event_type: str,
        data: Dict[str, Any],
        callback: Optional[Callable] = None
    ) -> str:
        """在延迟后安排事件

        Args:
            delay: 延迟时间
            event_type: 事件类型
            data: 事件数据
            callback: 回调函数

        Returns:
            str: 事件ID
        """
        trigger_time = self.current_time + delay
        return self.schedule_event(trigger_time, event_type, data, callback)

    def cancel_event(self, event_id: str) -> bool:
        """取消定时事件

        Args:
            event_id: 事件ID

        Returns:
            bool: 是否成功取消
        """
        # 由于我们用哈希生成ID，这里简化处理，按触发时间和类型查找
        for event in self.scheduled_events[:]:
            if event_id in f"event_{hash(event.trigger_time)}_{event.event_type}":
                self.scheduled_events.remove(event)
                return True
        return False

    def get_current_time(self) -> datetime:
        """获取当前时间"""
        return self.current_time

    def set_time_scale(self, scale: float):
        """设置时间流速

        Args:
            scale: 时间流速倍数
        """
        self.time_scale = max(0.1, min(scale, 100.0))  # 限制在合理范围内

    def get_time_scale(self) -> float:
        """获取时间流速"""
        return self.time_scale

    def register_time_update_callback(self, callback: Callable[[TimeUpdateResult], None]):
        """注册时间更新回调函数

        Args:
            callback: 回调函数
        """
        self.time_update_callbacks.append(callback)

    def unregister_time_update_callback(self, callback: Callable[[TimeUpdateResult], None]):
        """取消注册时间更新回调函数

        Args:
            callback: 回调函数
        """
        if callback in self.time_update_callbacks:
            self.time_update_callbacks.remove(callback)

    async def _check_scheduled_events(self) -> List[Dict[str, Any]]:
        """检查并触发到期事件

        Returns:
            List[Dict]: 触发的事件列表
        """
        triggered = []
        for event in self.scheduled_events[:]:
            if self.current_time >= event.trigger_time and not event.executed:
                # 执行回调
                if event.callback:
                    try:
                        await event.callback(event)
                    except Exception as e:
                        print(f"事件回调执行失败: {e}")

                # 记录触发事件
                triggered.append({
                    "event_type": event.event_type,
                    "data": event.data,
                    "trigger_time": event.trigger_time.isoformat()
                })

                # 处理循环事件
                if event.recurring and event.recurrence_interval:
                    event.trigger_time += event.recurrence_interval
                    event.executed = False
                else:
                    self.scheduled_events.remove(event)

        return triggered

    def _get_day_phase(self) -> DayPhase:
        """获取一天中的时段"""
        hour = self.current_time.hour
        if 5 <= hour < 9:
            return DayPhase.MORNING
        elif 9 <= hour < 12:
            return DayPhase.FORENOON
        elif 12 <= hour < 14:
            return DayPhase.NOON
        elif 14 <= hour < 18:
            return DayPhase.AFTERNOON
        elif 18 <= hour < 21:
            return DayPhase.EVENING
        else:
            return DayPhase.NIGHT

    def _get_season(self) -> Season:
        """获取季节"""
        month = self.current_time.month
        # 使用英文键名映射到枚举
        season_map = {
            "spring": Season.SPRING,
            "summer": Season.SUMMER,
            "autumn": Season.AUTUMN,
            "winter": Season.WINTER,
        }
        for season_name, config in self.seasons_config.items():
            if month in config["months"]:
                return season_map.get(season_name.lower(), Season.SPRING)
        return Season.SPRING  # 默认返回春天

    def get_formatted_time(self) -> str:
        """获取格式化的时间字符串

        Returns:
            str: 格式化的时间字符串
        """
        return self.current_time.strftime("%Y-%m-%d %H:%M:%S")

    def get_time_info(self) -> Dict[str, Any]:
        """获取时间信息字典

        Returns:
            Dict: 详细的时间信息
        """
        day_phase = self._get_day_phase()
        season = self._get_season()

        return {
            "current_time": self.current_time.isoformat(),
            "formatted_time": self.get_formatted_time(),
            "tick_count": self.tick_count,
            "time_scale": self.time_scale,
            "day_of_week": self.current_time.weekday(),
            "day_of_week_name": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][self.current_time.weekday()],
            "hour": self.current_time.hour,
            "minute": self.current_time.minute,
            "day_phase": day_phase.value,
            "season": season.value,
            "month": self.current_time.month,
            "day": self.current_time.day,
            "year": self.current_time.year,
        }

    def get_elapsed_time(self) -> timedelta:
        """获取从系统启动开始经过的时间

        Returns:
            timedelta: 经过的时间
        """
        if not hasattr(self, '_start_time'):
            self._start_time = self.current_time
        return self.current_time - self._start_time

    def reset(self):
        """重置时间系统"""
        self.current_time = datetime.utcnow()
        self.scheduled_events.clear()
        self.tick_count = 0
        if hasattr(self, '_start_time'):
            delattr(self, '_start_time')

    # ===== 时间非线性操作（v5扩展）=====

    def jump_to_time(self, target_time: datetime) -> TimeUpdateResult:
        """时间跳跃到指定时间点

        Args:
            target_time: 目标时间点

        Returns:
            TimeUpdateResult: 时间更新结果
        """
        previous_time = self.current_time
        self.current_time = target_time

        # 增加时钟周期计数
        self.tick_count += 1

        # 清理无法触发的定时事件（时间已经过去的）
        self._clean_expired_events()

        # 构建更新结果
        result = TimeUpdateResult(
            current_time=self.current_time,
            previous_time=previous_time,
            time_delta=self.current_time - previous_time,
            day_of_week=self.current_time.weekday(),
            day_phase=self._get_day_phase(),
            hour=self.current_time.hour,
            season=self._get_season(),
            triggered_events=[],
            time_scale=self.time_scale,
            tick_count=self.tick_count
        )

        # 通知注册的回调函数
        for callback in self.time_update_callbacks:
            try:
                callback(result)
            except Exception as e:
                print(f"时间更新回调执行失败: {e}")

        return result

    def jump_forward(self, timedelta_obj: timedelta) -> TimeUpdateResult:
        """时间向前跳跃

        Args:
            timedelta_obj: 时间间隔

        Returns:
            TimeUpdateResult: 时间更新结果
        """
        return self.jump_to_time(self.current_time + timedelta_obj)

    def jump_backward(self, timedelta_obj: timedelta) -> TimeUpdateResult:
        """时间向后跳跃（穿越）

        Args:
            timedelta_obj: 时间间隔（负值或正数都可以）

        Returns:
            TimeUpdateResult: 时间更新结果
        """
        return self.jump_to_time(self.current_time - timedelta_obj)

    def jump_to_year(self, year: int, month: int = 1, day: int = 1,
                    hour: int = 0, minute: int = 0, second: int = 0) -> TimeUpdateResult:
        """跳跃到指定年份

        Args:
            year: 年份
            month: 月份
            day: 日期
            hour: 小时
            minute: 分钟
            second: 秒

        Returns:
            TimeUpdateResult: 时间更新结果
        """
        target_time = datetime(year, month, day, hour, minute, second)
        return self.jump_to_time(target_time)

    def create_time_branch(self, branch_name: str) -> str:
        """创建时间分支（保存当前时间状态）

        Args:
            branch_name: 分支名称

        Returns:
            str: 分支ID
        """
        branch_id = f"branch_{branch_name}_{self.tick_count}"
        if not hasattr(self, '_time_branches'):
            self._time_branches = {}

        self._time_branches[branch_id] = {
            "name": branch_name,
            "time": self.current_time,
            "tick_count": self.tick_count,
            "scheduled_events": self.scheduled_events.copy(),
            "created_at": datetime.utcnow()
        }

        return branch_id

    def switch_to_branch(self, branch_id: str) -> bool:
        """切换到时间分支

        Args:
            branch_id: 分支ID

        Returns:
            bool: 是否成功切换
        """
        if not hasattr(self, '_time_branches') or branch_id not in self._time_branches:
            return False

        branch = self._time_branches[branch_id]
        self.jump_to_time(branch["time"])
        self.scheduled_events = branch["scheduled_events"].copy()
        return True

    def get_time_branches(self) -> List[Dict[str, Any]]:
        """获取所有时间分支

        Returns:
            List[Dict]: 时间分支列表
        """
        if not hasattr(self, '_time_branches'):
            return []

        branches = []
        for branch_id, data in self._time_branches.items():
            branches.append({
                "id": branch_id,
                "name": data["name"],
                "time": data["time"].isoformat(),
                "tick_count": data["tick_count"],
                "created_at": data["created_at"].isoformat(),
                "scheduled_events_count": len(data["scheduled_events"])
            })

        return branches

    def set_time_mode(self, mode: str):
        """设置时间模式

        Args:
            mode: 时间模式
                - "linear": 线性时间（默认）
                - "nonlinear": 非线性时间（允许跳跃、穿越）
                - "frozen": 时间冻结
        """
        self.time_mode = mode

    def get_time_mode(self) -> str:
        """获取当前时间模式"""
        return getattr(self, 'time_mode', 'linear')

    def freeze_time(self):
        """冻结时间（暂停时间推进）"""
        self.set_time_mode("frozen")

    def unfreeze_time(self):
        """解冻时间（恢复时间推进）"""
        if self.get_time_mode() == "frozen":
            self.set_time_mode("linear")

    def is_time_frozen(self) -> bool:
        """检查时间是否被冻结"""
        return self.get_time_mode() == "frozen"

    def _clean_expired_events(self):
        """清理过期的定时事件"""
        for event in self.scheduled_events[:]:
            if self.current_time > event.trigger_time and not event.recurring:
                self.scheduled_events.remove(event)

    # ===== 时间线历史记录 =====

    def record_time_point(self, note: str = "") -> str:
        """记录时间点（用于剧情关键节点）

        Args:
            note: 备注说明

        Returns:
            str: 时间点ID
        """
        time_point_id = f"timepoint_{self.tick_count}"
        if not hasattr(self, '_time_points'):
            self._time_points = []

        self._time_points.append({
            "id": time_point_id,
            "time": self.current_time,
            "tick_count": self.tick_count,
            "note": note,
            "day_phase": self._get_day_phase().value,
            "season": self._get_season().value
        })

        return time_point_id

    def get_time_history(self) -> List[Dict[str, Any]]:
        """获取时间历史记录

        Returns:
            List[Dict]: 时间历史列表
        """
        if not hasattr(self, '_time_points'):
            return []

        return [
            {
                "id": tp["id"],
                "time": tp["time"].isoformat(),
                "tick_count": tp["tick_count"],
                "note": tp["note"],
                "day_phase": tp["day_phase"],
                "season": tp["season"]
            }
            for tp in self._time_points
        ]

    def find_time_point_by_note(self, note_pattern: str) -> Optional[Dict[str, Any]]:
        """根据备注查找时间点

        Args:
            note_pattern: 备注模式（支持模糊匹配）

        Returns:
            Dict: 时间点信息，如果未找到则返回None
        """
        if not hasattr(self, '_time_points'):
            return None

        for tp in reversed(self._time_points):  # 从最新的开始查找
            if note_pattern.lower() in tp["note"].lower():
                return {
                    "id": tp["id"],
                    "time": tp["time"].isoformat(),
                    "tick_count": tp["tick_count"],
                    "note": tp["note"],
                    "day_phase": tp["day_phase"],
                    "season": tp["season"]
                }

        return None