"""Registry of validated skill-backed review specialists."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from data_agent.review.llm import ReviewLLMProvider

from data_agent.review.domain.domains import (
    SOURCE_DOMAINS,
    SPECIALIST_DOMAINS,
    SpecialistDomain,
)
from data_agent.skills.review import SkillDefinition, discover_skills


@dataclass(frozen=True)
class SpecialistRegistration:
    """Validated identity and skill definition for one specialist."""

    domain: SpecialistDomain
    source_domains: tuple[SpecialistDomain, ...]
    report_id: str
    label: str
    description: str
    skill: SkillDefinition


@cache
def _build_registry() -> dict[SpecialistDomain, SpecialistRegistration]:
    registrations = {
        definition.domain: SpecialistRegistration(
            domain=definition.domain,
            source_domains=definition.source_domains,
            report_id=definition.report_id,
            label=definition.label,
            description=definition.description,
            skill=definition,
        )
        for definition in discover_skills()
    }
    missing = [domain.value for domain in SPECIALIST_DOMAINS if domain not in registrations]
    if missing:
        raise RuntimeError(f"specialist registry is missing skill definitions: {missing}")
    return {domain: registrations[domain] for domain in SPECIALIST_DOMAINS}


class _LazyMapping(Mapping):
    """Compatibility mapping that discovers trusted resources only on access."""

    def __init__(self, factory):
        self._factory = factory

    def __getitem__(self, key):
        return self._factory()[key]

    def __iter__(self) -> Iterator:
        return iter(self._factory())

    def __len__(self) -> int:
        return len(self._factory())


SPECIALISTS = _LazyMapping(_build_registry)


@cache
def _build_source_domain_owners() -> dict[SpecialistDomain, SpecialistDomain]:
    owners: dict[SpecialistDomain, SpecialistDomain] = {}
    for registration in SPECIALISTS.values():
        for source_domain in registration.source_domains:
            previous = owners.get(source_domain)
            if previous is not None:
                raise RuntimeError(
                    f"source domain {source_domain.value!r} is owned by both "
                    f"{previous.value!r} and {registration.domain.value!r}"
                )
            owners[source_domain] = registration.domain
    missing = [domain.value for domain in SOURCE_DOMAINS if domain not in owners]
    if missing:
        raise RuntimeError(f"specialist registry has unowned source domains: {missing}")
    return {domain: owners[domain] for domain in SOURCE_DOMAINS}


SOURCE_DOMAIN_OWNERS = _LazyMapping(_build_source_domain_owners)


def get_specialist(domain: SpecialistDomain) -> SpecialistRegistration:
    return SPECIALISTS[domain]


def specialist_domain_for(source_domain: SpecialistDomain) -> SpecialistDomain:
    return SOURCE_DOMAIN_OWNERS[source_domain]


def build_specialist(
    domain: SpecialistDomain,
    llm_provider: ReviewLLMProvider | None = None,
) -> CompiledStateGraph:
    from data_agent.skills.runtime import build_skill_graph

    return build_skill_graph(SPECIALISTS[domain].skill, llm_provider=llm_provider)
