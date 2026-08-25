"""Deterministic policy for normalizing and persisting specialist findings."""

from __future__ import annotations

import re
from datetime import date

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.severity import SEVERITY_ORDER, Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.ingestion.evidence_validator import (
    EvidenceDisposition,
    EvidenceValidationResult,
    EvidenceValidator,
)
from data_agent.review.orchestration.specialist.schemas import MAX_ANALYST_FINDINGS
from data_agent.review.verification.candidates import (
    assign_candidate_ids,
    link_finding_to_candidates,
)

MAX_PERSISTED_FINDING_EVIDENCE = 8


def _source_locators(value: object) -> set[str]:
    if isinstance(value, str):
        return {value} if value.startswith("source://") else set()
    if isinstance(value, list):
        return {locator for item in value for locator in _source_locators(item)}
    if isinstance(value, dict):
        return {locator for item in value.values() for locator in _source_locators(item)}
    return set()


def _repair(finding: Finding) -> Finding:
    if finding.period is not None and finding.period.start > finding.period.end:
        finding.period = DateRange(start=finding.period.end, end=finding.period.start)
    finding.confidence = min(1.0, max(0.0, finding.confidence))
    return finding


def _infer_period(finding: Finding, analyses: list[dict[str, object]]) -> Finding:
    if finding.period is not None:
        return finding
    cited = {reference.locator for reference in finding.evidence}
    dates: list[date] = []
    for analysis in analyses:
        candidates = analysis.get("flag_candidates", [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict) or not cited.intersection(
                _source_locators(candidate)
            ):
                continue
            for key in (
                "event_date",
                "value_date",
                "effective_date",
                "date",
                "first_date",
                "last_date",
            ):
                value = candidate.get(key)
                if isinstance(value, str):
                    try:
                        dates.append(date.fromisoformat(value[:10]))
                    except ValueError:
                        pass
    if not dates:
        return finding
    return finding.model_copy(update={"period": DateRange(start=min(dates), end=max(dates))})


def _matches_finding(candidate: dict[object, object], finding: Finding) -> bool:
    finding_locators = {reference.locator for reference in finding.evidence}
    if not finding_locators.intersection(_source_locators(candidate)):
        return False
    terms = candidate.get("severity_match_terms", [])
    if not isinstance(terms, list) or not terms:
        return True
    text = " ".join(
        [finding.title, finding.category, finding.claim, *finding.analysis_performed]
    ).lower()
    matched = sum(1 for term in terms if isinstance(term, str) and term.lower() in text)
    return matched >= min(2, len(terms))


def _add_candidate_evidence(finding: Finding, analyses: list[dict[str, object]]) -> Finding:
    evidence = list(finding.evidence)
    seen = {reference.locator for reference in evidence}
    for analysis in analyses:
        candidates = analysis.get("flag_candidates", [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if (
                not isinstance(candidate, dict)
                or candidate.get("measured_observation") is not True
                or not _matches_finding(candidate, finding)
            ):
                continue
            for locator in sorted(_source_locators(candidate)):
                if locator not in seen:
                    seen.add(locator)
                    evidence.append(EvidenceReference(locator=locator))
                    if len(evidence) >= MAX_PERSISTED_FINDING_EVIDENCE:
                        return finding.model_copy(update={"evidence": evidence})
    return finding.model_copy(update={"evidence": evidence})


_CONTEXT_MATCH_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "for",
        "from",
        "reported",
        "review",
        "source",
        "that",
        "the",
        "this",
        "with",
    }
)


def _add_context_evidence(finding: Finding, desk_context: dict[str, object]) -> Finding:
    def terms(value: object) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", str(value).lower())
            if len(token) >= 3 and token not in _CONTEXT_MATCH_STOPWORDS
        }

    finding_terms = terms(
        " ".join(
            [
                finding.title,
                finding.category,
                finding.claim,
                *finding.analysis_performed,
            ]
        )
    )
    evidence = list(finding.evidence)
    seen = {reference.locator for reference in evidence}
    facts = desk_context.get("source_backed_facts", [])
    if not isinstance(facts, list):
        return finding
    for fact in facts:
        if not isinstance(fact, dict) or len(finding_terms & terms(fact.get("statement", ""))) < 2:
            continue
        references = fact.get("evidence", [])
        if not isinstance(references, list):
            continue
        for raw_reference in references:
            try:
                reference = EvidenceReference.model_validate(raw_reference)
            except ValueError:
                continue
            if reference.locator not in seen:
                seen.add(reference.locator)
                evidence.append(reference)
                if len(evidence) >= MAX_PERSISTED_FINDING_EVIDENCE:
                    return finding.model_copy(update={"evidence": evidence})
    return finding.model_copy(update={"evidence": evidence})


def _apply_severity_floor(finding: Finding, analyses: list[dict[str, object]]) -> Finding:
    floors: list[Severity] = []
    measured_observation = False
    for analysis in analyses:
        candidates = analysis.get("flag_candidates", [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict) or not _matches_finding(candidate, finding):
                continue
            try:
                floors.append(Severity(str(candidate.get("severity_floor"))))
            except ValueError:
                continue
            if candidate.get("measured_observation") is True:
                measured_observation = True
    updates: dict[str, object] = {}
    if floors:
        floor = max(floors, key=lambda severity: SEVERITY_ORDER[severity])
        if SEVERITY_ORDER[finding.severity] < SEVERITY_ORDER[floor]:
            updates["severity"] = floor
    if measured_observation:
        updates["is_observation"] = True
    return finding.model_copy(update=updates) if updates else finding


def _namespace(findings: list[Finding], report_id: str) -> list[Finding]:
    prefix = f"{report_id}-"
    for finding in findings:
        if not finding.finding_id.startswith(prefix):
            finding.finding_id = prefix + finding.finding_id
    return findings


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: dict[str, Finding] = {}
    order: list[str] = []
    for finding in findings:
        if finding.finding_id not in seen:
            order.append(finding.finding_id)
        seen[finding.finding_id] = finding
    return [seen[finding_id] for finding_id in order]


def normalize_findings(
    findings: list[Finding],
    *,
    analyses: list[dict[str, object]],
    desk_context: dict[str, object],
    report_id: str,
    previous: list[Finding] | None = None,
) -> tuple[list[Finding], set[str]]:
    """Apply all deterministic finding policy through one orchestration seam."""
    normalized_analyses: list[dict[str, object]] = []
    for raw_analysis in analyses:
        analysis = dict(raw_analysis)
        candidates = analysis.get("flag_candidates", [])
        if isinstance(candidates, list):
            analysis["flag_candidates"] = assign_candidate_ids(
                str(analysis.get("name") or "analysis"),
                [candidate for candidate in candidates if isinstance(candidate, dict)],
            )
        normalized_analyses.append(analysis)
    analyses = normalized_analyses
    normalized = [
        _apply_severity_floor(
            _add_context_evidence(
                _infer_period(_add_candidate_evidence(_repair(finding), analyses), analyses),
                desk_context,
            ),
            analyses,
        )
        for finding in findings
    ]
    normalized = _dedupe(_namespace(normalized, report_id))[:MAX_ANALYST_FINDINGS]
    all_candidates = [
        candidate
        for analysis in analyses
        for candidate in analysis.get("flag_candidates", [])
        if isinstance(candidate, dict)
    ]
    analysis_names = {str(analysis.get("name") or "analysis") for analysis in analyses}
    analysis_name = next(iter(analysis_names), "analysis") if len(analysis_names) == 1 else None
    normalized = [
        link_finding_to_candidates(finding, all_candidates, analysis_name=analysis_name)
        for finding in normalized
    ]
    revised_ids = {finding.finding_id for finding in normalized}
    if previous is None:
        return normalized, revised_ids
    revised_by_id = {finding.finding_id: finding for finding in normalized}
    merged = [revised_by_id.get(finding.finding_id, finding) for finding in previous]
    previous_ids = {finding.finding_id for finding in previous}
    merged.extend(finding for finding in normalized if finding.finding_id not in previous_ids)
    return merged[:MAX_ANALYST_FINDINGS], revised_ids


def sanitize_finding_references(
    finding: Finding, validator: EvidenceValidator
) -> tuple[Finding, list[EvidenceValidationResult]]:
    """Remove non-reopenable citations while preserving validation failures."""
    updates: dict[str, object] = {}
    failures: list[EvidenceValidationResult] = []
    for field_name, references in (
        ("evidence", finding.evidence),
        ("counter_evidence", finding.counter_evidence),
    ):
        validation = validator.validate_references(references)
        fatal = [
            failure
            for failure in validation.failures
            if failure.disposition is EvidenceDisposition.FATAL
        ]
        if fatal:
            details = "; ".join(f"{failure.locator}: {failure.reason}" for failure in fatal)
            raise RuntimeError(f"fatal evidence integrity failure: {details}")
        valid_locators = {result.locator for result in validation.results if result.valid}
        updates[field_name] = [
            reference for reference in references if reference.locator in valid_locators
        ]
        failures.extend(validation.failures)
    return finding.model_copy(update=updates), failures
