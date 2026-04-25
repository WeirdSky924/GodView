"""
世界快照数据模型 - 用于回档功能
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SnapshotType(str, Enum):
    """快照类型"""

    AUTO = "auto"  # 自动生成（章节结束）
    MANUAL = "manual"  # 手动保存
    PRE_INTERVENTION = "pre_intervention"  # 干预前自动保存


class WorldSnapshot(BaseModel):
    """世界快照模型 - 保存某一时刻的完整世界状态"""

    id: str = Field(..., description="快照唯一 ID")
    world_id: str = Field(..., description="所属世界 ID")
    chapter_id: Optional[str] = Field(None, description="关联章节 ID")

    # 快照类型
    snapshot_type: SnapshotType = Field(default=SnapshotType.AUTO, description="快照类型")

    # 快照名称（用户可自定义）
    name: Optional[str] = Field(None, description="快照名称")
    description: Optional[str] = Field(None, description="快照描述/备注")

    # 核心数据快照
    characters: Dict[str, Any] = Field(
        default_factory=dict, description="角色数据快照 {id: data}"
    )
    relationships: Dict[str, Any] = Field(
        default_factory=dict, description="关系数据快照 {id: data}"
    )
    regions: Dict[str, Any] = Field(
        default_factory=dict, description="区域数据快照 {id: data}"
    )
    hooks: Dict[str, Any] = Field(
        default_factory=dict, description="伏笔数据快照 {id: data}"
    )

    # 剧情状态
    main_plot_progress: float = Field(default=0.0, description="主线进度")
    completed_events: List[str] = Field(default_factory=list, description="已完成事件")

    # 位置状态
    character_locations: Dict[str, str] = Field(
        default_factory=dict, description="角色位置 {character_id: region_id}"
    )

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="system", description="创建者：system/user")

    # 父快照（用于构建快照树）
    parent_snapshot_id: Optional[str] = Field(None, description="父快照 ID")

    # 分支信息
    is_branch: bool = Field(default=False, description="是否为分支快照")
    branch_reason: Optional[str] = Field(None, description="分支原因（用户干预等）")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "snapshot_001",
                "world_id": "world_001",
                "chapter_id": "chapter_001",
                "snapshot_type": "auto",
                "name": "第一章结束",
                "main_plot_progress": 0.1,
                "character_locations": {
                    "char_001": "region_001",
                    "char_002": "region_002",
                },
            }
        }
    )


class InterventionLog(BaseModel):
    """用户干预日志"""

    id: str = Field(..., description="干预日志 ID")
    snapshot_id: str = Field(..., description="干预时基于的快照 ID")

    # 干预类型
    intervention_type: str = Field(
        ...,
        description="干预类型：modify_character/modify_plot/force_event/rollback",
    )

    # 干预内容
    description: str = Field(..., description="干预描述")
    details: Dict[str, Any] = Field(default_factory=dict, description="干预详细内容")

    # 影响分析
    affected_hooks: List[str] = Field(default_factory=list, description="受影响的伏笔")
    affected_relationships: List[str] = Field(
        default_factory=list, description="受影响的关系"
    )
    affected_characters: List[str] = Field(default_factory=list, description="受影响的角色")

    # 干预后评价
    outcome_rating: Optional[float] = Field(
        None, ge=0, le=1, description="干预后效果评分（后续填写）"
    )
    outcome_notes: Optional[str] = Field(None, description="干预效果备注")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "intervention_001",
                "snapshot_id": "snapshot_001",
                "intervention_type": "modify_character",
                "description": "修改张三的性格，增加'谨慎'特质",
                "details": {
                    "character_id": "char_001",
                    "change": "add_trait",
                    "trait": {"name": "谨慎", "value": 0.6},
                },
                "affected_hooks": ["hook_001"],
            }
        }
    )


class VersionDiff(BaseModel):
    """版本差异模型"""

    id: str = Field(..., description="差异 ID")
    snapshot_a_id: str = Field(..., description="快照 A ID")
    snapshot_b_id: str = Field(..., description="快照 B ID")

    # 差异内容
    characters_added: List[str] = Field(default_factory=list)
    characters_removed: List[str] = Field(default_factory=list)
    characters_modified: List[str] = Field(default_factory=list)

    hooks_added: List[str] = Field(default_factory=list)
    hooks_resolved: List[str] = Field(default_factory=list)

    plot_progress_diff: float = Field(default=0.0)

    # 详细差异
    details: Dict[str, Any] = Field(default_factory=dict, description="详细差异数据")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
