"""Provider-neutral structured-output invocation with bounded retries."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel


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
) -> BaseModel:
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            output = runnable.invoke(messages)
            if isinstance(output, schema):
                return output
            return schema.model_validate(_payload(output))
        except Exception as exc:  # bounded provider/schema retry
            last_error = exc
    raise ValueError(
        f"structured output failed after {attempts} attempt(s): {last_error}"
    ) from last_error

