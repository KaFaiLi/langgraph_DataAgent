"""LangChain chat model construction for supported providers."""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from data_agent.config import Settings, get_settings
from data_agent.llm.deepseek import get_deepseek_chat_model
from data_agent.llm.socgenai import get_chat_model as get_socgenai_chat_model


def get_chat_model(
    *,
    provider: str | None = None,
    settings: Settings | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Build a chat model for the configured provider."""
    settings = settings or get_settings()
    selected_provider = (provider or settings.llm_provider).strip().lower()
    if selected_provider == "socgenai":
        return get_socgenai_chat_model(settings=settings, **kwargs)
    if selected_provider == "deepseek":
        return get_deepseek_chat_model(settings=settings, **kwargs)
    raise ValueError(
        f"Unsupported LLM_PROVIDER={selected_provider!r}. Use 'socgenai' or 'deepseek'."
    )


__all__ = ["get_chat_model", "get_deepseek_chat_model"]
