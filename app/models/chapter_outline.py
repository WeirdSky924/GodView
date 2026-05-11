"""
章节大纲数据模型
GodView v9: PlotOutlineAgent 专用

用于存储和管理章节规划的结构化数据
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class EmotionType(str, Enum):
    """情绪类型枚举"""

    JOY = "joy"               # 喜悦
    ANGER = "anger"           # 愤怒
    SADNESS = "sadness"       # 悲伤
    FEAR = "fear"             # 恐惧
    SURPRISE = "surprise"     # 惊讶
    DISGUST = "disgust"       # 厌恶
    ANTICIPATION = "anticipation"  # 期待
    TRUST = "trust"           # 信任
    TENSION = "tension"       # 紧张
    RELIEF = "relief"         # 释然
    NEUTRAL = "neutral"       # 中性


class SceneType(str, Enum):
    """场景类型枚举"""

    DIALOGUE = "dialogue"         # 对话场景
    ACTION = "action"             # 动作场景
    DESCRIPTION = "description"   # 描写场景
    TRANSITION = "transition"     # 过渡场景
    CLIMAX = "climax"             # 高潮场景
    RESOLUTION = "resolution"     # 结局场景
    FLASHBACK = "flashback"       # 回忆场景
    FORESHADOW = "foreshadow"     # 伏笔场景


class ConflictLevel(str, Enum):
    """冲突强度等级"""

    LOW = "low"           # 低冲突（日常、铺垫）
    MEDIUM = "medium"     # 中等冲突（矛盾显现）
    HIGH = "high"         # 高冲突（激烈对抗）
    CRITICAL = "critical" # 关键冲突（生死存亡）


class SceneOutline(BaseModel):
    """场景大纲模型

    单个场景的规划信息
    """

    id: str = Field(default_factory=lambda: f"scene_{uuid.uuid4().hex[:8]}")
    scene_number: int = Field(..., description="场景序号（章节内）")
    title: str = Field(..., description="场景标题")

    # 场景类型
    scene_type: SceneType = Field(default=SceneType.DIALOGUE, description="场景类型")

    # 内容规划
    summary: str = Field(..., description="场景摘要")
    key_events: List[str] = Field(default_factory=list, description="关键事件")

    # 角色相关
    participating_characters: List[str] = Field(default_factory=list, description="参与角色")
    pov_character: Optional[str] = Field(None, description="视角角色")

    # 地点时间
    location: Optional[str] = Field(None, description="场景地点")
    time_of_day: Optional[str] = Field(None, description="场景时间（如\"黄昏\"、\"深夜\"）")

    # 情绪设计
    emotion_start: EmotionType = Field(default=EmotionType.NEUTRAL, description="开场情绪")
    emotion_end: EmotionType = Field(default=EmotionType.NEUTRAL, description="结束情绪")
    emotion_arc: List[EmotionType] = Field(default_factory=list, description="情绪变化轨迹")

    # 冲突设计
    conflict_level: ConflictLevel = Field(default=ConflictLevel.LOW, description="冲突强度")
    conflict_description: Optional[str] = Field(None, description="冲突描述")

    # 伏笔关联
    hooks_to_plant: List[str] = Field(default_factory=list, description="埋设的伏笔ID")
    hooks_to_resolve: List[str] = Field(default_factory=list, description="回收的伏笔ID")

    # 字数预估
    estimated_words: int = Field(default=500, description="预估字数")

    # 写作提示
    writing_hints: List[str] = Field(default_factory=list, description="写作提示")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "scene_abc123",
                "scene_number": 1,
                "title": "客栈相遇",
                "scene_type": "dialogue",
                "summary": "主角在客栈偶遇神秘老者，获得重要情报",
                "key_events": ["主角进入客栈", "老者主动搭话", "传递情报", "老者离去"],
                "participating_characters": ["char_001", "char_002"],
                "pov_character": "char_001",
                "location": "青云客栈大堂",
                "time_of_day": "黄昏",
                "emotion_start": "neutral",
                "emotion_end": "anticipation",
                "emotion_arc": ["neutral", "curiosity", "anticipation"],
                "conflict_level": "low",
                "conflict_description": "无明显冲突，主要是信息传递",
                "estimated_words": 800,
                "writing_hints": ["注意老者言行的神秘感", "主角内心要有疑惑和警觉"]
            }
        }
    )


class EmotionPoint(BaseModel):
    """情绪曲线数据点"""

    position: float = Field(..., ge=0, le=1, description="位置（0-1表示章节进度）")
    emotion: EmotionType = Field(..., description="情绪类型")
    intensity: float = Field(default=0.5, ge=0, le=1, description="情绪强度")
    description: Optional[str] = Field(None, description="情绪描述")


class EmotionCurve(BaseModel):
    """情绪曲线模型

    规划章节内的情绪起伏
    """

    id: str = Field(default_factory=lambda: f"curve_{uuid.uuid4().hex[:8]}")
    chapter_number: int = Field(..., description="章节号")

    # 情绪数据点
    points: List[EmotionPoint] = Field(default_factory=list, description="情绪数据点")

    # 整体设计
    dominant_emotion: EmotionType = Field(default=EmotionType.NEUTRAL, description="主导情绪")
    peak_emotion: Optional[EmotionPoint] = Field(None, description="情绪高潮点")

    # 节奏设计
    pacing_type: str = Field(default="moderate", description="节奏类型：slow/moderate/fast/variable")
    tension_buildup: Optional[str] = Field(None, description="紧张感构建方式")

    # 读者体验目标
    reader_experience_goal: Optional[str] = Field(None, description="期望读者体验")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "curve_xyz789",
                "chapter_number": 1,
                "points": [
                    {"position": 0.0, "emotion": "neutral", "intensity": 0.3, "description": "平静开场"},
                    {"position": 0.3, "emotion": "surprise", "intensity": 0.6, "description": "意外发现"},
                    {"position": 0.5, "emotion": "tension", "intensity": 0.8, "description": "危机降临"},
                    {"position": 0.7, "emotion": "fear", "intensity": 0.9, "description": "高潮紧张"},
                    {"position": 1.0, "emotion": "relief", "intensity": 0.5, "description": "暂时脱险"}
                ],
                "dominant_emotion": "tension",
                "peak_emotion": {"position": 0.7, "emotion": "fear", "intensity": 0.9},
                "pacing_type": "fast",
                "tension_buildup": "逐步揭示危机，节奏加快",
                "reader_experience_goal": "让读者为主角捏一把汗，期待下一章"
            }
        }
    )


class ChapterOutlineStatus(str, Enum):
    """章节大纲状态"""

    DRAFT = "draft"           # 草稿
    APPROVED = "approved"     # 已审批
    IN_WRITING = "in_writing" # 写作中
    COMPLETED = "completed"   # 已完成
    REVISION = "revision"     # 修订提案
    REJECTED = "rejected"     # 已拒绝


class ChapterOutline(BaseModel):
    """章节大纲模型

    完整的章节规划数据
    """

    id: str = Field(default_factory=lambda: f"outline_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节号")

    # 基本信息
    title: str = Field(..., description="章节标题")
    summary: str = Field(..., description="章节摘要")

    # 状态
    status: ChapterOutlineStatus = Field(default=ChapterOutlineStatus.DRAFT, description="大纲状态")

    # 场景规划
    scenes: List[SceneOutline] = Field(default_factory=list, description="场景列表")

    # 情绪曲线
    emotion_curve: Optional[EmotionCurve] = Field(None, description="情绪曲线")

    # 章节目标
    chapter_goals: List[str] = Field(default_factory=list, description="章节目标")
    plot_advancement: Optional[str] = Field(None, description="剧情推进描述")

    # 角色发展
    character_arcs: Dict[str, str] = Field(default_factory=dict, description="角色发展弧线 {角色ID: 发展描述}")

    # 伏笔管理
    hooks_planted: List[str] = Field(default_factory=list, description="本章埋设的伏笔")
    hooks_resolved: List[str] = Field(default_factory=list, description="本章回收的伏笔")

    # 质量指标
    quality_metrics: Dict[str, Any] = Field(default_factory=dict, description="质量指标")

    # 字数规划
    target_word_count: int = Field(default=3000, description="目标字数")
    estimated_word_count: int = Field(default=0, description="预估字数")

    # 写作指导（供Writer Agent使用）
    writing_guide: Optional[Dict[str, Any]] = Field(None, description="写作指导，包含节奏规范")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    approved_at: Optional[datetime] = Field(None, description="审批时间")
    approved_by: Optional[str] = Field(None, description="审批人")

    # 关联信息
    previous_outline_id: Optional[str] = Field(None, description="上一章大纲ID")
    next_outline_id: Optional[str] = Field(None, description="下一章大纲ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "outline_abc123",
                "project_id": "proj_001",
                "chapter_number": 1,
                "title": "第一章：风云际会",
                "summary": "主角初入江湖，意外卷入门派争斗",
                "status": "approved",
                "scenes": [
                    {
                        "scene_number": 1,
                        "title": "客栈初遇",
                        "scene_type": "dialogue",
                        "summary": "主角在客栈遇到神秘人物"
                    }
                ],
                "chapter_goals": ["建立主角形象", "引入主要冲突", "埋下伏笔"],
                "target_word_count": 3000,
                "hooks_planted": ["hook_001"],
                "character_arcs": {
                    "char_001": "展现初入江湖的青涩"
                }
            }
        }
    )


# ==================== DTO 模型 ====================

class CreateChapterOutlineDTO(BaseModel):
    """创建章节大纲请求"""

    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., ge=1, description="章节号")
    title: str = Field(..., description="章节标题")
    summary: str = Field(..., description="章节摘要")
    scenes: Optional[List[SceneOutline]] = Field(default=None, description="场景列表")
    chapter_goals: List[str] = Field(default_factory=list, description="章节目标")
    hooks_planted: Optional[List[str]] = Field(default=None, description="埋设伏笔")
    hooks_resolved: Optional[List[str]] = Field(default=None, description="回收伏笔")
    target_word_count: int = Field(default=3000, description="目标字数")


class UpdateChapterOutlineDTO(BaseModel):
    """更新章节大纲请求"""

    title: Optional[str] = Field(None, description="章节标题")
    summary: Optional[str] = Field(None, description="章节摘要")
    scenes: Optional[List[SceneOutline]] = Field(None, description="场景列表")
    emotion_curve: Optional[EmotionCurve] = Field(None, description="情绪曲线")
    chapter_goals: Optional[List[str]] = Field(None, description="章节目标")
    status: Optional[ChapterOutlineStatus] = Field(None, description="状态")
    hooks_planted: Optional[List[str]] = Field(None, description="埋设伏笔")
    hooks_resolved: Optional[List[str]] = Field(None, description="回收伏笔")
    target_word_count: Optional[int] = Field(None, description="目标字数")


class GenerateOutlineRequest(BaseModel):
    """生成章节大纲请求"""

    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., ge=1, description="章节号")
    context: Optional[str] = Field(None, description="上下文信息")
    previous_events: Optional[str] = Field(None, description="前文事件")
    special_requirements: Optional[List[str]] = Field(None, description="特殊要求")


class GenerateOutlineResponse(BaseModel):
    """生成章节大纲响应"""

    outline: ChapterOutline = Field(..., description="生成的章节大纲")
    suggestions: List[str] = Field(default_factory=list, description="写作建议")
    warnings: List[str] = Field(default_factory=list, description="注意事项")
    prompt_render_trace: Optional[Dict[str, Any]] = Field(None, description="运行时 prompt 渲染 trace")
    context_packet: Optional[Dict[str, Any]] = Field(None, description="Assistant Context Fabric 上下文包元数据")


class ValidateOutlineRequest(BaseModel):
    """验证章节大纲请求"""

    project_id: str = Field(..., description="项目ID")
    outline: ChapterOutline = Field(..., description="待验证的大纲")


class ValidateOutlineResponse(BaseModel):
    """验证章节大纲响应"""

    valid: bool = Field(..., description="是否有效")
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="问题列表")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    score: float = Field(default=0.0, ge=0, le=1, description="大纲质量评分")
