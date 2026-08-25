"""Map the shared guarded source catalogue into review domain contracts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.source import (
    DateRange,
    Source,
    SourceManifest,
    SourceType,
)
from data_agent.tools.source_tools import (
    SourcePathError,
    candidate_domains_from_path,
    discover_sources,
    iter_source_files,
)


def guess_domains_from_path(relative_path: str) -> list[SpecialistDomain]:
    """Return the shared catalogue's deterministic domain classifications."""
    return [SpecialistDomain(value) for value in candidate_domains_from_path(relative_path)]


def build_catalog(source_root: str | Path) -> SourceManifest:
    """Build the unbounded authoritative review manifest from shared metadata."""
    try:
        metadata, _ = discover_sources(source_root, max_sources=None)
    except SourcePathError as exc:
        raise FileNotFoundError(str(exc)) from exc
    sources: list[Source] = []
    for item in metadata:
        source_type = (
            SourceType(item.type)
            if item.type in {member.value for member in SourceType}
            else SourceType.UNSUPPORTED
        )
        parse_error = item.parse_error
        if source_type is SourceType.UNSUPPORTED and parse_error is None:
            parse_error = f"unsupported file type: {Path(item.path).suffix or '(no extension)'}"
        date_range = None
        if item.date_range_start and item.date_range_end:
            date_range = DateRange(
                start=date.fromisoformat(item.date_range_start),
                end=date.fromisoformat(item.date_range_end),
            )
        sources.append(
            Source(
                source_id=item.source_id,
                path=item.path,
                source_type=source_type,
                sha256=item.sha256,
                size_bytes=item.size_bytes,
                candidate_domains=[SpecialistDomain(value) for value in item.candidate_domains],
                date_range=date_range,
                row_count=item.row_count,
                sheet_names=list(item.sheet_names),
                column_names=list(item.column_names),
                page_count=item.page_count,
                line_count=item.line_count,
                parse_error=parse_error,
            )
        )
    return SourceManifest(sources=sources)


__all__ = ["build_catalog", "guess_domains_from_path", "iter_source_files"]
