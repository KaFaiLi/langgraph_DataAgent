from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from data_agent.config import Settings


def test_subagent_settings_have_bounded_opt_in_defaults() -> None:
    settings = Settings()

    assert settings.subagents_enabled is False
    assert settings.subagent_max_runs == 4
    assert settings.subagent_max_concurrency == 2
    assert settings.subagent_max_model_calls == 6
    assert settings.subagent_max_tool_calls == 12
    assert settings.subagent_timeout_seconds == 120.0
    assert settings.subagent_max_input_chars == 16_000
    assert settings.subagent_max_result_chars == 8_000


@pytest.mark.parametrize(
    "field",
    [
        "subagent_max_runs",
        "subagent_max_concurrency",
        "subagent_max_model_calls",
        "subagent_max_tool_calls",
        "subagent_max_input_chars",
        "subagent_max_result_chars",
    ],
)
@pytest.mark.parametrize("value", [0, -1])
def test_subagent_integer_limits_must_be_positive(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_subagent_concurrency_cannot_exceed_run_budget() -> None:
    with pytest.raises(ValidationError, match="subagent_max_concurrency"):
        Settings(subagent_max_runs=1, subagent_max_concurrency=2)


@pytest.mark.parametrize("value", [0, -1, math.inf, -math.inf, math.nan])
def test_subagent_timeout_must_be_positive_and_finite(value: float) -> None:
    with pytest.raises(ValidationError):
        Settings(subagent_timeout_seconds=value)
