"""Token / size estimation.

Uses ``tiktoken`` when installed for accurate counts, and falls back to a
character-based heuristic otherwise so the template works with zero extra deps.
"""

from __future__ import annotations

from typing import Any

# Rough industry heuristic: ~4 characters per token for English text.
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str, model: str = "gpt-4o-mini") -> tuple[int, str]:
    """Estimate the number of tokens in ``text``.

    Returns a ``(token_count, method)`` tuple where ``method`` is either the
    tiktoken encoding name or ``"heuristic:chars/4"``.
    """
    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), enc.name
    except Exception:
        # tiktoken missing or failed -> heuristic.
        return max(1, len(text) // _CHARS_PER_TOKEN), "heuristic:chars/4"


def payload_stats(payload: str) -> dict[str, Any]:
    """Return a size profile of a payload string."""
    tokens, method = estimate_tokens(payload)
    return {
        "tokens": tokens,
        "tokenizer": method,
        "bytes": len(payload.encode("utf-8")),
        "characters": len(payload),
        "lines": payload.count("\n") + 1 if payload else 0,
    }

