"""
统一 Agent 输入输出格式

所有 Agent 的输入输出都遵循这个统一格式，确保：
1. 跨 Agent 数据传递的一致性
2. 可追溯的执行历史
3. 标准化的错误处理
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field


class AgentIOStatus(str, Enum):
    """执行状态"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # 部分成功
    PENDING = "pending"  # 等待中（如等待用户干预）
    RETRY = "retry"      # 需要重试


class AgentMessageType(str, Enum):
    """Agent 消息类型"""
    # 执行相关
    EXECUTE = "execute"           # 执行请求
    RESULT = "result"             # 执行结果
    ERROR = "error"               # 错误报告

    # 协作相关
    REQUEST_INFO = "request_info" # 请求信息
    PROVIDE_INFO = "provide_info" # 提供信息
    BROADCAST = "broadcast"       # 广播消息

    # 干预相关
    INTERVENTION = "intervention" # 用户干预
    FEEDBACK = "feedback"         # 反馈

    # 控制相关
    PAUSE = "pause"               # 暂停
    RESUME = "resume"             # 恢复
    CANCEL = "cancel"             # 取消


class AgentInput(BaseModel):
    """统一的 Agent 输入格式"""

    # 核心字段
    task_type: str = Field(..., description="任务类型")
    instruction: str = Field(..., description="用户指令/任务描述")

    # 上下文
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="执行上下文（角色、设定、前文等）"
    )

    # 来源追踪
    source_agent: Optional[str] = Field(None, description="来源 Agent 类型")
    source_node_id: Optional[str] = Field(None, description="来源节点 ID")
    workflow_execution_id: Optional[str] = Field(None, description="工作流执行 ID")

    # 参数
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="执行参数"
    )

    # 配置
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="执行配置（温度、模型等）"
    )

    # 元数据
    request_id: str = Field(default_factory=lambda: f"req_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    timestamp: datetime = Field(default_factory=datetime.now)

    # 技能指定（可选）
    required_skills: List[str] = Field(
        default_factory=list,
        description="需要使用的技能 ID 列表"
    )


class AgentOutput(BaseModel):
    """统一的 Agent 输出格式"""

    # 核心字段
    status: AgentIOStatus = Field(..., description="执行状态")
    content: Any = Field(None, description="输出内容")

    # 结构化输出（按输出规范）
    structured_output: Dict[str, Any] = Field(
        default_factory=dict,
        description="结构化输出数据"
    )

    # 质量评估
    quality_score: Optional[float] = Field(None, description="质量评分 (0-1)")
    quality_check: Optional[Dict[str, Any]] = Field(None, description="质量检查结果")

    # 后续动作建议
    next_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="建议的后续动作"
    )

    # 追踪信息
    request_id: str = Field(..., description="对应的请求 ID")
    agent_type: str = Field(..., description="执行的 Agent 类型")
    execution_time_ms: Optional[int] = Field(None, description="执行耗时")

    # 错误信息
    error: Optional[str] = Field(None, description="错误信息")
    error_details: Optional[Dict[str, Any]] = Field(None, description="错误详情")

    # 重试信息
    retry_count: int = Field(default=0, description="重试次数")
    retry_recommended: bool = Field(default=False, description="是否建议重试")

    # 状态变更（用于全局状态更新）
    state_changes: Dict[str, Any] = Field(
        default_factory=dict,
        description="要更新的全局状态"
    )

    # 记忆更新（用于记忆系统）
    memory_updates: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="要添加的记忆条目"
    )

    # 元数据
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="其他元数据"
    )

    @classmethod
    def success(
        cls,
        content: Any,
        agent_type: str,
        request_id: str,
        **kwargs
    ) -> "AgentOutput":
        """创建成功输出"""
        return cls(
            status=AgentIOStatus.SUCCESS,
            content=content,
            agent_type=agent_type,
            request_id=request_id,
            **kwargs
        )

    @classmethod
    def failure(
        cls,
        error: str,
        agent_type: str,
        request_id: str,
        **kwargs
    ) -> "AgentOutput":
        """创建失败输出"""
        return cls(
            status=AgentIOStatus.FAILED,
            error=error,
            agent_type=agent_type,
            request_id=request_id,
            **kwargs
        )


class AgentMessage(BaseModel):
    """Agent 间消息格式"""

    # 消息头
    message_type: AgentMessageType = Field(..., description="消息类型")
    message_id: str = Field(
        default_factory=lambda: f"msg_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    )

    # 发送者
    sender_type: str = Field(..., description="发送者 Agent 类型")
    sender_id: Optional[str] = Field(None, description="发送者实例 ID")

    # 接收者
    receiver_type: Optional[str] = Field(None, description="接收者 Agent 类型（None 表示广播）")
    receiver_id: Optional[str] = Field(None, description="接收者实例 ID")

    # 内容
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="消息内容"
    )

    # 关联
    correlation_id: Optional[str] = Field(None, description="关联 ID（用于请求-响应匹配）")
    workflow_execution_id: Optional[str] = Field(None, description="工作流执行 ID")

    # 元数据
    timestamp: datetime = Field(default_factory=datetime.now)
    ttl: Optional[int] = Field(None, description="消息存活时间（秒）")


class SkillCallRequest(BaseModel):
    """技能调用请求"""

    skill_id: str = Field(..., description="技能 ID")
    skill_name: Optional[str] = Field(None, description="技能名称")

    # 输入
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="调用参数"
    )

    # 上下文
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="执行上下文"
    )

    # 追踪
    caller_agent: str = Field(..., description="调用者 Agent 类型")
    request_id: str = Field(..., description="请求 ID")

    # 配置
    use_memory: bool = Field(default=True, description="是否使用记忆")
    use_global_state: bool = Field(default=True, description="是否使用全局状态")
    check_threshold: bool = Field(default=True, description="是否检查评估阈值")


class SkillCallResult(BaseModel):
    """技能调用结果"""

    skill_id: str = Field(..., description="技能 ID")
    request_id: str = Field(..., description="对应的请求 ID")

    # 结果
    success: bool = Field(..., description="是否成功")
    output: Optional[Dict[str, Any]] = Field(None, description="输出结果")

    # 评估
    score: Optional[float] = Field(None, description="评估分数")
    passed_threshold: bool = Field(default=True, description="是否通过阈值")

    # 错误
    error: Optional[str] = Field(None, description="错误信息")

    # 重试
    retry_count: int = Field(default=0, description="重试次数")

    # 性能
    execution_time_ms: int = Field(default=0, description="执行耗时")

    # 状态变更
    state_changes: Dict[str, Any] = Field(
        default_factory=dict,
        description="产生的状态变更"
    )


# ==================== 类型别名 ====================

# 输入输出类型变量，用于泛型
InputT = TypeVar('InputT', bound=AgentInput)
OutputT = TypeVar('OutputT', bound=AgentOutput)


# ==================== 验证函数 ====================

def validate_output_against_spec(
    output: Dict[str, Any],
    output_spec: List[Dict[str, Any]]
) -> tuple[bool, List[str]]:
    """
    根据 output_spec 验证输出

    Args:
        output: 输出数据
        output_spec: 输出规范

    Returns:
        tuple[bool, List[str]]: (是否有效, 错误列表)
    """
    errors = []

    for spec in output_spec:
        field_name = spec.get("name")
        required = spec.get("required", True)

        if required and field_name not in output:
            errors.append(f"缺少必需字段: {field_name}")

        elif field_name in output:
            # 类型检查
            expected_type = spec.get("type", "string")
            actual_value = output[field_name]

            type_valid = _check_type(actual_value, expected_type)
            if not type_valid:
                errors.append(f"字段 {field_name} 类型错误: 期望 {expected_type}")

    return len(errors) == 0, errors


def _check_type(value: Any, expected_type: str) -> bool:
    """检查值是否符合期望类型"""
    type_mapping = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    expected_python_type = type_mapping.get(expected_type)
    if expected_python_type is None:
        return True  # 未知类型，跳过检查

    return isinstance(value, expected_python_type)
