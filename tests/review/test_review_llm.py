from __future__ import annotations

from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel

from data_agent.config import Settings
from data_agent.review.llm import (
    ConfiguredReviewProvider,
    DeepSeekReviewProvider,
    ModelTier,
    SocGenAIReviewProvider,
)


class _Payload(BaseModel):
    value: str


def test_model_tiers_expose_only_cost_based_names() -> None:
    assert set(ModelTier.__members__) == {"LOW_COST", "HIGH_COST"}


def test_review_provider_maps_cost_roles_to_explicit_models(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeModel:
        def with_structured_output(self, schema):
            calls.append({"schema": schema})
            return (self, schema)

    def fake_get_chat_model(**kwargs):
        calls.append(kwargs)
        return FakeModel()

    monkeypatch.setattr("data_agent.review.llm.get_chat_model", fake_get_chat_model)
    settings = Settings(
        _env_file=None,
        socgenai_low_cost_model="low-model",
        socgenai_high_cost_model="high-model",
    )
    provider = SocGenAIReviewProvider(settings)

    provider(ModelTier.LOW_COST)
    provider(ModelTier.HIGH_COST, _Payload)

    assert calls[0]["model"] == "low-model"
    assert calls[0]["provider"] == "socgenai"
    assert calls[1]["model"] == "high-model"
    assert calls[2] == {"schema": _Payload}


def test_deepseek_review_provider_maps_cost_roles_to_v4_models(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeModel:
        def with_structured_output(self, schema, **kwargs):
            calls.append({"schema": schema, **kwargs})
            return RunnableLambda(lambda messages: messages)

    def fake_get_chat_model(**kwargs):
        calls.append(kwargs)
        return FakeModel()

    monkeypatch.setattr("data_agent.review.llm.get_chat_model", fake_get_chat_model)
    settings = Settings(
        _env_file=None,
        deepseek_low_cost_model="deepseek-v4-flash",
        deepseek_high_cost_model="deepseek-v4-pro",
    )
    provider = DeepSeekReviewProvider(settings)

    provider(ModelTier.LOW_COST)
    runnable = provider(ModelTier.HIGH_COST, _Payload)

    assert calls[0]["model"] == "deepseek-v4-flash"
    assert calls[0]["provider"] == "deepseek"
    assert calls[0]["max_retries"] == 5
    assert calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert calls[1]["model"] == "deepseek-v4-pro"
    assert calls[1]["max_retries"] == 5
    assert calls[1]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert calls[2] == {"schema": _Payload, "method": "json_mode"}
    messages = runnable.invoke([])
    assert '"value"' in messages[-1].content


def test_configured_review_provider_respects_shared_provider_setting() -> None:
    deepseek = ConfiguredReviewProvider(Settings(_env_file=None, llm_provider="deepseek"))
    socgenai = ConfiguredReviewProvider(Settings(_env_file=None, llm_provider="socgenai"))

    assert isinstance(deepseek.provider, DeepSeekReviewProvider)
    assert isinstance(socgenai.provider, SocGenAIReviewProvider)
