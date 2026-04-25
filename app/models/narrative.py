"""
动态剧情 (Narrative) 数据模型
用于存储剧情发展、角色状态变化等"现在进行时"信息
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NarrativeEntryType(str, Enum):
    """叙事条目类型"""

    EVENT = "event"  # 事件
    DIALOGUE = "dialogue"  # 对话
    ACTION = "action"  # 动作
    STATE_CHANGE = "state_change"  # 状态变化
    RELATIONSHIP_CHANGE = "relationship_change"  # 关系变化
    DISCOVERY = "discovery"  # 发现
    CONFLICT = "conflict"  # 冲突
    RESOLUTION = "resolution"  # 解决
    TRANSITION = "transition"  # 过渡


class TemporalScope(str, Enum):
    """时间范围"""

    PAST = "past"  # 已发生的过去
    PRESENT = "present"  # 当前正在发生
    IMMEDIATE_FUTURE = "immediate_future"  # 即将发生（伏笔）
    FUTURE = "future"  # 未来计划


class NarrativeEntry(BaseModel):
    """叙事条目模型"""

    id: str = Field(..., description="叙事唯一 ID")
    project_id: str = Field(..., description="所属项目 ID")
    chapter_id: Optional[str] = Field(None, description="所属章节 ID")

    # 条目类型
    entry_type: NarrativeEntryType = Field(default=NarrativeEntryType.EVENT, description="条目类型")
    temporal_scope: TemporalScope = Field(default=TemporalScope.PRESENT, description="时间范围")

    # 内容
    title: str = Field(..., description="叙事标题")
    summary: str = Field(..., description="叙事摘要")
    content: Optional[str] = Field(None, description="详细内容")

    # 参与者
    participants: List[str] = Field(default_factory=list, description="参与角色 ID 列表")
    primary_character: Optional[str] = Field(None, description="主要角色 ID")

    # 地点和时间
    location_id: Optional[str] = Field(None, description="发生地点 ID")
    narrative_time: Optional[str] = Field(None, description="剧情内时间")

    # 关联信息
    related_hooks: List[str] = Field(default_factory=list, description="相关伏笔 ID")
    related_events: List[str] = Field(default_factory=list, description="相关事件 ID")
    caused_by: Optional[str] = Field(None, description="起因事件 ID")
    leads_to: List[str] = Field(default_factory=list, description="导致的事件 ID")

    # 状态变化
    state_changes: List[Dict[str, Any]] = Field(default_factory=list, description="状态变化记录")

    # 重要性
    importance: float = Field(default=0.5, ge=0, le=1, description="重要程度 0-1")
    emotional_intensity: float = Field(default=0.5, ge=0, le=1, description="情感强度 0-1")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    embedding_id: Optional[str] = Field(None, description="Qdrant 向量 ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "narr_001",
                "project_id": "proj_001",
                "chapter_id": "chap_001",
                "entry_type": "event",
                "temporal_scope": "present",
                "title": "主角与反派首次交锋",
                "summary": "张三在客栈遭遇李四，双方发生冲突",
                "participants": ["char_001", "char_002"],
                "location_id": "region_001",
                "importance": 0.8,
                "emotional_intensity": 0.7,
            }
        }
    )


class CharacterState(BaseModel):
    """角色状态模型（记录角色在某个时间点的状态）"""

    id: str = Field(..., description="状态记录 ID")
    character_id: str = Field(..., description="角色 ID")
    project_id: str = Field(..., description="所属项目 ID")

    # 时间点
    chapter_id: Optional[str] = Field(None, description="所在章节 ID")
    narrative_time: Optional[str] = Field(None, description="剧情内时间")
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    # 物理状态
    health: float = Field(default=100, ge=0, le=100, description="生命值")
    energy: float = Field(default=100, ge=0, le=100, description="精力值")
    location_id: Optional[str] = Field(None, description="当前位置 ID")

    # 心理状态
    mood: Optional[str] = Field(None, description="当前情绪")
    mental_state: Optional[str] = Field(None, description="心理状态")
    current_goals: List[str] = Field(default_factory=list, description="当前目标")

    # 属性变化
    attribute_changes: Dict[str, Any] = Field(default_factory=dict, description="属性变化")

    # 关系状态
    relationship_states: Dict[str, float] = Field(default_factory=dict, description="关系状态映射")

    # 装备和物品
    inventory: List[str] = Field(default_factory=list, description="物品清单")
    equipped_items: List[str] = Field(default_factory=list, description="装备物品")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "state_001",
                "character_id": "char_001",
                "project_id": "proj_001",
                "chapter_id": "chap_003",
                "health": 85,
                "energy": 70,
                "mood": "警惕",
                "current_goals": ["找到失踪的师妹"],
                "relationship_states": {"char_002": -0.3},
            }
        }
    )


class WorldSnapshot(BaseModel):
    """世界快照模型（记录世界在某个时间点的整体状态）"""

    id: str = Field(..., description="快照唯一 ID")
    project_id: str = Field(..., description="所属项目 ID")
    world_id: str = Field(..., description="世界 ID")

    # 时间点
    chapter_id: Optional[str] = Field(None, description="所在章节 ID")
    narrative_time: Optional[str] = Field(None, description="剧情内时间")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 快照类型
    snapshot_type: str = Field(default="auto", description="快照类型：auto/manual/milestone")
    name: Optional[str] = Field(None, description="快照名称")
    description: Optional[str] = Field(None, description="快照描述")

    # 角色状态汇总
    character_states: Dict[str, CharacterState] = Field(
        default_factory=dict, description="角色状态映射"
    )

    # 关系网络
    relationships: Dict[str, Dict[str, float]] = Field(
        default_factory=dict, description="关系网络"
    )

    # 伏笔状态
    hooks_planted: List[str] = Field(default_factory=list, description="已埋设伏笔")
    hooks_triggered: List[str] = Field(default_factory=list, description="已触发伏笔")
    hooks_resolved: List[str] = Field(default_factory=list, description="已回收伏笔")

    # 剧情进度
    main_plot_progress: float = Field(default=0.0, ge=0, le=1, description="主线进度")
    completed_events: List[str] = Field(default_factory=list, description="已完成事件")

    # 关键状态
    key_decisions: List[Dict[str, Any]] = Field(default_factory=list, description="关键决策")
    world_events: List[str] = Field(default_factory=list, description="世界级事件")

    # 分支信息
    parent_snapshot_id: Optional[str] = Field(None, description="父快照 ID")
    is_branch: bool = Field(default=False, description="是否为分支")
    branch_reason: Optional[str] = Field(None, description="分支原因")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "snap_001",
                "project_id": "proj_001",
                "world_id": "world_001",
                "chapter_id": "chap_005",
                "snapshot_type": "milestone",
                "name": "第一卷完结",
                "main_plot_progress": 0.25,
                "hooks_planted": ["hook_001", "hook_002"],
            }
        }
    )


class NarrativeContext(BaseModel):
    """叙事上下文模型（用于生成时提供上下文）"""

    project_id: str = Field(..., description="项目 ID")

    # 静态设定上下文
    relevant_lore: List[Dict[str, Any]] = Field(default_factory=list, description="相关设定")

    # 动态剧情上下文
    recent_events: List[NarrativeEntry] = Field(default_factory=list, description="最近事件")
    character_states: Dict[str, CharacterState] = Field(default_factory=dict, description="角色状态")
    active_hooks: List[str] = Field(default_factory=list, description="活跃伏笔")

    # 关系上下文
    relevant_relationships: Dict[str, Dict[str, float]] = Field(
        default_factory=dict, description="相关关系"
    )

    # 生成提示
    focus_characters: List[str] = Field(default_factory=list, description="焦点角色")
    current_location: Optional[str] = Field(None, description="当前位置")
    narrative_goals: List[str] = Field(default_factory=list, description="叙事目标")


class NarrativeSearchResult(BaseModel):
    """叙事搜索结果模型"""

    id: str = Field(..., description="叙事 ID")
    title: str = Field(..., description="叙事标题")
    entry_type: NarrativeEntryType = Field(..., description="条目类型")
    summary: str = Field(..., description="叙事摘要")
    chapter_id: Optional[str] = Field(None, description="所属章节")
    score: float = Field(..., description="相关性分数")
    participants: List[str] = Field(default_factory=list, description="参与角色")
    created_at: datetime = Field(default_factory=datetime.utcnow)
