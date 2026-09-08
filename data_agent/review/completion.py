"""One deterministic authority for planned-check completion."""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from data_agent.review.domain.analysis import AnalysisResult, AnalysisStatus
from data_agent.review.domain.plan import (
    AnalysisReceipt,
    CheckResult,
    CheckStatus,
    PlannedCheck,
)
from data_agent.review.domain.source import SourceManifest


def _digest(output: AnalysisResult) -> str:
    payload = json.dumps(output.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def evaluate_check(
    planned_check: PlannedCheck,
    outputs: list[AnalysisResult],
    catalog: SourceManifest,
    plan_fingerprint: str,
    *,
    attempt_id: str,
) -> CheckResult:
    """Evaluate execution facts without trusting report or model-authored status fields."""
    selected = [output for output in outputs if output.name in planned_check.analysis_names]
    counts = Counter(output.name for output in selected)
    issues: list[str] = []
    required = set(planned_check.analysis_names)
    if set(counts) != required:
        issues.append("required_analysis_set_mismatch")
    if any(count != 1 for count in counts.values()):
        issues.append("duplicate_analysis_output")

    receipts: list[AnalysisReceipt] = []
    for output in selected:
        execution = output.execution
        if execution is None:
            issues.append(f"missing_execution_metadata:{output.name}")
            continue
        population = execution.population
        bound_ids: set[str] = set()
        for binding in population.source_bindings:
            try:
                source = catalog.by_id(binding.source_id)
            except KeyError:
                issues.append(f"unknown_source_binding:{output.name}:{binding.source_id}")
                continue
            if source.path != binding.path or source.sha256 != binding.sha256:
                issues.append(f"source_binding_mismatch:{output.name}:{binding.source_id}")
            bound_ids.add(binding.source_id)
        if not set(planned_check.source_ids) <= bound_ids:
            issues.append(f"incomplete_source_binding:{output.name}")
        if execution.status is AnalysisStatus.SUCCEEDED and population.rows_processed == 0:
            issues.append(f"successful_empty_population:{output.name}")
        if execution.status is AnalysisStatus.EMPTY and not planned_check.empty_population_allowed:
            issues.append(f"empty_population_not_allowed:{output.name}")
        if execution.status not in {AnalysisStatus.SUCCEEDED, AnalysisStatus.EMPTY}:
            issues.append(f"unusable_analysis:{output.name}:{execution.status.value}")
        if population.rows_rejected and not planned_check.partial_rejection_allowed:
            issues.append(f"rejected_population_not_allowed:{output.name}")
        receipts.append(
            AnalysisReceipt(
                analysis_name=output.name,
                status=execution.status,
                population=population,
                result_digest=_digest(output),
                issue_codes=execution.issue_codes,
            )
        )
    complete = not issues
    return CheckResult(
        plan_fingerprint=plan_fingerprint,
        check_id=planned_check.check_id,
        attempt_id=attempt_id,
        domain=planned_check.domain,
        status=CheckStatus.PERFORMED if complete else CheckStatus.UNRESOLVED,
        source_ids=planned_check.source_ids,
        receipts=receipts,
        completion_rule_passed=complete,
        limitations=issues,
    )
