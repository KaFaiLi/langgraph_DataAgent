from pathlib import Path

import pytest
from langchain_core.tools import ToolException

from data_agent.config import REPO_ROOT
from data_agent.skills.loader import discover_skills
from data_agent.skills.tools import build_skill_tools, render_skills_overview


def test_discovers_bundled_skills():
    skills = discover_skills(REPO_ROOT / "skills")
    names = {s.name for s in skills}
    assert names == {
        "lead-review",
        "pnl",
        "post-trade-controls",
        "risk-commentary",
        "risk-metrics",
        "risk-ppt",
    }
    for s in skills:
        assert s.description
        assert s.instructions


def test_frontmatter_parsing(tmp_path: Path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: A demo skill.\n---\n# Body\nDo the thing.\n",
        encoding="utf-8",
    )
    skills = discover_skills(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "demo"
    assert skills[0].description == "A demo skill."
    assert "Do the thing." in skills[0].instructions


def test_skill_tool_roundtrip():
    skills = discover_skills(REPO_ROOT / "skills")
    tools = build_skill_tools(skills)
    names = {t.name for t in tools}
    assert names == {"load_skill"}

    load_skill = next(t for t in tools if t.name == "load_skill")
    out = load_skill.invoke({"name": "risk-metrics"})
    assert "risk metrics" in out.lower()

    # When called outside a graph, ToolException propagates directly.
    # Inside a react agent, handle_tool_errors=True catches it and surfaces
    # the message as a ToolMessage so the LLM can continue.
    with pytest.raises(ToolException, match="nope"):
        load_skill.invoke({"name": "nope"})

    overview = render_skills_overview(skills)
    assert "risk-metrics" in overview
    assert "risk-ppt" in overview


def test_no_skill_loader_is_exposed_without_skills():
    assert build_skill_tools([]) == []
