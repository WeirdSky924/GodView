"""
记忆数据模型
GodView v9: 长篇记忆架构

用于存储和管理长篇小说创作中的关键信息记忆
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class MemoryType(str, Enum):
    """记忆类型枚举"""

    SHORT_TERM = "short_term"    # 短期记忆（当前章节相关）
    MEDIUM_TERM = "medium_term"  # 中期记忆（最近几章）
    LONG_TERM = "long_term"      # 长期记忆（永久重要信息）


class MemoryCategory(str, Enum):
    """记忆分类"""

    CHARACTER = "character"      # 角色相关
    EVENT = "event"              # 事件相关
    SETTING = "setting"          # 设定相关
    RELATIONSHIP = "relationship"  # 关系相关
    FORESHADOWING = "foreshadowing"  # 伏笔相关
    PLOT = "plot"                # 剧情相关
    WORLD = "world"              # 世界观相关


class MemoryEntry(BaseModel):
    """记忆条目模型"""

    id: str = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")

    # 记忆类型
    memory_type: MemoryType = Field(default=MemoryType.MEDIUM_TERM, description="记忆类型")
    category: MemoryCategory = Field(default=MemoryCategory.EVENT, description="记忆分类")

    # 内容
    content: str = Field(..., description="记忆内容")
    summary: Optional[str] = Field(None, description="记忆摘要")

    # 关联信息
    chapter_number: Optional[int] = Field(None, description="相关章节号")
    character_ids: List[str] = Field(default_factory=list, description="关联角色ID")
    event_ids: List[str] = Field(default_factory=list, description="关联事件ID")
    location_ids: List[str] = Field(default_factory=list, description="关联地点ID")

    # 向量嵌入
    embedding: Optional[List[float]] = Field(None, description="向量嵌入")

    # 重要性
    importance_score: float = Field(default=0.5, ge=0, le=1, description="重要性分数")

    # 访问统计
    access_count: int = Field(default=0, description="访问次数")
    last_accessed_at: Optional[datetime] = Field(None, description="最后访问时间")

    # 时效性
    expires_at: Optional[datetime] = Field(None, description="过期时间（短期记忆）")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 来源
    source_type: Optional[str] = Field(None, description="来源类型（summary/analysis/manual）")
    source_agent: Optional[str] = Field(None, description="来源 Agent")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "mem_abc123",
                "project_id": "proj_001",
                "memory_type": "medium_term",
                "category": "character",
                "content": "张三在第三章获得了神秘玉佩，玉佩背面有奇怪的纹路",
                "summary": "张三获得玉佩",
                "chapter_number": 3,
                "character_ids": ["char_001"],
                "importance_score": 0.7,
                "source_type": "summary",
            }
        }
    )


class MemorySnapshot(BaseModel):
    """记忆快照模型"""

    id: str = Field(default_factory=lambda: f"snap_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节号")

    # 快照内容
    character_states: Dict[str, Any] = Field(default_factory=dict, description="角色状态汇总")
    active_hooks: List[Dict[str, Any]] = Field(default_factory=list, description="活跃伏笔")
    recent_events: List[str] = Field(default_factory=list, description="最近事件")
    world_state: Dict[str, Any] = Field(default_factory=dict, description="世界状态")

    # 关键信息
    key_memories: List[str] = Field(default_factory=list, description="关键记忆ID列表")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "snap_xyz789",
                "project_id": "proj_001",
                "chapter_number": 10,
                "character_states": {
                    "char_001": {"location": "青云宗", "status": "修炼中", "power_level": "筑基期"}
                },
                "active_hooks": ["hook_001", "hook_002"],
                "recent_events": ["张三突破筑基期", "李四离开宗门"],
            }
        }
    )


class CharacterMemoryState(BaseModel):
    """角色记忆状态"""

    character_id: str
    character_name: str

    # 位置状态
    current_location: Optional[str] = None
    last_seen_chapter: Optional[int] = None

    # 关系状态
    relationships: Dict[str, str] = Field(default_factory=dict, description="与其他角色的关系")

    # 状态变化
    status_changes: List[Dict[str, Any]] = Field(default_factory=list, description="状态变化记录")

    # 重要事件
    key_events: List[str] = Field(default_factory=list, description="参与的重要事件")

    # 记忆要点
    memory_points: List[str] = Field(default_factory=list, description="需要记住的要点")


# ==================== DTO 模型 ====================

class CreateMemoryDTO(BaseModel):
    """创建记忆请求"""

    project_id: str
    memory_type: MemoryType = MemoryType.MEDIUM_TERM
    category: MemoryCategory = MemoryCategory.EVENT
    content: str
    summary: Optional[str] = None
    chapter_number: Optional[int] = None
    character_ids: List[str] = Field(default_factory=list)
    importance_score: float = 0.5


class UpdateMemoryDTO(BaseModel):
    """更新记忆请求"""

    content: Optional[str] = None
    summary: Optional[str] = None
    importance_score: Optional[float] = None
    memory_type: Optional[MemoryType] = None


class SearchMemoryDTO(BaseModel):
    """搜索记忆请求"""

    project_id: str
    query: str
    memory_types: Optional[List[MemoryType]] = None
    categories: Optional[List[MemoryCategory]] = None
    chapter_range: Optional[tuple] = None
    character_ids: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=50)


class MemorySearchResult(BaseModel):
    """记忆搜索结果"""

    memory: MemoryEntry
    relevance_score: float


class BuildSnapshotDTO(BaseModel):
    """构建快照请求"""

    project_id: str
    chapter_number: int
    include_long_term: bool = True
    include_medium_term: bool = True
    medium_term_chapters: int = Field(default=5, description="中期记忆包含的章节数")


class GetSnapshotDTO(BaseModel):
    """获取快照请求"""

    project_id: str
    chapter_number: Optional[int] = None
