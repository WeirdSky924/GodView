"""
Agent 记忆模型 - Agent 的持久化记忆和状态

每个 Agent 都有自己的记忆存储，包括：
- 执行历史和决策记录
- 学到的知识和经验
- 对世界的理解和认知
- 与其他 Agent 的交互记录
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(str, Enum):
    """记忆类型"""

    OBSERVATION = "observation"      # 观察 - Agent 感知到的信息
    DECISION = "decision"            # 决策 - Agent 做出的选择
    ACTION = "action"                # 行动 - Agent 执行的操作
    LEARNING = "learning"            # 学习 - Agent 获得的知识
    REFLECTION = "reflection"        # 反思 - Agent 的自我分析
    INTERACTION = "interaction"      # 交互 - 与其他 Agent 的互动
    FEEDBACK = "feedback"            # 反馈 - 用户或系统的反馈


class MemoryImportance(str, Enum):
    """记忆重要性级别"""

    CRITICAL = "critical"    # 关键记忆，永不遗忘
    HIGH = "high"           # 重要记忆，长期保留
    MEDIUM = "medium"       # 普通记忆，中期保留
    LOW = "low"             # 次要记忆，可能被遗忘
    EPHEMERAL = "ephemeral" # 短期记忆，快速衰减


class MemoryEntry(BaseModel):
    """单条记忆"""

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.now)
    type: MemoryType = Field(..., description="记忆类型")
    importance: MemoryImportance = Field(
        default=MemoryImportance.MEDIUM, description="重要性"
    )

    # 记忆内容
    content: str = Field(..., description="记忆内容")
    summary: Optional[str] = Field(None, description="记忆摘要")

    # 上下文
    context: Dict[str, Any] = Field(
        default_factory=dict, description="记忆上下文"
    )
    tags: List[str] = Field(default_factory=list, description="标签")

    # 关联
    related_chapter: Optional[int] = Field(None, description="关联章节")
    related_characters: List[str] = Field(
        default_factory=list, description="关联角色"
    )
    related_events: List[str] = Field(
        default_factory=list, description="关联事件"
    )

    # 访问统计（用于遗忘机制）
    access_count: int = Field(default=0, description="访问次数")
    last_accessed: Optional[datetime] = Field(None, description="最后访问时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "mem_001",
                "timestamp": "2024-01-15T10:30:00",
                "type": "decision",
                "importance": "high",
                "content": "决定在第三章引入神秘商人角色，为后续剧情埋下伏笔",
                "summary": "引入神秘商人伏笔",
                "context": {
                    "chapter": 3,
                    "plot_direction": "悬念构建"
                },
                "tags": ["伏笔", "神秘商人", "第三章"],
                "related_chapter": 3,
                "related_characters": ["神秘商人"],
            }
        }
    )


class AgentKnowledge(BaseModel):
    """Agent 知识库 - 结构化的知识存储"""

    # 世界认知
    world_understanding: Dict[str, Any] = Field(
        default_factory=dict, description="对世界的理解"
    )

    # 角色认知
    character_knowledge: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="对角色的认知"
    )

    # 剧情认知
    plot_understanding: Dict[str, Any] = Field(
        default_factory=dict, description="对剧情的理解"
    )

    # 技能和经验
    learned_skills: List[str] = Field(
        default_factory=list, description="学到的技能"
    )
    experience_points: Dict[str, int] = Field(
        default_factory=dict, description="经验值（按领域）"
    )

    # 偏好设置（可以从用户输入学习）
    preferences: Dict[str, Any] = Field(
        default_factory=dict, description="Agent 偏好"
    )

    # 自我认知
    self_awareness: Dict[str, Any] = Field(
        default_factory=dict, description="自我认知"
    )


class AgentMemory(BaseModel):
    """Agent 完整记忆"""

    id: str = Field(default_factory=lambda: f"memory_{uuid4().hex[:8]}")
    project_id: str = Field(..., description="所属项目")
    agent_type: str = Field(..., description="Agent 类型")
    agent_id: Optional[str] = Field(None, description="Agent 实例 ID（区分同类型多实例）")

    # 记忆存储
    memories: List[MemoryEntry] = Field(
        default_factory=list, description="记忆条目列表"
    )
    knowledge: AgentKnowledge = Field(
        default_factory=AgentKnowledge, description="知识库"
    )

    # 工作记忆（短期）
    working_memory: Dict[str, Any] = Field(
        default_factory=dict, description="当前工作记忆"
    )

    # 统计信息
    total_memories: int = Field(default=0, description="总记忆数量")
    last_execution: Optional[datetime] = Field(None, description="最后执行时间")
    execution_count: int = Field(default=0, description="执行次数")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "memory_abc123",
                "project_id": "proj_001",
                "agent_type": "master_plotter",
                "memories": [
                    {
                        "type": "decision",
                        "importance": "high",
                        "content": "决定主线剧情走向为悬疑解谜",
                        "tags": ["主线", "悬疑"]
                    }
                ],
                "knowledge": {
                    "world_understanding": {
                        "main_theme": "赛博朋克与神秘学的融合"
                    }
                }
            }
        }
    )

    def add_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.OBSERVATION,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        tags: List[str] = None,
        context: Dict[str, Any] = None,
    ) -> MemoryEntry:
        """添加新记忆"""
        entry = MemoryEntry(
            type=memory_type,
            importance=importance,
            content=content,
            tags=tags or [],
            context=context or {},
        )
        self.memories.append(entry)
        self.total_memories = len(self.memories)
        self.updated_at = datetime.now()
        return entry

    def get_recent_memories(self, limit: int = 10) -> List[MemoryEntry]:
        """获取最近记忆"""
        return sorted(self.memories, key=lambda m: m.timestamp, reverse=True)[:limit]

    def get_memories_by_type(self, memory_type: MemoryType) -> List[MemoryEntry]:
        """按类型获取记忆"""
        return [m for m in self.memories if m.type == memory_type]

    def get_memories_by_tags(self, tags: List[str]) -> List[MemoryEntry]:
        """按标签获取记忆"""
        result = []
        for memory in self.memories:
            if any(tag in memory.tags for tag in tags):
                result.append(memory)
        return result

    def get_important_memories(self) -> List[MemoryEntry]:
        """获取重要记忆"""
        important_levels = {MemoryImportance.CRITICAL, MemoryImportance.HIGH}
        return [m for m in self.memories if m.importance in important_levels]

    def clear_ephemeral_memories(self, max_age_hours: int = 24):
        """清理短期记忆"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        self.memories = [
            m
            for m in self.memories
            if m.importance != MemoryImportance.EPHEMERAL or m.timestamp > cutoff
        ]
        self.total_memories = len(self.memories)


class AgentMemoryCreate(BaseModel):
    """创建 Agent 记忆请求"""

    project_id: str
    agent_type: str
    agent_id: Optional[str] = None
    initial_knowledge: Optional[Dict[str, Any]] = None


class MemoryEntryCreate(BaseModel):
    """创建记忆条目请求"""

    type: MemoryType
    importance: MemoryImportance = MemoryImportance.MEDIUM
    content: str
    tags: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    related_chapter: Optional[int] = None
    related_characters: List[str] = Field(default_factory=list)
