"""
Configuration Management for Godview
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent


def load_yaml_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    full_path = get_project_root() / config_path
    if full_path.exists():
        with open(full_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_name: str = Field(default="Godview", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本")
    app_env: str = Field(default="development", description="运行环境")
    log_level: str = Field(default="DEBUG", description="日志级别")

    # API Keys
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")
    openai_api_key: str = Field(default="", description="OpenAI API Key")

    # 数据库配置 - PostgreSQL
    database_url: str = Field(default="", description="PostgreSQL 连接 URL")
    async_database_url: str = Field(default="", description="PostgreSQL 异步连接 URL")

    # 数据库配置 - NebulaGraph
    nebula_host: str = Field(default="127.0.0.1", description="NebulaGraph 主机")
    nebula_port: int = Field(default=9669, description="NebulaGraph 端口")
    nebula_user: str = Field(default="root", description="NebulaGraph 用户名")
    nebula_password: str = Field(default="nebula", description="NebulaGraph 密码")

    # 数据库配置 - Qdrant
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant URL")

    # LangSmith 配置
    langchain_tracing_v2: bool = Field(default=True, description="是否启用 LangSmith 追踪")
    langsmith_api_key: str = Field(default="", description="LangSmith API Key")
    langchain_project: str = Field(default="godview", description="LangSmith 项目名称")

    # 模型配置
    default_model: str = Field(
        default="claude-sonnet-4-6-20250929", description="默认模型"
    )

    # WebSocket 配置
    ws_ping_interval: int = Field(default=30, description="WebSocket Ping 间隔")
    ws_ping_timeout: int = Field(default=10, description="WebSocket Ping 超时")

    @property
    def project_root(self) -> Path:
        """获取项目根目录"""
        return get_project_root()

    @property
    def config_path(self) -> Path:
        """获取配置文件目录"""
        return self.project_root / "config"

    def load_agent_config(self) -> dict:
        """加载 Agent 配置"""
        return load_yaml_config("config/settings.yaml")

    def load_prompts(self) -> dict:
        """加载 Prompt 模板"""
        return load_yaml_config("config/prompts/prompts.yaml")


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
