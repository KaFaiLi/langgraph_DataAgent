"""Source material contracts: sources, manifests, date ranges."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from data_agent.review.domain.domains import SpecialistDomain


class SourceType(StrEnum):
    """Supported source file formats."""

    CSV = "csv"
    XLSX = "xlsx"
    XLSM = "xlsm"
    PARQUET = "parquet"
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"
    TXT = "txt"
    UNSUPPORTED = "unsupported"


class DateRange(BaseModel):
    """Inclusive date range."""

    start: date
    end: date

    @model_validator(mode="after")
    def _check_order(self) -> DateRange:
        if self.start > self.end:
            raise ValueError(f"start {self.start} must be <= end {self.end}")
        return self

    @property
    def days(self) -> int:
        """Number of calendar days in the range (inclusive)."""
        return (self.end - self.start).days + 1

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def overlaps(self, other: DateRange) -> bool:
        return self.start <= other.end and other.start <= self.end


class Source(BaseModel):
    """One immutable source file, identified and profiled deterministically."""

    source_id: str
    path: str
    source_type: SourceType
    sha256: str
    size_bytes: int

    candidate_domains: list[SpecialistDomain] = Field(default_factory=list)
    date_range: DateRange | None = None

    row_count: int | None = None
    sheet_names: list[str] = Field(default_factory=list)
    column_names: list[str] = Field(default_factory=list)

    page_count: int | None = None
    """Page count for PDF sources; used to validate page locators."""

    line_count: int | None = None
    """Line/paragraph count for text-like sources; used to validate line locators."""

    parse_error: str | None = None
    """Set when the file could not be parsed; runs with parse errors FAIL loudly."""


class SourceManifest(BaseModel):
    """Deterministic catalogue of every source in a review run."""

    sources: list[Source] = Field(default_factory=list)

    def by_id(self, source_id: str) -> Source:
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise KeyError(f"unknown source id {source_id!r}")

    def by_path(self, path: str) -> Source:
        for source in self.sources:
            if source.path == path:
                return source
        raise KeyError(f"unknown source path {path!r}")

    @property
    def source_ids(self) -> list[str]:
        return [source.source_id for source in self.sources]
