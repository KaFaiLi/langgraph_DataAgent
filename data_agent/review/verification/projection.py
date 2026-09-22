"""Independent reviewer inputs without analyst anchoring fields."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from data_agent.review.domain.finding import Finding


def _finding_projection(finding: Finding) -> dict[str, Any]:
    """Project a finding while hiding anchoring fields from the challenger."""

    raw = finding.model_dump(mode="json")
    hidden = {"severity", "confidence", "recommendation", "verifier_status"}
    return {key: value for key, value in raw.items() if key not in hidden}


def _strip_hidden(value: object) -> object:
    """Remove anchoring fields from nested deterministic prompt data."""

    hidden = {"severity", "confidence", "recommendation", "verifier_status"}
    if isinstance(value, Mapping):
        return {
            str(key): _strip_hidden(nested)
            for key, nested in value.items()
            if str(key).lower() not in hidden
        }
    if isinstance(value, list):
        return [_strip_hidden(item) for item in value]
    return value
