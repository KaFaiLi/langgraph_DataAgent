# ruff: noqa: F401
"""Shared typed models, schema constants, and safely reusable helpers for PnL checks.

This trusted entrypoint owns schema-specific computation only. LangGraph owns execution,
LLMs interpret the returned candidates, and source access remains guarded by ToolContext.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Literal, Protocol

import polars as pl
from pydantic import BaseModel

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference, Locator, format_locator
from data_agent.review.domain.overview import (
    BarVisual,
    DataOverview,
    LineVisual,
    OverviewMetric,
    OverviewPoint,
    OverviewSeries,
    OverviewStatus,
    TableVisual,
)
from data_agent.tools.analysis_helpers import (
    bool_value,
    column_map,
    date_value,
    datetime_value,
    float_value,
    indexed_rows,
    normalized_columns,
    tabular_row_offset,
    text_value,
)
from data_agent.tools.analysis_helpers import (
    candidate_flag as _flag,
)
from data_agent.tools.analysis_helpers import (
    row_locator as _locator,
)
from data_agent.tools.review_context import ToolContext
from data_agent.tools.statistics_tools import zscore
from data_agent.tools.tabular_tools import load_table

Role = Literal[
    "pnl",
    "adjustment",
    "validation",
    "income_attribution",
    "income_attribution_legacy",
]

PNL_COLUMNS = {
    "value date",
    "version",
    "bu",
    "sbu",
    "gpc1",
    "gpc2",
    "gpc3",
    "pc",
    "ggop",
    "gop",
    "ptf",
    "notion",
    "region",
    "currency",
    "dtd",
    "wtd",
    "mtd",
    "qtd",
    "ytd",
}
ADJUSTMENT_COLUMNS = {
    "adjustmentid",
    "gop",
    "ptf",
    "ccy",
    "amount",
    "amountineur",
    "comments",
    "creationdate",
    "valdatebegin",
    "valdateend",
    "sbu",
    "pc",
    "nature",
    "adjustmentlinkid",
    "instrument",
    "filepath",
    "jedaiid",
    "jedaiidlink",
    "folder",
    "source",
    "region",
    "pnlcomponent",
    "craftindicator",
    "dealid",
    "securityid",
    "ccypair",
    "exchangerate",
    "pnltype",
    "tpr",
    "natureid",
    "type",
    "typo",
    "macrotypo",
    "endevent",
    "macroname",
    "macrolog",
    "incidentid",
    "documentid",
    "adjustmentsource",
    "rccode",
    "cpmimpact",
}
VALIDATION_COLUMNS = {
    "gop",
    "team",
    "state",
    "creationtime",
    "active",
    "user",
    "api_request_date",
    "pnltype",
}
INCOME_ATTRIBUTION_COLUMNS = {
    "asofdate",
    "gop",
    "final result acc dtd",
}
LEGACY_INCOME_ATTRIBUTION_COLUMNS = {"driver", "pnl_musd"}

# The export contains both parent and leaf attribution columns.  These are the
# reported primary buckets used for the concentration view; leaf columns are
# retained in the schema contract and are not silently added to their parents.
INCOME_PRIMARY_COMPONENTS = (
    "Unexplained",
    "Market Effect",
    "FX",
    "Fees non transactional",
    "Fees non transactional.1",
    "Fees transactional",
    "Fees non transactional.2",
    "Fees non transactional.3",
    "Theta/FIN",
    "Theta/FIN_L2",
    "Theta",
    "FIN",
    "N&M",
    "RP",
    "Other Exp",
    "Other Non Market",
    "Other",
    "EDM/EDMN",
    "Profit Sharing",
    "Other NTX",
    "Other S/F",
    "ia_not_relevant",
    "ia_not_running",
    "No IA",
    "hypo_pnl_dtd",
)
INCOME_RESIDUAL_COMPONENTS = {
    "unexplained",
    "ia_not_relevant",
    "ia_not_running",
    "no ia",
    "other",
    "other non market",
    "other ntx",
    "other s/f",
}
INCOME_HIERARCHY_COLUMNS = (
    "bu",
    "sbu",
    "grppc100",
    "grppc200",
    "grppc300",
    "td",
    "pc",
    "ggop",
    "gop",
)

MAX_FLAGS = 50
MIN_PATTERN_ROWS = 20
OUTLIER_Z = 3.0
REVERSAL_Z = 2.0
REVERSAL_RATIO_MIN = 0.5
REVERSAL_RATIO_MAX = 1.5
STREAK_MIN = 5
MONTH_END_RATIO = 2.0
ADJUSTMENT_OUTLIER_Z = 2.5
ADJUSTMENT_REVERSAL_DAYS = 5
ADJUSTMENT_REVERSAL_RATIO_MIN = 0.8
ADJUSTMENT_REVERSAL_RATIO_MAX = 1.25
SERIES_COVERAGE_MIN = 0.95


class _EvidenceRow(Protocol):
    @property
    def path(self) -> str: ...

    @property
    def sheet(self) -> str | None: ...

    @property
    def row(self) -> int: ...


@dataclass(frozen=True)
class SourceTable:
    path: str
    sheet: str | None
    role: Role
    frame: pl.DataFrame
    row_offset: int


@dataclass(frozen=True)
class PnlRow:
    path: str
    sheet: str | None
    row: int
    day: dt.date
    version: str
    notion: str
    ptf: str
    gop: str
    pc: str
    currency: str
    dtd: float
    wtd: float
    mtd: float
    qtd: float
    ytd: float


@dataclass(frozen=True)
class AdjustmentRow:
    path: str
    sheet: str | None
    row: int
    adjustment_id: str
    gop: str
    ptf: str
    pc: str
    currency: str
    amount: float
    amount_eur: float
    exchange_rate: float
    value_start: dt.date
    value_end: dt.date
    creation_date: dt.date
    source: str
    nature: str
    component: str
    link_id: str
    comment: str


@dataclass(frozen=True)
class ValidationRow:
    path: str
    sheet: str | None
    row: int
    gop: str
    team: str
    state: str
    created: dt.datetime
    request_date: dt.date
    pnl_type: str
    active: bool


@dataclass(frozen=True)
class IncomeAttributionRow:
    """One parsed row from the wide AIR income-attribution export."""

    path: str
    sheet: str | None
    row: int
    day: dt.date
    entity: tuple[str, ...]
    components: dict[str, float]
    cumulative: dict[str, float]
    total: float
    status: str
    validated: str
    mpc_status: str
    fo_status: str
    batch_validated: bool | None


__all__ = (
    "dt", "hashlib", "Counter", "defaultdict", "Sequence", "dataclass", "mean", "pstdev",
    "Literal", "Protocol", "pl", "BaseModel", "AnalysisResult", "SpecialistDomain",
    "EvidenceReference", "Locator", "format_locator", "BarVisual", "DataOverview", "LineVisual",
    "OverviewMetric", "OverviewPoint", "OverviewSeries", "OverviewStatus", "TableVisual",
    "bool_value", "column_map", "date_value", "datetime_value", "float_value", "indexed_rows",
    "normalized_columns", "tabular_row_offset", "text_value", "_flag", "_locator", "ToolContext",
    "zscore", "load_table", "Role", "PNL_COLUMNS", "ADJUSTMENT_COLUMNS", "VALIDATION_COLUMNS",
    "INCOME_ATTRIBUTION_COLUMNS", "LEGACY_INCOME_ATTRIBUTION_COLUMNS", "INCOME_PRIMARY_COMPONENTS",
    "INCOME_RESIDUAL_COMPONENTS", "INCOME_HIERARCHY_COLUMNS", "MAX_FLAGS", "MIN_PATTERN_ROWS",
    "OUTLIER_Z", "REVERSAL_Z", "REVERSAL_RATIO_MIN", "REVERSAL_RATIO_MAX", "STREAK_MIN",
    "MONTH_END_RATIO", "ADJUSTMENT_OUTLIER_Z", "ADJUSTMENT_REVERSAL_DAYS",
    "ADJUSTMENT_REVERSAL_RATIO_MIN", "ADJUSTMENT_REVERSAL_RATIO_MAX", "SERIES_COVERAGE_MIN",
    "_EvidenceRow", "SourceTable", "PnlRow", "AdjustmentRow", "ValidationRow",
    "IncomeAttributionRow",
)
