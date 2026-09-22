"""Persistent coverage and identical local/MCP assignment authorization."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fastmcp.exceptions import ToolError
from langchain_core.tools import ToolException

from data_agent.config import Settings
from data_agent.mcp_server.server import build_server
from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.run_record import SourceDisposition
from data_agent.skills.review import discover_skills
from data_agent.tools.review_runs import ReviewWorkspace, RunCapabilities
from data_agent.tools.review_skills import CandidateSubmission
from tests.review.fixtures.builder import make_csv
from tests.review.ported.test_risk_metrics_skill_analysis import _sgmr_row


@pytest.fixture()
def workspace(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    make_csv(source / "a.csv", [_sgmr_row(date(2025, 1, 2), value=12)])
    make_csv(source / "b.csv", [_sgmr_row(date(2025, 1, 3), value=20)])
    (source / "notes.md").write_text("unclassified source\n")
    definitions = {s.name: s for s in discover_skills()}
    workspace = ReviewWorkspace(source, tmp_path / "output", definitions)
    access = workspace.access("RUN-A")
    access.store.initialize(
        DeskContext(
            desk_name="Synthetic",
            business_description="Test desk",
            review_start=date(2025, 1, 1),
            review_end=date(2025, 1, 31),
        ),
        definitions,
    )
    return workspace


def _assign(workspace, path):
    access = workspace.access("RUN-A")
    record = access.store.read()
    source = record.manifest.by_path(path)
    access.classify(source.source_id, ["risk-metrics"], "SGMR schema")
    assignment = access.assign("risk-metrics", [source.source_id], "Review assigned SGMR rows")
    return access, assignment["assignment_id"], source.source_id


def test_complete_inventory_and_coverage_survive_reopening(workspace):
    access, assignment, source_id = _assign(workspace, "a.csv")
    original = access.store.read()
    page = access.inventory(limit=1)
    assert page["truncated"] and page["total_sources"] == 3
    assert len(access.inventory(offset=1)["sources"]) == 2
    assert access.coverage()["total_blockers"] > 0
    with pytest.raises(ValueError, match="stored analysis"):
        access.dispose_source(
            source_id, SourceDisposition(status="reviewed", reason="done"), assignment
        )
    access.execute(assignment)
    access.submit(
        assignment, CandidateSubmission(unresolved_items=["Independent verification pending"])
    )
    access.dispose_source(
        source_id,
        SourceDisposition(status="reviewed", reason="Analysis and draft recorded"),
        assignment,
    )
    reopened = workspace.access("RUN-A")
    current_source = next(s for s in reopened.inventory()["sources"] if s["source_id"] == source_id)
    assert not current_source["disposition_required"]
    assert current_source["dispositions"][assignment]["status"] == "reviewed"
    assert reopened.store.read().manifest == original.manifest
    assert reopened.store.read().assignments[assignment].analysis_ref
    assert not reopened.coverage()["source_coverage_complete"]
    assert not reopened.coverage()["candidate_coverage_complete"]
    for source in original.manifest.sources:
        if source.source_id != source_id:
            access.dispose_source(
                source.source_id,
                SourceDisposition(status="unsupported", reason="Unreviewed in this slice"),
            )
    assert access.coverage()["source_coverage_complete"]
    assert access.coverage()["disclosures"]
    assert access.coverage()["publication_ready"] is False


def test_assignment_scope_blocks_reads_joins_sql_and_evidence(workspace):
    access, first, _ = _assign(workspace, "a.csv")
    _, second, _ = _assign(workspace, "b.csv")
    scoped = RunCapabilities(access.store, workspace.definitions, first)
    cases = [
        ("read_rows", {"path": "b.csv", "start": 1, "end": 1}),
        ("join_tables", {"left": "a.csv", "right": "b.csv", "on": ["stranaPc"]}),
        ("run_duckdb_query", {"sql": "SELECT * FROM src_b_csv"}),
        ("reopen_evidence", {"locator": "source://b.csv#rows=2:2"}),
    ]
    for name, arguments in cases:
        with pytest.raises((ToolException, ValueError)):
            scoped.source_tool(first, name, arguments)
    with pytest.raises(ValueError, match="host-authorized"):
        scoped.source_tool(second, "read_rows", {"path": "b.csv", "start": 1, "end": 1})
    with pytest.raises(ValueError, match="root review"):
        scoped.classify("SRC-001", ["pnl"], "attempted reassignment")
    result = scoped.source_tool(
        first, "run_duckdb_query", {"sql": "SELECT table_name FROM information_schema.tables"}
    )
    assert "src_a_csv" in result["result"] and "src_b_csv" not in result["result"]
    search = scoped.source_tool(first, "search_text", {"pattern": "20"})
    assert "b.csv" not in search["result"]
    inventory = scoped.inventory()
    assert [s["path"] for s in inventory["sources"]] == ["a.csv"]


def test_scoped_search_discloses_population_truncation(workspace):
    access = workspace.access("RUN-A")
    record = access.store.read()
    for source in record.manifest.sources:
        access.classify(source.source_id, ["risk-metrics"], "Test source set")
    assignment = access.assign("risk-metrics", record.manifest.source_ids, "Search scope")[
        "assignment_id"
    ]
    result = access.source_tool(assignment, "search_text", {"pattern": ".", "max_results": 1})
    assert json.loads(result["result"])["truncated"] is True


def test_sources_and_run_binding_cannot_change(workspace, tmp_path):
    access, assignment, _ = _assign(workspace, "a.csv")
    other = tmp_path / "other"
    other.mkdir()
    unauthorized = ReviewWorkspace(other, workspace.workspace_root, workspace.definitions)
    with pytest.raises(ValueError, match="host-authorized"):
        unauthorized.access("RUN-A").inventory()
    bound = ReviewWorkspace(
        workspace.source_root, workspace.workspace_root, workspace.definitions, "RUN-A", assignment
    )
    with pytest.raises(ValueError, match="host-authorized"):
        bound.access("RUN-B")
    with (workspace.source_root / "a.csv").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="source changed"):
        access.source_tool(assignment, "inspect_table", {"path": "a.csv"})
    with pytest.raises(ValueError, match="source changed"):
        access.execute(assignment)
    with pytest.raises(ValueError, match="source changed"):
        access.coverage()


def test_new_source_and_parse_failures_are_visible(workspace):
    (workspace.source_root / "bad.xlsx").write_text("not a workbook")
    access = workspace.access("RUN-A")
    with pytest.raises(ValueError, match="inventory changed"):
        access.coverage()
    other = workspace.access("RUN-B")
    other.store.initialize(access.store.read().desk_context, workspace.definitions)
    source = next(s for s in other.inventory()["sources"] if s["path"] == "bad.xlsx")
    assert source["parse_error"] and source["disposition_required"]
    assert any("parse failure" in blocker for blocker in other.coverage()["blockers"])


def test_concurrent_writes_preserve_budgets_and_assignments(workspace):
    access, assignment, _ = _assign(workspace, "a.csv")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: workspace.access("RUN-A").source_tool(
                    assignment, "list_assigned_sources", {}
                ),
                range(8),
            )
        )
    assert len(results) == 8
    record = access.store.read()
    assert record.tool_calls == 8 and len(record.trace) == 8
    assert list(record.assignments) == [assignment]


@pytest.mark.asyncio
async def test_scoped_mcp_exposes_only_bound_capabilities(workspace):
    _access, assignment, _ = _assign(workspace, "a.csv")
    server = build_server(
        Settings(
            _env_file=None,
            source_root=workspace.source_root,
            review_workspace=str(workspace.workspace_root),
            review_run_id="RUN-A",
            review_assignment_id=assignment,
        )
    )
    names = {t.name for t in await server.list_tools()}
    from data_agent.agent.react_agent import build_agent
    from tests.agent.test_agent_factory import _NoopModel

    bundle = await build_agent(
        Settings(
            _env_file=None,
            source_root=workspace.source_root,
            review_workspace=str(workspace.workspace_root),
            review_run_id="RUN-A",
            review_assignment_id=assignment,
        ),
        model=_NoopModel(),
    )
    assert "execute_review_analysis" not in {tool.name for tool in bundle.root_tools}
    assert "review_source_tool" in {tool.name for tool in bundle.root_tools}
    assert "review_source_tool" in names
    assert not names.intersection(
        {"run_python_analysis", "grep", "read_rows", "assign_review_work", "initialize_review_run"}
    )
    args = {
        "run_id": "RUN-A",
        "assignment_id": assignment,
        "tool_name": "read_rows",
        "arguments": {"path": "a.csv", "start": 1, "end": 1},
    }
    result = await server.call_tool("review_source_tool", args)
    assert not result.is_error
    assert "PTF-A" in str(result.content)
    for mutation in ({"run_id": "RUN-B"}, {"arguments": {"path": "b.csv", "start": 1, "end": 1}}):
        with pytest.raises((ToolError, ToolException, ValueError)):
            await server.call_tool("review_source_tool", {**args, **mutation})
    with (workspace.source_root / "a.csv").open("a") as handle:
        handle.write("\n")
    with pytest.raises((ToolError, ToolException, ValueError)):
        await server.call_tool("review_source_tool", args)


def test_locator_free_candidate_identity_survives_accounting_replay():
    from data_agent.review.domain.analysis import AnalysisResult
    from data_agent.review.verification.candidates import assign_candidate_ids
    from data_agent.review.verification.omission import audit_omissions

    flags = assign_candidate_ids("inputs", [{"kind": "missing_source", "material": True}])
    assert flags == assign_candidate_ids("inputs", flags)
    analysis = AnalysisResult(name="inputs", summary="Missing input", flag_candidates=flags)
    audit = audit_omissions([analysis], [])
    assert audit.uncovered_candidate_ids == [flags[0]["candidate_id"]]
    assert audit.material_candidate_ids == [flags[0]["candidate_id"]]
