"""
Agent Skill 数据模型

Skill 是 Agent 可以执行的独立能力单元，可以被多个 Agent 共享。
每个 Skill 定义了执行该能力所需的 Prompt 模板、输入输出规范等。

特点：
- 可持久化存储到数据库
- 可在 Agent Skills 界面管理
- 可分配给 Agent 模板作为 skill 插槽
- 通用技能可被多个 Agent 共享
"""

from datetime import datetime
from enum import Enum
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.agent_output_contract import OutputContractMode


class SkillType(str, Enum):
    """Skill 类型"""
    PROMPT = "prompt"        # 提示词模板（调用LLM生成）
    FUNCTION = "function"    # Python 函数（直接执行代码）
    WORKFLOW = "workflow"    # 多步骤工作流
    KNOWLEDGE = "knowledge"  # 知识片段（提供上下文）


class SkillCategory(str, Enum):
    """Skill 类别（用于分类管理）"""

    # 写作相关
    WRITING = "writing"               # 内容写作
    EDITING = "editing"               # 编辑修改
    STYLE = "style"                   # 风格处理

    # 剧情相关
    PLOTTING = "plotting"             # 剧情规划
    PACING = "pacing"                 # 节奏控制
    CONFLICT = "conflict"             # 冲突设计

    # 角色相关
    CHARACTER = "character"           # 角色塑造
    DIALOGUE = "dialogue"             # 对话生成
    OOC_CHECK = "ooc_check"           # OOC检查

    # 伏笔相关
    FORESHADOWING = "foreshadowing"   # 伏笔管理
    HOOK = "hook"                     # 钩子/悬念

    # 评估相关
    EVALUATION = "evaluation"         # 质量评估
    READER_SIM = "reader_sim"         # 读者模拟

    # 世界观相关
    WORLD_BUILDING = "world_building" # 世界观构建
    SETTING = "setting"               # 设定管理

    # 分析相关
    ANALYSIS = "analysis"             # 内容分析
    SUMMARY = "summary"               # 内容摘要

    # 协作相关
    DISCUSSION = "discussion"         # 集体讨论
    PERFORMANCE = "performance"       # 角色演绎

    # 通用
    GENERAL = "general"               # 通用技能


class SkillStatus(str, Enum):
    """Skill 状态"""
    DRAFT = "draft"          # 草稿
    ACTIVE = "active"        # 激活
    DEPRECATED = "deprecated" # 已废弃


class SkillLoadMode(str, Enum):
    """Skill 加载模式"""
    CORE = "core"           # 核心层：始终加载到上下文
    ON_DEMAND = "on_demand" # 按需层：根据场景关键词动态加载


class SkillPriority(int, Enum):
    """Skill 优先级"""
    CRITICAL = 100    # 核心必需
    HIGH = 80         # 高优先级
    NORMAL = 50       # 正常
    LOW = 30          # 低优先级
    OPTIONAL = 10     # 可选


class SkillParameter(BaseModel):
    """Skill 参数定义"""
    name: str = Field(..., description="参数名称")
    type: str = Field(default="string", description="参数类型: string, number, boolean, array, object")
    description: str = Field(default="", description="参数描述")
    default: Optional[Any] = Field(default=None, description="默认值")
    required: bool = Field(default=False, description="是否必填")
    options: Optional[List[Any]] = Field(default=None, description="可选值列表")
    validation: Optional[Dict[str, Any]] = Field(default=None, description="验证规则")


class SkillOutputSpec(BaseModel):
    """Skill 输出字段规范"""
    name: str = Field(..., description="输出字段名")
    type: str = Field(default="string", description="字段类型")
    description: str = Field(default="", description="字段描述")
    required: bool = Field(default=True, description="是否必需输出")


class EvaluationThreshold(BaseModel):
    """评估阈值配置"""
    min_score: float = Field(default=0.7, ge=0, le=1, description="最低通过分数")
    blocking: bool = Field(default=False, description="未达标时是否阻断流程")
    auto_retry: bool = Field(default=True, description="未达标时是否自动重试")
    max_retries: int = Field(default=2, ge=0, le=5, description="最大重试次数")
    retry_strategy: str = Field(default="improve", description="重试策略: improve=改进输出, regenerate=重新生成")

    # 评估维度
    dimensions: List[str] = Field(
        default_factory=lambda: ["quality", "consistency", "stance"],
        description="评估维度列表"
    )
    dimension_weights: Dict[str, float] = Field(
        default_factory=lambda: {"quality": 0.4, "consistency": 0.3, "stance": 0.3},
        description="各维度权重"
    )


class SubSkillReference(BaseModel):
    """子技能引用"""
    skill_id: str = Field(..., description="子技能ID")
    slot_name: str = Field(default="", description="插槽名称")
    execution_order: int = Field(default=0, description="执行顺序")
    pass_output_to: Optional[str] = Field(default=None, description="将输出传递给下一个子技能的参数名")
    is_required: bool = Field(default=True, description="是否必需执行")


class Skill(BaseModel):
    """Skill 模型"""

    id: str = Field(..., description="Skill ID")
    name: str = Field(..., description="Skill 名称")
    description: str = Field(default="", description="详细描述")

    # 类型和分类
    skill_type: SkillType = Field(..., description="Skill 类型")
    category: SkillCategory = Field(default=SkillCategory.GENERAL, description="Skill 类别")
    tags: List[str] = Field(default_factory=list, description="标签")

    # 适用范围
    applicable_agent_types: List[str] = Field(
        default_factory=list,
        description="适用的 Agent 类型列表，空列表表示所有 Agent 都可用"
    )

    # 内容定义
    prompt_template: Optional[str] = Field(
        default=None,
        description="Prompt 模板内容（可直接内嵌）"
    )
    prompt_template_id: Optional[str] = Field(default=None, description="关联的 PromptTemplate ID")
    function_code: Optional[str] = Field(default=None, description="Function 类型：Python 代码")
    workflow_steps: Optional[List[Dict[str, Any]]] = Field(default=None, description="Workflow 类型：工作流步骤")
    knowledge_content: Optional[str] = Field(default=None, description="Knowledge 类型：知识内容")

    # 参数和输出
    parameters: List[SkillParameter] = Field(default_factory=list, description="输入参数列表")
    output_spec: List[SkillOutputSpec] = Field(default_factory=list, description="输出字段规范")

    # 执行配置
    temperature: float = Field(default=0.7, ge=0, le=2, description="LLM 温度参数")
    max_tokens: Optional[int] = Field(default=None, description="最大 token 数")
    timeout: int = Field(default=60, ge=1, le=600, description="超时时间（秒）")
    retry_count: int = Field(default=0, ge=0, le=5, description="重试次数")

    # 优先级和状态
    priority: int = Field(default=SkillPriority.NORMAL, description="优先级")
    status: SkillStatus = Field(default=SkillStatus.ACTIVE, description="状态")
    is_system: bool = Field(default=False, description="是否系统内置")
    is_enabled: bool = Field(default=True, description="是否启用")
    is_composable: bool = Field(
        default=True,
        description="是否可组合（多个 Skill 可以在同一执行中一起使用）"
    )

    # 加载模式
    load_mode: SkillLoadMode = Field(
        default=SkillLoadMode.ON_DEMAND,
        description="加载模式：core=始终加载, on_demand=按需加载"
    )
    trigger_keywords: List[str] = Field(
        default_factory=list,
        description="触发关键词（按需加载时匹配场景关键词）"
    )
    trigger_scenes: List[str] = Field(
        default_factory=list,
        description="触发场景类型（如：战斗、对话、谈判）"
    )

    # 子技能（技能分解）
    sub_skills: List[SubSkillReference] = Field(
        default_factory=list,
        description="子技能列表（用于复杂技能分解）"
    )
    parent_skill_id: Optional[str] = Field(
        default=None,
        description="父技能ID（如果是子技能）"
    )

    # 评估配置
    evaluation_threshold: Optional[EvaluationThreshold] = Field(
        default=None,
        description="评估阈值配置（用于质量检查类技能）"
    )
    on_failure_action: str = Field(
        default="continue",
        description="失败时动作: continue=继续, retry=重试, abort=中止流程"
    )

    # 记忆集成
    use_agent_memory: bool = Field(
        default=False,
        description="是否使用Agent长期记忆"
    )
    memory_types: List[str] = Field(
        default_factory=list,
        description="要加载的记忆类型: decision/observation/fact"
    )

    # 全局状态
    reads_global_state: List[str] = Field(
        default_factory=list,
        description="需要读取的全局状态键"
    )
    writes_global_state: List[str] = Field(
        default_factory=list,
        description="要写入的全局状态键"
    )

    # 创建来源
    creator_project_id: Optional[str] = Field(default=None, description="创建项目 ID")
    creator_agent_id: Optional[str] = Field(default=None, description="创建 Agent ID")
    creator_user_id: Optional[str] = Field(default=None, description="创建用户 ID")

    # 元数据
    version: str = Field(default="1.0.0", description="版本号")
    author: str = Field(default="system", description="作者")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="使用示例")

    # 使用统计
    usage_count: int = Field(default=0, description="使用次数")
    last_used_at: Optional[datetime] = Field(default=None, description="最后使用时间")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class SkillAssignment(BaseModel):
    """Skill 分配到 Agent 模板的关系"""

    id: str = Field(..., description="分配 ID")
    skill_id: str = Field(..., description="Skill ID")
    agent_type: str = Field(..., description="Agent 类型")

    # 分配配置
    slot_name: str = Field(default="", description="插槽名称")
    custom_parameters: Optional[Dict[str, Any]] = Field(default=None, description="自定义参数覆盖")
    variable_overrides: Dict[str, Any] = Field(default_factory=dict, description="变量覆盖")
    priority: int = Field(default=50, description="执行优先级")

    # 执行条件
    execution_condition: Optional[str] = Field(default=None, description="执行条件表达式")
    is_enabled: bool = Field(default=True, description="是否启用")
    is_required: bool = Field(default=False, description="是否必需")

    # 加载模式（可覆盖Skill的默认设置）
    load_mode: Optional[SkillLoadMode] = Field(
        default=None,
        description="加载模式覆盖（None表示使用Skill的默认设置）"
    )
    trigger_keywords: List[str] = Field(
        default_factory=list,
        description="触发关键词覆盖"
    )

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
    token_usage: Optional[Dict[str, int]] = Field(default=None, description="Token 使用量")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


# ==================== DTOs ====================

class CreateSkillDTO(BaseModel):
    """创建 Skill DTO"""
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    skill_type: SkillType
    category: SkillCategory = SkillCategory.GENERAL
    tags: List[str] = []
    applicable_agent_types: List[str] = []

    prompt_template: Optional[str] = None
    prompt_template_id: Optional[str] = None
    function_code: Optional[str] = None
    workflow_steps: Optional[List[Dict[str, Any]]] = None
    knowledge_content: Optional[str] = None

    parameters: List[SkillParameter] = []
    output_spec: List[SkillOutputSpec] = []

    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 60

    priority: int = SkillPriority.NORMAL
    is_composable: bool = True
    examples: List[Dict[str, Any]] = []

    # 加载模式
    load_mode: SkillLoadMode = SkillLoadMode.ON_DEMAND
    trigger_keywords: List[str] = []
    trigger_scenes: List[str] = []

    # 子技能
    sub_skills: List[SubSkillReference] = []
    parent_skill_id: Optional[str] = None

    # 评估配置
    evaluation_threshold: Optional[EvaluationThreshold] = None
    on_failure_action: str = "continue"

    # 记忆集成
    use_agent_memory: bool = False
    memory_types: List[str] = []

    # 全局状态
    reads_global_state: List[str] = []
    writes_global_state: List[str] = []

    creator_project_id: Optional[str] = None
    creator_agent_id: Optional[str] = None
    creator_user_id: Optional[str] = None


class UpdateSkillDTO(BaseModel):
    """更新 Skill DTO"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[SkillCategory] = None
    tags: Optional[List[str]] = None
    applicable_agent_types: Optional[List[str]] = None

    prompt_template: Optional[str] = None
    prompt_template_id: Optional[str] = None
    function_code: Optional[str] = None
    workflow_steps: Optional[List[Dict[str, Any]]] = None
    knowledge_content: Optional[str] = None

    parameters: Optional[List[SkillParameter]] = None
    output_spec: Optional[List[SkillOutputSpec]] = None

    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None

    priority: Optional[int] = None
    status: Optional[SkillStatus] = None
    is_enabled: Optional[bool] = None
    is_composable: Optional[bool] = None
    examples: Optional[List[Dict[str, Any]]] = None

    # 加载模式
    load_mode: Optional[SkillLoadMode] = None
    trigger_keywords: Optional[List[str]] = None
    trigger_scenes: Optional[List[str]] = None

    # 子技能
    sub_skills: Optional[List[SubSkillReference]] = None
    parent_skill_id: Optional[str] = None

    # 评估配置
    evaluation_threshold: Optional[EvaluationThreshold] = None
    on_failure_action: Optional[str] = None

    # 记忆集成
    use_agent_memory: Optional[bool] = None
    memory_types: Optional[List[str]] = None

    # 全局状态
    reads_global_state: Optional[List[str]] = None
    writes_global_state: Optional[List[str]] = None


class AssignSkillDTO(BaseModel):
    """分配 Skill 到 Agent 模板 DTO"""
    skill_id: str
    agent_type: str
    slot_name: str = ""
    custom_parameters: Optional[Dict[str, Any]] = None
    variable_overrides: Dict[str, Any] = {}
    priority: int = 50
    execution_condition: Optional[str] = None
    is_enabled: bool = True
    is_required: bool = False

    # 加载模式
    load_mode: Optional[SkillLoadMode] = None
    trigger_keywords: List[str] = []


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
    token_usage: Optional[Dict[str, int]] = None

    mode: Optional[OutputContractMode] = None
    structured_output: Optional[Any] = None
    text_output: Optional[str] = None
    contract_id: Optional[str] = None
    schema_name: Optional[str] = None
    schema_version: Optional[str] = None

    @model_validator(mode="after")
    def _sync_output_fields(self):
        if self.output is not None:
            if self.text_output is None:
                self.text_output = self.output
            if self.structured_output is None:
                try:
                    parsed = json.loads(self.output)
                    if isinstance(parsed, (dict, list)):
                        self.structured_output = parsed
                        if self.mode is None:
                            self.mode = OutputContractMode.STRICT
                except (TypeError, json.JSONDecodeError):
                    pass
            if self.mode is None:
                self.mode = OutputContractMode.TEXT
        elif self.structured_output is not None:
            self.output = json.dumps(self.structured_output, ensure_ascii=False)
            if self.mode is None:
                self.mode = OutputContractMode.STRICT
        elif self.text_output is not None:
            self.output = self.text_output
            if self.mode is None:
                self.mode = OutputContractMode.TEXT
        return self

    def get_structured_output(self) -> Optional[Any]:
        return self.structured_output

    def require_structured_output(self) -> Any:
        if self.structured_output is None:
            raise ValueError("Skill 未返回结构化输出")
        return self.structured_output

    def require_structured_dict(self) -> Dict[str, Any]:
        data = self.require_structured_output()
        if not isinstance(data, dict):
            raise ValueError("Skill 结构化输出不是对象")
        return data
