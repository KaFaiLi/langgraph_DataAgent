"""Contained, paginated access to registered skill references."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from data_agent.skills.loader import Skill
from data_agent.skills.review import SkillLoadError


class ReferenceRequest(BaseModel):
    name: str
    reference: Literal["dataset", "policy"]
    offset: int = Field(default=0, ge=0)
    max_chars: int = Field(default=12000, ge=1, le=16000)


def read_reference(skill: Skill, request: ReferenceRequest) -> dict[str, object]:
    """Load an allowlisted file below the selected, host-registered skill root."""
    root = skill.path.parent.resolve(strict=True)
    path = root / "references" / f"{request.reference}.md"
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise SkillLoadError(
            f"Missing {request.reference} reference for skill {skill.name!r}"
        ) from exc
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise SkillLoadError("skill reference escapes the registered skill directory")
    # A bounded read prevents an unexpectedly large local reference exhausting memory.
    if resolved.stat().st_size > 2_000_000:
        raise SkillLoadError("skill reference exceeds the 2 MB size limit")
    value = resolved.read_text(encoding="utf-8")
    return text_page(value, offset=request.offset, max_chars=request.max_chars) | {
        "skill": skill.name,
        "reference": request.reference,
    }


def text_page(value: str, *, offset: int, max_chars: int) -> dict[str, object]:
    """Make partial content unmistakable, including the final page of a long result."""
    if offset < 0 or not 1 <= max_chars <= 16000:
        raise ValueError("offset must be nonnegative and max_chars between 1 and 16000")
    if offset > len(value):
        raise ValueError(f"offset exceeds total_chars ({len(value)})")
    end = min(len(value), offset + max_chars)
    return {
        "content": value[offset:end],
        "offset": offset,
        "total_chars": len(value),
        "truncated": offset > 0 or end < len(value),
        "next_offset": end if end < len(value) else None,
    }
