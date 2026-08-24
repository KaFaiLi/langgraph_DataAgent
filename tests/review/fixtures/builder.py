"""Deterministic sample-source builders for tests.

Every builder writes a small, well-formed file of the given format. Used by
ingestion, tool, graph, and security tests.
"""

from __future__ import annotations

import csv as csv_module
from pathlib import Path

import polars as pl


def make_csv(path: Path, rows: list[dict]) -> Path:
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv_module.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def make_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> Path:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(title=name)
        for row in rows:
            worksheet.append(row)
    workbook.save(path)
    return path


def make_parquet(path: Path, rows: list[dict]) -> Path:
    pl.DataFrame(rows).write_parquet(path)
    return path


def make_pdf(path: Path, pages: list[str]) -> Path:
    import pymupdf

    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path


def make_docx(path: Path, paragraphs: list[str]) -> Path:
    from docx import Document

    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(path)
    return path


def make_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def make_risky_tree(root: Path) -> dict[str, Path]:
    """Build a sample source tree covering all 8 supported formats.

    Returns a mapping of source id-ish keys to paths (relative to ``root``).
    """
    risk_dir = root / "risk_metrics"
    pnl_dir = root / "pnl"
    income_dir = root / "income_attribution"
    controls_dir = root / "post_trade_controls"
    commentary_dir = root / "risk_commentary"
    validation_dir = root / "pnl_validation"
    adjustments_dir = root / "pnl_adjustments"
    for directory in (
        risk_dir,
        pnl_dir,
        income_dir,
        controls_dir,
        commentary_dir,
        validation_dir,
        adjustments_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    risk_csv = make_csv(
        risk_dir / "risk.csv",
        [
            {"date": "2025-01-02", "var": "3.1", "limit": "5.0"},
            {"date": "2025-01-03", "var": "4.2", "limit": "5.0"},
            {"date": "2025-01-06", "var": "5.8", "limit": "5.0", "note": "noise 1899-12-31"},
        ],
    )
    pnl_xlsx = make_xlsx(
        pnl_dir / "pnl.xlsx",
        {
            "DailyPnl": [
                ["date", "pnl_musd", "comment"],
                ["2025-01-02", 0.4, "carry"],
                ["2025-01-03", -1.8, "elections"],
            ],
            "Adjustments": [
                ["date", "adj_musd", "reason"],
                ["2025-01-31", 2.0, "manual"],
            ],
        },
    )
    income_parquet = make_parquet(
        income_dir / "attribution.parquet",
        [
            {"date": "2025-02-03", "driver": "carry", "pnl_musd": 0.9},
            {"date": "2025-02-04", "driver": "vol", "pnl_musd": 2.3},
        ],
    )
    breach_docx = make_docx(
        controls_dir / "breaches.docx",
        [
            "Post-trade control breaches log.",
            "2025-03-10: FX options mapping breach, product FXOPT, closed T+1.",
            "2025-03-11: FX options mapping breach, product FXOPT, closed T+1.",
        ],
    )
    commentary_md = make_text(
        commentary_dir / "comments.md",
        "# Risk commentary\n\n2025-04-01: VaR within limits.\n2025-04-02: VaR within limits.\n",
    )
    validation_pdf = make_pdf(
        validation_dir / "validation.pdf",
        [
            "PnL Validation Summary\nPeriod 2025-05-01 to 2025-05-31\nUnexplained PnL: 1.2 mUSD",
            "All breaks closed within T+2.",
        ],
    )
    adjustments_txt = make_text(
        adjustments_dir / "adjustments.txt",
        "Manual adjustments log\n2025-06-30: +1.5 mUSD reversal expected 2025-07-01\n",
    )
    return {
        "risk_csv": risk_csv,
        "pnl_xlsx": pnl_xlsx,
        "income_parquet": income_parquet,
        "breach_docx": breach_docx,
        "commentary_md": commentary_md,
        "validation_pdf": validation_pdf,
        "adjustments_txt": adjustments_txt,
    }


