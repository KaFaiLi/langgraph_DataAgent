"""Behavioral tests for the authoritative deterministic check evaluator."""

from __future__ import annotations

from data_agent.review.completion import evaluate_check
from data_agent.review.domain.analysis import (
    AnalysisExecution,
    AnalysisResult,
    AnalysisStatus,
    PopulationReceipt,
    SourceBinding,
)
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.plan import (
    AnalysisRequirement,
    CheckApplicability,
    CheckStatus,
    PlannedCheck,
)
from data_agent.review.domain.source import Source, SourceManifest, SourceType

SOURCE = Source(
    source_id="SRC-1",
    path="risk/input.csv",
    source_type=SourceType.CSV,
    sha256="a" * 64,
    size_bytes=10,
    candidate_domains=[SpecialistDomain.RISK_METRICS],
)
CATALOG = SourceManifest(sources=[SOURCE])
CHECK = PlannedCheck(
    check_id="CHECK-RISK",
    domain=SpecialistDomain.RISK_METRICS,
    title="Risk check",
    playbook="risk-metrics",
    playbook_version="1.0",
    required_source_domains=[SpecialistDomain.RISK_METRICS],
    source_ids=[SOURCE.source_id],
    analysis_requirements=(
        AnalysisRequirement(name="risk_analysis", required_source_ids=(SOURCE.source_id,)),
    ),
    applicability=CheckApplicability.APPLICABLE,
    applicability_reason="input available",
    completion_criteria=["analysis succeeds"],
    policy_fingerprint="b" * 64,
)


def _output(
    *, status: AnalysisStatus, sha256: str = SOURCE.sha256, rows: int = 1
) -> AnalysisResult:
    return AnalysisResult(
        name="risk_analysis",
        summary="A material exception was found.",
        flag_candidates=[{"kind": "material_exception"}],
        execution=AnalysisExecution(
            status=status,
            population=PopulationReceipt(
                source_bindings=[
                    SourceBinding(source_id=SOURCE.source_id, path=SOURCE.path, sha256=sha256)
                ],
                dataset_id="risk:test",
                rows_read=rows,
                rows_in_scope=rows,
                rows_processed=rows,
                rows_rejected=0,
                rows_excluded=0,
                calculation_basis="typed synthetic records",
                observations_produced=1,
            ),
        ),
    )


def test_unavailable_output_cannot_be_promoted_by_receipt_metadata() -> None:
    result = evaluate_check(
        CHECK, [_output(status=AnalysisStatus.UNAVAILABLE)], CATALOG, "c" * 64, attempt_id="A-1"
    )
    assert result.status is CheckStatus.UNRESOLVED
    assert "unusable_analysis:risk_analysis:unavailable" in result.limitations


def test_manifest_hash_mismatch_and_successful_zero_population_are_rejected() -> None:
    mismatch = evaluate_check(
        CHECK,
        [_output(status=AnalysisStatus.SUCCEEDED, sha256="d" * 64)],
        CATALOG,
        "c" * 64,
        attempt_id="A-1",
    )
    zero = evaluate_check(
        CHECK,
        [_output(status=AnalysisStatus.SUCCEEDED, rows=0)],
        CATALOG,
        "c" * 64,
        attempt_id="A-2",
    )
    assert mismatch.status is CheckStatus.UNRESOLVED
    assert zero.status is CheckStatus.UNRESOLVED


def test_material_exception_does_not_make_execution_incomplete() -> None:
    result = evaluate_check(
        CHECK, [_output(status=AnalysisStatus.SUCCEEDED)], CATALOG, "c" * 64, attempt_id="A-1"
    )
    assert result.status is CheckStatus.PERFORMED
    assert result.completion_rule_passed
