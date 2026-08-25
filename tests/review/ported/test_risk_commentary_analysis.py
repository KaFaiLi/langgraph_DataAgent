"""Deterministic tests for the skill-backed risk-commentary runner."""

from __future__ import annotations

from pathlib import Path

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.ingestion.catalog import build_catalog
from data_agent.skills.registry import get_specialist
from data_agent.skills.review import load_analysis_runner
from data_agent.tools.review_context import ToolContext


def _context(tmp_path: Path) -> tuple[ToolContext, str]:
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    commentary = source / "risk_commentary"
    commentary.mkdir(parents=True)
    workspace.mkdir()
    relative = "risk_commentary/quarterly_review.md"
    records = [
        (
            '- [C1] — Alert: "Evidence ID: certification:1 Error Message: '
            "threshold exceeded Comment: No material change, within tolerance. "
            'Managerial Validation Comment: pending"'
        ),
        (
            '- [C2] — Alert: "Evidence ID: certification:2 Error Message: No data '
            "Comment: Booking system delay caused late capture. "
            'Managerial Validation Comment: No data"'
        ),
        (
            '- [C3] — Alert: "Evidence ID: certification:3 Error Message: No data '
            "Comment: Booking system delay caused late capture. "
            'Managerial Validation Comment: validated"'
        ),
        (
            '- [C4] — Alert: "Evidence ID: certification:4 Error Message: No data '
            "Comment: Booking system delay caused late capture. "
            'Managerial Validation Comment: pending"'
        ),
    ]
    (source / relative).write_text(
        "# Quarterly Review\n\n## Sources\n" + "\n".join(records) + "\n",
        encoding="utf-8",
    )
    return (
        ToolContext(
            source_root=source,
            workspace_root=workspace,
            manifest=build_catalog(source),
        ),
        relative,
    )


def test_skill_runner_profiles_commentary_and_retains_exact_locators(
    tmp_path: Path,
) -> None:
    ctx, path = _context(tmp_path)
    registration = get_specialist(SpecialistDomain.RISK_COMMENTARY)
    runner = load_analysis_runner(registration.skill)

    results = {result.name: result for result in runner(ctx, [path])}

    assert set(results) == {
        "commentary_extract_population",
        "commentary_validation_gaps",
        "commentary_internal_consistency",
        "commentary_repeated_explanations",
        "commentary_normalized_reassurance_claims",
    }
    population = results["commentary_extract_population"].tables[0]
    assert population["quoted_source_records"] == 4
    overview = results["commentary_extract_population"].overviews[0]
    assert overview.overview_id == "risk-commentary.extract-coverage"
    assert overview.primary_for_deck is True
    assert overview.visual is not None
    assert overview.visual.kind == "table"
    assert overview.visual.rows == [["risk_commentary/quarterly_review.md", "7", "4", "4", "3"]]
    assert {metric.label: metric.value for metric in overview.metrics} == {
        "Extracts": "1",
        "Quoted records": "4",
        "Unique evidence IDs": "4",
        "Validation gaps": "3",
    }
    assert overview.source_locators == ["source://risk_commentary/quarterly_review.md#lines=1:7"]
    contradiction = results["commentary_internal_consistency"].flag_candidates[0]
    assert contradiction["evidence_id"] == "certification:1"
    assert contradiction["locator"] == ("source://risk_commentary/quarterly_review.md#lines=4:4")
    repeated = results["commentary_repeated_explanations"].flag_candidates[0]
    assert repeated["unique_evidence_records"] == 3


def test_skill_runner_is_deterministic(tmp_path: Path) -> None:
    ctx, path = _context(tmp_path)
    registration = get_specialist(SpecialistDomain.RISK_COMMENTARY)
    assert registration.skill is not None
    runner = load_analysis_runner(registration.skill)

    first = [result.model_dump(mode="json") for result in runner(ctx, [path])]
    second = [result.model_dump(mode="json") for result in runner(ctx, [path])]

    assert first == second
