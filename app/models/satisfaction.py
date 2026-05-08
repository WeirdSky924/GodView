"""
爽点数据模型
GodView v9: 爽点设计框架

用于管理爽点类型、设计方案和分析结果
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class CoolPointType(str, Enum):
    """爽点类型"""

    FACE_SLAP = "face_slap"           # 打脸
    COUNTERATTACK = "counterattack"   # 反击
    UPGRADE = "upgrade"               # 升级
    TREASURE = "treasure"             # 获宝
    REVENGE = "revenge"               # 复仇
    RECOGNITION = "recognition"       # 认可
    POWER_DISPLAY = "power_display"   # 震慑
    PLOT_TWIST = "plot_twist"         # 反转
    ROMANCE = "romance"               # 感情
    MYSTERY_REVEAL = "mystery_reveal" # 揭秘
    UNDERDOG_WIN = "underdog_win"     # 弱胜强
    LUCKY_ENCOUNTER = "lucky_encounter" # 奇遇


class CoolPointIntensity(str, Enum):
    """爽点强度等级"""

    LOW = "low"           # 低（小爽）
    MEDIUM = "medium"     # 中（中爽）
    HIGH = "high"         # 高（大爽）
    EXTREME = "extreme"   # 极高（爽爆）


class PibuBurstPhase(str, Enum):
    """铺垫-爆发阶段"""

    SETUP = "setup"       # 铺垫期
    BUILDUP = "buildup"   # 积累期
    BURST = "burst"       # 爆发期
    AFTERMATH = "aftermath" # 余韵期


class CoolPointDefinition(BaseModel):
    """爽点类型定义（配置化）"""

    id: str = Field(default_factory=lambda: f"cp_type_{uuid.uuid4().hex[:8]}")
    type: CoolPointType = Field(..., description="爽点类型")
    name: str = Field(..., description="类型名称")
    description: str = Field(..., description="类型描述")

    # 典型特征
    typical_elements: List[str] = Field(default_factory=list, description="典型元素")
    common_patterns: List[str] = Field(default_factory=list, description="常见模式")

    # 强度因子
    intensity_factors: Dict[str, float] = Field(default_factory=dict, description="强度影响因子")

    # 适用场景
    applicable_genres: List[str] = Field(default_factory=list, description="适用题材")
    applicable_chapters: str = Field(default="all", description="适用章节范围")

    # 示例
    examples: List[str] = Field(default_factory=list, description="典型示例")

    # 元数据
    is_active: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "cp_type_face_slap",
                "type": "face_slap",
                "name": "打脸",
                "description": "主角被看不起后实力碾压对方",
                "typical_elements": ["嘲讽", "轻视", "实力展示", "震惊"],
                "common_patterns": ["先抑后扬", "对比反差"],
                "intensity_factors": {"对方地位": 0.3, "羞辱程度": 0.2, "反击力度": 0.5},
                "applicable_genres": ["xuanhuan", "urban", "history"],
                "examples": ["宗门大比逆袭", "商业谈判反转"]
            }
        }
    )


class CoolPointInstance(BaseModel):
    """爽点实例（章节中的具体爽点）"""

    id: str = Field(default_factory=lambda: f"cp_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节号")

    # 爽点类型
    point_type: CoolPointType = Field(..., description="爽点类型")
    intensity: float = Field(default=0.5, ge=0, le=1, description="强度 0-1")

    # 描述
    description: str = Field(..., description="爽点描述")
    position: str = Field(..., description="位置描述（章节中位置）")

    # 相关角色
    characters_involved: List[str] = Field(default_factory=list, description="相关角色")

    # 铺垫-爆发关联
    setup_chapter: Optional[int] = Field(None, description="铺垫章节")
    setup_description: Optional[str] = Field(None, description="铺垫描述")

    # 效果评估
    reader_satisfaction: Optional[float] = Field(None, ge=0, le=1, description="读者满意度")
    execution_quality: Optional[float] = Field(None, ge=0, le=1, description="执行质量")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)


class PibuBurstDesign(BaseModel):
    """铺垫-爆发结构设计"""

    id: str = Field(default_factory=lambda: f"pibu_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")

    # 设计信息
    design_name: str = Field(..., description="设计名称")
    description: str = Field(..., description="整体描述")

    # 铺垫阶段
    setup_chapters: List[int] = Field(default_factory=list, description="铺垫章节")
    setup_elements: List[str] = Field(default_factory=list, description="铺垫元素")
    setup_tension: float = Field(default=0.3, ge=0, le=1, description="铺垫张力")

    # 积累阶段
    buildup_chapters: List[int] = Field(default_factory=list, description="积累章节")
    buildup_events: List[str] = Field(default_factory=list, description="积累事件")

    # 爆发阶段
    burst_chapter: int = Field(..., description="爆发章节")
    burst_description: str = Field(..., description="爆发描述")
    burst_intensity: float = Field(default=0.8, ge=0, le=1, description="爆发强度")

    # 余韵阶段
    aftermath_chapters: List[int] = Field(default_factory=list, description="余韵章节")
    aftermath_elements: List[str] = Field(default_factory=list, description="余韵元素")

    # 预期效果
    expected_satisfaction: float = Field(default=0.7, ge=0, le=1, description="预期满意度")

    # 关联爽点
    cool_point_ids: List[str] = Field(default_factory=list, description="关联爽点ID")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SatisfactionAnalysisRecord(BaseModel):
    """满意度分析记录"""

    id: str = Field(default_factory=lambda: f"sat_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节号")

    # 总体评分
    overall_score: float = Field(default=0.0, ge=0, le=100, description="总体爽点评分")
    satisfaction_index: float = Field(default=0.0, ge=0, le=1, description="满意度指数")

    # 检测到的爽点
    detected_points: List[CoolPointInstance] = Field(default_factory=list, description="检测到的爽点")

    # 铺垫-爆发结构
    pibu_burst_structures: List[PibuBurstDesign] = Field(default_factory=list, description="铺垫-爆发结构")

    # 分析详情
    analysis_details: Dict[str, Any] = Field(default_factory=dict, description="分析详情")

    # 改进建议
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    warnings: List[str] = Field(default_factory=list, description="警告")

    # 元数据
    analyzed_at: datetime = Field(default_factory=datetime.now)


# ==================== DTO 模型 ====================

class CreateCoolPointDTO(BaseModel):
    """创建爽点实例请求"""

    project_id: str
    chapter_number: int
    point_type: CoolPointType
    description: str
    position: str
    intensity: float = 0.5
    characters_involved: List[str] = Field(default_factory=list)


class CreatePibuBurstDTO(BaseModel):
    """创建铺垫-爆发设计请求"""

    project_id: str
    design_name: str
    description: str
    setup_chapters: List[int] = Field(default_factory=list)
    burst_chapter: int
    burst_description: str
    expected_satisfaction: float = 0.7


class AnalyzeSatisfactionDTO(BaseModel):
    """满意度分析请求"""

    project_id: str
    chapter_number: int
    content: Optional[str] = None
    analysis_depth: str = Field(default="standard", description="分析深度: quick/standard/deep")


class CoolPointSuggestion(BaseModel):
    """爽点设计建议"""

    point_type: CoolPointType
    suggestion: str
    expected_intensity: float
    implementation_hints: List[str]
