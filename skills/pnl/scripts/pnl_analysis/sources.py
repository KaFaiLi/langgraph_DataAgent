"""Schema recognition, guarded loading, and typed row parsing for the PnL skill."""

# ruff: noqa: F403, F405
from .shared import *
from fastmcp.exceptions import ToolError


def _classify(frame: pl.DataFrame) -> Role | None:
    columns = normalized_columns(frame)
    if columns >= INCOME_ATTRIBUTION_COLUMNS:
        return "income_attribution"
    if columns >= LEGACY_INCOME_ATTRIBUTION_COLUMNS:
        return "income_attribution_legacy"
    if columns >= PNL_COLUMNS:
        return "pnl"
    if columns >= ADJUSTMENT_COLUMNS:
        return "adjustment"
    if columns >= VALIDATION_COLUMNS:
        return "validation"
    return None


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
                        "kind": "unreadable_pnl_table",
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
                        "unrecognized_pnl_table",
                        path,
                        sheet,
                        1,
                        columns=list(frame.columns),
                    )
                )
                continue
            tables.append(
                SourceTable(
                    path=path,
                    sheet=sheet,
                    role=role,
                    frame=frame,
                    row_offset=tabular_row_offset(source.source_type),
                )
            )
    return tables, issues


def _pnl_rows(
    tables: list[SourceTable],
) -> tuple[list[PnlRow], list[dict[str, object]]]:
    parsed: list[PnlRow] = []
    issues: list[dict[str, object]] = []
    for table in tables:
        if table.role != "pnl":
            continue
        columns = column_map(table.frame)
        for raw in indexed_rows(table.frame, table.row_offset):
            row = int(str(raw["_source_row"]))
            day = date_value(raw.get(columns["value date"]))
            values = [
                float_value(raw.get(columns[name]))
                for name in ("dtd", "wtd", "mtd", "qtd", "ytd")
            ]
            keys = {
                name: text_value(raw.get(columns[name]))
                for name in ("version", "notion", "ptf", "gop", "pc", "currency")
            }
            problems = []
            if day is None:
                problems.append("Value Date")
            if any(value is None for value in values):
                problems.append("DTD/WTD/MTD/QTD/YTD")
            problems.extend(name for name, value in keys.items() if not value)
            if problems:
                issues.append(
                    _flag(
                        "invalid_pnl_row",
                        table.path,
                        table.sheet,
                        row,
                        invalid_fields=problems,
                    )
                )
                continue
            dtd, wtd, mtd, qtd, ytd = values
            assert day is not None
            assert dtd is not None
            assert wtd is not None
            assert mtd is not None
            assert qtd is not None
            assert ytd is not None
            parsed.append(
                PnlRow(
                    path=table.path,
                    sheet=table.sheet,
                    row=row,
                    day=day,
                    version=keys["version"],
                    notion=keys["notion"],
                    ptf=keys["ptf"],
                    gop=keys["gop"],
                    pc=keys["pc"],
                    currency=keys["currency"],
                    dtd=float(dtd),
                    wtd=float(wtd),
                    mtd=float(mtd),
                    qtd=float(qtd),
                    ytd=float(ytd),
                )
            )
    return parsed, issues


def _adjustment_rows(
    tables: list[SourceTable],
) -> tuple[list[AdjustmentRow], list[dict[str, object]]]:
    parsed: list[AdjustmentRow] = []
    issues: list[dict[str, object]] = []
    for table in tables:
        if table.role != "adjustment":
            continue
        columns = column_map(table.frame)
        for raw in indexed_rows(table.frame, table.row_offset):
            row = int(str(raw["_source_row"]))
            amount = float_value(raw.get(columns["amount"]))
            amount_eur = float_value(raw.get(columns["amountineur"]))
            rate = float_value(raw.get(columns["exchangerate"]))
            value_start = date_value(raw.get(columns["valdatebegin"]))
            value_end = date_value(raw.get(columns["valdateend"]))
            created = date_value(raw.get(columns["creationdate"]))
            keys = {
                name: text_value(raw.get(columns[name]))
                for name in ("adjustmentid", "gop", "ptf", "pc", "ccy")
            }
            problems = [name for name, value in keys.items() if not value]
            if amount is None or amount_eur is None or rate is None:
                problems.append("AMOUNT/AMOUNTINEUR/EXCHANGERATE")
            if value_start is None or value_end is None or created is None:
                problems.append("VALDATEBEGIN/VALDATEEND/CREATIONDATE")
            if problems:
                issues.append(
                    _flag(
                        "invalid_adjustment_row",
                        table.path,
                        table.sheet,
                        row,
                        invalid_fields=problems,
                    )
                )
                continue
            assert amount is not None and amount_eur is not None and rate is not None
            assert value_start is not None and value_end is not None and created is not None
            parsed.append(
                AdjustmentRow(
                    path=table.path,
                    sheet=table.sheet,
                    row=row,
                    adjustment_id=keys["adjustmentid"],
                    gop=keys["gop"],
                    ptf=keys["ptf"],
                    pc=keys["pc"],
                    currency=keys["ccy"],
                    amount=amount,
                    amount_eur=amount_eur,
                    exchange_rate=rate,
                    value_start=value_start,
                    value_end=value_end,
                    creation_date=created,
                    source=text_value(raw.get(columns["source"])),
                    nature=text_value(raw.get(columns["nature"])),
                    component=text_value(raw.get(columns["pnlcomponent"])),
                    link_id=text_value(raw.get(columns["adjustmentlinkid"])),
                    comment=text_value(raw.get(columns["comments"])),
                )
            )
    return parsed, issues


def _validation_rows(
    tables: list[SourceTable],
) -> tuple[list[ValidationRow], list[dict[str, object]]]:
    parsed: list[ValidationRow] = []
    issues: list[dict[str, object]] = []
    for table in tables:
        if table.role != "validation":
            continue
        columns = column_map(table.frame)
        for raw in indexed_rows(table.frame, table.row_offset):
            row = int(str(raw["_source_row"]))
            created = datetime_value(raw.get(columns["creationtime"]))
            request_date = date_value(raw.get(columns["api_request_date"]))
            active = bool_value(raw.get(columns["active"]))
            keys = {
                name: text_value(raw.get(columns[name]))
                for name in ("gop", "team", "state", "pnltype")
            }
            problems = [name for name, value in keys.items() if not value]
            if created is None or request_date is None:
                problems.append("creationTime/api_request_date")
            if active is None:
                problems.append("active")
            if problems:
                issues.append(
                    _flag(
                        "invalid_validation_row",
                        table.path,
                        table.sheet,
                        row,
                        invalid_fields=problems,
                    )
                )
                continue
            assert created is not None and request_date is not None and active is not None
            parsed.append(
                ValidationRow(
                    path=table.path,
                    sheet=table.sheet,
                    row=row,
                    gop=keys["gop"],
                    team=keys["team"],
                    state=keys["state"],
                    created=created,
                    request_date=request_date,
                    pnl_type=keys["pnltype"],
                    active=active,
                )
            )
    return parsed, issues


def _income_attribution_rows(
    tables: list[SourceTable],
) -> tuple[list[IncomeAttributionRow], list[dict[str, object]]]:
    """Parse the wide AIR attribution export without double-counting its hierarchy."""
    parsed: list[IncomeAttributionRow] = []
    issues: list[dict[str, object]] = []
    for table in tables:
        if table.role != "income_attribution":
            continue
        columns = column_map(table.frame)
        component_columns = {
            name: columns[name.lower()]
            for name in INCOME_PRIMARY_COMPONENTS
            if name.lower() in columns
        }
        cumulative_columns = {
            name: columns[f"{name.lower()} cumulative"]
            for name in INCOME_PRIMARY_COMPONENTS
            if f"{name.lower()} cumulative" in columns
        }
        total_column = columns["final result acc dtd"]
        cumulative_total_column = columns.get("final result acc dtd cumulative")
        for raw in indexed_rows(table.frame, table.row_offset):
            row_number = int(str(raw["_source_row"]))
            day = date_value(raw.get(columns["asofdate"]))
            total = float_value(raw.get(total_column))
            entity = tuple(text_value(raw.get(columns[name])) for name in INCOME_HIERARCHY_COLUMNS)
            problems = []
            if day is None:
                problems.append("asofdate")
            if total is None:
                problems.append("Final Result Acc DTD")
            if not entity[-1]:
                problems.append("gop")
            if problems:
                issues.append(
                    _flag(
                        "invalid_income_attribution_row",
                        table.path,
                        table.sheet,
                        row_number,
                        invalid_fields=problems,
                    )
                )
                continue
            assert day is not None and total is not None
            components = {
                name: value
                for name, column in component_columns.items()
                if (value := float_value(raw.get(column))) is not None
            }
            cumulative = {
                name: value
                for name, column in cumulative_columns.items()
                if (value := float_value(raw.get(column))) is not None
            }
            if cumulative_total_column is not None:
                cumulative_total = float_value(raw.get(cumulative_total_column))
                if cumulative_total is not None:
                    cumulative["Final Result Acc DTD"] = cumulative_total
            batch_validated = (
                bool_value(raw.get(columns["isbatchvalidated"]))
                if "isbatchvalidated" in columns
                else None
            )
            parsed.append(
                IncomeAttributionRow(
                    path=table.path,
                    sheet=table.sheet,
                    row=row_number,
                    day=day,
                    entity=entity,
                    components=components,
                    cumulative=cumulative,
                    total=float(total),
                    status=text_value(raw.get(columns["status"]))
                    if "status" in columns
                    else "",
                    validated=text_value(raw.get(columns["validated"]))
                    if "validated" in columns
                    else "",
                    mpc_status=text_value(raw.get(columns["air_mpc_validation_status"]))
                    if "air_mpc_validation_status" in columns
                    else "",
                    fo_status=text_value(raw.get(columns["air_fo_validation status"]))
                    if "air_fo_validation status" in columns
                    else "",
                    batch_validated=batch_validated,
                )
            )
    return parsed, issues


