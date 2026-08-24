"""Desk context: shared immutable desk background + deterministic enrichment."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.desk_context import (
    DeskContext,
    DeskFact,
    FactProvenance,
    RiskLimit,
)
from data_agent.review.domain.evidence import EvidenceReference, Locator, format_locator
from data_agent.review.domain.source import Source, SourceManifest
from data_agent.review.ingestion.evidence_validator import (
    EvidenceDisposition,
    EvidenceValidator,
)
from data_agent.review.orchestration.state import ParentState
from data_agent.tools.analysis_helpers import tabular_row_offset
from data_agent.tools.review_context import ToolContext, source_file
from data_agent.tools.tabular_helpers import (
    floats,
    load_frame,
)

_LIMIT_METRICS = ("var", "svar", "exposure")
MAX_DESK_TEXT_FACTS = 100


def _ctx(state: ParentState) -> ToolContext:
    manifest = SourceManifest.model_validate(state["manifest"])
    return ToolContext(
        source_root=Path(state["source_root"]),
        workspace_root=Path(state["output_dir"]) / "workspace",
        manifest=manifest,
    )


def _desk_template(config: RunnableConfig) -> DeskContext:
    template = (config or {}).get("configurable", {}).get("desk_template")
    if template is None:
        raise RuntimeError(
            "parent graph requires config['configurable']['desk_template'] "
            "(a DeskContext or its dict dump)"
        )
    if isinstance(template, DeskContext):
        return template
    return DeskContext.model_validate(template)


def _desk_text_facts(ctx: ToolContext, source: Source) -> list[DeskFact]:
    """Extract exact bullet facts from dedicated desk-context text sources."""
    normalized = source.path.replace("\\", "/")
    if not normalized.casefold().startswith("desk_context/"):
        return []
    path = source_file(ctx, source.path)
    if path.suffix.casefold() not in {".md", ".markdown", ".txt"}:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    facts: list[DeskFact] = []
    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped.startswith(("- ", "* ")):
            continue
        statement = stripped[2:].strip()
        if not statement:
            continue
        locator = format_locator(Locator(path=source.path, lines=(line_number, line_number)))
        facts.append(
            DeskFact(
                fact_id=f"FACT-{source.source_id}-line-{line_number}",
                statement=statement,
                provenance=FactProvenance.SOURCE_BACKED,
                evidence=[EvidenceReference(locator=locator, quote=statement)],
            )
        )
        if len(facts) >= MAX_DESK_TEXT_FACTS:
            break
    return facts


def build_desk_context(state: ParentState, config: RunnableConfig) -> dict:
    """Build the shared DeskContext and enrich it deterministically.

    Enrichment (code only, no LLM): every source exposing a limit column
    yields a versioned RiskLimit entry (max observed value over the source's
    date range) and a SOURCE_BACKED desk fact citing the exact row where the
    maximum occurs. INFERRED/UNKNOWN facts are never promoted.
    """
    desk = _desk_template(config).model_copy(deep=True)
    ctx = _ctx(state)
    validator = EvidenceValidator.source_backed(ctx.source_root, ctx.manifest)

    for source in ctx.manifest.sources:
        desk.source_backed_facts.extend(_desk_text_facts(ctx, source))
        frame = load_frame(ctx, source.path)
        if frame is None or not source.column_names:
            continue
        limit_column = next(
            (c for c in frame.columns if c.lower() in {"limit", "var_limit", "exposure_limit"}),
            None,
        )
        if limit_column is None:
            continue
        try:
            values = floats(frame[limit_column])
        except (TypeError, ValueError):
            continue
        if not values:
            continue
        maximum = max(values)
        max_index = values.index(maximum)
        physical_row = max_index + tabular_row_offset(source.source_type)
        rows = f"{physical_row}:{physical_row}"
        locator = format_locator(Locator(path=source.path, rows=(physical_row, physical_row)))
        desk.limits.append(
            RiskLimit(
                limit_id=f"LIM-{source.source_id}",
                name=f"{limit_column} limit from {source.source_id}",
                metric=limit_column,
                value=maximum,
                unit="units",
                effective_from=source.date_range.start if source.date_range else None,
                effective_to=source.date_range.end if source.date_range else None,
            )
        )
        desk.source_backed_facts.append(
            DeskFact(
                fact_id=f"FACT-{source.source_id}-limit",
                statement=(
                    f"{source.source_id} ({source.path}) defines a {limit_column!r} "
                    f"limit column; its maximum value over the file is {maximum} "
                    f"at rows {rows}."
                ),
                provenance=FactProvenance.SOURCE_BACKED,
                evidence=[EvidenceReference(locator=locator)],
            )
        )

    retained_facts: list[DeskFact] = []
    fatal_details: list[str] = []
    for fact in desk.source_backed_facts:
        validation = validator.validate_references(fact.evidence)
        if validation.valid:
            retained_facts.append(fact)
            continue
        fatal = [
            failure
            for failure in validation.failures
            if failure.disposition is EvidenceDisposition.FATAL
        ]
        if fatal:
            fatal_details.append(
                "; ".join(f"{failure.locator}: {failure.reason}" for failure in fatal)
            )
            continue
        failures = "; ".join(
            f"{failure.locator}: {failure.reason}" for failure in validation.failures
        )
        desk.unresolved_items.append(
            f"{fact.fact_id}: source-backed fact withheld because evidence is unavailable: "
            f"{failures}"
        )
    desk.source_backed_facts = retained_facts
    if fatal_details:
        return {
            "status": "failed",
            "failure_reason": "fatal evidence integrity failure while building desk context: "
            + "\n".join(fatal_details),
        }

    context_path = Path(state["output_dir"]) / "desk_context.json"
    context_path.write_text(
        json.dumps(desk.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    return {"desk_context": desk.model_dump(mode="json")}
