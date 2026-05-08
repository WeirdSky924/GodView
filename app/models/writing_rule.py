"""
写作规则系统数据模型
管理写作风格规则、规则集和项目写作配置
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WritingRuleCategory(str, Enum):
    """写作规则分类"""

    DIALOGUE = "dialogue"          # 对话类规则
    STRUCTURE = "structure"        # 结构类规则
    STYLE = "style"                # 风格类规则
    GRAMMAR = "grammar"            # 语法类规则
    FORMAT = "format"              # 格式类规则
    CHARACTER = "character"        # 角色塑造类规则
    PLOT = "plot"                  # 剧情类规则
    PACING = "pacing"              # 节奏类规则


class RuleSeverity(str, Enum):
    """规则严重程度"""

    REQUIRED = "required"          # 必须遵守
    STRONG = "strong"              # 强烈建议
    RECOMMENDED = "recommended"    # 推荐
    OPTIONAL = "optional"          # 可选
    INFO = "info"                  # 信息性


class WritingRuleApplicationMode(str, Enum):
    """规则运行时应用模式"""

    ALWAYS = "always"                          # 常驻加载
    ALWAYS_POSTCHECK = "always_postcheck"      # 常驻加载 + 写后检查
    RETRIEVE = "retrieve"                      # 按需检索
    RETRIEVE_POSTCHECK = "retrieve_postcheck"  # 按需检索 + 写后检查
    RETRIEVE_ON_MATCH = "retrieve_on_match"    # 强匹配时检索
    REFERENCE = "reference"                    # 仅参考/解释


def get_default_application_mode(
    severity: Optional[RuleSeverity | str] = None,
) -> WritingRuleApplicationMode:
    """根据严重程度推导默认运行时应用模式"""

    severity_value = severity.value if isinstance(severity, RuleSeverity) else severity
    mapping = {
        RuleSeverity.REQUIRED.value: WritingRuleApplicationMode.ALWAYS_POSTCHECK,
        RuleSeverity.STRONG.value: WritingRuleApplicationMode.RETRIEVE_POSTCHECK,
        RuleSeverity.RECOMMENDED.value: WritingRuleApplicationMode.RETRIEVE,
        RuleSeverity.OPTIONAL.value: WritingRuleApplicationMode.RETRIEVE_ON_MATCH,
        RuleSeverity.INFO.value: WritingRuleApplicationMode.REFERENCE,
    }
    return mapping.get(severity_value or RuleSeverity.RECOMMENDED.value, WritingRuleApplicationMode.RETRIEVE)


class WritingRule(BaseModel):
    """写作规则模型"""

    id: str = Field(..., description="规则ID")
    name: str = Field(..., description="规则名称")
    description: str = Field(default="", description="规则描述")

    # 分类
    category: WritingRuleCategory = Field(..., description="规则分类")
    severity: RuleSeverity = Field(default=RuleSeverity.RECOMMENDED, description="规则严重程度")
    application_mode: WritingRuleApplicationMode = Field(
        default=WritingRuleApplicationMode.RETRIEVE,
        description="规则运行时应用模式",
    )
    tags: List[str] = Field(default_factory=list, description="标签")

    # 内容
    content: str = Field(..., description="规则内容描述")
    examples: List[str] = Field(default_factory=list, description="示例列表")
    counter_examples: Optional[List[str]] = Field(default=None, description="反例列表")

    # 应用条件
    conditions: List[Dict[str, Any]] = Field(default_factory=list, description="应用条件")
    exceptions: Optional[List[str]] = Field(default=None, description="例外情况")

    # 元数据
    is_system: bool = Field(default=False, description="是否系统内置规则")
    version: str = Field(default="1.0.0", description="规则版本")
    author: Optional[str] = Field(default=None, description="作者")
    source: Optional[str] = Field(default=None, description="来源")

    # 使用统计
    usage_count: int = Field(default=0, description="使用次数")
    last_used_at: Optional[datetime] = Field(default=None, description="最后使用时间")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "dialogue_voice_character",
                "name": "角色声音差异化",
                "description": "不同角色应有独特的说话方式和用词习惯",
                "category": "dialogue",
                "severity": "required",
                "application_mode": "always_postcheck",
                "tags": ["dialogue", "character"],
                "content": "每个角色应有独特的说话风格、用词习惯和口头禅。避免所有角色说话方式雷同。",
                "examples": [
                    "角色A使用正式语言和复杂句式，角色B使用俚语和简短句子",
                    "学者角色使用专业术语，农民角色使用方言土语"
                ],
                "is_system": True
            }
        }
    )


class WritingRuleCreate(BaseModel):
    """创建写作规则请求"""

    name: str = Field(..., description="规则名称", min_length=1, max_length=200)
    description: str = Field(default="", description="规则描述")
    category: WritingRuleCategory = Field(..., description="规则分类")
    severity: RuleSeverity = Field(default=RuleSeverity.RECOMMENDED, description="规则严重程度")
    application_mode: WritingRuleApplicationMode = Field(
        default=WritingRuleApplicationMode.RETRIEVE,
        description="规则运行时应用模式",
    )
    tags: List[str] = Field(default_factory=list, description="标签")
    content: str = Field(..., description="规则内容描述", min_length=1)
    examples: List[str] = Field(default_factory=list, description="示例列表")
    counter_examples: Optional[List[str]] = Field(default=None, description="反例列表")
    conditions: List[Dict[str, Any]] = Field(default_factory=list, description="应用条件")
    exceptions: Optional[List[str]] = Field(default=None, description="例外情况")
    author: Optional[str] = Field(default=None, description="作者")
    source: Optional[str] = Field(default=None, description="来源")
    is_system: bool = Field(default=False, description="是否系统内置规则")


class WritingRuleUpdate(BaseModel):
    """更新写作规则请求"""

    name: Optional[str] = Field(None, description="规则名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="规则描述")
    category: Optional[WritingRuleCategory] = Field(None, description="规则分类")
    severity: Optional[RuleSeverity] = Field(None, description="规则严重程度")
    application_mode: Optional[WritingRuleApplicationMode] = Field(None, description="规则运行时应用模式")
    tags: Optional[List[str]] = Field(None, description="标签")
    content: Optional[str] = Field(None, description="规则内容描述", min_length=1)
    examples: Optional[List[str]] = Field(None, description="示例列表")
    counter_examples: Optional[List[str]] = Field(None, description="反例列表")
    conditions: Optional[List[Dict[str, Any]]] = Field(None, description="应用条件")
    exceptions: Optional[List[str]] = Field(None, description="例外情况")
    author: Optional[str] = Field(None, description="作者")
    source: Optional[str] = Field(None, description="来源")
    is_system: Optional[bool] = Field(None, description="是否系统内置规则")
    version: Optional[str] = Field(None, description="规则版本")


class WritingRuleSet(BaseModel):
    """写作规则集模型"""

    id: str = Field(..., description="规则集ID")
    name: str = Field(..., description="规则集名称")
    description: str = Field(default="", description="规则集描述")

    # 规则组成
    rule_ids: List[str] = Field(default_factory=list, description="包含的规则ID列表")
    rule_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="规则覆盖配置（规则ID -> 覆盖配置）"
    )

    # 分类
    category: WritingRuleCategory = Field(..., description="主要分类")
    tags: List[str] = Field(default_factory=list, description="标签")
    target_genres: List[str] = Field(default_factory=list, description="目标体裁")

    # 元数据
    is_system: bool = Field(default=False, description="是否系统内置规则集")
    version: str = Field(default="1.0.0", description="规则集版本")
    author: Optional[str] = Field(default=None, description="作者")

    # 使用统计
    usage_count: int = Field(default=0, description="使用次数")
    last_used_at: Optional[datetime] = Field(default=None, description="最后使用时间")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "rule_set_web_novel",
                "name": "网文爽文风格规则集",
                "description": "适用于网络爽文的写作规则集",
                "rule_ids": ["dialogue_voice_character", "sentence_rhythm_variation"],
                "category": "style",
                "tags": ["web_novel", "爽文", "fast_paced"],
                "target_genres": ["fantasy", "xianxia", "urban"],
                "is_system": True
            }
        }
    )


class WritingRuleSetCreate(BaseModel):
    """创建写作规则集请求"""

    name: str = Field(..., description="规则集名称", min_length=1, max_length=200)
    description: str = Field(default="", description="规则集描述")
    rule_ids: List[str] = Field(default_factory=list, description="包含的规则ID列表")
    rule_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="规则覆盖配置"
    )
    category: WritingRuleCategory = Field(..., description="主要分类")
    tags: List[str] = Field(default_factory=list, description="标签")
    target_genres: List[str] = Field(default_factory=list, description="目标体裁")
    author: Optional[str] = Field(default=None, description="作者")
    is_system: bool = Field(default=False, description="是否系统内置规则集")


class WritingRuleSetUpdate(BaseModel):
    """更新写作规则集请求"""

    name: Optional[str] = Field(None, description="规则集名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="规则集描述")
    rule_ids: Optional[List[str]] = Field(None, description="包含的规则ID列表")
    rule_overrides: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="规则覆盖配置")
    category: Optional[WritingRuleCategory] = Field(None, description="主要分类")
    tags: Optional[List[str]] = Field(None, description="标签")
    target_genres: Optional[List[str]] = Field(None, description="目标体裁")
    author: Optional[str] = Field(None, description="作者")
    is_system: Optional[bool] = Field(None, description="是否系统内置规则集")
    version: Optional[str] = Field(None, description="规则集版本")


class ProjectWritingConfig(BaseModel):
    """项目写作配置模型"""

    id: str = Field(..., description="配置ID")
    project_id: str = Field(..., description="项目ID")

    # 规则配置
    enabled_rule_ids: List[str] = Field(default_factory=list, description="启用的规则ID列表")
    enabled_rule_set_ids: List[str] = Field(default_factory=list, description="启用的规则集ID列表")
    rule_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="规则覆盖配置（规则ID -> 覆盖配置）"
    )

    # 优先级配置
    rule_priorities: Dict[str, int] = Field(default_factory=dict, description="规则优先级（数值越大优先级越高）")
    default_severity: RuleSeverity = Field(default=RuleSeverity.RECOMMENDED, description="默认严重程度")

    # 应用范围
    apply_to_chapters: bool = Field(default=True, description="是否应用于章节")
    apply_to_characters: bool = Field(default=True, description="是否应用于角色对话")
    apply_to_descriptions: bool = Field(default=True, description="是否应用于描写")
    apply_to_narration: bool = Field(default=True, description="是否应用于叙述")

    # 元数据
    is_active: bool = Field(default=True, description="是否激活")
    version: str = Field(default="1.0.0", description="配置版本")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "config_001",
                "project_id": "proj_001",
                "enabled_rule_ids": ["dialogue_voice_character", "sentence_rhythm_variation"],
                "enabled_rule_set_ids": ["rule_set_web_novel"],
                "rule_overrides": {
                    "dialogue_voice_character": {"severity": "required"}
                },
                "rule_priorities": {
                    "dialogue_voice_character": 90,
                    "sentence_rhythm_variation": 80
                },
                "default_severity": "recommended",
                "is_active": True
            }
        }
    )


class ProjectWritingConfigUpdate(BaseModel):
    """更新项目写作配置请求"""

    enabled_rule_ids: Optional[List[str]] = Field(None, description="启用的规则ID列表")
    enabled_rule_set_ids: Optional[List[str]] = Field(None, description="启用的规则集ID列表")
    rule_overrides: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="规则覆盖配置")
    rule_priorities: Optional[Dict[str, int]] = Field(None, description="规则优先级")
    default_severity: Optional[RuleSeverity] = Field(None, description="默认严重程度")
    apply_to_chapters: Optional[bool] = Field(None, description="是否应用于章节")
    apply_to_characters: Optional[bool] = Field(None, description="是否应用于角色对话")
    apply_to_descriptions: Optional[bool] = Field(None, description="是否应用于描写")
    apply_to_narration: Optional[bool] = Field(None, description="是否应用于叙述")
    is_active: Optional[bool] = Field(None, description="是否激活")
    version: Optional[str] = Field(None, description="配置版本")