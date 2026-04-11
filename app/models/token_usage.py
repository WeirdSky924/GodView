"""
Token 使用记录模型

用于追踪项目的 Token 消耗和成本
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TokenType(str, Enum):
    """Token 类型"""
    INPUT = "input"
    OUTPUT = "output"


class UsageCategory(str, Enum):
    """使用场景分类"""
    BOOTSTRAP = "bootstrap"          # 项目初始化
    CHARACTER = "character"          # 角色生成
    WORLD = "world"                  # 世界生成
    PLOT = "plot"                    # 剧情生成
    CHAPTER = "chapter"              # 章节生成
    HOOK = "hook"                    # 伏笔管理
    DIRECTOR = "director"            # 导演模式
    SETTING_AGENT = "setting_agent"  # 设定代理
    SKILL = "skill"                  # Skill 执行
    RAG = "rag"                      # RAG 检索
    PLANNING = "planning"            # 分段规划
    OTHER = "other"                  # 其他


# 模型价格表（每 1M tokens 价格，美元）
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    # Anthropic
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-latest": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku-latest": {"input": 0.8, "output": 4.0},
    "claude-3-opus-latest": {"input": 15.0, "output": 75.0},
    # 智谱
    "glm-4-plus": {"input": 0.7, "output": 0.7},
    "glm-4-0520": {"input": 0.7, "output": 0.7},
    "glm-4-air": {"input": 0.1, "output": 0.1},
    "glm-4-flash": {"input": 0.0, "output": 0.0},
    # 通义
    "qwen-max": {"input": 0.5, "output": 2.0},
    "qwen-plus": {"input": 0.08, "output": 0.3},
    "qwen-turbo": {"input": 0.02, "output": 0.08},
    # DeepSeek
    "deepseek-chat": {"input": 0.07, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # 月之暗面
    "moonshot-v1-8k": {"input": 0.15, "output": 0.15},
    "moonshot-v1-32k": {"input": 0.3, "output": 0.3},
    "moonshot-v1-128k": {"input": 0.6, "output": 0.6},
    # 百川
    "Baichuan4": {"input": 0.15, "output": 0.15},
    "Baichuan3-Turbo": {"input": 0.05, "output": 0.05},
    # 文心
    "ernie-4.0-8k": {"input": 0.18, "output": 0.18},
    "ernie-3.5-8k": {"input": 0.04, "output": 0.04},
    # Yi
    "yi-large": {"input": 0.25, "output": 0.25},
    "yi-medium": {"input": 0.03, "output": 0.03},
    # MiniMax
    "abab6.5-chat": {"input": 0.03, "output": 0.03},
    "abab5.5-chat": {"input": 0.02, "output": 0.02},
    # 默认（未知模型）
    "default": {"input": 1.0, "output": 3.0},
}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """
    计算 Token 消耗成本（美元）

    Args:
        model: 模型名称
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数

    Returns:
        估算成本（美元）
    """
    # 查找模型价格，使用模糊匹配
    pricing = MODEL_PRICING.get("default")
    for model_key in MODEL_PRICING:
        if model_key.lower() in model.lower() or model.lower() in model_key.lower():
            pricing = MODEL_PRICING[model_key]
            break

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return round(input_cost + output_cost, 6)


class TokenUsageRecord(BaseModel):
    """Token 使用记录"""
    id: Optional[str] = None
    project_id: str
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)
    provider: str                          # LLM 提供商
    model: str                             # 模型名称
    category: UsageCategory                # 使用场景
    agent_name: Optional[str] = None       # Agent 名称
    session_id: Optional[str] = None       # 会话 ID
    chapter_id: Optional[str] = None       # 章节 ID
    character_id: Optional[str] = None     # 角色 ID
    estimated_cost: float = 0.0            # 估算成本（美元）
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class TokenUsageSummary(BaseModel):
    """Token 使用摘要"""
    total_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    record_count: int = 0

    # 按场景分组
    by_category: Dict[str, int] = Field(default_factory=dict)

    # 按模型分组
    by_model: Dict[str, int] = Field(default_factory=dict)


class ProjectTokenStats(BaseModel):
    """项目 Token 统计"""
    project_id: str
    project_name: str
    total_tokens: int = 0
    total_cost: float = 0.0
    today_tokens: int = 0
    today_cost: float = 0.0
    week_tokens: int = 0
    week_cost: float = 0.0
    month_tokens: int = 0
    month_cost: float = 0.0
    updated_at: datetime = Field(default_factory=datetime.now)


class DailyTokenStats(BaseModel):
    """每日 Token 统计"""
    date: str                              # YYYY-MM-DD
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    record_count: int = 0


# DTO 类型
class CreateTokenUsageDTO(BaseModel):
    """创建 Token 使用记录"""
    project_id: str
    input_tokens: int
    output_tokens: int
    provider: str
    model: str
    category: UsageCategory
    agent_name: Optional[str] = None
    session_id: Optional[str] = None
    chapter_id: Optional[str] = None
    character_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
