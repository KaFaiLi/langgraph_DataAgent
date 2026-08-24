from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from data_agent.tools.grep_tools import search_files


def test_search_files_returns_bounded_structured_matches(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def build_app():\n    return True\n\n# build_app\n", encoding="utf-8"
    )
    (tmp_path / ".env").write_text("SECRET=build_app\n", encoding="utf-8")
    (tmp_path / "ignored.pyc").write_bytes(b"build_app\x00")

    result = search_files(
        tmp_path,
        "build_app",
        include="**/*.py",
        max_results=1,
    )

    assert result["count"] == 1
    assert result["truncated"]
    assert result["matches"][0]["path"] == "src/app.py"
    assert result["matches"][0]["line"] == 1
    assert all(".env" not in match["path"] for match in result["matches"])


def test_search_files_rejects_paths_outside_root(tmp_path: Path):
    with pytest.raises(ToolError, match="inside the workspace"):
        search_files(tmp_path, "secret", path="..")


def test_search_files_reports_invalid_regex(tmp_path: Path):
    with pytest.raises(ToolError, match="invalid regular expression"):
        search_files(tmp_path, "[")
