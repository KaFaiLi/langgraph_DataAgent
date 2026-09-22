"""Outcome-focused verification of model-directed specialist capabilities."""

from __future__ import annotations

import pytest

from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.outputs import AdjudicatorOutput, ChallengerOutput
from data_agent.review.domain.run_record import SourceDisposition
from data_agent.review.domain.verification import ChallengeResult
from data_agent.review.verification.rules import required_challenge_types
from data_agent.tools.review_skills import CandidateSubmission
from data_agent.tools.review_verification import VerificationCapabilities
from tests.agent.test_review_roles import role_context as _role_fixture
from tests.agent.test_review_roles import workspace as _workspace_fixture


@pytest.fixture()
def workspace(tmp_path):
    return _workspace_fixture.__wrapped__(tmp_path)


@pytest.fixture()
def role_context(workspace):
    return _role_fixture.__wrapped__(workspace)


def _independent_result(context, *, decision="pass", complete=True, bad_evidence=False, child="1"):
    _access, _assignment, adapter, specs, request = context
    challenges = [
        ChallengeResult(
            challenge_type=kind,
            status="not_applicable",
            explanation="No additional claim in this category.",
        ).model_dump(mode="json")
        for kind in required_challenge_types()
    ]
    if bad_evidence:
        challenges[0].update(status="pass", evidence=[{"locator": "source://a.csv#rows=500:500"}])
    challenge = adapter.prepare(specs["review-challenger"], request, "challenge-" + child)
    challenge.accept(
        ChallengerOutput(finding_id="RISK-F1", research_complete=complete, challenges=challenges)
    )
    adjudicate = adapter.prepare(specs["review-adjudicator"], request, "adjudicate-" + child)
    return adjudicate.accept(AdjudicatorOutput(finding_id="RISK-F1", decision=decision))[
        "result_ref"
    ]


def _disposition(context):
    access, assignment, *_ = context
    source_id = access.store.read().assignments[assignment].source_ids[0]
    access.dispose_source(
        source_id,
        SourceDisposition(status="reviewed", reason="All assigned data inspected"),
        assignment,
    )


def test_verification_is_version_bound_idempotent_and_invalidated_by_revision(role_context):
    access, assignment, *_ = role_context
    capability = VerificationCapabilities(access)
    reference = _independent_result(role_context)
    first = capability.apply(assignment, reference)
    assert first["status"] == "passed"
    assert capability.apply(assignment, reference) == first
    assert len(access.store.read().assignments[assignment].verification["RISK-F1"]) == 1
    current = access.store.read().assignments[assignment].findings["RISK-F1"]
    pending = Finding.model_validate(current).model_copy(
        update={"verifier_status": VerificationStatus.PENDING}
    )
    access.submit(assignment, CandidateSubmission(findings=[pending]))
    assert (
        access.store.read().assignments[assignment].findings["RISK-F1"]["verifier_status"]
        == "passed"
    )
    revised = pending.model_copy(
        update={"claim": "Observed consumption 12 versus bound 10; cause unestablished."}
    )
    access.submit(assignment, CandidateSubmission(findings=[revised]))
    assert (
        access.store.read().assignments[assignment].findings["RISK-F1"]["verifier_status"]
        == "pending"
    )
    with pytest.raises(ValueError, match="stale"):
        capability.apply(assignment, reference)
    reference = _independent_result(role_context, child="2")
    assert capability.apply(assignment, reference)["status"] == "revised"
    with pytest.raises(ValueError, match="budget exhausted"):
        access.submit(
            assignment,
            CandidateSubmission(findings=[revised.model_copy(update={"claim": "Another change"})]),
        )


@pytest.mark.parametrize("failure", ["incomplete", "bad_evidence"])
def test_unsafe_model_pass_becomes_revision_then_explicit_unresolved(role_context, failure):
    access, assignment, *_ = role_context
    capability = VerificationCapabilities(access)
    kwargs = {"complete": failure != "incomplete", "bad_evidence": failure == "bad_evidence"}
    reference = _independent_result(role_context, **kwargs)
    first = capability.apply(assignment, reference)
    assert first["decision"] == "revise" and first["status"] == "pending"
    _disposition(role_context)
    with pytest.raises(ValueError, match="pending finding"):
        capability.finalize(assignment)
    second = capability.apply(assignment, _independent_result(role_context, child="2", **kwargs))
    assert second["status"] == "unresolved"
    capability.omissions(
        assignment, "disclose", "No remaining research budget; retain candidate uncertainty"
    )
    result = capability.finalize(assignment)
    assert result["unresolved_items"] and result["verified_findings"] == 0
    report = access.store.read().assignments[assignment].report
    assert report["findings"][0]["verifier_status"] == "unresolved"
    assert len(report["verification_history"]["RISK-F1"]) == 2


def test_rejected_finding_is_retained_in_history_and_omissions_are_disclosed(role_context):
    access, assignment, *_ = role_context
    capability = VerificationCapabilities(access)
    assert (
        capability.apply(assignment, _independent_result(role_context, decision="reject"))["status"]
        == "rejected"
    )
    _disposition(role_context)
    audit = capability.omissions(assignment)["audit"]
    assert audit["uncovered_candidates"]
    with pytest.raises(ValueError, match="unaccounted deterministic"):
        capability.finalize(assignment)
    capability.omissions(assignment, "rescue", "Investigate missing source-family signal")
    with pytest.raises(ValueError, match="rescue budget"):
        capability.omissions(assignment, "rescue", "Second attempt")
    capability.omissions(assignment, "disclose", "Colibris input is unavailable")
    report = capability.finalize(assignment)
    assert report["unresolved_items"] and report["overview_count"] > 0
    stored = access.store.read().assignments[assignment].report
    assert (
        stored["findings"] == []
        and stored["verification_history"]["RISK-F1"][0]["decision"] == "reject"
    )


def test_missing_independence_and_self_declared_status_cannot_finalize(role_context):
    access, assignment, *_ = role_context
    capability = VerificationCapabilities(access)
    with pytest.raises(ValueError, match="stored review-adjudicator"):
        capability.apply(assignment, "invented")
    _disposition(role_context)
    access.store.update(
        lambda r: r.assignments[assignment].findings["RISK-F1"].update(verifier_status="passed")
    )
    with pytest.raises(ValueError, match="independent verification"):
        capability.finalize(assignment)
    reference = _independent_result(role_context)
    access.store.update(lambda r: r.role_results[reference]["output"].update(feedback="Tampered"))
    with pytest.raises(ValueError, match="integrity check"):
        capability.apply(assignment, reference)


def test_source_mutation_blocks_verification(role_context, workspace):
    access, assignment, *_ = role_context
    reference = _independent_result(role_context)
    with (workspace.source_root / "a.csv").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="source changed"):
        VerificationCapabilities(access).apply(assignment, reference)


def test_transport_pages_evidence_and_reports_actual_candidate_coverage(role_context):
    from data_agent.review.domain.verification import CandidateDispositionRecord
    from data_agent.tools.review_runs import build_review_run_tools

    access, assignment, adapter, *_ = role_context
    tools = {t.name: t for t in build_review_run_tools(adapter.workspace)}
    page = tools["validate_review_evidence"].invoke(
        {
            "run_id": "RUN-A",
            "assignment_id": assignment,
            "finding_id": "RISK-F1",
            "max_chars": 100,
        }
    )
    assert page["decision"] == "pass" and page["truncated"] and page["next_offset"] == 100
    assert len(page["content"]) == 100
    with pytest.raises(ValueError, match="unsupported source tool arguments"):
        access.source_tool(
            assignment, "read_rows", {"path": "a.csv", "start": 1, "end": 1, "invented": True}
        )
    audit = VerificationCapabilities(access).omissions(assignment)["audit"]
    candidate_id = audit["uncovered_candidates"][0]["candidate_id"]
    receipt = access.dispose_candidate(
        assignment,
        CandidateDispositionRecord(
            candidate_id=candidate_id,
            disposition="finding",
            reason="Named without a linked finding",
            evidence=[{"locator": "source://a.csv#rows=2:2"}],
        ),
    )
    assert receipt["recorded"] and not receipt["covered"] and receipt["next_action"]
