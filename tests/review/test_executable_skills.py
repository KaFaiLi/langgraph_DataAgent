"""Executable skill contracts, storage integrity and general ReAct integration."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import ToolException

from data_agent.agent.react_agent import build_agent
from data_agent.config import Settings
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.severity import Severity
from data_agent.skills.loader import discover_skills
from data_agent.skills.review import SkillLoadError, load_skill
from data_agent.skills.review import discover_skills as review_skills
from data_agent.skills.tools import build_skill_tools
from data_agent.tools.review_skills import CandidateSubmission, SkillExecution
from tests.agent.test_agent_factory import _NoopModel
from tests.review.fixtures.builder import make_csv
from tests.review.ported.test_risk_metrics_skill_analysis import _sgmr_row


@pytest.fixture()
def execution(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    make_csv(source / "sgmr.csv", [_sgmr_row(date(2025, 1, 2), value=12)])
    return SkillExecution(source, tmp_path / "results", {s.name: s for s in review_skills()})


def _finding():
    return Finding(
        finding_id="F1",
        title="Recorded exceedance",
        category="limit",
        severity=Severity.MEDIUM,
        confidence=0.9,
        claim="The SGMR row records consumption 12 against a maximum of 10.",
        evidence=[EvidenceReference(locator="source://sgmr.csv#rows=2:2")],
    )


def test_analysis_storage_pagination_evidence_and_pending_submission(execution):
    summary = execution.execute("risk-metrics", ["sgmr.csv"])
    assert summary["coverage_complete"] is False
    reference = summary["result_ref"]
    result = execution.load(reference)
    assert result.analyses
    assert all(c.get("candidate_id") for a in result.analyses for c in a.flag_candidates)
    assert reference == execution.execute("risk-metrics", ["sgmr.csv"])["result_ref"]
    page = execution.read(reference, max_chars=20)
    assert page["truncated"] and page["next_offset"] == 20
    last = execution.read(reference, offset=page["total_chars"] - 1)
    assert last["truncated"] and last["next_offset"] is None
    assert execution.reopen(reference, _finding().evidence[0].locator)["valid"]
    assert not execution.reopen(reference, "source://elsewhere.csv#rows=1:1")["valid"]
    draft = CandidateSubmission(findings=[_finding()])
    submitted = execution.submit(reference, draft)
    assert submitted["status"] == "pending" and not submitted["verified"]
    assert submitted["finding_ids"] == ["RISK-F1"]
    assert submitted == execution.submit(reference, draft)
    stored = json.loads(
        (execution.workspace_root / (submitted["candidate_ref"] + ".json")).read_text()
    )
    assert stored["candidate"]["findings"][0]["verifier_status"] == "pending"


def test_submission_cannot_self_verify_or_invent_evidence(execution):
    reference = execution.execute("risk-metrics", ["sgmr.csv"])["result_ref"]
    finding = _finding().model_copy(update={"verifier_status": VerificationStatus.PASSED})
    with pytest.raises(ValueError, match="self-declare"):
        execution.submit(reference, CandidateSubmission(findings=[finding]))
    finding = _finding().model_copy(
        update={"evidence": [EvidenceReference(locator="source://sgmr.csv#rows=999:999")]}
    )
    with pytest.raises(ValueError, match="invalid candidate evidence"):
        execution.submit(reference, CandidateSubmission(findings=[finding]))


def test_analysis_rejects_unknown_skills_escaped_sources_and_changed_storage(execution):
    with pytest.raises(ValueError, match="Unknown executable"):
        execution.execute("/tmp/arbitrary.py:run", ["sgmr.csv"])
    with pytest.raises(KeyError):
        execution.execute("risk-metrics", ["../secret.csv"])
    reference = execution.execute("risk-metrics", ["sgmr.csv"])["result_ref"]
    path = execution.workspace_root / (reference + ".json")
    original = path.read_text()
    path.write_text(original + " ")
    with pytest.raises(ValueError, match="integrity"):
        execution.read(reference)
    path.write_text(original)
    with (execution.source_root / "sgmr.csv").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="source changed"):
        execution.read(reference)


def test_reference_loader_is_bounded_and_rejects_missing_unknown_and_escape(tmp_path):
    root = tmp_path / "demo"
    root.mkdir()
    (root / "SKILL.md").write_text("---\nname: demo\ndescription: Test\n---\nInstructions")
    references = root / "references"
    references.mkdir()
    (references / "dataset.md").write_text("abcdef")
    loader = {t.name: t for t in build_skill_tools(discover_skills(tmp_path))}[
        "load_skill_reference"
    ]
    page = loader.invoke({"name": "demo", "reference": "dataset", "max_chars": 2})
    assert page["content"] == "ab" and page["truncated"] and page["next_offset"] == 2
    with pytest.raises(ToolException, match="Missing"):
        loader.invoke({"name": "demo", "reference": "policy"})
    with pytest.raises(ToolException, match="Unknown"):
        loader.invoke({"name": "unknown", "reference": "policy"})
    outside = tmp_path / "private.md"
    outside.write_text("private")
    (references / "policy.md").symlink_to(outside)
    with pytest.raises(ToolException, match="escapes"):
        loader.invoke({"name": "demo", "reference": "policy"})


def test_registered_entrypoint_cannot_escape(tmp_path):
    root = tmp_path / "risk-metrics"
    root.mkdir()
    original = Path("skills/risk-metrics/SKILL.md").read_text()
    (root / "SKILL.md").write_text(
        original.replace("scripts/analysis.py:run_analysis", "../outside.py:run_analysis")
    )
    with pytest.raises(SkillLoadError, match="contained"):
        load_skill(root / "SKILL.md", skills_root=tmp_path)


@pytest.mark.asyncio
async def test_general_agent_executes_slice_without_legacy_workflow(execution, monkeypatch):
    from data_agent.review import service
    from data_agent.review.orchestration import graph
    from data_agent.review.orchestration.specialist import graph as specialist_graph

    def forbidden(*args, **kwargs):
        raise AssertionError("legacy workflow invoked")

    monkeypatch.setattr(service, "ReviewService", forbidden)
    monkeypatch.setattr(graph, "build_parent_graph", forbidden)
    monkeypatch.setattr(specialist_graph, "build_specialist_graph", forbidden)

    class SliceModel(_NoopModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            from langchain_core.outputs import ChatGeneration, ChatResult

            completed = {
                m.name: json.loads(m.content) if m.name != "load_skill" else m.content
                for m in messages
                if isinstance(m, ToolMessage)
            }
            reference = completed.get("execute_review_analysis", {}).get("result_ref")
            operations = [
                ("load_skill", {"name": "risk-metrics"}),
                ("load_skill_reference", {"name": "risk-metrics", "reference": "dataset"}),
                (
                    "execute_review_analysis",
                    {"skill_name": "risk-metrics", "source_paths": ["sgmr.csv"]},
                ),
                ("read_analysis_result", {"result_ref": reference}),
                (
                    "reopen_analysis_evidence",
                    {"result_ref": reference, "locator": _finding().evidence[0].locator},
                ),
                (
                    "submit_candidate_result",
                    {
                        "result_ref": reference,
                        "candidate": CandidateSubmission(findings=[_finding()]).model_dump(
                            mode="json"
                        ),
                    },
                ),
            ]
            remaining = [(name, args) for name, args in operations if name not in completed]
            if remaining:
                name, args = remaining[0]
                answer = AIMessage(
                    content="", tool_calls=[{"id": name, "name": name, "args": args}]
                )
            else:
                answer = AIMessage(
                    content="Candidate stored; independent verification remains pending."
                )
            return ChatResult(generations=[ChatGeneration(message=answer)])

    bundle = await build_agent(
        Settings(
            _env_file=None,
            source_root=execution.source_root,
            review_workspace=str(execution.workspace_root),
        ),
        model=SliceModel(),
    )
    result = await bundle.ainvoke("Review the risk metrics sample")
    submissions = [
        m
        for m in result["messages"]
        if isinstance(m, ToolMessage) and m.name == "submit_candidate_result"
    ]
    assert len(submissions) == 1
    submitted = json.loads(submissions[0].content)
    assert submitted["status"] == "pending" and submitted["finding_ids"] == ["RISK-F1"]
