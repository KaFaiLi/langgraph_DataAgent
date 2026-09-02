"""Focused coverage for the migrated tabular and analysis tools."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from data_agent.tools.python_tools import run_python_analysis
from data_agent.tools.tabular_tools import (
    describe_columns,
    group_by,
    inspect_table,
    join_tables,
    read_rows,
    run_duckdb_query,
)


def _tables(root: Path) -> None:
    (root / "sales.csv").write_text(
        "desk,asset,amount\nA,one,10\nA,two,20\nB,one,5\n", encoding="utf-8"
    )
    (root / "owners.csv").write_text("desk,owner\nA,Alice\nB,Bob\n", encoding="utf-8")


def test_tabular_tools_cover_inspection_reads_describe_group_join_and_sql(
    tmp_path: Path,
):
    _tables(tmp_path)

    inspected = inspect_table(tmp_path, "sales.csv")
    assert inspected["columns"] == ["desk", "asset", "amount"]
    assert inspected["row_count"] == 3
    assert read_rows(tmp_path, "sales.csv", 2, 3)[0]["asset"] == "two"
    descriptions = describe_columns(tmp_path, "sales.csv")
    assert descriptions[2]["column"] == "amount"
    assert descriptions[2]["min"] == 5
    assert group_by(tmp_path, "sales.csv", ["desk"], "amount")[0]["sum(amount)"] == 30
    joined = join_tables(tmp_path, "sales.csv", "owners.csv", ["desk"])
    assert {row["owner"] for row in joined} == {"Alice", "Bob"}
    result = run_duckdb_query(
        tmp_path,
        "SELECT desk, sum(amount) AS total FROM src_sales_csv GROUP BY desk ORDER BY desk",
    )
    assert result == [{"desk": "A", "total": 30}, {"desk": "B", "total": 5}]


@pytest.mark.parametrize("path", ["../outside.csv", "C:/outside.csv", "/tmp/outside.csv"])
def test_tabular_paths_are_relative_and_contained(tmp_path: Path, path: str):
    with pytest.raises(ToolError):
        inspect_table(tmp_path, path)


def test_tabular_paths_apply_hidden_and_secret_file_policy(tmp_path: Path):
    hidden = tmp_path / ".private"
    hidden.mkdir()
    (hidden / "data.csv").write_text("value\n1\n", encoding="utf-8")
    (tmp_path / ".env.csv").write_text("value\n2\n", encoding="utf-8")

    with pytest.raises(ToolError):
        inspect_table(tmp_path, ".private/data.csv")
    with pytest.raises(ToolError):
        inspect_table(tmp_path, ".env.csv")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM src_sales_csv",
        "SELECT 1; DROP TABLE src_sales_csv",
        "PRAGMA enable_external_access",
        "COPY (SELECT 1) TO 'out.csv'",
        "SELECT * FROM read_csv_auto('../outside.csv')",
        "SELECT * FROM read_json_auto('../outside.json')",
        "SELECT * FROM read_text('../outside.txt')",
        "SELECT * FROM '../outside.csv'",
        "SELECT * FROM risk_metrics.source.parquet",
        "SELECT * FROM sales_csv",
    ],
)
def test_duckdb_rejects_mutating_or_chained_sql(tmp_path: Path, sql: str):
    _tables(tmp_path)
    with pytest.raises(ToolError):
        run_duckdb_query(tmp_path, sql)


def test_excel_sheet_is_supported(tmp_path: Path):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(["desk", "amount"])
    sheet.append(["A", 4])
    sheet.append(["B", 6])
    workbook.save(tmp_path / "book.xlsx")
    inspected = inspect_table(tmp_path, "book.xlsx", sheet="Data")
    assert inspected["row_count"] == 2
    assert group_by(tmp_path, "book.xlsx", ["desk"], "amount", sheet="Data")


def test_python_sandbox_allows_analysis_but_blocks_paths_imports_and_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    source.mkdir()
    workspace.mkdir()
    (source / "input.txt").write_text("ok", encoding="utf-8")
    result = run_python_analysis(
        source,
        workspace,
        f"""
import json
from pathlib import Path
print(Path(r'{source / "input.txt"}').read_text())
Path('result.json').write_text(json.dumps({{'ok': True}}))
""",
    )
    assert result["ok"] is True, result
    assert json.loads((workspace / "result.json").read_text()) == {"ok": True}
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "other-secret")
    env = run_python_analysis(
        source, workspace, "import os; print(os.environ.get('OPENAI_API_KEY'))"
    )
    assert env["ok"] is True
    assert "secret" not in env["stdout"]
    env = run_python_analysis(
        source, workspace, "import os; print(os.environ.get('AWS_SECRET_ACCESS_KEY'))"
    )
    assert env["ok"] is True
    assert "other-secret" not in env["stdout"]
    blocked = run_python_analysis(source, workspace, "import socket")
    assert blocked["ok"] is False
    outside = run_python_analysis(source, workspace, "open('/etc/passwd').read()")
    assert outside["ok"] is False
    repo_file = Path(__file__).resolve().parents[1] / "pyproject.toml"
    outside_repo = run_python_analysis(
        source,
        workspace,
        f"open({str(repo_file)!r}).read()",
    )
    assert outside_repo["ok"] is False
    source_write = run_python_analysis(
        source,
        workspace,
        f"from pathlib import Path; Path(r'{source / 'input.txt'}').write_text('nope')",
    )
    assert source_write["ok"] is False
    assert (source / "input.txt").read_text() == "ok"
    process = run_python_analysis(source, workspace, "import os; os.system('echo nope')")
    assert process["ok"] is False


def test_python_sandbox_bounds_output_and_timeout(tmp_path: Path):
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    source.mkdir()
    workspace.mkdir()
    output = run_python_analysis(source, workspace, "print('x' * 1000000)", max_output_chars=100)
    assert len(output["stdout"]) == 100
    timeout = run_python_analysis(source, workspace, "while True: pass", timeout_seconds=0.1)
    assert timeout["timed_out"] is True


def test_python_sandbox_blocks_platform_process_module(tmp_path: Path):
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    source.mkdir()
    workspace.mkdir()
    platform_module = "nt" if os.name == "nt" else "posix"

    result = run_python_analysis(
        source,
        workspace,
        f"import {platform_module}; {platform_module}.system('echo escape')",
    )

    assert result["ok"] is False
    assert "blocked" in result["stderr"].lower()


def test_python_registration_does_not_create_missing_source_root(tmp_path: Path):
    from fastmcp import FastMCP

    from data_agent.tools.python_tools import register

    missing_root = tmp_path / "not-mounted-yet"
    server = FastMCP("sandbox-registration-test")
    register(server, root=missing_root)

    assert not missing_root.exists()
