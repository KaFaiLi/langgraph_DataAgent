"""Deterministic, report-safe data overviews shared by specialists and PPT."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference


class OverviewStatus(StrEnum):
    """Whether an overview is safe to show as quantitative reviewed output."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class OverviewMetric(BaseModel):
    """One code-owned metric with its unit and comparison basis."""

    label: str
    value: str
    unit: str = ""
    basis: str = ""


class OverviewPoint(BaseModel):
    """One ordered category or time-series observation."""

    label: str
    value: float


class OverviewSeries(BaseModel):
    """One named numeric series."""

    name: str
    points: list[OverviewPoint]

    @model_validator(mode="after")
    def _validate_points(self) -> OverviewSeries:
        if not self.points:
            raise ValueError(f"overview series {self.name!r} requires at least one point")
        labels = [point.label for point in self.points]
        if len(labels) != len(set(labels)):
            raise ValueError(f"overview series {self.name!r} has duplicate point labels")
        return self


class _SeriesVisual(BaseModel):
    x_label: str
    y_label: str
    unit: str = ""
    series: list[OverviewSeries]

    @field_validator("series")
    @classmethod
    def _unique_series(cls, value: list[OverviewSeries]) -> list[OverviewSeries]:
        if not value:
            raise ValueError("series visual requires at least one series")
        names = [series.name for series in value]
        if len(names) != len(set(names)):
            raise ValueError(f"series visual has duplicate names: {names}")
        return value


class LineVisual(_SeriesVisual):
    kind: Literal["line"] = "line"


class BarVisual(_SeriesVisual):
    kind: Literal["bar"] = "bar"


class StackedBarVisual(_SeriesVisual):
    kind: Literal["stacked_bar"] = "stacked_bar"


class TableVisual(BaseModel):
    kind: Literal["table"] = "table"
    columns: list[str]
    rows: list[list[str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _rectangular(self) -> TableVisual:
        if not self.columns:
            raise ValueError("table visual requires at least one column")
        mismatched = [index for index, row in enumerate(self.rows) if len(row) != len(self.columns)]
        if mismatched:
            raise ValueError(f"table rows do not match columns at indexes {mismatched}")
        return self


OverviewVisual = Annotated[
    LineVisual | BarVisual | StackedBarVisual | TableVisual,
    Field(discriminator="kind"),
]


class DataOverview(BaseModel):
    """One deterministic view of a specialist's reviewed data population."""

    overview_id: str
    domain: SpecialistDomain
    source_family: str
    title: str
    summary: str
    status: OverviewStatus
    primary_for_deck: bool = False
    metrics: list[OverviewMetric] = Field(default_factory=list)
    visual: OverviewVisual | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("overview_id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
        if not value or value[0] not in set("abcdefghijklmnopqrstuvwxyz0123456789"):
            raise ValueError("overview_id must start with a lowercase letter or digit")
        if any(character not in allowed for character in value):
            raise ValueError(f"invalid overview_id {value!r}")
        return value

    @model_validator(mode="after")
    def _safe_payload(self) -> DataOverview:
        if self.status is OverviewStatus.UNAVAILABLE:
            if self.visual is not None:
                raise ValueError("unavailable overview cannot expose a quantitative visual")
            if not self.limitations:
                raise ValueError("unavailable overview requires a limitation")
            return self
        if self.visual is None:
            raise ValueError(f"{self.status.value} overview requires a visual")
        if not self.evidence:
            raise ValueError("quantitative overview requires evidence")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def data_fingerprint(self) -> str:
        """Hash the canonical code-owned payload for authoring/verification receipts."""
        payload = self.model_dump(mode="json", exclude={"data_fingerprint"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def source_locators(self) -> list[str]:
        return [reference.locator for reference in self.evidence]
