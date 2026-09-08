"""Fail-closed completion gate for sources and planned checks."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from langchain_core.runnables.config import RunnableConfig
from pydantic import ValidationError

from data_agent.review.completion import evaluate_check
from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.plan import CheckApplicability, CheckResult, ReviewPlan
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
    raw_ids = [
        str(raw.get("check_id", ""))
        for report in state.get("specialist_reports", {}).values()
        for raw in report.get("check_coverage", [])
    ]
    duplicates = {check_id for check_id, count in Counter(raw_ids).items() if count > 1}
    if duplicates:
        return {
            "status": "failed",
            "failure_reason": "coverage gate failed: duplicate check results: "
            + ", ".join(sorted(duplicates)),
        }
    for owner, report in state.get("specialist_reports", {}).items():
        for raw in report.get("check_coverage", []):
            check_id = str(raw.get("check_id", ""))
            if raw.get("owner_domain") != owner:
                return {
                    "status": "failed",
                    "failure_reason": f"coverage gate failed: {check_id} has unexpected owner {owner}",
                }
            try:
                records[check_id] = CheckCoverageRecord.model_validate(raw)
            except ValidationError as exc:
                return {
                    "status": "failed",
                    "failure_reason": f"coverage gate failed: invalid result for {check_id}: {exc}",
                }
    unknown_results = sorted(set(records) - {check.check_id for check in plan.checks})
    if unknown_results:
        return {
            "status": "failed",
            "failure_reason": "coverage gate failed: unknown check results: "
            + ", ".join(unknown_results),
        }
    outputs_by_owner: dict[str, list[AnalysisResult]] = {}
    authoritative_results: dict[str, CheckResult] = {}
    for outcome in state.get("specialist_outcomes", []):
        owner = str(outcome.get("domain", ""))
        raw_outputs = (outcome.get("verification") or {}).get("analysis_outputs", [])
        raw_results = (outcome.get("verification") or {}).get("check_results", {})
        try:
            outputs_by_owner.setdefault(owner, []).extend(
                AnalysisResult.model_validate(output) for output in raw_outputs
            )
            for check_id, raw_result in raw_results.items():
                if check_id in authoritative_results:
                    raise ValueError(f"duplicate authoritative result {check_id}")
                authoritative_results[check_id] = CheckResult.model_validate(raw_result)
        except (ValidationError, ValueError) as exc:
            return {
                "status": "failed",
                "failure_reason": f"coverage gate failed: invalid saved analysis output: {exc}",
            }
    declared_outputs = {
        (check.domain.value, analysis_name)
        for check in plan.checks
        for analysis_name in check.analysis_names
    }
    unexpected_outputs = sorted(
        (owner, output.name)
        for owner, outputs in outputs_by_owner.items()
        for output in outputs
        if (owner, output.name) not in declared_outputs
    )
    if unexpected_outputs:
        names = ", ".join(f"{owner}:{name}" for owner, name in unexpected_outputs)
        return {
            "status": "failed",
            "failure_reason": f"coverage gate failed: unexpected analysis outputs: {names}",
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
        evaluated = evaluate_check(
            check,
            outputs_by_owner.get(check.domain.value, []),
            manifest,
            fingerprint,
            attempt_id=f"gate:{check.check_id}",
        )
        receipts_match = [receipt.model_dump(mode="json") for receipt in evaluated.receipts] == [
            receipt.model_dump(mode="json") for receipt in record.analysis_receipts
        ]
        authoritative = authoritative_results.get(check.check_id)
        authoritative_matches = (
            authoritative is not None
            and authoritative.model_copy(update={"attempt_id": evaluated.attempt_id}) == evaluated
        )
        evidence_valid = all(
            validator.validate(reference.locator).valid for reference in record.evidence
        )
        if not (
            record.plan_fingerprint == fingerprint
            and record.owner_domain == check.domain.value
            and record.performed
            and record.completion_rule_passed
            and evaluated.completion_rule_passed
            and authoritative_matches
            and receipts_match
            and evidence_valid
        ):
            failures.append(f"{check.check_id}: execution contract not satisfied")
    if failures:
        return {
            "status": "failed",
            "failure_reason": "coverage gate failed: " + "; ".join(failures),
        }
    return {}
