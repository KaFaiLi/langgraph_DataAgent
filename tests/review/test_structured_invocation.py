"""Tests for typed structured-output invocation failures."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from data_agent.review.llm.errors import (
    ProviderInvocationError,
    RetryableLLMError,
    StructuredOutputError,
)
from data_agent.review.llm.structured import invoke_structured


class _Result(BaseModel):
    value: int


class _SequenceRunnable:
    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = outputs
        self.calls = 0

    def invoke(self, _messages: object) -> Any:
        output = self.outputs[self.calls]
        self.calls += 1
        if isinstance(output, Exception):
            raise output
        return output


def test_retries_temporary_failure_with_exponential_backoff_and_jitter() -> None:
    runnable = _SequenceRunnable([ConnectionError("offline"), TimeoutError("slow"), '{"value": 7}'])
    delays: list[float] = []

    result = invoke_structured(
        runnable,
        [],
        schema=_Result,
        attempts=3,
        base_delay=1,
        jitter=0.5,
        _sleep=delays.append,
        _random=lambda: 0.5,
    )

    assert result.value == 7
    assert delays == [1.25, 2.5]


def test_exhausted_connection_failure_preserves_typed_retryable_error() -> None:
    original = ConnectionError("offline")
    runnable = _SequenceRunnable([original, original])

    with pytest.raises(RetryableLLMError) as caught:
        invoke_structured(runnable, [], schema=_Result, base_delay=0)

    assert caught.value.cause is original
    assert caught.value.original_type == "ConnectionError"
    assert caught.value.attempts == 2


def test_rate_limit_status_is_retryable_without_provider_sdk_dependency() -> None:
    class ProviderError(Exception):
        status_code = 429

    runnable = _SequenceRunnable([ProviderError("limited"), '{"value": 2}'])

    assert invoke_structured(runnable, [], schema=_Result, base_delay=0).value == 2


def test_malformed_response_is_a_distinct_non_retryable_output_error() -> None:
    runnable = _SequenceRunnable(['{"value": "not-an-integer"}', '{"value": 2}'])

    with pytest.raises(StructuredOutputError) as caught:
        invoke_structured(runnable, [], schema=_Result, base_delay=0)

    assert runnable.calls == 1
    assert caught.value.original_type == "ValidationError"


def test_non_temporary_provider_failure_is_not_misclassified_as_output() -> None:
    runnable = _SequenceRunnable([RuntimeError("bad request")])

    with pytest.raises(ProviderInvocationError):
        invoke_structured(runnable, [], schema=_Result, base_delay=0)
