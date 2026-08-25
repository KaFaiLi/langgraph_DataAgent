"""Build the native SocGenAI LangChain chat model."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from data_agent.config import Settings, get_settings


def get_chat_model(
    *,
    model: str | None = None,
    settings: Settings | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Return ``socgenai_llm.GenAIChatModel`` configured from settings."""
    settings = settings or get_settings()
    try:
        from socgenai_llm import GenAIChatModel
    except ModuleNotFoundError as exc:
        if exc.name != "socgenai_llm":
            raise
        raise RuntimeError(
            "socgenai_llm is not installed. Install the internal package and set "
            "LLM_PROVIDER=socgenai, or use the default DeepSeek provider."
        ) from exc

    return GenAIChatModel(
        model=model or settings.genai_model,
        **kwargs,
    )
