"""Classify sources and create check-driven specialist review tasks."""

from __future__ import annotations

import hashlib
import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel

from data_agent.review.domain.domains import SOURCE_DOMAINS, SpecialistDomain
from data_agent.review.domain.plan import (
    AnalysisRequirement,
    CheckApplicability,
    PlannedCheck,
    ReviewPlan,
)
from data_agent.review.domain.review import ReviewTask, SourceCoverage
from data_agent.review.domain.source import DateRange, SourceManifest
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.llm.models import ModelTier
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.state import ParentState
from data_agent.skills.registry import SPECIALISTS
from data_agent.tools.source_roles import pnl_source_role, risk_metrics_source_role

REGISTERED_DOMAINS = tuple(SPECIALISTS)
_CLASSIFY_SYSTEM = "Classify trading-desk source files into these domains: " + ", ".join(
    d.value for d in SOURCE_DOMAINS
)


class ClassificationOutput(BaseModel):
    source_id: str
    domains: list[SpecialistDomain]


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


def _policy_fingerprint(registration: object) -> str:
    skill = registration.skill
    payload = {
        "instructions": skill.instructions,
        "verifier_policy": skill.verifier_policy,
        "dataset_reference": skill.dataset_reference,
        "checks": [check.model_dump(mode="json") for check in skill.checks],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _source_role(source: object) -> str | None:
    risk_role = risk_metrics_source_role(source.column_names)
    if risk_role is not None:
        return risk_role
    pnl_role = pnl_source_role(source.column_names, allow_legacy_pnl=True)
    if pnl_role is SpecialistDomain.PNL:
        return "pnl"
    if pnl_role is SpecialistDomain.PNL_ADJUSTMENTS:
        return "adjustment"
    if pnl_role is SpecialistDomain.PNL_VALIDATION:
        return "validation"
    if pnl_role is SpecialistDomain.INCOME_ATTRIBUTION:
        normalized = {
            str(column).strip().lower().replace("_", "") for column in source.column_names
        }
        return (
            "legacy_attribution"
            if {"date", "driver", "pnlmusd"} <= normalized
            else "wide_attribution"
        )
    for domain in (SpecialistDomain.POST_TRADE_CONTROLS, SpecialistDomain.RISK_COMMENTARY):
        if domain in source.candidate_domains:
            return domain.value
    return None


def _source_domain(role: str) -> SpecialistDomain:
    return {
        "pnl": SpecialistDomain.PNL,
        "adjustment": SpecialistDomain.PNL_ADJUSTMENTS,
        "validation": SpecialistDomain.PNL_VALIDATION,
        "wide_attribution": SpecialistDomain.INCOME_ATTRIBUTION,
        "legacy_attribution": SpecialistDomain.INCOME_ATTRIBUTION,
        "sgmr": SpecialistDomain.RISK_METRICS,
        "colibris": SpecialistDomain.RISK_METRICS,
        "post_trade_controls": SpecialistDomain.POST_TRADE_CONTROLS,
        "risk_commentary": SpecialistDomain.RISK_COMMENTARY,
    }[role]


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
    roles_by_source = {source.source_id: _source_role(source) for source in manifest.sources}
    for domain, registration in SPECIALISTS.items():
        domain_checks: list[PlannedCheck] = []
        policy_fingerprint = _policy_fingerprint(registration)
        for declaration in registration.skill.checks:
            all_roles = {
                role
                for analysis in declaration.analyses
                for role in (*analysis.required_roles, *analysis.supporting_roles)
            }
            required_roles = {
                role for analysis in declaration.analyses for role in analysis.required_roles
            }
            missing = sorted(
                role for role in required_roles if role not in roles_by_source.values()
            )
            matched = sorted(
                source_id for source_id, role in roles_by_source.items() if role in all_roles
            )
            if domain.value not in selected:
                applicability = CheckApplicability.INAPPLICABLE
                reason = "Playbook is not required by desk scope."
            elif not declaration.implemented:
                applicability = CheckApplicability.BLOCKED
                reason = (
                    "No trusted implementation with a compatible entity, date, currency, "
                    "unit, and inclusion basis is registered."
                )
            elif missing or not matched:
                applicability = CheckApplicability.BLOCKED
                unavailable = missing or sorted(all_roles)
                reason = f"Required source roles unavailable: {', '.join(unavailable)}."
            else:
                applicability = CheckApplicability.APPLICABLE
                reason = "Required source roles are available."
            requirements = tuple(
                AnalysisRequirement(
                    name=analysis.name,
                    required_source_ids=tuple(
                        sorted(
                            source_id
                            for source_id, role in roles_by_source.items()
                            if role in analysis.required_roles
                        )
                    ),
                    supporting_source_ids=tuple(
                        sorted(
                            source_id
                            for source_id, role in roles_by_source.items()
                            if role in analysis.supporting_roles
                        )
                    ),
                    minimum_observations=analysis.minimum_observations,
                    date_range_required=analysis.date_range_required,
                    empty_population_allowed=analysis.empty_population_allowed,
                )
                for analysis in declaration.analyses
            )
            source_domains = sorted(
                {_source_domain(role) for role in required_roles}, key=lambda item: item.value
            ) or [domain]
            check = PlannedCheck(
                check_id=declaration.check_id,
                domain=domain,
                title=declaration.title,
                playbook=registration.skill.name,
                playbook_version=f"2.0+{policy_fingerprint[:12]}",
                required_source_domains=source_domains,
                source_ids=matched,
                analysis_requirements=requirements,
                applicability=applicability,
                applicability_reason=reason,
                completion_criteria=[
                    "Every declared analysis satisfies its source and population contract."
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
