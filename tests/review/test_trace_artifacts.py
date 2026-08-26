from __future__ import annotations

import json

import pytest

from data_agent.review.application.run_bundle import RunBundleError, load_completed_run
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.orchestration.nodes.fanout import (
    _merge_outcomes,
    _persist_specialist_outcome,
    _SpecialistOutcome,
)
from data_agent.review.service import ReviewService


def test_modern_specialist_bundle_loads_separate_trace_artifacts(tmp_path) -> None:
    """Modern verification artifacts expose analyst/challenger traces independently."""

    # Reuse the stable archive builder from the existing run-bundle suite.
    from tests.review.ported_integration.test_run_bundle import _write_completed_run

    _write_completed_run(tmp_path)
    verification_path = tmp_path / "specialists" / "risk_metrics.verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["evidence_gates"] = {}
    verification["adversarial_cases"] = {}
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    (tmp_path / "specialists" / "risk_metrics.research_trace.json").write_text(
        json.dumps([{"tool": "inspect_table"}]), encoding="utf-8"
    )
    (tmp_path / "specialists" / "risk_metrics.adversarial_trace.json").write_text(
        json.dumps({"RISK-F-1": [{"tool": "read_rows"}]}), encoding="utf-8"
    )

    bundle = load_completed_run(tmp_path)

    assert bundle.research_trace_artifacts[next(iter(bundle.specialist_reports))]
    assert bundle.adversarial_trace_artifacts[next(iter(bundle.specialist_reports))]["RISK-F-1"]


def test_modern_specialist_bundle_rejects_missing_trace_artifact(tmp_path) -> None:
    from tests.review.ported_integration.test_run_bundle import _write_completed_run

    _write_completed_run(tmp_path)
    verification_path = tmp_path / "specialists" / "risk_metrics.verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["evidence_gates"] = {}
    verification_path.write_text(json.dumps(verification), encoding="utf-8")

    with pytest.raises(RunBundleError, match="artifact_missing"):
        load_completed_run(tmp_path)


def test_successful_specialist_artifacts_survive_another_branch_failure(tmp_path) -> None:
    success = _SpecialistOutcome(
        domain=SpecialistDomain.RISK_METRICS,
        source_ids=["SRC-1"],
        report={"domain": "risk_metrics"},
        markdown="# Risk metrics\n",
        verification={"verifier_round": 0},
        research_trace=[{"tool": "inspect_table"}],
        adversarial_trace={},
    )
    failure = _SpecialistOutcome(
        domain=SpecialistDomain.PNL,
        source_ids=["SRC-2"],
        failure_reason="specialist pnl failed",
    )
    _persist_specialist_outcome(tmp_path, success)

    result = _merge_outcomes(
        {"specialist_reports": {}, "specialist_markdown": {}, "coverage": []},
        [success, failure],
    )

    assert result["status"] == "failed"
    assert (tmp_path / "specialists" / "risk_metrics.json").is_file()
    assert (tmp_path / "specialists" / "risk_metrics.research_trace.json").is_file()
    assert ReviewService._completed_specialists(tmp_path) == ["risk_metrics"]
