"""Source and manifest contract tests."""

from __future__ import annotations

from datetime import date

import pytest

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.source import (
    DateRange,
    Source,
    SourceManifest,
    SourceType,
)


def make_source(source_id: str = "SRC-001", path: str = "risk_metrics/risk.xlsx") -> Source:
    return Source(
        source_id=source_id,
        path=path,
        source_type=SourceType.XLSX,
        sha256="a" * 64,
        size_bytes=1024,
        candidate_domains=[SpecialistDomain.RISK_METRICS],
        date_range=DateRange(start=date(2025, 1, 1), end=date(2026, 6, 30)),
    )


class TestDateRange:
    def test_days_inclusive(self) -> None:
        assert DateRange(start=date(2025, 1, 1), end=date(2025, 1, 3)).days == 3

    def test_rejects_reversed(self) -> None:
        with pytest.raises(ValueError):
            DateRange(start=date(2025, 2, 1), end=date(2025, 1, 1))

    def test_contains(self) -> None:
        rng = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 3))
        assert rng.contains(date(2025, 1, 2))
        assert not rng.contains(date(2025, 1, 4))

    def test_overlaps(self) -> None:
        a = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))
        b = DateRange(start=date(2025, 1, 20), end=date(2025, 2, 10))
        c = DateRange(start=date(2025, 2, 1), end=date(2025, 2, 28))
        assert a.overlaps(b)
        assert not a.overlaps(c)


class TestSourceManifest:
    def test_lookup_by_id_and_path(self) -> None:
        manifest = SourceManifest(sources=[make_source()])
        assert manifest.by_id("SRC-001").path == "risk_metrics/risk.xlsx"
        assert manifest.by_path("risk_metrics/risk.xlsx").source_id == "SRC-001"

    def test_missing_lookup_raises(self) -> None:
        manifest = SourceManifest(sources=[])
        with pytest.raises(KeyError):
            manifest.by_id("SRC-999")
        with pytest.raises(KeyError):
            manifest.by_path("nope.xlsx")

    def test_source_ids(self) -> None:
        manifest = SourceManifest(sources=[make_source("SRC-001"), make_source("SRC-002", "b.csv")])
        assert manifest.source_ids == ["SRC-001", "SRC-002"]
