"""Schema recognition and guarded source loading for risk metrics."""

# ruff: noqa: F403, F405
from .shared import *
from fastmcp.exceptions import ToolError


def _classify(frame: pl.DataFrame) -> Role | None:
    columns = _normal_columns(frame)
    if columns >= SGMR_SIGNATURE:
        return "sgmr"
    if columns >= COLIBRIS_SIGNATURE:
        return "colibris"
    return None


def _norm(value: str) -> str:
    return " ".join(value.upper().split())


def _value(
    raw: dict[str, object], columns: dict[str, str], normalized_name: str
) -> object:
    column = columns.get(normalized_name)
    return None if column is None else raw.get(column)


def _load_sources(
    ctx: ToolContext, source_paths: list[str]
) -> tuple[list[SourceTable], list[dict[str, object]]]:
    tables: list[SourceTable] = []
    issues: list[dict[str, object]] = []
    for path in source_paths:
        try:
            source = ctx.manifest.by_path(path)
        except KeyError:
            issues.append({"kind": "source_not_in_manifest", "path": path})
            continue
        sheets: list[str | None] = list(source.sheet_names) or [None]
        for sheet in sheets:
            try:
                frame = load_table(ctx.source_root, path, sheet)
            except (FileNotFoundError, OSError, ValueError, ToolError) as exc:
                issues.append(
                    {
                        "kind": "unreadable_risk_metrics_table",
                        "path": path,
                        "sheet": sheet,
                        "detail": str(exc),
                    }
                )
                continue
            role = _classify(frame)
            if role is None:
                issues.append(
                    _flag(
                        "unrecognized_risk_metrics_table",
                        path,
                        sheet,
                        1,
                        columns=list(frame.columns),
                    )
                )
                continue
            expected = SGMR_REQUIRED if role == "sgmr" else COLIBRIS_REQUIRED
            missing = tuple(sorted(expected - _normal_columns(frame)))
            row_offset = tabular_row_offset(source.source_type)
            tables.append(
                SourceTable(
                    path=path,
                    sheet=sheet,
                    role=role,
                    frame=frame,
                    row_offset=row_offset,
                    missing_columns=missing,
                )
            )
            if missing:
                issues.append(
                    _flag(
                        "risk_metrics_schema_missing_columns",
                        path,
                        sheet,
                        1,
                        role=role,
                        missing_columns=list(missing),
                    )
                )
    return tables, issues


def _flat_hierarchy_issue(
    raw: dict[str, object], columns: dict[str, str]
) -> dict[str, list[str]] | None:
    flat_text = _text(_value(raw, columns, "flatstrana"))
    if not flat_text:
        return None
    try:
        flat = json.loads(flat_text)
    except (json.JSONDecodeError, TypeError):
        return {"invalid_json": [flat_text[:100]]}
    if not isinstance(flat, dict):
        return {"invalid_json_type": [type(flat).__name__]}
    mapping = {
        "BU": "stranabu",
        "SBU": "stranasbu",
        "GPC1": "stranagrppc1",
        "GPC2": "stranagrppc2",
        "GPC3": "stranagrppc3",
        "PC": "stranapc",
    }
    mismatches = [
        key
        for key, column in mapping.items()
        if key in flat
        and _norm(_text(flat.get(key))) != _norm(_text(_value(raw, columns, column)))
    ]
    return {"mismatched_levels": mismatches} if mismatches else None


def _sgmr_rows(
    tables: list[SourceTable],
) -> tuple[list[SgmrRow], list[dict[str, object]]]:
    parsed: list[SgmrRow] = []
    issues: list[dict[str, object]] = []
    for table in tables:
        if table.role != "sgmr" or table.missing_columns:
            continue
        columns = _column_map(table.frame)
        for raw in indexed_rows(table.frame, table.row_offset):
            row = int(str(raw["_source_row"]))
            limit_start = _date(_value(raw, columns, "limstartdate"))
            limit_end = _date(_value(raw, columns, "limenddate"))
            day = _date(_value(raw, columns, "consovaluedate"))
            created = _datetime(_value(raw, columns, "consocreationdate"))
            value = _float(_value(raw, columns, "consovalue"))
            lower_limit = _float(_value(raw, columns, "limminvalue"))
            upper_limit = _float(_value(raw, columns, "limmaxvalue"))
            version = _int(_value(raw, columns, "consoversion"))
            text_fields = {
                name: _text(_value(raw, columns, name))
                for name in (
                    "limid",
                    "limtype",
                    "limunit",
                    "rmriskindicator",
                    "rmriskmetricname",
                    "strananodename",
                    "stranapc",
                    "consoid",
                    "id",
                )
            }
            invalid: list[str] = []
            invalid.extend(name for name, value_ in text_fields.items() if not value_)
            if limit_start is None or limit_end is None:
                invalid.append("limStartDate/limEndDate")
            if day is None or created is None:
                invalid.append("consoValueDate/consoCreationDate")
            if value is None or lower_limit is None or upper_limit is None:
                invalid.append("consoValue/limMinValue/limMaxValue")
            if version is None:
                invalid.append("consoVersion")
            if invalid:
                issues.append(
                    _flag(
                        "invalid_sgmr_row",
                        table.path,
                        table.sheet,
                        row,
                        invalid_fields=invalid,
                    )
                )
                continue
            hierarchy_issue = _flat_hierarchy_issue(raw, columns)
            if hierarchy_issue:
                issues.append(
                    _flag(
                        "flat_hierarchy_mismatch",
                        table.path,
                        table.sheet,
                        row,
                        **hierarchy_issue,
                    )
                )
            assert limit_start is not None and limit_end is not None
            assert day is not None and created is not None and version is not None
            assert value is not None and lower_limit is not None and upper_limit is not None
            parsed.append(
                SgmrRow(
                    path=table.path,
                    sheet=table.sheet,
                    row=row,
                    limit_id=text_fields["limid"],
                    limit_type=text_fields["limtype"],
                    unit=text_fields["limunit"],
                    display_unit=_text(_value(raw, columns, "limdisplayunit")),
                    limit_start=limit_start,
                    limit_end=limit_end,
                    warning_threshold=_float(_value(raw, columns, "limrelativethreshold")),
                    request_owner=_text(_value(raw, columns, "limrequestowner")),
                    consumption_owner=_text(_value(raw, columns, "limconsumptionowner")),
                    delegation=_text(_value(raw, columns, "limdelegation")),
                    indicator=text_fields["rmriskindicator"],
                    metric_name=text_fields["rmriskmetricname"],
                    metric_type=_text(_value(raw, columns, "metrictype_lb")),
                    portfolio=text_fields["strananodename"],
                    pc=text_fields["stranapc"],
                    sbu=_text(_value(raw, columns, "stranasbu")),
                    bu=_text(_value(raw, columns, "stranabu")),
                    region=_text(_value(raw, columns, "geographicalzone_lb")),
                    risk_currency=_text(_value(raw, columns, "rmcurrency")),
                    underlying=(
                        _text(_value(raw, columns, "underlyings_lb"))
                        or _text(_value(raw, columns, "rmunderlyingname1"))
                        or _text(_value(raw, columns, "rmircurve1"))
                    ),
                    consumption_id=text_fields["consoid"],
                    record_id=text_fields["id"],
                    day=day,
                    last_day=_date(_value(raw, columns, "consolastvaluedate")),
                    created=created,
                    version=version,
                    official_stamp=_text(
                        _value(raw, columns, "consoofficialstampindic")
                    ),
                    value=value,
                    value_eur=_float(_value(raw, columns, "consovalueeur")),
                    lower_limit=lower_limit,
                    upper_limit=upper_limit,
                    initial_lower=_float(_value(raw, columns, "liminitialminvalue")),
                    initial_upper=_float(_value(raw, columns, "liminitialmaxvalue")),
                    temporary_lower=_float(_value(raw, columns, "limtempminvalue")),
                    temporary_upper=_float(_value(raw, columns, "limtempmaxvalue")),
                    frequency=_text(_value(raw, columns, "limfrequency")),
                )
            )
    return parsed, issues


def _excess_rows(
    tables: list[SourceTable],
) -> tuple[list[ExcessRow], list[dict[str, object]]]:
    parsed: list[ExcessRow] = []
    issues: list[dict[str, object]] = []
    for table in tables:
        if table.role != "colibris" or table.missing_columns:
            continue
        columns = _column_map(table.frame)
        for raw in indexed_rows(table.frame, table.row_offset):
            row = int(str(raw["_source_row"]))
            excess_id = _text(_value(raw, columns, "excessid"))
            created = _datetime(_value(raw, columns, "excesscreationdate"))
            value_day = _date(_value(raw, columns, "excesslastconsovaluedate"))
            value = _float(_value(raw, columns, "excesslastconsovalue"))
            limit_value = _float(_value(raw, columns, "limitvalue"))
            still_open = _bool(_value(raw, columns, "excessstillopen"))
            text_fields = {
                name: _text(_value(raw, columns, name))
                for name in (
                    "perimetermnemonic",
                    "riskindicator",
                    "riskmetricname",
                    "unit",
                    "excessworkflowstatus",
                )
            }
            invalid: list[str] = []
            if not excess_id:
                invalid.append("excessId")
            invalid.extend(name for name, value_ in text_fields.items() if not value_)
            if created is None or value_day is None:
                invalid.append("excessCreationDate/excessLastConsoValueDate")
            if value is None or limit_value in (None, 0.0):
                invalid.append("excessLastConsoValue/limitValue")
            if still_open is None:
                invalid.append("excessStillOpen")
            if invalid:
                issues.append(
                    _flag(
                        "invalid_colibris_row",
                        table.path,
                        table.sheet,
                        row,
                        invalid_fields=invalid,
                    )
                )
                continue
            assert created is not None and value_day is not None
            assert value is not None and limit_value is not None and still_open is not None
            parsed.append(
                ExcessRow(
                    path=table.path,
                    sheet=table.sheet,
                    row=row,
                    excess_id=excess_id,
                    created=created,
                    limit_type=_text(_value(raw, columns, "limittype")),
                    pc=text_fields["perimetermnemonic"],
                    perimeter_level=_text(_value(raw, columns, "perimeterlevel")),
                    sbu=_text(_value(raw, columns, "colibrissbu")),
                    indicator=text_fields["riskindicator"],
                    metric_name=text_fields["riskmetricname"],
                    risk_type=_text(_value(raw, columns, "risktype")),
                    scenario=_text(_value(raw, columns, "scenario")),
                    underlying=_text(_value(raw, columns, "underlying")),
                    value=value,
                    value_day=value_day,
                    limit_value=limit_value,
                    unit=text_fields["unit"],
                    still_open=still_open,
                    workflow_status=text_fields["excessworkflowstatus"],
                    max_usage_pct=_float(_value(raw, columns, "excessmaxusage")),
                    usage_pct=_percent(_value(raw, columns, "usage")),
                    creation_value=_float(_value(raw, columns, "creationconsvalue")),
                    creation_day=_date(_value(raw, columns, "creationconsdate")),
                    days_in_excess=_int(_value(raw, columns, "daysinexcess")),
                    days_without_validation=_int(
                        _value(raw, columns, "dayswithoutvalidationtotal")
                    ),
                    days_without_explanation=_int(
                        _value(raw, columns, "dayswithoutexplanation")
                    ),
                    close_time=_datetime(_value(raw, columns, "excessclosedate")),
                    closing_day=_date(_value(raw, columns, "closingconsdate")),
                    explanation_time=_datetime(
                        _value(raw, columns, "lastexcessexplanationcreationdate")
                    ),
                    explanation_cause=_text(
                        _value(raw, columns, "lastexcessexplanationcause")
                    ),
                    action_plan=_text(
                        _value(raw, columns, "lastexcessexplanationactionplan")
                    ),
                    action_deadline=_date(
                        _value(raw, columns, "lastexcessexplanationdeadline")
                    ),
                    solution=_text(_value(raw, columns, "lastexcessexplanationsolution")),
                    validation_time=_datetime(
                        _value(raw, columns, "lastexcessvalidationcreationdate")
                    ),
                    validation_classification=_text(
                        _value(raw, columns, "lastexcessvalidationclassification")
                    ),
                    validation_satisfactory=_bool(
                        _value(raw, columns, "lastexcessvalidationissatisfactory")
                    ),
                    technical_deadline=_date(
                        _value(raw, columns, "lastexcessvalidationtechnicaldeadline")
                    ),
                    lod2_time=_datetime(
                        _value(raw, columns, "lastexcessvalidationlod2creationdate")
                    ),
                    increase_id=_text(_value(raw, columns, "increaseid")),
                    increase_status=_text(_value(raw, columns, "increaseworkflowstatus")),
                    increase_created=_datetime(
                        _value(raw, columns, "increasecreationdate")
                    ),
                    increase_trader_approved=_datetime(
                        _value(raw, columns, "increasevalidationtrddircreationdate")
                    ),
                    increase_risk_approved=_datetime(
                        _value(raw, columns, "increasevalidationrisqcreationdate")
                    ),
                    sgmr_id=_text(_value(raw, columns, "sgmrid")),
                    consumption_owner=_text(_value(raw, columns, "consumptionowner")),
                    delegation=_text(_value(raw, columns, "limitdelegation")),
                    closed_manually=_bool(_value(raw, columns, "closedmanually")),
                )
            )
    return parsed, issues


def _input_contract(
    tables: list[SourceTable],
    load_issues: list[dict[str, object]],
    parse_issues: list[dict[str, object]],
    sgmr: list[SgmrRow],
    excesses: list[ExcessRow],
) -> AnalysisResult:
    flags = [*load_issues, *parse_issues]
    roles = Counter(table.role for table in tables)
    if not roles["sgmr"]:
        flags.append({"kind": "missing_sgmr_consumption_source"})
    if not roles["colibris"]:
        flags.append({"kind": "missing_colibris_excess_source"})
    source_tables: list[dict[str, object]] = [
        {
            "path": table.path,
            "sheet": table.sheet,
            "role": table.role,
            "rows": table.frame.height,
            "columns": len(table.frame.columns),
            "row_locator_offset": table.row_offset,
            "missing_required_columns": list(table.missing_columns),
        }
        for table in tables
    ]
    population = {
        "sgmr_rows": len(sgmr),
        "sgmr_dates": len({item.day for item in sgmr}),
        "sgmr_portfolios": len({item.portfolio for item in sgmr}),
        "sgmr_pcs": len({item.pc for item in sgmr}),
        "sgmr_metrics": sorted({item.indicator for item in sgmr}),
        "colibris_rows": len(excesses),
        "colibris_pcs": len({item.pc for item in excesses}),
        "colibris_metrics": sorted({item.indicator for item in excesses}),
    }
    return AnalysisResult(
        name="risk_metrics_input_contract",
        summary=(
            f"Classified {len(tables)} risk table(s): {roles['sgmr']} SGMR and "
            f"{roles['colibris']} Colibris; parsed {len(sgmr)} consumption row(s) and "
            f"{len(excesses)} excess row(s), with {len(flags)} input candidate(s)."
        ),
        tables=[*source_tables, population],
        flag_candidates=flags[:MAX_FLAGS],
    )


def _duplicates(values: list[str]) -> set[str]:
    counts = Counter(values)
    return {value for value, count in counts.items() if value and count > 1}
