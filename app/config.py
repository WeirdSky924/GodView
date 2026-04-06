"""
应用配置
"""

import os
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置"""

    # 应用基本信息
    app_name: str = "Godview"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # 数据库配置
    database_url: Optional[str] = Field(
        default=os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5432/godview"),
        description="PostgreSQL 连接 URL",
    )

    # NebulaGraph 配置
    nebula_host: Optional[str] = Field(
        default=os.getenv("NEBULA_HOST", "127.0.0.1"),
        description="NebulaGraph 主机地址",
    )
    nebula_port: int = Field(
        default=int(os.getenv("NEBULA_PORT", 9669)),
        description="NebulaGraph 端口",
    )
    nebula_user: str = Field(
        default=os.getenv("NEBULA_USER", "root"),
        description="NebulaGraph 用户名",
    )
    nebula_password: str = Field(
        default=os.getenv("NEBULA_PASSWORD", "nebula"),
        description="NebulaGraph 密码",
    )

    # Qdrant 配置
    qdrant_url: Optional[str] = Field(
        default=os.getenv("QDRANT_URL", "http://localhost:6333"),
        description="Qdrant 服务 URL",
    )

    # LLM 配置
    llm_provider: str = Field(
        default=os.getenv("LLM_PROVIDER", "openai"),
        description="LLM 提供商 (openai/anthropic/azure)",
    )
    llm_api_key: Optional[str] = Field(
        default=os.getenv("LLM_API_KEY", ""),
        description="LLM API Key",
    )
    llm_base_url: Optional[str] = Field(
        default=os.getenv("LLM_BASE_URL", ""),
        description="LLM API 基础 URL（用于代理或自部署）",
    )
    llm_model: str = Field(
        default=os.getenv("LLM_MODEL", "gpt-4o"),
        description="LLM 模型名称",
    )
    llm_temperature: float = Field(
        default=float(os.getenv("LLM_TEMPERATURE", 0.7)),
        description="LLM 温度参数",
    )
    llm_max_tokens: int = Field(
        default=int(os.getenv("LLM_MAX_TOKENS", 4096)),
        description="LLM 最大 token 数",
    )

    # Embedding 配置
    embedding_provider: str = Field(
        default=os.getenv("EMBEDDING_PROVIDER", "openai"),
        description="Embedding 提供商",
    )
    embedding_model: str = Field(
        default=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        description="Embedding 模型名称",
    )
    embedding_dimension: int = Field(
        default=int(os.getenv("EMBEDDING_DIMENSION", 1536)),
        description="Embedding 向量维度",
    )

    # 导演系统配置
    max_turns_threshold: int = Field(
        default=int(os.getenv("MAX_TURNS_THRESHOLD", 5)),
        description="单交互最大轮次阈值",
    )
    target_word_count_per_intent: int = Field(
        default=int(os.getenv("TARGET_WORD_COUNT_PER_INTENT", 200)),
        description="每个意图的目标字数",
    )
    min_chapter_word_count: int = Field(
        default=int(os.getenv("MIN_CHAPTER_WORD_COUNT", 2000)),
        description="章节最小字数",
    )

    # CORS 配置
    cors_origins: List[str] = Field(
        default=["*"],
        description="允许的 CORS 来源",
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


# 全局配置实例
settings = Settings()
