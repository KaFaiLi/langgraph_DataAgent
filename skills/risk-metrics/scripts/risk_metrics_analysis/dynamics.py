"""Comparable risk-metric dynamics checks."""

from .limits import _series_key
from .shared import *
from .sources import _norm


def _sustained_shift(values: list[float]) -> tuple[int, float, float] | None:
    window = SUSTAINED_SHIFT_WINDOW
    if len(values) < window * 2:
        return None
    best: tuple[int, float, float] | None = None
    best_score = -1.0
    for index in range(window, len(values) - window + 1):
        before = values[index - window : index]
        after = values[index : index + window]
        mean_before = statistics.fmean(before)
        mean_after = statistics.fmean(after)
        if mean_before == 0:
            continue
        pct = (mean_after - mean_before) / abs(mean_before)
        pooled = (statistics.pstdev(before) + statistics.pstdev(after)) / 2
        effect = abs(mean_after - mean_before) / pooled if pooled > 0 else float("inf")
        score = abs(pct) * effect
        if (
            abs(pct) >= SUSTAINED_SHIFT_PCT
            and effect >= SUSTAINED_SHIFT_EFFECT
            and score > best_score
        ):
            best = (index, pct, effect)
            best_score = score
    return best


def _metric_dynamics(sgmr: list[SgmrRow]) -> AnalysisResult:
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    series: dict[tuple[str, str, str, str, str, int], list[SgmrRow]] = defaultdict(list)
    for item in sgmr:
        series[_series_key(item)].append(item)
    paired: dict[tuple[str, str, str, dt.date], dict[str, float]] = defaultdict(dict)
    paired_rows: dict[tuple[str, str, str, dt.date], dict[str, SgmrRow]] = defaultdict(dict)
    for key, raw_rows in sorted(series.items()):
        rows = sorted(raw_rows, key=lambda item: (item.day, item.row))
        values = [item.value for item in rows]
        for item in rows:
            paired[(item.portfolio, item.pc, item.unit, item.day)][_norm(item.indicator)] = (
                item.value
            )
            paired_rows[(item.portfolio, item.pc, item.unit, item.day)][_norm(item.indicator)] = (
                item
            )
        if len(values) < MIN_SERIES_ROWS:
            continue
        average = statistics.fmean(values)
        deviation = statistics.pstdev(values)
        scores = zscore(values)
        worst_outlier = max(range(len(scores)), key=lambda index: abs(scores[index]))
        changes = percent_change(values)
        change_indices = [index for index, value in enumerate(changes) if value is not None]
        largest_change = (
            max(change_indices, key=lambda index: abs(changes[index] or 0.0))
            if change_indices
            else None
        )
        shift = _sustained_shift(values)
        rolling = [value for value in rolling_std(values, 20) if value is not None]
        volatility_change: float | None = None
        if len(rolling) >= 20:
            split = len(rolling) // 2
            first = statistics.fmean(rolling[:split])
            second = statistics.fmean(rolling[split:])
            volatility_change = None if first == 0 else (second - first) / first
        trend = trend_analysis(values)
        projected_change = None if average == 0 else trend.slope * (len(values) - 1) / abs(average)
        tables.append(
            {
                "table_type": "metric_series",
                "limit_id": key[0],
                "portfolio": key[1],
                "pc": key[2],
                "indicator": key[3],
                "metric_name": key[4],
                "version": key[5],
                "unit": rows[-1].unit,
                "rows": len(rows),
                "date_start": rows[0].day,
                "date_end": rows[-1].day,
                "min": round(min(values), 6),
                "mean": round(average, 6),
                "max": round(max(values), 6),
                "stdev": round(deviation, 6),
                "trend_slope_per_observation": round(trend.slope, 8),
                "trend_r_squared": round(trend.r_squared, 4),
                "projected_period_change": (
                    round(projected_change, 4) if projected_change is not None else None
                ),
                "rolling_volatility_half_change": (
                    round(volatility_change, 4) if volatility_change is not None else None
                ),
            }
        )
        if abs(scores[worst_outlier]) > OUTLIER_Z:
            item = rows[worst_outlier]
            flags.append(
                _flag(
                    "risk_metric_outlier",
                    item.path,
                    item.sheet,
                    item.row,
                    portfolio=item.portfolio,
                    indicator=item.indicator,
                    metric_name=item.metric_name,
                    date=item.day.isoformat(),
                    value=item.value,
                    z_score=round(scores[worst_outlier], 4),
                )
            )
        if (
            largest_change is not None
            and abs(changes[largest_change] or 0.0) >= DAILY_CHANGE_THRESHOLD
        ):
            item = rows[largest_change]
            previous = rows[largest_change - 1]
            flags.append(
                _flag(
                    "large_daily_risk_change",
                    item.path,
                    item.sheet,
                    item.row,
                    portfolio=item.portfolio,
                    indicator=item.indicator,
                    date=item.day.isoformat(),
                    prior_date=previous.day.isoformat(),
                    prior_value=previous.value,
                    value=item.value,
                    percent_change=round(changes[largest_change] or 0.0, 4),
                    prior_locator=_locator(previous.path, previous.sheet, previous.row),
                )
            )
        if shift is not None:
            index, pct, effect = shift
            item = rows[index]
            flags.append(
                _flag(
                    "sustained_risk_level_shift",
                    item.path,
                    item.sheet,
                    item.row,
                    portfolio=item.portfolio,
                    indicator=item.indicator,
                    date=item.day.isoformat(),
                    window_observations=SUSTAINED_SHIFT_WINDOW,
                    mean_change=round(pct, 4),
                    standardized_effect=round(effect, 4),
                )
            )
        if volatility_change is not None and abs(volatility_change) >= VOLATILITY_REGIME_CHANGE:
            item = rows[len(rows) // 2]
            flags.append(
                _flag(
                    "risk_volatility_regime_change",
                    item.path,
                    item.sheet,
                    item.row,
                    portfolio=item.portfolio,
                    indicator=item.indicator,
                    comparison_date=item.day.isoformat(),
                    rolling_20_observation_volatility_change=round(volatility_change, 4),
                )
            )
        if (
            projected_change is not None
            and abs(projected_change) >= TREND_PERIOD_CHANGE
            and trend.r_squared >= 0.6
        ):
            item = rows[-1]
            flags.append(
                _flag(
                    "persistent_risk_trend",
                    item.path,
                    item.sheet,
                    item.row,
                    portfolio=item.portfolio,
                    indicator=item.indicator,
                    period_start=rows[0].day.isoformat(),
                    period_end=item.day.isoformat(),
                    projected_period_change=round(projected_change, 4),
                    r_squared=round(trend.r_squared, 4),
                    start_locator=_locator(rows[0].path, rows[0].sheet, rows[0].row),
                )
            )

    scopes: dict[tuple[str, str, str], list[tuple[dt.date, dict[str, SgmrRow]]]] = defaultdict(list)
    for (portfolio, pc, unit, day), metrics in paired_rows.items():
        if {"EXPOSURE", "STRESS TEST", "VAR"} <= set(metrics):
            scopes[(portfolio, pc, unit)].append((day, metrics))
    for (portfolio, pc, unit), observations in sorted(scopes.items()):
        ordered = sorted(observations, key=lambda item: item[0])
        if len(ordered) < 40:
            continue
        window = min(20, len(ordered) // 2)

        def window_mean(values: list[tuple[dt.date, dict[str, SgmrRow]]], metric: str) -> float:
            return statistics.fmean(item[1][metric].value for item in values)

        first_window = ordered[:window]
        last_window = ordered[-window:]
        exposure_start = window_mean(first_window, "EXPOSURE")
        exposure_end = window_mean(last_window, "EXPOSURE")
        stress_start = window_mean(first_window, "STRESS TEST")
        stress_end = window_mean(last_window, "STRESS TEST")
        var_start = window_mean(first_window, "VAR")
        var_end = window_mean(last_window, "VAR")
        if min(exposure_start, stress_start, var_start) <= 0:
            continue
        exposure_growth = exposure_end / exposure_start
        stress_growth = stress_end / stress_start
        var_change = abs(var_end - var_start) / abs(var_start)
        if exposure_growth < 2.0 or stress_growth < 1.5 or var_change > 0.2:
            continue
        first_metrics = first_window[0][1]
        last_metrics = last_window[-1][1]
        exposure = last_metrics["EXPOSURE"]
        flags.append(
            _flag(
                "factor_concentration_diverges_from_headline_var",
                exposure.path,
                exposure.sheet,
                exposure.row,
                portfolio=portfolio,
                pc=pc,
                unit=unit,
                underlying=exposure.underlying,
                risk_currency=exposure.risk_currency,
                period_start=first_window[0][0].isoformat(),
                period_end=last_window[-1][0].isoformat(),
                exposure_start_mean=round(exposure_start, 6),
                exposure_end_mean=round(exposure_end, 6),
                exposure_growth=round(exposure_growth, 4),
                stress_start_mean=round(stress_start, 6),
                stress_end_mean=round(stress_end, 6),
                stress_growth=round(stress_growth, 4),
                var_start_mean=round(var_start, 6),
                var_end_mean=round(var_end, 6),
                var_absolute_change_share=round(var_change, 4),
                severity_floor=(
                    "high"
                    if exposure_growth >= 4.0 and stress_growth >= 2.0 and var_change <= 0.1
                    else "medium"
                ),
                severity_basis=(
                    "multi-fold component exposure and stress growth with stable "
                    "headline VaR is a material concentration/representation divergence"
                ),
                severity_match_terms=["exposure", "stress", "var"],
                measured_observation=True,
                exposure_start_locator=_locator(
                    first_metrics["EXPOSURE"].path,
                    first_metrics["EXPOSURE"].sheet,
                    first_metrics["EXPOSURE"].row,
                ),
                stress_end_locator=_locator(
                    last_metrics["STRESS TEST"].path,
                    last_metrics["STRESS TEST"].sheet,
                    last_metrics["STRESS TEST"].row,
                ),
                var_end_locator=_locator(
                    last_metrics["VAR"].path,
                    last_metrics["VAR"].sheet,
                    last_metrics["VAR"].row,
                ),
                detail=(
                    "comparable exposure and stress series increased materially while "
                    "headline VaR stayed within a 20% band; metrics were not added"
                ),
            )
        )

    ratios: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (portfolio, pc, unit, _), paired_values in paired.items():
        var = paired_values.get("VAR")
        if var in (None, 0.0):
            continue
        if "SVAR" in paired_values:
            ratios[(portfolio, pc, unit)]["svar_to_var"].append(paired_values["SVAR"] / var)
        if "STRESS TEST" in paired_values:
            ratios[(portfolio, pc, unit)]["stress_to_var"].append(
                paired_values["STRESS TEST"] / var
            )
    for ratio_key, ratio_values in sorted(ratios.items()):
        tables.append(
            {
                "table_type": "paired_metric_relationship",
                "portfolio": ratio_key[0],
                "pc": ratio_key[1],
                "unit": ratio_key[2],
                "svar_to_var_median": (
                    round(statistics.median(ratio_values["svar_to_var"]), 4)
                    if ratio_values["svar_to_var"]
                    else None
                ),
                "svar_to_var_pairs": len(ratio_values["svar_to_var"]),
                "stress_to_var_median": (
                    round(statistics.median(ratio_values["stress_to_var"]), 4)
                    if ratio_values["stress_to_var"]
                    else None
                ),
                "stress_to_var_pairs": len(ratio_values["stress_to_var"]),
                "interpretation": "descriptive only; methodology comparability required",
            }
        )
    return AnalysisResult(
        name="risk_metric_dynamics",
        summary=(
            f"Screened {len(series)} portfolio/metric series and aligned metric ratios "
            f"without summing non-additive risk; {len(flags)} dynamics candidate(s)."
        ),
        tables=tables,
        flag_candidates=flags[:MAX_FLAGS],
    )
