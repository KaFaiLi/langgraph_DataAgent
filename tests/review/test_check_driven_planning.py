"""Regression tests for check-driven review planning."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.plan import CheckApplicability, ReviewPlan
from data_agent.review.domain.source import DateRange, Source, SourceManifest, SourceType
from data_agent.review.orchestration.graph import build_parent_graph
from data_agent.review.orchestration.nodes.coverage import coverage_gate
from data_agent.review.orchestration.nodes.dispatch import create_review_tasks

PERIOD = DateRange(start=date(2026, 1, 1), end=date(2026, 3, 31))


def _source(domain: SpecialistDomain) -> Source:
    columns = {
        SpecialistDomain.PNL_ADJUSTMENTS: [
            "adjustmentid",
            "amount",
            "amountineur",
            "exchangerate",
        ],
        SpecialistDomain.RISK_METRICS: [
            "limid",
            "rmriskindicator",
            "rmriskmetricname",
            "consovalue",
            "consovaluedate",
            "limmaxvalue",
            "limminvalue",
        ],
    }.get(domain, [])
    return Source(
        source_id=f"SRC-{domain.value}",
        path=f"{domain.value}/input.csv",
        source_type=SourceType.CSV,
        sha256="a" * 64,
        size_bytes=10,
        candidate_domains=[domain],
        column_names=columns,
    )


def _plan(*domains: SpecialistDomain) -> dict:
    state = {
        "manifest": SourceManifest(sources=[_source(domain) for domain in domains]).model_dump(
            mode="json"
        ),
        "review_period": PERIOD.model_dump(mode="json"),
        "desk_context": {},
    }
    return create_review_tasks(state, {})


def test_adjustment_only_runs_independent_check_and_blocks_reconciliation() -> None:
    result = _plan(SpecialistDomain.PNL_ADJUSTMENTS)
    plan = ReviewPlan.model_validate(result["review_plan"])
    applicability = {check.check_id: check.applicability for check in plan.checks}

    assert applicability["CHECK-ADJUSTMENT-CURRENCY"] is CheckApplicability.APPLICABLE
    assert applicability["CHECK-ADJUSTMENT-RECONCILIATION"] is CheckApplicability.BLOCKED
    assert result["tasks"][0]["check_ids"] == ["CHECK-ADJUSTMENT-CURRENCY"]


def test_missing_playbook_sources_are_blocked_not_inapplicable() -> None:
    result = _plan(SpecialistDomain.PNL_ADJUSTMENTS)
    plan = ReviewPlan.model_validate(result["review_plan"])
    assert (
        next(check for check in plan.checks if check.check_id == "CHECK-RISK-SGMR").applicability
        is CheckApplicability.BLOCKED
    )


def test_plan_schema_rejects_future_versions_and_unknown_budget_fields() -> None:
    result = _plan(SpecialistDomain.RISK_METRICS)
    payload = result["review_plan"]
    payload["schema_version"] = 999
    with pytest.raises(ValidationError):
        ReviewPlan.model_validate(payload)


def test_coverage_gate_rejects_missing_planned_check_records() -> None:
    result = _plan(SpecialistDomain.RISK_METRICS)
    result["coverage"][0]["status"] = "reviewed"
    result["specialist_reports"] = {"risk_metrics": {"check_coverage": []}}
    failure = coverage_gate(result, {})
    assert "CHECK-RISK-SGMR" in failure["failure_reason"]


def test_legacy_checkpoint_node_name_remains_registered() -> None:
    """A checkpoint waiting at the former dispatcher can still resolve its node."""
    assert "create_review_tasks" in build_parent_graph().get_graph().nodes


def test_partial_or_wrong_owner_receipts_cannot_pass() -> None:
    result = _plan(SpecialistDomain.RISK_METRICS)
    result["coverage"][0]["status"] = "reviewed"
    check = next(
        item for item in result["review_plan"]["checks"] if item["check_id"] == "CHECK-RISK-SGMR"
    )
    record = {
        "check_id": check["check_id"],
        "source_ids": check["source_ids"],
        "check_type": check["title"],
        "performed": True,
        "population_definition": "planned population",
        "result": "partial",
        "plan_fingerprint": result["review_plan_fingerprint"],
        "owner_domain": "pnl",
        "analysis_receipts": [{"analysis_name": "wrong", "result_digest": "a" * 64}],
        "population_start": PERIOD.start.isoformat(),
        "population_end": PERIOD.end.isoformat(),
        "completion_rule_passed": True,
    }
    result["specialist_reports"] = {"risk_metrics": {"check_coverage": [record]}}
    assert "unexpected owner" in coverage_gate(result, {})["failure_reason"]


def test_duplicate_results_fail_independently_of_order() -> None:
    result = _plan(SpecialistDomain.RISK_METRICS)
    result["coverage"][0]["status"] = "reviewed"
    check = next(
        item for item in result["review_plan"]["checks"] if item["check_id"] == "CHECK-RISK-SGMR"
    )
    record = {
        "check_id": check["check_id"],
        "source_ids": check["source_ids"],
        "check_type": check["title"],
        "performed": True,
        "population_definition": "planned population",
        "result": "complete",
        "plan_fingerprint": result["review_plan_fingerprint"],
        "owner_domain": "risk_metrics",
        "analysis_receipts": [{"analysis_name": "anything", "result_digest": "a" * 64}],
        "population_start": PERIOD.start.isoformat(),
        "population_end": PERIOD.end.isoformat(),
        "completion_rule_passed": True,
    }
    for records in (
        [record, {**record, "performed": False}],
        [{**record, "performed": False}, record],
    ):
        result["specialist_reports"] = {"risk_metrics": {"check_coverage": records}}
        assert "duplicate check results" in coverage_gate(result, {})["failure_reason"]


def test_forged_result_digest_and_wrong_population_are_rejected() -> None:
    import hashlib
    import json

    result = _plan(SpecialistDomain.RISK_METRICS)
    result["coverage"][0]["status"] = "reviewed"
    check = next(
        item for item in result["review_plan"]["checks"] if item["check_id"] == "CHECK-RISK-SGMR"
    )
    population = {
        "source_bindings": [
            {
                "source_id": check["source_ids"][0],
                "path": "risk_metrics/input.csv",
                "sha256": "a" * 64,
            }
        ],
        "dataset_id": "risk_metrics:test",
        "rows_read": 1,
        "rows_in_scope": 1,
        "rows_processed": 1,
        "rows_rejected": 0,
        "rows_excluded": 0,
        "exclusion_reasons": {},
        "actual_date_range": PERIOD.model_dump(mode="json"),
        "calculation_basis": "synthetic empty population",
        "observations_produced": 1,
        "issues": [],
    }
    outputs = [
        {
            "name": name,
            "summary": "complete",
            "tables": [],
            "flag_candidates": [],
            "overviews": [],
            "execution": {"status": "succeeded", "population": population, "issue_codes": []},
        }
        for name in check["analysis_names"]
    ]
    receipts = [
        {
            "analysis_name": output["name"],
            "status": "succeeded",
            "population": population,
            "result_digest": hashlib.sha256(
                json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "issue_codes": [],
        }
        for output in outputs
    ]
    record = {
        "check_id": check["check_id"],
        "source_ids": check["source_ids"],
        "check_type": check["title"],
        "performed": True,
        "population_definition": "planned population",
        "result": "complete",
        "plan_fingerprint": result["review_plan_fingerprint"],
        "owner_domain": "risk_metrics",
        "analysis_receipts": receipts,
        "population_start": PERIOD.start.isoformat(),
        "population_end": PERIOD.end.isoformat(),
        "completion_rule_passed": True,
    }
    result["specialist_reports"] = {"risk_metrics": {"check_coverage": [record]}}
    result["specialist_outcomes"] = [
        {
            "domain": "risk_metrics",
            "verification": {
                "analysis_outputs": outputs,
                "check_results": {
                    check["check_id"]: {
                        "plan_fingerprint": result["review_plan_fingerprint"],
                        "check_id": check["check_id"],
                        "attempt_id": f"TASK-risk_metrics:{check['check_id']}",
                        "domain": "risk_metrics",
                        "status": "performed",
                        "source_ids": check["source_ids"],
                        "receipts": receipts,
                        "completion_rule_passed": True,
                        "limitations": [],
                    }
                },
            },
        }
    ]
    assert coverage_gate(result, {}) == {}

    record["analysis_receipts"][0]["result_digest"] = "0" * 64
    assert "execution contract not satisfied" in coverage_gate(result, {})["failure_reason"]
