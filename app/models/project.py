"""
项目数据模型
GodView v4 新增：项目级别抽象，作为世界和角色的顶级容器
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    """项目状态"""

    DRAFT = "draft"  # 草稿
    BOOTSTRAPPING = "bootstrapping"  # 正在初始化
    ACTIVE = "active"  # 活跃
    ARCHIVED = "archived"  # 已归档
    FAILED = "failed"  # 失败


class Project(BaseModel):
    """项目模型

    作为世界和角色的顶级容器，提供项目级别的管理抽象
    """

    id: str = Field(..., description="项目ID")
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    user_id: Optional[str] = Field(None, description="用户ID")

    # 项目状态
    status: ProjectStatus = Field(default=ProjectStatus.DRAFT, description="项目状态")

    # 关联实体
    world_id: Optional[str] = Field(None, description="关联的世界ID")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="项目元数据")


class ProjectSummary(BaseModel):
    """项目摘要模型（用于列表展示）"""

    id: str = Field(..., description="项目ID")
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    status: ProjectStatus = Field(..., description="项目状态")
    world_id: Optional[str] = Field(None, description="关联的世界ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    character_count: int = Field(default=0, description="角色数量")
    chapter_count: int = Field(default=0, description="章节数量")


class CreateProjectRequest(BaseModel):
    """创建项目请求"""

    name: str = Field(..., min_length=1, max_length=255, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    user_id: Optional[str] = Field(None, description="用户ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="项目元数据")


class UpdateProjectRequest(BaseModel):
    """更新项目请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    status: Optional[ProjectStatus] = Field(None, description="项目状态")
    metadata: Optional[Dict[str, Any]] = Field(None, description="项目元数据")