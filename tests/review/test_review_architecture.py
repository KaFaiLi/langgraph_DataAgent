"""Architecture gates for the shared-tool and skill-only review design."""

from pathlib import Path

from data_agent.review.ingestion.catalog import build_catalog
from data_agent.skills.registry import SPECIALISTS
from data_agent.tools.source_tools import discover_sources


def test_tools_and_skills_have_one_package_each() -> None:
    assert not list(Path("data_agent/review/tools").glob("*.py"))
    assert not list(Path("data_agent/mcp_server/tools").glob("*.py"))
    assert not list(Path("data_agent/review/skills").glob("*.py"))
    assert Path("data_agent/tools/source_tools.py").is_file()
    assert Path("data_agent/tools/research.py").is_file()
    assert Path("data_agent/skills/review.py").is_file()


def test_command_line_interface_has_one_owner() -> None:
    assert Path("data_agent/cli.py").is_file()
    assert not Path("data_agent/agent/cli.py").exists()
    assert not Path("data_agent/review/cli.py").exists()


def test_review_catalog_maps_shared_source_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "risk.csv").write_text("date,value\n2025-01-02,1\n2025-01-03,2\n", encoding="utf-8")

    shared, truncated = discover_sources(source, max_sources=None)
    manifest = build_catalog(source)

    assert not truncated
    assert len(shared) == len(manifest.sources) == 1
    assert manifest.sources[0].sha256 == shared[0].sha256
    assert manifest.sources[0].row_count == shared[0].row_count


def test_every_specialist_is_skill_backed() -> None:
    assert SPECIALISTS
    assert all(registration.skill.analysis_file.is_file() for registration in SPECIALISTS.values())
