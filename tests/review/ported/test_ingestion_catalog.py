"""Catalog builder tests over a real sample source tree."""

from __future__ import annotations

import hashlib

import pytest
from tests.review.fixtures.builder import make_risky_tree

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.source import SourceType
from data_agent.review.ingestion.catalog import (
    build_catalog,
    guess_domains_from_path,
    iter_source_files,
)


@pytest.fixture()
def source_tree(tmp_path) -> dict:
    return make_risky_tree(tmp_path / "source")


def test_all_formats_are_catalogued(tmp_path, source_tree) -> None:
    manifest = build_catalog(tmp_path / "source")
    assert len(manifest.sources) == 7
    by_path = {source.path: source for source in manifest.sources}

    risk = by_path["risk_metrics/risk.csv"]
    assert risk.source_type is SourceType.CSV
    assert risk.row_count == 3
    assert risk.column_names == ["date", "var", "limit", "note"]
    assert risk.candidate_domains == [SpecialistDomain.RISK_METRICS]
    assert risk.date_range is not None
    assert str(risk.date_range.start) == "2025-01-02"
    assert str(risk.date_range.end) == "2025-01-06"

    pnl = by_path["pnl/pnl.xlsx"]
    assert pnl.source_type is SourceType.XLSX
    assert pnl.sheet_names == ["DailyPnl", "Adjustments"]
    assert pnl.column_names == ["date", "pnl_musd", "comment"]
    assert pnl.candidate_domains == [SpecialistDomain.PNL]

    parquet = by_path["income_attribution/attribution.parquet"]
    assert parquet.source_type is SourceType.PARQUET
    assert parquet.row_count == 2
    assert parquet.column_names == ["date", "driver", "pnl_musd"]
    assert parquet.candidate_domains == [SpecialistDomain.INCOME_ATTRIBUTION]

    docx = by_path["post_trade_controls/breaches.docx"]
    assert docx.source_type is SourceType.DOCX
    assert docx.line_count == 3
    assert docx.candidate_domains == [SpecialistDomain.POST_TRADE_CONTROLS]

    md = by_path["risk_commentary/comments.md"]
    assert md.source_type is SourceType.MARKDOWN
    assert md.line_count == 4
    assert md.candidate_domains == [SpecialistDomain.RISK_COMMENTARY]

    pdf = by_path["pnl_validation/validation.pdf"]
    assert pdf.source_type is SourceType.PDF
    assert pdf.page_count == 2
    assert pdf.candidate_domains == [SpecialistDomain.PNL_VALIDATION]

    txt = by_path["pnl_adjustments/adjustments.txt"]
    assert txt.source_type is SourceType.TXT
    assert txt.line_count == 2
    assert txt.candidate_domains == [SpecialistDomain.PNL_ADJUSTMENTS]


def test_source_ids_are_deterministic(tmp_path, source_tree) -> None:
    first = build_catalog(tmp_path / "source")
    second = build_catalog(tmp_path / "source")
    assert [s.source_id for s in first.sources] == [s.source_id for s in second.sources]
    assert first.sources[0].source_id == "SRC-001"


def test_sha256_matches_raw_file(tmp_path, source_tree) -> None:
    manifest = build_catalog(tmp_path / "source")
    for source in manifest.sources:
        raw = hashlib.sha256((tmp_path / "source" / source.path).read_bytes()).hexdigest()
        assert source.sha256 == raw


def test_unsupported_extension_records_parse_error(tmp_path, source_tree) -> None:
    (tmp_path / "source" / "misc").mkdir(parents=True)
    (tmp_path / "source" / "misc" / "notes.bin").write_bytes(b"\x00\x01")
    manifest = build_catalog(tmp_path / "source")
    weird = manifest.by_path("misc/notes.bin")
    assert weird.source_type is SourceType.UNSUPPORTED
    assert weird.parse_error is not None
    assert "unsupported" in weird.parse_error


def test_corrupt_file_records_parse_error(tmp_path, source_tree) -> None:
    (tmp_path / "source" / "broken.xlsx").write_bytes(b"\xff\xfe\x00garbage\x9c")
    manifest = build_catalog(tmp_path / "source")
    broken = manifest.by_path("broken.xlsx")
    assert broken.source_type is SourceType.XLSX
    assert broken.parse_error is not None


def test_missing_source_root_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        build_catalog(tmp_path / "nope")


def test_iter_source_files_skips_hidden(tmp_path) -> None:
    (tmp_path / "a.csv").write_text("x\n1\n", encoding="utf-8")
    (tmp_path / ".hidden.csv").write_text("x\n1\n", encoding="utf-8")
    (tmp_path / "thumbs.db").write_bytes(b"x")
    files = iter_source_files(tmp_path)
    assert [f.name for f in files] == ["a.csv"]


def test_guess_domains_from_path() -> None:
    assert guess_domains_from_path("risk_metrics/var/daily.csv") == [SpecialistDomain.RISK_METRICS]
    assert guess_domains_from_path("pnl/daily.xlsx") == [SpecialistDomain.PNL]
    assert guess_domains_from_path("misc/unknown.csv") == []
