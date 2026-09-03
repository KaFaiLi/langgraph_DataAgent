"""Regression tests for check-driven review planning."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.plan import CheckApplicability, ExecutionBudget, ReviewPlan
from data_agent.review.domain.source import DateRange, Source, SourceManifest, SourceType
from data_agent.review.orchestration.graph import build_parent_graph
from data_agent.review.orchestration.nodes.coverage import coverage_gate
from data_agent.review.orchestration.nodes.dispatch import create_review_tasks

PERIOD = DateRange(start=date(2026, 1, 1), end=date(2026, 3, 31))


def _source(domain: SpecialistDomain) -> Source:
    return Source(
        source_id=f"SRC-{domain.value}",
        path=f"{domain.value}/input.csv",
        source_type=SourceType.CSV,
        sha256="a" * 64,
        size_bytes=10,
        candidate_domains=[domain],
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
        next(check for check in plan.checks if check.check_id == "CHECK-RISK_METRICS").applicability
        is CheckApplicability.BLOCKED
    )


def test_plan_schema_rejects_future_versions_and_unknown_budget_fields() -> None:
    result = _plan(SpecialistDomain.RISK_METRICS)
    payload = result["review_plan"]
    payload["schema_version"] = 999
    with pytest.raises(ValidationError):
        ReviewPlan.model_validate(payload)
    with pytest.raises(ValidationError):
        ExecutionBudget.model_validate({"max_modle_calls": 5})


def test_coverage_gate_rejects_missing_planned_check_records() -> None:
    result = _plan(SpecialistDomain.RISK_METRICS)
    result["coverage"][0]["status"] = "reviewed"
    result["specialist_reports"] = {"risk_metrics": {"check_coverage": []}}
    failure = coverage_gate(result, {})
    assert "CHECK-RISK_METRICS" in failure["failure_reason"]


def test_legacy_checkpoint_node_name_remains_registered() -> None:
    """A checkpoint waiting at the former dispatcher can still resolve its node."""
    assert "create_review_tasks" in build_parent_graph().get_graph().nodes
