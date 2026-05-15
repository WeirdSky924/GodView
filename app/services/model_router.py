"""
模型路由服务 - 根据配置创建 LLM 实例
简化版：只区分 OpenAI 兼容 API 和 Anthropic API
"""

import logging
from typing import Optional

import httpx

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


def create_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseLanguageModel:
    """
    根据配置创建 LangChain 语言模型实例。

    简化逻辑：
    - provider == "anthropic" → 使用 ChatAnthropic
    - 其他所有情况 → 使用 ChatOpenAI（OpenAI 兼容 API）

    前端的 provider 选择只是预填配置，不影响后端调用方式。
    """
    provider = (provider or settings.llm_provider or "openai").strip().lower()

    # 获取当前 provider 的配置
    llm_config = settings.get_llm_config(provider)

    model_name = model or llm_config.get("model", "")
    api_key = api_key if api_key is not None else llm_config.get("api_key", "")
    base_url = _normalize_base_url(base_url if base_url is not None else llm_config.get("base_url", ""))
    temperature = llm_config.get("temperature", 0.7) if temperature is None else temperature
    max_tokens = llm_config.get("max_tokens", 4096) if max_tokens is None else max_tokens

    logger.info(f"create_llm: provider={provider}, model={model_name}, base_url={base_url}")

    if not api_key:
        logger.warning("未配置 LLM_API_KEY，返回占位模型")
        return MissingAPIKeyModel(provider=provider, model_name=model_name)

    # Anthropic 使用专用 SDK
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
        client = httpx.Client(event_hooks={"response": [_log_llm_error_response]})
        async_client = httpx.AsyncClient(event_hooks={"response": [_log_llm_error_response_async]})
        kwargs["client"] = client
        kwargs["async_client"] = async_client
        return ChatAnthropic(**kwargs)

    # 其他所有 provider 都使用 OpenAI 兼容 API
    # 包括：openai, zhipu, qwen, deepseek, moonshot, baichuan, wenxin, yi, minimax, openrouter, custom 等
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

    # base_url 必须由用户在配置界面填写（前端选择 provider 时会预填）
    if base_url:
        kwargs["base_url"] = base_url

    # OpenRouter 需要额外的 headers
    if provider == "openrouter":
        kwargs["default_headers"] = {
            "HTTP-Referer": "https://godview.app",
            "X-Title": "GodView",
        }

    return ChatOpenAI(**kwargs)


def _normalize_base_url(base_url: Optional[str]) -> Optional[str]:
    """规范化 base_url"""
    if not base_url:
        return None
    value = base_url.strip()
    return value or None


def _redact_headers(headers: httpx.Headers) -> dict:
    sensitive_names = {"authorization", "x-api-key", "api-key", "cookie", "set-cookie"}
    return {
        key: "<redacted>" if key.lower() in sensitive_names else value
        for key, value in headers.items()
    }


def _truncate_for_log(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<truncated {len(text) - limit} chars>"


def _log_llm_error_response(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    try:
        response.read()
        body = response.text
    except Exception as exc:
        body = f"<failed to read response body: {exc}>"
    logger.error(
        "LLM HTTP error response: status=%s method=%s url=%s request_headers=%s response_headers=%s body=%s",
        response.status_code,
        response.request.method,
        response.request.url,
        _redact_headers(response.request.headers),
        _redact_headers(response.headers),
        _truncate_for_log(body),
    )


async def _log_llm_error_response_async(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    try:
        await response.aread()
        body = response.text
    except Exception as exc:
        body = f"<failed to read response body: {exc}>"
    logger.error(
        "LLM HTTP error response: status=%s method=%s url=%s request_headers=%s response_headers=%s body=%s",
        response.status_code,
        response.request.method,
        response.request.url,
        _redact_headers(response.request.headers),
        _redact_headers(response.headers),
        _truncate_for_log(body),
    )


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
