from __future__ import annotations

from pathlib import Path

from data_agent.skills.loader import discover_skills


def test_specialist_skill_metadata_is_preserved() -> None:
    skills = {skill.name: skill for skill in discover_skills(Path("skills"))}

    pnl = skills["pnl"]
    assert pnl.kind == "specialist-review"
    assert pnl.domain == "pnl"
    assert pnl.report_id == "PNL"
    assert pnl.label == "PnL"
    assert pnl.analysis_entrypoint == "scripts/analysis.py:run_analysis"
    assert set(pnl.source_domains) == {
        "pnl",
        "pnl_validation",
        "pnl_adjustments",
        "income_attribution",
    }


def test_non_specialist_skill_remains_loadable() -> None:
    skills = {skill.name: skill for skill in discover_skills(Path("skills"))}
    assert skills["lead-review"].kind == "lead-review"
    assert skills["lead-review"].domain is None
    assert skills["lead-review"].analysis_entrypoint == "scripts/analysis.py:run_analysis"
    assert skills["risk-ppt"].kind == "presentation"
    assert skills["risk-ppt"].domain is None
