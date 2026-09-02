"""Provider-neutral structured-output invocation with bounded retries."""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ValidationError

from data_agent.review.llm.errors import (
    ProviderInvocationError,
    RetryableLLMError,
    StructuredOutputError,
    is_retryable_provider_error,
)


def _payload(output: Any) -> Any:
    if isinstance(output, BaseModel):
        return output
    content = getattr(output, "content", output)
    if isinstance(content, str):
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
            if text.startswith("json"):
                text = text[4:].lstrip()
        return json.loads(text)
    return content


def invoke_structured(
    runnable: Runnable[Any, Any],
    messages: list[BaseMessage],
    *,
    schema: type[BaseModel],
    attempts: int = 2,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    jitter: float = 0.25,
    _sleep: Callable[[float], None] = time.sleep,
    _random: Callable[[], float] = random.random,
) -> BaseModel:
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if base_delay < 0 or max_delay < 0 or jitter < 0:
        raise ValueError("retry delays and jitter must be >= 0")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            output = runnable.invoke(messages)
        except Exception as exc:
            if not is_retryable_provider_error(exc):
                raise ProviderInvocationError(
                    f"provider invocation failed: {type(exc).__name__}: {exc}", cause=exc
                ) from exc
            last_error = exc
            if attempt < attempts:
                delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                _sleep(delay + (delay * jitter * _random()))
                continue
            break
        try:
            if isinstance(output, schema):
                return output
            return schema.model_validate(_payload(output))
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            raise StructuredOutputError(
                f"malformed structured output for {schema.__name__}: {type(exc).__name__}: {exc}",
                cause=exc,
            ) from exc
    assert last_error is not None
    raise RetryableLLMError(
        f"temporary provider failure after {attempts} attempt(s): "
        f"{type(last_error).__name__}: {last_error}",
        cause=last_error,
        attempts=attempts,
    ) from last_error
