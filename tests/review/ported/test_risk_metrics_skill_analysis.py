"""Behavior tests for the finalized-format risk-metrics skill entrypoint."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import ModuleType

from tests.review.fixtures.builder import make_csv, make_parquet

from data_agent.review.ingestion.catalog import build_catalog
from data_agent.review.ingestion.evidence_reader import validate_locator
from data_agent.tools.review_context import ToolContext

SKILL_SCRIPT = Path(__file__).parents[3] / "skills" / "risk-metrics" / "scripts" / "analysis.py"


def _load_skill_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "test_risk_metrics_skill_analysis_module", SKILL_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RISK_METRICS_SKILL = _load_skill_module()


def _iso_time(day: date, hour: int) -> str:
    return datetime.combine(day, time(hour, 0)).isoformat()


def _sgmr_row(
    day: date,
    *,
    value: float = 6.0,
    limit: float = 10.0,
    indicator: str = "VAR",
    portfolio: str = "PTF-A",
) -> dict[str, object]:
    metric_name = f"METRIC-{indicator}"
    pc = "PC-A"
    return {
        "limId": f"LIMIT-{portfolio}-{indicator}",
        "limType": "ABSOLUTE_THRESHOLD",
        "limUnit": "MEUR",
        "limStartDate": "2025-01-01",
        "limEndDate": "2025-12-31",
        "limDisplayUnit": "MEUR",
        "limInitialMinValue": -limit,
        "limInitialMaxValue": limit,
        "limTempMinValue": None,
        "limTempMaxValue": None,
        "limRelativeThreshold": 0.9,
        "limFrequency": "Daily",
        "limConsumptionOwner": "RISK-OWNER",
        "limRequestOwner": "RISK-REQUESTOR",
        "limDelegation": "RISK-DELEGATION",
        "rmRiskIndicator": indicator,
        "rmRiskMetricName": metric_name,
        "rmRiskMetricLabel": indicator,
        "rmRiskMetricNameGeneric": indicator,
        "rmRiskMeasureId": f"MEASURE-{indicator}",
        "metricType_LB": indicator,
        "paramTypeId": f"MEASURE-{indicator}",
        "stranaNodeName": portfolio,
        "stranaPc": pc,
        "stranaSbu": "SBU-A",
        "stranaBu": "BU-A",
        "stranaGrppc1": "GPC1-A",
        "stranaGrppc2": "GPC2-A",
        "stranaGrppc3": "GPC3-A",
        "flatStrana": json.dumps(
            {
                "BU": "BU-A",
                "SBU": "SBU-A",
                "GPC1": "GPC1-A",
                "GPC2": "GPC2-A",
                "GPC3": "GPC3-A",
                "PC": pc,
            }
        ),
        "rmCurrency": "EUR",
        "geographicalZone_LB": "EUROPE",
        "consoId": f"CONSO-{portfolio}-{indicator}-{day.isoformat()}",
        "id": f"ROW-{portfolio}-{indicator}-{day.isoformat()}",
        "consoValue": value,
        "consoValueEur": value,
        "consoValueDate": day.isoformat(),
        "consoLastValueDate": (day - timedelta(days=1)).isoformat(),
        "consoCreationDate": _iso_time(day + timedelta(days=1), 2),
        "consoVersion": 1,
        "consoOfficialStampIndic": "N",
        "limMaxValue": limit,
        "limMinValue": -limit,
    }


def _colibris_row(
    excess_id: int,
    value_day: date,
    *,
    still_open: bool = False,
    increase_status: str = "",
) -> dict[str, object]:
    created = value_day + timedelta(days=1)
    close_day = created + timedelta(days=2)
    return {
        "excessId": excess_id,
        "excessCreationDate": _iso_time(created, 10),
        "limitType": "ABSOLUTE_THRESHOLD",
        "perimeterMnemonic": "PC-A",
        "perimeterLevel": "GPC3-A",
        "riskIndicator": "VAR",
        "excessLastConsoValue": 11.0,
        "excessLastConsoValueDate": value_day.isoformat(),
        "limitValue": 10.0,
        "unit": "MEUR",
        "excessStillOpen": still_open,
        "excessWorkflowStatus": "OPEN" if still_open else "VALIDATED",
        "lastExcessExplanationClassification": "REVIEWED",
        "lastExcessValidationClassification": "PASSIVE",
        "limitDelegation": "RISK-DELEGATION",
        "riskType": "VaR",
        "sgmrId": "NO-DIRECT-MATCH",
        "riskMetricName": "METRIC-VAR",
        "scenario": "VAR-SCENARIO",
        "increaseId": 0,
        "increaseWorkflowStatus": increase_status,
        "excessMaxUsage": 115.0,
        "colibrisSbu": "SBU-A",
        "creationConsValue": 10.5,
        "creationConsDate": value_day.isoformat(),
        "underlying": "UNDERLYING-A",
        "requestOwner": "RISK-REQUESTOR",
        "consumptionOwner": "RISK-OWNER",
        "limitRegulatoryFlag": "STANDARD",
        "frequency": "Daily",
        "daysInExcess": 2,
        "daysWithoutValidationTotal": 1,
        "daysWithoutExplanation": 1,
        "daysWithoutValidateExplanation": 0,
        "excessCloseDate": "" if still_open else _iso_time(close_day, 12),
        "riskMetricComment": "risk event",
        "increaseCreationDate": "",
        "increaseValidationTrdDirCreationDate": "",
        "increaseValidationRisqCreationDate": "",
        "lastExcessExplanationCreationDate": _iso_time(created + timedelta(days=1), 12),
        "lastExcessExplanationIsExcessConfirmed": True,
        "lastExcessExplanationCause": "market move",
        "lastExcessExplanationIsCustomerDeal": False,
        "lastExcessExplanationAnticipation": "monitored",
        "lastExcessExplanationActionPlan": "reduce risk",
        "lastExcessExplanationDeadline": (created + timedelta(days=1)).isoformat(),
        "lastExcessExplanationSolution": "hedge",
        "lastExcessExplanationFullname": "TRADER-A",
        "lastExcessValidationFullname": "VALIDATOR-A",
        "lastExcessValidationCreationDate": _iso_time(created + timedelta(days=1), 14),
        "lastExcessValidationDecisionDetails": "reviewed",
        "lastExcessValidationIsSatisfactory": not still_open,
        "lastExcessValidationTechnicalType": "FOLLOW-UP",
        "lastExcessValidationTechnicalSubType": "RISK-REDUCTION",
        "lastExcessValidationTechnicalDeadline": (created + timedelta(days=2)).isoformat(),
        "lastExcessValidationTechnicalFollowUp": "monitor",
        "excessValidationTechnicalConsumptionOwners": "RISK-OWNER",
        "lastExcessValidationLod2Fullname": "LOD2-A",
        "lastExcessValidationLod2CreationDate": _iso_time(created + timedelta(days=1), 15),
        "lastExcessValidationLod2DecisionDetails": "reviewed",
        "lastExcessValidationLod2IsSatisfactory": not still_open,
        "closingConsDate": "" if still_open else close_day.isoformat(),
        "nbDaysFoFirstComment": 1,
        "totalNbDaysFo": 2,
        "avgNbDaysFo": 1.0,
        "nbDaysMmgFirstComment": 1,
        "nbDaysMmgLastComment": 1,
        "totalNbDaysMmg": 2,
        "avgNbDaysMmg": 1.0,
        "usage": "110%",
        "lastExplanationRequestDate": created.isoformat() if still_open else "",
        "nbDaysWaitingTrader": 1 if still_open else 0,
        "nbDaysWaitingMacc": 1 if still_open else 0,
        "delegationRisq": "RISK-DELEGATION",
        "closedManually": False,
        "LLM_Explanation_Cause": "machine tag",
        "LLM_Explanation_Solution": "machine tag",
    }


def _context(
    tmp_path: Path,
    sgmr_rows: list[dict[str, object]],
    excess_rows: list[dict[str, object]] | None = None,
) -> ToolContext:
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    risk_dir = source / "risk_metrics"
    risk_dir.mkdir(parents=True)
    workspace.mkdir()
    make_parquet(risk_dir / "sgmr.parquet", sgmr_rows)
    if excess_rows is not None:
        make_csv(risk_dir / "colibris.csv", excess_rows)
    return ToolContext(
        source_root=source,
        workspace_root=workspace,
        manifest=build_catalog(source),
    )


def _results(ctx: ToolContext) -> dict[str, object]:
    paths = [source.path for source in ctx.manifest.sources]
    return {result.name: result for result in RISK_METRICS_SKILL.run_analysis(ctx, paths)}


def test_finalized_two_file_contract_runs_as_one_skill(tmp_path: Path) -> None:
    day = date(2025, 1, 2)
    results = _results(_context(tmp_path, [_sgmr_row(day)], [_colibris_row(1, day)]))
    assert list(results) == [
        "risk_metrics_input_contract",
        "risk_metrics_data_integrity",
        "risk_limit_consumption",
        "risk_metric_dynamics",
        "risk_excess_workflow",
        "risk_cross_source_consistency",
    ]
    assert results["risk_metrics_input_contract"].flag_candidates == []
    reconciliation = results["risk_cross_source_consistency"].tables[0]
    assert reconciliation["event_to_sgmr_row_reconciliation"] == "UNRESOLVED"
    assert reconciliation["semantic_date_matches"] == 1


def test_directional_limit_breach_and_proximity_have_valid_locators(
    tmp_path: Path,
) -> None:
    start = date(2025, 1, 2)
    values = [8.0, 9.2, 9.5, 10.5, -11.0]
    rows = [
        _sgmr_row(start + timedelta(days=index), value=value) for index, value in enumerate(values)
    ]
    ctx = _context(tmp_path, rows, [_colibris_row(1, start)])
    results = _results(ctx)
    flags = results["risk_limit_consumption"].flag_candidates
    breach = next(flag for flag in flags if flag["kind"] == "limit_breach_population")
    proximity = next(flag for flag in flags if flag["kind"] == "repeated_limit_proximity")
    assert breach["breach_observations"] == 2
    assert breach["worst_utilization"] == 1.1
    assert proximity["streak_observations"] == 4
    for flag in (breach, proximity):
        validation = validate_locator(flag["locator"], ctx.source_root, ctx.manifest)
        assert validation.valid, validation.reason


def test_excess_recurrence_open_deadline_and_increase_consistency(
    tmp_path: Path,
) -> None:
    sgmr_day = date(2025, 1, 10)
    excesses = [
        _colibris_row(1, date(2025, 1, 1), still_open=True, increase_status="APPROVED"),
        _colibris_row(2, date(2025, 1, 2)),
        _colibris_row(3, date(2025, 1, 3)),
    ]
    ctx = _context(tmp_path, [_sgmr_row(sgmr_day)], excesses)
    flags = _results(ctx)["risk_excess_workflow"].flag_candidates
    kinds = {flag["kind"] for flag in flags}
    assert kinds >= {
        "repeated_excess_population",
        "open_excess_past_recorded_deadline",
        "limit_increase_status_without_increase_id",
    }
    for flag in flags:
        validation = validate_locator(flag["locator"], ctx.source_root, ctx.manifest)
        assert validation.valid, validation.reason


def test_sustained_metric_shift_is_deterministic_and_cited(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    rows = [
        _sgmr_row(start + timedelta(days=index), value=4.0 if index < 30 else 7.0)
        for index in range(60)
    ]
    ctx = _context(tmp_path, rows)
    first = _results(ctx)
    second = _results(ctx)
    assert [result.model_dump(mode="json") for result in first.values()] == [
        result.model_dump(mode="json") for result in second.values()
    ]
    flags = first["risk_metric_dynamics"].flag_candidates
    shift = next(flag for flag in flags if flag["kind"] == "sustained_risk_level_shift")
    validation = validate_locator(shift["locator"], ctx.source_root, ctx.manifest)
    assert validation.valid, validation.reason


def test_risk_overview_profiles_limit_utilization_trajectory(tmp_path: Path) -> None:
    start = date(2025, 1, 2)
    rows = [
        _sgmr_row(start + timedelta(days=index), value=value)
        for index, value in enumerate([8.0, 9.2, 10.5])
    ]
    overview = _results(_context(tmp_path, rows))["risk_limit_consumption"].overviews[0]

    assert overview.primary_for_deck
    assert overview.visual.kind == "line"
    assert [series.name for series in overview.visual.series] == [
        "Utilization",
        "Warning threshold",
        "Limit",
    ]
    assert [point.value for point in overview.visual.series[0].points] == [
        0.8,
        0.92,
        1.05,
    ]
    assert [(metric.label, metric.value) for metric in overview.metrics] == [
        ("Current utilization", "105.0%"),
        ("Worst utilization", "105.0%"),
        ("P95 utilization", "103.7%"),
        ("Breach observations", "1"),
    ]
    assert overview.evidence[0].locator.endswith("#rows=1:3")
