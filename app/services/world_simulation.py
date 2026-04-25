"""
世界模拟引擎 - GodView v5 核心组件
协调所有子系统，管理整个世界的运行状态
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from app.services.time_system import TimeSystem, TimeUpdateResult
from app.services.entity_system import EntitySystem
from app.services.location_system import LocationSystem
from app.services.event_system import EventSystem
from app.services.memory_system import EnhancedMemorySystem


class SimulationStatus(Enum):
    """模拟状态"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class WorldState:
    """世界状态快照"""
    current_time: datetime
    tick_count: int
    entity_count: int
    active_events: int
    simulation_status: SimulationStatus
    last_update: datetime
    snapshot_data: Dict[str, Any] = field(default_factory=dict)


class WorldSimulationEngine:
    """世界模拟引擎

    管理整个世界的运行状态，协调所有子系统
    """

    def __init__(self, world_id: str, config: Dict[str, Any] = None):
        """初始化世界模拟引擎

        Args:
            world_id: 世界ID
            config: 配置参数
        """
        self.world_id = world_id
        self.config = config or {}

        # 核心子系统
        self.time_system: Optional[TimeSystem] = None
        self.entity_system = None  # EntitySystem
        self.location_system = None  # LocationSystem
        self.event_system = None  # EventSystem
        self.memory_system = None  # EnhancedMemorySystem
        self.intervention_system = None  # InterventionSystem

        # 运行状态
        self.is_running = False
        self.is_paused = False
        self.current_tick = 0
        self.tick_interval = self.config.get("tick_interval", 1.0)  # 秒
        self.simulation_task: Optional[asyncio.Task] = None

        # 状态监控
        self.status = SimulationStatus.STOPPED
        self.last_tick_time: Optional[datetime] = None
        self.total_ticks = 0
        self.error_count = 0

        # 回调函数
        self.tick_callbacks: List[Callable[[WorldState], None]] = []
        self.state_update_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        # 性能统计
        self.tick_durations: List[float] = []
        self.max_tick_duration_history = 100

        # 日志
        self.logger = logging.getLogger(__name__)

    async def initialize(
        self,
        time_config: Dict[str, Any] = None,
        entities: List[Dict[str, Any]] = None,
        locations: List[Dict[str, Any]] = None
    ):
        """初始化世界模拟引擎

        Args:
            time_config: 时间系统配置
            entities: 初始实体列表
            locations: 初始位置列表
        """
        self.logger.info(f"初始化世界模拟引擎: {self.world_id}")

        # 初始化时间系统
        self.time_system = TimeSystem(time_config or self.config.get("time_config", {}))

        # 初始化其他子系统（暂时使用占位符，后续实现）
        # self.entity_system = EntitySystem(entities or [])
        # self.location_system = LocationSystem(locations or [])
        # self.event_system = EventSystem(self.config.get("event_config", {}))
        # self.memory_system = EnhancedMemorySystem()
        # self.intervention_system = InterventionSystem()

        # 注册时间更新回调
        def time_update_callback(result: TimeUpdateResult):
            asyncio.create_task(self._handle_time_update(result))

        self.time_system.register_time_update_callback(time_update_callback)

        # 初始化实体系统
        self.entity_system = EntitySystem(self.config.get("entity_config", {}))
        if entities:
            for entity_data in entities:
                entity = self.entity_system.create_character_from_data(entity_data)
                self.entity_system.add_entity(entity)

        # 初始化位置系统
        self.location_system = LocationSystem(self.config.get("location_config", {}))
        if locations:
            from app.models.world import Region
            for location_data in locations:
                region = Region(**location_data)
                self.location_system.add_location(region)

        # 初始化事件系统
        self.event_system = EventSystem(self.config.get("event_config", {}))

        # 初始化记忆系统
        qdrant_db = self.config.get("qdrant_db")
        nebula_db = self.config.get("nebula_db")
        self.memory_system = EnhancedMemorySystem(qdrant_db, nebula_db)

        self.status = SimulationStatus.STOPPED
        self.logger.info("世界模拟引擎初始化完成")

        self.status = SimulationStatus.STOPPED
        self.logger.info("世界模拟引擎初始化完成")

    async def start_simulation(self):
        """启动世界模拟"""
        if self.is_running:
            self.logger.warning("模拟已在运行中")
            return False

        self.logger.info(f"启动世界模拟: {self.world_id}")
        self.is_running = True
        self.is_paused = False
        self.status = SimulationStatus.RUNNING

        # 创建模拟任务
        self.simulation_task = asyncio.create_task(self._simulation_loop())

        return True

    async def stop_simulation(self):
        """停止世界模拟"""
        if not self.is_running:
            self.logger.warning("模拟未在运行")
            return False

        self.logger.info(f"停止世界模拟: {self.world_id}")
        self.is_running = False
        self.status = SimulationStatus.STOPPED

        # 取消模拟任务
        if self.simulation_task:
            self.simulation_task.cancel()
            try:
                await self.simulation_task
            except asyncio.CancelledError:
                pass

        return True

    async def pause_simulation(self):
        """暂停世界模拟"""
        if not self.is_running or self.is_paused:
            return False

        self.logger.info(f"暂停世界模拟: {self.world_id}")
        self.is_paused = True
        self.status = SimulationStatus.PAUSED

        # 暂停时间系统
        if self.time_system:
            self.time_system.freeze_time()

        return True

    async def resume_simulation(self):
        """恢复世界模拟"""
        if not self.is_running or not self.is_paused:
            return False

        self.logger.info(f"恢复世界模拟: {self.world_id}")
        self.is_paused = False
        self.status = SimulationStatus.RUNNING

        # 恢复时间系统
        if self.time_system:
            self.time_system.unfreeze_time()

        return True

    async def manual_tick(self):
        """手动执行一个时钟周期"""
        if self.is_paused:
            return False

        self.logger.info(f"手动执行时钟周期: {self.world_id}")
        await self.tick()

        return True

    async def _simulation_loop(self):
        """模拟主循环"""
        self.logger.info(f"模拟循环已启动: {self.world_id}")

        try:
            while self.is_running:
                if not self.is_paused:
                    await self.tick()

                # 等待下一个周期
                await asyncio.sleep(self.tick_interval)

        except asyncio.CancelledError:
            self.logger.info(f"模拟循环被取消: {self.world_id}")
        except Exception as e:
            self.logger.error(f"模拟循环错误: {e}")
            self.status = SimulationStatus.ERROR
            self.error_count += 1

    async def tick(self):
        """执行一个时钟周期

        这是世界模拟的核心，每个周期执行以下步骤：
        1. 推进时间
        2. 更新所有实体状态
        3. 处理位置系统
        4. 触发事件
        5. 更新记忆
        6. 广播状态更新
        """
        tick_start_time = datetime.utcnow()

        try:
            # 1. 推进时间
            time_update = await self.time_system.advance()
            time_delta = time_update.time_delta
            self.current_tick += 1
            self.total_ticks += 1

            # 2. 更新所有实体状态
            await self._update_entities(time_delta)

            # 3. 处理位置系统
            await self._process_locations(time_delta)

            # 4. 触发事件
            await self._trigger_events(time_delta)

            # 5. 更新记忆
            await self._update_memories(time_delta)

            # 6. 记录性能统计
            tick_duration = (datetime.utcnow() - tick_start_time).total_seconds()
            self._record_tick_performance(tick_duration)

            # 7. 通知状态更新
            world_state = await self._get_current_world_state()
            await self._notify_state_update(world_state)

            # 记录最后tick时间
            self.last_tick_time = datetime.utcnow()

            # 通知tick回调
            await self._notify_tick_callbacks(world_state)

        except Exception as e:
            self.logger.error(f"时钟周期执行失败: {e}")
            self.status = SimulationStatus.ERROR
            self.error_count += 1
            raise

    async def _update_entities(self, time_delta: timedelta):
        """更新所有实体状态"""
        if self.entity_system:
            await self.entity_system.update_all(time_delta)

    async def _process_locations(self, time_delta: timedelta):
        """处理位置系统"""
        if self.location_system and self.entity_system:
            await self.location_system.simulate_activity(time_delta, self.entity_system)

    async def _trigger_events(self, time_delta: timedelta):
        """触发事件"""
        if self.event_system:
            world_state = await self._build_world_state()
            await self.event_system.process_triggers(time_delta, world_state)
            await self.event_system.update_active_events(time_delta)

    async def _update_memories(self, time_delta: timedelta):
        """更新记忆"""
        if self.memory_system:
            await self.memory_system.update_decay(time_delta)

            # 为实体添加记忆（基于世界状态）
            if self.entity_system:
                world_state = await self._build_world_state()
                await self._generate_entity_memories(world_state)

    async def _handle_time_update(self, time_update: TimeUpdateResult):
        """处理时间更新"""
        # 可以在这里处理时间变化对世界的影响
        # 比如昼夜交替、季节变化等
        pass

    async def _build_world_state(self) -> Dict[str, Any]:
        """构建世界状态"""
        time_info = self.time_system.get_time_info() if self.time_system else {}

        entities = {}
        if self.entity_system:
            for entity_id, entity in self.entity_system.entities.items():
                entities[entity_id] = {
                    "name": entity.name,
                    "type": entity.entity_type.value,
                    "location": entity.current_location,
                    "status": entity.status.value,
                    "attributes": entity.attributes
                }

        world_state = {
            "current_time": self.time_system.get_current_time() if self.time_system else None,
            "time_phase": time_info.get("day_phase", "day"),
            "entities": entities,
            "total_entities": len(entities),
            "simulation_status": self.status.value,
            "current_tick": self.current_tick
        }

        return world_state

    async def _get_current_world_state(self) -> WorldState:
        """获取当前世界状态"""
        return WorldState(
            current_time=self.time_system.get_current_time(),
            tick_count=self.current_tick,
            entity_count=0,  # TODO: 从实体系统获取
            active_events=0,  # TODO: 从事件系统获取
            simulation_status=self.status,
            last_update=datetime.utcnow(),
            snapshot_data=await self.create_snapshot()
        )

    async def _notify_state_update(self, world_state: WorldState):
        """通知状态更新"""
        state_data = {
            "type": "world_state_update",
            "data": {
                "world_id": self.world_id,
                "current_time": world_state.current_time.isoformat(),
                "tick_count": world_state.tick_count,
                "entity_count": world_state.entity_count,
                "active_events": world_state.active_events,
                "status": world_state.simulation_status.value,
                "last_update": world_state.last_update.isoformat()
            }
        }

        for callback in self.state_update_callbacks:
            try:
                callback(state_data)
            except Exception as e:
                self.logger.error(f"状态更新回调执行失败: {e}")

    async def _notify_tick_callbacks(self, world_state: WorldState):
        """通知tick回调函数"""
        for callback in self.tick_callbacks:
            try:
                callback(world_state)
            except Exception as e:
                self.logger.error(f"tick回调执行失败: {e}")

    def _record_tick_performance(self, duration: float):
        """记录时钟周期性能"""
        self.tick_durations.append(duration)
        if len(self.tick_durations) > self.max_tick_duration_history:
            self.tick_durations.pop(0)

    def get_average_tick_duration(self) -> float:
        """获取平均时钟周期时长"""
        if not self.tick_durations:
            return 0.0
        return sum(self.tick_durations) / len(self.tick_durations)

    def get_max_tick_duration(self) -> float:
        """获取最大时钟周期时长"""
        if not self.tick_durations:
            return 0.0
        return max(self.tick_durations)

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            "average_tick_duration": self.get_average_tick_duration(),
            "max_tick_duration": self.get_max_tick_duration(),
            "total_ticks": self.total_ticks,
            "error_count": self.error_count,
            "current_tick": self.current_tick,
            "status": self.status.value,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "last_tick_time": self.last_tick_time.isoformat() if self.last_tick_time else None,
        }

    async def create_snapshot(self) -> Dict[str, Any]:
        """创建世界快照"""
        snapshot = {
            "world_id": self.world_id,
            "timestamp": datetime.utcnow().isoformat(),
            "time_system": {
                "current_time": self.time_system.get_current_time().isoformat(),
                "time_scale": self.time_system.get_time_scale(),
                "tick_count": self.time_system.tick_count
            } if self.time_system else None,
            "entities": await self._get_entities_snapshot() if self.entity_system else [],
            "locations": await self._get_locations_snapshot() if self.location_system else [],
            "active_events": await self._get_events_snapshot() if self.event_system else [],
            "memory_snapshots": {},  # TODO: 从记忆系统获取
            "performance": self.get_performance_stats()
        }

        return snapshot

    def register_tick_callback(self, callback: Callable[[WorldState], None]):
        """注册时钟周期回调函数"""
        self.tick_callbacks.append(callback)

    def unregister_tick_callback(self, callback: Callable[[WorldState], None]):
        """取消注册时钟周期回调函数"""
        if callback in self.tick_callbacks:
            self.tick_callbacks.remove(callback)

    def register_state_update_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """注册状态更新回调函数"""
        self.state_update_callbacks.append(callback)

    def unregister_state_update_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """取消注册状态更新回调函数"""
        if callback in self.state_update_callbacks:
            self.state_update_callbacks.remove(callback)

    def get_time_system(self) -> Optional[TimeSystem]:
        """获取时间系统实例"""
        return self.time_system

    def get_status(self) -> SimulationStatus:
        """获取模拟状态"""
        return self.status

    def set_tick_interval(self, interval: float):
        """设置时钟周期间隔

        Args:
            interval: 间隔时间（秒）
        """
        self.tick_interval = max(0.1, min(interval, 60.0))
        self.logger.info(f"设置时钟周期间隔: {self.tick_interval}秒")

    async def _get_entities_snapshot(self) -> List[Dict[str, Any]]:
        """获取实体快照"""
        entities = []
        for entity_id, entity in self.entity_system.entities.items():
            entities.append({
                "id": entity_id,
                "name": entity.name,
                "type": entity.entity_type.value,
                "status": entity.status.value,
                "location": entity.current_location,
                "attributes": entity.attributes,
                "current_action": entity.current_action.description if entity.current_action else None,
                "current_goal": entity.current_goal.description if entity.current_goal else None
            })
        return entities

    async def _get_locations_snapshot(self) -> List[Dict[str, Any]]:
        """获取位置快照"""
        locations = []
        for location_id, location in self.location_system.locations.items():
            locations.append({
                "id": location_id,
                "name": location.region.name,
                "type": location.region.region_type.value,
                "state": location.state.value,
                "weather": location.weather,
                "temperature": location.temperature,
                "population": location.state_data.population,
                "activity_level": location.state_data.activity_level
            })
        return locations

    async def _get_events_snapshot(self) -> List[Dict[str, Any]]:
        """获取事件快照"""
        events = []
        for event in self.event_system.active_events:
            events.append({
                "id": event.event_id,
                "name": event.name,
                "type": event.event_type.value,
                "priority": event.priority.value,
                "status": event.status.value,
                "description": event.description,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "involved_entities": event.involved_entities,
                "involved_locations": event.involved_locations
            })
        return events

    async def _generate_entity_memories(self, world_state: Dict[str, Any]):
        """为实体生成记忆"""
        if not self.entity_system or not self.memory_system:
            return

        # 为每个活跃实体生成记忆
        for entity_id, entity in self.entity_system.entities.items():
            if entity.status.value != "active":
                continue

            # 基于当前状态生成记忆
            current_context = self._build_entity_context(entity, world_state)

            # 检查是否值得记录记忆
            if self._is_memory_worth_recording(entity, world_state):
                memory_content = f"在{entity.current_location}进行了相关活动，当前状态正常"
                metadata = {
                    "emotional_intensity": entity.mood if hasattr(entity, 'mood') else 0.5,
                    "related_entities": self.entity_system.get_entities_in_location(entity.current_location) if entity.current_location else [],
                    "related_locations": [entity.current_location] if entity.current_location else []
                }

                await self.memory_system.add_memory(entity_id, memory_content, metadata)

    def _build_entity_context(self, entity, world_state: Dict[str, Any]) -> str:
        """构建实体上下文"""
        context_parts = []

        if entity.current_location:
            context_parts.append(f"当前位置: {entity.current_location}")

        if hasattr(entity, 'mood'):
            mood_desc = "愉快" if entity.mood > 0.6 else "平静" if entity.mood > 0.4 else "低落"
            context_parts.append(f"情绪状态: {mood_desc}")

        return ", ".join(context_parts)

    def _is_memory_worth_recording(self, entity, world_state: Dict[str, Any]) -> bool:
        """检查记忆是否值得记录"""
        # 简化实现：随机决定
        import random
        return random.random() < 0.2  # 20%概率记录记忆