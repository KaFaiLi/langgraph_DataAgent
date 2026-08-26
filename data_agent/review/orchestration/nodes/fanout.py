"""Fan-out: run every specialist task and record the coverage gate inputs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.reports import SpecialistReport
from data_agent.review.domain.source import SourceManifest
from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.orchestration.finding_policy import sanitize_finding_references
from data_agent.review.orchestration.state import ParentState
from data_agent.skills.registry import build_specialist, get_specialist
from data_agent.tools.review_context import ToolContext


def _sanitize_verification_collection(
    items: list[dict[str, Any]], validator: EvidenceValidator
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sanitized: list[dict[str, Any]] = []
    citation_failures: list[dict[str, Any]] = []
    for item in items:
        finding = Finding.model_validate(item)
        clean, failures = sanitize_finding_references(finding, validator)
        sanitized.append(clean.model_dump(mode="json"))
        citation_failures.extend(
            {
                "finding_id": finding.finding_id,
                "locator": failure.locator,
                "disposition": failure.disposition.value,
                "code": failure.code.value if failure.code is not None else None,
                "reason": failure.reason,
            }
            for failure in failures
        )
    return sanitized, citation_failures


@dataclass(frozen=True)
class _SpecialistOutcome:
    """One worker's isolated result, merged by the coordinator in task order."""

    domain: SpecialistDomain
    source_ids: list[str]
    report: dict[str, Any] | None = None
    markdown: str = ""
    verification: dict[str, Any] | None = None
    research_trace: list[dict[str, Any]] | None = None
    adversarial_trace: dict[str, list[dict[str, Any]]] | None = None
    failure_reason: str | None = None


def _atomic_write(path: Path, content: str) -> None:
    """Replace one specialist artifact without exposing a partial file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _persist_specialist_outcome(output_dir: Path, outcome: _SpecialistOutcome) -> None:
    """Persist one successful branch before other parallel branches are merged."""

    assert outcome.report is not None
    assert outcome.verification is not None
    assert outcome.research_trace is not None
    assert outcome.adversarial_trace is not None
    directory = output_dir / "specialists"
    stem = outcome.domain.value
    artifacts = {
        directory / f"{stem}.md": outcome.markdown,
        directory / f"{stem}.json": json.dumps(outcome.report, indent=2, default=str),
        directory / f"{stem}.verification.json": json.dumps(
            outcome.verification, indent=2, default=str
        ),
        directory / f"{stem}.research_trace.json": json.dumps(
            outcome.research_trace, indent=2, default=str
        ),
        directory / f"{stem}.adversarial_trace.json": json.dumps(
            outcome.adversarial_trace, indent=2, default=str
        ),
    }
    for path, content in artifacts.items():
        _atomic_write(path, content)


def _provider(config: RunnableConfig) -> ReviewLLMProvider:
    provider = (config or {}).get("configurable", {}).get("llm_provider")
    if provider is None:
        return DEFAULT_LLM_PROVIDER
    return provider


def _update_coverage(
    coverage: list[dict], domain: SpecialistDomain, source_ids: list[str]
) -> list[dict]:
    for entry in coverage:
        if entry["source_id"] not in source_ids:
            continue
        if domain.value not in entry["completed_reviewers"]:
            entry["completed_reviewers"].append(domain.value)
        if set(entry["completed_reviewers"]) >= set(entry["required_reviewers"]):
            entry["status"] = "reviewed"
    return coverage


def _specialist_config(
    config: RunnableConfig, ctx: ToolContext, domain: SpecialistDomain
) -> RunnableConfig:
    """Build a child config that preserves callbacks across worker threads."""
    child_config: RunnableConfig = {
        "configurable": {"tool_ctx": ctx},
        "metadata": {
            **(config or {}).get("metadata", {}),
            "risk_agent_graph": f"specialist:{domain.value}",
            "risk_agent_specialist": domain.value,
        },
    }
    callbacks = (config or {}).get("callbacks")
    if callbacks is not None:
        child_config["callbacks"] = callbacks
    tags = (config or {}).get("tags")
    if tags is not None:
        child_config["tags"] = tags
    recursion_limit = (config or {}).get("recursion_limit")
    if recursion_limit is not None:
        child_config["recursion_limit"] = recursion_limit
    return child_config


def _run_specialist(
    task_data: dict,
    *,
    provider: ReviewLLMProvider,
    manifest: SourceManifest,
    ctx: ToolContext,
    state: ParentState,
    config: RunnableConfig,
) -> _SpecialistOutcome:
    """Invoke one specialist without mutating shared parent state or artifacts."""
    domain = SpecialistDomain(task_data["domain"])
    registration = get_specialist(domain)
    source_ids = list(task_data["source_ids"])
    try:
        source_paths = [manifest.by_id(source_id).path for source_id in source_ids]
        initial: dict = {
            "task_id": task_data["task_id"],
            "domain": domain.value,
            "report_id": registration.report_id,
            "domain_label": registration.label,
            "source_ids": source_ids,
            "source_paths": source_paths,
            "desk_context": state.get("desk_context", {}),
            "review_period": state.get("review_period", {}),
        }
        graph = build_specialist(domain, provider)
        result = graph.invoke(initial, config=_specialist_config(config, ctx, domain))
        report_data = result.get("report")
        markdown = result.get("markdown", "")
        if not report_data or not markdown:
            return _SpecialistOutcome(
                domain=domain,
                source_ids=source_ids,
                failure_reason=f"specialist {domain.value} produced no report",
            )
        report = SpecialistReport.model_validate(report_data)
        validator = EvidenceValidator.source_backed(ctx.source_root, ctx.manifest)
        verification: dict[str, Any] = {"verifier_round": result.get("verifier_round", 0)}
        for artifact_key in (
            "evidence_gates",
            "adversarial_cases",
            "adjudications",
            "adversarial_errors",
            "omission_audit",
            "candidate_dispositions",
            "omission_rescue_used",
            "research_mode",
        ):
            verification[artifact_key] = result.get(artifact_key, {})
        citation_failures: list[dict[str, Any]] = []
        for collection in (
            "initial_candidates",
            "verified_findings",
            "rejected_findings",
            "unresolved_findings",
        ):
            clean, failures = _sanitize_verification_collection(
                list(result.get(collection, [])), validator
            )
            verification[collection] = clean
            citation_failures.extend({"collection": collection, **failure} for failure in failures)
        verification["citation_failures"] = citation_failures
        return _SpecialistOutcome(
            domain=domain,
            source_ids=source_ids,
            report=report.model_dump(mode="json"),
            markdown=markdown,
            verification=verification,
            research_trace=list(result.get("research_trace", [])),
            adversarial_trace={
                str(finding_id): list(trace)
                for finding_id, trace in result.get("adversarial_trace", {}).items()
            },
        )
    except Exception as exc:  # noqa: BLE001 - explicit run failure
        return _SpecialistOutcome(
            domain=domain,
            source_ids=source_ids,
            failure_reason=(f"specialist {domain.value} failed: {type(exc).__name__}: {exc}"),
        )


def run_specialist_task(state: ParentState, config: RunnableConfig) -> dict:
    """Execute one LangGraph Send branch and return a reducer-friendly outcome."""
    task = state["active_task"]
    provider = _provider(config)
    manifest = SourceManifest.model_validate(state["manifest"])
    output_dir = Path(state["output_dir"])
    ctx = ToolContext(
        source_root=Path(state["source_root"]),
        workspace_root=output_dir / "workspace",
        manifest=manifest,
    )
    outcome = _run_specialist(
        task,
        provider=provider,
        manifest=manifest,
        ctx=ctx,
        state=state,
        config=config,
    )
    if outcome.failure_reason is None:
        _persist_specialist_outcome(output_dir, outcome)
    return {
        "specialist_outcomes": [
            {
                "domain": outcome.domain.value,
                "source_ids": outcome.source_ids,
                "report": outcome.report,
                "markdown": outcome.markdown,
                "verification": outcome.verification,
                "research_trace": outcome.research_trace,
                "adversarial_trace": outcome.adversarial_trace,
                "failure_reason": outcome.failure_reason,
            }
        ]
    }


def merge_specialist_outcomes(state: ParentState, config: RunnableConfig) -> dict:
    """Merge parallel Send branches in deterministic review-task order."""
    order = {task["domain"]: index for index, task in enumerate(state.get("tasks", []))}
    raw = sorted(
        state.get("specialist_outcomes", []),
        key=lambda item: order.get(item["domain"], len(order)),
    )
    outcomes = [
        _SpecialistOutcome(
            domain=SpecialistDomain(item["domain"]),
            source_ids=list(item["source_ids"]),
            report=item.get("report"),
            markdown=item.get("markdown", ""),
            verification=item.get("verification"),
            research_trace=item.get("research_trace"),
            adversarial_trace=item.get("adversarial_trace"),
            failure_reason=item.get("failure_reason"),
        )
        for item in raw
    ]
    return _merge_outcomes(state, outcomes)


def _merge_outcomes(state: ParentState, outcomes: list[_SpecialistOutcome]) -> dict:
    reports: dict[str, dict] = dict(state.get("specialist_reports", {}))
    markdowns: dict[str, str] = dict(state.get("specialist_markdown", {}))
    coverage: list[dict] = [dict(entry) for entry in state.get("coverage", [])]
    failure = next((outcome.failure_reason for outcome in outcomes if outcome.failure_reason), None)
    if failure is not None:
        return {"status": "failed", "failure_reason": failure}

    for outcome in outcomes:
        assert outcome.report is not None
        assert outcome.verification is not None
        assert outcome.research_trace is not None
        assert outcome.adversarial_trace is not None
        domain = outcome.domain
        reports[domain.value] = outcome.report
        markdowns[domain.value] = outcome.markdown

        coverage = _update_coverage(coverage, domain, outcome.source_ids)

    return {
        "specialist_reports": reports,
        "specialist_markdown": markdowns,
        "coverage": coverage,
    }
