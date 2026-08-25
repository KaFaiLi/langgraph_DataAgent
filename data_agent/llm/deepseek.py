"""Build a LangChain DeepSeek chat model."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from data_agent.config import Settings, get_settings


def get_deepseek_chat_model(
    *,
    model: str | None = None,
    api_key: str | None = None,
    settings: Settings | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Return ``langchain_deepseek.ChatDeepSeek`` configured from settings."""
    settings = settings or get_settings()
    try:
        from langchain_deepseek import ChatDeepSeek
    except ModuleNotFoundError as exc:
        if exc.name != "langchain_deepseek":
            raise
        raise RuntimeError(
            "langchain-deepseek is not installed; run `pip install langchain-deepseek`."
        ) from exc

    model_kwargs: dict[str, Any] = {
        "model": model or settings.deepseek_model,
        **kwargs,
    }
    configured_api_key = api_key or (
        settings.deepseek_api_key.get_secret_value() if settings.deepseek_api_key else None
    )
    if configured_api_key:
        model_kwargs["api_key"] = configured_api_key

    return ChatDeepSeek(
        **model_kwargs,
    )
