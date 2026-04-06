"""
模型路由服务 - 根据配置创建 LLM 实例
"""

import logging
from typing import Optional

from langchain_core.language_models import BaseLanguageModel

from app.config import settings

logger = logging.getLogger(__name__)


class MissingAPIKeyModel:
    """在未配置真实 LLM 时提供明确报错，避免静默回退到 Mock。"""

    def __init__(self, provider: str, model_name: str):
        self.provider = provider
        self.model_name = model_name

    async def ainvoke(self, messages):
        raise RuntimeError(
            f"LLM 未配置完成：provider={self.provider}, model={self.model_name}。"
            "请先在环境变量中设置 LLM_API_KEY，或通过配置接口更新运行时配置。"
        )


_SUPPORTED_PROVIDERS = {"openai", "anthropic"}


def _normalize_base_url(base_url: Optional[str]) -> Optional[str]:
    if not base_url:
        return None
    value = base_url.strip()
    return value or None


def create_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseLanguageModel:
    """根据配置创建 LangChain 语言模型实例。"""
    provider = (provider or settings.llm_provider or "openai").strip().lower()
    model_name = model or settings.llm_model
    api_key = api_key if api_key is not None else settings.llm_api_key
    base_url = _normalize_base_url(base_url if base_url is not None else settings.llm_base_url)
    temperature = settings.llm_temperature if temperature is None else temperature
    max_tokens = settings.llm_max_tokens if max_tokens is None else max_tokens

    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(f"不支持的 LLM provider: {provider}")

    if not api_key:
        logger.warning("未配置 LLM_API_KEY，返回占位模型")
        return MissingAPIKeyModel(provider=provider, model_name=model_name)

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("缺少依赖 langchain-openai，请先安装") from exc

        kwargs = {
            "model": model_name,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("缺少依赖 langchain-anthropic，请先安装") from exc

        kwargs = {
            "model": model_name,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if base_url:
            kwargs["base_url"] = base_url
        return ChatAnthropic(**kwargs)

    raise ValueError(f"未知的 LLM provider: {provider}")


def create_model_factory(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
):
    """返回一个可复用的模型工厂。"""

    def factory() -> BaseLanguageModel:
        return create_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    return factory
