"""
Setting Agent 数据模型
持续的设定管理者，负责管理项目的 Lore RAG
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SettingAgentMode(str, Enum):
    """Setting Agent 运行模式"""
    BOOTSTRAP = "bootstrap"  # 初始化模式 - 创建新项目设定
    MANAGEMENT = "management"  # 管理模式 - 维护现有设定
    CONFLICT_RESOLUTION = "conflict_resolution"  # 冲突解决模式 - 处理设定冲突


class SettingChangeType(str, Enum):
    """设定变更类型"""
    ADD = "add"  # 添加新设定
    MODIFY = "modify"  # 修改现有设定
    DELETE = "delete"  # 删除设定
    MERGE = "merge"  # 合并设定


class ConflictSeverity(str, Enum):
    """冲突严重程度"""
    LOW = "low"  # 轻微冲突 - 可忽略
    MEDIUM = "medium"  # 中等冲突 - 需要注意
    HIGH = "high"  # 严重冲突 - 必须解决
    CRITICAL = "critical"  # 致命冲突 - 阻塞操作


class ConflictResolutionStatus(str, Enum):
    """冲突解决状态"""
    PENDING = "pending"  # 待解决
    NEGOTIATING = "negotiating"  # 协商中
    RESOLVED = "resolved"  # 已解决
    ESCALATED = "escalated"  # 已升级（需要人工介入）


class SettingConflict(BaseModel):
    """设定冲突模型"""
    id: str = Field(default_factory=lambda: f"conflict_{datetime.now().strftime('%Y%m%d%H%M%S')}")

    # 冲突类型
    conflict_type: str  # name_collision, semantic_conflict, constitutional_violation
    description: str
    severity: ConflictSeverity

    # 涉及的设定
    existing_lore_id: Optional[str] = None
    existing_lore_title: Optional[str] = None
    new_lore_id: Optional[str] = None
    new_lore_title: Optional[str] = None

    # 解决状态
    status: ConflictResolutionStatus = ConflictResolutionStatus.PENDING
    resolution_suggestions: List[str] = Field(default_factory=list)
    selected_resolution: Optional[str] = None

    # 时间戳
    detected_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None


class SettingChangeRequest(BaseModel):
    """设定变更请求模型"""
    id: str = Field(default_factory=lambda: f"change_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    project_id: str

    # 变更信息
    change_type: SettingChangeType
    target_lore_id: Optional[str] = None  # 修改/删除时需要

    # 新设定内容
    new_lore_data: Optional[Dict[str, Any]] = None

    # 冲突检测结果
    conflicts: List[SettingConflict] = Field(default_factory=list)
    has_conflicts: bool = False

    # 用户意图
    user_intent: Optional[str] = None  # 用户对这次变更的描述

    # 状态
    status: str = "pending"  # pending, conflict_detected, resolved, executed, rejected

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None


class SettingAgentSession(BaseModel):
    """Setting Agent 持久化会话模型"""
    id: str = Field(default_factory=lambda: f"sas_{uuid4().hex[:12]}")
    project_id: str

    # 运行模式
    mode: SettingAgentMode = SettingAgentMode.MANAGEMENT

    # 对话历史
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)

    # 当前请求和待解决冲突
    current_request: Optional[SettingChangeRequest] = None
    pending_conflicts: List[SettingConflict] = Field(default_factory=list)

    # 缓存上一轮提取的 pending 数据（用于"保存"指令跳过LLM）
    cached_pending_lores: List[Dict[str, Any]] = Field(default_factory=list)
    cached_pending_characters: List[Dict[str, Any]] = Field(default_factory=list)
    cached_pending_hooks: List[Dict[str, Any]] = Field(default_factory=list)

    # 增量上下文：记录是否已加载过全量项目上下文
    full_context_loaded: bool = False
    cached_context_sections: Dict[str, str] = Field(default_factory=dict)

    # 状态
    is_active: bool = True

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_activity_at: datetime = Field(default_factory=datetime.now)


class LoreKnowledgeIndex(BaseModel):
    """Lore 知识索引模型"""
    project_id: str

    # 关键词索引
    keyword_index: Dict[str, List[str]] = Field(default_factory=dict)  # keyword -> lore_ids

    # 实体索引
    entity_index: Dict[str, List[str]] = Field(default_factory=dict)  # entity_name -> lore_ids

    # 宪法级规则缓存
    constitutional_rules: List[Dict[str, Any]] = Field(default_factory=list)

    # 最后更新时间
    last_updated: datetime = Field(default_factory=datetime.now)

    def add_keyword(self, keyword: str, lore_id: str):
        """添加关键词索引"""
        if keyword not in self.keyword_index:
            self.keyword_index[keyword] = []
        if lore_id not in self.keyword_index[keyword]:
            self.keyword_index[keyword].append(lore_id)

    def add_entity(self, entity: str, lore_id: str):
        """添加实体索引"""
        if entity not in self.entity_index:
            self.entity_index[entity] = []
        if entity not in self.entity_index[entity]:
            self.entity_index[entity].append(lore_id)

    def search_by_keyword(self, keyword: str) -> List[str]:
        """通过关键词搜索"""
        return self.keyword_index.get(keyword, [])

    def search_by_entity(self, entity: str) -> List[str]:
        """通过实体搜索"""
        return self.entity_index.get(entity, [])


class SettingSummary(BaseModel):
    """设定摘要模型"""
    project_id: str

    # 统计信息
    total_lore_count: int = 0
    by_category: Dict[str, int] = Field(default_factory=dict)
    by_priority: Dict[str, int] = Field(default_factory=dict)

    # 宪法级规则
    constitutional_rules: List[str] = Field(default_factory=list)

    # 关键实体
    key_entities: List[str] = Field(default_factory=list)

    # 最近变更
    recent_changes: List[Dict[str, Any]] = Field(default_factory=list)

    # 待处理冲突
    pending_conflicts: int = 0

    # 生成时间
    generated_at: datetime = Field(default_factory=datetime.now)


class NegotiationMessage(BaseModel):
    """协商消息模型"""
    role: str  # user, assistant
    content: str
    conflict_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class NegotiationSession(BaseModel):
    """协商会话模型"""
    id: str
    conflict_id: str
    project_id: str

    # 协商历史
    messages: List[NegotiationMessage] = Field(default_factory=list)

    # 状态
    status: ConflictResolutionStatus = ConflictResolutionStatus.NEGOTIATING

    # 最终决定
    final_decision: Optional[str] = None

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
