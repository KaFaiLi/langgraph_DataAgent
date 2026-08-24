"""Contracts for trusted analytical-skill discovery and registration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from data_agent.review.domain.domains import SPECIALIST_DOMAINS, SpecialistDomain
from data_agent.skills.review import (
    SkillLoadError,
    discover_skills,
    load_analysis_runner,
    load_lead_review_skill,
    load_skill,
)
from data_agent.skills.registry import SPECIALISTS, specialist_domain_for


def test_repository_analytical_skills_are_discovered() -> None:
    definitions = discover_skills()

    assert [definition.domain for definition in definitions] == [
        SpecialistDomain.PNL,
        SpecialistDomain.POST_TRADE_CONTROLS,
        SpecialistDomain.RISK_COMMENTARY,
        SpecialistDomain.RISK_METRICS,
    ]
    assert all(definition.analysis_file.is_file() for definition in definitions)
    assert all(definition.instructions for definition in definitions)
    assert all(definition.verifier_policy for definition in definitions)


def test_repository_lead_review_skill_is_loaded() -> None:
    definition = load_lead_review_skill()

    assert definition.name == "lead-review"
    assert definition.label == "Lead Review"
    assert definition.analysis_file.is_file()
    assert definition.analysis_function == "run_analysis"
    assert "Required reconciliations" in definition.instructions
    assert "PASS" in definition.verifier_policy


def test_lead_review_prompts_are_loaded_from_the_skill() -> None:
    from data_agent.review.synthesis.lead_review import LEAD_REVIEW_SYSTEM
    from data_agent.review.synthesis.lead_verifier import LEAD_VERIFIER_SYSTEM

    definition = load_lead_review_skill()

    assert LEAD_REVIEW_SYSTEM == definition.instructions
    assert LEAD_VERIFIER_SYSTEM == definition.verifier_policy


def test_lead_review_loader_rejects_missing_verifier_policy(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skill_root = skills_root / "lead-review"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "analysis.py").write_text("def run_analysis(reports): return {}\n", encoding="utf-8")
    skill_file = skill_root / "SKILL.md"
    skill_file.write_text(
        """---
name: lead-review
description: Test lead review.
metadata:
  kind: lead-review
  label: Lead Review
  analysis_entrypoint: scripts/analysis.py:run_analysis
---
# Lead review
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillLoadError, match="policy.md is required"):
        load_lead_review_skill(skill_file, skills_root=skills_root)


def test_registry_uses_one_composite_pnl_specialist() -> None:
    assert tuple(SPECIALISTS) == SPECIALIST_DOMAINS
    assert set(SPECIALISTS) == {
        SpecialistDomain.RISK_METRICS,
        SpecialistDomain.PNL,
        SpecialistDomain.POST_TRADE_CONTROLS,
        SpecialistDomain.RISK_COMMENTARY,
    }
    assert all(registration.skill for registration in SPECIALISTS.values())

    pnl = SPECIALISTS[SpecialistDomain.PNL]
    assert pnl.source_domains == (
        SpecialistDomain.PNL,
        SpecialistDomain.PNL_VALIDATION,
        SpecialistDomain.PNL_ADJUSTMENTS,
        SpecialistDomain.INCOME_ATTRIBUTION,
    )
    assert specialist_domain_for(SpecialistDomain.PNL_VALIDATION) is SpecialistDomain.PNL
    assert specialist_domain_for(SpecialistDomain.PNL_ADJUSTMENTS) is SpecialistDomain.PNL
    assert specialist_domain_for(SpecialistDomain.INCOME_ATTRIBUTION) is SpecialistDomain.PNL


def test_loader_rejects_entrypoint_escape(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skill_root = skills_root / "bad-skill"
    skill_root.mkdir(parents=True)
    (tmp_path / "outside.py").write_text("def run_analysis(ctx, paths): return []\n")
    skill_file = skill_root / "SKILL.md"
    skill_file.write_text(
        """---
name: bad-skill
description: Invalid test skill.
metadata:
  kind: specialist-review
  domain: pnl
  report_id: BAD
  label: Bad Skill
  analysis_entrypoint: ../../outside.py:run_analysis
---
# Invalid
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillLoadError, match="contained relative path"):
        load_skill(skill_file, skills_root=skills_root)


def test_loader_rejects_duplicate_domain(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    for name in ("first", "second"):
        skill_root = skills_root / name
        (skill_root / "scripts").mkdir(parents=True)
        (skill_root / "scripts" / "analysis.py").write_text(
            "def run_analysis(ctx, paths): return []\n", encoding="utf-8"
        )
        (skill_root / "SKILL.md").write_text(
            f"""---
name: {name}
description: Duplicate-domain test skill.
metadata:
  kind: specialist-review
  domain: pnl
  report_id: {name.upper()}
  label: {name.title()}
  analysis_entrypoint: scripts/analysis.py:run_analysis
---
# Test
""",
            encoding="utf-8",
        )

    with pytest.raises(SkillLoadError, match="duplicate specialist skill domain"):
        discover_skills(skills_root)


def test_loader_rejects_duplicate_source_domain_owner(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    for name, domain in (("first", "pnl"), ("second", "risk_metrics")):
        skill_root = skills_root / name
        (skill_root / "scripts").mkdir(parents=True)
        (skill_root / "scripts" / "analysis.py").write_text(
            "def run_analysis(ctx, paths): return []\n", encoding="utf-8"
        )
        (skill_root / "SKILL.md").write_text(
            f"""---
name: {name}
description: Duplicate-source-domain test skill.
metadata:
  kind: specialist-review
  domain: {domain}
  source_domains:
    - {domain}
    - pnl_validation
  report_id: {name.upper()}
  label: {name.title()}
  analysis_entrypoint: scripts/analysis.py:run_analysis
---
# Test
""",
            encoding="utf-8",
        )

    with pytest.raises(SkillLoadError, match="duplicate specialist skill source domain"):
        discover_skills(skills_root)


def test_loader_supports_contained_relative_imports(tmp_path: Path) -> None:
    """A skill entrypoint can keep its implementation in a sibling package."""
    skills_root = tmp_path / "skills"
    skill_root = skills_root / "relative-skill"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "payload.py").write_text("def result() -> int:\n    return 37\n", encoding="utf-8")
    (scripts / "analysis.py").write_text(
        "from .payload import result\n\n"
        "def run_analysis(ctx, source_paths):\n"
        "    return [result()]\n",
        encoding="utf-8",
    )
    skill_file = skill_root / "SKILL.md"
    skill_file.write_text(
        """---
name: relative-skill
description: Relative-import test skill.
metadata:
  kind: specialist-review
  domain: pnl
  report_id: RELATIVE
  label: Relative Skill
  analysis_entrypoint: scripts/analysis.py:run_analysis
---
# Relative imports
""",
        encoding="utf-8",
    )

    runner = load_analysis_runner(load_skill(skill_file, skills_root=skills_root))

    assert runner(None, []) == [37]  # type: ignore[arg-type]


def test_loader_caches_relative_runner_when_loaded_in_parallel(tmp_path: Path) -> None:
    """Parallel specialist startup reuses one contained runner without global path changes."""
    skills_root = tmp_path / "skills"
    skill_root = skills_root / "parallel-skill"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "value.py").write_text("VALUE = 11\n", encoding="utf-8")
    (scripts / "analysis.py").write_text(
        "from .value import VALUE\n\ndef run_analysis(ctx, source_paths):\n    return [VALUE]\n",
        encoding="utf-8",
    )
    skill_file = skill_root / "SKILL.md"
    skill_file.write_text(
        """---
name: parallel-skill
description: Parallel relative-import test skill.
metadata:
  kind: specialist-review
  domain: pnl
  report_id: PARALLEL
  label: Parallel Skill
  analysis_entrypoint: scripts/analysis.py:run_analysis
---
# Parallel relative imports
""",
        encoding="utf-8",
    )
    definition = load_skill(skill_file, skills_root=skills_root)

    with ThreadPoolExecutor(max_workers=4) as executor:
        runners = list(executor.map(lambda _: load_analysis_runner(definition), range(8)))

    assert all(runner(None, []) == [11] for runner in runners)  # type: ignore[arg-type]
    assert len({id(runner) for runner in runners}) == 1


def test_loader_rejects_symlinked_relative_import_escape(tmp_path: Path) -> None:
    """A relative import cannot escape a skill through a linked Python file."""
    skills_root = tmp_path / "skills"
    skill_root = skills_root / "linked-skill"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")
    linked_payload = scripts / "payload.py"
    try:
        linked_payload.symlink_to(outside)
    except OSError as exc:  # pragma: no cover - depends on Windows symlink policy.
        pytest.skip(f"symlink creation unavailable: {exc}")
    (scripts / "analysis.py").write_text(
        "from .payload import VALUE\n\ndef run_analysis(ctx, source_paths):\n    return [VALUE]\n",
        encoding="utf-8",
    )
    skill_file = skill_root / "SKILL.md"
    skill_file.write_text(
        """---
name: linked-skill
description: Symlink containment test skill.
metadata:
  kind: specialist-review
  domain: pnl
  report_id: LINKED
  label: Linked Skill
  analysis_entrypoint: scripts/analysis.py:run_analysis
---
# Linked import
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillLoadError, match="Python file escapes"):
        load_analysis_runner(load_skill(skill_file, skills_root=skills_root))
