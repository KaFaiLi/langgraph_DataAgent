"""Shared typed models, schema constants, and safely reusable risk-check helpers.

This trusted entrypoint owns schema-specific computation only. LangGraph owns execution,
LLMs interpret returned candidates, and source access remains guarded by ToolContext.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import polars as pl
from pydantic import BaseModel

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference, Locator, format_locator
from data_agent.review.domain.overview import (
    DataOverview,
    LineVisual,
    OverviewMetric,
    OverviewPoint,
    OverviewSeries,
    OverviewStatus,
)
from data_agent.tools.analysis_helpers import (
    bool_value as _bool,
)
from data_agent.tools.analysis_helpers import (
    candidate_flag as _flag,
)
from data_agent.tools.analysis_helpers import (
    column_map as _column_map,
)
from data_agent.tools.analysis_helpers import (
    date_value as _date,
)
from data_agent.tools.analysis_helpers import (
    datetime_value as _datetime,
)
from data_agent.tools.analysis_helpers import (
    float_value as _float,
)
from data_agent.tools.analysis_helpers import (
    indexed_rows,
    tabular_row_offset,
)
from data_agent.tools.analysis_helpers import (
    int_value as _int,
)
from data_agent.tools.analysis_helpers import (
    normalized_columns as _normal_columns,
)
from data_agent.tools.analysis_helpers import (
    percent_value as _percent,
)
from data_agent.tools.analysis_helpers import (
    row_locator as _locator,
)
from data_agent.tools.analysis_helpers import (
    text_value as _text,
)
from data_agent.tools.review_context import ToolContext
from data_agent.tools.statistics_tools import (
    percent_change,
    quantile,
    rolling_std,
    trend_analysis,
    zscore,
)
from data_agent.tools.tabular_tools import load_table

Role = Literal["sgmr", "colibris"]

SGMR_SIGNATURE = {
    "limid",
    "rmriskindicator",
    "rmriskmetricname",
    "strananodename",
    "consovalue",
    "consovaluedate",
    "limmaxvalue",
    "limminvalue",
}
SGMR_REQUIRED = SGMR_SIGNATURE | {
    "limtype",
    "limunit",
    "limstartdate",
    "limenddate",
    "limdisplayunit",
    "liminitialminvalue",
    "liminitialmaxvalue",
    "limtempminvalue",
    "limtempmaxvalue",
    "limrelativethreshold",
    "limfrequency",
    "limconsumptionowner",
    "limrequestowner",
    "limdelegation",
    "consoid",
    "id",
    "consovalueeur",
    "consolastvaluedate",
    "consocreationdate",
    "consoversion",
    "consoofficialstampindic",
    "stranabu",
    "stranasbu",
    "stranagrppc1",
    "stranagrppc2",
    "stranagrppc3",
    "stranapc",
    "flatstrana",
    "rmcurrency",
    "geographicalzone_lb",
    "metrictype_lb",
}

COLIBRIS_SIGNATURE = {
    "excessid",
    "excesscreationdate",
    "perimetermnemonic",
    "riskindicator",
    "excesslastconsovalue",
    "excesslastconsovaluedate",
    "limitvalue",
    "excessworkflowstatus",
}
COLIBRIS_REQUIRED = COLIBRIS_SIGNATURE | {
    "limittype",
    "unit",
    "excessstillopen",
    "riskmetricname",
    "excessmaxusage",
    "creationconsvalue",
    "creationconsdate",
    "daysinexcess",
    "dayswithoutvalidationtotal",
    "dayswithoutexplanation",
    "excessclosedate",
    "closingconsdate",
    "lastexcessexplanationcreationdate",
    "lastexcessexplanationcause",
    "lastexcessexplanationactionplan",
    "lastexcessexplanationdeadline",
    "lastexcessexplanationsolution",
    "lastexcessvalidationcreationdate",
    "lastexcessvalidationclassification",
    "lastexcessvalidationissatisfactory",
    "lastexcessvalidationtechnicaldeadline",
    "lastexcessvalidationlod2creationdate",
    "increaseid",
    "increaseworkflowstatus",
    "increasecreationdate",
    "increasevalidationtrddircreationdate",
    "increasevalidationrisqcreationdate",
    "usage",
    "sgmrid",
    "colibrissbu",
    "consumptionowner",
    "limitdelegation",
    "closedmanually",
    "llm_explanation_cause",
    "llm_explanation_solution",
}

MAX_FLAGS = 50
MIN_SERIES_ROWS = 20
NEAR_LIMIT_DEFAULT = 0.90
NEAR_LIMIT_STREAK = 3
OUTLIER_Z = 3.0
DAILY_CHANGE_THRESHOLD = 0.25
SUSTAINED_SHIFT_WINDOW = 20
SUSTAINED_SHIFT_PCT = 0.20
SUSTAINED_SHIFT_EFFECT = 2.5
VOLATILITY_REGIME_CHANGE = 0.50
TREND_PERIOD_CHANGE = 0.20
FLOAT_TOLERANCE = 1e-8


@dataclass(frozen=True)
class SourceTable:
    path: str
    sheet: str | None
    role: Role
    frame: pl.DataFrame
    row_offset: int
    missing_columns: tuple[str, ...]


@dataclass(frozen=True)
class SgmrRow:
    path: str
    sheet: str | None
    row: int
    limit_id: str
    limit_type: str
    unit: str
    display_unit: str
    limit_start: dt.date
    limit_end: dt.date
    warning_threshold: float | None
    request_owner: str
    consumption_owner: str
    delegation: str
    indicator: str
    metric_name: str
    metric_type: str
    portfolio: str
    pc: str
    sbu: str
    bu: str
    region: str
    risk_currency: str
    underlying: str
    consumption_id: str
    record_id: str
    day: dt.date
    last_day: dt.date | None
    created: dt.datetime
    version: int
    official_stamp: str
    value: float
    value_eur: float | None
    lower_limit: float
    upper_limit: float
    initial_lower: float | None
    initial_upper: float | None
    temporary_lower: float | None
    temporary_upper: float | None
    frequency: str


@dataclass(frozen=True)
class ExcessRow:
    path: str
    sheet: str | None
    row: int
    excess_id: str
    created: dt.datetime
    limit_type: str
    pc: str
    perimeter_level: str
    sbu: str
    indicator: str
    metric_name: str
    risk_type: str
    scenario: str
    underlying: str
    value: float
    value_day: dt.date
    limit_value: float
    unit: str
    still_open: bool
    workflow_status: str
    max_usage_pct: float | None
    usage_pct: float | None
    creation_value: float | None
    creation_day: dt.date | None
    days_in_excess: int | None
    days_without_validation: int | None
    days_without_explanation: int | None
    close_time: dt.datetime | None
    closing_day: dt.date | None
    explanation_time: dt.datetime | None
    explanation_cause: str
    action_plan: str
    action_deadline: dt.date | None
    solution: str
    validation_time: dt.datetime | None
    validation_classification: str
    validation_satisfactory: bool | None
    technical_deadline: dt.date | None
    lod2_time: dt.datetime | None
    increase_id: str
    increase_status: str
    increase_created: dt.datetime | None
    increase_trader_approved: dt.datetime | None
    increase_risk_approved: dt.datetime | None
    sgmr_id: str
    consumption_owner: str
    delegation: str
    closed_manually: bool | None


__all__ = (
    "COLIBRIS_REQUIRED",
    "COLIBRIS_SIGNATURE",
    "DAILY_CHANGE_THRESHOLD",
    "FLOAT_TOLERANCE",
    "MAX_FLAGS",
    "MIN_SERIES_ROWS",
    "NEAR_LIMIT_DEFAULT",
    "NEAR_LIMIT_STREAK",
    "OUTLIER_Z",
    "SGMR_REQUIRED",
    "SGMR_SIGNATURE",
    "SUSTAINED_SHIFT_EFFECT",
    "SUSTAINED_SHIFT_PCT",
    "SUSTAINED_SHIFT_WINDOW",
    "TREND_PERIOD_CHANGE",
    "VOLATILITY_REGIME_CHANGE",
    "AnalysisResult",
    "BaseModel",
    "Callable",
    "Counter",
    "DataOverview",
    "EvidenceReference",
    "ExcessRow",
    "LineVisual",
    "Literal",
    "Locator",
    "OverviewMetric",
    "OverviewPoint",
    "OverviewSeries",
    "OverviewStatus",
    "Role",
    "Sequence",
    "SgmrRow",
    "SourceTable",
    "SpecialistDomain",
    "ToolContext",
    "_bool",
    "_column_map",
    "_date",
    "_datetime",
    "_flag",
    "_float",
    "_int",
    "_locator",
    "_normal_columns",
    "_percent",
    "_text",
    "dataclass",
    "defaultdict",
    "dt",
    "format_locator",
    "hashlib",
    "indexed_rows",
    "json",
    "load_table",
    "percent_change",
    "pl",
    "quantile",
    "rolling_std",
    "statistics",
    "tabular_row_offset",
    "trend_analysis",
    "zscore",
)
