"""Fail-closed completion gate for sources and planned checks."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
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
    outputs: dict[tuple[str, str], dict] = {}
    duplicate_outputs: set[tuple[str, str]] = set()
    for outcome in state.get("specialist_outcomes", []):
        owner = str(outcome.get("domain", ""))
        for output in (outcome.get("verification") or {}).get("analysis_outputs", []):
            key = (owner, str(output.get("name", "")))
            if key in outputs:
                duplicate_outputs.add(key)
            outputs[key] = output
    if duplicate_outputs:
        names = ", ".join(f"{owner}:{name}" for owner, name in sorted(duplicate_outputs))
        return {
            "status": "failed",
            "failure_reason": f"coverage gate failed: duplicate analysis outputs: {names}",
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
        receipt_names = [receipt.analysis_name for receipt in record.analysis_receipts]
        required = set(check.analysis_names)
        receipts_complete = required == set(receipt_names) and len(receipt_names) == len(required)
        receipts_valid = True
        for receipt in record.analysis_receipts:
            output = outputs.get((check.domain.value, receipt.analysis_name))
            digest = (
                hashlib.sha256(
                    json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                if output is not None
                else ""
            )
            population = receipt.population
            bound_ids = {binding.source_id for binding in population.source_bindings}
            usable_status = receipt.status.value == "succeeded" or (
                receipt.status.value == "empty" and check.empty_population_allowed
            )
            accounted = (
                population.rows_processed + population.rows_rejected + population.rows_excluded
            )
            receipts_valid = receipts_valid and (
                digest == receipt.result_digest
                and set(check.source_ids) <= bound_ids
                and usable_status
                and (population.rows_rejected == 0 or check.partial_rejection_allowed)
                and accounted >= population.rows_read
                and bool(population.calculation_basis)
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
            and receipts_valid
            and evidence_valid
        ):
            failures.append(f"{check.check_id}: execution contract not satisfied")
    if failures:
        return {
            "status": "failed",
            "failure_reason": "coverage gate failed: " + "; ".join(failures),
        }
    return {}
