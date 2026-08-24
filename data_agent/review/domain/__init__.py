"""Domain contracts: the internal Pydantic vocabulary of the review pipeline."""

from data_agent.review.domain.desk_context import (
    ControlDefinition,
    DeskContext,
    DeskFact,
    FactProvenance,
    RiskLimit,
)
from data_agent.review.domain.domains import (
    SOURCE_DOMAINS,
    SPECIALIST_DOMAINS,
    SpecialistDomain,
)
from data_agent.review.domain.evidence import (
    EvidenceReference,
    Locator,
    format_locator,
    parse_locator,
)
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.overview import (
    BarVisual,
    DataOverview,
    LineVisual,
    OverviewMetric,
    OverviewPoint,
    OverviewSeries,
    OverviewStatus,
    StackedBarVisual,
    TableVisual,
)
from data_agent.review.domain.reports import (
    CrossSourceCluster,
    FinalFinding,
    FinalReport,
    SpecialistReport,
)
from data_agent.review.domain.review import (
    CoverageError,
    CoverageStatus,
    ReviewRun,
    ReviewTask,
    RunContext,
    RunStatus,
    SourceCoverage,
)
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange, Source, SourceManifest, SourceType
from data_agent.review.domain.verification import (
    VerificationQuestion,
    VerifierDecision,
    VerifierResult,
)

__all__ = [
    "ControlDefinition",
    "CoverageError",
    "CoverageStatus",
    "CrossSourceCluster",
    "DateRange",
    "DeskContext",
    "DeskFact",
    "EvidenceReference",
    "FactProvenance",
    "FinalFinding",
    "FinalReport",
    "Finding",
    "DataOverview",
    "OverviewStatus",
    "OverviewMetric",
    "OverviewPoint",
    "OverviewSeries",
    "LineVisual",
    "BarVisual",
    "StackedBarVisual",
    "TableVisual",
    "Locator",
    "ReviewRun",
    "ReviewTask",
    "RunContext",
    "RiskLimit",
    "RunStatus",
    "Severity",
    "Source",
    "SourceCoverage",
    "SourceManifest",
    "SourceType",
    "SOURCE_DOMAINS",
    "SpecialistDomain",
    "SPECIALIST_DOMAINS",
    "SpecialistReport",
    "VerificationQuestion",
    "VerificationStatus",
    "VerifierDecision",
    "VerifierResult",
    "format_locator",
    "parse_locator",
]


