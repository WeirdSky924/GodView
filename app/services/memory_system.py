"""
增强记忆系统 - GodView v5 核心组件
实现四层记忆架构：短期、中期、长期、程序性记忆
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import random


class MemoryType(Enum):
    """记忆类型"""
    WORKING = "working"       # 工作记忆（短期）
    EPISODIC = "episodic"     # 情节记忆（中期）
    SEMANTIC = "semantic"      # 语义记忆（长期）
    PROCEDURAL = "procedural"  # 程序性记忆（行为模式）


class MemoryImportance(Enum):
    """记忆重要性"""
    CRITICAL = "critical"    # 关键记忆
    HIGH = "high"            # 高重要性
    MEDIUM = "medium"        # 中等重要性
    LOW = "low"              # 低重要性


@dataclass
class Memory:
    """记忆基类"""
    memory_id: str
    character_id: str
    memory_type: MemoryType
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # 重要性评估
    importance: float = 0.5  # 0.0-1.0
    importance_level: MemoryImportance = MemoryImportance.MEDIUM

    # 情感相关
    emotional_intensity: float = 0.5  # 0.0-1.0
    valence: float = 0.5  # 0.0（负面）-1.0（正面）

    # 访问相关
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    # 关联信息
    related_entities: List[str] = field(default_factory=list)
    related_locations: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # 记忆强度和衰减
    strength: float = 1.0  # 0.0-1.0
    decay_rate: float = 0.1  # 衰减率

    def is_expired(self) -> bool:
        """检查记忆是否过期"""
        if self.strength <= 0.1:
            return True

        # 时间衰减
        time_since_creation = datetime.utcnow() - self.timestamp
        max_lifetime = {
            MemoryType.WORKING: timedelta(hours=1),
            MemoryType.EPISODIC: timedelta(days=7),
            MemoryType.SEMANTIC: timedelta(days=30),
            MemoryType.PROCEDURAL: timedelta(days=90)
        }.get(self.memory_type, timedelta(days=7))

        return time_since_creation > max_lifetime

    def access(self):
        """访问记忆"""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
        # 访问增强记忆强度
        self.strength = min(1.0, self.strength + 0.1)

    def decay(self, delta: timedelta):
        """记忆衰减"""
        # 根据衰减率减少强度
        decay_amount = self.decay_rate * (delta.total_seconds() / 3600)  # 每小时衰减
        self.strength = max(0.0, self.strength - decay_amount)


class WorkingMemory:
    """工作记忆（短期记忆）"""

    def __init__(self, capacity: int = 7):
        self.capacity = capacity
        self.memories: List[Memory] = []
        self.logger = logging.getLogger(__name__)

    def add(self, character_id: str, content: str, metadata: Dict[str, Any] = None) -> Optional[Memory]:
        """添加工作记忆"""
        memory = Memory(
            memory_id=f"working_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}",
            character_id=character_id,
            memory_type=MemoryType.WORKING,
            content=content,
            importance=0.3,  # 工作记忆默认低重要性
            decay_rate=0.5  # 工作记忆快速衰减
        )

        # 添加元数据
        if metadata:
            if "emotional_intensity" in metadata:
                memory.emotional_intensity = metadata["emotional_intensity"]
            if "valence" in metadata:
                memory.valence = metadata["valence"]
            if "related_entities" in metadata:
                memory.related_entities = metadata["related_entities"]
            if "related_locations" in metadata:
                memory.related_locations = metadata["related_locations"]

        # 如果容量已满，移除最旧的记忆
        if len(self.memories) >= self.capacity:
            self.memories.pop(0)

        self.memories.append(memory)
        return memory

    def get_recent(self, character_id: str, limit: int = 5) -> List[Memory]:
        """获取最近的记忆"""
        character_memories = [
            m for m in self.memories
            if m.character_id == character_id
        ]
        return character_memories[-limit:]

    def clear(self):
        """清空工作记忆"""
        self.memories.clear()

    def update_all(self, delta: timedelta):
        """更新所有工作记忆"""
        for memory in self.memories[:]:
            memory.decay(delta)
            if memory.is_expired():
                self.memories.remove(memory)


class EpisodicMemory:
    """情节记忆（中期记忆）"""

    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.memories: Dict[str, List[Memory]] = {}  # character_id -> memories
        self.logger = logging.getLogger(__name__)

    def add(self, character_id: str, memory: Memory):
        """添加情节记忆"""
        memory.memory_type = MemoryType.EPISODIC
        memory.decay_rate = 0.2  # 中等衰减率

        if character_id not in self.memories:
            self.memories[character_id] = []

        # 如果容量已满，移除最弱/最旧的记忆
        if len(self.memories[character_id]) >= self.capacity:
            # 按重要性排序，移除最不重要的
            self.memories[character_id].sort(key=lambda m: m.importance)
            self.memories[character_id].pop(0)

        self.memories[character_id].append(memory)

    async def get_relevant(self, character_id: str, context: str) -> List[Memory]:
        """获取相关记忆"""
        if character_id not in self.memories:
            return []

        character_memories = self.memories[character_id]

        # 简单的关键词匹配（实际实现应该使用向量相似度）
        context_words = set(context.lower().split())

        relevant_memories = []
        for memory in character_memories:
            memory_words = set(memory.content.lower().split())
            overlap = len(context_words & memory_words)

            if overlap > 0:
                # 计算相关性得分
                relevance_score = overlap / len(context_words)
                relevant_memories.append((memory, relevance_score))

        # 按相关性排序
        relevant_memories.sort(key=lambda x: x[1], reverse=True)

        # 返回前5个最相关的
        return [memory for memory, _ in relevant_memories[:5]]

    def update_all(self, delta: timedelta):
        """更新所有情节记忆"""
        for character_id, memories in self.memories.items():
            for memory in memories[:]:
                memory.decay(delta)
                if memory.is_expired():
                    memories.remove(memory)


class KnowledgeGraph:
    """知识图谱（长期记忆）"""

    def __init__(self, nebula_db=None, qdrant_db=None):
        self.nebula_db = nebula_db
        self.qdrant_db = qdrant_db
        self.logger = logging.getLogger(__name__)

    async def add_memory(self, character_id: str, memory: Memory, qdrant_db=None):
        """添加长期记忆"""
        memory.memory_type = MemoryType.SEMANTIC
        memory.decay_rate = 0.05  # 长期记忆缓慢衰减

        # 存储到向量数据库
        if qdrant_db:
            try:
                # 创建文档用于向量存储
                document = {
                    "character_id": character_id,
                    "memory_id": memory.memory_id,
                    "content": memory.content,
                    "importance": memory.importance,
                    "emotional_intensity": memory.emotional_intensity,
                    "valence": memory.valence,
                    "related_entities": memory.related_entities,
                    "related_locations": memory.related_locations,
                    "tags": memory.tags,
                    "timestamp": memory.timestamp.isoformat()
                }

                # 存储到Qdrant
                await qdrant_db.add_memory(document)

                self.logger.info(f"添加长期记忆: {character_id} - {memory.content[:50]}...")

            except Exception as e:
                self.logger.error(f"添加长期记忆失败: {e}")

    async def semantic_search(
        self,
        character_id: str,
        query: str,
        limit: int = 5,
        qdrant_db=None
    ) -> List[Memory]:
        """语义搜索"""
        if not qdrant_db:
            return []

        try:
            # 执行向量搜索
            results = await qdrant_db.search_memories(
                character_id=character_id,
                query=query,
                limit=limit
            )

            # 转换为Memory对象
            memories = []
            for result in results:
                memory = Memory(
                    memory_id=result.get("memory_id", ""),
                    character_id=character_id,
                    memory_type=MemoryType.SEMANTIC,
                    content=result.get("content", ""),
                    timestamp=datetime.fromisoformat(result.get("timestamp", datetime.utcnow().isoformat())),
                    importance=result.get("importance", 0.5),
                    emotional_intensity=result.get("emotional_intensity", 0.5),
                    valence=result.get("valence", 0.5),
                    related_entities=result.get("related_entities", []),
                    related_locations=result.get("related_locations", []),
                    tags=result.get("tags", [])
                )

                memories.append(memory)

            return memories

        except Exception as e:
            self.logger.error(f"语义搜索失败: {e}")
            return []


class ProceduralMemory:
    """程序性记忆（行为模式）"""

    def __init__(self):
        self.behavior_patterns: Dict[str, List[Dict[str, Any]]] = {}  # character_id -> patterns
        self.logger = logging.getLogger(__name__)

    def add_behavior_pattern(
        self,
        character_id: str,
        pattern_type: str,
        pattern_data: Dict[str, Any]
    ):
        """添加行为模式"""
        if character_id not in self.behavior_patterns:
            self.behavior_patterns[character_id] = []

        pattern = {
            "pattern_type": pattern_type,
            "data": pattern_data,
            "frequency": 1,
            "success_rate": 0.5,  # 0.0-1.0
            "last_used": datetime.utcnow()
        }

        # 检查是否已有类似模式
        existing_patterns = [
            p for p in self.behavior_patterns[character_id]
            if p["pattern_type"] == pattern_type
        ]

        if existing_patterns:
            # 更新现有模式
            existing_pattern = existing_patterns[0]
            existing_pattern["frequency"] += 1
            existing_pattern["data"] = pattern_data
            existing_pattern["last_used"] = datetime.utcnow()
        else:
            # 添加新模式
            self.behavior_patterns[character_id].append(pattern)

    def get_relevant_patterns(
        self,
        character_id: str,
        context: str
    ) -> List[Dict[str, Any]]:
        """获取相关行为模式"""
        if character_id not in self.behavior_patterns:
            return []

        # 按频率和成功率排序
        patterns = self.behavior_patterns[character_id]
        sorted_patterns = sorted(
            patterns,
            key=lambda p: (p["frequency"] * p["success_rate"]),
            reverse=True
        )

        return sorted_patterns[:5]

    def update_pattern_success(self, character_id: str, pattern_type: str, success: bool):
        """更新模式成功率"""
        if character_id not in self.behavior_patterns:
            return

        for pattern in self.behavior_patterns[character_id]:
            if pattern["pattern_type"] == pattern_type:
                # 更新成功率
                current_rate = pattern["success_rate"]
                if success:
                    pattern["success_rate"] = min(1.0, current_rate + 0.1)
                else:
                    pattern["success_rate"] = max(0.0, current_rate - 0.1)

                pattern["last_used"] = datetime.utcnow()
                break


class EnhancedMemorySystem:
    """增强记忆系统

    实现四层记忆架构，支持记忆的添加、检索、更新和衰减
    """

    def __init__(self, qdrant_db=None, nebula_db=None):
        # 四层记忆架构
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = KnowledgeGraph(nebula_db, qdrant_db)
        self.procedural = ProceduralMemory()

        # 向量数据库引用
        self.qdrant_db = qdrant_db

        # 记忆统计
        self.memory_stats: Dict[str, Any] = {
            "total_memories": 0,
            "memories_by_type": {},
            "memories_by_character": {}
        }

        self.logger = logging.getLogger(__name__)

    async def add_memory(
        self,
        character_id: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> Memory:
        """添加记忆

        这是记忆系统的核心方法，根据重要性自动分发到不同的记忆层
        """
        # 1. 添加到工作记忆
        working_memory = self.working.add(character_id, content, metadata)

        # 2. 计算重要性
        importance = await self._calculate_importance(working_memory, metadata or {})

        working_memory.importance = importance
        working_memory.importance_level = self._get_importance_level(importance)

        # 3. 根据重要性决定存储到其他层
        if importance > 0.3:
            # 添加到情节记忆
            self.episodic.add(character_id, working_memory)

        if importance > 0.7:
            # 添加到长期记忆
            await self.semantic.add_memory(character_id, working_memory, self.qdrant_db)

        # 4. 更新统计
        self._update_statistics(working_memory)

        self.logger.info(f"添加记忆: {character_id} - 重要性: {importance:.2f}")

        return working_memory

    async def retrieve_relevant_memories(
        self,
        character_id: str,
        context: str,
        limit: int = 5
    ) -> List[Memory]:
        """检索相关记忆

        从所有记忆层中检索相关记忆并合并
        """
        # 1. 从工作记忆获取
        working_memories = self.working.get_recent(character_id, limit)

        # 2. 从情节记忆获取
        episodic_memories = await self.episodic.get_relevant(character_id, context)

        # 3. 从长期记忆向量检索
        semantic_memories = await self.semantic.semantic_search(
            character_id, context, limit, self.qdrant_db
        )

        # 4. 合并并去重
        all_memories = working_memories + episodic_memories + semantic_memories

        # 5. 按重要性和时间排序
        all_memories.sort(key=lambda m: (m.importance, m.timestamp), reverse=True)

        # 6. 返回前N个最相关的
        relevant_memories = all_memories[:limit]

        # 7. 更新访问统计
        for memory in relevant_memories:
            memory.access()

        return relevant_memories

    async def _calculate_importance(self, memory: Memory, metadata: Dict[str, Any]) -> float:
        """计算记忆重要性"""
        # 基础重要性
        factors = {
            "emotional_intensity": memory.emotional_intensity,
            "novelty": await self._calculate_novelty(memory, metadata),
            "relevance": await self._calculate_relevance(memory, metadata),
            "frequency": metadata.get("frequency", 0.5),  # 发生频率
            "surprise": metadata.get("surprise", 0.5),  # 意外程度
            "personal_significance": metadata.get("personal_significance", 0.5)  # 个人意义
        }

        # 加权平均
        weights = {
            "emotional_intensity": 0.2,
            "novelty": 0.25,
            "relevance": 0.25,
            "frequency": 0.1,
            "surprise": 0.1,
            "personal_significance": 0.1
        }

        total_importance = sum(factors[key] * weights[key] for key in factors)

        return max(0.0, min(1.0, total_importance))

    async def _calculate_novelty(self, memory: Memory, metadata: Dict[str, Any]) -> float:
        """计算新颖性"""
        # 简化实现：基于相关实体的新颖性
        # 实际实现应该检查记忆相似度

        related_entities_count = len(memory.related_entities)
        novelty = 1.0 - min(1.0, related_entities_count / 10.0)

        return novelty

    async def _calculate_relevance(self, memory: Memory, metadata: Dict[str, Any]) -> float:
        """计算相关性"""
        # 简化实现：基于时间和上下文的相关性
        recency_factor = 1.0  # 新近度因子

        # 越近的记忆越相关
        time_since_creation = datetime.utcnow() - memory.timestamp
        hours_elapsed = time_since_creation.total_seconds() / 3600

        if hours_elapsed < 1:
            recency_factor = 1.0
        elif hours_elapsed < 24:
            recency_factor = 0.8
        elif hours_elapsed < 168:  # 1周
            recency_factor = 0.6
        else:
            recency_factor = 0.4

        return recency_factor

    def _get_importance_level(self, importance: float) -> MemoryImportance:
        """获取重要性等级"""
        if importance >= 0.8:
            return MemoryImportance.CRITICAL
        elif importance >= 0.6:
            return MemoryImportance.HIGH
        elif importance >= 0.4:
            return MemoryImportance.MEDIUM
        else:
            return MemoryImportance.LOW

    async def update_decay(self, delta: timedelta):
        """更新记忆衰减"""
        # 更新工作记忆
        self.working.update_all(delta)

        # 更新情节记忆
        self.episodic.update_all(delta)

        # 长期记忆和程序性记忆不随时间快速衰减

    def add_behavior_pattern(
        self,
        character_id: str,
        pattern_type: str,
        pattern_data: Dict[str, Any]
    ):
        """添加行为模式到程序性记忆"""
        self.procedural.add_behavior_pattern(character_id, pattern_type, pattern_data)

    def get_behavior_patterns(
        self,
        character_id: str,
        context: str
    ) -> List[Dict[str, Any]]:
        """获取相关行为模式"""
        return self.procedural.get_relevant_patterns(character_id, context)

    def update_pattern_success(self, character_id: str, pattern_type: str, success: bool):
        """更新行为模式成功率"""
        self.procedural.update_pattern_success(character_id, pattern_type, success)

    def _update_statistics(self, memory: Memory):
        """更新统计信息"""
        self.memory_stats["total_memories"] += 1

        memory_type = memory.memory_type.value
        self.memory_stats["memories_by_type"][memory_type] = (
            self.memory_stats["memories_by_type"].get(memory_type, 0) + 1
        )

        character_id = memory.character_id
        self.memory_stats["memories_by_character"][character_id] = (
            self.memory_stats["memories_by_character"].get(character_id, 0) + 1
        )

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.memory_stats,
            "working_memory_size": len(self.working.memories),
            "episodic_memory_size": sum(
                len(memories) for memories in self.episodic.memories.values()
            ),
            "procedural_memory_size": sum(
                len(patterns) for patterns in self.procedural.behavior_patterns.values()
            )
        }

    def get_character_memories(
        self,
        character_id: str,
        memory_types: List[MemoryType] = None
    ) -> List[Memory]:
        """获取角色的所有记忆"""
        memories = []

        if not memory_types or MemoryType.WORKING in memory_types:
            memories.extend(self.working.get_recent(character_id, limit=100))

        if not memory_types or MemoryType.EPISODIC in memory_types:
            if character_id in self.episodic.memories:
                memories.extend(self.episodic.memories[character_id])

        return memories

    def clear_character_memory(self, character_id: str, memory_type: MemoryType = None):
        """清除角色的记忆"""
        if memory_type == MemoryType.WORKING or memory_type is None:
            # 清除工作记忆
            self.working.memories = [
                m for m in self.working.memories
                if m.character_id != character_id
            ]

        if memory_type == MemoryType.EPISODIC or memory_type is None:
            # 清除情节记忆
            if character_id in self.episodic.memories:
                del self.episodic.memories[character_id]