"""Deterministic cross-specialist candidate analysis for the lead-review skill."""

from __future__ import annotations

import re
from collections import Counter
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


class _UnionFind:
    def __init__(self, ids: list[str]) -> None:
        self.parent = {item: item for item in ids}

    def find(self, item: str) -> str:
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _tokenize(text: str) -> set[str]:
    identifiers = {token.lower() for token in _IDENTIFIER_RE.findall(text)}
    proper_names = {
        token.lower()
        for token in _PROPER_NAME_RE.findall(text)
        if token.lower() not in _STOPWORDS
    }
    domain_terms = set(_TOKEN_RE.findall(text.lower())) & _DOMAIN_ENTITY_TERMS
    return (identifiers | proper_names | domain_terms) - _STOPWORDS


def _entity_tokens(findings: list[Finding], min_count: int = 2) -> dict[str, set[str]]:
    per_finding = {
        finding.finding_id: _tokenize(f"{finding.title} {finding.claim}")
        for finding in findings
    }
    counts: Counter[str] = Counter()
    for tokens in per_finding.values():
        counts.update(tokens)

    max_document_frequency = max(2, int(len(findings) * 0.20))
    return {
        finding_id: {
            token
            for token in tokens
            if counts[token] >= min_count
            and (len(findings) < 8 or counts[token] <= max_document_frequency)
        }
        for finding_id, tokens in per_finding.items()
    }


def _finding_dates(finding: Finding) -> list[date]:
    if finding.period is None:
        return []
    start, end = finding.period.start, finding.period.end
    if (end - start).days > 366:
        return [start]
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _date_buckets(findings: list[Finding]) -> dict[date, list[str]]:
    buckets: dict[date, list[str]] = {}
    for finding in findings:
        for day in _finding_dates(finding):
            buckets.setdefault(day, []).append(finding.finding_id)
    return buckets


def _relationship_types(
    findings: list[Finding], dates: set[date], tokens: set[str]
) -> list[str]:
    kinds: list[str] = []
    if dates:
        kinds.append("same_date")
    if tokens:
        kinds.append("shared_entity")
    if len({finding.category for finding in findings}) == 1:
        kinds.append("same_category")
    return kinds


def _build_clusters(findings: list[Finding]) -> list[CrossSourceCluster]:
    if not findings:
        return []

    union_find = _UnionFind([finding.finding_id for finding in findings])
    event_findings = [
        finding
        for finding in findings
        if finding.period is not None
        and (finding.period.end - finding.period.start).days <= MAX_EVENT_SPAN_DAYS
    ]
    shared_tokens = _entity_tokens(findings)

    for finding_ids in _date_buckets(event_findings).values():
        if len(finding_ids) >= 2:
            for other_id in finding_ids[1:]:
                union_find.union(finding_ids[0], other_id)

    for left, right in combinations(findings, 2):
        common = shared_tokens.get(left.finding_id, set()) & shared_tokens.get(
            right.finding_id, set()
        )
        if len(common) >= MIN_SHARED_ENTITY_TOKENS:
            union_find.union(left.finding_id, right.finding_id)

    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(union_find.find(finding.finding_id), []).append(finding)

    clusters: list[CrossSourceCluster] = []
    groups = sorted(grouped.values(), key=lambda group: sorted(f.finding_id for f in group))
    for index, members in enumerate(groups, start=1):
        dates = {day for finding in members for day in _finding_dates(finding)}
        tokens = set().union(
            *(shared_tokens.get(finding.finding_id, set()) for finding in members)
        )
        evidence: list[EvidenceReference] = [
            reference for finding in members for reference in finding.evidence
        ]
        clusters.append(
            CrossSourceCluster(
                cluster_id=f"CL-{index:03d}",
                findings=sorted(finding.finding_id for finding in members),
                relationship_types=_relationship_types(members, dates, tokens),
                start_date=min(dates) if dates else None,
                end_date=max(dates) if dates else None,
                shared_entities=sorted(tokens),
                supporting_evidence=evidence[:20],
            )
        )
    return clusters


def _polarity(text: str) -> int:
    tokens = set(text.lower().split())
    upward = len(tokens & _UP_WORDS)
    downward = len(tokens & _DOWN_WORDS)
    if upward > downward:
        return 1
    if downward > upward:
        return -1
    return 0


def _find_contradictions(findings: list[Finding]) -> list[ContradictionCandidate]:
    shared_tokens = _entity_tokens(findings)
    contradictions: list[ContradictionCandidate] = []
    for left, right in combinations(findings, 2):
        if (
            left.period is None
            or right.period is None
            or not left.period.overlaps(right.period)
        ):
            continue
        common = shared_tokens.get(left.finding_id, set()) & shared_tokens.get(
            right.finding_id, set()
        )
        if not common:
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
    findings = [
        finding
        for report in reports
        for finding in [*report.verified_findings(), *report.unresolved_findings()]
    ]
    return CrossSpecialistAnalysis(
        clusters=_build_clusters(findings),
        contradiction_candidates=_find_contradictions(findings),
    )
