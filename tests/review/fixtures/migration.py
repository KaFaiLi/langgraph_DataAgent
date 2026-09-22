"""Synthetic supported-domain sources shared by migration tests and manual CLI smoke runs."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from tests.review.fixtures.builder import make_csv
from tests.review.ported.test_pnl_skill_analysis import _context as pnl_context
from tests.review.ported.test_post_trade_controls_analysis import _breach_rows
from tests.review.ported.test_risk_commentary_analysis import _context as commentary_context
from tests.review.ported.test_risk_metrics_skill_analysis import _sgmr_row


def make_migration_sources(root: Path, scratch: Path) -> dict[str, list[str]]:
    """Small deterministic fixture: finalized PnL, SGMR, breach log and quoted commentary."""
    root.mkdir(parents=True, exist_ok=True)
    pnl = pnl_context(scratch / "pnl", bad_wtd=True, bad_fx=True)
    commentary, _ = commentary_context(scratch / "commentary")
    for ctx in (pnl, commentary):
        shutil.copytree(ctx.source_root, root, dirs_exist_ok=True)
    (root / "risk_metrics").mkdir(exist_ok=True)
    make_csv(
        root / "risk_metrics" / "sgmr.csv",
        [
            _sgmr_row(date(2025, 1, day), value=value)
            for day, value in zip(range(2, 7), [6, 7, 12, 13, 8], strict=True)
        ],
    )
    (root / "post_trade_controls").mkdir(exist_ok=True)
    make_csv(root / "post_trade_controls" / "breaches.csv", _breach_rows())
    return {
        "risk-metrics": ["risk_metrics/sgmr.csv"],
        "pnl": ["pnl/air.xlsx", "pnl/adjustments.csv", "pnl/validation.csv"],
        "post-trade-controls": ["post_trade_controls/breaches.csv"],
        "risk-commentary": ["risk_commentary/quarterly_review.md"],
    }
