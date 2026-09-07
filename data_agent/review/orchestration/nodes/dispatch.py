"""Classify sources and create check-driven specialist review tasks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel

from data_agent.review.domain.domains import SOURCE_DOMAINS, SpecialistDomain
from data_agent.review.domain.plan import CheckApplicability, PlannedCheck, ReviewPlan
from data_agent.review.domain.review import ReviewTask, SourceCoverage
from data_agent.review.domain.source import DateRange, SourceManifest
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.llm.models import ModelTier
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.state import ParentState
from data_agent.skills.registry import SPECIALISTS
from data_agent.tools.source_roles import pnl_source_role

REGISTERED_DOMAINS = tuple(SPECIALISTS)
_CLASSIFY_SYSTEM = "Classify trading-desk source files into these domains: " + ", ".join(
    d.value for d in SOURCE_DOMAINS
)


class ClassificationOutput(BaseModel):
    source_id: str
    domains: list[SpecialistDomain]


@dataclass(frozen=True)
class _CheckDefinition:
    suffix: str
    title: str
    required: tuple[SpecialistDomain, ...]
    analyses: tuple[str, ...]
    implemented: bool = True


# Independent calculations are separate checks. Cross-source checks are blocked
# without suppressing checks whose own inputs are available.
_PNL_CHECKS = (
    _CheckDefinition(
        "PNL-CUMULATIVE",
        "P&L cumulative consistency",
        (SpecialistDomain.PNL,),
        ("pnl_input_contract", "pnl_cumulative_integrity", "pnl_statistical_patterns"),
    ),
    _CheckDefinition(
        "ADJUSTMENT-CURRENCY",
        "Adjustment currency conversion",
        (SpecialistDomain.PNL_ADJUSTMENTS,),
        ("pnl_adjustment_controls",),
    ),
    _CheckDefinition(
        "ATTRIBUTION-INTERNAL-CONSISTENCY",
        "Income attribution consistency",
        (SpecialistDomain.INCOME_ATTRIBUTION,),
        (
            "income_attribution_schema",
            "income_attribution_driver_profile",
            "income_attribution_persistence",
            "income_attribution_status",
        ),
    ),
    _CheckDefinition(
        "PNL-VALIDATION-WORKFLOW",
        "P&L validation workflow consistency",
        (SpecialistDomain.PNL_VALIDATION,),
        ("pnl_validation_and_reconciliation",),
    ),
    _CheckDefinition(
        "ADJUSTMENT-RECONCILIATION",
        "Adjustment/P&L reconciliation",
        (SpecialistDomain.PNL, SpecialistDomain.PNL_ADJUSTMENTS),
        ("pnl_validation_and_reconciliation",),
    ),
    _CheckDefinition(
        "ATTRIBUTION-RECONCILIATION",
        "Attribution/P&L reconciliation",
        (SpecialistDomain.PNL, SpecialistDomain.INCOME_ATTRIBUTION),
        ("pnl_to_attribution_reconciliation",),
        implemented=False,
    ),
)

_DOMAIN_ANALYSES = {
    SpecialistDomain.RISK_METRICS: (
        "risk_metrics_input_contract",
        "risk_metrics_data_integrity",
        "risk_limit_consumption",
        "risk_metric_dynamics",
        "risk_excess_workflow",
        "risk_cross_source_consistency",
    ),
    SpecialistDomain.POST_TRADE_CONTROLS: (
        "repeated_breaches",
        "product_recurrence",
        "resolution_time",
        "approval_gaps",
        "override_patterns",
        "severity_changes",
    ),
    SpecialistDomain.RISK_COMMENTARY: (
        "commentary_extract_population",
        "commentary_validation_gaps",
        "commentary_internal_consistency",
        "commentary_repeated_explanations",
        "commentary_normalized_reassurance_claims",
    ),
}


def _provider(config: RunnableConfig) -> ReviewLLMProvider:
    return (config or {}).get("configurable", {}).get("llm_provider") or DEFAULT_LLM_PROVIDER


def _classify_source(
    provider: ReviewLLMProvider, source_id: str, path: str, columns: list[str]
) -> list[SpecialistDomain]:
    output = invoke_structured(
        provider(ModelTier.LOW_COST, ClassificationOutput),
        [
            SystemMessage(content=_CLASSIFY_SYSTEM),
            HumanMessage(content=f"source_id={source_id}\npath={path}\ncolumns={columns}"),
        ],
        schema=ClassificationOutput,
    )
    parsed = (
        output
        if isinstance(output, ClassificationOutput)
        else ClassificationOutput.model_validate(output)
    )
    return [domain for domain in parsed.domains if domain in SOURCE_DOMAINS]


def _definitions(
    domain: SpecialistDomain, source_domains: tuple[SpecialistDomain, ...]
) -> tuple[_CheckDefinition, ...]:
    if domain is SpecialistDomain.PNL:
        return _PNL_CHECKS
    return (
        _CheckDefinition(
            domain.value.upper(),
            f"{domain.value} core review",
            source_domains,
            _DOMAIN_ANALYSES[domain],
        ),
    )


def _policy_fingerprint(registration: object) -> str:
    skill = registration.skill
    payload = f"{skill.instructions}\n{skill.verifier_policy}\n{skill.dataset_reference}"
    return hashlib.sha256(payload.encode()).hexdigest()


def create_review_tasks(state: ParentState, config: RunnableConfig) -> dict:
    """Compatibility-stable graph node that classifies, plans, and dispatches checks."""
    manifest = SourceManifest.model_validate(state["manifest"])
    for source in manifest.sources:
        schema_role = pnl_source_role(source.column_names, allow_legacy_pnl=True)
        path_is_pnl_family = source.candidate_domains == [SpecialistDomain.PNL]
        if schema_role is not None:
            source.candidate_domains = [schema_role]
        elif not source.candidate_domains or path_is_pnl_family:
            domains = _classify_source(
                _provider(config), source.source_id, source.path, source.column_names
            )
            source.candidate_domains = domains

    configured = state.get("selected_review_domains")
    selected = (
        {domain.value for domain in REGISTERED_DOMAINS}
        if configured is None
        else {SpecialistDomain(domain).value for domain in configured}
    )
    checks: list[PlannedCheck] = []
    tasks: list[dict] = []
    reviewers_by_source: dict[str, list[SpecialistDomain]] = {
        source.source_id: [] for source in manifest.sources
    }
    period = DateRange.model_validate(state["review_period"])
    for domain, registration in SPECIALISTS.items():
        domain_checks: list[PlannedCheck] = []
        for definition in _definitions(domain, registration.source_domains):
            policy_fingerprint = _policy_fingerprint(registration)
            matched = sorted(
                source.source_id
                for source in manifest.sources
                if any(required in source.candidate_domains for required in definition.required)
            )
            present = {
                candidate for source in manifest.sources for candidate in source.candidate_domains
            }
            missing = [
                required.value for required in definition.required if required not in present
            ]
            analysis_names = definition.analyses
            if definition.suffix == "ATTRIBUTION-INTERNAL-CONSISTENCY" and any(
                {"driver", "pnl_musd"} <= set(source.column_names)
                for source in manifest.sources
                if source.source_id in matched
            ):
                analysis_names = (
                    "driver_concentration",
                    "unexpected_drivers",
                    "income_source_shifts",
                    "risk_consistency",
                    "risk_pnl_mismatch",
                )
            if domain.value not in selected:
                applicability, reason = (
                    CheckApplicability.INAPPLICABLE,
                    "Playbook is not required by desk scope.",
                )
            elif not definition.implemented:
                applicability, reason = (
                    CheckApplicability.BLOCKED,
                    "No trusted cross-source implementation with compatible entity, date, currency, unit, and inclusion basis is registered.",
                )
            elif missing:
                applicability, reason = (
                    CheckApplicability.BLOCKED,
                    f"Required source roles unavailable: {', '.join(missing)}.",
                )
            else:
                applicability, reason = (
                    CheckApplicability.APPLICABLE,
                    "Required source roles are available.",
                )
            check = PlannedCheck(
                check_id=f"CHECK-{definition.suffix}",
                domain=domain,
                title=definition.title,
                playbook=registration.skill.name,
                playbook_version=f"1.0+{policy_fingerprint[:12]}",
                required_source_domains=list(definition.required),
                source_ids=matched,
                analysis_names=list(analysis_names),
                applicability=applicability,
                applicability_reason=reason,
                completion_criteria=[
                    "All declared deterministic analyses are recorded with population, result, evidence, and limitations."
                ],
                policy_fingerprint=policy_fingerprint,
            )
            checks.append(check)
            if applicability is CheckApplicability.APPLICABLE:
                domain_checks.append(check)
                for source_id in matched:
                    if domain not in reviewers_by_source[source_id]:
                        reviewers_by_source[source_id].append(domain)
        if domain_checks:
            source_ids = sorted(
                {source_id for check in domain_checks for source_id in check.source_ids}
            )
            tasks.append(
                ReviewTask(
                    task_id=f"TASK-{domain.value}",
                    domain=domain,
                    source_ids=source_ids,
                    check_ids=[check.check_id for check in domain_checks],
                    scope=period,
                ).model_dump(mode="json")
            )

    identity = {
        "period": period.model_dump(mode="json"),
        "sources": sorted((source.source_id, source.sha256) for source in manifest.sources),
        "checks": [check.model_dump(mode="json") for check in checks],
    }
    plan_id = (
        "PLAN-"
        + hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())
        .hexdigest()[:16]
        .upper()
    )
    plan = ReviewPlan(plan_id=plan_id, review_period=period, checks=checks)
    coverage = [
        SourceCoverage(
            source_id=source.source_id,
            required_reviewers=[domain.value for domain in reviewers_by_source[source.source_id]],
            status=(
                "unsupported"
                if not source.candidate_domains
                else "irrelevant"
                if not reviewers_by_source[source.source_id]
                else "pending"
            ),
            notes=(
                "Source role remains unresolved."
                if not source.candidate_domains
                else "No applicable planned check."
                if not reviewers_by_source[source.source_id]
                else None
            ),
        ).model_dump(mode="json")
        for source in manifest.sources
    ]
    return {
        "manifest": manifest.model_dump(mode="json"),
        "review_plan": plan.model_dump(mode="json"),
        "review_plan_fingerprint": plan.fingerprint,
        "tasks": tasks,
        "coverage": coverage,
        "check_results": {},
    }
