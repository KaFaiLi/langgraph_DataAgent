"""Stable identity and deterministic coverage for analysis candidates."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from data_agent.review.domain.evidence import EvidenceReference, format_locator, parse_locator
from data_agent.review.domain.finding import Finding

_PROSE_KEYS = frozenset(
    {
        "summary",
        "rationale",
        "explanation",
        "reason",
        "note",
        "description",
        "message",
        "title",
        "claim",
        "text",
        "quote",
        "recommendation",
        "comment",
        "comments",
        "details_text",
    }
)


def _canonical_locator(value: str) -> str | None:
    if not value.startswith("source://"):
        return None
    try:
        return format_locator(parse_locator(value))
    except ValueError:
        # Invalid citations are handled by the evidence gate.  They should not
        # make candidate identity non-deterministic or crash an omission audit.
        return value


def _collect_locators(value: object) -> set[str]:
    if isinstance(value, EvidenceReference):
        return {value.locator}
    if isinstance(value, str):
        locator = _canonical_locator(value)
        return {locator} if locator is not None else set()
    if isinstance(value, Mapping):
        # Deterministic analysis contracts are skill-owned, so locator-bearing
        # fields are not limited to a small vocabulary (for example,
        # ``prior_locator`` and ``comparison_source`` are both valid).  Walk
        # every value; plain prose strings are ignored by ``_canonical_locator``.
        return {locator for nested in value.values() for locator in _collect_locators(nested)}
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return {locator for item in value for locator in _collect_locators(item)}
    return set()


def candidate_locators(candidate: object) -> set[str]:
    """Return canonical ``source://`` locators embedded in a candidate."""

    return _collect_locators(candidate)


def _stable_value(value: object, *, key: str | None = None) -> object:
    """Canonicalize non-prose values for a stable candidate fingerprint."""

    normalized_key = key.lower() if key else None
    if normalized_key in _PROSE_KEYS or normalized_key in {"candidate_id", "id"}:
        return None
    if isinstance(value, EvidenceReference):
        return value.locator
    if isinstance(value, str):
        locator = _canonical_locator(value)
        return locator if locator is not None else value.strip()
    if isinstance(value, Mapping):
        pairs = []
        for nested_key in sorted(value, key=str):
            value_ = _stable_value(value[nested_key], key=str(nested_key))
            if value_ is not None:
                pairs.append((str(nested_key), value_))
        return dict(pairs)
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [_stable_value(item) for item in value]
        return sorted((item for item in values if item is not None), key=repr)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # Dates and enums have stable string representations; arbitrary objects do
    # not belong in deterministic candidate payloads.
    return str(value)


def candidate_fingerprint(
    analysis_name: str,
    candidate: Mapping[str, Any] | None = None,
    *,
    kind: str | None = None,
    locators: Iterable[str] | None = None,
) -> str:
    """Return a stable SHA-256 fingerprint for one deterministic candidate.

    Locator-bearing candidates are keyed by analysis, kind, and sorted
    canonical locators.  Locator-free candidates include only canonical
    non-prose fields, so generated summaries/rationales cannot change identity.
    """

    data = dict(candidate or {})
    candidate_kind = kind or str(data.get("kind") or data.get("type") or "candidate")
    canonical_locators = sorted(
        _canonical_locator(locator) or locator
        for locator in (set(locators or ()) | candidate_locators(data))
    )
    payload: dict[str, object] = {
        "analysis_name": analysis_name,
        "kind": candidate_kind,
        "locators": canonical_locators,
    }
    if not canonical_locators:
        stable_data = _stable_value(data)
        if stable_data:
            payload["data"] = stable_data
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def stable_candidate_id(
    analysis_name: str,
    candidate: Mapping[str, Any] | str | None = None,
    *positional: object,
    kind: str | None = None,
    locators: Iterable[str] | None = None,
) -> str:
    """Build ``analysis:kind:fingerprint`` for a deterministic candidate."""

    # Accept the compact ``stable_candidate_id(name, kind, locators)`` form in
    # addition to the mapping-oriented interface used by analysis runners.
    if positional:
        if len(positional) > 1:
            raise TypeError("stable_candidate_id accepts at most one positional locator collection")
        if locators is not None:
            raise TypeError("locators supplied both positionally and by keyword")
        locators = positional[0]  # type: ignore[assignment]
    if isinstance(candidate, str) and kind is None:
        kind = candidate
        candidate = None
    data = dict(candidate) if isinstance(candidate, Mapping) else None
    candidate_kind = kind or str(
        (data or {}).get("kind") or (data or {}).get("type") or "candidate"
    )
    digest = candidate_fingerprint(analysis_name, data, kind=candidate_kind, locators=locators)
    return f"{analysis_name}:{candidate_kind}:{digest}"


def assign_candidate_ids(
    analysis_name: str,
    candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Copy candidates and attach stable ``candidate_id`` values.

    The input is never mutated.  Existing IDs are intentionally replaced so a
    stale/volatile model-provided ID cannot defeat deterministic coverage.
    """

    assigned: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        identifier = stable_candidate_id(analysis_name, item)
        item["candidate_id"] = identifier
        item["deterministic_candidate_id"] = identifier
        assigned.append(item)
    return assigned


def _candidate_id(candidate: object, analysis_name: str | None = None) -> str:
    if isinstance(candidate, Mapping):
        existing = candidate.get("candidate_id") or candidate.get("deterministic_candidate_id")
        if isinstance(existing, str) and existing:
            return existing
        name = analysis_name or str(
            candidate.get("analysis_name") or candidate.get("analysis") or "analysis"
        )
        return stable_candidate_id(name, candidate)
    identifier = getattr(candidate, "candidate_id", None)
    if isinstance(identifier, str) and identifier:
        return identifier
    raise TypeError(f"candidate has no deterministic candidate_id: {candidate!r}")


def _finding_locators(finding: Finding) -> set[str]:
    return {reference.locator for reference in [*finding.evidence, *finding.counter_evidence]}


def _locators_overlap(left: str, right: str) -> bool:
    """Return true when two canonical locators identify overlapping regions."""

    try:
        first, second = parse_locator(left), parse_locator(right)
    except ValueError:
        return left == right
    if first.path != second.path:
        return False
    if first.sheet is not None and second.sheet is not None and first.sheet != second.sheet:
        return False
    if first.page is not None and second.page is not None:
        return first.page == second.page
    if first.rows is not None and second.rows is not None:
        return first.rows[0] <= second.rows[1] and second.rows[0] <= first.rows[1]
    if first.lines is not None and second.lines is not None:
        return first.lines[0] <= second.lines[1] and second.lines[0] <= first.lines[1]
    # A path-only reference is broad and therefore overlaps a more specific
    # locator for that path.  The evidence validator decides if it is reopenable.
    return True


def finding_covers_candidate(
    finding: Finding,
    candidate: Mapping[str, Any] | object,
    *,
    analysis_name: str | None = None,
) -> bool:
    """Check explicit-ID or source-region linkage between a finding/candidate."""

    candidate_id = _candidate_id(candidate, analysis_name)
    if candidate_id in finding.deterministic_candidate_ids:
        return True
    candidate_regions = candidate_locators(candidate)
    finding_regions = _finding_locators(finding)
    return any(
        _locators_overlap(finding_locator, candidate_locator)
        for finding_locator in finding_regions
        for candidate_locator in candidate_regions
    )


def covered_candidate_ids(
    candidates: Sequence[Mapping[str, Any] | object],
    findings: Sequence[Finding],
    *,
    analysis_name: str | None = None,
    dispositions: Mapping[str, object] | Sequence[object] | None = None,
) -> list[str]:
    """Return covered IDs in deterministic candidate order.

    Any explicit analyst disposition counts as consideration, including an
    ``UNRESOLVED`` disposition.  Rejected and unresolved findings are passed in
    by the caller just like verified findings because omission is about whether
    a signal was considered, not whether it ultimately survived.
    """

    disposition_ids: set[str] = set()
    if isinstance(dispositions, Mapping):
        disposition_ids = {str(identifier) for identifier in dispositions}
    elif dispositions is not None:
        for disposition in dispositions:
            identifier = getattr(disposition, "candidate_id", None)
            if identifier is None and isinstance(disposition, Mapping):
                identifier = disposition.get("candidate_id")
            if identifier:
                disposition_ids.add(str(identifier))

    covered: list[str] = []
    for candidate in candidates:
        identifier = _candidate_id(candidate, analysis_name)
        if identifier in disposition_ids or any(
            finding_covers_candidate(finding, candidate, analysis_name=analysis_name)
            for finding in findings
        ):
            covered.append(identifier)
    return covered


def find_uncovered_candidates(
    candidates: Sequence[Mapping[str, Any] | object],
    findings: Sequence[Finding],
    *,
    analysis_name: str | None = None,
    dispositions: Mapping[str, object] | Sequence[object] | None = None,
) -> list[object]:
    """Return candidate objects not linked to findings or dispositions."""

    covered = set(
        covered_candidate_ids(
            candidates,
            findings,
            analysis_name=analysis_name,
            dispositions=dispositions,
        )
    )
    return [
        candidate
        for candidate in candidates
        if _candidate_id(candidate, analysis_name) not in covered
    ]


def link_finding_to_candidates(
    finding: Finding,
    candidates: Sequence[Mapping[str, Any] | object],
    *,
    analysis_name: str | None = None,
) -> Finding:
    """Return a finding with deterministic IDs for overlapping candidates added."""

    identifiers = list(finding.deterministic_candidate_ids)
    for candidate in candidates:
        identifier = _candidate_id(candidate, analysis_name)
        if identifier not in identifiers and finding_covers_candidate(
            finding, candidate, analysis_name=analysis_name
        ):
            identifiers.append(identifier)
    return finding.model_copy(update={"deterministic_candidate_ids": identifiers})
