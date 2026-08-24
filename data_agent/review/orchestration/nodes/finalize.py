"""Finalize: write final_findings.md + the run manifest, mark the run completed."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.runnables.config import RunnableConfig

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

    output_dir = Path(state["output_dir"])
    (output_dir / "final_findings.md").write_text(markdown, encoding="utf-8")
    (output_dir / "final_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
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
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(run.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    return {"status": "completed", "final_markdown": markdown}
