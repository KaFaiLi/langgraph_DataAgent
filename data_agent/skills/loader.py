"""Discover and parse ``SKILL.md`` files from the skills directory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field

from data_agent.config import get_settings
from data_agent.logging_utils import get_logger

logger = get_logger(__name__)

_FRONT_MATTER_PATTERN = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(?P<body>.*)\Z",
    re.DOTALL,
)


class Skill(BaseModel):
    """A single skill loaded from disk.

    Using Pydantic guarantees that every field is validated on construction
    and that the object is hashable/comparable via ``model_config = frozen``.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    body: str
    path: Path
    kind: str | None = None
    domain: str | None = None
    source_domains: tuple[str, ...] = Field(default_factory=tuple)
    report_id: str | None = None
    label: str | None = None
    analysis_entrypoint: str | None = None

    @property
    def instructions(self) -> str:
        """The full model-facing instruction text (frontmatter stripped)."""
        return self.body.strip()


def parse_skill_document(
    text: str, *, require_frontmatter: bool = False
) -> tuple[dict[str, Any], str]:
    """Parse one skill document for both chat discovery and trusted review loading."""
    match = _FRONT_MATTER_PATTERN.match(text)
    if match is None:
        if require_frontmatter:
            raise ValueError("missing or malformed YAML front matter")
        return {}, text
    try:
        raw = yaml.safe_load(match.group("yaml"))
    except yaml.YAMLError as exc:
        if require_frontmatter:
            raise ValueError(f"invalid YAML front matter: {exc}") from exc
        logger.warning("Bad YAML frontmatter: %s", exc)
        return {}, match.group("body")
    if not isinstance(raw, dict):
        if require_frontmatter:
            raise ValueError("front matter must be a mapping")
        return {}, match.group("body")
    return cast(dict[str, Any], raw), match.group("body")


def _load_one(skill_md: Path) -> Skill | None:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError as e:  # pragma: no cover - defensive
        logger.warning("Could not read %s: %s", skill_md, e)
        return None

    meta, body = parse_skill_document(text)
    # Fall back to the folder name and first heading if frontmatter is missing.
    name = str(meta.get("name") or skill_md.parent.name).strip()
    description = str(
        meta.get("description") or _first_paragraph(body) or "(no description)"
    ).strip()
    metadata = meta.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    source_domains = metadata.get("source_domains") or ()
    if isinstance(source_domains, str):
        source_domains = (source_domains,)
    domain = metadata.get("domain")
    if domain and not source_domains:
        source_domains = (domain,)
    return Skill(
        name=name,
        description=description,
        body=body,
        path=skill_md,
        kind=_optional_text(metadata.get("kind")),
        domain=_optional_text(domain),
        source_domains=tuple(str(value) for value in source_domains),
        report_id=_optional_text(metadata.get("report_id")),
        label=_optional_text(metadata.get("label")),
        analysis_entrypoint=_optional_text(metadata.get("analysis_entrypoint")),
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_paragraph(body: str) -> str:
    for line in body.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line
    return ""


def discover_skills(skills_dir: str | Path | None = None) -> list[Skill]:
    """Find and parse all skills under ``skills_dir``.

    A skill is any directory containing a ``SKILL.md`` file. A top-level
    ``SKILL.md`` is also supported. Results are sorted by name.
    """
    if skills_dir is None:
        skills_dir = get_settings().skills_path
    root = Path(skills_dir)
    if not root.exists():
        logger.warning("Skills dir does not exist: %s", root)
        return []

    skills: dict[str, Skill] = {}
    for skill_md in sorted(root.rglob("SKILL.md")):
        skill = _load_one(skill_md)
        if skill is None:
            continue
        if skill.name in skills:
            logger.warning(
                "Duplicate skill name %r (%s); keeping first.",
                skill.name,
                skill_md,
            )
            continue
        skills[skill.name] = skill

    logger.info("Discovered %d skill(s) in %s", len(skills), root)
    return list(skills.values())
