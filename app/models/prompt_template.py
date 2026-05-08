"""
Prompt 模板模型 - 可复用的 prompt 片段

支持：
- 分类管理（基础、角色、功能、价值观、输出格式、约束）
- 变量插值
- 标签分类
- 优先级排序
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class PromptCategory(str, Enum):
    """Prompt 片段分类"""
    BASE = "base"              # 基础 prompt（如通用角色定义）
    ROLE = "role"              # 角色定义（如"你是总编剧"）
    FUNCTION = "function"      # 功能规范（如写作规范、冲突检测规则）
    VALUE = "value"            # 价值观/风格（如角色发言时的价值观）
    OUTPUT = "output"          # 输出格式（如 JSON 格式规范）
    CONSTRAINT = "constraint"  # 约束条件


class PromptVariable(BaseModel):
    """Prompt 变量定义"""
    name: str = Field(..., description="变量名")
    type: str = Field(default="string", description="变量类型")
    description: str = Field(default="", description="变量描述")
    default: Optional[Any] = Field(default=None, description="默认值")
    required: bool = Field(default=False, description="是否必填")


class PromptTemplate(BaseModel):
    """Prompt 模板片段"""

    id: str = Field(..., description="Prompt ID")
    name: str = Field(..., description="Prompt 名称")
    description: str = Field(default="", description="Prompt 描述")

    # 分类
    category: PromptCategory = Field(..., description="Prompt 分类")
    tags: List[str] = Field(default_factory=list, description="标签")

    # 内容
    content: str = Field(..., description="Prompt 内容，支持 {variable} 插值")
    variables: List[Union[str, PromptVariable]] = Field(default_factory=list, description="所需的变量列表")
    default_values: Dict[str, Any] = Field(default_factory=dict, description="变量默认值")

    # 优先级（数值越大优先级越高，排在前面）
    priority: int = Field(default=50, description="拼接优先级，数值越大越靠前")

    # 元数据
    is_system: bool = Field(default=False, description="是否系统内置（不可删除）")
    version: int = Field(default=1, description="版本号")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "role_master_plotter",
                "name": "总编剧角色定义",
                "description": "定义总编剧的角色定位",
                "category": "role",
                "tags": ["director", "plot"],
                "content": "你是总编剧，负责把控主线进度和剧情走向。",
                "variables": [],
                "default_values": {},
                "priority": 90,
                "is_system": True,
            }
        }
    )


class PromptTemplateCreate(BaseModel):
    """创建 Prompt 模板请求"""

    name: str = Field(..., description="Prompt 名称", min_length=1, max_length=200)
    description: str = Field(default="", description="Prompt 描述")
    category: PromptCategory = Field(..., description="Prompt 分类")
    tags: List[str] = Field(default_factory=list, description="标签")
    content: str = Field(..., description="Prompt 内容", min_length=1)
    variables: List[str] = Field(default_factory=list, description="所需的变量列表")
    default_values: Dict[str, Any] = Field(default_factory=dict, description="变量默认值")
    priority: int = Field(default=50, description="拼接优先级")


class PromptTemplateUpdate(BaseModel):
    """更新 Prompt 模板请求"""

    name: Optional[str] = Field(None, description="Prompt 名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Prompt 描述")
    category: Optional[PromptCategory] = Field(None, description="Prompt 分类")
    tags: Optional[List[str]] = Field(None, description="标签")
    content: Optional[str] = Field(None, description="Prompt 内容", min_length=1)
    variables: Optional[List[str]] = Field(None, description="所需的变量列表")
    default_values: Optional[Dict[str, Any]] = Field(None, description="变量默认值")
    priority: Optional[int] = Field(None, description="拼接优先级")


class PromptFilter(BaseModel):
    """Prompt 过滤条件"""

    category: Optional[PromptCategory] = Field(None, description="按分类过滤")
    tags: Optional[List[str]] = Field(None, description="按标签过滤（任一匹配）")
    search: Optional[str] = Field(None, description="搜索关键词")
    is_system: Optional[bool] = Field(None, description="是否系统内置")

    # 分页
    limit: int = Field(default=50, description="返回数量限制")
    offset: int = Field(default=0, description="偏移量")


class PromptRenderRequest(BaseModel):
    """Prompt 渲染请求"""

    template_id: str = Field(..., description="模板 ID")
    variables: Dict[str, Any] = Field(default_factory=dict, description="变量值")


class PromptRenderResult(BaseModel):
    """Prompt 渲染结果"""

    template_id: str
    original_content: str
    rendered_content: str
    used_variables: Dict[str, Any]
    missing_variables: List[str]
