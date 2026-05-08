"""
Agent 配置模型 - 项目级别的 Agent 配置

每个项目可以有多个 Agent 配置，每个配置基于一个 AgentTemplate，
但可以覆盖模板中的 Prompt 选择和模型参数。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConfigOverrideType(str, Enum):
    """配置覆盖类型"""

    PROMPT_REPLACE = "prompt_replace"     # 替换整个 Prompt
    VARIABLE_OVERRIDE = "variable_override"  # 覆盖变量值
    SLOT_DISABLE = "slot_disable"        # 禁用插槽
    SLOT_ENABLE = "slot_enable"          # 启用插槽
    MODEL_CHANGE = "model_change"        # 更改模型参数


class SlotOverride(BaseModel):
    """Prompt 插槽覆盖配置"""

    slot_name: str = Field(..., description="插槽名称")
    override_type: ConfigOverrideType = Field(..., description="覆盖类型")

    # 覆盖值
    prompt_template_id: Optional[str] = Field(None, description="新的 PromptTemplate ID")
    variable_values: Optional[Dict[str, Any]] = Field(None, description="变量覆盖值")
    is_enabled: Optional[bool] = Field(None, description="是否启用此插槽")

    # 优先级调整
    priority_override: Optional[int] = Field(None, description="优先级覆盖值")


class ModelConfig(BaseModel):
    """模型配置"""

    model_name: str = Field(default="gpt-4o-mini", description="模型名称")
    temperature: float = Field(default=0.7, description="温度参数")
    max_tokens: Optional[int] = Field(default=None, description="最大 Token 数")
    top_p: Optional[float] = Field(default=None, description="Top-P 参数")
    frequency_penalty: Optional[float] = Field(default=None, description="频率惩罚")
    presence_penalty: Optional[float] = Field(default=None, description="存在惩罚")


class AgentConfig(BaseModel):
    """Agent 配置模型"""

    id: str = Field(..., description="配置 ID")
    project_id: str = Field(..., description="项目 ID")
    agent_type: str = Field(..., description="Agent 类型")
    scenario: str = Field(default="default", description="Agent 使用场景")

    # 基础信息
    name: str = Field(..., description="配置名称")
    description: str = Field(default="", description="配置描述")

    # 模板关联
    template_id: Optional[str] = Field(None, description="基于的模板 ID")
    is_custom: bool = Field(default=False, description="是否为自定义配置（非模板派生）")

    # Prompt 配置
    slot_overrides: List[SlotOverride] = Field(default_factory=list, description="插槽覆盖配置")
    custom_prompt_order: Optional[List[str]] = Field(None, description="自定义 Prompt 顺序")

    # 模型配置
    llm_config: ModelConfig = Field(default_factory=ModelConfig, description="模型配置")

    # 元数据
    is_active: bool = Field(default=True, description="是否激活")
    version: str = Field(default="1.0.0", description="配置版本")

    # 使用统计
    usage_count: int = Field(default=0, description="使用次数")
    last_used_at: Optional[datetime] = Field(default=None, description="最后使用时间")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "config_001",
                "project_id": "proj_001",
                "agent_type": "writer",
                "scenario": "workflow_chapter_generation",
                "name": "项目 Writer 配置",
                "description": "项目的作家 Agent 配置",
                "template_id": "director_writer",
                "is_custom": False,
                "slot_overrides": [
                    {
                        "slot_name": "role_definition",
                        "override_type": "variable_override",
                        "variable_values": {"style": "literary"}
                    }
                ],
                "llm_config": {
                    "model_name": "gpt-4o",
                    "temperature": 0.8
                },
                "is_active": True
            }
        }
    )


class AgentConfigCreate(BaseModel):
    """创建 Agent 配置请求"""

    project_id: str = Field(..., description="项目 ID")
    agent_type: str = Field(..., description="Agent 类型")
    scenario: str = Field(default="default", description="Agent 使用场景")

    # 基础信息
    name: str = Field(..., description="配置名称", min_length=1, max_length=200)
    description: str = Field(default="", description="配置描述")

    # 模板关联
    template_id: Optional[str] = Field(None, description="基于的模板 ID")
    is_custom: bool = Field(default=False, description="是否为自定义配置")

    # Prompt 配置
    slot_overrides: List[SlotOverride] = Field(default_factory=list, description="插槽覆盖配置")
    custom_prompt_order: Optional[List[str]] = Field(None, description="自定义 Prompt 顺序")

    # 模型配置
    llm_config: ModelConfig = Field(default_factory=ModelConfig, description="模型配置")

    # 元数据
    is_active: bool = Field(default=True, description="是否激活")


class AgentConfigUpdate(BaseModel):
    """更新 Agent 配置请求"""

    name: Optional[str] = Field(None, description="配置名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="配置描述")
    scenario: Optional[str] = Field(None, description="Agent 使用场景")

    # 模板关联
    template_id: Optional[str] = Field(None, description="基于的模板 ID")
    is_custom: Optional[bool] = Field(None, description="是否为自定义配置")

    # Prompt 配置
    slot_overrides: Optional[List[SlotOverride]] = Field(None, description="插槽覆盖配置")
    custom_prompt_order: Optional[List[str]] = Field(None, description="自定义 Prompt 顺序")

    # 模型配置
    llm_config: Optional[ModelConfig] = Field(None, description="模型配置")

    # 元数据
    is_active: Optional[bool] = Field(None, description="是否激活")
    version: Optional[str] = Field(None, description="配置版本")