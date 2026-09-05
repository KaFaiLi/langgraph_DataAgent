"""Fail-closed completion gate for sources and planned checks."""

from __future__ import annotations

from pathlib import Path

from langchain_core.runnables.config import RunnableConfig
from pydantic import ValidationError

from data_agent.review.domain.plan import CheckApplicability, ReviewPlan
from data_agent.review.domain.source import SourceManifest
from data_agent.review.domain.verification import CheckCoverageRecord
from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.orchestration.state import ParentState


def coverage_gate(state: ParentState, config: RunnableConfig) -> dict:
    """Accept only unique, correctly owned results satisfying their plan contract."""
    pending = [entry for entry in state.get("coverage", []) if entry["status"] == "pending"]
    if pending:
        ids = ", ".join(sorted(entry["source_id"] for entry in pending))
        return {
            "status": "failed",
            "failure_reason": f"coverage gate failed: {len(pending)} source(s) unreviewed: {ids}",
        }
    if not state.get("review_plan"):
        return {
            "status": "failed",
            "failure_reason": (
                "coverage gate failed: workflow upgrade requires restart; legacy checkpoint "
                "has no review plan"
            ),
        }
    try:
        plan = ReviewPlan.model_validate(state["review_plan"])
        manifest = SourceManifest.model_validate(state["manifest"])
    except (ValidationError, KeyError) as exc:
        return {
            "status": "failed",
            "failure_reason": f"coverage gate failed: invalid review plan: {exc}",
        }
    fingerprint = state.get("review_plan_fingerprint", "")
    if fingerprint != plan.fingerprint:
        return {
            "status": "failed",
            "failure_reason": "coverage gate failed: plan fingerprint mismatch",
        }

    records: dict[str, CheckCoverageRecord] = {}
    duplicates: set[str] = set()
    for owner, report in state.get("specialist_reports", {}).items():
        for raw in report.get("check_coverage", []):
            record = CheckCoverageRecord.model_validate(raw)
            if record.check_id in records:
                duplicates.add(record.check_id)
            records[record.check_id] = record
            if record.owner_domain != owner:
                return {
                    "status": "failed",
                    "failure_reason": f"coverage gate failed: {record.check_id} has unexpected owner {owner}",
                }
    if duplicates:
        return {
            "status": "failed",
            "failure_reason": "coverage gate failed: duplicate check results: "
            + ", ".join(sorted(duplicates)),
        }

    validator = EvidenceValidator.source_backed(Path(state.get("source_root", ".")), manifest)
    failures: list[str] = []
    for check in plan.checks:
        if check.applicability is not CheckApplicability.APPLICABLE:
            continue
        record = records.get(check.check_id)
        if record is None:
            failures.append(f"{check.check_id}: result missing")
            continue
        receipt_names = [receipt.get("analysis_name", "") for receipt in record.analysis_receipts]
        required = set(check.analysis_names)
        receipts_complete = required == set(receipt_names) and len(receipt_names) == len(required)
        population_matches = (
            record.source_ids == check.source_ids
            and record.population_start == plan.review_period.start.isoformat()
            and record.population_end == plan.review_period.end.isoformat()
        )
        evidence_valid = all(
            validator.validate(reference.locator).valid for reference in record.evidence
        )
        if not (
            record.plan_fingerprint == fingerprint
            and record.owner_domain == check.domain.value
            and record.performed
            and record.completion_rule_passed
            and receipts_complete
            and population_matches
            and evidence_valid
        ):
            failures.append(f"{check.check_id}: execution contract not satisfied")
    if failures:
        return {
            "status": "failed",
            "failure_reason": "coverage gate failed: " + "; ".join(failures),
        }
    return {}
