"""Evidence locator reopening tests (the verifier's evidence contract)."""

from __future__ import annotations

import pytest

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.ingestion.catalog import build_catalog
from data_agent.review.ingestion.evidence_reader import (
    LocatorValidationError,
    reopen_locator,
    validate_locator,
)
from data_agent.review.ingestion.evidence_validator import (
    EvidenceDisposition,
    EvidenceFailureCode,
    EvidenceValidator,
)
from tests.review.fixtures.builder import make_risky_tree


@pytest.fixture()
def bundle(tmp_path):
    tree = make_risky_tree(tmp_path / "source")
    manifest = build_catalog(tmp_path / "source")
    return tmp_path / "source", manifest, tree


def test_reopen_csv_rows(bundle) -> None:
    root, manifest, _ = bundle
    snippet = reopen_locator("source://risk_metrics/risk.csv#rows=2:3", root, manifest)
    assert "row 2:" in snippet
    assert "var=3.1" in snippet
    assert "row 3:" in snippet
    assert "var=4.2" in snippet


def test_reopen_csv_out_of_range_fails(bundle) -> None:
    root, manifest, _ = bundle
    with pytest.raises(LocatorValidationError, match="out of range"):
        reopen_locator("source://risk_metrics/risk.csv#rows=99:100", root, manifest)


def test_reopen_xlsx_sheet_rows(bundle) -> None:
    root, manifest, _ = bundle
    snippet = reopen_locator("source://pnl/pnl.xlsx#sheet=Adjustments&rows=1:2", root, manifest)
    assert "row 1:" in snippet
    assert "2025-01-31" in snippet
    assert "manual" in snippet


def test_reopen_xlsx_unknown_sheet_fails(bundle) -> None:
    root, manifest, _ = bundle
    with pytest.raises(LocatorValidationError, match="not found"):
        reopen_locator("source://pnl/pnl.xlsx#sheet=Nope&rows=1:2", root, manifest)


def test_reopen_multi_sheet_requires_sheet(bundle) -> None:
    root, manifest, _ = bundle
    with pytest.raises(LocatorValidationError, match="sheet required"):
        reopen_locator("source://pnl/pnl.xlsx#rows=1:2", root, manifest)


def test_reopen_parquet_rows(bundle) -> None:
    root, manifest, _ = bundle
    snippet = reopen_locator(
        "source://income_attribution/attribution.parquet#rows=2:2", root, manifest
    )
    assert "driver=vol" in snippet


def test_reopen_pdf_page(bundle) -> None:
    root, manifest, _ = bundle
    snippet = reopen_locator("source://pnl_validation/validation.pdf#page=2", root, manifest)
    assert "closed within T+2" in snippet


def test_reopen_pdf_out_of_range_fails(bundle) -> None:
    root, manifest, _ = bundle
    with pytest.raises(LocatorValidationError, match="out of range"):
        reopen_locator("source://pnl_validation/validation.pdf#page=9", root, manifest)


def test_reopen_markdown_lines(bundle) -> None:
    root, manifest, _ = bundle
    snippet = reopen_locator("source://risk_commentary/comments.md#lines=3:4", root, manifest)
    assert "2025-04-01" in snippet


def test_reopen_docx_lines(bundle) -> None:
    root, manifest, _ = bundle
    snippet = reopen_locator("source://post_trade_controls/breaches.docx#lines=2:3", root, manifest)
    assert "2025-03-10" in snippet


def test_reopen_unknown_file_fails(bundle) -> None:
    root, manifest, _ = bundle
    with pytest.raises(LocatorValidationError, match="not found"):
        reopen_locator("source://missing.csv#rows=1:2", root, manifest)


def test_validate_locator_returns_structured_result(bundle) -> None:
    root, manifest, _ = bundle
    ok = validate_locator("source://risk_metrics/risk.csv#rows=2:3", root, manifest)
    assert ok.valid
    assert ok.snippet
    bad = validate_locator("source://risk_metrics/risk.csv#rows=99:100", root, manifest)
    assert not bad.valid
    assert "out of range" in (bad.reason or "")


def test_validate_locator_rejects_source_changed_after_catalogue(bundle) -> None:
    root, manifest, _ = bundle
    source = root / "risk_metrics" / "risk.csv"
    original_size = source.stat().st_size
    source.write_bytes(source.read_bytes().replace(b"3.1", b"9.9", 1))
    assert source.stat().st_size == original_size

    result = validate_locator("source://risk_metrics/risk.csv#rows=2:2", root, manifest)

    assert not result.valid
    assert result.disposition is EvidenceDisposition.FATAL
    assert "changed" in (result.reason or "").lower()


def test_reviewed_output_adapter_never_reopens_unapproved_raw_evidence() -> None:
    result = EvidenceValidator.reviewed_output(set()).validate_references(
        [EvidenceReference(locator="source://risk_metrics/risk.csv#rows=2:2")]
    )

    assert not result.valid
    assert result.failures[0].disposition is EvidenceDisposition.REVISE
    assert result.failures[0].code is EvidenceFailureCode.REVIEWED_OUTPUT_UNAPPROVED
