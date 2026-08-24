"""Deterministic screens for finalized quarterly risk-commentary extracts."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference, Locator, format_locator
from data_agent.review.domain.overview import (
    DataOverview,
    OverviewMetric,
    OverviewStatus,
    TableVisual,
)
from data_agent.tools.review_context import ToolContext, source_file

MAX_FLAGS: Final = 50
REPEATED_PHRASE_MIN: Final = 3
_SOURCE_RECORD = re.compile(r"^\s*-\s*(?:\[C\d+\]|Source record:)", re.IGNORECASE)
_EVENT_LINE = re.compile(
    r"^\s*-\s*Event date (\d{4}-\d{2}-\d{2}); desk ([^;]+); "
    r"perimeter ([^;]+); metric ([^.]+)\.",
    re.IGNORECASE,
)
_REVIEW_NOTE = re.compile(r"^\s*-\s*Review note:\s*(.+)$", re.IGNORECASE)
_MANAGERIAL_VALIDATION = re.compile(r"^\s*-\s*Managerial validation:\s*(.+)$", re.IGNORECASE)
_EVIDENCE_ID = re.compile(r"Evidence ID:\s*([^\s\"]+)", re.IGNORECASE)
_VALIDATION = re.compile(
    r"Managerial Validation(?: Comment)?:\s*(No data|pending|blank|missing)",
    re.IGNORECASE,
)
_TRIGGER_TERMS = ("threshold exceed", "limit breach", "stress scenario triggered")
_REASSURANCE_TERMS = ("no material change", "within tolerance", "no breach")
_EXPLANATION_PHRASES = (
    "booking system delay caused late capture",
    "limit breach driven by increased volatility on eqd book",
    "limit breach driven by increased volatility on fic book",
    "no material change within tolerance",
    "pnl spike linked to client hedging activity",
    "stress scenario triggered on rates curve",
)
_MATERIAL_REASSURANCE_TERMS = (
    "well diversified",
    "within appetite",
    "all validation workflows were clean",
    "flat after ordinary processing",
    "routine carry and immaterial",
    "isolated and promptly remediated",
)


@dataclass(frozen=True)
class _Record:
    path: str
    line: int
    text: str
    normalized: str
    evidence_id: str
    event_date: str
    desk: str
    perimeter: str
    metric: str
    claim: str
    validation: str

    @property
    def locator(self) -> str:
        return format_locator(Locator(path=self.path, lines=(self.line, self.line)))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def _read_extract(ctx: ToolContext, path: str) -> tuple[list[str], list[_Record]]:
    full = source_file(ctx, path)
    if full.suffix.lower() not in {".md", ".markdown", ".txt"}:
        return [], []
    lines = full.read_text(encoding="utf-8").splitlines()
    records: list[_Record] = []
    event_date = ""
    desk = ""
    perimeter = ""
    metric = ""
    claim = ""
    validation = ""
    for line_number, text in enumerate(lines, start=1):
        event = _EVENT_LINE.match(text)
        if event is not None:
            event_date, desk, perimeter, metric = (value.strip() for value in event.groups())
            claim = ""
            validation = ""
            continue
        note = _REVIEW_NOTE.match(text)
        if note is not None:
            claim = note.group(1).strip()
            continue
        managerial = _MANAGERIAL_VALIDATION.match(text)
        if managerial is not None:
            validation = managerial.group(1).strip()
            continue
        if _SOURCE_RECORD.match(text) is None:
            continue
        evidence = _EVIDENCE_ID.search(text)
        records.append(
            _Record(
                path=path,
                line=line_number,
                text=text,
                normalized=_normalize(text),
                evidence_id=evidence.group(1) if evidence else f"{path}:{line_number}",
                event_date=event_date,
                desk=desk,
                perimeter=perimeter,
                metric=metric,
                claim=claim,
                validation=validation,
            )
        )
    return lines, records


def _population_profile(
    extracts: list[tuple[str, list[str], list[_Record]]],
) -> AnalysisResult:
    tables: list[dict[str, object]] = []
    evidence: list[EvidenceReference] = []
    for path, lines, records in extracts:
        headings = [line.strip() for line in lines if line.lstrip().startswith("#")]
        validation_gaps = len(
            {record.evidence_id for record in records if _VALIDATION.search(record.text)}
        )
        tables.append(
            {
                "path": path,
                "lines": len(lines),
                "headings": len(headings),
                "quoted_source_records": len(records),
                "unique_evidence_ids": len({record.evidence_id for record in records}),
                "validation_gaps": validation_gaps,
                "first_heading": headings[0] if headings else None,
            }
        )
        evidence.append(
            EvidenceReference(locator=format_locator(Locator(path=path, lines=(1, len(lines)))))
        )
    total_records = sum(int(table["quoted_source_records"]) for table in tables)
    total_unique = sum(int(table["unique_evidence_ids"]) for table in tables)
    total_gaps = sum(int(table["validation_gaps"]) for table in tables)
    overview = (
        DataOverview(
            overview_id="risk-commentary.extract-coverage",
            domain=SpecialistDomain.RISK_COMMENTARY,
            source_family="risk_commentary",
            title="Risk commentary extract and evidence coverage",
            summary=(
                "Final commentary extracts are profiled by quoted-record and evidence-ID "
                "coverage before interpreting validation gaps or repeated explanations."
            ),
            status=(OverviewStatus.AVAILABLE if total_records else OverviewStatus.PARTIAL),
            primary_for_deck=True,
            metrics=[
                OverviewMetric(
                    label="Extracts",
                    value=str(len(tables)),
                    unit="count",
                    basis="reviewed final commentary extracts",
                ),
                OverviewMetric(
                    label="Quoted records",
                    value=str(total_records),
                    unit="occurrences",
                    basis="records marked with a commentary source tag",
                ),
                OverviewMetric(
                    label="Unique evidence IDs",
                    value=str(total_unique),
                    unit="count",
                    basis="unique IDs within each extract",
                ),
                OverviewMetric(
                    label="Validation gaps",
                    value=str(total_gaps),
                    unit="unique records",
                    basis="No data, pending, blank, or missing managerial validation",
                ),
            ],
            visual=TableVisual(
                columns=[
                    "Extract",
                    "Lines",
                    "Quoted records",
                    "Unique evidence IDs",
                    "Validation gaps",
                ],
                rows=[
                    [
                        str(table["path"]),
                        str(table["lines"]),
                        str(table["quoted_source_records"]),
                        str(table["unique_evidence_ids"]),
                        str(table["validation_gaps"]),
                    ]
                    for table in tables
                ],
            ),
            evidence=evidence,
            limitations=(
                [
                    (
                        "The supplied extracts contain no tagged quoted records; theme "
                        "and validation coverage is partial."
                    )
                ]
                if not total_records
                else [
                    (
                        "Coverage counts the finalized extracts only and does not imply "
                        "the underlying commentary is complete."
                    )
                ]
            ),
        )
        if tables
        else DataOverview(
            overview_id="risk-commentary.extract-coverage",
            domain=SpecialistDomain.RISK_COMMENTARY,
            source_family="risk_commentary",
            title="Risk commentary extract and evidence coverage",
            summary="No compatible finalized commentary extract was available for profiling.",
            status=OverviewStatus.UNAVAILABLE,
            primary_for_deck=True,
            limitations=[
                "Overview unavailable because no readable Markdown or text extract was supplied."
            ],
        )
    )
    return AnalysisResult(
        name="commentary_extract_population",
        summary=(
            f"Profiled {len(tables)} final commentary extract(s) containing "
            f"{total_records} quoted source-record occurrence(s)."
        ),
        tables=tables,
        overviews=[overview],
    )


def _validation_gaps(records: list[_Record]) -> AnalysisResult:
    unique: dict[str, _Record] = {}
    for record in records:
        if _VALIDATION.search(record.text):
            unique.setdefault(record.evidence_id, record)
    flags = [
        {
            "kind": "commentary_validation_gap",
            "path": record.path,
            "line": record.line,
            "evidence_id": record.evidence_id,
            "validation_state": _VALIDATION.search(record.text).group(1),  # type: ignore[union-attr]
            "locator": record.locator,
            "text": record.text[:500],
        }
        for record in unique.values()
    ][:MAX_FLAGS]
    by_path = Counter(record.path for record in unique.values())
    return AnalysisResult(
        name="commentary_validation_gaps",
        summary=(
            f"Found {len(unique)} unique quoted record(s) with No data, pending, blank, "
            "or missing managerial validation; these are evidence-gap candidates only."
        ),
        tables=[{"path": path, "unique_records": count} for path, count in sorted(by_path.items())],
        flag_candidates=flags,
    )


def _internal_consistency(records: list[_Record]) -> AnalysisResult:
    unique: dict[str, _Record] = {}
    for record in records:
        has_trigger = any(term in record.normalized for term in _TRIGGER_TERMS)
        has_reassurance = any(term in record.normalized for term in _REASSURANCE_TERMS)
        if has_trigger and has_reassurance:
            unique.setdefault(record.evidence_id, record)
    flags = [
        {
            "kind": "commentary_internal_consistency_candidate",
            "path": record.path,
            "line": record.line,
            "evidence_id": record.evidence_id,
            "locator": record.locator,
            "text": record.text[:500],
            "detail": (
                "one quoted record contains both movement/breach language and reassuring "
                "language; field and scope differences must be checked"
            ),
        }
        for record in unique.values()
    ][:MAX_FLAGS]
    return AnalysisResult(
        name="commentary_internal_consistency",
        summary=(
            f"Screened quoted records for trigger/reassurance combinations and retained "
            f"{len(unique)} unique candidate(s) for scope-aware review."
        ),
        tables=[{"unique_candidates": len(unique), "screen": "trigger + reassurance"}],
        flag_candidates=flags,
    )


def _repeated_explanations(records: list[_Record]) -> AnalysisResult:
    occurrences: dict[str, dict[str, _Record]] = defaultdict(dict)
    for record in records:
        for phrase in _EXPLANATION_PHRASES:
            if phrase in record.normalized:
                occurrences[phrase].setdefault(record.evidence_id, record)

    tables: list[dict[str, object]] = []
    flags: list[dict[str, object]] = []
    for phrase, by_evidence in sorted(occurrences.items()):
        if len(by_evidence) < REPEATED_PHRASE_MIN:
            continue
        retained = list(by_evidence.values())
        locators = [record.locator for record in retained]
        tables.append(
            {
                "phrase": phrase,
                "unique_evidence_records": len(retained),
                "source_extracts": len({record.path for record in retained}),
            }
        )
        flags.append(
            {
                "kind": "repeated_commentary_phrase",
                "phrase": phrase,
                "unique_evidence_records": len(retained),
                "locator": locators[0],
                "locators": locators[:MAX_FLAGS],
                "examples": [
                    {"locator": record.locator, "text": record.text[:500]}
                    for record in retained[:5]
                ],
                "detail": "repetition requires interpretation across materially different events",
            }
        )
    theme_evidence: dict[str, EvidenceReference] = {}
    for flag_item in flags:
        for locator in flag_item["locators"]:
            theme_evidence.setdefault(locator, EvidenceReference(locator=locator))
    overviews = (
        [
            DataOverview(
                overview_id="risk-commentary.repeated-themes",
                domain=SpecialistDomain.RISK_COMMENTARY,
                source_family="risk_commentary",
                title="Repeated risk-commentary explanations",
                summary=(
                    "Repeated explanations are counted on unique evidence records so copied "
                    "extract occurrences do not inflate the theme profile."
                ),
                status=OverviewStatus.AVAILABLE,
                metrics=[
                    OverviewMetric(
                        label="Repeated themes",
                        value=str(len(tables)),
                        unit="count",
                        basis=f"at least {REPEATED_PHRASE_MIN} unique evidence records",
                    )
                ],
                visual=TableVisual(
                    columns=["Explanation phrase", "Unique records", "Extracts"],
                    rows=[
                        [
                            str(table["phrase"]),
                            str(table["unique_evidence_records"]),
                            str(table["source_extracts"]),
                        ]
                        for table in tables
                    ],
                ),
                evidence=list(theme_evidence.values()),
                limitations=[
                    (
                        "Phrase matching is exact after normalization and requires "
                        "contextual interpretation."
                    )
                ],
            )
        ]
        if tables
        else []
    )
    return AnalysisResult(
        name="commentary_repeated_explanations",
        summary=(
            f"Deduplicated quoted records by evidence ID and retained {len(flags)} "
            f"explanation phrase(s) appearing at least {REPEATED_PHRASE_MIN} times."
        ),
        tables=tables,
        flag_candidates=flags[:MAX_FLAGS],
        overviews=overviews,
    )


def _normalized_reassurance_claims(records: list[_Record]) -> AnalysisResult:
    """Expose dated, scoped reassurance claims for downstream correlation."""
    unique: dict[str, _Record] = {}
    for record in records:
        if any(term in _normalize(record.claim) for term in _MATERIAL_REASSURANCE_TERMS):
            unique.setdefault(record.evidence_id, record)

    grouped: dict[str, list[_Record]] = defaultdict(list)
    for record in unique.values():
        grouped[_normalize(record.claim)].append(record)
    flags: list[dict[str, object]] = []
    for normalized_claim, grouped_records in sorted(grouped.items()):
        retained = sorted(grouped_records, key=lambda record: (record.event_date, record.line))
        if len(retained) < REPEATED_PHRASE_MIN:
            continue
        flags.append(
            {
                "kind": "repeated_commentary_reassurance_claim",
                "normalized_claim": normalized_claim,
                "occurrences": len(retained),
                "first_date": retained[0].event_date,
                "last_date": retained[-1].event_date,
                "desk": retained[0].desk,
                "perimeter": retained[0].perimeter,
                "metric": retained[0].metric,
                "claim": retained[0].claim,
                "validation": retained[0].validation,
                "locator": retained[0].locator,
                "locators": [record.locator for record in retained],
                "detail": (
                    "repeated dated reassurance claim; consistency with independently "
                    "reviewed metrics remains a downstream correlation question"
                ),
            }
        )
    for record in sorted(unique.values(), key=lambda item: (item.event_date, item.line)):
        flags.append(
            {
                "kind": "commentary_reassurance_claim",
                "event_date": record.event_date,
                "desk": record.desk,
                "perimeter": record.perimeter,
                "metric": record.metric,
                "claim": record.claim,
                "validation": record.validation,
                "evidence_id": record.evidence_id,
                "locator": record.locator,
                "detail": (
                    "source-backed claim only; the commentary specialist does not "
                    "determine whether other source families contradict it"
                ),
            }
        )
    tables = [
        {
            "event_date": record.event_date,
            "desk": record.desk,
            "perimeter": record.perimeter,
            "metric": record.metric,
            "claim": record.claim,
            "validation": record.validation,
            "locator": record.locator,
        }
        for record in sorted(unique.values(), key=lambda item: (item.event_date, item.line))
    ]
    return AnalysisResult(
        name="commentary_normalized_reassurance_claims",
        summary=(
            f"Normalized {len(unique)} material reassurance claim(s), including "
            f"{sum(item['kind'].startswith('repeated_') for item in flags)} repeated "
            "claim pattern(s), for downstream correlation."
        ),
        tables=tables,
        flag_candidates=flags[:MAX_FLAGS],
    )


def run_analysis(ctx: ToolContext, source_paths: list[str]) -> list[BaseModel]:
    """Run every deterministic screen over the scoped final Markdown extracts."""
    extracts: list[tuple[str, list[str], list[_Record]]] = []
    records: list[_Record] = []
    for path in source_paths:
        lines, source_records = _read_extract(ctx, path)
        if not lines:
            continue
        extracts.append((path, lines, source_records))
        records.extend(source_records)
    return [
        _population_profile(extracts),
        _validation_gaps(records),
        _internal_consistency(records),
        _repeated_explanations(records),
        _normalized_reassurance_claims(records),
    ]
