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


class EmbeddingConfig(BaseModel):
    """Embedding 配置"""
    provider: str
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    dimension: int = 0


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

    # 验证 provider
    valid_providers = [p["id"] for p in EMBEDDING_PROVIDERS]
    if config.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 provider: {config.provider}，可选：{valid_providers}"
        )

    # 填充默认值
    provider_info = next(p for p in EMBEDDING_PROVIDERS if p["id"] == config.provider)
    model = config.model or provider_info["default_model"]
    base_url = config.base_url or provider_info["default_url"]
    dimension = config.dimension or provider_info["default_dimension"]

    # 更新 settings
    settings.embedding_provider = config.provider
    settings.embedding_model = model
    if config.api_key:
        settings.embedding_api_key = config.api_key
    settings.embedding_base_url = base_url
    settings.embedding_dimension = dimension

    # 测试新配置
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
            # 更新全局 embedding 服务
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
