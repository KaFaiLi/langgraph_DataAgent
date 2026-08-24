"""Dispatch: classify unclassified sources, create review tasks, init coverage."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel

from data_agent.review.domain.domains import SOURCE_DOMAINS, SpecialistDomain
from data_agent.review.domain.review import ReviewTask, SourceCoverage
from data_agent.review.domain.source import SourceManifest
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.llm.models import ModelTier
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.state import ParentState
from data_agent.skills.registry import SPECIALISTS, specialist_domain_for

REGISTERED_DOMAINS: tuple[SpecialistDomain, ...] = tuple(SPECIALISTS)

_CLASSIFY_SYSTEM = (
    "You classify trading-desk source files into registered review domains. "
    "Allowed domains and their review purpose: "
    + "; ".join(
        f"{domain.value} ({registration.description})"
        for domain, registration in SPECIALISTS.items()
    )
    + ". Source classifications may include: "
    + ", ".join(domain.value for domain in SOURCE_DOMAINS)
    + ". Use only the file path and its column names; assign one or more domains "
    "and never invent evidence."
)


class ClassificationOutput(BaseModel):
    """Structured classification of one source."""

    source_id: str
    domains: list[SpecialistDomain]


def _provider(config: RunnableConfig) -> ReviewLLMProvider:
    provider = (config or {}).get("configurable", {}).get("llm_provider")
    if provider is None:
        return DEFAULT_LLM_PROVIDER
    return provider


def _classify_source(
    provider: ReviewLLMProvider, source_id: str, path: str, columns: list[str]
) -> list[SpecialistDomain]:
    runnable = provider(ModelTier.LOW_COST, ClassificationOutput)
    user = (
        f"source_id={source_id}\npath={path}\ncolumns={columns}\n"
        "Which review domains does this file plausibly belong to?"
    )
    output = invoke_structured(
        runnable,
        [SystemMessage(content=_CLASSIFY_SYSTEM), HumanMessage(content=user)],
        schema=ClassificationOutput,
    )
    classification = (
        output
        if isinstance(output, ClassificationOutput)
        else ClassificationOutput.model_validate(output)
    )
    # Deterministic bounds: only allow-listed domains survive.
    return [domain for domain in classification.domains if domain in SOURCE_DOMAINS]


def create_review_tasks(state: ParentState, config: RunnableConfig) -> dict:
    """Classify unclassified sources (low-cost model), then build tasks and coverage.

    A source whose classification comes back empty is conservatively routed
    to ALL specialists - it must be reviewed by someone (spec section 19).
    """
    provider = _provider(config)
    manifest = SourceManifest.model_validate(state["manifest"])
    reviewers_by_source: dict[str, list[SpecialistDomain]] = {}

    for source in manifest.sources:
        if not source.candidate_domains:
            domains = _classify_source(
                provider, source.source_id, source.path, source.column_names
            )
            source.candidate_domains = domains or list(REGISTERED_DOMAINS)
        reviewers_by_source[source.source_id] = list(
            dict.fromkeys(
                specialist_domain_for(domain) for domain in source.candidate_domains
            )
        )

    tasks: list[dict] = []
    for domain in REGISTERED_DOMAINS:
        source_ids = [
            source.source_id
            for source in manifest.sources
            if domain in reviewers_by_source[source.source_id]
        ]
        if source_ids:
            tasks.append(
                ReviewTask(
                    task_id=f"TASK-{domain.value}",
                    domain=domain,
                    source_ids=source_ids,
                ).model_dump(mode="json")
            )

    coverage = [
        SourceCoverage(
            source_id=source.source_id,
            required_reviewers=[
                domain.value for domain in reviewers_by_source[source.source_id]
            ],
        ).model_dump(mode="json")
        for source in manifest.sources
    ]
    return {
        "manifest": manifest.model_dump(mode="json"),
        "tasks": tasks,
        "coverage": coverage,
    }
