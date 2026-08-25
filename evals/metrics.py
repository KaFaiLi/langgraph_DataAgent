"""Schema-tolerant metrics for completed controlled-review run bundles.

This module is evaluation-only.  It consumes JSON artifacts and telemetry and
does not import production Pydantic models, open source files, invoke an LLM,
or mutate a run directory.  Keeping this boundary deliberately loose lets the
suite compare a legacy verifier run with the adversarial verifier while still
requiring the same observable outcomes.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ACCEPTED_STATUSES = frozenset(
    {
        "accept",
        "accepted",
        "pass",
        "passed",
        "revised",
        "verified",
    }
)
REJECTED_STATUSES = frozenset({"reject", "rejected", "discarded", "false_positive"})
UNRESOLVED_STATUSES = frozenset({"unknown", "unresolved", "pending"})
DECISIONS = ACCEPTED_STATUSES | REJECTED_STATUSES | UNRESOLVED_STATUSES | {"revise"}
SEVERITY_ALIASES = {
    "informational": "info",
    "information": "info",
    "notice": "info",
    "moderate": "medium",
    "major": "high",
    "severe": "critical",
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: object) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _status(value: object) -> str:
    """Return a stable lower-case outcome for strings and enum-like values."""

    if isinstance(value, Mapping):
        for key in ("decision", "verifier_status", "status", "outcome"):
            if key in value:
                return _status(value[key])
    text = _text(value)
    if text.startswith("verificationstatus."):
        text = text.split(".", 1)[1]
    if text.startswith("verifierdecision."):
        text = text.split(".", 1)[1]
    return text


def _finding_id(value: Mapping[str, Any]) -> str:
    for key in ("finding_id", "final_id", "id", "candidate_id"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _severity(value: object) -> str:
    text = _text(value)
    return SEVERITY_ALIASES.get(text, text)


def _ratio(numerator: float, denominator: float, *, empty: float = 0.0) -> float:
    if not denominator:
        return empty
    return round(float(numerator) / float(denominator), 6)


def _iter_mappings(value: object) -> Iterable[Mapping[str, Any]]:
    """Yield every mapping in a JSON value, including the root mapping."""

    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _iter_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_mappings(child)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class FindingSnapshot:
    """A normalized finding projection used only by the evaluator."""

    finding_id: str
    status: str
    severity: str
    source: str
    round_number: int | None = None
    candidate_ids: tuple[str, ...] = ()
    statement: str = ""

    @property
    def accepted(self) -> bool:
        return self.status in ACCEPTED_STATUSES or self.status == ""


@dataclass(frozen=True)
class TelemetryMetrics:
    """Aggregates extracted from completed JSONL telemetry."""

    adversarial_tool_calls: int = 0
    tier_token_totals: dict[str, dict[str, int]] = field(default_factory=dict)
    latency_seconds: float = 0.0
    invocation_count: int = 0


@dataclass(frozen=True)
class RunArtifacts:
    """Raw, production-independent view of a completed run directory."""

    run_dir: Path
    final_report: Mapping[str, Any]
    specialist_reports: tuple[Mapping[str, Any], ...]
    verification_artifacts: tuple[Mapping[str, Any], ...]
    telemetry: tuple[Mapping[str, Any], ...]


def load_run_artifacts(run_dir: str | Path) -> RunArtifacts:
    """Load completed JSON artifacts without requiring production imports.

    ``run_manifest.json`` is checked when present.  Small synthetic artifacts
    used for offline self-checks may omit it, but must still provide a final
    report.  The function never follows files outside ``run_dir`` and never
    reads raw source files.
    """

    root = Path(run_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"run directory does not exist: {run_dir}")
    manifest_path = root / "run_manifest.json"
    if manifest_path.is_file():
        manifest = _mapping(_read_json(manifest_path))
        status = _text(manifest.get("status"))
        if status and status not in {"completed", "complete", "succeeded", "success"}:
            raise ValueError(f"run is not completed: {status}")
    report_path = root / "final_report.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"completed run is missing {report_path.name}: {root}")
    final_report = _mapping(_read_json(report_path))

    specialists: list[Mapping[str, Any]] = []
    verification: list[Mapping[str, Any]] = []
    specialist_root = root / "specialists"
    if specialist_root.is_dir():
        for path in sorted(specialist_root.glob("*.json")):
            if path.name.endswith(".verification.json"):
                payload = _mapping(_read_json(path))
                if payload:
                    verification.append(payload)
            elif not path.name.endswith(".research_trace.json"):
                payload = _mapping(_read_json(path))
                if payload:
                    specialists.append(payload)

    telemetry: list[Mapping[str, Any]] = []
    telemetry_root = root / "telemetry"
    if telemetry_root.is_dir():
        for path in sorted(telemetry_root.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, Mapping):
                    telemetry.append(payload)
    return RunArtifacts(
        run_dir=root,
        final_report=final_report,
        specialist_reports=tuple(specialists),
        verification_artifacts=tuple(verification),
        telemetry=tuple(telemetry),
    )


def _report_findings(artifacts: RunArtifacts) -> list[FindingSnapshot]:
    """Extract final retained findings, preferring ``final_report.json``."""

    report = artifacts.final_report
    values = _list(report.get("key_findings")) or _list(report.get("findings"))
    snapshots: list[FindingSnapshot] = []
    for value in values:
        finding = _mapping(value)
        identifier = _finding_id(finding)
        if not identifier:
            continue
        status = _status(finding.get("verifier_status", finding.get("status", "")))
        candidate_ids = tuple(
            str(item)
            for item in _list(finding.get("deterministic_candidate_ids"))
            if isinstance(item, str)
        )
        snapshots.append(
            FindingSnapshot(
                finding_id=identifier,
                status=status,
                severity=_severity(finding.get("severity")),
                source="final_report",
                candidate_ids=candidate_ids,
                statement=str(finding.get("statement", finding.get("claim", ""))),
            )
        )
    if snapshots:
        return _unique_findings(snapshots)

    # A failed/partial run may not have a final report.  This fallback is also
    # useful when scoring a specialist in isolation.
    for report in artifacts.specialist_reports:
        for value in _list(report.get("findings")):
            finding = _mapping(value)
            identifier = _finding_id(finding)
            if identifier:
                snapshots.append(
                    FindingSnapshot(
                        finding_id=identifier,
                        status=_status(finding.get("verifier_status", finding.get("status", ""))),
                        severity=_severity(finding.get("severity")),
                        source="specialist_report",
                        candidate_ids=tuple(
                            str(item)
                            for item in _list(finding.get("deterministic_candidate_ids"))
                            if isinstance(item, str)
                        ),
                        statement=str(finding.get("statement", finding.get("claim", ""))),
                    )
                )
    return _unique_findings(snapshots)


def _unique_findings(findings: Iterable[FindingSnapshot]) -> list[FindingSnapshot]:
    unique: dict[str, FindingSnapshot] = {}
    for finding in findings:
        unique.setdefault(finding.finding_id, finding)
    return list(unique.values())


def _history_records(artifacts: RunArtifacts) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for artifact in artifacts.verification_artifacts:
        for value in _iter_mappings(artifact):
            if "round_number" not in value:
                continue
            decision = _status(value.get("decision", value.get("verifier_status")))
            identifier = _finding_id(value)
            if identifier and decision in DECISIONS:
                records.append(value)
    return records


def _initial_statuses(artifacts: RunArtifacts) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for artifact in artifacts.verification_artifacts:
        for key in ("initial_candidates", "initial_findings", "candidates"):
            for value in _list(artifact.get(key)):
                candidate = _mapping(value)
                identifier = _finding_id(candidate)
                if not identifier:
                    continue
                status = _status(
                    candidate.get(
                        "verifier_status", candidate.get("status", candidate.get("decision"))
                    )
                )
                if status:
                    statuses.setdefault(identifier, status)
        for record in _history_records_for_artifact(artifact):
            identifier = _finding_id(record)
            if identifier:
                statuses.setdefault(identifier, _status(record.get("decision")))
    return statuses


def _history_records_for_artifact(artifact: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = []
    for value in _iter_mappings(artifact):
        if (
            "round_number" in value
            and _status(value.get("decision")) in DECISIONS
            and _finding_id(value)
        ):
            values.append(value)
    return values


def _final_statuses(artifacts: RunArtifacts, findings: list[FindingSnapshot]) -> dict[str, str]:
    statuses = {finding.finding_id: finding.status or "accepted" for finding in findings}
    for artifact in artifacts.verification_artifacts:
        for key, default_status in (
            ("verified_findings", "passed"),
            ("rejected_findings", "rejected"),
            ("unresolved_findings", "unresolved"),
        ):
            for value in _list(artifact.get(key)):
                finding = _mapping(value)
                identifier = _finding_id(finding)
                if identifier:
                    statuses.setdefault(identifier, _status(finding) or default_status)
    return statuses


def _challenge_records(artifacts: RunArtifacts) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []

    def visit(value: object, parent_finding_id: str = "") -> None:
        if isinstance(value, Mapping):
            finding_id = _finding_id(value) or parent_finding_id
            challenge_type = value.get("challenge_type", value.get("type"))
            challenge_status = _status(value.get("status", value.get("outcome")))
            if isinstance(challenge_type, str) and challenge_status:
                record = dict(value)
                if finding_id:
                    record.setdefault("finding_id", finding_id)
                records.append(record)
            for child in value.values():
                visit(child, finding_id)
        elif isinstance(value, list):
            for child in value:
                visit(child, parent_finding_id)

    for artifact in artifacts.verification_artifacts:
        visit(artifact)
    # Some implementations persist challenge cases next to the final report.
    visit(artifacts.final_report)
    return records


def _telemetry_metrics(events: Iterable[Mapping[str, Any]]) -> TelemetryMetrics:
    starts: dict[str, Mapping[str, Any]] = {}
    tier_tokens: dict[str, dict[str, int]] = defaultdict(
        lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    )
    adversarial_tool_calls = 0
    latency = 0.0
    invocation_count = 0

    def is_adversarial(event: Mapping[str, Any]) -> bool:
        haystack = " ".join(
            str(event.get(key, ""))
            for key in ("node", "graph", "stage", "phase", "agent", "specialist")
        ).lower()
        return any(token in haystack for token in ("adversarial", "challenger", "challenge"))

    for event in events:
        event_name = _text(event.get("event"))
        run_id = str(event.get("run_id", ""))
        if event_name == "llm_start":
            starts[run_id] = event
        elif event_name == "llm_end":
            invocation_count += 1
            start = starts.get(run_id, {})
            tier = _text(event.get("tier")) or _text(start.get("tier")) or "unknown"
            bucket = tier_tokens[tier]
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = event.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    bucket[key] += int(value)
            duration = event.get("duration_seconds")
            if isinstance(duration, (int, float)) and not isinstance(duration, bool):
                latency += float(duration)
            if is_adversarial(start) or is_adversarial(event):
                count = event.get("tool_calls", event.get("adversarial_tool_calls", 0))
                if isinstance(count, list):
                    count = len(count)
                if isinstance(count, (int, float)) and not isinstance(count, bool):
                    adversarial_tool_calls += int(count)
        elif event_name in {
            "tool_call",
            "tool_start",
            "tool_end",
            "tool_invocation",
        } and is_adversarial(event):
            count = event.get("count", event.get("tool_calls", 1))
            if isinstance(count, list):
                count = len(count)
            if isinstance(count, (int, float)) and not isinstance(count, bool):
                adversarial_tool_calls += int(count)

    return TelemetryMetrics(
        adversarial_tool_calls=adversarial_tool_calls,
        tier_token_totals={tier: dict(values) for tier, values in tier_tokens.items()},
        latency_seconds=round(latency, 6),
        invocation_count=invocation_count,
    )


def _gold_expected(gold: Mapping[str, Any]) -> Mapping[str, Any]:
    expected = _mapping(gold.get("expected"))
    return expected or gold


def _entries(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [
            item if isinstance(item, Mapping) else {"finding_id": item}
            for item in value
            if isinstance(item, (Mapping, str))
        ]
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, str):
        return [{"finding_id": value}]
    return []


def _expected_findings(expected: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = expected.get("required_findings", expected.get("true_positive_findings", []))
    result: list[Mapping[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, str):
            result.append({"finding_id": item})
        elif isinstance(item, Mapping):
            result.append(item)
    return result


def _aliases(entry: Mapping[str, Any]) -> set[str]:
    result = set()
    for key in ("finding_id", "id", "final_id"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            result.add(value)
    for key in ("aliases", "finding_aliases"):
        for value in _list(entry.get(key)):
            if isinstance(value, str) and value:
                result.add(value)
    return result


def _matches(snapshot: FindingSnapshot, entry: Mapping[str, Any]) -> bool:
    return bool(_aliases(entry) & {snapshot.finding_id})


@dataclass(frozen=True)
class EvaluationMetrics:
    """All required suite metrics for one completed run."""

    case_id: str
    run_dir: str
    finding_precision: float
    unsupported_pass_rate: float
    true_positive_preservation: float
    contradiction_recall: float
    verifier_rescue: float
    omission_rescue: float
    revision_success: float
    severity_calibration: float
    average_rounds: float
    adversarial_tool_calls_per_finding: float
    adversarial_tool_calls: int
    tier_token_totals: dict[str, dict[str, int]]
    latency_seconds: float
    llm_invocations: int
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def token_totals_by_tier(self) -> dict[str, dict[str, int]]:
        """Alias used by report consumers that prefer a longer field name."""

        return self.tier_token_totals

    @property
    def wall_clock_latency_seconds(self) -> float:
        return self.latency_seconds

    def to_dict(self) -> dict[str, Any]:
        result = {
            "case_id": self.case_id,
            "run_dir": self.run_dir,
            "finding_precision": self.finding_precision,
            "unsupported_pass_rate": self.unsupported_pass_rate,
            "true_positive_preservation": self.true_positive_preservation,
            "contradiction_recall": self.contradiction_recall,
            "verifier_rescue": self.verifier_rescue,
            "omission_rescue": self.omission_rescue,
            "revision_success": self.revision_success,
            "severity_calibration": self.severity_calibration,
            "average_rounds": self.average_rounds,
            "adversarial_tool_calls_per_finding": self.adversarial_tool_calls_per_finding,
            "adversarial_tool_calls": self.adversarial_tool_calls,
            "tier_token_totals": self.tier_token_totals,
            "token_totals_by_tier": self.tier_token_totals,
            "tier_total_tokens": {
                tier: values.get("total_tokens", 0)
                for tier, values in self.tier_token_totals.items()
            },
            "latency_seconds": self.latency_seconds,
            "wall_clock_latency_seconds": self.latency_seconds,
            "llm_invocations": self.llm_invocations,
            "counts": self.counts,
        }
        return result


def evaluate_run(
    run_dir: str | Path,
    gold_manifest: Mapping[str, Any],
    *,
    case_id: str | None = None,
) -> EvaluationMetrics:
    """Score a completed run against an evaluation-only gold manifest."""

    artifacts = load_run_artifacts(run_dir)
    findings = _report_findings(artifacts)
    expected = _gold_expected(gold_manifest)
    required = _expected_findings(expected)
    required_groups = [_aliases(entry) for entry in required]
    required_groups = [group for group in required_groups if group]
    forbidden_value = expected.get(
        "forbidden_findings", expected.get("false_positive_findings", [])
    )
    forbidden_ids = {alias for entry in _entries(forbidden_value) for alias in _aliases(entry)}
    accepted_findings = [finding for finding in findings if finding.accepted]
    accepted_ids = {finding.finding_id for finding in accepted_findings}
    matched_required_groups = {
        index for index, group in enumerate(required_groups) if accepted_ids & group
    }
    true_positive_ids = {
        finding.finding_id
        for finding in accepted_findings
        if any(finding.finding_id in group for group in required_groups)
    }
    unsupported_passes = accepted_ids - true_positive_ids
    finding_precision = _ratio(len(matched_required_groups), len(accepted_ids), empty=1.0)
    unsupported_pass_rate = _ratio(len(unsupported_passes), len(accepted_ids))
    true_positive_preservation = _ratio(
        len(matched_required_groups), len(required_groups), empty=1.0
    )

    challenges = _challenge_records(artifacts)
    contradiction_entries = _entries(
        expected.get("contradictions", expected.get("expected_contradictions", []))
    )
    contradiction_hits = 0
    for expected_challenge in contradiction_entries:
        expected_type = _text(
            expected_challenge.get("challenge_type", expected_challenge.get("type"))
        )
        expected_finding = _text(
            expected_challenge.get("finding_id", expected_challenge.get("finding"))
        )
        hit = False
        for challenge in challenges:
            actual_type = _text(challenge.get("challenge_type", challenge.get("type")))
            actual_finding = _text(challenge.get("finding_id", challenge.get("finding")))
            actual_status = _status(challenge.get("status", challenge.get("outcome")))
            if (
                (not expected_type or actual_type == expected_type)
                and (not expected_finding or actual_finding in {expected_finding, ""})
                and actual_status in {"fail", "failed", "unknown", "unresolved"}
            ):
                hit = True
                break
        contradiction_hits += int(hit)
    contradiction_recall = _ratio(contradiction_hits, len(contradiction_entries), empty=1.0)

    initial = _initial_statuses(artifacts)
    final = _final_statuses(artifacts, findings)
    rescue_groups = [
        _aliases(entry)
        for entry in _entries(expected.get("verifier_rescue", expected.get("rescue_findings", [])))
    ]
    rescue_groups = [group for group in rescue_groups if group]
    verifier_rescue_hits = sum(
        1
        for group in rescue_groups
        if any(
            _status(initial.get(identifier)) in REJECTED_STATUSES | UNRESOLVED_STATUSES | {"revise"}
            for identifier in group
        )
        and any(_status(final.get(identifier)) in ACCEPTED_STATUSES for identifier in group)
    )
    verifier_rescue = _ratio(verifier_rescue_hits, len(rescue_groups), empty=1.0)

    revision_value = expected.get("revision_required", expected.get("revision_findings", []))
    revision_groups = [_aliases(entry) for entry in _entries(revision_value)]
    revision_groups = [group for group in revision_groups if group]
    if isinstance(revision_value, bool):
        revision_groups = [
            {_finding_id(record)}
            for record in _history_records(artifacts)
            if _status(record.get("decision")) == "revise" and _finding_id(record)
        ]
    revision_success_hits = 0
    for group in revision_groups:
        records = [record for record in _history_records(artifacts) if _finding_id(record) in group]
        had_revise = any(_status(record.get("decision")) == "revise" for record in records)
        if had_revise and any(
            _status(final.get(identifier)) in ACCEPTED_STATUSES for identifier in group
        ):
            revision_success_hits += 1
    revision_success = _ratio(revision_success_hits, len(revision_groups), empty=1.0)

    omission_entries = _entries(expected.get("omission_candidates", expected.get("omissions", [])))
    omission_ids = {
        str(entry.get("candidate_id"))
        for entry in omission_entries
        if isinstance(entry.get("candidate_id"), str)
    }
    dispositions: dict[str, str] = {}
    omission_rescue_used = False
    for artifact in artifacts.verification_artifacts:
        for value in _iter_mappings(artifact):
            candidate_id = value.get("candidate_id")
            disposition = _status(value.get("disposition", value.get("candidate_disposition")))
            if isinstance(candidate_id, str) and disposition:
                dispositions[candidate_id] = disposition
            if value.get("rescue_used") is True or value.get("rescue_round_used") is True:
                omission_rescue_used = True
            for covered in _list(value.get("covered_candidate_ids")):
                if isinstance(covered, str):
                    dispositions.setdefault(covered, "covered")
    rescued_omissions = sum(
        1
        for identifier in omission_ids
        if identifier in dispositions
        or any(identifier in finding.candidate_ids for finding in accepted_findings)
        or any(identifier == finding.finding_id for finding in accepted_findings)
    )
    if omission_ids and omission_rescue_used and not rescued_omissions:
        # A bounded audit can persist only the boolean when all candidates were
        # accounted for in the new finding set.
        rescued_omissions = len(omission_ids)
    omission_rescue = _ratio(rescued_omissions, len(omission_ids), empty=1.0)

    severity_hits = 0
    severity_total = 0
    for entry in required:
        expected_severity = entry.get("severity", entry.get("expected_severity"))
        if expected_severity is None:
            continue
        severity_total += 1
        matched = next((finding for finding in findings if _matches(finding, entry)), None)
        if matched and _severity(matched.severity) == _severity(expected_severity):
            severity_hits += 1
    severity_calibration = _ratio(severity_hits, severity_total, empty=1.0)

    history_rounds: dict[str, int] = {}
    for record in _history_records(artifacts):
        identifier = _finding_id(record)
        round_number = record.get("round_number")
        if identifier and isinstance(round_number, int):
            history_rounds[identifier] = max(history_rounds.get(identifier, 0), round_number)
    artifact_round = 0
    for artifact in artifacts.verification_artifacts:
        value = artifact.get("verifier_round", artifact.get("round_number", 0))
        if isinstance(value, int):
            artifact_round = max(artifact_round, value)
    rounds = [history_rounds.get(finding.finding_id, artifact_round or 1) for finding in findings]
    average_rounds = round(sum(rounds) / len(rounds), 6) if rounds else 0.0

    telemetry = _telemetry_metrics(artifacts.telemetry)
    tool_calls_per_finding = _ratio(
        telemetry.adversarial_tool_calls,
        len(findings),
    )
    resolved_case_id = case_id or str(gold_manifest.get("case_id", artifacts.run_dir.name))
    counts = {
        "expected_findings": len(required_groups),
        "predicted_findings": len(accepted_ids),
        "true_positive_findings": len(true_positive_ids),
        "unsupported_pass_findings": len(unsupported_passes),
        "forbidden_findings": len(accepted_ids & forbidden_ids),
        "expected_contradictions": len(contradiction_entries),
        "detected_contradictions": contradiction_hits,
        "expected_verifier_rescues": len(rescue_groups),
        "verifier_rescue_hits": verifier_rescue_hits,
        "expected_omission_rescues": len(omission_ids),
        "omission_rescue_hits": rescued_omissions,
        "expected_revisions": len(revision_groups),
        "revision_success_hits": revision_success_hits,
        "severity_total": severity_total,
        "severity_hits": severity_hits,
    }
    return EvaluationMetrics(
        case_id=resolved_case_id,
        run_dir=str(artifacts.run_dir),
        finding_precision=finding_precision,
        unsupported_pass_rate=unsupported_pass_rate,
        true_positive_preservation=true_positive_preservation,
        contradiction_recall=contradiction_recall,
        verifier_rescue=verifier_rescue,
        omission_rescue=omission_rescue,
        revision_success=revision_success,
        severity_calibration=severity_calibration,
        average_rounds=average_rounds,
        adversarial_tool_calls_per_finding=tool_calls_per_finding,
        adversarial_tool_calls=telemetry.adversarial_tool_calls,
        tier_token_totals=telemetry.tier_token_totals,
        latency_seconds=telemetry.latency_seconds,
        llm_invocations=telemetry.invocation_count,
        counts=counts,
    )


def aggregate_metrics(metrics: Iterable[EvaluationMetrics]) -> dict[str, Any]:
    """Aggregate case metrics with count-weighted rates.

    Latency and tool calls are additive; ratios use their raw numerators and
    denominators so benign no-finding cases do not skew precision or recall.
    """

    values = list(metrics)
    if not values:
        return {
            "case_count": 0,
            "finding_precision": 0.0,
            "unsupported_pass_rate": 0.0,
            "true_positive_preservation": 0.0,
            "contradiction_recall": 0.0,
            "verifier_rescue": 0.0,
            "omission_rescue": 0.0,
            "revision_success": 0.0,
            "severity_calibration": 0.0,
            "average_rounds": 0.0,
            "adversarial_tool_calls_per_finding": 0.0,
            "adversarial_tool_calls": 0,
            "tier_token_totals": {},
            "latency_seconds": 0.0,
            "llm_invocations": 0,
        }
    totals: dict[str, int] = defaultdict(int)
    for item in values:
        for key, value in item.counts.items():
            totals[key] += value
    tier_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    )
    for item in values:
        for tier, buckets in item.tier_token_totals.items():
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                tier_totals[tier][key] += int(buckets.get(key, 0))
    predicted = totals["predicted_findings"]
    average_round_denominator = sum(item.counts.get("predicted_findings", 0) for item in values)
    if average_round_denominator:
        average_rounds = round(
            sum(item.average_rounds * item.counts.get("predicted_findings", 0) for item in values)
            / average_round_denominator,
            6,
        )
    else:
        average_rounds = round(
            sum(item.average_rounds for item in values) / len(values),
            6,
        )
    result = {
        "case_count": len(values),
        "finding_precision": _ratio(totals["true_positive_findings"], predicted, empty=1.0),
        "unsupported_pass_rate": _ratio(totals["unsupported_pass_findings"], predicted),
        "true_positive_preservation": _ratio(
            totals["true_positive_findings"], totals["expected_findings"], empty=1.0
        ),
        "contradiction_recall": _ratio(
            totals["detected_contradictions"], totals["expected_contradictions"], empty=1.0
        ),
        "verifier_rescue": _ratio(
            totals["verifier_rescue_hits"], totals["expected_verifier_rescues"], empty=1.0
        ),
        "omission_rescue": _ratio(
            totals["omission_rescue_hits"], totals["expected_omission_rescues"], empty=1.0
        ),
        "revision_success": _ratio(
            totals["revision_success_hits"], totals["expected_revisions"], empty=1.0
        ),
        "severity_calibration": _ratio(
            totals["severity_hits"], totals["severity_total"], empty=1.0
        ),
        "average_rounds": average_rounds,
        "adversarial_tool_calls_per_finding": _ratio(
            sum(item.adversarial_tool_calls for item in values), predicted
        ),
        "adversarial_tool_calls": sum(item.adversarial_tool_calls for item in values),
        "tier_token_totals": dict(tier_totals),
        "token_totals_by_tier": dict(tier_totals),
        "latency_seconds": round(sum(item.latency_seconds for item in values), 6),
        "wall_clock_latency_seconds": round(sum(item.latency_seconds for item in values), 6),
        "llm_invocations": sum(item.llm_invocations for item in values),
        "counts": dict(totals),
    }
    return result


# Short aliases keep the evaluator convenient for notebooks and historical
# harness scripts without creating a second scoring implementation.
compute_metrics = evaluate_run
score_run = evaluate_run
