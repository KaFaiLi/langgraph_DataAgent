"""Parent-graph tests: catalog, tasks, fan-out, hard coverage gate (fakes)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.domains import SPECIALIST_DOMAINS, SpecialistDomain
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import VerifierDecision
from data_agent.review.llm.models import ModelTier
from data_agent.review.orchestration.graph import build_parent_graph
from data_agent.review.orchestration.nodes.context import build_desk_context
from data_agent.review.orchestration.nodes.coverage import coverage_gate
from data_agent.review.orchestration.specialist.schemas import AnalystOutput
from tests.review.fixtures.builder import make_risky_tree, make_text

DESK_TEMPLATE = DeskContext(
    desk_name="EM Rates",
    business_description="EM rates market making.",
    review_start=date(2025, 1, 1),
    review_end=date(2026, 6, 30),
).model_dump(mode="json")

PERIOD = DateRange(start=date(2025, 1, 1), end=date(2026, 6, 30))


class FakeParentProvider:
    """Serves classification (flash) and specialist analyst/verifier fakes.

    ``classification`` maps source *paths* to domains; unmapped paths get
    the default (risk_metrics).
    """

    def __init__(
        self,
        classification: dict[str, list[SpecialistDomain]] | None = None,
    ):
        self.classification = classification or {}
        self.calls: list[tuple[str, ModelTier]] = []

    def __call__(self, tier, schema=None):
        from data_agent.review.orchestration.nodes.dispatch import ClassificationOutput
        from data_agent.review.synthesis.lead_review import LeadDraft
        from data_agent.review.synthesis.lead_verifier import LeadVerifierOutput

        name = schema.__name__ if schema else "plain"
        self.calls.append((name, tier))
        if schema is ClassificationOutput:
            return RunnableLambda(lambda messages: self._classify(messages))
        if schema is AnalystOutput:
            return RunnableLambda(lambda _m: AnalystOutput(findings=[]))
        if schema is LeadDraft:
            return RunnableLambda(
                lambda _m: LeadDraft(
                    executive_summary="Nothing material found.",
                    overall_desk_risk_assessment="No material issues.",
                )
            )
        if schema is LeadVerifierOutput:
            return RunnableLambda(
                lambda _m: LeadVerifierOutput(decision=VerifierDecision.PASS, checks=["ok"])
            )
        raise AssertionError(f"unexpected schema {schema}")

    def _classify(self, messages):
        from data_agent.review.orchestration.nodes.dispatch import ClassificationOutput

        text = "\n".join(str(getattr(m, "content", "")) for m in messages)
        source_match = re.search(r"source_id=(\S+)", text)
        path_match = re.search(r"path=(\S+)", text)
        source_id = source_match.group(1) if source_match else "SRC-000"
        path = path_match.group(1) if path_match else ""
        return ClassificationOutput(
            source_id=source_id,
            domains=self.classification.get(path, [SpecialistDomain.RISK_METRICS]),
        )


def run_parent(
    tmp_path: Path,
    provider: FakeParentProvider,
    *,
    tree_modifier=None,
    period: DateRange | None = PERIOD,
) -> tuple[dict, Path]:
    source = tmp_path / "source"
    out = tmp_path / "runs" / "RUN-1"
    make_risky_tree(source)
    if tree_modifier:
        tree_modifier(source)
    state = {"source_root": str(source), "output_dir": str(out)}
    configurable: dict = {
        "llm_provider": provider,
        "desk_template": DESK_TEMPLATE,
    }
    if period is not None:
        configurable["review_period"] = period
    graph = build_parent_graph(llm_provider=provider)
    result = graph.invoke(state, config={"configurable": configurable})
    return result, out


def test_happy_path_covers_all_sources(tmp_path: Path) -> None:
    provider = FakeParentProvider()
    result, out = run_parent(tmp_path, provider)

    assert result.get("status") == "completed", result.get("failure_reason")
    assert len(result["tasks"]) == 4  # every active specialist has material
    assert all(entry["status"] == "reviewed" for entry in result["coverage"])
    assert len(result["specialist_reports"]) == 4

    specialists = sorted(p.name for p in (out / "specialists").glob("*.md"))
    assert specialists == sorted(f"{d.value}.md" for d in SPECIALIST_DOMAINS)

    pnl_task = next(task for task in result["tasks"] if task["domain"] == "pnl")
    assert set(pnl_task["source_ids"]) == {
        _source_id_by_path(result, "pnl/pnl.xlsx"),
        _source_id_by_path(result, "income_attribution/attribution.parquet"),
        _source_id_by_path(result, "pnl_adjustments/adjustments.txt"),
        _source_id_by_path(result, "pnl_validation/validation.pdf"),
    }
    coverage_by_source = {entry["source_id"]: entry for entry in result["coverage"]}
    assert all(
        coverage_by_source[source_id]["required_reviewers"] == ["pnl"]
        for source_id in pnl_task["source_ids"]
    )

    catalog = out / "catalog.json"
    assert catalog.exists()
    desk_context = out / "desk_context.json"
    assert desk_context.exists()
    limits = result["desk_context"]["limits"]
    assert limits  # risk.csv exposes a limit column -> deterministic enrichment
    assert result["desk_context"]["source_backed_facts"]
    assert result["desk_context"]["source_backed_facts"][0]["evidence"][0]["locator"].endswith(
        "#rows=2:2"
    )

    # Synthesis phase artifacts.
    assert result["final_report"] is not None
    final_markdown = out / "final_findings.md"
    assert final_markdown.exists()
    assert "## Key Findings" in final_markdown.read_text(encoding="utf-8")
    assert (out / "run_manifest.json").exists()
    # Lead review + lead verification both use the high-cost model.
    assert ("LeadDraft", ModelTier.HIGH_COST) in provider.calls
    assert ("LeadVerifierOutput", ModelTier.HIGH_COST) in provider.calls


def _source_id_by_path(result: dict, path: str) -> str:
    for source in result["manifest"]["sources"]:
        if source["path"] == path:
            return source["source_id"]
    raise AssertionError(f"source not found: {path}")


def test_unclassified_source_gets_classified_by_flash(tmp_path: Path) -> None:
    provider = FakeParentProvider()

    def _add_unclassified(source: Path) -> None:
        (source / "misc").mkdir(exist_ok=True)
        make_text(source / "misc" / "unknown.csv", "x,y\n1,2\n")

    result, _ = run_parent(tmp_path, provider, tree_modifier=_add_unclassified)

    assert result.get("status") != "failed", result.get("failure_reason")
    classification_calls = [c for c in provider.calls if c[0] == "ClassificationOutput"]
    assert len(classification_calls) == 1
    assert classification_calls[0][1] is ModelTier.LOW_COST
    unknown_id = _source_id_by_path(result, "misc/unknown.csv")
    unknown = next(entry for entry in result["coverage"] if entry["source_id"] == unknown_id)
    assert unknown["required_reviewers"] == ["risk_metrics"]
    assert unknown["status"] == "reviewed"


def test_empty_classification_routes_to_all_specialists(tmp_path: Path) -> None:
    provider = FakeParentProvider(classification={"misc/unknown.csv": []})

    def _add_unclassified(source: Path) -> None:
        (source / "misc").mkdir(exist_ok=True)
        make_text(source / "misc" / "unknown.csv", "x,y\n1,2\n")

    result, _ = run_parent(tmp_path, provider, tree_modifier=_add_unclassified)

    assert result.get("status") != "failed", result.get("failure_reason")
    unknown_id = _source_id_by_path(result, "misc/unknown.csv")
    unknown = next(entry for entry in result["coverage"] if entry["source_id"] == unknown_id)
    assert len(unknown["required_reviewers"]) == len(SPECIALIST_DOMAINS)
    assert unknown["status"] == "reviewed"


def test_unsupported_source_fails_run(tmp_path: Path) -> None:
    def _add_bin(source: Path) -> None:
        (source / "misc").mkdir(exist_ok=True)
        (source / "misc" / "notes.bin").write_bytes(b"\x00\x01")

    result, _ = run_parent(tmp_path, FakeParentProvider(), tree_modifier=_add_bin)
    assert result["status"] == "failed"
    assert "unsupported" in (result["failure_reason"] or "")


def test_corrupt_source_fails_run(tmp_path: Path) -> None:
    def _add_corrupt(source: Path) -> None:
        (source / "broken.xlsx").write_bytes(b"\xff\xfe\x00garbage")

    result, _ = run_parent(tmp_path, FakeParentProvider(), tree_modifier=_add_corrupt)
    assert result["status"] == "failed"
    assert "source parsing failed" in (result["failure_reason"] or "")


def test_missing_source_root_fails(tmp_path: Path) -> None:
    provider = FakeParentProvider()
    state = {"source_root": str(tmp_path / "nope"), "output_dir": str(tmp_path / "out")}
    graph = build_parent_graph(llm_provider=provider)
    result = graph.invoke(
        state,
        config={
            "configurable": {
                "llm_provider": provider,
                "desk_template": DESK_TEMPLATE,
                "review_period": PERIOD,
            }
        },
    )
    assert result["status"] == "failed"
    assert "does not exist" in (result["failure_reason"] or "")


def test_missing_review_period_fails(tmp_path: Path) -> None:
    provider = FakeParentProvider()
    source = tmp_path / "source"
    make_risky_tree(source)
    graph = build_parent_graph(llm_provider=provider)
    result = graph.invoke(
        {"source_root": str(source), "output_dir": str(tmp_path / "out")},
        config={
            "configurable": {
                "llm_provider": provider,
                "desk_template": DESK_TEMPLATE,
            }
        },
    )
    assert result["status"] == "failed"
    assert "review period" in (result["failure_reason"] or "")


def test_coverage_gate_node_blocks_pending_sources() -> None:
    result = coverage_gate(
        {"coverage": [{"source_id": "SRC-001", "status": "pending"}]},
        {},
    )
    assert result["status"] == "failed"
    assert "SRC-001" in (result["failure_reason"] or "")


def test_changed_source_fails_desk_context_construction(tmp_path: Path) -> None:
    source = tmp_path / "source"
    make_risky_tree(source)
    from data_agent.review.ingestion.catalog import build_catalog

    manifest = build_catalog(source)
    risk_file = source / "risk_metrics" / "risk.csv"
    risk_file.write_bytes(risk_file.read_bytes().replace(b"3.1", b"9.9", 1))

    result = build_desk_context(
        {
            "source_root": str(source),
            "output_dir": str(tmp_path / "out"),
            "manifest": manifest.model_dump(mode="json"),
        },
        {"configurable": {"desk_template": DESK_TEMPLATE}},
    )

    assert result["status"] == "failed"
    assert "integrity" in result["failure_reason"]


def test_desk_context_bullet_facts_are_shared_with_exact_line_evidence(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    (source / "desk_context").mkdir()
    make_text(
        source / "desk_context" / "background.md",
        "# Desk facts\n\n- GOP India maps uniquely to Portfolio Ivory.\n",
    )
    from data_agent.review.ingestion.catalog import build_catalog

    manifest = build_catalog(source)
    result = build_desk_context(
        {
            "source_root": str(source),
            "output_dir": str(output),
            "manifest": manifest.model_dump(mode="json"),
        },
        {"configurable": {"desk_template": DESK_TEMPLATE}},
    )

    facts = result["desk_context"]["source_backed_facts"]
    assert facts[0]["statement"] == "GOP India maps uniquely to Portfolio Ivory."
    assert facts[0]["evidence"][0]["locator"].endswith("#lines=3:3")


def test_specialist_failure_fails_run(tmp_path: Path, monkeypatch) -> None:
    from data_agent.review.orchestration.nodes import fanout

    def _exploding_builder(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(fanout, "build_specialist", _exploding_builder)
    result, _ = run_parent(tmp_path, FakeParentProvider())

    assert result["status"] == "failed"
    assert "risk_metrics" in (result["failure_reason"] or "")
    assert "boom" in (result["failure_reason"] or "")
