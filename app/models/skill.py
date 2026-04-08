"""
Agent Skill 数据模型
Agent 可以生成 skill 并保存到全局库中，用户可将 skill 分配给特定项目的特定 Agent
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillType(str, Enum):
    """Skill 类型"""
    PROMPT = "prompt"        # 提示词模板
    FUNCTION = "function"    # Python 函数
    WORKFLOW = "workflow"    # 多步骤工作流
    KNOWLEDGE = "knowledge"  # 知识片段


class SkillStatus(str, Enum):
    """Skill 状态"""
    DRAFT = "draft"          # 草稿
    ACTIVE = "active"        # 激活
    DEPRECATED = "deprecated" # 已废弃


class SkillParameter(BaseModel):
    """Skill 参数定义"""
    name: str = Field(..., description="参数名称")
    type: str = Field(default="string", description="参数类型: string, number, boolean, array, object")
    description: str = Field(default="", description="参数描述")
    default: Optional[Any] = Field(default=None, description="默认值")
    required: bool = Field(default=False, description="是否必填")
    options: Optional[List[Any]] = Field(default=None, description="可选值列表")


class Skill(BaseModel):
    """Skill 模型"""
    id: str = Field(..., description="Skill ID")
    name: str = Field(..., description="Skill 名称")
    description: str = Field(default="", description="Skill 描述")
    skill_type: SkillType = Field(..., description="Skill 类型")

    # 内容定义
    prompt_template_id: Optional[str] = Field(default=None, description="关联的 PromptTemplate ID")
    function_code: Optional[str] = Field(default=None, description="Function 类型：Python 代码")
    workflow_steps: Optional[List[Dict[str, Any]]] = Field(default=None, description="Workflow 类型：工作流步骤")
    knowledge_content: Optional[str] = Field(default=None, description="Knowledge 类型：知识内容")

    # 参数定义
    parameters: List[SkillParameter] = Field(default_factory=list, description="参数列表")

    # 元数据
    tags: List[str] = Field(default_factory=list, description="标签")
    version: str = Field(default="1.0.0", description="版本号")
    status: SkillStatus = Field(default=SkillStatus.DRAFT, description="状态")

    # 创建来源
    creator_project_id: Optional[str] = Field(default=None, description="创建项目 ID")
    creator_agent_id: Optional[str] = Field(default=None, description="创建 Agent ID")
    creator_user_id: Optional[str] = Field(default=None, description="创建用户 ID")

    # 使用统计
    usage_count: int = Field(default=0, description="使用次数")
    last_used_at: Optional[datetime] = Field(default=None, description="最后使用时间")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class SkillAssignment(BaseModel):
    """Skill 分配关系"""
    id: str = Field(..., description="分配 ID")
    skill_id: str = Field(..., description="Skill ID")
    project_id: str = Field(..., description="项目 ID")
    agent_id: str = Field(..., description="Agent ID (character_id)")

    # 分配配置
    custom_parameters: Optional[Dict[str, Any]] = Field(default=None, description="自定义参数覆盖")
    priority: int = Field(default=0, description="执行优先级")

    # 分配信息
    assigned_by: str = Field(default="user", description="分配者: user/system")
    assigned_at: datetime = Field(default_factory=datetime.now, description="分配时间")


class SkillExecutionLog(BaseModel):
    """Skill 执行日志"""
    id: str = Field(..., description="日志 ID")
    skill_id: str = Field(..., description="Skill ID")
    project_id: Optional[str] = Field(default=None, description="项目 ID")
    agent_id: Optional[str] = Field(default=None, description="Agent ID")

    # 执行数据
    input_params: Dict[str, Any] = Field(default_factory=dict, description="输入参数")
    output_result: Optional[str] = Field(default=None, description="输出结果")
    success: bool = Field(default=True, description="是否成功")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    execution_time_ms: Optional[int] = Field(default=None, description="执行耗时(毫秒)")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class CreateSkillDTO(BaseModel):
    """创建 Skill DTO"""
    name: str
    description: str = ""
    skill_type: SkillType
    prompt_template_id: Optional[str] = None
    function_code: Optional[str] = None
    workflow_steps: Optional[List[Dict[str, Any]]] = None
    knowledge_content: Optional[str] = None
    parameters: List[SkillParameter] = []
    tags: List[str] = []
    creator_project_id: Optional[str] = None
    creator_agent_id: Optional[str] = None
    creator_user_id: Optional[str] = None


class UpdateSkillDTO(BaseModel):
    """更新 Skill DTO"""
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_template_id: Optional[str] = None
    function_code: Optional[str] = None
    workflow_steps: Optional[List[Dict[str, Any]]] = None
    knowledge_content: Optional[str] = None
    parameters: Optional[List[SkillParameter]] = None
    tags: Optional[List[str]] = None
    version: Optional[str] = None
    status: Optional[SkillStatus] = None


class AssignSkillDTO(BaseModel):
    """分配 Skill DTO"""
    skill_id: str
    project_id: str
    agent_id: str
    custom_parameters: Optional[Dict[str, Any]] = None
    priority: int = 0


class ExecuteSkillDTO(BaseModel):
    """执行 Skill DTO"""
    skill_id: str
    project_id: Optional[str] = None
    agent_id: Optional[str] = None
    parameters: Dict[str, Any] = {}


class SkillTestResult(BaseModel):
    """Skill 测试结果"""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
