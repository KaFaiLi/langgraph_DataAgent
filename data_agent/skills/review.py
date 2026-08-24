"""Trusted analytical-skill validation and entrypoint loading."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
import threading
from collections.abc import Callable, Sequence
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from data_agent.skills.loader import parse_skill_document
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.reports import CrossSpecialistAnalysis, SpecialistReport
from data_agent.tools.review_context import ToolContext

SPECIALIST_SKILL_KIND = "specialist-review"
LEAD_REVIEW_SKILL_KIND = "lead-review"
_ENTRYPOINT_PATTERN = re.compile(
    r"^(?P<path>[A-Za-z0-9_.\-/]+\.py):(?P<function>[A-Za-z_][A-Za-z0-9_]*)$"
)

AnalysisRunner = Callable[[ToolContext, list[str]], Sequence[BaseModel]]
LeadAnalysisRunner = Callable[[list[SpecialistReport]], CrossSpecialistAnalysis]

_MODULE_LOAD_LOCK = threading.RLock()


class SkillLoadError(ValueError):
    """Raised when a repository skill violates the trusted runtime contract."""


class SkillMetadata(BaseModel):
    """Validated runtime metadata declared by an analytical skill."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["specialist-review"]
    domain: SpecialistDomain
    source_domains: tuple[SpecialistDomain, ...] = ()
    report_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,31}$")
    label: str = Field(min_length=1, max_length=80)
    analysis_entrypoint: str = Field(min_length=1)


class SkillFrontMatter(BaseModel):
    """Supported YAML front matter for an analytical skill."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1)
    metadata: SkillMetadata


class SkillDefinition(BaseModel):
    """One fully validated specialist skill ready for generic execution."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    domain: SpecialistDomain
    source_domains: tuple[SpecialistDomain, ...]
    report_id: str
    label: str
    skill_root: Path
    skill_file: Path
    analysis_file: Path
    analysis_function: str
    instructions: str
    dataset_reference: str = ""
    verifier_policy: str

    @property
    def analyst_guidance(self) -> str:
        """Return the skill playbook plus any dataset contract for the analyst."""
        if not self.dataset_reference:
            return self.instructions
        return f"{self.instructions}\n\nDATASET REFERENCE\n{self.dataset_reference}"


class LeadReviewSkillMetadata(BaseModel):
    """Validated metadata for the singleton cross-specialist review skill."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["lead-review"]
    label: str = Field(min_length=1, max_length=80)
    analysis_entrypoint: str = Field(min_length=1)


class LeadReviewSkillFrontMatter(BaseModel):
    """Supported YAML front matter for the lead-review skill."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["lead-review"]
    description: str = Field(min_length=1)
    metadata: LeadReviewSkillMetadata


class LeadReviewSkillDefinition(BaseModel):
    """Model-facing cross-specialist policy loaded from a trusted skill."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    label: str
    skill_root: Path
    skill_file: Path
    analysis_file: Path
    analysis_function: str
    instructions: str
    verifier_policy: str


def repository_skills_root() -> Path:
    """Return the version-controlled repository ``skills/`` directory."""
    return Path(__file__).resolve().parents[2] / "skills"


def _parse_front_matter(skill_file: Path) -> tuple[dict[str, Any], str]:
    text = skill_file.read_text(encoding="utf-8")
    try:
        raw, body = parse_skill_document(text, require_frontmatter=True)
    except ValueError as exc:
        raise SkillLoadError(f"{skill_file}: {exc}") from exc
    return raw, body.strip()


def _is_analytical_front_matter(raw: dict[str, Any]) -> bool:
    metadata = raw.get("metadata")
    return isinstance(metadata, dict) and metadata.get("kind") == SPECIALIST_SKILL_KIND


def _contained_path(root: Path, relative: str, *, label: str) -> Path:
    supplied = Path(relative)
    if supplied.is_absolute() or ".." in supplied.parts:
        raise SkillLoadError(f"{label} must be a contained relative path: {relative!r}")
    candidate = (root / supplied).resolve(strict=True)
    resolved_root = root.resolve(strict=True)
    if not candidate.is_relative_to(resolved_root):
        raise SkillLoadError(f"{label} escapes the skill directory: {relative!r}")
    return candidate


def _reference_text(skill_root: Path, name: str) -> str:
    reference = skill_root / "references" / name
    if not reference.exists():
        return ""
    resolved = reference.resolve(strict=True)
    if not resolved.is_relative_to(skill_root.resolve(strict=True)):
        raise SkillLoadError(f"reference escapes the skill directory: {reference}")
    return resolved.read_text(encoding="utf-8").strip()


def load_skill(skill_file: Path, *, skills_root: Path | None = None) -> SkillDefinition:
    """Load and validate one analytical ``SKILL.md`` from the trusted skills root."""
    root = (skills_root or repository_skills_root()).resolve(strict=True)
    resolved_skill = skill_file.resolve(strict=True)
    if not resolved_skill.is_relative_to(root):
        raise SkillLoadError(f"skill file is outside the trusted skills root: {skill_file}")
    if resolved_skill.name != "SKILL.md":
        raise SkillLoadError(f"skill definition must be named SKILL.md: {skill_file}")

    raw, instructions = _parse_front_matter(resolved_skill)
    if not _is_analytical_front_matter(raw):
        raise SkillLoadError(f"not an analytical specialist skill: {skill_file}")
    try:
        front_matter = SkillFrontMatter.model_validate(raw)
    except ValidationError as exc:
        raise SkillLoadError(f"{skill_file}: invalid analytical skill metadata: {exc}") from exc
    if not instructions:
        raise SkillLoadError(f"{skill_file}: specialist instructions are required")

    source_domains = front_matter.metadata.source_domains or (
        front_matter.metadata.domain,
    )
    if front_matter.metadata.domain not in source_domains:
        raise SkillLoadError(
            f"{skill_file}: source_domains must include primary domain "
            f"{front_matter.metadata.domain.value!r}"
        )
    if len(set(source_domains)) != len(source_domains):
        raise SkillLoadError(f"{skill_file}: source_domains must be unique")

    skill_root = resolved_skill.parent
    if front_matter.name != skill_root.name:
        raise SkillLoadError(
            f"{skill_file}: skill name {front_matter.name!r} must match folder "
            f"{skill_root.name!r}"
        )
    entrypoint = _ENTRYPOINT_PATTERN.fullmatch(
        front_matter.metadata.analysis_entrypoint
    )
    if entrypoint is None:
        raise SkillLoadError(
            f"{skill_file}: invalid analysis_entrypoint "
            f"{front_matter.metadata.analysis_entrypoint!r}"
        )
    analysis_file = _contained_path(
        skill_root, entrypoint.group("path"), label="analysis_entrypoint"
    )
    if not analysis_file.is_file():
        raise SkillLoadError(f"analysis entrypoint is not a file: {analysis_file}")

    policy_reference = _reference_text(skill_root, "policy.md")
    verifier_policy = (
        f"{instructions}\n\nVERIFIER POLICY\n{policy_reference}"
        if policy_reference
        else instructions
    )
    return SkillDefinition(
        name=front_matter.name,
        description=front_matter.description.strip(),
        domain=front_matter.metadata.domain,
        source_domains=source_domains,
        report_id=front_matter.metadata.report_id,
        label=front_matter.metadata.label.strip(),
        skill_root=skill_root,
        skill_file=resolved_skill,
        analysis_file=analysis_file,
        analysis_function=entrypoint.group("function"),
        instructions=instructions,
        dataset_reference=_reference_text(skill_root, "dataset.md"),
        verifier_policy=verifier_policy,
    )


def load_lead_review_skill(
    skill_file: Path | None = None,
    *,
    skills_root: Path | None = None,
) -> LeadReviewSkillDefinition:
    """Load the singleton cross-specialist review policy from the trusted skills root."""
    root = (skills_root or repository_skills_root()).resolve(strict=True)
    candidate = skill_file or (root / "lead-review" / "SKILL.md")
    resolved_skill = candidate.resolve(strict=True)
    if not resolved_skill.is_relative_to(root):
        raise SkillLoadError(f"skill file is outside the trusted skills root: {candidate}")
    if resolved_skill.name != "SKILL.md":
        raise SkillLoadError(f"skill definition must be named SKILL.md: {candidate}")

    raw, instructions = _parse_front_matter(resolved_skill)
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("kind") != LEAD_REVIEW_SKILL_KIND:
        raise SkillLoadError(f"not a lead-review skill: {resolved_skill}")
    try:
        front_matter = LeadReviewSkillFrontMatter.model_validate(raw)
    except ValidationError as exc:
        raise SkillLoadError(
            f"{resolved_skill}: invalid lead-review skill metadata: {exc}"
        ) from exc
    if resolved_skill.parent.name != front_matter.name:
        raise SkillLoadError(
            f"{resolved_skill}: skill name {front_matter.name!r} must match folder "
            f"{resolved_skill.parent.name!r}"
        )
    if not instructions:
        raise SkillLoadError(f"{resolved_skill}: lead-review instructions are required")
    entrypoint = _ENTRYPOINT_PATTERN.fullmatch(
        front_matter.metadata.analysis_entrypoint
    )
    if entrypoint is None:
        raise SkillLoadError(
            f"{resolved_skill}: invalid analysis_entrypoint "
            f"{front_matter.metadata.analysis_entrypoint!r}"
        )
    analysis_file = _contained_path(
        resolved_skill.parent,
        entrypoint.group("path"),
        label="analysis_entrypoint",
    )
    if not analysis_file.is_file():
        raise SkillLoadError(f"analysis entrypoint is not a file: {analysis_file}")
    verifier_policy = _reference_text(resolved_skill.parent, "policy.md")
    if not verifier_policy:
        raise SkillLoadError(
            f"{resolved_skill}: references/policy.md is required for lead verification"
        )
    return LeadReviewSkillDefinition(
        name=front_matter.name,
        description=front_matter.description.strip(),
        label=front_matter.metadata.label.strip(),
        skill_root=resolved_skill.parent,
        skill_file=resolved_skill,
        analysis_file=analysis_file,
        analysis_function=entrypoint.group("function"),
        instructions=instructions,
        verifier_policy=verifier_policy,
    )


def discover_skills(skills_root: Path | None = None) -> tuple[SkillDefinition, ...]:
    """Discover analytical skills and reject duplicate identities."""
    root = (skills_root or repository_skills_root()).resolve(strict=True)
    discovered: list[SkillDefinition] = []
    for skill_file in sorted(root.glob("*/SKILL.md")):
        raw, _ = _parse_front_matter(skill_file)
        if not _is_analytical_front_matter(raw):
            continue
        discovered.append(load_skill(skill_file, skills_root=root))

    for attribute in ("name", "domain", "report_id"):
        values: dict[object, Path] = {}
        for definition in discovered:
            value = getattr(definition, attribute)
            if value in values:
                raise SkillLoadError(
                    f"duplicate specialist skill {attribute} {value!r}: "
                    f"{values[value]} and {definition.skill_file}"
                )
            values[value] = definition.skill_file

    source_owners: dict[SpecialistDomain, Path] = {}
    for definition in discovered:
        for source_domain in definition.source_domains:
            previous = source_owners.get(source_domain)
            if previous is not None:
                raise SkillLoadError(
                    f"duplicate specialist skill source domain {source_domain.value!r}: "
                    f"{previous} and {definition.skill_file}"
                )
            source_owners[source_domain] = definition.skill_file
    return tuple(discovered)


def _assert_contained_python_files(skill_root: Path) -> None:
    """Reject a skill package whose Python files resolve outside its checked-in root."""
    resolved_root = skill_root.resolve(strict=True)
    for candidate in skill_root.rglob("*.py"):
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(resolved_root):
            raise SkillLoadError(f"skill Python file escapes the skill directory: {candidate}")


def _install_package_chain(
    package_name: str,
    skill_root: Path,
    relative_parent: Path,
) -> list[str]:
    """Install synthetic contained packages needed by a relative skill import."""
    installed: list[str] = []
    package_path = skill_root
    package = package_name
    if package not in sys.modules:
        root_module = ModuleType(package)
        root_module.__path__ = [str(package_path)]
        root_module.__package__ = package
        sys.modules[package] = root_module
        installed.append(package)
    for part in relative_parent.parts:
        package_path = package_path / part
        package = f"{package}.{part}"
        if package in sys.modules:
            continue
        module = ModuleType(package)
        module.__path__ = [str(package_path)]
        module.__package__ = package
        sys.modules[package] = module
        installed.append(package)
    return installed


@cache
def _load_module(path: Path, skill_root: Path) -> ModuleType:
    """Load one entrypoint as a contained synthetic package module.

    The synthetic namespace gives trusted scripts normal relative-import semantics while
    leaving ``sys.path`` untouched.  Every Python file below the skill root is resolved
    before execution so symlinked import-path escapes are rejected.
    """
    resolved_root = skill_root.resolve(strict=True)
    resolved_path = path.resolve(strict=True)
    if not resolved_path.is_relative_to(resolved_root):
        raise SkillLoadError(f"skill script escapes the skill directory: {path}")
    _assert_contained_python_files(resolved_root)

    relative_module = resolved_path.relative_to(resolved_root).with_suffix("")
    digest = hashlib.sha256(str(resolved_root).encode("utf-8")).hexdigest()[:16]
    package_name = f"data_agent_trusted_skill_{digest}"
    module_name = f"{package_name}.{'.'.join(relative_module.parts)}"
    with _MODULE_LOAD_LOCK:
        existing = sys.modules.get(module_name)
        if isinstance(existing, ModuleType):
            return existing
        installed = _install_package_chain(
            package_name,
            resolved_root,
            relative_module.parent,
        )
        spec = importlib.util.spec_from_file_location(module_name, resolved_path)
        if spec is None or spec.loader is None:
            raise SkillLoadError(f"cannot create an import spec for skill script: {resolved_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            for package in reversed(installed):
                sys.modules.pop(package, None)
            raise
        return module


def load_analysis_runner(definition: SkillDefinition) -> AnalysisRunner:
    """Load the validated callable from a version-controlled skill script."""
    module = _load_module(definition.analysis_file, definition.skill_root)
    runner = getattr(module, definition.analysis_function, None)
    if not callable(runner):
        raise SkillLoadError(
            f"{definition.analysis_file}: entrypoint {definition.analysis_function!r} "
            "is not callable"
        )
    return cast(AnalysisRunner, runner)


def load_lead_analysis_runner(
    definition: LeadReviewSkillDefinition | None = None,
) -> LeadAnalysisRunner:
    """Load the trusted cross-specialist analysis callable from the lead skill."""
    selected = definition or load_lead_review_skill()
    module = _load_module(selected.analysis_file, selected.skill_root)
    runner = getattr(module, selected.analysis_function, None)
    if not callable(runner):
        raise SkillLoadError(
            f"{selected.analysis_file}: entrypoint {selected.analysis_function!r} "
            "is not callable"
        )
    return cast(LeadAnalysisRunner, runner)
