"""Deterministic omission auditing for skill-produced candidates."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from data_agent.review.domain.finding import Finding
from data_agent.review.domain.severity import SEVERITY_ORDER, Severity
from data_agent.review.domain.verification import (
    CandidateDisposition,
    CandidateDispositionRecord,
    OmissionAuditResult,
    OmissionCandidate,
)
from data_agent.review.verification.candidates import (
    assign_candidate_ids,
    candidate_locators,
    covered_candidate_ids,
    stable_candidate_id,
)


def _analysis_parts(analysis: object) -> tuple[str, list[Mapping[str, Any]]]:
    if isinstance(analysis, Mapping):
        name = str(analysis.get("name") or analysis.get("analysis_name") or "analysis")
        candidates = analysis.get("flag_candidates", analysis.get("candidates", []))
    else:
        name = str(
            getattr(analysis, "name", None)
            or getattr(analysis, "analysis_name", None)
            or "analysis"
        )
        candidates = getattr(analysis, "flag_candidates", getattr(analysis, "candidates", []))
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes, bytearray)):
        return name, []
    return name, [candidate for candidate in candidates if isinstance(candidate, Mapping)]


def _candidate_value(candidate: object) -> dict[str, Any]:
    if isinstance(candidate, Mapping):
        return dict(candidate)
    if isinstance(candidate, OmissionCandidate):
        return candidate.model_dump(mode="json")
    model_dump = getattr(candidate, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def candidate_is_material(
    candidate: Mapping[str, Any] | OmissionCandidate,
    *,
    severity_floor: Severity | str = Severity.MEDIUM,
) -> bool:
    """Apply generic materiality floors while preserving skill-owned flags."""

    data = _candidate_value(candidate)
    if data.get("material") is True or data.get("deterministic_material") is True:
        return True
    materiality = str(
        data.get("materiality") or data.get("materiality_hint") or data.get("impact") or ""
    ).lower()
    if materiality in {"material", "high", "critical", "medium"}:
        return True
    severity_value = data.get("severity")
    try:
        severity = (
            severity_value
            if isinstance(severity_value, Severity)
            else Severity(str(severity_value).lower())
        )
        floor = (
            severity_floor
            if isinstance(severity_floor, Severity)
            else Severity(str(severity_floor).lower())
        )
    except (ValueError, TypeError):
        return False
    return SEVERITY_ORDER[severity] >= SEVERITY_ORDER[floor]


def _candidate_reason(data: Mapping[str, Any], kind: str | None) -> str:
    explicit = data.get("reason") or data.get("materiality_reason")
    if explicit:
        return str(explicit)
    if kind:
        return f"deterministic candidate of kind {kind!r}"
    return "deterministic candidate was not linked to an analyst finding"


def candidate_to_omission(
    analysis_name: str,
    candidate: Mapping[str, Any] | OmissionCandidate,
) -> OmissionCandidate:
    """Convert a deterministic flag into the persisted omission contract."""

    if isinstance(candidate, OmissionCandidate):
        return candidate
    data = _candidate_value(candidate)
    identifier = str(
        data.get("candidate_id")
        or data.get("deterministic_candidate_id")
        or stable_candidate_id(analysis_name, data)
    )
    kind = data.get("kind") or data.get("type")
    references = []
    for locator in sorted(candidate_locators(data)):
        try:
            from data_agent.review.domain.evidence import EvidenceReference

            references.append(EvidenceReference(locator=locator))
        except ValueError:
            # Invalid locators remain discoverable through deterministic details;
            # the evidence gate owns their repair/unresolved classification.
            continue
    hint = data.get("materiality_hint") or data.get("materiality") or data.get("severity")
    return OmissionCandidate(
        candidate_id=identifier,
        analysis_name=analysis_name,
        reason=_candidate_reason(data, str(kind) if kind else None),
        evidence=references,
        materiality_hint=str(hint) if hint is not None else None,
        kind=str(kind) if kind is not None else None,
        details=data,
    )


def _normalize_dispositions(
    dispositions: Mapping[str, object] | Sequence[object] | None,
) -> list[CandidateDispositionRecord]:
    if dispositions is None:
        return []
    records: list[CandidateDispositionRecord] = []
    if isinstance(dispositions, Mapping):
        values = dispositions.items()
    else:
        values = ((None, value) for value in dispositions)
    for identifier, value in values:
        if isinstance(value, CandidateDispositionRecord):
            records.append(value)
            continue
        if isinstance(value, Mapping):
            data = dict(value)
            candidate_id = data.get("candidate_id") or identifier
            disposition = data.get("disposition") or data.get("status")
            if candidate_id is None or disposition is None:
                continue
            data["candidate_id"] = candidate_id
            data["disposition"] = disposition
            records.append(CandidateDispositionRecord(**data))
            continue
        if identifier is None:
            identifier = getattr(value, "candidate_id", None)
        disposition = getattr(value, "disposition", value)
        if identifier is None or disposition is None:
            continue
        try:
            records.append(
                CandidateDispositionRecord(
                    candidate_id=str(identifier),
                    disposition=CandidateDisposition(str(disposition)),
                )
            )
        except ValueError:
            continue
    by_id: dict[str, CandidateDispositionRecord] = {}
    for record in records:
        by_id[record.candidate_id] = record
    return list(by_id.values())


def audit_omissions(
    analyses: Sequence[object],
    findings: Sequence[Finding],
    *,
    rejected_findings: Sequence[Finding] | None = None,
    unresolved_findings: Sequence[Finding] | None = None,
    candidate_dispositions: Mapping[str, object] | Sequence[object] | None = None,
    dispositions: Mapping[str, object] | Sequence[object] | None = None,
    severity_floor: Severity | str = Severity.MEDIUM,
    materiality_predicate: Callable[[Mapping[str, Any]], bool] | None = None,
    rescue_used: bool = False,
) -> OmissionAuditResult:
    """Audit deterministic candidate coverage and identify material omissions.

    Findings supplied in any status count as consideration.  A candidate with
    no explicit material marker is retained as an uncovered ambiguous lead but
    does not force rescue; skill-owned material flags and severity at or above
    ``severity_floor`` do.
    """

    all_findings = list(findings)
    all_findings.extend(rejected_findings or ())
    all_findings.extend(unresolved_findings or ())
    disposition_input = (
        candidate_dispositions if candidate_dispositions is not None else dispositions
    )
    normalized_dispositions = _normalize_dispositions(disposition_input)
    # A model cannot cover a deterministic signal merely by naming a
    # disposition.  Non-finding dispositions need a concrete explanation and
    # source support; ``FINDING`` coverage is established only by an actual
    # linked finding below.
    eligible_dispositions = [
        record
        for record in normalized_dispositions
        if record.disposition is not CandidateDisposition.FINDING
        and bool(record.reason.strip())
        and bool(record.evidence)
    ]

    normalized_by_analysis: list[tuple[str, list[dict[str, Any]]]] = []
    omission_candidates: list[OmissionCandidate] = []
    for analysis in analyses:
        analysis_name, raw_candidates = _analysis_parts(analysis)
        assigned = assign_candidate_ids(analysis_name, raw_candidates)
        normalized_by_analysis.append((analysis_name, assigned))
        omission_candidates.extend(
            candidate_to_omission(analysis_name, candidate) for candidate in assigned
        )

    # A repeated deterministic row should be one candidate, not several
    # omission disclosures.  Stable identity makes this de-duplication safe.
    unique_candidates: dict[str, OmissionCandidate] = {}
    for candidate in omission_candidates:
        unique_candidates.setdefault(candidate.candidate_id, candidate)
    omission_candidates = list(unique_candidates.values())

    covered: list[str] = []
    for analysis_name, candidates in normalized_by_analysis:
        covered.extend(
            covered_candidate_ids(
                candidates,
                all_findings,
                analysis_name=analysis_name,
                dispositions={record.candidate_id: record for record in eligible_dispositions},
            )
        )
    covered_set = set(covered)
    uncovered = [
        candidate for candidate in omission_candidates if candidate.candidate_id not in covered_set
    ]

    material_ids: list[str] = []
    for candidate in uncovered:
        data = candidate.details
        material = (
            materiality_predicate(data)
            if materiality_predicate
            else candidate_is_material(
                data,
                severity_floor=severity_floor,
            )
        )
        if material:
            material_ids.append(candidate.candidate_id)

    material_ids = list(dict.fromkeys(material_ids))
    disclosures = []
    if rescue_used and material_ids:
        disclosures = [
            f"deterministic candidate {candidate_id} remained materially omitted after rescue"
            for candidate_id in material_ids
        ]
    return OmissionAuditResult(
        covered_candidate_ids=list(dict.fromkeys(covered)),
        uncovered_candidates=uncovered,
        material_candidate_ids=material_ids,
        candidate_dispositions=normalized_dispositions,
        material_omission_exists=bool(material_ids),
        rescue_required=bool(material_ids) and not rescue_used,
        rescue_used=rescue_used,
        unresolved_disclosures=disclosures,
    )
