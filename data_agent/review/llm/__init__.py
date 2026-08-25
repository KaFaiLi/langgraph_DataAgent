"""Cost-tiered LLM providers for the controlled review workflow."""

from __future__ import annotations

import json
from typing import Any, Protocol

from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

from data_agent.config import Settings, get_settings
from data_agent.llm import get_chat_model
from data_agent.review.llm.models import ModelTier
from data_agent.review.llm.runner import (
    AgentCapabilityError,
    run_bounded_agent,
    run_bounded_structured_agent,
)


class ReviewLLMProvider(Protocol):
    def __call__(
        self, tier: ModelTier, schema: type[BaseModel] | None = None
    ) -> Runnable[Any, Any]: ...


class _CostTierReviewProvider:
    """Shared structured-output behavior for one configured model provider."""

    provider_name: str

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def model_name(self, tier: ModelTier) -> str:
        raise NotImplementedError

    def model_options(self) -> dict[str, Any]:
        return {}

    def structured_output(
        self, model: Runnable[Any, Any], schema: type[BaseModel]
    ) -> Runnable[Any, Any]:
        return model.with_structured_output(schema)

    def __call__(
        self, tier: ModelTier, schema: type[BaseModel] | None = None
    ) -> Runnable[Any, Any]:
        model = get_chat_model(
            provider=self.provider_name,
            settings=self.settings,
            model=self.model_name(tier),
            **self.model_options(),
        )
        if schema is None:
            return model
        try:
            return self.structured_output(model, schema)
        except (AttributeError, NotImplementedError):
            return _json_structured(model, schema)


class SocGenAIReviewProvider(_CostTierReviewProvider):
    """Map review cost tiers to explicitly configured SocGenAI models."""

    provider_name = "socgenai"

    def model_name(self, tier: ModelTier) -> str:
        return (
            self.settings.socgenai_low_cost_model
            if tier is ModelTier.LOW_COST
            else self.settings.socgenai_high_cost_model
        )


class DeepSeekReviewProvider(_CostTierReviewProvider):
    """Map review cost tiers to DeepSeek v4 flash/pro models."""

    provider_name = "deepseek"

    def model_options(self) -> dict[str, Any]:
        return {
            "max_retries": self.settings.deepseek_max_retries,
            # Review calls are schema-constrained and already use low/high-cost
            # model selection. DeepSeek v4 enables high-effort thinking by
            # default, which greatly lengthens these JSON generations and is
            # incompatible with forced tool selection. Keep it explicit here.
            "extra_body": {"thinking": {"type": "disabled"}},
        }

    def structured_output(
        self, model: Runnable[Any, Any], schema: type[BaseModel]
    ) -> Runnable[Any, Any]:
        # DeepSeek v4 thinking models reject the forced tool choice emitted by
        # LangChain's default function-calling mode. JSON mode avoids tools and
        # requires the requested schema to be included explicitly in the prompt.
        return _json_mode_structured(model, schema)

    def model_name(self, tier: ModelTier) -> str:
        return (
            self.settings.deepseek_low_cost_model
            if tier is ModelTier.LOW_COST
            else self.settings.deepseek_high_cost_model
        )


class ConfiguredReviewProvider:
    """Select the cost-tier adapter named by the shared ``LLM_PROVIDER`` setting."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        selected = self.settings.llm_provider.strip().lower()
        providers: dict[str, ReviewLLMProvider] = {
            "deepseek": DeepSeekReviewProvider(self.settings),
            "socgenai": SocGenAIReviewProvider(self.settings),
        }
        try:
            self.provider = providers[selected]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported LLM_PROVIDER={selected!r}. Use 'socgenai' or 'deepseek'."
            ) from exc

    def __call__(
        self, tier: ModelTier, schema: type[BaseModel] | None = None
    ) -> Runnable[Any, Any]:
        return self.provider(tier, schema)


def _json_structured(model: Runnable[Any, Any], schema: type[BaseModel]) -> Runnable[Any, Any]:
    instruction = HumanMessage(
        content=(
            "Return only JSON matching this schema. No Markdown fences.\n"
            + json.dumps(schema.model_json_schema(), default=str)
        )
    )

    def invoke(messages: Any) -> Any:
        sequence = list(messages) if isinstance(messages, list) else [messages]
        return model.invoke([*sequence, instruction])

    return RunnableLambda(invoke)


def _json_mode_structured(model: Runnable[Any, Any], schema: type[BaseModel]) -> Runnable[Any, Any]:
    runnable = model.with_structured_output(schema, method="json_mode")
    instruction = HumanMessage(
        content=(
            "Return only one JSON object matching this schema exactly. "
            "Do not add Markdown fences or fields outside the schema.\n"
            + json.dumps(schema.model_json_schema(), default=str)
        )
    )

    def add_schema_instruction(messages: Any) -> list[Any]:
        sequence = list(messages) if isinstance(messages, list) else [messages]
        return [*sequence, instruction]

    return RunnableLambda(add_schema_instruction) | runnable


DEFAULT_LLM_PROVIDER: ReviewLLMProvider = ConfiguredReviewProvider()


__all__ = [
    "DEFAULT_LLM_PROVIDER",
    "AgentCapabilityError",
    "ConfiguredReviewProvider",
    "DeepSeekReviewProvider",
    "ModelTier",
    "ReviewLLMProvider",
    "SocGenAIReviewProvider",
    "run_bounded_agent",
    "run_bounded_structured_agent",
]
