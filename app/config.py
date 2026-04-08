"""
应用配置
"""

import os
from typing import List, Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

# 显式加载 .env 文件，override=True 确保 .env 文件值覆盖系统环境变量
load_dotenv(override=True)


class Settings(BaseSettings):
    """应用配置"""

    # 应用基本信息
    app_name: str = "Godview"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # 服务器配置（前后端分离时需要）
    api_base_url: str = Field(
        default=os.getenv("API_BASE_URL", "http://localhost:8000"),
        description="后端 API 基础 URL",
    )
    ws_base_url: str = Field(
        default=os.getenv("WS_BASE_URL", "ws://localhost:8000"),
        description="WebSocket 基础 URL",
    )
    frontend_url: str = Field(
        default=os.getenv("FRONTEND_URL", "http://localhost:5173"),
        description="前端 URL（用于 CORS 配置）",
    )

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

    # ===== LLM 当前使用的 Provider =====
    llm_provider: str = Field(
        default=os.getenv("LLM_PROVIDER", "openai"),
        description="LLM 提供商",
    )

    # ===== LLM 分 Provider 配置 =====
    # OpenAI
    llm_openai_model: str = Field(
        default=os.getenv("LLM_OPENAI_MODEL", "gpt-4o"),
        description="OpenAI 模型名称",
    )
    llm_openai_api_key: Optional[str] = Field(
        default=os.getenv("LLM_OPENAI_API_KEY", ""),
        description="OpenAI API Key",
    )
    llm_openai_base_url: str = Field(
        default=os.getenv("LLM_OPENAI_BASE_URL", "https://api.openai.com/v1"),
        description="OpenAI API 基础 URL",
    )
    llm_openai_temperature: float = Field(
        default=float(os.getenv("LLM_OPENAI_TEMPERATURE", "0.7")),
        description="OpenAI Temperature",
    )
    llm_openai_max_tokens: int = Field(
        default=int(os.getenv("LLM_OPENAI_MAX_TOKENS", "4096")),
        description="OpenAI Max Tokens",
    )

    # Anthropic
    llm_anthropic_model: str = Field(
        default=os.getenv("LLM_ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        description="Anthropic 模型名称",
    )
    llm_anthropic_api_key: Optional[str] = Field(
        default=os.getenv("LLM_ANTHROPIC_API_KEY", ""),
        description="Anthropic API Key",
    )
    llm_anthropic_base_url: str = Field(
        default=os.getenv("LLM_ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        description="Anthropic API 基础 URL",
    )
    llm_anthropic_temperature: float = Field(
        default=float(os.getenv("LLM_ANTHROPIC_TEMPERATURE", "0.7")),
        description="Anthropic Temperature",
    )
    llm_anthropic_max_tokens: int = Field(
        default=int(os.getenv("LLM_ANTHROPIC_MAX_TOKENS", "4096")),
        description="Anthropic Max Tokens",
    )

    # Zhipu (智谱)
    llm_zhipu_model: str = Field(
        default=os.getenv("LLM_ZHIPU_MODEL", "glm-4-plus"),
        description="智谱模型名称",
    )
    llm_zhipu_api_key: Optional[str] = Field(
        default=os.getenv("LLM_ZHIPU_API_KEY", ""),
        description="智谱 API Key",
    )
    llm_zhipu_base_url: str = Field(
        default=os.getenv("LLM_ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        description="智谱 API 基础 URL",
    )
    llm_zhipu_temperature: float = Field(
        default=float(os.getenv("LLM_ZHIPU_TEMPERATURE", "0.7")),
        description="智谱 Temperature",
    )
    llm_zhipu_max_tokens: int = Field(
        default=int(os.getenv("LLM_ZHIPU_MAX_TOKENS", "4096")),
        description="智谱 Max Tokens",
    )

    # Qwen (通义千问)
    llm_qwen_model: str = Field(
        default=os.getenv("LLM_QWEN_MODEL", "qwen-max"),
        description="通义千问模型名称",
    )
    llm_qwen_api_key: Optional[str] = Field(
        default=os.getenv("LLM_QWEN_API_KEY", ""),
        description="通义千问 API Key",
    )
    llm_qwen_base_url: str = Field(
        default=os.getenv("LLM_QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        description="通义千问 API 基础 URL",
    )
    llm_qwen_temperature: float = Field(
        default=float(os.getenv("LLM_QWEN_TEMPERATURE", "0.7")),
        description="通义千问 Temperature",
    )
    llm_qwen_max_tokens: int = Field(
        default=int(os.getenv("LLM_QWEN_MAX_TOKENS", "4096")),
        description="通义千问 Max Tokens",
    )

    # DeepSeek
    llm_deepseek_model: str = Field(
        default=os.getenv("LLM_DEEPSEEK_MODEL", "deepseek-chat"),
        description="DeepSeek 模型名称",
    )
    llm_deepseek_api_key: Optional[str] = Field(
        default=os.getenv("LLM_DEEPSEEK_API_KEY", ""),
        description="DeepSeek API Key",
    )
    llm_deepseek_base_url: str = Field(
        default=os.getenv("LLM_DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        description="DeepSeek API 基础 URL",
    )
    llm_deepseek_temperature: float = Field(
        default=float(os.getenv("LLM_DEEPSEEK_TEMPERATURE", "0.7")),
        description="DeepSeek Temperature",
    )
    llm_deepseek_max_tokens: int = Field(
        default=int(os.getenv("LLM_DEEPSEEK_MAX_TOKENS", "4096")),
        description="DeepSeek Max Tokens",
    )

    # Moonshot
    llm_moonshot_model: str = Field(
        default=os.getenv("LLM_MOONSHOT_MODEL", "moonshot-v1-8k"),
        description="Moonshot 模型名称",
    )
    llm_moonshot_api_key: Optional[str] = Field(
        default=os.getenv("LLM_MOONSHOT_API_KEY", ""),
        description="Moonshot API Key",
    )
    llm_moonshot_base_url: str = Field(
        default=os.getenv("LLM_MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"),
        description="Moonshot API 基础 URL",
    )
    llm_moonshot_temperature: float = Field(
        default=float(os.getenv("LLM_MOONSHOT_TEMPERATURE", "0.7")),
        description="Moonshot Temperature",
    )
    llm_moonshot_max_tokens: int = Field(
        default=int(os.getenv("LLM_MOONSHOT_MAX_TOKENS", "4096")),
        description="Moonshot Max Tokens",
    )

    # Baichuan
    llm_baichuan_model: str = Field(
        default=os.getenv("LLM_BAICHUAN_MODEL", "Baichuan4"),
        description="百川模型名称",
    )
    llm_baichuan_api_key: Optional[str] = Field(
        default=os.getenv("LLM_BAICHUAN_API_KEY", ""),
        description="百川 API Key",
    )
    llm_baichuan_base_url: str = Field(
        default=os.getenv("LLM_BAICHUAN_BASE_URL", "https://api.baichuan-ai.com/v1"),
        description="百川 API 基础 URL",
    )
    llm_baichuan_temperature: float = Field(
        default=float(os.getenv("LLM_BAICHUAN_TEMPERATURE", "0.7")),
        description="百川 Temperature",
    )
    llm_baichuan_max_tokens: int = Field(
        default=int(os.getenv("LLM_BAICHUAN_MAX_TOKENS", "4096")),
        description="百川 Max Tokens",
    )

    # Yi
    llm_yi_model: str = Field(
        default=os.getenv("LLM_YI_MODEL", "yi-large"),
        description="零一万物模型名称",
    )
    llm_yi_api_key: Optional[str] = Field(
        default=os.getenv("LLM_YI_API_KEY", ""),
        description="零一万物 API Key",
    )
    llm_yi_base_url: str = Field(
        default=os.getenv("LLM_YI_BASE_URL", "https://api.lingyiwanwu.com/v1"),
        description="零一万物 API 基础 URL",
    )
    llm_yi_temperature: float = Field(
        default=float(os.getenv("LLM_YI_TEMPERATURE", "0.7")),
        description="零一万物 Temperature",
    )
    llm_yi_max_tokens: int = Field(
        default=int(os.getenv("LLM_YI_MAX_TOKENS", "4096")),
        description="零一万物 Max Tokens",
    )

    # MiniMax
    llm_minimax_model: str = Field(
        default=os.getenv("LLM_MINIMAX_MODEL", "abab6.5-chat"),
        description="MiniMax 模型名称",
    )
    llm_minimax_api_key: Optional[str] = Field(
        default=os.getenv("LLM_MINIMAX_API_KEY", ""),
        description="MiniMax API Key",
    )
    llm_minimax_base_url: str = Field(
        default=os.getenv("LLM_MINIMAX_BASE_URL", "https://api.minimax.chat/v1"),
        description="MiniMax API 基础 URL",
    )
    llm_minimax_temperature: float = Field(
        default=float(os.getenv("LLM_MINIMAX_TEMPERATURE", "0.7")),
        description="MiniMax Temperature",
    )
    llm_minimax_max_tokens: int = Field(
        default=int(os.getenv("LLM_MINIMAX_MAX_TOKENS", "4096")),
        description="MiniMax Max Tokens",
    )

    # OpenRouter
    llm_openrouter_model: str = Field(
        default=os.getenv("LLM_OPENROUTER_MODEL", "anthropic/claude-sonnet-4"),
        description="OpenRouter 模型名称",
    )
    llm_openrouter_api_key: Optional[str] = Field(
        default=os.getenv("LLM_OPENROUTER_API_KEY", ""),
        description="OpenRouter API Key",
    )
    llm_openrouter_base_url: str = Field(
        default=os.getenv("LLM_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        description="OpenRouter API 基础 URL",
    )
    llm_openrouter_temperature: float = Field(
        default=float(os.getenv("LLM_OPENROUTER_TEMPERATURE", "0.7")),
        description="OpenRouter Temperature",
    )
    llm_openrouter_max_tokens: int = Field(
        default=int(os.getenv("LLM_OPENROUTER_MAX_TOKENS", "4096")),
        description="OpenRouter Max Tokens",
    )

    # ===== Embedding 当前使用的 Provider =====
    embedding_provider: str = Field(
        default=os.getenv("EMBEDDING_PROVIDER", "sentence_transformers"),
        description="Embedding 提供商",
    )

    # ===== Embedding 分 Provider 配置 =====
    # OpenAI
    embedding_openai_model: str = Field(
        default=os.getenv("EMBEDDING_OPENAI_MODEL", "text-embedding-3-small"),
        description="OpenAI Embedding 模型名称",
    )
    embedding_openai_api_key: Optional[str] = Field(
        default=os.getenv("EMBEDDING_OPENAI_API_KEY", ""),
        description="OpenAI Embedding API Key",
    )
    embedding_openai_base_url: str = Field(
        default=os.getenv("EMBEDDING_OPENAI_BASE_URL", "https://api.openai.com/v1"),
        description="OpenAI Embedding API 基础 URL",
    )

    # Sentence-Transformers
    embedding_st_model: str = Field(
        default=os.getenv("EMBEDDING_ST_MODEL", "all-MiniLM-L6-v2"),
        description="Sentence-Transformers 模型名称",
    )
    embedding_st_cache_folder: str = Field(
        default=os.getenv("EMBEDDING_ST_CACHE_FOLDER", ""),
        description="Sentence-Transformers 模型存储路径",
    )

    # Ollama
    embedding_ollama_model: str = Field(
        default=os.getenv("EMBEDDING_OLLAMA_MODEL", "nomic-embed-text"),
        description="Ollama Embedding 模型名称",
    )
    embedding_ollama_base_url: str = Field(
        default=os.getenv("EMBEDDING_OLLAMA_BASE_URL", "http://localhost:11434"),
        description="Ollama 服务地址",
    )

    # 导演系统配置
    max_turns_threshold: int = Field(
        default=int(os.getenv("MAX_TURNS_THRESHOLD", "5")),
        description="单交互最大轮次阈值",
    )
    target_word_count_per_intent: int = Field(
        default=int(os.getenv("TARGET_WORD_COUNT_PER_INTENT", "200")),
        description="每个意图的目标字数",
    )
    min_chapter_word_count: int = Field(
        default=int(os.getenv("MIN_CHAPTER_WORD_COUNT", "2000")),
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
        extra = "allow"

    def get_llm_config(self, provider: str) -> dict:
        """获取指定 LLM provider 的配置"""
        provider = provider.lower()
        prefix = f"llm_{provider}_"
        return {
            "provider": provider,
            "model": getattr(self, f"{prefix}model", ""),
            "api_key": getattr(self, f"{prefix}api_key", "") or "",
            "base_url": getattr(self, f"{prefix}base_url", ""),
            "temperature": getattr(self, f"{prefix}temperature", 0.7),
            "max_tokens": getattr(self, f"{prefix}max_tokens", 4096),
        }

    def set_llm_config(self, provider: str, **kwargs):
        """设置指定 LLM provider 的配置"""
        provider = provider.lower()
        prefix = f"llm_{provider}_"
        if "model" in kwargs:
            setattr(self, f"{prefix}model", kwargs["model"])
        if "api_key" in kwargs:
            setattr(self, f"{prefix}api_key", kwargs["api_key"])
        if "base_url" in kwargs:
            setattr(self, f"{prefix}base_url", kwargs["base_url"])
        if "temperature" in kwargs:
            setattr(self, f"{prefix}temperature", kwargs["temperature"])
        if "max_tokens" in kwargs:
            setattr(self, f"{prefix}max_tokens", kwargs["max_tokens"])

    def get_embedding_config(self, provider: str) -> dict:
        """获取指定 Embedding provider 的配置"""
        provider = provider.lower()
        if provider == "sentence_transformers":
            provider = "st"
        prefix = f"embedding_{provider}_"
        return {
            "provider": provider if provider != "st" else "sentence_transformers",
            "model": getattr(self, f"{prefix}model", ""),
            "api_key": getattr(self, f"{prefix}api_key", "") or "",
            "base_url": getattr(self, f"{prefix}base_url", "") or getattr(self, f"{prefix}cache_folder", ""),
        }

    def set_embedding_config(self, provider: str, **kwargs):
        """设置指定 Embedding provider 的配置"""
        provider = provider.lower()
        if provider == "sentence_transformers":
            provider = "st"
        prefix = f"embedding_{provider}_"
        if "model" in kwargs:
            setattr(self, f"{prefix}model", kwargs["model"])
        if "api_key" in kwargs:
            setattr(self, f"{prefix}api_key", kwargs["api_key"])
        if "base_url" in kwargs:
            if provider == "st":
                setattr(self, f"{prefix}cache_folder", kwargs["base_url"])
            else:
                setattr(self, f"{prefix}base_url", kwargs["base_url"])


# 全局配置实例
settings = Settings()
