"""
GodView v5 系统集成测试
验证时间系统、实体系统、位置系统、事件系统和记忆系统的协同工作
"""

import asyncio
import pytest
from datetime import datetime, timedelta

from app.services.time_system import TimeSystem, TimeEvent
from app.services.entity_system import EntitySystem, Entity, EntityType, CharacterEntity
from app.services.location_system import LocationSystem, LocationEntity
from app.services.event_system import EventSystem, Event, EventType, EventPriority
from app.services.memory_system import EnhancedMemorySystem
from app.services.world_simulation import WorldSimulationEngine

# 模拟数据
TEST_WORLD_ID = "test_world_v5"
TEST_CHARACTER_DATA = {
    "id": "char_001",
    "name": "测试角色",
    "description": "用于测试的角色",
    "personality_traits": [
        {"trait_name": "开放性", "trait_value": 0.7},
        {"trait_name": "外向性", "trait_value": 0.6},
        {"trait_name": "宜人性", "trait_value": 0.5}
    ],
    "background_story": "这是一个测试角色",
    "goals": ["测试目标1", "测试目标2"],
    "role": "supporting"
}

TEST_REGION_DATA = {
    "id": "loc_001",
    "name": "测试地点",
    "world_id": TEST_WORLD_ID,
    "region_type": "custom",
    "terrain_type": "custom",
    "description": "用于测试的地点",
    "atmosphere": "平静",
    "connections": []
}


class TestV5Integration:
    """v5系统集成测试类"""

    @pytest.mark.asyncio
    async def test_time_system_basic(self):
        """测试时间系统基础功能"""
        time_system = TimeSystem({"time_scale": 1.0})

        # 测试时间推进
        initial_time = time_system.get_current_time()
        update_result = await time_system.advance(minutes=60)
        new_time = time_system.get_current_time()

        assert new_time == initial_time + timedelta(hours=1)
        assert update_result.tick_count == 1
        assert update_result.time_scale == 1.0

    @pytest.mark.asyncio
    async def test_time_system_jumps(self):
        """测试时间跳跃功能"""
        time_system = TimeSystem({"time_scale": 1.0})

        # 测试向前跳跃
        initial_time = time_system.get_current_time()
        result = time_system.jump_forward(timedelta(hours=2))
        new_time = time_system.get_current_time()

        assert new_time == initial_time + timedelta(hours=2)

        # 测试向后跳跃
        result = time_system.jump_backward(timedelta(hours=1))
        new_time = time_system.get_current_time()

        assert new_time == initial_time + timedelta(hours=1)

    @pytest.mark.asyncio
    async def test_entity_system_basic(self):
        """测试实体系统基础功能"""
        entity_system = EntitySystem()

        # 创建角色实体
        character_entity = entity_system.create_character_from_data(TEST_CHARACTER_DATA)
        entity_system.add_entity(character_entity)

        # 验证实体添加
        assert "char_001" in entity_system.entities
        assert "char_001" in entity_system.characters

        # 验证角色属性
        assert character_entity.name == "测试角色"
        assert character_entity.entity_type == EntityType.CHARACTER
        assert len(character_entity.available_actions) > 0
        assert len(character_entity.goals) > 0

    @pytest.mark.asyncio
    async def test_character_autonomous_behavior(self):
        """测试角色自主行为决策"""
        entity_system = EntitySystem()

        character_entity = entity_system.create_character_from_data(TEST_CHARACTER_DATA)
        entity_system.add_entity(character_entity)

        # 测试行动概率计算
        if isinstance(character_entity, CharacterEntity):
            context = {
                "time_phase": "day",
                "location_type": "tavern",
                "present_entities": []
            }

            # 获取可用行动
            if character_entity.available_actions:
                action = character_entity.available_actions[0]
                probability = character_entity.calculate_action_probability(action, context)

                assert 0.0 <= probability <= 1.0

    @pytest.mark.asyncio
    async def test_location_system_basic(self):
        """测试位置系统基础功能"""
        location_system = LocationSystem()

        # 添加地点
        from app.models.world import Region
        region = Region(**TEST_REGION_DATA)
        location_system.add_location(region)

        # 验证地点添加
        assert "loc_001" in location_system.locations
        assert location_system.locations["loc_001"].region.name == "测试地点"

    @pytest.mark.asyncio
    async def test_character_movement(self):
        """测试角色移动功能"""
        entity_system = EntitySystem()
        location_system = LocationSystem()

        # 创建角色和地点
        character_entity = entity_system.create_character_from_data(TEST_CHARACTER_DATA)
        entity_system.add_entity(character_entity)

        from app.models.world import Region
        region = Region(**TEST_REGION_DATA)
        location_system.add_location(region)

        # 移动角色
        success = await location_system.move_character("char_001", "loc_001", entity_system)

        assert success
        assert character_entity.current_location == "loc_001"

    @pytest.mark.asyncio
    async def test_event_system_basic(self):
        """测试事件系统基础功能"""
        event_system = EventSystem()

        # 创建自定义事件
        from app.services.event_system import EventEffect
        event = event_system.create_custom_event(
            event_id="test_event_001",
            event_type=EventType.SOCIAL,
            name="测试事件",
            description="这是一个测试事件",
            effects=[
                EventEffect(
                    effect_type="add_item",
                    target_type="entity",
                    parameters={"item": "test_item"}
                )
            ],
            priority=EventPriority.NORMAL
        )

        assert event.event_id == "test_event_001"
        assert event.event_type == EventType.SOCIAL
        assert len(event.effects) > 0

    @pytest.mark.asyncio
    async def test_event_generation(self):
        """测试随机事件生成"""
        event_system = EventSystem()

        world_state = {
            "current_time": datetime.utcnow(),
            "time_phase": "day",
            "entities": {},
            "simulation_status": "running"
        }

        # 生成随机事件
        event = await event_system.generate_random_event(world_state)

        # 事件生成是概率性的，所以可能为None
        if event:
            assert event.event_type in EventType
            assert event.status.value == "pending"

    @pytest.mark.asyncio
    async def test_memory_system_basic(self):
        """测试记忆系统基础功能"""
        memory_system = EnhancedMemorySystem()

        # 添加记忆
        memory = await memory_system.add_memory(
            character_id="char_001",
            content="这是一条测试记忆",
            metadata={
                "emotional_intensity": 0.7,
                "valence": 0.8,
                "personal_significance": 0.6
            }
        )

        assert memory.character_id == "char_001"
        assert memory.content == "这是一条测试记忆"
        assert memory.importance > 0

        # 验证记忆添加到工作记忆
        assert len(memory_system.working.memories) > 0

    @pytest.mark.asyncio
    async def test_memory_retrieval(self):
        """测试记忆检索功能"""
        memory_system = EnhancedMemorySystem()

        # 添加多条记忆
        await memory_system.add_memory("char_001", "关于战斗的记忆", {"emotional_intensity": 0.9})
        await memory_system.add_memory("char_001", "关于社交的记忆", {"emotional_intensity": 0.6})
        await memory_system.add_memory("char_001", "关于探索的记忆", {"emotional_intensity": 0.4})

        # 检索相关记忆
        relevant_memories = await memory_system.retrieve_relevant_memories(
            character_id="char_001",
            context="战斗相关",
            limit=3
        )

        assert len(relevant_memories) > 0

    @pytest.mark.asyncio
    async def test_world_simulation_engine(self):
        """测试世界模拟引擎"""
        engine = WorldSimulationEngine(TEST_WORLD_ID)

        # 初始化引擎
        await engine.initialize(
            time_config={"time_scale": 1.0},
            entities=[TEST_CHARACTER_DATA],
            locations=[TEST_REGION_DATA]
        )

        # 验证子系统初始化
        assert engine.time_system is not None
        assert engine.entity_system is not None
        assert engine.location_system is not None
        assert engine.event_system is not None
        assert engine.memory_system is not None

        # 测试时钟周期
        await engine.tick()
        assert engine.current_tick == 1

    @pytest.mark.asyncio
    async def test_world_simulation_lifecycle(self):
        """测试世界模拟生命周期"""
        engine = WorldSimulationEngine(TEST_WORLD_ID)

        # 初始化
        await engine.initialize(
            time_config={"time_scale": 1.0},
            entities=[TEST_CHARACTER_DATA],
            locations=[TEST_REGION_DATA]
        )

        # 启动模拟
        success = await engine.start_simulation()
        assert success
        assert engine.is_running
        assert engine.get_status().value == "running"

        # 等待几个时钟周期
        await asyncio.sleep(2)  # 等待2秒，应该执行2-3个时钟周期

        # 暂停模拟
        success = await engine.pause_simulation()
        assert success
        assert engine.is_paused

        # 恢复模拟
        success = await engine.resume_simulation()
        assert success
        assert not engine.is_paused

        # 停止模拟
        success = await engine.stop_simulation()
        assert success
        assert not engine.is_running

    @pytest.mark.asyncio
    async def test_integration_workflow(self):
        """测试完整的集成工作流"""
        # 1. 创建世界模拟引擎
        engine = WorldSimulationEngine(TEST_WORLD_ID)
        await engine.initialize(
            time_config={"time_scale": 2.0},
            entities=[TEST_CHARACTER_DATA],
            locations=[TEST_REGION_DATA]
        )

        # 2. 启动模拟
        await engine.start_simulation()

        # 3. 运行几个时钟周期
        await asyncio.sleep(1)

        # 4. 验证时间推进
        time_info = engine.get_time_system().get_time_info()
        assert time_info["tick_count"] > 0

        # 5. 验证实体行为
        entity_stats = engine.entity_system.get_statistics()
        assert entity_stats["total_entities"] > 0

        # 6. 验证位置系统
        location_stats = engine.location_system.get_location_statistics()
        assert location_stats["total_locations"] > 0

        # 7. 停止模拟
        await engine.stop_simulation()


if __name__ == "__main__":
    """运行测试"""
    pytest.main([__file__, "-v", "-s"])