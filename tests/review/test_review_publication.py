"""Lead gates and atomic, downstream-compatible publication without legacy orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_agent.agent.subagents.contracts import DelegationRequest
from data_agent.review.application.run_bundle import load_completed_run
from data_agent.review.application.sealed_bundle import load_sealed_bundle
from data_agent.review.domain.lead_outputs import LeadDraft, LeadVerifierOutput
from data_agent.review.domain.run_record import SourceDisposition
from data_agent.tools.review_publication import PublicationCapabilities
from data_agent.tools.review_verification import VerificationCapabilities
from tests.review.test_review_verification import _disposition, _independent_result
from tests.review.test_review_verification import role_context as _role_fixture
from tests.review.test_review_verification import workspace as _workspace_fixture


@pytest.fixture()
def workspace(tmp_path):
    return _workspace_fixture.__wrapped__(tmp_path)


@pytest.fixture()
def context(workspace):
    return _role_fixture.__wrapped__(workspace)


@pytest.fixture()
def ready(context):
    access, assignment, _adapter, _specs, _request = context
    verification = VerificationCapabilities(access)
    verification.apply(assignment, _independent_result(context))
    _disposition(context)
    for source in access.store.read().manifest.sources:
        if source.path != "a.csv":
            access.dispose_source(
                source.source_id,
                SourceDisposition(
                    status="unsupported", reason="Outside this test's selected review scope"
                ),
            )
    verification.omissions(assignment, "disclose", "Colibris unavailable in assigned scope")
    verification.finalize(assignment)
    return context


def _lead(context, *, severity="high", locator="source://a.csv#rows=2:2", child="1"):
    _access, _assignment, adapter, specs, _request = context
    request = DelegationRequest(agent_name="review-lead", task="Synthesize", context="{}")
    prepared = adapter.prepare(specs["review-lead"], request, "lead-" + child)
    assert {t.name for t in prepared.tools} == {"read_specialist_report"}
    output = LeadDraft(
        executive_summary="Observed consumption exceeds the supplied bound.",
        overall_desk_risk_assessment="Limited source scope; further assessment required.",
        key_findings=[
            {
                "final_id": "FINAL-1",
                "title": "Limit observation",
                "severity": severity,
                "confidence": 0.9,
                "statement": "Consumption 12 exceeds bound 10.",
                "derived_from": ["RISK-F1"],
                "evidence": [{"locator": locator}],
            }
        ],
    )
    return prepared.accept(output)["result_ref"]


def _verify(context, *, decision="pass", challenges=(), child="1"):
    _access, _assignment, adapter, specs, _request = context
    request = DelegationRequest(
        agent_name="review-lead-verifier", task="Independently verify", context="{}"
    )
    prepared = adapter.prepare(specs["review-lead-verifier"], request, "lead-verifier-" + child)
    payload = json.loads(prepared.prompt.split("\n", 1)[1])
    assert (
        "final_report" in payload and "verification_history" not in payload["specialist_reports"][0]
    )
    assert {t.name for t in prepared.tools} == {"read_specialist_report"}
    return prepared.accept(LeadVerifierOutput(decision=decision, challenges=list(challenges)))[
        "result_ref"
    ]


def test_early_publication_returns_actionable_requirements(context):
    access, assignment, *_ = context
    result = PublicationCapabilities(access).publish()
    assert not result["published"]
    assert any(assignment in message for message in result["blockers"])
    assert not (access.store.output_dir / "bundle").exists()


@pytest.mark.parametrize(
    "change, message",
    [
        ({"severity": "critical"}, "exceeds verified support"),
        ({"locator": "source://b.csv#rows=2:2"}, "not copied"),
    ],
)
def test_invalid_lead_cannot_reach_independent_verification_or_publication(ready, change, message):
    access, *_ = ready
    capabilities = PublicationCapabilities(access)
    result = capabilities.prepare(_lead(ready, **change))
    assert result["status"] == "invalid" and any(message in b for b in result["blockers"])
    with pytest.raises(ValueError, match="structurally valid"):
        _verify(ready)
    assert not capabilities.publish()["published"]
    repaired = capabilities.prepare(_lead(ready, child="repair"))
    assert repaired["status"] == "draft"
    assert capabilities.apply(_verify(ready))["accepted"]


def test_completed_bundle_is_compatible_sealed_and_idempotent(ready):
    access, _assignment, *_ = ready
    capabilities = PublicationCapabilities(access)
    capabilities.prepare(_lead(ready))
    assert not capabilities.publish()["published"]
    receipt = capabilities.apply(_verify(ready))
    assert receipt["accepted"]
    result = capabilities.publish()
    assert result["published"] and result["unresolved_items"] > 0
    path = Path(result["bundle_path"])
    bundle = load_completed_run(path)
    assert bundle.run.run_id == "RUN-A"
    assert bundle.final_report.key_findings[0].derived_from == ["RISK-F1"]
    assert bundle.specialist_reports
    assert bundle.lead_verification_history[0]["decision"] == "pass"
    assert capabilities.publish() == result
    assert not list(access.store.output_dir.glob(".bundle-*"))
    assert access.store.read().status == "completed"
    load_sealed_bundle(path, result["seal"])
    (path / "final_findings.md").write_text("Corrupted markdown")
    with pytest.raises(RuntimeError, match="hash changed"):
        capabilities.publish()


def test_semantic_revision_uses_existing_targeted_suppression_rules(ready):
    access, *_ = ready
    capabilities = PublicationCapabilities(access)
    capabilities.prepare(_lead(ready))
    challenge = {
        "challenge_type": "introduced_causality",
        "materiality": "medium",
        "explanation": "This conclusion overstates the scoped observation.",
        "affected_finding_ids": ["FINAL-1"],
    }
    first = capabilities.apply(_verify(ready, decision="revise", challenges=[challenge]))
    assert first["status"] == "revise" and not first["accepted"]
    capabilities.prepare(_lead(ready, child="2"))
    last = capabilities.apply(_verify(ready, decision="revise", challenges=[challenge], child="2"))
    assert last["accepted"]
    assert access.store.read().lead_state["final_report"]["key_findings"] == []
    assert "suppressed" in " ".join(
        access.store.read().lead_state["final_report"]["unresolved_questions"]
    )
    assert capabilities.publish()["published"]


def test_stage_failure_never_seals_completion(ready, monkeypatch):
    import data_agent.tools.review_publication as publication

    access, *_ = ready
    capabilities = PublicationCapabilities(access)
    capabilities.prepare(_lead(ready))
    capabilities.apply(_verify(ready))

    def fail(*args):
        raise RuntimeError("injected incomplete artifact write")

    monkeypatch.setattr(publication, "load_completed_run", fail)
    with pytest.raises(RuntimeError, match="injected"):
        capabilities.publish()
    assert access.store.read().status == "running"
    assert not (access.store.output_dir / "bundle").exists()
    assert not list(access.store.output_dir.glob(".bundle-*"))


def test_stale_or_tampered_lead_acceptance_cannot_publish(ready):
    access, _assignment, *_ = ready
    capabilities = PublicationCapabilities(access)
    capabilities.prepare(_lead(ready))
    reference = _verify(ready)
    capabilities.apply(reference)
    access.store.update(lambda r: r.role_results[reference]["output"].update(feedback="tampered"))
    with pytest.raises(ValueError, match="integrity"):
        capabilities.publish()
    assert not (access.store.output_dir / "bundle").exists()


def test_collection_namespaces_same_domain_assignments_and_history(ready):
    from data_agent.review.synthesis.collection import collect_reports

    access, assignment, *_ = ready
    record = access.store.read()
    duplicate = record.assignments[assignment].model_copy(deep=True)
    duplicate.assignment_id = "task-secondassignment"
    record.assignments[duplicate.assignment_id] = duplicate
    reports, identities = collect_reports(record)
    assert len(reports) == 1
    report = reports[0]
    assert len({f.finding_id for f in report.findings}) == 2
    assert set(report.verification_history) == {f.finding_id for f in report.findings}
    for aid, mapping in identities.items():
        assert mapping["RISK-F1"].endswith(aid[5:13])
    assert len({o.overview_id for o in report.data_overviews}) == len(report.data_overviews)


def test_each_derived_finding_must_contribute_its_own_evidence(ready):
    from data_agent.review.domain.reports import FinalReport
    from data_agent.review.synthesis.collection import collect_reports
    from data_agent.review.synthesis.validation import validate_final_report

    access, *_ = ready
    capabilities = PublicationCapabilities(access)
    capabilities.prepare(_lead(ready))
    record = access.store.read()
    reports, _ = collect_reports(record)
    other = reports[0].findings[0].model_copy(deep=True)
    other.finding_id = "RISK-F2"
    other.evidence[0].locator = "source://a.csv#rows=3:3"
    reports[0].findings.append(other)
    report = FinalReport.model_validate(record.lead_state["final_report"])
    report.key_findings[0].derived_from.append("RISK-F2")
    blockers = validate_final_report(capabilities._request(record, reports, []), report)
    assert any("RISK-F2 requires its own copied evidence" in b for b in blockers)
