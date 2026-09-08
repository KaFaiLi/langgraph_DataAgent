"""Finalize: write final_findings.md + the run manifest, mark the run completed."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.plan import CheckApplicability, ReviewPlan
from data_agent.review.domain.reports import FinalReport
from data_agent.review.domain.review import (
    ReviewRun,
    ReviewTask,
    RunStatus,
    SourceCoverage,
)
from data_agent.review.domain.source import SourceManifest
from data_agent.review.orchestration.state import ParentState
from data_agent.review.reporting.markdown import render_final_report
from data_agent.review.synthesis.lead_verifier import (
    FatalEvidenceIntegrityError,
    validate_final_report,
)


def _atomic_write(path: Path, content: str) -> None:
    """Publish one validated final artifact without exposing partial content."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def finalize(state: ParentState, config: RunnableConfig) -> dict:
    """Persist final_findings.md and the run manifest; set status completed."""
    report_data = state.get("final_report")
    if not report_data:
        return {"status": "failed", "failure_reason": "no final report to finalize"}
    report = FinalReport.model_validate(report_data)
    try:
        evidence_failures = validate_final_report(state, report)
    except FatalEvidenceIntegrityError as exc:
        return {"status": "failed", "failure_reason": str(exc)}
    if evidence_failures:
        return {
            "status": "failed",
            "failure_reason": "final report evidence validation failed: "
            + "\n".join(evidence_failures),
        }
    markdown = render_final_report(report)
    plan = ReviewPlan.model_validate(state["review_plan"])
    blocked = [check for check in plan.checks if check.applicability is CheckApplicability.BLOCKED]
    if blocked:
        markdown += "\n\n## Review limitations\n\n" + "\n".join(
            f"- **{check.check_id} — {check.title}:** {check.applicability_reason}"
            for check in blocked
        )

    output_dir = Path(state["output_dir"])
    _atomic_write(output_dir / "final_findings.md", markdown)
    _atomic_write(
        output_dir / "final_report.json",
        json.dumps(report.model_dump(mode="json"), indent=2, default=str),
    )
    _atomic_write(
        output_dir / "lead_verification.json",
        json.dumps(
            {
                "lead_round": int(state.get("lead_round", 0)),
                "history": list(state.get("lead_verification_history", [])),
            },
            indent=2,
            default=str,
        ),
    )
    check_results = [
        check
        for specialist in state.get("specialist_reports", {}).values()
        for check in specialist.get("check_coverage", [])
    ]
    _atomic_write(
        output_dir / "review_plan.json",
        json.dumps(
            {
                "plan": plan.model_dump(mode="json"),
                "fingerprint": state["review_plan_fingerprint"],
                "check_results": check_results,
            },
            indent=2,
        ),
    )

    manifest = SourceManifest.model_validate(state["manifest"])
    coverage = [SourceCoverage.model_validate(entry) for entry in state.get("coverage", [])]
    tasks = [ReviewTask.model_validate(task) for task in state.get("tasks", [])]
    run = ReviewRun(
        run_id=state.get("run_id", "RUN-UNKNOWN"),
        status=RunStatus.COMPLETED,
        created_at=datetime.now(UTC),
        source_root=state["source_root"],
        output_dir=state["output_dir"],
        manifest=manifest,
        coverage=coverage,
        tasks=tasks,
        review_plan=plan.model_dump(mode="json"),
        review_plan_fingerprint=state["review_plan_fingerprint"],
        check_results=check_results,
    )
    # Publish the run manifest last: its presence seals the preceding artifacts.
    _atomic_write(
        output_dir / "run_manifest.json",
        json.dumps(run.model_dump(mode="json"), indent=2, default=str),
    )
    return {"status": "completed", "final_markdown": markdown}
