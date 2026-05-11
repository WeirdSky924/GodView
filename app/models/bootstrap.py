"""
Bootstrap 会话和状态模型
GodView v4 新增：管理项目初始化流程的状态机
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class BootstrapStage(str, Enum):
    """Bootstrap 阶段枚举"""

    DRAFT = "draft"  # 草稿
    COLLECTING_SETTING = "collecting_setting"  # 收集设定
    OUTLINE_INGESTED = "outline_ingested"  # 大纲已读取
    SEED_EXTRACTED = "seed_extracted"  # 种子已提取
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # 等待确认
    BOOTSTRAPPING_WORLD = "bootstrapping_world"  # 创建世界中
    BOOTSTRAPPING_AGENTS = "bootstrapping_agents"  # 初始化Agent中
    BOOTSTRAPPING_CHARACTERS = "bootstrapping_characters"  # 创建角色中
    CREATING_SNAPSHOT = "creating_initial_snapshot"  # 创建初始快照
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败
    NEEDS_REVISION = "needs_revision"  # 需要修订


class BootstrapSession(BaseModel):
    """Bootstrap 会话模型

    记录项目初始化流程的完整状态
    """

    id: str = Field(..., description="会话ID")
    project_id: str = Field(..., description="项目ID")

    # 状态信息
    status: BootstrapStage = Field(default=BootstrapStage.DRAFT, description="当前状态")
    current_stage: BootstrapStage = Field(default=BootstrapStage.DRAFT, description="当前阶段")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="进度(0-1)")

    # 会话数据
    setting_agent_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="设定Agent对话历史"
    )
    extracted_seed: Dict[str, Any] = Field(
        default_factory=dict, description="提取的结构化种子"
    )
    confirmed_seed: Dict[str, Any] = Field(
        default_factory=dict, description="用户确认的种子"
    )

    # 错误处理
    error_message: Optional[str] = Field(None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(None, description="完成时间")


class BootstrapMessage(BaseModel):
    """Bootstrap 消息模型（用于与 SettingAgent 通信）"""

    role: str = Field(..., description="消息角色：user/assistant")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="消息元数据")


class BootstrapProgressUpdate(BaseModel):
    """Bootstrap 进度更新模型"""

    session_id: str = Field(..., description="会话ID")
    stage: BootstrapStage = Field(..., description="当前阶段")
    progress: float = Field(..., ge=0.0, le=1.0, description="进度")
    message: Optional[str] = Field(None, description="进度消息")
    estimated_time_remaining: Optional[float] = Field(None, description="预计剩余时间（秒）")


class StartBootstrapRequest(BaseModel):
    """启动 Bootstrap 请求"""

    project_id: str = Field(..., description="项目ID")
    initial_message: Optional[str] = Field(
        None, description="初始消息（可选，用于直接开始对话）"
    )
    request_id: Optional[str] = Field(None, description="幂等请求ID")


class SendMessageRequest(BaseModel):
    """发送消息到 SettingAgent 请求"""

    message: str = Field(..., min_length=1, description="消息内容")
    session_id: str = Field(..., description="会话ID")
    project_id: Optional[str] = Field(None, description="项目ID（用于会话恢复）")
    assistant_session_id: Optional[str] = Field(None, description="Assistant Context 会话ID")
    request_id: Optional[str] = Field(None, description="幂等请求ID")


class UploadOutlineRequest(BaseModel):
    """上传大纲请求"""

    content: str = Field(..., min_length=1, description="大纲内容")
    source_type: str = Field(default="pasted_text", description="来源类型：pasted_text/file_txt/file_md")
    session_id: str = Field(..., description="会话ID")


class ConfirmSeedRequest(BaseModel):
    """确认种子请求"""

    seed_data: Dict[str, Any] = Field(..., description="种子数据")
    session_id: str = Field(..., description="会话ID")


class RunBootstrapRequest(BaseModel):
    """执行 Bootstrap 请求"""

    session_id: str = Field(..., description="会话ID")
    request_id: Optional[str] = Field(None, description="幂等请求ID")


class ReviseSeedRequest(BaseModel):
    """修订种子请求"""

    feedback: str = Field(..., min_length=1, description="修订反馈")
    session_id: str = Field(..., description="会话ID")