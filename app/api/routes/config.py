"""
配置管理 API 路由
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== .env 文件操作 ====================

def get_env_file_path() -> Path:
    """获取 .env 文件路径"""
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        return env_path
    return Path.cwd() / ".env"


def update_env_file(updates: Dict[str, str]) -> bool:
    """更新 .env 文件中的配置"""
    try:
        env_path = get_env_file_path()
        logger.info(f"Updating .env file at: {env_path}")

        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            lines = []

        updated_keys = set()
        new_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                new_lines.append(line)
                continue

            if '=' in stripped:
                key = stripped.split('=')[0].strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        for key, value in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")

        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        logger.info(f"Updated .env file with keys: {list(updates.keys())}")
        return True

    except Exception as e:
        logger.error(f"Failed to update .env file: {e}")
        return False


# ==================== Provider 配置 ====================

def get_embedding_providers_config() -> List[Dict[str, Any]]:
    """获取 Embedding Provider 配置"""
    return [
        {
            "id": "openai",
            "name": "OpenAI API（在线）",
            "description": "调用 OpenAI 官方 embedding 接口，效果好但需要 API Key",
            "default_model": "text-embedding-3-small",
            "default_url": "https://api.openai.com/v1",
            "requires_api_key": True,
            "requires_url": True,
            "requires_local_install": False,
            "models": [
                {"id": "text-embedding-3-small", "name": "text-embedding-3-small", "description": "推荐，性价比高"},
                {"id": "text-embedding-3-large", "name": "text-embedding-3-large", "description": "更高精度"},
                {"id": "text-embedding-ada-002", "name": "text-embedding-ada-002", "description": "旧版本"},
            ],
        },
        {
            "id": "sentence_transformers",
            "name": "Sentence-Transformers（本地）",
            "description": "本地运行，首次下载模型权重，之后完全离线可用",
            "default_model": "all-MiniLM-L6-v2",
            "default_url": "",
            "requires_api_key": False,
            "requires_url": False,
            "requires_local_install": True,
            "install_command": "pip install sentence-transformers",
            "models": [
                {"id": "all-MiniLM-L6-v2", "name": "all-MiniLM-L6-v2", "description": "推荐，速度快体积小"},
                {"id": "all-mpnet-base-v2", "name": "all-mpnet-base-v2", "description": "更高精度"},
                {"id": "bge-small-en-v1.5", "name": "BGE Small", "description": "BGE 小模型"},
                {"id": "bge-base-en-v1.5", "name": "BGE Base", "description": "BGE 中等模型"},
                {"id": "bge-large-en-v1.5", "name": "BGE Large", "description": "BGE 大模型"},
                {"id": "e5-small-v2", "name": "E5 Small", "description": "E5 小模型"},
                {"id": "e5-base-v2", "name": "E5 Base", "description": "E5 中等模型"},
                {"id": "e5-large-v2", "name": "E5 Large", "description": "E5 大模型"},
            ],
        },
        {
            "id": "ollama",
            "name": "Ollama（本地自部署）",
            "description": "本地部署 Ollama 服务，完全免费，可选 GPU 加速",
            "default_model": "nomic-embed-text",
            "default_url": "http://localhost:11434",
            "requires_api_key": False,
            "requires_url": True,
            "requires_local_install": True,
            "install_command": "curl -fsSL https://ollama.com/install.sh | sh",
            "models": [
                {"id": "nomic-embed-text", "name": "nomic-embed-text", "description": "推荐，效果好"},
                {"id": "mxbai-embed-large", "name": "mxbai-embed-large", "description": "高精度"},
                {"id": "all-minilm", "name": "all-minilm", "description": "轻量快速"},
            ],
        },
    ]


def get_llm_providers_config() -> List[Dict[str, Any]]:
    """获取 LLM Provider 配置"""
    return [
        {
            "id": "openai",
            "name": "OpenAI",
            "description": "GPT-4、GPT-3.5 等系列模型",
            "default_model": "gpt-4o",
            "default_url": "https://api.openai.com/v1",
            "requires_api_key": True,
            "api_key_url": "https://platform.openai.com/api-keys",
            "models": [
                {"id": "gpt-4o", "name": "GPT-4o", "description": "最新旗舰模型"},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "轻量版，速度快"},
                {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "description": "GPT-4 增强版"},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "经济实惠"},
            ],
        },
        {
            "id": "anthropic",
            "name": "Anthropic Claude",
            "description": "Claude 系列模型，擅长长文本和推理",
            "default_model": "claude-sonnet-4-20250514",
            "default_url": "https://api.anthropic.com",
            "requires_api_key": True,
            "api_key_url": "https://console.anthropic.com/",
            "models": [
                {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "description": "最新 Claude 模型"},
                {"id": "claude-3-5-sonnet-latest", "name": "Claude 3.5 Sonnet", "description": "主力模型"},
                {"id": "claude-3-5-haiku-latest", "name": "Claude 3.5 Haiku", "description": "快速响应版"},
                {"id": "claude-3-opus-latest", "name": "Claude 3 Opus", "description": "最强推理"},
            ],
        },
        {
            "id": "zhipu",
            "name": "智谱AI (GLM)",
            "description": "国产 GLM 系列大模型",
            "default_model": "glm-4-plus",
            "default_url": "https://open.bigmodel.cn/api/paas/v4",
            "requires_api_key": True,
            "api_key_url": "https://open.bigmodel.cn/",
            "models": [
                {"id": "glm-4-plus", "name": "GLM-4 Plus", "description": "旗舰模型"},
                {"id": "glm-4-air", "name": "GLM-4 Air", "description": "快速响应版"},
                {"id": "glm-4-flash", "name": "GLM-4 Flash", "description": "极速版，免费额度"},
                {"id": "glm-4-long", "name": "GLM-4 Long", "description": "超长上下文"},
            ],
        },
        {
            "id": "qwen",
            "name": "通义千问 (阿里云)",
            "description": "阿里云 Qwen 系列大模型",
            "default_model": "qwen-max",
            "default_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "requires_api_key": True,
            "api_key_url": "https://dashscope.console.aliyun.com/",
            "models": [
                {"id": "qwen-max", "name": "Qwen Max", "description": "旗舰模型"},
                {"id": "qwen-plus", "name": "Qwen Plus", "description": "高性价比"},
                {"id": "qwen-turbo", "name": "Qwen Turbo", "description": "快速响应"},
                {"id": "qwen-long", "name": "Qwen Long", "description": "超长上下文"},
            ],
        },
        {
            "id": "deepseek",
            "name": "DeepSeek (深度求索)",
            "description": "DeepSeek 系列，性价比高",
            "default_model": "deepseek-chat",
            "default_url": "https://api.deepseek.com",
            "requires_api_key": True,
            "api_key_url": "https://platform.deepseek.com/",
            "models": [
                {"id": "deepseek-chat", "name": "DeepSeek Chat", "description": "对话模型"},
                {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner", "description": "推理模型（R1）"},
            ],
        },
        {
            "id": "moonshot",
            "name": "月之暗面 (Kimi)",
            "description": "Kimi 系列，擅长长文本处理",
            "default_model": "moonshot-v1-8k",
            "default_url": "https://api.moonshot.cn/v1",
            "requires_api_key": True,
            "api_key_url": "https://platform.moonshot.cn/",
            "models": [
                {"id": "moonshot-v1-8k", "name": "Moonshot V1 8K", "description": "标准版"},
                {"id": "moonshot-v1-32k", "name": "Moonshot V1 32K", "description": "长文本版"},
                {"id": "moonshot-v1-128k", "name": "Moonshot V1 128K", "description": "超长文本版"},
            ],
        },
        {
            "id": "baichuan",
            "name": "百川智能",
            "description": "Baichuan 系列大模型",
            "default_model": "Baichuan4",
            "default_url": "https://api.baichuan-ai.com/v1",
            "requires_api_key": True,
            "api_key_url": "https://platform.baichuan-ai.com/",
            "models": [
                {"id": "Baichuan4", "name": "Baichuan 4", "description": "最新旗舰"},
                {"id": "Baichuan3-Turbo", "name": "Baichuan 3 Turbo", "description": "快速版"},
            ],
        },
        {
            "id": "yi",
            "name": "零一万物 (Yi)",
            "description": "Yi 系列大模型",
            "default_model": "yi-large",
            "default_url": "https://api.lingyiwanwu.com/v1",
            "requires_api_key": True,
            "api_key_url": "https://platform.lingyiwanwu.com/",
            "models": [
                {"id": "yi-large", "name": "Yi Large", "description": "旗舰模型"},
                {"id": "yi-large-turbo", "name": "Yi Large Turbo", "description": "快速版"},
                {"id": "yi-medium", "name": "Yi Medium", "description": "中等规格"},
            ],
        },
        {
            "id": "minimax",
            "name": "MiniMax",
            "description": "MiniMax 系列大模型",
            "default_model": "abab6.5-chat",
            "default_url": "https://api.minimax.chat/v1",
            "requires_api_key": True,
            "api_key_url": "https://www.minimaxi.com/",
            "models": [
                {"id": "abab6.5-chat", "name": "ABAB 6.5", "description": "旗舰模型"},
                {"id": "abab6.5s-chat", "name": "ABAB 6.5S", "description": "快速版"},
            ],
        },
        {
            "id": "openrouter",
            "name": "OpenRouter (聚合网关)",
            "description": "聚合多个 LLM 提供商的统一网关",
            "default_model": "anthropic/claude-sonnet-4",
            "default_url": "https://openrouter.ai/api/v1",
            "requires_api_key": True,
            "api_key_url": "https://openrouter.ai/keys",
            "models": [
                {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4 (via OR)", "description": "通过 OpenRouter"},
                {"id": "openai/gpt-4o", "name": "GPT-4o (via OR)", "description": "通过 OpenRouter"},
                {"id": "google/gemini-pro-1.5", "name": "Gemini Pro 1.5", "description": "Google 长文本"},
            ],
        },
        {
            "id": "custom",
            "name": "自定义 (OpenAI 兼容)",
            "description": "任意 OpenAI 兼容的 API 服务",
            "default_model": "",
            "default_url": "",
            "requires_api_key": True,
            "api_key_url": "",
            "models": [],
        },
    ]


# ==================== 请求/响应模型 ====================

class EmbeddingConfig(BaseModel):
    """Embedding 配置"""
    provider: str
    model: str = ""
    api_key: str = ""
    base_url: str = ""


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: str
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


# ==================== API 路由 ====================

@router.get("/embedding/providers")
async def get_embedding_providers() -> List[Dict[str, Any]]:
    """获取所有支持的 Embedding Provider 信息"""
    return get_embedding_providers_config()


@router.get("/embedding")
async def get_embedding_config() -> Dict[str, Any]:
    """获取当前 Embedding 配置"""
    from app.config import settings
    from app.api.app import get_embedding_service

    provider = settings.embedding_provider
    config = settings.get_embedding_config(provider)

    dimension = 384
    service = get_embedding_service()
    if service:
        try:
            dimension = await service.get_dimension()
        except Exception:
            pass

    config["dimension"] = dimension
    return config


@router.get("/embedding/{provider}")
async def get_embedding_provider_config(provider: str) -> Dict[str, Any]:
    """获取指定 Embedding Provider 的配置"""
    from app.config import settings
    config = settings.get_embedding_config(provider)

    # 获取维度（如果是当前 provider）
    if provider == settings.embedding_provider:
        from app.api.app import get_embedding_service
        service = get_embedding_service()
        if service:
            try:
                config["dimension"] = await service.get_dimension()
            except Exception:
                config["dimension"] = 384
    else:
        config["dimension"] = None

    return config


@router.put("/embedding")
async def update_embedding_config(config: EmbeddingConfig) -> Dict[str, Any]:
    """更新 Embedding 配置并保存到 .env 文件"""
    from app.config import settings
    from app.services.embedding_service import create_embedding_service

    providers = get_embedding_providers_config()
    valid_providers = [p["id"] for p in providers]
    if config.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 provider: {config.provider}，可选：{valid_providers}"
        )

    provider_info = next(p for p in providers if p["id"] == config.provider)
    model = config.model or provider_info["default_model"]

    # 根据不同 provider 处理配置
    if config.provider == "sentence_transformers":
        api_key = ""
        base_url = config.base_url
    elif config.provider == "ollama":
        api_key = ""
        base_url = config.base_url or provider_info["default_url"]
    else:
        api_key = config.api_key
        base_url = config.base_url or provider_info["default_url"]

    # 更新当前 provider
    settings.embedding_provider = config.provider
    settings.set_embedding_config(config.provider, model=model, api_key=api_key, base_url=base_url)

    # 准备 .env 更新
    env_updates = {
        "EMBEDDING_PROVIDER": config.provider,
    }

    # 根据 provider 类型设置对应的环境变量
    env_prefix = "EMBEDDING_ST" if config.provider == "sentence_transformers" else f"EMBEDDING_{config.provider.upper()}"
    env_updates[f"{env_prefix}_MODEL"] = model

    if config.provider == "sentence_transformers":
        if base_url:
            env_updates["EMBEDDING_ST_CACHE_FOLDER"] = base_url
    elif config.provider == "ollama":
        env_updates["EMBEDDING_OLLAMA_BASE_URL"] = base_url
    else:
        if api_key and api_key != "***":
            env_updates[f"EMBEDDING_{config.provider.upper()}_API_KEY"] = api_key
        if base_url:
            env_updates[f"EMBEDDING_{config.provider.upper()}_BASE_URL"] = base_url

    if not update_env_file(env_updates):
        logger.warning("Failed to save Embedding config to .env file, but runtime config updated")

    try:
        service = create_embedding_service(
            provider=config.provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        success, message = await service.test_connection()
        dimension = await service.get_dimension()

        if success:
            from app.api.app import set_embedding_service
            set_embedding_service(service)

            return {
                "success": True,
                "message": f"配置已保存：{config.provider} ({model}) - {message}",
                "dimension": dimension,
                "config": {
                    "provider": config.provider,
                    "model": model,
                    "base_url": base_url,
                },
            }
        else:
            return {
                "success": False,
                "message": f"配置已保存但连接测试失败：{message}",
                "dimension": dimension,
                "config": {
                    "provider": config.provider,
                    "model": model,
                    "base_url": base_url,
                },
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置更新失败：{str(e)}")


@router.post("/embedding/test")
async def test_embedding_config(config: Optional[EmbeddingConfig] = None) -> Dict[str, Any]:
    """测试 Embedding 连接"""
    from app.config import settings
    from app.services.embedding_service import create_embedding_service

    providers = get_embedding_providers_config()

    if config:
        provider = config.provider
        model = config.model

        if provider == "sentence_transformers":
            api_key = ""
            base_url = config.base_url
        elif provider == "ollama":
            api_key = ""
            base_url = config.base_url or next(p["default_url"] for p in providers if p["id"] == "ollama")
        else:
            provider_config = settings.get_embedding_config(provider)
            api_key = config.api_key or provider_config.get("api_key", "")
            base_url = config.base_url or provider_config.get("base_url", "")
    else:
        provider = settings.embedding_provider
        provider_config = settings.get_embedding_config(provider)
        model = provider_config.get("model", "")
        api_key = provider_config.get("api_key", "")
        base_url = provider_config.get("base_url", "")

    try:
        service = create_embedding_service(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        success, message = await service.test_connection()
        dimension = await service.get_dimension()

        return {
            "success": success,
            "message": message,
            "dimension": dimension,
            "config": {
                "provider": provider,
                "model": model,
                "base_url": base_url,
            },
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"测试失败：{str(e)}",
        }


@router.get("/embedding/download-progress")
async def get_embedding_download_progress() -> Dict[str, Any]:
    """获取 Embedding 模型下载进度"""
    from app.services.embedding_service import get_download_progress
    return get_download_progress()


@router.get("/llm/providers")
async def get_llm_providers() -> List[Dict[str, Any]]:
    """获取所有支持的 LLM Provider 信息"""
    return get_llm_providers_config()


@router.get("/llm")
async def get_llm_config() -> Dict[str, Any]:
    """获取当前 LLM 配置"""
    from app.config import settings
    return settings.get_llm_config(settings.llm_provider)


@router.get("/llm/{provider}")
async def get_llm_provider_config(provider: str) -> Dict[str, Any]:
    """获取指定 LLM Provider 的配置"""
    from app.config import settings
    return settings.get_llm_config(provider)


@router.put("/llm")
async def update_llm_config(config: LLMConfig) -> Dict[str, Any]:
    """更新 LLM 配置并保存到 .env 文件"""
    from app.config import settings
    from app.services.model_router import create_llm

    providers = get_llm_providers_config()
    provider_info = next((p for p in providers if p["id"] == config.provider), None)
    if provider_info:
        model = config.model or provider_info["default_model"]
        base_url = config.base_url or provider_info["default_url"]
    else:
        model = config.model
        base_url = config.base_url

    # 更新当前 provider
    settings.llm_provider = config.provider
    settings.set_llm_config(
        config.provider,
        model=model,
        api_key=config.api_key,
        base_url=base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )

    # 准备 .env 更新
    env_updates = {
        "LLM_PROVIDER": config.provider,
        f"LLM_{config.provider.upper()}_MODEL": model,
        f"LLM_{config.provider.upper()}_TEMPERATURE": str(config.temperature),
        f"LLM_{config.provider.upper()}_MAX_TOKENS": str(config.max_tokens),
    }
    if base_url:
        env_updates[f"LLM_{config.provider.upper()}_BASE_URL"] = base_url
    if config.api_key and config.api_key != "***":
        env_updates[f"LLM_{config.provider.upper()}_API_KEY"] = config.api_key

    if not update_env_file(env_updates):
        logger.warning("Failed to save LLM config to .env file, but runtime config updated")

    try:
        llm = create_llm(
            provider=config.provider,
            model=model,
            api_key=settings.get_llm_config(config.provider).get("api_key", ""),
            base_url=base_url,
            temperature=config.temperature,
        )
        response = await llm.ainvoke("回复OK表示连接成功")

        return {
            "success": True,
            "message": f"配置已保存并测试成功：{config.provider} ({model})",
            "response": response.content if hasattr(response, 'content') else str(response)[:100],
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"配置已保存但测试失败：{str(e)}",
        }


@router.post("/llm/test")
async def test_llm_config(config: Optional[LLMConfig] = None) -> Dict[str, Any]:
    """测试 LLM 连接"""
    from app.config import settings
    from app.services.model_router import create_llm

    if config:
        provider = config.provider
        provider_config = settings.get_llm_config(provider)
        model = config.model or provider_config.get("model", "")
        api_key = config.api_key or provider_config.get("api_key", "")
        base_url = config.base_url or provider_config.get("base_url", "")
        temperature = config.temperature
    else:
        provider = settings.llm_provider
        provider_config = settings.get_llm_config(provider)
        model = provider_config.get("model", "")
        api_key = provider_config.get("api_key", "")
        base_url = provider_config.get("base_url", "")
        temperature = provider_config.get("temperature", 0.7)

    try:
        llm = create_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
        )
        response = await llm.ainvoke("回复OK表示连接成功")

        return {
            "success": True,
            "message": f"连接成功：{provider} ({model})",
            "response": response.content if hasattr(response, 'content') else str(response)[:100],
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败：{str(e)}",
        }


@router.get("/llm/providers/{provider_id}/models")
async def get_provider_models(provider_id: str) -> Dict[str, Any]:
    """获取指定 Provider 的模型列表"""
    providers = get_llm_providers_config()
    provider = next((p for p in providers if p["id"] == provider_id), None)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

    return {
        "provider_id": provider_id,
        "provider_name": provider["name"],
        "models": provider.get("models", []),
        "default_model": provider["default_model"],
    }


# ==================== 系统配置（公开） ====================

@router.get("/system")
async def get_system_config() -> Dict[str, Any]:
    """
    获取系统配置（公开接口，供前端使用）

    返回前端需要的配置信息，如 API 地址、WebSocket 地址等
    """
    from app.config import settings

    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "api_base_url": settings.api_base_url,
        "ws_base_url": settings.ws_base_url,
    }


@router.get("/database/status")
async def get_database_status() -> Dict[str, Any]:
    """
    获取数据库连接状态

    返回所有数据库的连接状态信息
    """
    import asyncio
    import httpx
    import socket

    from app.config import settings
    from app.api import app as app_module

    databases = []

    # PostgreSQL 状态
    postgres_status = {
        "name": "PostgreSQL",
        "type": "关系数据库",
        "status": "disconnected",
        "message": "",
        "host": "",
    }
    try:
        if settings.database_url:
            # 解析数据库 URL
            db_url = settings.database_url
            if "@" in db_url:
                host_part = db_url.split("@")[1].split("/")[0]
                postgres_status["host"] = host_part
            else:
                postgres_status["host"] = "localhost:5432"

            # 检查全局实例
            if hasattr(app_module, 'postgres_db') and app_module.postgres_db:
                postgres_status["status"] = "connected"
                postgres_status["message"] = "连接正常"
            else:
                # 尝试简单连接测试
                try:
                    host = "localhost"
                    port = 5432
                    if ":" in postgres_status["host"]:
                        parts = postgres_status["host"].split(":")
                        host = parts[0]
                        port = int(parts[1])
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((host, port))
                    if result == 0:
                        postgres_status["status"] = "reachable"
                        postgres_status["message"] = "端口可达，未连接"
                    else:
                        postgres_status["message"] = "无法连接"
                    sock.close()
                except Exception as e:
                    postgres_status["message"] = str(e)[:30]
        else:
            postgres_status["message"] = "未配置"
    except Exception as e:
        postgres_status["message"] = str(e)[:50]
    databases.append(postgres_status)

    # Qdrant 状态
    qdrant_status = {
        "name": "Qdrant",
        "type": "向量数据库",
        "status": "disconnected",
        "message": "",
        "host": "",
    }
    try:
        if settings.qdrant_url:
            qdrant_status["host"] = settings.qdrant_url.replace("http://", "").replace("https://", "")

            # 尝试直接连接
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    response = await client.get(f"{settings.qdrant_url}/collections")
                    if response.status_code == 200:
                        qdrant_status["status"] = "connected"
                        qdrant_status["message"] = "连接正常"
                    else:
                        qdrant_status["status"] = "reachable"
                        qdrant_status["message"] = f"HTTP {response.status_code}"
                except httpx.ConnectError:
                    qdrant_status["message"] = "无法连接"
                except Exception as e:
                    qdrant_status["message"] = str(e)[:30]
        else:
            qdrant_status["message"] = "未配置"
    except Exception as e:
        qdrant_status["message"] = str(e)[:50]
    databases.append(qdrant_status)

    # NebulaGraph 状态
    nebula_status = {
        "name": "NebulaGraph",
        "type": "图数据库",
        "status": "disconnected",
        "message": "",
        "host": "",
    }
    try:
        if settings.nebula_host:
            nebula_status["host"] = f"{settings.nebula_host}:{settings.nebula_port}"

            # 检查全局实例
            if hasattr(app_module, 'nebula_db') and app_module.nebula_db:
                nebula_status["status"] = "connected"
                nebula_status["message"] = "连接正常"
            else:
                # 尝试简单连接测试
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((settings.nebula_host, settings.nebula_port))
                    if result == 0:
                        nebula_status["status"] = "reachable"
                        nebula_status["message"] = "端口可达，未连接"
                    else:
                        nebula_status["message"] = "无法连接"
                    sock.close()
                except Exception as e:
                    nebula_status["message"] = str(e)[:30]
        else:
            nebula_status["message"] = "未配置"
    except Exception as e:
        nebula_status["message"] = str(e)[:50]
    databases.append(nebula_status)

    # 计算总体状态
    connected_count = sum(1 for db in databases if db["status"] == "connected")
    total_count = len(databases)

    return {
        "databases": databases,
        "summary": {
            "connected": connected_count,
            "total": total_count,
            "status": "healthy" if connected_count == total_count else "degraded" if connected_count > 0 else "error",
        },
    }
