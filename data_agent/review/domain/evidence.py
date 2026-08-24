"""Evidence locator standard: reproducible references into source material.

Every source reference uses a ``source://`` URI with a fragment that pins the
exact region of the file that supports a claim::

    source://risk.xlsx#sheet=DailyRisk&rows=120:128
    source://comments.pdf#page=14
    source://validation.csv#rows=94:99
    source://notes.md#lines=10:15

A verifier must be able to reopen the cited region from the locator alone.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

SCHEME = "source://"

_FRAGMENT_KEYS = frozenset({"sheet", "page", "rows", "lines"})


class Locator(BaseModel):
    """Parsed form of a ``source://`` evidence locator."""

    path: str
    sheet: str | None = None
    page: int | None = None
    rows: tuple[int, int] | None = None
    lines: tuple[int, int] | None = None

    @field_validator("path")
    @classmethod
    def _check_path(cls, value: str) -> str:
        if not value or value.startswith("/") or ".." in value.split("/"):
            raise ValueError(f"invalid locator path: {value!r}")
        return value


def _parse_positive_int(key: str, value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"locator {key} must be an integer, got {value!r}") from exc
    if number <= 0:
        raise ValueError(f"locator {key} must be positive, got {number}")
    return number


def _parse_range(key: str, value: str) -> tuple[int, int]:
    """Parse ``start:end``; a bare ``N`` (no colon) means the single row/line N."""
    if ":" in value:
        start_text, end_text = value.split(":", 1)
    else:
        start_text, end_text = value, value
    start = _parse_positive_int(key, start_text)
    end = _parse_positive_int(key, end_text)
    if start > end:
        raise ValueError(f"locator {key} start {start} must be <= end {end}")
    return (start, end)


def parse_locator(uri: str) -> Locator:
    """Parse a ``source://`` URI into a :class:`Locator` (strict)."""
    if not uri.startswith(SCHEME):
        raise ValueError(f"locator must start with {SCHEME!r}, got {uri!r}")
    rest = uri[len(SCHEME) :]
    path, separator, fragment = rest.partition("#")
    if not path:
        raise ValueError("locator is missing a source path")
    locator = Locator(path=path)
    if separator:
        for part in fragment.split("&"):
            if not part:
                continue
            if "=" not in part:
                raise ValueError(f"locator fragment {part!r} must be key=value")
            key, value = part.split("=", 1)
            if key not in _FRAGMENT_KEYS:
                raise ValueError(f"unknown locator fragment key {key!r}")
            if key == "sheet":
                if not value:
                    raise ValueError("locator sheet must not be empty")
                locator.sheet = value
            elif key == "page":
                locator.page = _parse_positive_int(key, value)
            elif key == "rows":
                locator.rows = _parse_range(key, value)
            elif key == "lines":
                locator.lines = _parse_range(key, value)
    return locator


def format_locator(locator: Locator) -> str:
    """Render a :class:`Locator` back to its canonical ``source://`` URI."""
    fragments: list[str] = []
    if locator.sheet is not None:
        fragments.append(f"sheet={locator.sheet}")
    if locator.page is not None:
        fragments.append(f"page={locator.page}")
    if locator.rows is not None:
        fragments.append(f"rows={locator.rows[0]}:{locator.rows[1]}")
    if locator.lines is not None:
        fragments.append(f"lines={locator.lines[0]}:{locator.lines[1]}")
    fragment = f"#{'&'.join(fragments)}" if fragments else ""
    return f"{SCHEME}{locator.path}{fragment}"


class EvidenceReference(BaseModel):
    """A reproducible pointer to the source region supporting a claim."""

    locator: str
    quote: str | None = None

    @field_validator("locator")
    @classmethod
    def _canonicalize(cls, value: str) -> str:
        # Validate and store the canonical rendering so equal references
        # compare equal regardless of how they were written.
        return format_locator(parse_locator(value))

    @property
    def parsed(self) -> Locator:
        return parse_locator(self.locator)


