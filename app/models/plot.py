"""
剧情与伏笔数据模型
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HookStatus(str, Enum):
    """伏笔状态"""

    PLANTED = "planted"  # 已埋设
    TRIGGERED = "triggered"  # 已触发
    RESOLVED = "resolved"  # 已回收
    DROPPED = "dropped"  # 已放弃


class HookType(str, Enum):
    """伏笔类型"""

    MYSTERY = "mystery"  # 谜团
    OBJECT = "object"  # 物品
    CHARACTER = "character"  # 角色相关
    EVENT = "event"  # 事件
    LOCATION = "location"  # 地点
    RELATIONSHIP = "relationship"  # 关系
    CUSTOM = "custom"  # 自定义


class Hook(BaseModel):
    """伏笔模型"""

    id: Optional[str] = Field(None, description="伏笔唯一 ID（创建时自动生成）")
    title: str = Field(..., description="伏笔标题")
    description: Optional[str] = Field(default="", description="伏笔描述")

    # 项目归属
    project_id: Optional[str] = Field(None, description="所属项目ID")
    world_id: Optional[str] = Field(None, description="所属世界ID")
    scope_type: str = Field(default="project", description="作用域：project/world/character/arc")
    character_id: Optional[str] = Field(None, description="人物级伏笔关联角色 ID")
    parent_hook_id: Optional[str] = Field(None, description="父级伏笔 ID")
    promoted_from_hook_id: Optional[str] = Field(None, description="提升来源伏笔 ID")
    visibility: str = Field(default="global", description="可见性：global/local")

    # 伏笔类型
    hook_type: HookType = Field(default=HookType.CUSTOM, description="伏笔类型")

    # 状态追踪
    status: HookStatus = Field(default=HookStatus.PLANTED, description="伏笔状态")

    # 关联信息
    related_characters: List[str] = Field(default_factory=list, description="相关角色 ID")
    related_locations: List[str] = Field(default_factory=list, description="相关地点 ID")
    related_objects: List[str] = Field(default_factory=list, description="相关物品 ID")

    # 内容
    plant_context: Optional[str] = Field(None, description="埋设时的情境")
    plant_chapter: Optional[str] = Field(None, description="埋设章节 ID")
    resolution_hint: Optional[str] = Field(None, description="回收提示（给作者看）")
    resolution_context: Optional[str] = Field(None, description="回收时的情境")
    resolution_chapter: Optional[str] = Field(None, description="回收章节 ID")

    # 优先级
    priority: int = Field(default=1, ge=1, le=5, description="优先级 1-5")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = Field(None, description="回收时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "hook_001",
                "title": "神秘的玉佩",
                "description": "主角随身携带的玉佩，似乎隐藏着身世秘密",
                "hook_type": "object",
                "status": "planted",
                "related_characters": ["char_001"],
                "plant_context": "主角整理遗物时发现玉佩背面有奇怪的纹路",
                "priority": 3,
            }
        }
    )


class EventType(str, Enum):
    """事件类型"""

    DIALOGUE = "dialogue"  # 对话
    ACTION = "action"  # 动作
    DISCOVERY = "discovery"  # 发现
    CONFLICT = "conflict"  # 冲突
    RESOLUTION = "resolution"  # 解决
    TRANSITION = "transition"  # 过渡
    CUSTOM = "custom"  # 自定义


class EventSummary(BaseModel):
    """事件摘要模型（由 Summarizer 生成）"""

    id: str = Field(..., description="事件摘要 ID")
    chapter_id: str = Field(..., description="所属章节 ID")

    # 事件内容
    summary: str = Field(..., description="事件摘要")
    event_type: EventType = Field(default=EventType.CUSTOM, description="事件类型")

    # 参与者
    participants: List[str] = Field(default_factory=list, description="参与角色 ID 列表")

    # 潜台词标记
    subtext_markers: List[Dict[str, str]] = Field(
        default_factory=list, description="潜台词标记"
    )

    # 伏笔触发
    hook_triggers: List[str] = Field(default_factory=list, description="触发的伏笔 ID")

    # 信息增量评分
    info_gain_score: float = Field(default=0.0, ge=0, le=1, description="信息增量评分")

    # 原始对话引用（如有潜台词）
    raw_dialogue_refs: List[str] = Field(default_factory=list, description="原始对话引用 ID")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    order: int = Field(default=0, description="在章节中的顺序")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "event_001",
                "chapter_id": "chapter_001",
                "summary": "张三试图套取李四的门派秘籍，但李四极其警惕并转移了话题",
                "event_type": "conflict",
                "participants": ["char_001", "char_002"],
                "subtext_markers": [
                    {
                        "speaker": "char_001",
                        "implied_meaning": "表面询问武功，实则想套取秘籍",
                    }
                ],
                "info_gain_score": 0.7,
            }
        }
    )


class ChapterStatus(str, Enum):
    """章节状态"""

    DRAFT = "draft"  # 草稿
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"  # 已完成
    ARCHIVED = "archived"  # 已归档


class Chapter(BaseModel):
    """章节模型"""

    id: str = Field(..., description="章节唯一 ID")
    title: str = Field(..., description="章节标题")

    # 项目归属
    project_id: Optional[str] = Field(None, description="所属项目ID")
    world_id: Optional[str] = Field(None, description="所属世界 ID")

    # 内容
    summary: Optional[str] = Field(None, description="章节摘要/期望内容")
    content: Optional[str] = Field(None, description="章节正文")
    word_count: int = Field(default=0, description="字数")

    # 状态
    status: ChapterStatus = Field(default=ChapterStatus.DRAFT, description="章节状态")

    # 剧情节点
    events: List[str] = Field(default_factory=list, description="事件摘要 ID 列表")

    # 伏笔追踪
    hooks_planted: List[str] = Field(default_factory=list, description="本章埋设的伏笔")
    hooks_resolved: List[str] = Field(default_factory=list, description="本章回收的伏笔")

    # 主线进度
    main_plot_progress: float = Field(default=0.0, ge=0, le=1, description="主线进度")

    # 评分
    reader_scores: Optional[Dict[str, float]] = Field(None, description="读者模拟评分")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "chapter_001",
                "title": "第一章：初入江湖",
                "world_id": "world_001",
                "status": "completed",
                "word_count": 3500,
                "hooks_planted": ["hook_001", "hook_002"],
                "main_plot_progress": 0.1,
            }
        }
    )


class CreateChapterDTO(BaseModel):
    """创建章节请求模型"""

    title: str = Field(..., description="章节标题")
    project_id: Optional[str] = Field(None, description="所属项目 ID")
    world_id: Optional[str] = Field(None, description="所属世界 ID")
    summary: Optional[str] = Field(None, description="章节摘要/期望内容")
    content: Optional[str] = Field(default="", description="章节正文")
    status: ChapterStatus = Field(default=ChapterStatus.DRAFT, description="章节状态")


class UpdateChapterDTO(BaseModel):
    """更新章节请求模型"""

    title: Optional[str] = Field(default=None, description="章节标题")
    world_id: Optional[str] = Field(default=None, description="所属世界 ID")
    summary: Optional[str] = Field(default=None, description="章节摘要/期望内容")
    content: Optional[str] = Field(default=None, description="章节正文")
    status: Optional[ChapterStatus] = Field(default=None, description="章节状态")


class Plot(BaseModel):
    """剧情模型（用于追踪整体剧情线）"""

    id: str = Field(..., description="剧情线 ID")
    title: str = Field(..., description="剧情线标题")

    # 项目归属
    project_id: Optional[str] = Field(None, description="所属项目ID")
    world_id: str = Field(..., description="所属世界 ID")

    # 剧情类型
    plot_type: str = Field(default="main", description="剧情类型：main/submission/character")

    # 描述
    description: Optional[str] = Field(None, description="剧情线描述")

    # 目标状态
    goals: List[str] = Field(default_factory=list, description="剧情目标列表")
    completed_goals: List[str] = Field(default_factory=list, description="已完成目标")

    # 关联章节
    chapters: List[str] = Field(default_factory=list, description="相关章节 ID 列表")

    # 关联角色
    characters: List[str] = Field(default_factory=list, description="主要角色 ID 列表")

    # 进度
    progress: float = Field(default=0.0, ge=0, le=1, description="剧情进度")
    status: str = Field(default="active", description="状态：active/completed/hiatus")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "plot_001",
                "title": "主角成长线",
                "world_id": "world_001",
                "plot_type": "main",
                "goals": ["获得第一本秘籍", "击败第一个强敌", "找到失散的师妹"],
                "progress": 0.33,
            }
        }
    )
