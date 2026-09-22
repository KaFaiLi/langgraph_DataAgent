"""Deployment must discover one host-selected skill tree without legacy initialization."""

from __future__ import annotations

import subprocess
import sys

from data_agent.config import Settings
from data_agent.skills.paths import default_skills_root


def test_cli_import_does_not_initialize_legacy_review_workflows():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import data_agent.cli; "
                "assert 'data_agent.review.service' not in sys.modules; "
                "assert 'data_agent.review.orchestration.graph' not in sys.modules; "
                "assert 'data_agent.review.orchestration.specialist.graph' not in sys.modules"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_explicit_deployed_skills_are_used_by_shared_lead_operations(tmp_path):
    import shutil

    import pytest

    from data_agent.skills.review import load_lead_review_skill
    from data_agent.tools.review_operations import analyze_reports

    root = tmp_path / "deployed-skills"
    shutil.copytree(default_skills_root() / "lead-review", root / "lead-review")
    settings = Settings(_env_file=None, skills_dir=str(root))
    assert settings.skills_path == root
    definition = load_lead_review_skill(skills_root=settings.skills_path)
    assert definition.analysis_file.is_relative_to(root)
    definition.analysis_file.write_text(
        'def run_analysis(reports):\n    raise RuntimeError("deployed lead selected")\n'
    )
    with pytest.raises(RuntimeError, match="deployed lead selected"):
        analyze_reports([], skills_root=settings.skills_path)


def test_default_skill_root_contains_deployable_review_contracts():
    root = default_skills_root()
    assert root.is_absolute()
    for name in ("risk-metrics", "pnl", "post-trade-controls", "risk-commentary", "lead-review"):
        assert (root / name / "SKILL.md").is_file()
        assert (root / name / "references" / "dataset.md").is_file()
        assert (root / name / "references" / "policy.md").is_file()
        assert (root / name / "scripts" / "analysis.py").is_file()
