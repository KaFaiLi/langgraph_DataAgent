"""Risk input integrity checks."""

# ruff: noqa: F403, F405
from .limits import _close
from .shared import *
from .sources import _duplicates, _norm


def _data_integrity(sgmr: list[SgmrRow], excesses: list[ExcessRow]) -> AnalysisResult:
    flags: list[dict[str, object]] = []
    conso_duplicates = _duplicates([item.consumption_id for item in sgmr])
    record_duplicates = _duplicates([item.record_id for item in sgmr])
    excess_duplicates = _duplicates([item.excess_id for item in excesses])
    business_keys: dict[tuple[dt.date, str, str, str, int], list[SgmrRow]] = defaultdict(list)
    for item in sgmr:
        business_keys[
            (item.day, item.limit_id, item.portfolio, item.indicator, item.version)
        ].append(item)
    duplicate_keys = [rows for rows in business_keys.values() if len(rows) > 1]
    for duplicate_set, kind, attr in (
        (conso_duplicates, "duplicate_sgmr_consumption_id", "consumption_id"),
        (record_duplicates, "duplicate_sgmr_record_id", "record_id"),
    ):
        for duplicate in sorted(duplicate_set):
            item = next(row for row in sgmr if getattr(row, attr) == duplicate)
            flags.append(_flag(kind, item.path, item.sheet, item.row, duplicated_value=duplicate))
    for rows in duplicate_keys:
        item = rows[0]
        flags.append(
            _flag(
                "duplicate_sgmr_business_key",
                item.path,
                item.sheet,
                item.row,
                date=item.day.isoformat(),
                limit_id=item.limit_id,
                portfolio=item.portfolio,
                indicator=item.indicator,
                version=item.version,
                duplicate_rows=len(rows),
                locators=[_locator(row.path, row.sheet, row.row) for row in rows],
            )
        )
    for duplicate in sorted(excess_duplicates):
        excess_item = next(row for row in excesses if row.excess_id == duplicate)
        flags.append(
            _flag(
                "duplicate_colibris_excess_id",
                excess_item.path,
                excess_item.sheet,
                excess_item.row,
                excess_id=duplicate,
            )
        )

    all_dates = {item.day for item in sgmr}
    series: dict[tuple[str, str, str, int], list[SgmrRow]] = defaultdict(list)
    for item in sgmr:
        series[(item.limit_id, item.portfolio, item.indicator, item.version)].append(item)
        if item.limit_start > item.limit_end:
            flags.append(
                _flag(
                    "invalid_limit_date_range",
                    item.path,
                    item.sheet,
                    item.row,
                    limit_id=item.limit_id,
                    start=item.limit_start.isoformat(),
                    end=item.limit_end.isoformat(),
                )
            )
        creation_lag = (item.created.date() - item.day).days
        if creation_lag < 0:
            flags.append(
                _flag(
                    "sgmr_creation_before_value_date",
                    item.path,
                    item.sheet,
                    item.row,
                    value_date=item.day.isoformat(),
                    creation_date=item.created.date().isoformat(),
                    calendar_lag_days=creation_lag,
                )
            )
        if item.last_day is not None:
            previous_lag = (item.day - item.last_day).days
            if previous_lag <= 0 or previous_lag > 7:
                flags.append(
                    _flag(
                        "sgmr_previous_value_date_gap",
                        item.path,
                        item.sheet,
                        item.row,
                        value_date=item.day.isoformat(),
                        last_value_date=item.last_day.isoformat(),
                        calendar_gap_days=previous_lag,
                    )
                )
        if (
            "EUR" in _norm(item.unit)
            and item.value_eur is not None
            and not _close(item.value, item.value_eur)
        ):
            flags.append(
                _flag(
                    "sgmr_eur_value_mismatch",
                    item.path,
                    item.sheet,
                    item.row,
                    unit=item.unit,
                    value=item.value,
                    value_eur=item.value_eur,
                )
            )
    coverage_rows: list[dict[str, object]] = []
    for key, rows in sorted(series.items()):
        dates = {item.day for item in rows}
        coverage = len(dates) / len(all_dates) if all_dates else 0.0
        item = min(rows, key=lambda row: (row.day, row.row))
        coverage_rows.append(
            {
                "limit_id": key[0],
                "portfolio": key[1],
                "indicator": key[2],
                "version": key[3],
                "rows": len(rows),
                "dates": len(dates),
                "population_dates": len(all_dates),
                "coverage": round(coverage, 4),
            }
        )
        if coverage < 0.95:
            flags.append(
                _flag(
                    "incomplete_sgmr_series_coverage",
                    item.path,
                    item.sheet,
                    item.row,
                    limit_id=item.limit_id,
                    portfolio=item.portfolio,
                    indicator=item.indicator,
                    observed_dates=len(dates),
                    population_dates=len(all_dates),
                    coverage=round(coverage, 4),
                )
            )

    portfolio_mappings: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)
    portfolio_examples: dict[str, SgmrRow] = {}
    for item in sgmr:
        portfolio_mappings[item.portfolio].add((item.bu, item.sbu, item.pc, item.risk_currency))
        portfolio_examples.setdefault(item.portfolio, item)
    for portfolio, mappings in sorted(portfolio_mappings.items()):
        if len(mappings) <= 1:
            continue
        item = portfolio_examples[portfolio]
        flags.append(
            _flag(
                "sgmr_portfolio_mapping_change",
                item.path,
                item.sheet,
                item.row,
                portfolio=portfolio,
                mappings=[list(mapping) for mapping in sorted(mappings)],
            )
        )

    metric_map: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for item in sgmr:
        metric_map[_norm(item.indicator)].add((item.metric_name, item.metric_type))
    tables: list[dict[str, object]] = [
        {
            "sgmr_rows": len(sgmr),
            "unique_consumption_ids": len({item.consumption_id for item in sgmr}),
            "unique_record_ids": len({item.record_id for item in sgmr}),
            "duplicate_business_keys": len(duplicate_keys),
            "date_start": min((item.day for item in sgmr), default=None),
            "date_end": max((item.day for item in sgmr), default=None),
            "creation_lag_days_min": min(
                ((item.created.date() - item.day).days for item in sgmr), default=None
            ),
            "creation_lag_days_mean": (
                round(
                    statistics.fmean((item.created.date() - item.day).days for item in sgmr),
                    4,
                )
                if sgmr
                else None
            ),
            "creation_lag_days_max": max(
                ((item.created.date() - item.day).days for item in sgmr), default=None
            ),
            "colibris_rows": len(excesses),
            "unique_excess_ids": len({item.excess_id for item in excesses}),
        },
        {
            "metric_mappings": [
                {
                    "indicator": indicator,
                    "metric_names_and_types": [list(value) for value in sorted(values)],
                }
                for indicator, values in sorted(metric_map.items())
            ]
        },
        *coverage_rows,
    ]
    return AnalysisResult(
        name="risk_metrics_data_integrity",
        summary=(
            f"Checked identifiers, business keys, dates, processing lags, hierarchy "
            f"mappings, EUR values, and {len(series)} series population(s); "
            f"{len(flags)} integrity candidate(s)."
        ),
        tables=tables,
        flag_candidates=flags[:MAX_FLAGS],
    )
