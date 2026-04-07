"""
配置管理 API 路由
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# 支持的 Embedding Provider 列表
EMBEDDING_PROVIDERS = [
    {
        "id": "openai",
        "name": "OpenAI API（在线）",
        "description": "调用 OpenAI 官方 embedding 接口，效果好但需要 API Key",
        "default_model": "text-embedding-3-small",
        "default_url": "https://api.openai.com/v1",
        "default_dimension": 1536,
        "requires_api_key": True,
        "requires_local_install": False,
    },
    {
        "id": "sentence_transformers",
        "name": "Sentence-Transformers（本地）",
        "description": "本地运行，首次下载模型权重，之后完全离线可用",
        "default_model": "all-MiniLM-L6-v2",
        "default_url": "",
        "default_dimension": 384,
        "requires_api_key": False,
        "requires_local_install": True,
        "install_command": "pip install sentence-transformers",
    },
    {
        "id": "ollama",
        "name": "Ollama（本地自部署）",
        "description": "本地部署 Ollama 服务，完全免费，可选 GPU 加速",
        "default_model": "nomic-embed-text",
        "default_url": "http://localhost:11434",
        "default_dimension": 768,
        "requires_api_key": False,
        "requires_local_install": True,
        "install_command": "curl -fsSL https://ollama.com/install.sh | sh  # 或从 ollama.com 下载安装包",
    },
]

# LLM Provider 配置
# 每个提供商包含基本信息和支持的模型列表
LLM_PROVIDERS = [
    {
        "id": "openai",
        "name": "OpenAI",
        "description": "GPT-4、GPT-3.5 等系列模型",
        "default_model": "gpt-4o",
        "default_url": "https://api.openai.com/v1",
        "requires_api_key": True,
        "api_key_url": "https://platform.openai.com/api-keys",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o", "context_length": 128000, "description": "最新旗舰模型，综合能力最强"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context_length": 128000, "description": "轻量版，速度快成本低"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context_length": 128000, "description": "GPT-4 增强版"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "context_length": 16385, "description": "经济实惠"},
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
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "context_length": 200000, "description": "最新 Claude 模型"},
            {"id": "claude-3-5-sonnet-latest", "name": "Claude 3.5 Sonnet", "context_length": 200000, "description": "Claude 3.5 系列主力"},
            {"id": "claude-3-5-haiku-latest", "name": "Claude 3.5 Haiku", "context_length": 200000, "description": "快速响应版"},
            {"id": "claude-3-opus-latest", "name": "Claude 3 Opus", "context_length": 200000, "description": "最强推理能力"},
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
            {"id": "glm-4-plus", "name": "GLM-4 Plus", "context_length": 128000, "description": "旗舰模型，综合能力最强"},
            {"id": "glm-4-0520", "name": "GLM-4 0520", "context_length": 128000, "description": "高性价比版本"},
            {"id": "glm-4-air", "name": "GLM-4 Air", "context_length": 128000, "description": "快速响应版"},
            {"id": "glm-4-flash", "name": "GLM-4 Flash", "context_length": 128000, "description": "极速版，免费额度"},
            {"id": "glm-4-long", "name": "GLM-4 Long", "context_length": 1000000, "description": "超长上下文"},
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
            {"id": "qwen-max", "name": "Qwen Max", "context_length": 32000, "description": "旗舰模型"},
            {"id": "qwen-max-longcontext", "name": "Qwen Max 长文本", "context_length": 28000, "description": "长文本版本"},
            {"id": "qwen-plus", "name": "Qwen Plus", "context_length": 128000, "description": "高性价比"},
            {"id": "qwen-turbo", "name": "Qwen Turbo", "context_length": 128000, "description": "快速响应"},
            {"id": "qwen-long", "name": "Qwen Long", "context_length": 1000000, "description": "超长上下文"},
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
            {"id": "deepseek-chat", "name": "DeepSeek Chat", "context_length": 64000, "description": "对话模型"},
            {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner", "context_length": 64000, "description": "推理模型（R1）"},
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
            {"id": "moonshot-v1-8k", "name": "Moonshot V1 8K", "context_length": 8192, "description": "标准版"},
            {"id": "moonshot-v1-32k", "name": "Moonshot V1 32K", "context_length": 32768, "description": "长文本版"},
            {"id": "moonshot-v1-128k", "name": "Moonshot V1 128K", "context_length": 131072, "description": "超长文本版"},
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
            {"id": "Baichuan4", "name": "Baichuan 4", "context_length": 128000, "description": "最新旗舰"},
            {"id": "Baichuan3-Turbo", "name": "Baichuan 3 Turbo", "context_length": 32000, "description": "快速版"},
            {"id": "Baichuan3-Turbo-128k", "name": "Baichuan 3 Turbo 128K", "context_length": 128000, "description": "长文本版"},
        ],
    },
    {
        "id": "wenxin",
        "name": "百度文心一言",
        "description": "ERNIE 系列大模型",
        "default_model": "ernie-4.0-8k",
        "default_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        "requires_api_key": True,
        "api_key_url": "https://console.bce.baidu.com/qianfan/",
        "models": [
            {"id": "ernie-4.0-8k", "name": "ERNIE 4.0", "context_length": 8192, "description": "旗舰模型"},
            {"id": "ernie-4.0-turbo-8k", "name": "ERNIE 4.0 Turbo", "context_length": 8192, "description": "快速版"},
            {"id": "ernie-3.5-8k", "name": "ERNIE 3.5", "context_length": 8192, "description": "经济版"},
            {"id": "ernie-speed-8k", "name": "ERNIE Speed", "context_length": 8192, "description": "极速版"},
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
            {"id": "yi-large", "name": "Yi Large", "context_length": 32000, "description": "旗舰模型"},
            {"id": "yi-large-turbo", "name": "Yi Large Turbo", "context_length": 16384, "description": "快速版"},
            {"id": "yi-medium", "name": "Yi Medium", "context_length": 16384, "description": "中等规格"},
            {"id": "yi-spark", "name": "Yi Spark", "context_length": 16384, "description": "极速版"},
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
            {"id": "abab6.5-chat", "name": "ABAB 6.5", "context_length": 245000, "description": "旗舰模型"},
            {"id": "abab6.5s-chat", "name": "ABAB 6.5S", "context_length": 245000, "description": "快速版"},
            {"id": "abab5.5-chat", "name": "ABAB 5.5", "context_length": 16384, "description": "标准版"},
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
            {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4 (via OR)", "context_length": 200000, "description": "通过 OpenRouter"},
            {"id": "openai/gpt-4o", "name": "GPT-4o (via OR)", "context_length": 128000, "description": "通过 OpenRouter"},
            {"id": "google/gemini-pro-1.5", "name": "Gemini Pro 1.5 (via OR)", "context_length": 2800000, "description": "Google 长文本"},
            {"id": "meta-llama/llama-3.1-405b", "name": "Llama 3.1 405B (via OR)", "context_length": 131072, "description": "开源最强"},
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
        "models": [],  # 用户自定义
    },
]


class EmbeddingConfig(BaseModel):
    """Embedding 配置"""
    provider: str
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    dimension: int = 0


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: str
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


class AppConfig(BaseModel):
    """应用配置"""
    embedding: EmbeddingConfig


class ConfigTestResult(BaseModel):
    """配置测试结果"""
    success: bool
    message: str


@router.get("/embedding/providers")
async def get_embedding_providers() -> List[Dict[str, Any]]:
    """获取所有支持的 Embedding Provider 信息"""
    return EMBEDDING_PROVIDERS


@router.get("/embedding")
async def get_embedding_config() -> Dict[str, Any]:
    """获取当前 Embedding 配置"""
    from app.config import settings

    return {
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "api_key": "***" if settings.embedding_api_key else "",
        "base_url": settings.embedding_base_url,
        "dimension": settings.embedding_dimension,
    }


@router.put("/embedding")
async def update_embedding_config(config: EmbeddingConfig) -> Dict[str, Any]:
    """
    更新 Embedding 配置（运行时生效）

    注意：此接口仅更新运行时配置，不会修改 .env 文件
    重启后配置会从 .env 文件重新加载
    """
    from app.config import settings
    from app.services.embedding_service import create_embedding_service

    valid_providers = [p["id"] for p in EMBEDDING_PROVIDERS]
    if config.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 provider: {config.provider}，可选：{valid_providers}"
        )

    provider_info = next(p for p in EMBEDDING_PROVIDERS if p["id"] == config.provider)
    model = config.model or provider_info["default_model"]
    base_url = config.base_url or provider_info["default_url"]
    dimension = config.dimension or provider_info["default_dimension"]

    settings.embedding_provider = config.provider
    settings.embedding_model = model
    if config.api_key:
        settings.embedding_api_key = config.api_key
    settings.embedding_base_url = base_url
    settings.embedding_dimension = dimension

    try:
        service = create_embedding_service(
            provider=config.provider,
            model=model,
            api_key=config.api_key,
            base_url=base_url,
            dimension=dimension,
        )
        success, message = await service.test_connection()

        if success:
            from app.api.app import set_embedding_service
            set_embedding_service(service)

            return {
                "success": True,
                "message": f"配置已更新：{config.provider} ({model}) - {message}",
                "config": {
                    "provider": config.provider,
                    "model": model,
                    "base_url": base_url,
                    "dimension": dimension,
                },
            }
        else:
            return {
                "success": False,
                "message": f"配置已保存但连接测试失败：{message}",
                "config": {
                    "provider": config.provider,
                    "model": model,
                    "base_url": base_url,
                    "dimension": dimension,
                },
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置更新失败：{str(e)}")


@router.post("/embedding/test")
async def test_embedding_config(config: Optional[EmbeddingConfig] = None) -> Dict[str, Any]:
    """
    测试 Embedding 连接

    如果提供 config 参数，则测试该配置；否则测试当前配置
    """
    from app.config import settings
    from app.services.embedding_service import create_embedding_service

    if config:
        provider = config.provider
        model = config.model
        api_key = config.api_key
        base_url = config.base_url
        dimension = config.dimension
    else:
        provider = settings.embedding_provider
        model = settings.embedding_model
        api_key = settings.embedding_api_key
        base_url = settings.embedding_base_url
        dimension = settings.embedding_dimension

    try:
        service = create_embedding_service(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            dimension=dimension,
        )
        success, message = await service.test_connection()

        return {
            "success": success,
            "message": message,
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


@router.get("/llm/providers")
async def get_llm_providers() -> List[Dict[str, Any]]:
    """获取所有支持的 LLM Provider 信息"""
    return LLM_PROVIDERS


@router.get("/llm")
async def get_llm_config() -> Dict[str, Any]:
    """获取当前 LLM 配置"""
    from app.config import settings

    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "api_key": "***" if settings.llm_api_key else "",
        "base_url": settings.llm_base_url,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }


@router.put("/llm")
async def update_llm_config(config: LLMConfig) -> Dict[str, Any]:
    """更新 LLM 配置（运行时生效）"""
    from app.config import settings
    from app.services.model_router import create_llm

    valid_providers = [p["id"] for p in LLM_PROVIDERS]
    if config.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 provider: {config.provider}，可选：{valid_providers}"
        )

    provider_info = next(p for p in LLM_PROVIDERS if p["id"] == config.provider)
    model = config.model or provider_info["default_model"]
    base_url = config.base_url or provider_info["default_url"]

    settings.llm_provider = config.provider
    settings.llm_model = model
    if config.api_key:
        settings.llm_api_key = config.api_key
    settings.llm_base_url = base_url
    settings.llm_temperature = config.temperature
    settings.llm_max_tokens = config.max_tokens

    try:
        create_llm(
            provider=config.provider,
            model=model,
            api_key=settings.llm_api_key,
            base_url=base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        return {
            "success": True,
            "message": f"LLM 配置已更新：{config.provider} ({model})",
            "config": {
                "provider": config.provider,
                "model": model,
                "base_url": base_url,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 配置更新失败：{str(e)}")


@router.post("/llm/test")
async def test_llm_config(config: Optional[LLMConfig] = None) -> Dict[str, Any]:
    """测试 LLM 连接"""
    from app.config import settings
    from app.services.model_router import create_llm

    if config:
        provider = config.provider
        model = config.model
        api_key = config.api_key or settings.llm_api_key
        base_url = config.base_url
        temperature = config.temperature
        max_tokens = config.max_tokens
    else:
        provider = settings.llm_provider
        model = settings.llm_model
        api_key = settings.llm_api_key
        base_url = settings.llm_base_url
        temperature = settings.llm_temperature
        max_tokens = settings.llm_max_tokens

    try:
        llm = create_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        await llm.ainvoke([{"role": "user", "content": "请回复 test"}])
        return {
            "success": True,
            "message": "LLM 连接测试成功",
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


@router.get("/llm/providers/{provider_id}/models")
async def get_provider_models(provider_id: str) -> Dict[str, Any]:
    """
    获取指定 Provider 支持的模型列表

    返回模型 ID、名称、上下文长度等信息
    """
    provider = next((p for p in LLM_PROVIDERS if p["id"] == provider_id), None)
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider not found: {provider_id}"
        )

    return {
        "provider_id": provider_id,
        "provider_name": provider["name"],
        "models": provider.get("models", []),
        "default_model": provider["default_model"],
    }
