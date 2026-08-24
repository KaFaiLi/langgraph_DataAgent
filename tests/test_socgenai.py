"""Tests for direct SocGenAI model construction."""

import sys
from types import ModuleType

from data_agent.config import Settings
from data_agent.llm import get_chat_model


def test_builds_socgenai_model_from_settings(monkeypatch):
    module = ModuleType("socgenai_llm")

    class StubModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    module.GenAIChatModel = StubModel
    monkeypatch.setitem(sys.modules, "socgenai_llm", module)

    settings = Settings(
        llm_provider="socgenai",
        genai_model="gpt-test",
        genai_temperature=0.25,
    )
    model = get_chat_model(settings=settings, max_tokens=123)

    assert model.kwargs == {
        "model": "gpt-test",
        "temperature": 0.25,
        "max_tokens": 123,
    }


def test_builds_deepseek_model_from_settings(monkeypatch):
    module = ModuleType("langchain_deepseek")

    class StubModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    module.ChatDeepSeek = StubModel
    monkeypatch.setitem(sys.modules, "langchain_deepseek", module)

    settings = Settings(
        llm_provider="deepseek",
        deepseek_model="deepseek-test",
        deepseek_temperature=0.2,
        deepseek_api_key="key-from-settings",
    )
    model = get_chat_model(settings=settings, max_tokens=456)

    assert model.kwargs == {
        "model": "deepseek-test",
        "temperature": 0.2,
        "api_key": "key-from-settings",
        "max_tokens": 456,
    }
