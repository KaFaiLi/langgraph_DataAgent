"""Deterministic cross-specialist candidate analysis for the lead-review skill."""

from __future__ import annotations

import re
from datetime import date, timedelta
from itertools import combinations

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.reports import (
    ContradictionCandidate,
    CrossSourceCluster,
    CrossSpecialistAnalysis,
    SpecialistReport,
)

MAX_EVENT_SPAN_DAYS = 7
MIN_SHARED_ENTITY_TOKENS = 2

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_IDENTIFIER_RE = re.compile(r"\b(?:[A-Z][A-Z0-9]*_[A-Z0-9_]+|[A-Z]{2,})\b")
_PROPER_NAME_RE = re.compile(r"\b[A-Z][a-z][A-Za-z0-9-]{2,}\b")

_DOMAIN_ENTITY_TERMS = frozenset(
    {
        "adjustment",
        "adjustments",
        "approval",
        "attribution",
        "breach",
        "breaches",
        "carry",
        "cds",
        "commentary",
        "credit",
        "equity",
        "excess",
        "excesses",
        "exposure",
        "fx",
        "mapping",
        "options",
        "pnl",
        "rates",
        "stress",
        "svar",
        "threshold",
        "var",
        "workflow",
    }
)

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "was",
        "were",
        "are",
        "has",
        "had",
        "have",
        "from",
        "this",
        "that",
        "these",
        "those",
        "over",
        "under",
        "into",
        "per",
        "not",
        "but",
        "day",
        "days",
        "period",
        "during",
        "between",
        "above",
        "below",
        "within",
        "limit",
        "limits",
        "risk",
        "finding",
        "material",
        "review",
        "source",
        "evidence",
        "daily",
        "total",
        "value",
        "exceeded",
        "shows",
        "reported",
        "across",
        "observed",
        "multiple",
        "recurring",
        "analysis",
        "deterministic",
        "candidate",
        "observation",
        "population",
        "record",
        "records",
        "row",
        "rows",
        "table",
        "output",
        "result",
        "results",
        "confirmed",
        "documented",
        "unresolved",
        "validated",
        "comparison",
        "series",
    }
)

_UP_WORDS = frozenset(
    {
        "increase",
        "increased",
        "rising",
        "rise",
        "rose",
        "higher",
        "up",
        "gain",
        "positive",
        "profit",
        "profitable",
        "exceeded",
        "breach",
        "breached",
    }
)
_DOWN_WORDS = frozenset(
    {
        "decrease",
        "decreased",
        "falling",
        "fell",
        "fall",
        "lower",
        "down",
        "loss",
        "negative",
        "declined",
        "decline",
        "within",
        "compliant",
        "stable",
        "flat",
    }
)


def _tokenize(text: str) -> set[str]:
    identifiers = {token.lower() for token in _IDENTIFIER_RE.findall(text)}
    proper_names = {
        token.lower() for token in _PROPER_NAME_RE.findall(text) if token.lower() not in _STOPWORDS
    }
    domain_terms = set(_TOKEN_RE.findall(text.lower())) & _DOMAIN_ENTITY_TERMS
    return (identifiers | proper_names | domain_terms) - _STOPWORDS


def _finding_dates(finding: Finding) -> list[date]:
    if finding.period is None:
        return []
    start, end = finding.period.start, finding.period.end
    if (end - start).days > MAX_EVENT_SPAN_DAYS:
        return []
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _shared_relationship(left: Finding, right: Finding) -> tuple[set[str], set[date], bool, bool]:
    common = _tokenize(f"{left.title} {left.claim}") & _tokenize(f"{right.title} {right.claim}")
    shared_dates = set(_finding_dates(left)) & set(_finding_dates(right))
    specific_common = common - _DOMAIN_ENTITY_TERMS
    same_event = bool(shared_dates and common)
    same_entity = len(common) >= MIN_SHARED_ENTITY_TOKENS and bool(specific_common)
    return common, shared_dates, same_event, same_entity


def _build_clusters(findings: list[Finding], owners: dict[str, str]) -> list[CrossSourceCluster]:
    """Return precise cross-specialist relationship pairs.

    Connected-component unioning is deliberately avoided: a weak bridge through one
    finding must not turn several distinct issues into one apparent cross-source event.
    """
    if not findings:
        return []

    clusters: list[CrossSourceCluster] = []
    ordered = sorted(findings, key=lambda finding: finding.finding_id)
    for left, right in combinations(ordered, 2):
        if owners.get(left.finding_id) == owners.get(right.finding_id):
            continue
        common, shared_dates, same_event, same_entity = _shared_relationship(left, right)
        if not same_event and not same_entity:
            continue

        relationship_types: list[str] = []
        if same_event:
            relationship_types.append("same_date")
        if common:
            relationship_types.append("shared_entity")
        if left.category == right.category:
            relationship_types.append("same_category")

        evidence: list[EvidenceReference] = []
        seen_locators: set[str] = set()
        for reference in [*left.evidence, *right.evidence]:
            if reference.locator in seen_locators:
                continue
            seen_locators.add(reference.locator)
            # A cluster points back to specialist evidence by locator. Quotes are
            # omitted because specialist summaries may be derived rather than verbatim.
            evidence.append(EvidenceReference(locator=reference.locator))

        clusters.append(
            CrossSourceCluster(
                cluster_id=f"CL-{len(clusters) + 1:03d}",
                findings=[left.finding_id, right.finding_id],
                relationship_types=relationship_types,
                start_date=min(shared_dates) if shared_dates else None,
                end_date=max(shared_dates) if shared_dates else None,
                shared_entities=sorted(common),
                supporting_evidence=evidence[:20],
            )
        )
    return clusters


def _polarity(text: str) -> int:
    tokens = set(_TOKEN_RE.findall(text.lower()))
    upward = len(tokens & _UP_WORDS)
    downward = len(tokens & _DOWN_WORDS)
    if upward > downward:
        return 1
    if downward > upward:
        return -1
    return 0


def _find_contradictions(
    findings: list[Finding], owners: dict[str, str]
) -> list[ContradictionCandidate]:
    contradictions: list[ContradictionCandidate] = []
    for left, right in combinations(findings, 2):
        if owners.get(left.finding_id) == owners.get(right.finding_id):
            continue
        if left.period is None or right.period is None or not left.period.overlaps(right.period):
            continue
        common, _shared_dates, same_event, same_entity = _shared_relationship(left, right)
        if not same_event and not same_entity:
            continue
        left_polarity = _polarity(f"{left.title} {left.claim}")
        right_polarity = _polarity(f"{right.title} {right.claim}")
        if left_polarity == 0 or right_polarity == 0 or left_polarity == right_polarity:
            continue
        contradictions.append(
            ContradictionCandidate(
                contradiction_id=f"CTR-{len(contradictions) + 1:03d}",
                finding_a=left.finding_id,
                finding_b=right.finding_id,
                kind="opposing_polarity",
                note=(
                    f"Shared entities {sorted(common)}; {left.finding_id} reads "
                    f"{'up' if left_polarity > 0 else 'down'} while {right.finding_id} "
                    f"reads {'up' if right_polarity > 0 else 'down'} over overlapping periods."
                ),
            )
        )
    return contradictions


def run_analysis(reports: list[SpecialistReport]) -> CrossSpecialistAnalysis:
    """Return deterministic relationship candidates from completed specialist reports."""
    findings: list[Finding] = []
    owners: dict[str, str] = {}
    for report in reports:
        for finding in [*report.verified_findings(), *report.unresolved_findings()]:
            findings.append(finding)
            owners[finding.finding_id] = report.domain.value
    return CrossSpecialistAnalysis(
        clusters=_build_clusters(findings, owners),
        contradiction_candidates=_find_contradictions(findings, owners),
    )
