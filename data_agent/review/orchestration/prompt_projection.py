"""Bounded projections of review state for specialist model prompts."""

from __future__ import annotations

import json
from typing import Any

from data_agent.review.domain.finding import Finding

MAX_ANALYSIS_PROMPT_CHARS = 60_000
MAX_REVISION_ANALYSIS_CHARS = 25_000
MAX_VERIFIER_SUPPORT_CHARS = 18_000


def _compact(value: object, *, depth: int = 0) -> object:
    if depth >= 5:
        return "[nested value omitted]"
    if isinstance(value, str):
        return value if len(value) <= 2_000 else value[:1_997] + "..."
    if isinstance(value, list):
        compacted = [_compact(item, depth=depth + 1) for item in value[:20]]
        if len(value) > 20:
            compacted.append(f"[{len(value) - 20} item(s) omitted]")
        return compacted
    if isinstance(value, dict):
        return {str(key): _compact(item, depth=depth + 1) for key, item in list(value.items())[:50]}
    return value


def bounded_analyses_json(
    analyses: list[dict[str, object]], *, max_chars: int = MAX_ANALYSIS_PROMPT_CHARS
) -> str:
    """Fairly project large analyses without letting one source consume the prompt."""
    payload: list[dict[str, object]] = []
    for analysis in analyses:
        flags = analysis.get("flag_candidates", [])
        tables = analysis.get("tables", [])
        payload.append(
            {
                "name": analysis.get("name", "?"),
                "summary": _compact(analysis.get("summary", "")),
                "flag_candidate_count": len(flags) if isinstance(flags, list) else 0,
                "table_count": len(tables) if isinstance(tables, list) else 0,
                "flag_candidates": [],
                "tables": [],
            }
        )

    def add_round_robin(field: str) -> bool:
        positions = [0] * len(analyses)
        while True:
            progressed = False
            for index, analysis in enumerate(analyses):
                values = analysis.get(field, [])
                if not isinstance(values, list) or positions[index] >= len(values):
                    continue
                progressed = True
                target = payload[index][field]
                if not isinstance(target, list):
                    raise TypeError(f"prompt projection field {field!r} must be a list")
                target.append(_compact(values[positions[index]]))
                if len(json.dumps(payload, indent=2, default=str)) > max_chars:
                    target.pop()
                    return False
                positions[index] += 1
            if not progressed:
                return True

    if add_round_robin("flag_candidates"):
        add_round_robin("tables")
    return json.dumps(payload, indent=2, default=str)


def _source_locators(value: object) -> set[str]:
    if isinstance(value, str):
        return {value} if value.startswith("source://") else set()
    if isinstance(value, list):
        return {locator for item in value for locator in _source_locators(item)}
    if isinstance(value, dict):
        return {locator for item in value.values() for locator in _source_locators(item)}
    return set()


def finding_analysis_support_json(
    finding: Finding,
    analyses: list[dict[str, object]],
    *,
    max_chars: int = MAX_VERIFIER_SUPPORT_CHARS,
) -> str:
    """Project deterministic candidates sharing a finding's evidence locators."""
    finding_locators = {
        reference.locator for reference in [*finding.evidence, *finding.counter_evidence]
    }
    payload: list[dict[str, object]] = []
    for analysis in analyses:
        flags = analysis.get("flag_candidates", [])
        if not isinstance(flags, list):
            continue
        matching = [
            _compact(flag)
            for flag in flags
            if finding_locators.intersection(_source_locators(flag))
        ]
        if matching:
            payload.append(
                {
                    "name": analysis.get("name", "?"),
                    "summary": _compact(analysis.get("summary", "")),
                    "matching_flag_candidates": matching,
                }
            )

    encoded = json.dumps(payload, indent=2, default=str)
    if len(encoded) <= max_chars:
        return encoded

    bounded = [
        {
            "name": item["name"],
            "summary": _compact(item["summary"]),
            "matching_flag_candidates": [],
        }
        for item in payload
    ]
    positions = [0] * len(payload)
    while True:
        progressed = False
        for index, item in enumerate(payload):
            flags = item["matching_flag_candidates"]
            if not isinstance(flags, list) or positions[index] >= len(flags):
                continue
            progressed = True
            target = bounded[index]["matching_flag_candidates"]
            if not isinstance(target, list):
                raise TypeError("matching_flag_candidates must be a list")
            target.append(flags[positions[index]])
            candidate = json.dumps(bounded, indent=2, default=str)
            if len(candidate) > max_chars:
                target.pop()
                return json.dumps(bounded, indent=2, default=str)
            positions[index] += 1
        if not progressed:
            return json.dumps(bounded, indent=2, default=str)


def revision_candidates_json(candidates: list[dict[str, Any]]) -> str:
    """Compact prior candidates while preserving IDs and evidence locators."""
    payload = [
        {
            "finding_id": candidate.get("finding_id"),
            "title": str(candidate.get("title", ""))[:300],
            "category": candidate.get("category"),
            "severity": candidate.get("severity"),
            "confidence": candidate.get("confidence"),
            "claim": str(candidate.get("claim", ""))[:1_200],
            "period": candidate.get("period"),
            "evidence": _compact(candidate.get("evidence", [])),
            "alternative_explanations": _compact(candidate.get("alternative_explanations", [])),
            "counter_evidence": _compact(candidate.get("counter_evidence", [])),
            "recommendation": str(candidate.get("recommendation") or "")[:500],
        }
        for candidate in candidates
    ]
    encoded = json.dumps(payload, separators=(",", ":"), default=str)
    if len(encoded) <= 28_000:
        return encoded
    minimal = [
        {
            "finding_id": candidate.get("finding_id"),
            "title": str(candidate.get("title", ""))[:200],
            "claim": str(candidate.get("claim", ""))[:600],
            "period": candidate.get("period"),
            "evidence_locators": [
                reference.get("locator")
                for reference in candidate.get("evidence", [])
                if isinstance(reference, dict)
            ],
        }
        for candidate in candidates
    ]
    return json.dumps(minimal, separators=(",", ":"), default=str)


def bounded_revision_feedback(feedback: str, *, max_chars: int) -> str:
    """Retain a fair slice of every per-finding verifier response."""
    if len(feedback) <= max_chars:
        return feedback
    sections = feedback.split("\n\n---\n\n")
    per_section = max(400, max_chars // max(len(sections), 1))
    return "\n\n---\n\n".join(section[:per_section] for section in sections)[:max_chars]
