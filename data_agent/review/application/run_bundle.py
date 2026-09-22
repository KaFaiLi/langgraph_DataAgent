"""Validated, raw-source-free boundaries for completed review archives."""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.reports import FinalReport, SpecialistReport
from data_agent.review.domain.review import ReviewRun, RunStatus
from data_agent.review.domain.source import DateRange, SourceManifest
from data_agent.review.domain.verification import OmissionAuditResult
from data_agent.review.ingestion.evidence_validator import EvidenceValidator

RUN_MANIFEST_FILE = "run_manifest.json"
CATALOG_FILE = "catalog.json"
LEAD_VERIFICATION_FILE = "lead_verification.json"


class RunBundleError(RuntimeError):
    """A stable, artifact-specific validation error for CLI and service callers."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class CompletedRunBundle:
    """The sealed reviewed-output corpus that downstream consumers may use."""

    run_dir: Path
    run: ReviewRun
    catalog: SourceManifest
    desk_context: DeskContext
    final_report: FinalReport
    final_markdown: str
    specialist_reports: dict[SpecialistDomain, SpecialistReport]
    specialist_markdown: dict[SpecialistDomain, str]
    verification_artifacts: dict[SpecialistDomain, dict[str, Any]]
    approved_evidence_index: frozenset[str]
    lead_verification_history: list[dict[str, Any]] = dataclass_field(default_factory=list)
    research_trace_artifacts: dict[SpecialistDomain, list[Any]] = dataclass_field(
        default_factory=dict
    )
    adversarial_trace_artifacts: dict[SpecialistDomain, dict[str, list[Any]]] = dataclass_field(
        default_factory=dict
    )


def _run_directory(run_dir: str | Path) -> Path:
    path = Path(run_dir)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RunBundleError("run_dir_missing", f"run directory does not exist: {path}") from exc
    if not resolved.is_dir():
        raise RunBundleError("run_dir_invalid", f"run path is not a directory: {resolved}")
    return resolved


def _artifact_path(run_dir: Path, relative_path: str | Path) -> Path:
    """Resolve a required artifact while rejecting symlinks out of the archive."""
    path = run_dir / relative_path
    if not path.is_file():
        raise RunBundleError("artifact_missing", f"required artifact missing: {relative_path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RunBundleError(
            "artifact_unreadable", f"cannot resolve {relative_path}: {exc}"
        ) from exc
    if not resolved.is_relative_to(run_dir):
        raise RunBundleError(
            "artifact_path_escape",
            f"artifact escapes the completed run: {relative_path}",
        )
    return resolved


def _read_json(path: Path, artifact: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RunBundleError("artifact_unreadable", f"cannot read {artifact}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RunBundleError(
            "artifact_invalid_json", f"invalid JSON in {artifact}: {exc.msg}"
        ) from exc


def _typed(model: type[Any], payload: object, artifact: str) -> Any:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise RunBundleError("artifact_invalid_schema", f"invalid {artifact}: {exc}") from exc


def _read_nonempty_text(path: Path, artifact: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RunBundleError("artifact_unreadable", f"cannot read {artifact}: {exc}") from exc
    if not text.strip():
        raise RunBundleError("artifact_empty", f"required artifact is empty: {artifact}")
    return text


def _validate_lead_verification_artifact(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise RunBundleError(
            "lead_verification_invalid", "lead_verification.json must contain an object"
        )
    history = payload.get("history")
    if not isinstance(history, list) or any(not isinstance(item, dict) for item in history):
        raise RunBundleError(
            "lead_verification_invalid", "lead verification history must be a list of objects"
        )
    lead_round = payload.get("lead_round")
    if not isinstance(lead_round, int) or lead_round != len(history) or not 0 <= lead_round <= 2:
        raise RunBundleError(
            "lead_verification_invalid",
            "lead_round must equal the bounded lead verification history length",
        )
    return [dict(item) for item in history]


def _manifest_identity(
    manifest: SourceManifest,
) -> list[tuple[str, str, str, int, str]]:
    return [
        (
            source.source_id,
            source.path,
            source.sha256,
            source.size_bytes,
            source.source_type.value,
        )
        for source in manifest.sources
    ]


def _report_locators(
    reports: dict[SpecialistDomain, SpecialistReport],
) -> frozenset[str]:
    locators: set[str] = set()

    def add_references(references: list[EvidenceReference]) -> None:
        locators.update(reference.locator for reference in references)

    for report in reports.values():
        for finding in report.findings:
            add_references(finding.evidence)
            add_references(finding.counter_evidence)
        for overview in report.data_overviews:
            add_references(overview.evidence)
    return frozenset(locators)


def _final_references(report: FinalReport) -> list[EvidenceReference]:
    references = list(report.evidence_index)
    for finding in report.key_findings:
        references.extend(finding.evidence)
    for cluster in report.cross_source_findings:
        references.extend(cluster.supporting_evidence)
    return references


def _validate_verification_artifact(
    artifact: object, *, artifact_name: str, report: SpecialistReport
) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        raise RunBundleError(
            "artifact_invalid_schema",
            f"invalid {artifact_name}: expected a JSON object",
        )
    required_lists = (
        "initial_candidates",
        "verified_findings",
        "rejected_findings",
        "unresolved_findings",
    )
    missing = [key for key in required_lists if key not in artifact]
    verifier_round = artifact.get("verifier_round")
    if missing or type(verifier_round) is not int or verifier_round < 0:
        raise RunBundleError(
            "artifact_invalid_schema",
            f"invalid {artifact_name}: required verifier-effectiveness fields are missing",
        )
    if any(not isinstance(artifact[key], list) for key in required_lists):
        raise RunBundleError(
            "artifact_invalid_schema",
            f"invalid {artifact_name}: verifier lists are malformed",
        )
    try:
        for key in required_lists:
            for finding in artifact[key]:
                Finding.model_validate(finding)
    except ValidationError as exc:
        raise RunBundleError(
            "artifact_invalid_schema",
            f"invalid {artifact_name}: verifier finding is malformed: {exc}",
        ) from exc
    # Pydantic's SpecialistReport validates each retained VerificationRound.
    # Requiring this history keeps the artifact tied to the bounded verifier.
    if any(not isinstance(rounds, list) for rounds in report.verification_history.values()):
        raise RunBundleError(
            "artifact_invalid_schema",
            f"invalid {artifact_name}: verification history is malformed",
        )
    omission = artifact.get("omission_audit")
    if omission is not None:
        try:
            OmissionAuditResult.model_validate(omission)
        except ValidationError as exc:
            raise RunBundleError(
                "artifact_invalid_schema",
                f"invalid {artifact_name}: omission audit is malformed",
            ) from exc
    return artifact


def _load_trace_artifacts(
    root: Path,
    *,
    stem: str,
    verification: dict[str, Any],
) -> tuple[list[Any], dict[str, list[Any]]]:
    """Load separate raw analyst/challenger traces for modern specialist artifacts.

    Older hand-authored archives contain only the original verifier lists.  They
    remain readable; once the modern evidence/adversarial fields are present,
    both trace files are required and shape-checked together.
    """

    modern = any(
        key in verification for key in ("evidence_gates", "adversarial_cases", "adjudications")
    )
    if not modern:
        return [], {}
    research_path = _artifact_path(root, Path("specialists") / f"{stem}.research_trace.json")
    adversarial_path = _artifact_path(root, Path("specialists") / f"{stem}.adversarial_trace.json")
    raw_research = _read_json(research_path, research_path.name)
    raw_adversarial = _read_json(adversarial_path, adversarial_path.name)
    if not isinstance(raw_research, list):
        raise RunBundleError(
            "artifact_invalid_schema",
            f"invalid {research_path.name}: expected a JSON list",
        )
    if not isinstance(raw_adversarial, dict) or any(
        not isinstance(trace, list) for trace in raw_adversarial.values()
    ):
        raise RunBundleError(
            "artifact_invalid_schema",
            f"invalid {adversarial_path.name}: expected finding-id to list mapping",
        )
    return raw_research, {str(key): list(value) for key, value in raw_adversarial.items()}


def load_completed_run(run_dir: str | Path) -> CompletedRunBundle:
    """Load a completed archive without reopening or otherwise reading raw sources."""
    root = _run_directory(run_dir)
    run = _typed(
        ReviewRun,
        _read_json(_artifact_path(root, RUN_MANIFEST_FILE), RUN_MANIFEST_FILE),
        RUN_MANIFEST_FILE,
    )
    if run.status is not RunStatus.COMPLETED:
        raise RunBundleError("run_not_completed", f"run status is {run.status.value!r}")
    if not run.manifest.sources:
        raise RunBundleError("manifest_empty", "completed run manifest contains no sources")
    pending = [entry.source_id for entry in run.coverage if not entry.is_settled()]
    if pending:
        raise RunBundleError(
            "coverage_unsettled",
            f"unsettled coverage for: {', '.join(sorted(pending))}",
        )

    catalog = _typed(
        SourceManifest,
        _read_json(_artifact_path(root, CATALOG_FILE), CATALOG_FILE),
        CATALOG_FILE,
    )
    if not catalog.sources:
        raise RunBundleError("manifest_empty", "catalog.json contains no sources")
    if _manifest_identity(catalog) != _manifest_identity(run.manifest):
        raise RunBundleError(
            "catalog_manifest_mismatch",
            "catalog.json does not match the completed run manifest source identities",
        )
    desk_context = _typed(
        DeskContext,
        _read_json(_artifact_path(root, "desk_context.json"), "desk_context.json"),
        "desk_context.json",
    )
    final_report = _typed(
        FinalReport,
        _read_json(_artifact_path(root, "final_report.json"), "final_report.json"),
        "final_report.json",
    )
    final_markdown = _read_nonempty_text(
        _artifact_path(root, "final_findings.md"), "final_findings.md"
    )
    lead_verification_history = _validate_lead_verification_artifact(
        _read_json(
            _artifact_path(root, LEAD_VERIFICATION_FILE),
            LEAD_VERIFICATION_FILE,
        )
    )

    reports: dict[SpecialistDomain, SpecialistReport] = {}
    markdown: dict[SpecialistDomain, str] = {}
    verification: dict[SpecialistDomain, dict[str, Any]] = {}
    research_traces: dict[SpecialistDomain, list[Any]] = {}
    adversarial_traces: dict[SpecialistDomain, dict[str, list[Any]]] = {}
    task_sources: dict[SpecialistDomain, set[str]] = {}
    task_periods: dict[SpecialistDomain, DateRange | None] = {}
    for task in run.tasks:
        task_sources.setdefault(task.domain, set()).update(task.source_ids)
        task_periods.setdefault(task.domain, task.scope)
    for domain, expected_sources in task_sources.items():
        stem = domain.value
        report_relative = Path("specialists") / f"{stem}.json"
        report_path = _artifact_path(root, report_relative)
        report = _typed(
            SpecialistReport,
            _read_json(report_path, report_path.name),
            report_path.name,
        )
        if report.domain is not domain:
            raise RunBundleError(
                "specialist_domain_mismatch",
                f"{report_path.name} declares {report.domain.value!r}, expected {domain.value!r}",
            )
        expected_period = task_periods[domain]
        if expected_period is None:
            expected_period = DateRange(
                start=desk_context.review_start, end=desk_context.review_end
            )
        if report.review_period != expected_period:
            raise RunBundleError(
                "specialist_period_mismatch",
                f"{report_path.name} review period does not match its selected task",
            )
        if set(report.sources_reviewed) != expected_sources:
            raise RunBundleError(
                "specialist_sources_mismatch",
                f"{report_path.name} sources_reviewed does not match its selected task",
            )
        reports[domain] = report
        markdown[domain] = _read_nonempty_text(
            _artifact_path(root, Path("specialists") / f"{stem}.md"),
            f"specialists/{stem}.md",
        )
        verification_path = _artifact_path(root, Path("specialists") / f"{stem}.verification.json")
        raw_verification = _read_json(verification_path, verification_path.name)
        verification[domain] = _validate_verification_artifact(
            raw_verification, artifact_name=verification_path.name, report=report
        )
        research_trace, adversarial_trace = _load_trace_artifacts(
            root,
            stem=stem,
            verification=verification[domain],
        )
        research_traces[domain] = research_trace
        adversarial_traces[domain] = adversarial_trace

    approved_locators = _report_locators(reports)
    validation = EvidenceValidator.validate_approved_references(
        _final_references(final_report), set(approved_locators)
    )
    if validation.failures:
        detail = "; ".join(
            f"{failure.locator}: {failure.reason}" for failure in validation.failures
        )
        raise RunBundleError("approved_evidence_invalid", detail)

    return CompletedRunBundle(
        run_dir=root,
        run=run,
        catalog=catalog,
        desk_context=desk_context,
        final_report=final_report,
        final_markdown=final_markdown,
        specialist_reports=reports,
        specialist_markdown=markdown,
        verification_artifacts=verification,
        approved_evidence_index=approved_locators,
        lead_verification_history=lead_verification_history,
        research_trace_artifacts=research_traces,
        adversarial_trace_artifacts=adversarial_traces,
    )
