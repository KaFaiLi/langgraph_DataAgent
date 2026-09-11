"""Scope preparation and deterministic inspection nodes for specialists."""

from __future__ import annotations

import json

from fastmcp.exceptions import ToolError
from langchain_core.runnables.config import RunnableConfig

from data_agent.review.completion import evaluate_check
from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.plan import PlannedCheck
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.state import (
    SpecialistState,
    dumps_period,
)
from data_agent.review.verification.candidates import assign_candidate_ids
from data_agent.tools.review_context import ToolContext
from data_agent.tools.tabular_tools import inspect_table


def context_from_config(config: RunnableConfig) -> ToolContext:
    """Read the assigned-source context from the graph's configurable input."""
    ctx = (config or {}).get("configurable", {}).get("tool_ctx")
    if ctx is None:
        raise RuntimeError("specialist graph requires config['configurable']['tool_ctx']")
    return ctx


def review_period_from_config(config: RunnableConfig, state: SpecialistState) -> tuple[str, str]:
    """Resolve the review period from invocation config or serialized state."""
    period = (config or {}).get("configurable", {}).get("review_period")
    if period is not None:
        serialized = dumps_period(period)
        return serialized["start"], serialized["end"]
    if state.get("review_period"):
        return state["review_period"]["start"], state["review_period"]["end"]
    raise RuntimeError("specialist graph requires a review period")


def prepare_scope(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict:
    """Initialize bounded specialist state and render its source scope."""
    start, end = review_period_from_config(config, state)
    sources = ", ".join(state.get("source_paths", []))
    return {
        "scope": (
            f"{runtime.spec.domain_label} review of {len(state.get('source_paths', []))} "
            f"source(s) ({sources}) for the period {start} to {end}."
        ),
        "verifier_round": 0,
        "loop_status": "running",
        "error": None,
        "research_summary": "",
        "research_trace": [],
        "research_round": 0,
        "research_budget_exhausted": False,
        "candidate_dispositions": [],
        "evidence_gates": {},
        "adversarial_cases": {},
        "adversarial_trace": {},
        "adjudications": {},
        "research_mode": "initial",
        "omission_audit": None,
        "omission_rescue_used": False,
        "omission_rescue_requested": False,
        "findings_by_id": {},
        "issues_by_id": {},
        "checks_by_id": {},
        "candidates_by_id": {},
        "pending_work": [],
    }


def inspect_material(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict:
    """Build a bounded source manifest and preview for the analyst."""
    ctx = context_from_config(config)
    lines: list[str] = []
    for source in ctx.manifest.sources:
        if state.get("source_ids") and source.source_id not in state["source_ids"]:
            continue
        lines.append(
            f"SOURCE {source.source_id} | {source.path} | type={source.source_type.value} "
            f"| rows={source.row_count} | columns={source.column_names} "
            f"| date_range={source.date_range.start.isoformat() if source.date_range else None}"
            f"..{source.date_range.end.isoformat() if source.date_range else None}"
        )
    for path in state.get("source_paths", []):
        try:
            # Small files (limit registers, control logs) are shown in full so
            # the analyst can cite exact row numbers; large tables get a preview.
            inspection = inspect_table(ctx.source_root, path, preview_rows=3)
            if inspection["row_count"] <= 25 and inspection["row_count"] > 0:
                inspection = inspect_table(
                    ctx.source_root, path, preview_rows=inspection["row_count"]
                )
        except (FileNotFoundError, OSError, ValueError, ToolError):
            continue
        preview_lines = "\n".join(
            f"  row {index}: " + json.dumps(row, default=str)
            for index, row in enumerate(inspection["preview"], start=1)
        )
        lines.append(
            f"PREVIEW {path} (sheet={inspection['sheet']}, "
            f"rows={inspection['row_count']}):\n{preview_lines}"
        )
    return {"material_summary": "\n".join(lines)[: runtime.max_material_chars]}


def run_deterministic_analysis(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict:
    """Execute the trusted skill runner against assigned source paths."""
    ctx = context_from_config(config)
    planned_checks = list(state.get("planned_checks", []))
    analysis_names = tuple(
        dict.fromkeys(
            name
            for check in planned_checks
            for name in PlannedCheck.model_validate(check).analysis_names
        )
    )
    if not analysis_names:
        analysis_names = runtime.spec.analysis_names
    analyses = runtime.spec.analyses_runner(
        ctx,
        list(state.get("source_paths", [])),
        analysis_names=analysis_names,
    )
    serialized: list[dict] = []
    checks_by_id: dict[str, dict] = dict(state.get("checks_by_id", {}))
    candidates_by_id: dict[str, dict] = dict(state.get("candidates_by_id", {}))
    pending_work = list(state.get("pending_work", []))
    queued_ids = {str(item.get("work_id")) for item in pending_work}
    for analysis in analyses:
        data = analysis.model_dump(mode="json")
        candidates = data.get("flag_candidates", [])
        if isinstance(candidates, list):
            data["flag_candidates"] = assign_candidate_ids(
                str(data.get("name") or "analysis"),
                [candidate for candidate in candidates if isinstance(candidate, dict)],
            )
            for candidate in data["flag_candidates"]:
                candidate_id = str(candidate["candidate_id"])
                candidates_by_id[candidate_id] = candidate
                work_id = f"account-candidate:{candidate_id}"
                if work_id not in queued_ids:
                    pending_work.append(
                        {
                            "work_id": work_id,
                            "work_type": "candidate_accounting",
                            "target_ids": [candidate_id],
                            "attempt_budget": 2,
                            "attempts": 0,
                            "status": "pending",
                        }
                    )
                    queued_ids.add(work_id)
        serialized.append(data)
    typed_outputs = [AnalysisResult.model_validate(data) for data in serialized]
    check_results_by_id: dict[str, dict] = {}
    for check_data in planned_checks:
        check = PlannedCheck.model_validate(check_data)
        result = evaluate_check(
            check,
            typed_outputs,
            ctx.manifest,
            state.get("plan_fingerprint", ""),
            attempt_id=f"{state.get('task_id', 'task')}:{check.check_id}",
        )
        check_results_by_id[check.check_id] = result.model_dump(mode="json")
        summaries = [
            f"{output.name}: {output.summary}"
            for output in typed_outputs
            if output.name in check.analysis_names
        ]
        checks_by_id[check.check_id] = {
            "check_id": check.check_id,
            "source_ids": check.source_ids,
            "check_type": check.title,
            "performed": result.completion_rule_passed,
            "population_definition": "Parser-owned populations in analysis receipts",
            "result": "\n".join(summaries)[:4_000],
            "limitations": result.limitations,
            "evidence": [],
            "issue_ids": [],
            "plan_fingerprint": result.plan_fingerprint,
            "owner_domain": result.domain.value,
            "analysis_receipts": [receipt.model_dump(mode="json") for receipt in result.receipts],
            "population_start": state["review_period"]["start"],
            "population_end": state["review_period"]["end"],
            "completion_rule_passed": result.completion_rule_passed,
        }
    return {
        "analyses": serialized,
        "checks_by_id": checks_by_id,
        "check_results_by_id": check_results_by_id,
        "candidates_by_id": candidates_by_id,
        "pending_work": pending_work,
    }


__all__ = [
    "context_from_config",
    "inspect_material",
    "prepare_scope",
    "review_period_from_config",
    "run_deterministic_analysis",
]
