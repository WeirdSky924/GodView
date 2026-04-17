"""
静态设定 (Lore) 数据模型
用于存储世界观、历史、势力、文化等"世界宪法"级设定
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


LEGACY_LORE_PRIORITY_MAP = {
    "low": "flexible",
    "medium": "standard",
    "high": "core",
}

LEGACY_LORE_CATEGORY_MAP = {
    "world": "world_rule",
    "worldview": "world_rule",
    "rule": "world_rule",
    "rules": "world_rule",
    "location": "geography",
    "place": "geography",
    "organization": "faction",
    "organisation": "faction",
    "group": "faction",
    "job": "profession",
    "class": "profession",
    "artifact": "item",
    "equipment": "item",
    "ability": "skill",
    "power": "skill",
}


def normalize_lore_category(value: Any) -> "LoreCategory":
    """将输入值归一化为当前 LoreCategory。"""
    if isinstance(value, LoreCategory):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        normalized = LEGACY_LORE_CATEGORY_MAP.get(normalized, normalized)

        try:
            return LoreCategory(normalized)
        except ValueError:
            pass

    return LoreCategory.CUSTOM


def normalize_lore_priority(value: Any) -> "LorePriority":
    """将 legacy priority 值归一化为当前 LorePriority。"""
    if isinstance(value, LorePriority):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in LEGACY_LORE_PRIORITY_MAP:
            normalized = LEGACY_LORE_PRIORITY_MAP[normalized]

        try:
            return LorePriority(normalized)
        except ValueError:
            pass

    return LorePriority.STANDARD


class LoreCategory(str, Enum):
    """设定类别"""

    WORLD_RULE = "world_rule"  # 世界规则（物理法则、魔法体系等）
    GEOGRAPHY = "geography"  # 地理设定
    HISTORY = "history"  # 历史背景
    FACTION = "faction"  # 势力体系
    CULTURE = "culture"  # 文化习俗
    RACE = "race"  # 种族设定
    PROFESSION = "profession"  # 职业/阶层
    ITEM = "item"  # 物品/装备
    SKILL = "skill"  # 技能/能力
    CUSTOM = "custom"  # 自定义


class LorePriority(str, Enum):
    """设定优先级"""

    CONSTITUTIONAL = "constitutional"  # 宪法级（不可违反的核心规则）
    CORE = "core"  # 核心设定（重要但可微调）
    STANDARD = "standard"  # 标准设定（一般性描述）
    FLEXIBLE = "flexible"  # 灵活设定（可随剧情调整）


class LoreEntry(BaseModel):
    """设定条目模型"""

    id: Optional[str] = Field(None, description="设定唯一 ID（创建时自动生成）")
    project_id: str = Field(..., description="所属项目 ID")

    # 基本信息
    title: str = Field(..., description="设定标题")
    category: LoreCategory = Field(default=LoreCategory.CUSTOM, description="设定类别")
    priority: LorePriority = Field(default=LorePriority.STANDARD, description="设定优先级")

    # 内容
    content: str = Field(..., description="设定详细内容（支持 Markdown）")
    summary: Optional[str] = Field(None, description="设定摘要")

    # 关键词和标签
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    tags: List[str] = Field(default_factory=list, description="标签列表")

    # 关联信息
    related_characters: List[str] = Field(default_factory=list, description="相关角色 ID")
    related_locations: List[str] = Field(default_factory=list, description="相关地点 ID")
    related_items: List[str] = Field(default_factory=list, description="相关物品 ID")
    parent_lore_id: Optional[str] = Field(None, description="父设定 ID（用于层级结构）")

    # 约束条件
    constraints: List[str] = Field(default_factory=list, description="约束条件列表")
    forbidden_actions: List[str] = Field(default_factory=list, description="禁止行为列表")

    # 元数据
    source: Optional[str] = Field(None, description="设定来源")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # 向量嵌入 ID（用于 RAG 检索）
    embedding_id: Optional[str] = Field(None, description="Qdrant 向量 ID")

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: Any) -> LoreCategory:
        return normalize_lore_category(value)

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value: Any) -> LorePriority:
        return normalize_lore_priority(value)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "lore_001",
                "project_id": "proj_001",
                "title": "修真体系规则",
                "category": "world_rule",
                "priority": "constitutional",
                "content": "## 修真境界\n\n本世界修真分为九大境界：\n1. 炼气期\n2. 筑基期\n3. 金丹期\n...",
                "summary": "定义了本世界的修真体系和境界划分",
                "keywords": ["修真", "境界", "功法"],
                "tags": ["核心设定", "力量体系"],
                "constraints": ["高境界不能随意干涉低境界事务"],
                "forbidden_actions": ["禁止越级挑战超过两个大境界"],
            }
        }


class LoreReference(BaseModel):
    """设定引用模型（用于追踪设定被哪些内容引用）"""

    id: str = Field(..., description="引用唯一 ID")
    lore_id: str = Field(..., description="被引用的设定 ID")

    # 引用来源
    source_type: str = Field(..., description="引用来源类型：chapter/event/character/world")
    source_id: str = Field(..., description="引用来源 ID")

    # 引用上下文
    context: Optional[str] = Field(None, description="引用上下文")
    quote: Optional[str] = Field(None, description="引用的具体内容")

    created_at: datetime = Field(default_factory=datetime.utcnow)


class LoreConflict(BaseModel):
    """设定冲突模型（用于检测和记录设定冲突）"""

    id: str = Field(..., description="冲突唯一 ID")
    project_id: str = Field(..., description="所属项目 ID")

    # 冲突涉及的设定
    lore_id_1: str = Field(..., description="设定 1 ID")
    lore_id_2: str = Field(..., description="设定 2 ID")

    # 冲突描述
    conflict_type: str = Field(..., description="冲突类型：contradiction/overlap/ambiguity")
    description: str = Field(..., description="冲突描述")
    severity: str = Field(default="medium", description="严重程度：low/medium/high/critical")

    # 涉及的内容
    content_1: Optional[str] = Field(None, description="设定 1 相关内容")
    content_2: Optional[str] = Field(None, description="设定 2 相关内容")

    # 解决状态
    status: str = Field(default="unresolved", description="状态：unresolved/resolved/ignored")
    resolution: Optional[str] = Field(None, description="解决方案")
    resolved_at: Optional[datetime] = Field(None, description="解决时间")

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "conflict_001",
                "project_id": "proj_001",
                "lore_id_1": "lore_001",
                "lore_id_2": "lore_002",
                "conflict_type": "contradiction",
                "description": "修真境界数量与另一设定不一致",
                "severity": "high",
                "status": "unresolved",
            }
        }


class LoreSearchResult(BaseModel):
    """设定搜索结果模型"""

    id: str = Field(..., description="设定 ID")
    title: str = Field(..., description="设定标题")
    category: LoreCategory = Field(..., description="设定类别")
    priority: LorePriority = Field(..., description="设定优先级")
    summary: Optional[str] = Field(None, description="设定摘要")
    score: float = Field(..., description="相关性分数")
    keywords: List[str] = Field(default_factory=list, description="关键词")


class LoreValidationResult(BaseModel):
    """设定验证结果模型"""

    valid: bool = Field(..., description="是否通过验证")
    conflicts: List[LoreConflict] = Field(default_factory=list, description="检测到的冲突")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
