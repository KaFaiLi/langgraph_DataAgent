"""Behavior tests for the finalized-format PnL skill entrypoint."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from tests.review.fixtures.builder import make_csv, make_xlsx

from data_agent.review.ingestion.catalog import build_catalog
from data_agent.review.ingestion.evidence_reader import validate_locator
from data_agent.tools.review_context import ToolContext

SKILL_SCRIPT = Path(__file__).parents[3] / "skills" / "pnl" / "scripts" / "analysis.py"

PNL_HEADERS = [
    "Value Date",
    "Version",
    "BU",
    "SBU",
    "GPC1",
    "GPC2",
    "GPC3",
    "PC",
    "GGOP",
    "GOP",
    "PTF",
    "Notion",
    "REGION",
    "Currency",
    "DTD",
    "WTD",
    "MTD",
    "QTD",
    "YTD",
]

ADJUSTMENT_HEADERS = [
    "ADJUSTMENTID",
    "GOP",
    "PTF",
    "CCY",
    "AMOUNT",
    "AMOUNTINEUR",
    "COMMENTS",
    "CREATIONDATE",
    "USER",
    "VALDATEBEGIN",
    "VALDATEEND",
    "SBU",
    "PC",
    "NATURE",
    "ADJUSTMENTLINKID",
    "INSTRUMENT",
    "FILEPATH",
    "JEDAIID",
    "JEDAIIDLINK",
    "FOLDER",
    "SOURCE",
    "REGION",
    "PNLCOMPONENT",
    "CRAFTINDICATOR",
    "DEALID",
    "SECURITYID",
    "CCYPAIR",
    "EXCHANGERATE",
    "PNLTYPE",
    "TPR",
    "NATUREID",
    "TYPE",
    "TYPO",
    "MACROTYPO",
    "ENDEVENT",
    "MACRONAME",
    "MACROLOG",
    "INCIDENTID",
    "DOCUMENTID",
    "ADJUSTMENTSOURCE",
    "RCCODE",
    "CPMIMPACT",
]


def _load_skill_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("test_pnl_skill_analysis_module", SKILL_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PNL_SKILL = _load_skill_module()


def _pnl_row(
    day: str,
    *,
    dtd: float = 1.0,
    wtd: float = 1.0,
    gop: str = "GOP-A",
    currency: str = "EUR",
) -> dict:
    return {
        "Value Date": day,
        "Version": "PUBLISHED_WW_FLASH",
        "BU": "BU-A",
        "SBU": "SBU-A",
        "GPC1": "GPC1-A",
        "GPC2": "GPC2-A",
        "GPC3": "GPC3-A",
        "PC": "PC-A",
        "GGOP": "GGOP-A",
        "GOP": gop,
        "PTF": "PTF-A",
        "Notion": "Pnl_Notion/Final Result Acc",
        "REGION": "REGION-A",
        "Currency": currency,
        "DTD": dtd,
        "WTD": wtd,
        "MTD": 1.0 if day.endswith("01") else 3.0,
        "QTD": 1.0 if day.endswith("01") else 3.0,
        "YTD": 1.0 if day.endswith("01") else 3.0,
    }


def _adjustment_row(
    *,
    adjustment_id: str = "ADJ-1",
    amount: float = 10.0,
    amount_eur: float = 9.0,
    gop: str = "GOP-A",
    value_date: str = "2025-07-02",
    creation_date: str = "2025-07-03",
    link_id: str = "LINK-1",
) -> dict:
    row = dict.fromkeys(ADJUSTMENT_HEADERS, "")
    row.update(
        {
            "ADJUSTMENTID": adjustment_id,
            "GOP": gop,
            "PTF": "PTF-A",
            "CCY": "EUR",
            "AMOUNT": amount,
            "AMOUNTINEUR": amount_eur,
            "COMMENTS": "documented true-up",
            "CREATIONDATE": creation_date,
            "USER": "control.user",
            "VALDATEBEGIN": value_date,
            "VALDATEEND": value_date,
            "SBU": "SBU-A",
            "PC": "PC-A",
            "NATURE": "M - Manual",
            "ADJUSTMENTLINKID": link_id,
            "INSTRUMENT": "Accrual",
            "FOLDER": "PTF-A",
            "SOURCE": "MANUAL",
            "REGION": "REGION-A",
            "PNLCOMPONENT": "COMPONENT-A",
            "CRAFTINDICATOR": "COMPONENT-A",
            "EXCHANGERATE": 0.9,
            "PNLTYPE": "T",
            "TPR": "TRADE PNL",
            "NATUREID": "CMANUAL",
            "TYPE": "Correction",
            "ADJUSTMENTSOURCE": "SOURCE-A",
            "RCCODE": "RC-A",
            "CPMIMPACT": False,
        }
    )
    return row


def _validation_row(
    *,
    gop: str = "GOP-A",
    state: str = "Validated",
    request_date: str = "7/2/2025",
    created: str = "2025-07-02T10:00:00",
) -> dict:
    return {
        "gop": gop,
        "team": "TEAM-A",
        "state": state,
        "creationTime": created,
        "active": True,
        "user": "control.user",
        "api_request_date": request_date,
        "pnlType": "FLASH",
    }


def _context(tmp_path: Path, *, bad_wtd: bool = False, bad_fx: bool = False) -> ToolContext:
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    pnl_dir = source / "pnl"
    pnl_dir.mkdir(parents=True)
    workspace.mkdir()
    rows = [
        _pnl_row("2025-07-01"),
        _pnl_row("2025-07-02", dtd=2.0, wtd=99.0 if bad_wtd else 3.0),
    ]
    make_xlsx(
        pnl_dir / "air.xlsx",
        {
            "Sheet1": [
                PNL_HEADERS,
                *[[row[header] for header in PNL_HEADERS] for row in rows],
            ]
        },
    )
    make_csv(
        pnl_dir / "adjustments.csv",
        [_adjustment_row(amount_eur=8.0 if bad_fx else 9.0)],
    )
    make_csv(pnl_dir / "validation.csv", [_validation_row()])
    return ToolContext(
        source_root=source,
        workspace_root=workspace,
        manifest=build_catalog(source),
    )


def _results(ctx: ToolContext) -> dict:
    paths = [source.path for source in ctx.manifest.sources]
    return {result.name: result for result in PNL_SKILL.run_analysis(ctx, paths)}


def test_finalized_three_file_contract_runs_as_one_skill(tmp_path: Path) -> None:
    results = _results(_context(tmp_path))
    assert list(results) == [
        "pnl_input_contract",
        "pnl_cumulative_integrity",
        "pnl_statistical_patterns",
        "pnl_adjustment_controls",
        "pnl_validation_and_reconciliation",
    ]
    assert results["pnl_input_contract"].flag_candidates == []
    reconciliation = results["pnl_validation_and_reconciliation"].tables[-1]
    assert reconciliation["monetary_reconciliation"] == "UNRESOLVED"
    assert "unit" in str(reconciliation["reason"]).lower()

    adjustment = results["pnl_adjustment_controls"].overviews[0]
    assert adjustment.overview_id == "pnl.adjustment-profile"
    assert adjustment.visual is not None
    assert adjustment.visual.kind == "bar"
    assert [(point.label, point.value) for point in adjustment.visual.series[0].points] == [
        ("2025-07", 9.0)
    ]
    validation = results["pnl_validation_and_reconciliation"].overviews[0]
    assert validation.overview_id == "pnl.validation-profile"
    assert validation.visual is not None
    assert validation.visual.kind == "table"
    assert validation.visual.rows == [["FLASH", "TEAM-A", "Validated", "Yes", "1"]]


def test_schema_specific_calculations_flag_reperforming_errors(tmp_path: Path) -> None:
    ctx = _context(tmp_path, bad_wtd=True, bad_fx=True)
    first = _results(ctx)
    second = _results(ctx)
    assert [result.model_dump(mode="json") for result in first.values()] == [
        result.model_dump(mode="json") for result in second.values()
    ]

    cumulative_flags = first["pnl_cumulative_integrity"].flag_candidates
    assert {flag["kind"] for flag in cumulative_flags} == {"pnl_cumulative_mismatch"}
    assert cumulative_flags[0]["field"] == "WTD"

    adjustment_flags = first["pnl_adjustment_controls"].flag_candidates
    conversion = next(
        flag for flag in adjustment_flags if flag["kind"] == "adjustment_eur_conversion_mismatch"
    )
    assert conversion["actual_eur"] == pytest.approx(8.0)
    assert conversion["expected_eur"] == pytest.approx(9.0)

    for flag in [*cumulative_flags, conversion]:
        validation = validate_locator(flag["locator"], ctx.source_root, ctx.manifest)
        assert validation.valid, validation.reason


def test_cross_source_gop_population_is_checked_in_both_directions(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    validation_path = ctx.source_root / "pnl" / "validation.csv"
    make_csv(validation_path, [_validation_row(gop="GOP-B")])
    ctx = ToolContext(
        source_root=ctx.source_root,
        workspace_root=ctx.workspace_root,
        manifest=build_catalog(ctx.source_root),
    )
    flags = _results(ctx)["pnl_validation_and_reconciliation"].flag_candidates
    assert {flag["kind"] for flag in flags} >= {
        "pnl_gop_without_validation_history",
        "validation_gop_without_pnl_rows",
    }


def test_pnl_duplicate_key_keeps_currency_dimension(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    pnl_path = ctx.source_root / "pnl" / "air.xlsx"
    rows = [
        _pnl_row("2025-07-01", currency="EUR"),
        _pnl_row("2025-07-01", currency="USD"),
    ]
    make_xlsx(
        pnl_path,
        {
            "Sheet1": [
                PNL_HEADERS,
                *[[row[header] for header in PNL_HEADERS] for row in rows],
            ]
        },
    )
    ctx = ToolContext(
        source_root=ctx.source_root,
        workspace_root=ctx.workspace_root,
        manifest=build_catalog(ctx.source_root),
    )
    flags = _results(ctx)["pnl_input_contract"].flag_candidates
    assert not any(flag["kind"] == "duplicate_pnl_business_key" for flag in flags)


def test_adjustment_reversal_and_validation_persistence_are_computed(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    adjustment_path = ctx.source_root / "pnl" / "adjustments.csv"
    make_csv(
        adjustment_path,
        [
            _adjustment_row(adjustment_id="ADJ-1"),
            _adjustment_row(
                adjustment_id="ADJ-2",
                amount=-10.0,
                amount_eur=-9.0,
                value_date="2025-07-04",
                creation_date="2025-07-05",
            ),
        ],
    )
    validation_path = ctx.source_root / "pnl" / "validation.csv"
    make_csv(
        validation_path,
        [
            _validation_row(
                state="Waiting",
                request_date=f"7/{day}/2025",
                created=f"2025-07-{day:02d}T10:00:00",
            )
            for day in (2, 3, 4)
        ],
    )
    ctx = ToolContext(
        source_root=ctx.source_root,
        workspace_root=ctx.workspace_root,
        manifest=build_catalog(ctx.source_root),
    )
    results = _results(ctx)
    reversal = next(
        flag
        for flag in results["pnl_adjustment_controls"].flag_candidates
        if flag["kind"] == "adjustment_reversal_candidate"
    )
    validation = validate_locator(reversal["locator"], ctx.source_root, ctx.manifest)
    assert validation.valid, validation.reason
    persistence = next(
        table
        for table in results["pnl_validation_and_reconciliation"].tables
        if table.get("longest_same_state_observations") == 3
    )
    assert persistence["longest_same_state"] == "Waiting"


def test_pnl_overview_resets_cumulative_dtd_each_calendar_year(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    pnl_path = ctx.source_root / "pnl" / "air.xlsx"
    rows = [
        _pnl_row("2025-12-30", dtd=2.0),
        _pnl_row("2025-12-31", dtd=-1.0),
        _pnl_row("2026-01-02", dtd=3.0),
        _pnl_row("2026-01-05", dtd=-2.0),
    ]
    make_xlsx(
        pnl_path,
        {
            "Sheet1": [
                PNL_HEADERS,
                *[[row[header] for header in PNL_HEADERS] for row in rows],
            ]
        },
    )
    ctx = ToolContext(
        source_root=ctx.source_root,
        workspace_root=ctx.workspace_root,
        manifest=build_catalog(ctx.source_root),
    )

    overviews = _results(ctx)["pnl_cumulative_integrity"].overviews

    assert len(overviews) == 1
    overview = overviews[0]
    assert overview.primary_for_deck
    assert overview.visual.kind == "line"
    assert [series.name for series in overview.visual.series] == ["2025", "2026"]
    assert [[point.value for point in series.points] for series in overview.visual.series] == [
        [2.0, 1.0],
        [3.0, 1.0],
    ]
    assert [(metric.label, metric.value) for metric in overview.metrics] == [
        ("2025 total", "1"),
        ("2026 total", "1"),
    ]
    assert overview.evidence[0].locator == "source://pnl/air.xlsx#sheet=Sheet1&rows=2:5"


def test_pnl_overview_never_aggregates_incompatible_currency_or_ptf_series(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    pnl_path = ctx.source_root / "pnl" / "air.xlsx"
    rows = [
        _pnl_row("2025-07-01", currency="EUR", dtd=2.0),
        _pnl_row("2025-07-02", currency="EUR", dtd=-1.0),
        {**_pnl_row("2025-07-01", currency="USD", dtd=4.0), "PTF": "PTF-B"},
        {**_pnl_row("2025-07-02", currency="USD", dtd=3.0), "PTF": "PTF-B"},
    ]
    make_xlsx(
        pnl_path,
        {
            "Sheet1": [
                PNL_HEADERS,
                *[[row[header] for header in PNL_HEADERS] for row in rows],
            ]
        },
    )
    ctx = ToolContext(
        source_root=ctx.source_root,
        workspace_root=ctx.workspace_root,
        manifest=build_catalog(ctx.source_root),
    )

    overviews = _results(ctx)["pnl_cumulative_integrity"].overviews

    assert len(overviews) == 2
    assert sum(overview.primary_for_deck for overview in overviews) == 1
    assert {
        (overview.visual.unit, overview.metrics[0].value)
        for overview in overviews
        if overview.visual is not None
    } == {("EUR", "1"), ("USD", "7")}
    assert all("not a desk total" in overview.limitations[0] for overview in overviews)


def test_pnl_overview_is_explicitly_unavailable_for_malformed_schema(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    make_xlsx(
        ctx.source_root / "pnl" / "air.xlsx",
        {"Sheet1": [["date", "amount"], ["2025-07-01", 4.0]]},
    )
    ctx = ToolContext(
        source_root=ctx.source_root,
        workspace_root=ctx.workspace_root,
        manifest=build_catalog(ctx.source_root),
    )

    overview = _results(ctx)["pnl_cumulative_integrity"].overviews[0]

    assert overview.status.value == "unavailable"
    assert overview.visual is None
    assert "recognized" in overview.limitations[0]


def test_wide_income_attribution_export_runs_inside_the_pnl_skill(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    income_dir = source / "income_attribution"
    income_dir.mkdir(parents=True)
    workspace.mkdir()
    headers = [
        "bu",
        "sbu",
        "grppc100",
        "grppc200",
        "grppc300",
        "td",
        "pc",
        "ggop",
        "gop",
        "asofdate",
        "Unexplained",
        "Market Effect",
        "Final Result Acc DTD",
        "Unexplained Cumulative",
        "Market Effect Cumulative",
        "Final Result Acc DTD Cumulative",
        "isbatchvalidated",
        "status",
        "validated",
        "air_mpc_validation_status",
        "air_fo_validation status",
    ]
    rows = [
        [
            "MARK",
            "EQD",
            "G1",
            "G2",
            "G3",
            "TD",
            "PC",
            "GGOP",
            "GOP-A",
            "2025-01-02",
            1.0,
            9.0,
            10.0,
            1.0,
            9.0,
            10.0,
            True,
            "IA process is complete",
            True,
            "Validated",
            "Validated",
        ],
        [
            "MARK",
            "EQD",
            "G1",
            "G2",
            "G3",
            "TD",
            "PC",
            "GGOP",
            "GOP-A",
            "2025-01-03",
            0.0,
            -5.0,
            -5.0,
            1.0,
            4.0,
            5.0,
            False,
            "IA process is running",
            False,
            "Pending",
            "Pending",
        ],
    ]
    make_csv(
        income_dir / "FSI_myIA_2025-01-01_to_2026-06-30_post_processed.csv",
        [dict(zip(headers, row, strict=True)) for row in rows],
    )
    ctx = ToolContext(
        source_root=source,
        workspace_root=workspace,
        manifest=build_catalog(source),
    )

    results = _results(ctx)

    assert list(results)[-5:] == [
        "income_attribution_schema",
        "income_attribution_driver_profile",
        "income_attribution_persistence",
        "income_attribution_reconciliation",
        "income_attribution_status",
    ]
    assert results["income_attribution_schema"].tables[-1]["parsed_rows"] == 2
    profile = results["income_attribution_driver_profile"]
    assert profile.tables[0]["top3_share"] == pytest.approx(1.0)
    assert profile.overviews[0].source_locators == [
        "source://income_attribution/FSI_myIA_2025-01-01_to_2026-06-30_post_processed.csv#rows=2:3"
    ]
    assert not results["income_attribution_reconciliation"].flag_candidates
    status_flags = results["income_attribution_status"].flag_candidates
    assert status_flags[0]["kind"] == "income_attribution_processing_state"
    assert status_flags[0]["status"] == "IA process is running"
