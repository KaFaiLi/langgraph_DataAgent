"""Typed failures raised by the review LLM invocation boundary."""

from __future__ import annotations

from typing import Any


class LLMInvocationError(RuntimeError):
    """Base class for failures attributed to one LLM work item."""

    def __init__(self, message: str, *, cause: Exception) -> None:
        super().__init__(message)
        self.cause = cause
        self.original_type = type(cause).__name__


class RetryableLLMError(LLMInvocationError):
    """A temporary provider failure that may be resumed from its checkpoint."""

    def __init__(self, message: str, *, cause: Exception, attempts: int) -> None:
        super().__init__(message, cause=cause)
        self.attempts = attempts


class StructuredOutputError(LLMInvocationError):
    """The provider responded, but its payload did not satisfy the requested schema."""


class ProviderInvocationError(LLMInvocationError):
    """A non-retryable provider or request-configuration failure."""


_RETRYABLE_NAMES = {
    "APIConnectionError",
    "APITimeoutError",
    "ConnectionError",
    "ConnectError",
    "ConnectTimeout",
    "ReadTimeout",
    "RateLimitError",
    "TimeoutError",
}
_RETRYABLE_STATUS_CODES = {408, 409, 425, 429}


def is_retryable_provider_error(exc: BaseException) -> bool:
    """Classify common provider-neutral transient failures, including wrapped causes."""

    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        nested = getattr(current, "exceptions", ())
        if nested and any(is_retryable_provider_error(item) for item in nested):
            return True
        if isinstance(current, (ConnectionError, TimeoutError)):
            return True
        if type(current).__name__ in _RETRYABLE_NAMES:
            return True
        status = _status_code(current)
        if status in _RETRYABLE_STATUS_CODES or (status is not None and status >= 500):
            return True
        current = current.__cause__ or current.__context__
    return False


def _status_code(exc: BaseException) -> int | None:
    value: Any = getattr(exc, "status_code", None)
    if value is None:
        value = getattr(getattr(exc, "response", None), "status_code", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
