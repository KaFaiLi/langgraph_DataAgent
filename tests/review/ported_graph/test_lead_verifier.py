"""Deterministic lead-verification guards (all LLM calls are faked)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.reports import (
    CrossSourceCluster,
    FinalReport,
    SpecialistReport,
)
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import (
    LeadChallenge,
    LeadChallengeType,
    ObjectionMateriality,
    ReviewIssue,
    ReviewIssueKind,
    VerifierDecision,
)
from data_agent.review.ingestion.catalog import build_catalog
from data_agent.review.synthesis.lead_review import (
    MAX_LEAD_UNRESOLVED_ITEMS,
    LeadDraft,
    LeadFinalFinding,
    _collect,
    _finding_payload,
    _repair_report_structure,
)
from data_agent.review.synthesis.lead_verifier import LeadVerifierOutput, lead_verifier
from tests.review.fixtures.builder import make_risky_tree

LOCATOR = "source://risk_metrics/risk.csv#rows=2:2"
PERIOD = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))


def test_lead_draft_can_disclose_every_bounded_specialist_candidate() -> None:
    questions = [f"Question {index}" for index in range(MAX_LEAD_UNRESOLVED_ITEMS)]
    draft = LeadDraft(
        executive_summary="summary",
        overall_desk_risk_assessment="assessment",
        unresolved_questions=questions,
    )
    assert draft.unresolved_questions == questions


def test_lead_output_boundary_repairs_verbose_model_values() -> None:
    finding = _report().key_findings[0].model_dump(mode="json")
    finding["statement"] = "s" * 1_200
    finding["derived_from"] = [f"RISK-{index:03d}" for index in range(12)]
    draft = LeadDraft(
        executive_summary="e" * 3_000,
        overall_desk_risk_assessment="a" * 2_000,
        key_findings=[finding] * 11,
        control_weaknesses=["w" * 700] * 12,
        unresolved_questions=["q" * 700] * 40,
    )

    assert len(draft.executive_summary) == 2_500
    assert len(draft.overall_desk_risk_assessment) == 1_800
    assert len(draft.key_findings) == 8
    assert isinstance(draft.key_findings[0], LeadFinalFinding)
    assert len(draft.key_findings[0].statement) == 900
    assert len(draft.key_findings[0].derived_from) == 8
    assert len(draft.control_weaknesses) == 8
    assert len(draft.control_weaknesses[0]) == 500
    assert len(draft.unresolved_questions) == 32


def test_lead_finding_payload_keeps_locators_but_drops_repeated_quotes() -> None:
    payload = _finding_payload(
        [
            {
                "finding_id": "RISK-001",
                "title": "Title",
                "claim": "Claim",
                "evidence": [{"locator": LOCATOR, "quote": "large repeated quote"}],
                "counter_evidence": [
                    {
                        "locator": "source://risk_metrics/risk.csv#rows=3:3",
                        "quote": "quote",
                    }
                ],
                "alternative_explanations": ["alternative"],
            }
        ]
    )

    assert payload[0]["evidence"] == [{"locator": LOCATOR}]
    assert payload[0]["counter_evidence"] == [
        {"locator": "source://risk_metrics/risk.csv#rows=3:3"}
    ]
    assert "quote" not in str(payload)


def test_lead_collection_preserves_specialist_review_issues() -> None:
    specialist = SpecialistReport(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="risk_metrics",
        title="Risk Metrics Review",
        review_period=PERIOD,
        generated_at=datetime.now(UTC),
        scope="scope",
        overall_conclusion="conclusion",
        issues=[
            ReviewIssue(
                issue_id="omitted-candidate:C-1",
                kind=ReviewIssueKind.OMITTED_CANDIDATE,
                description="Material signal was not resolved.",
                material=True,
                candidate_ids=["C-1"],
            )
        ],
    )

    collected = _collect(
        {"specialist_reports": {"risk_metrics": specialist.model_dump(mode="json")}}
    )

    assert collected["issues"][0]["issue_id"] == "omitted-candidate:C-1"


def _state(tmp_path, report: FinalReport) -> dict:
    source = tmp_path / "source"
    make_risky_tree(source)
    finding = Finding(
        finding_id="RISK-001",
        title="Risk limit breach",
        category="risk",
        severity=Severity.HIGH,
        confidence=0.8,
        claim="Risk exceeded its limit.",
        evidence=[EvidenceReference(locator=LOCATOR)],
        verifier_status=VerificationStatus.PASSED,
    )
    specialist = SpecialistReport(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="risk_metrics",
        title="Risk Metrics Review",
        review_period=PERIOD,
        generated_at=datetime.now(UTC),
        scope="scope",
        findings=[finding],
        overall_conclusion="conclusion",
    )
    return {
        "source_root": str(source),
        "output_dir": str(tmp_path / "out"),
        "manifest": build_catalog(source).model_dump(mode="json"),
        "specialist_reports": {"risk_metrics": specialist.model_dump(mode="json")},
        "final_report": report.model_dump(mode="json"),
        "lead_round": 0,
    }


def _pass_provider(calls: list[str]):
    def provider(_tier, schema=None):
        assert schema is LeadVerifierOutput
        calls.append("lead")
        return RunnableLambda(lambda _messages: LeadVerifierOutput(decision=VerifierDecision.PASS))

    return provider


def _report(*, derived_from: list[str] | None = None) -> FinalReport:
    return FinalReport(
        executive_summary="summary",
        overall_desk_risk_assessment="assessment",
        key_findings=[
            {
                "final_id": "KF-001",
                "title": "Limit breach",
                "severity": "high",
                "confidence": 0.8,
                "statement": "Risk exceeded its limit.",
                "derived_from": derived_from or ["RISK-001"],
                "evidence": [{"locator": LOCATOR}],
            }
        ],
        evidence_index=[EvidenceReference(locator=LOCATOR)],
    )


def test_lead_report_structure_is_repaired_from_exact_specialist_support() -> None:
    verified = Finding(
        finding_id="RISK-001",
        title="Verified limit breach",
        category="risk",
        severity=Severity.HIGH,
        confidence=0.9,
        claim="Risk exceeded its limit.",
        evidence=[EvidenceReference(locator=LOCATOR)],
        verifier_status=VerificationStatus.PASSED,
    )
    unresolved_locator = "source://risk_metrics/risk.csv#rows=3:3"
    unresolved = Finding(
        finding_id="RISK-002",
        title="Unresolved mapping",
        category="mapping",
        severity=Severity.MEDIUM,
        confidence=0.6,
        claim="Mapping may be incomplete.",
        evidence=[EvidenceReference(locator=unresolved_locator)],
        verifier_status=VerificationStatus.UNRESOLVED,
    )
    report = FinalReport(
        executive_summary="summary",
        overall_desk_risk_assessment="assessment",
        key_findings=[
            {
                "final_id": "FF-001",
                "title": "Supported conclusion",
                "severity": "critical",
                "confidence": 0.8,
                "statement": "A supported conclusion.",
                "derived_from": ["RISK-002"],
                "evidence": [{"locator": LOCATOR}],
                "unresolved_dependencies": ["RISK-001"],
            },
            {
                "final_id": "FF-002",
                "title": "Unresolved-only draft",
                "severity": "medium",
                "confidence": 0.5,
                "statement": "Not ready for promotion.",
                "derived_from": ["RISK-002"],
                "evidence": [{"locator": unresolved_locator}],
            },
        ],
    )

    repaired = _repair_report_structure(
        report,
        {
            "verified": [verified.model_dump(mode="json")],
            "unresolved": [unresolved.model_dump(mode="json")],
        },
    )

    assert [finding.final_id for finding in repaired.key_findings] == ["FF-001"]
    assert repaired.key_findings[0].derived_from == ["RISK-001"]
    assert repaired.key_findings[0].unresolved_dependencies == []
    assert repaired.key_findings[0].severity is Severity.HIGH
    assert repaired.evidence_index == [
        EvidenceReference(locator=LOCATOR),
    ]
    unresolved_text = "\n".join(repaired.unresolved_questions)
    assert "Unresolved specialist finding RISK-002" in unresolved_text
    assert "FF-002" not in unresolved_text
    assert "Lead draft" not in unresolved_text


def test_lead_repair_never_promotes_specialist_counter_evidence() -> None:
    counter_locator = "source://risk_metrics/risk.csv#rows=3:3"
    verified = Finding(
        finding_id="RISK-001",
        title="Verified limit breach",
        category="risk",
        severity=Severity.HIGH,
        confidence=0.9,
        claim="Risk exceeded its limit.",
        evidence=[EvidenceReference(locator=LOCATOR)],
        counter_evidence=[EvidenceReference(locator=counter_locator)],
        verifier_status=VerificationStatus.PASSED,
    )
    report = _report()
    report.key_findings[0].evidence = [EvidenceReference(locator=counter_locator)]

    repaired = _repair_report_structure(
        report,
        {"verified": [verified.model_dump(mode="json")], "unresolved": []},
    )

    assert repaired.key_findings[0].evidence == [EvidenceReference(locator=LOCATOR)]
    assert repaired.evidence_index == [EvidenceReference(locator=LOCATOR)]


def test_lead_repair_copies_complete_primary_evidence_from_declared_support() -> None:
    second_locator = "source://risk_metrics/risk.csv#rows=3:3"
    verified = Finding(
        finding_id="RISK-001",
        title="Verified population finding",
        category="risk",
        severity=Severity.HIGH,
        confidence=0.9,
        claim="Two rows establish the population finding.",
        evidence=[
            EvidenceReference(locator=LOCATOR),
            EvidenceReference(locator=second_locator),
        ],
        verifier_status=VerificationStatus.PASSED,
    )
    report = _report()

    repaired = _repair_report_structure(
        report,
        {"verified": [verified.model_dump(mode="json")], "unresolved": []},
    )

    assert repaired.key_findings[0].evidence == [
        EvidenceReference(locator=LOCATOR),
        EvidenceReference(locator=second_locator),
    ]


def test_shared_context_locator_does_not_expand_derivation_chain() -> None:
    context_locator = "source://desk_context/desk.md#lines=20:20"
    findings = [
        Finding(
            finding_id=f"RISK-{index:03d}",
            title=f"Finding {index}",
            category="risk",
            severity=Severity.LOW,
            confidence=0.8,
            claim=f"Distinct claim {index}.",
            evidence=[
                EvidenceReference(
                    locator=f"source://risk_metrics/risk.csv#rows={index + 1}:{index + 1}"
                ),
                EvidenceReference(locator=context_locator),
            ],
            verifier_status=VerificationStatus.PASSED,
        )
        for index in range(1, 5)
    ]
    report = _report(derived_from=["RISK-001", "RISK-002", "RISK-003"])
    report.key_findings[0].evidence = [
        EvidenceReference(locator="source://risk_metrics/risk.csv#rows=2:2"),
        EvidenceReference(locator=context_locator),
    ]

    repaired = _repair_report_structure(
        report,
        {
            "verified": [finding.model_dump(mode="json") for finding in findings],
            "unresolved": [],
        },
    )

    assert repaired.key_findings[0].derived_from == ["RISK-001"]


def test_unknown_derivation_forces_revision_despite_model_pass(tmp_path) -> None:
    calls: list[str] = []
    result = lead_verifier(
        _state(tmp_path, _report(derived_from=["DOES-NOT-EXIST"])),
        {"configurable": {"llm_provider": _pass_provider(calls)}},
    )

    assert result["lead_status"] == "running"
    assert "unknown" in result["lead_feedback"].lower()


def test_missing_final_evidence_forces_revision_without_model(tmp_path) -> None:
    calls: list[str] = []
    report = _report()
    report.key_findings[0].evidence = []
    result = lead_verifier(
        _state(tmp_path, report),
        {"configurable": {"llm_provider": _pass_provider(calls)}},
    )

    assert result["lead_status"] == "running"
    assert "evidence" in result["lead_feedback"].lower()
    assert calls == []


def test_final_deterministic_failure_fails_closed_after_bound(tmp_path) -> None:
    calls: list[str] = []
    state = _state(tmp_path, _report(derived_from=["DOES-NOT-EXIST"]))
    state["lead_round"] = 1

    result = lead_verifier(
        state,
        {"configurable": {"llm_provider": _pass_provider(calls)}},
    )

    assert result["status"] == "failed"
    assert result["lead_status"] == "complete"
    assert calls == []


def test_source_mutation_fails_immediately_without_model_judgment(tmp_path) -> None:
    calls: list[str] = []
    state = _state(tmp_path, _report())
    source = Path(state["source_root"]) / "risk_metrics" / "risk.csv"
    source.write_bytes(source.read_bytes().replace(b"3.1", b"9.9", 1))

    result = lead_verifier(
        state,
        {"configurable": {"llm_provider": _pass_provider(calls)}},
    )

    assert result["status"] == "failed"
    assert result["lead_status"] == "complete"
    assert "fatal evidence integrity failure" in result["failure_reason"]
    assert calls == []


def _add_unresolved_support(state: dict, *, locator: str = LOCATOR) -> None:
    report = SpecialistReport.model_validate(state["specialist_reports"]["risk_metrics"])
    report.findings.append(
        Finding(
            finding_id="RISK-002",
            title="Unresolved risk detail",
            category="risk",
            severity=Severity.MEDIUM,
            confidence=0.5,
            claim="The source detail remains incomplete.",
            evidence=[EvidenceReference(locator=locator)],
            verifier_status=VerificationStatus.UNRESOLVED,
        )
    )
    state["specialist_reports"]["risk_metrics"] = report.model_dump(mode="json")


def test_duplicate_specialist_ids_block_model_pass(tmp_path) -> None:
    calls: list[str] = []
    state = _state(tmp_path, _report())
    duplicate = dict(state["specialist_reports"]["risk_metrics"])
    duplicate["domain"] = "pnl"
    duplicate["report_id"] = "pnl"
    state["specialist_reports"]["pnl"] = duplicate

    result = lead_verifier(state, {"configurable": {"llm_provider": _pass_provider(calls)}})

    assert result["lead_status"] == "running"
    assert "duplicate" in result["lead_feedback"].lower()
    assert calls == []


def test_severity_escalation_blocks_model_pass(tmp_path) -> None:
    calls: list[str] = []
    report = _report()
    report.key_findings[0].severity = Severity.CRITICAL

    result = lead_verifier(
        _state(tmp_path, report),
        {"configurable": {"llm_provider": _pass_provider(calls)}},
    )

    assert result["lead_status"] == "running"
    assert "exceeds" in result["lead_feedback"].lower()
    assert calls == []


def test_non_copied_evidence_blocks_model_pass(tmp_path) -> None:
    calls: list[str] = []
    report = _report()
    invented = EvidenceReference(locator="source://risk_metrics/risk.csv#rows=3:3")
    report.key_findings[0].evidence = [invented]
    report.evidence_index = [invented]

    result = lead_verifier(
        _state(tmp_path, report),
        {"configurable": {"llm_provider": _pass_provider(calls)}},
    )

    assert result["lead_status"] == "running"
    assert "not copied" in result["lead_feedback"].lower()
    assert calls == []


def test_undeclared_unresolved_support_blocks_model_pass(tmp_path) -> None:
    calls: list[str] = []
    report = _report(derived_from=["RISK-001", "RISK-002"])
    state = _state(tmp_path, report)
    _add_unresolved_support(state)

    result = lead_verifier(state, {"configurable": {"llm_provider": _pass_provider(calls)}})

    assert result["lead_status"] == "running"
    assert "unverified support" in result["lead_feedback"].lower()
    assert calls == []


def test_verified_and_declared_unresolved_support_can_pass(tmp_path) -> None:
    calls: list[str] = []
    report = _report(derived_from=["RISK-001", "RISK-002"])
    report.key_findings[0].unresolved_dependencies = ["RISK-002"]
    state = _state(tmp_path, report)
    _add_unresolved_support(state)

    result = lead_verifier(state, {"configurable": {"llm_provider": _pass_provider(calls)}})

    assert result["lead_status"] == "complete"
    assert calls == ["lead"]


def test_declared_unresolved_support_may_contribute_distinct_evidence(tmp_path) -> None:
    calls: list[str] = []
    unresolved_locator = "source://risk_metrics/risk.csv#rows=3:3"
    report = _report(derived_from=["RISK-001", "RISK-002"])
    report.key_findings[0].unresolved_dependencies = ["RISK-002"]
    report.key_findings[0].evidence.append(EvidenceReference(locator=unresolved_locator))
    report.evidence_index.append(EvidenceReference(locator=unresolved_locator))
    state = _state(tmp_path, report)
    _add_unresolved_support(state, locator=unresolved_locator)

    result = lead_verifier(state, {"configurable": {"llm_provider": _pass_provider(calls)}})

    assert result["lead_status"] == "complete"
    assert calls == ["lead"]


def test_model_verifier_receives_verified_and_unresolved_finding_ids(tmp_path) -> None:
    report = _report()
    report.unresolved_questions = ["Investigate RISK-002."]
    state = _state(tmp_path, report)
    _add_unresolved_support(state)
    captured: list[str] = []

    def provider(_tier, schema=None):
        assert schema is LeadVerifierOutput

        def answer(messages):
            captured.append("\n".join(str(message.content) for message in messages))
            return LeadVerifierOutput(decision=VerifierDecision.PASS)

        return RunnableLambda(answer)

    result = lead_verifier(state, {"configurable": {"llm_provider": provider}})

    assert result["lead_status"] == "complete"
    assert "RISK-001" in captured[0]
    assert "RISK-002" in captured[0]
    assert '"verifier_status": "unresolved"' in captured[0]


def test_unknown_cluster_and_missing_evidence_index_block_model_pass(tmp_path) -> None:
    calls: list[str] = []
    report = _report()
    report.key_findings[0].cross_source_cluster_ids = ["CLUSTER-404"]
    report.evidence_index = []

    result = lead_verifier(
        _state(tmp_path, report),
        {"configurable": {"llm_provider": _pass_provider(calls)}},
    )

    assert result["lead_status"] == "running"
    assert "cluster" in result["lead_feedback"].lower()
    assert "evidence_index" in result["lead_feedback"]
    assert calls == []


def test_evidence_index_must_include_cluster_support(tmp_path) -> None:
    calls: list[str] = []
    report = _report()
    cluster_locator = "source://risk_metrics/risk.csv#rows=3:3"
    cluster = CrossSourceCluster(
        cluster_id="CLUSTER-001",
        findings=["RISK-001"],
        supporting_evidence=[EvidenceReference(locator=cluster_locator)],
    )
    report.key_findings[0].cross_source_cluster_ids = ["CLUSTER-001"]
    report.cross_source_findings = [cluster]
    state = _state(tmp_path, report)
    state["clusters"] = [cluster.model_dump(mode="json")]
    state["specialist_reports"]["risk_metrics"]["findings"][0]["counter_evidence"] = [
        {"locator": cluster_locator}
    ]

    result = lead_verifier(
        state,
        {"configurable": {"llm_provider": _pass_provider(calls)}},
    )

    assert result["lead_status"] == "running"
    assert cluster_locator in result["lead_feedback"]
    assert "evidence_index" in result["lead_feedback"]
    assert calls == []


def test_lead_semantic_revision_is_bounded_and_history_is_json_safe(tmp_path) -> None:
    challenge = LeadChallenge(
        challenge_type=LeadChallengeType.CONTRADICTION_OMISSION,
        materiality=ObjectionMateriality.HIGH,
        explanation="The broader population contains a contradictory row.",
        affected_finding_ids=["KF-001"],
    )
    responses = iter(
        [
            LeadVerifierOutput(decision=VerifierDecision.REVISE, challenges=[challenge]),
            LeadVerifierOutput(decision=VerifierDecision.PASS),
        ]
    )

    def provider(_tier, schema=None):
        assert schema is LeadVerifierOutput
        return RunnableLambda(lambda _messages: next(responses))

    state = _state(tmp_path, _report())
    first = lead_verifier(state, {"configurable": {"llm_provider": provider}})
    state.update(first)
    assert first["lead_status"] == "running"
    assert first["lead_verification_history"][0]["challenges"][0]["challenge_type"] == (
        "contradiction_omission"
    )

    second = lead_verifier(state, {"configurable": {"llm_provider": provider}})
    assert second["lead_status"] == "complete"
    assert len(second["lead_verification_history"]) == 2
    assert second["lead_verification_history"][1]["decision"] == "pass"


def test_final_medium_objection_suppresses_target_and_rebuilds_index(tmp_path) -> None:
    challenge = LeadChallenge(
        challenge_type=LeadChallengeType.SEVERITY_INFLATION,
        materiality=ObjectionMateriality.MEDIUM,
        explanation="The conclusion is not supported at the stated severity.",
        affected_finding_ids=["KF-001"],
    )

    def provider(_tier, schema=None):
        assert schema is LeadVerifierOutput
        return RunnableLambda(
            lambda _messages: LeadVerifierOutput(
                decision=VerifierDecision.PASS,
                challenges=[challenge],
            )
        )

    state = _state(tmp_path, _report())
    state["lead_round"] = 1
    result = lead_verifier(state, {"configurable": {"llm_provider": provider}})

    assert result["lead_status"] == "complete"
    report = FinalReport.model_validate(result["final_report"])
    assert report.key_findings == []
    assert report.evidence_index == []
    assert "suppressed" in report.unresolved_questions[0]


def test_second_revise_with_targeted_medium_objection_suppresses_once(tmp_path) -> None:
    challenge = LeadChallenge(
        challenge_type=LeadChallengeType.HIDDEN_UNCERTAINTY,
        materiality=ObjectionMateriality.MEDIUM,
        explanation="The final claim hides a material uncertainty after revision.",
        affected_finding_ids=["KF-001"],
    )

    def provider(_tier, schema=None):
        assert schema is LeadVerifierOutput
        return RunnableLambda(
            lambda _messages: LeadVerifierOutput(
                decision=VerifierDecision.REVISE,
                challenges=[challenge],
            )
        )

    state = _state(tmp_path, _report())
    state["lead_round"] = 1
    result = lead_verifier(state, {"configurable": {"llm_provider": provider}})

    assert result["lead_status"] == "complete"
    assert result.get("status") != "failed"
    assert FinalReport.model_validate(result["final_report"]).key_findings == []


def test_final_high_report_wide_objection_fails_closed(tmp_path) -> None:
    challenge = LeadChallenge(
        challenge_type=LeadChallengeType.UNSUPPORTED_MISCONDUCT,
        materiality=ObjectionMateriality.HIGH,
        explanation="The report-wide misconduct language is unsupported.",
    )

    def provider(_tier, schema=None):
        assert schema is LeadVerifierOutput
        return RunnableLambda(
            lambda _messages: LeadVerifierOutput(
                decision=VerifierDecision.PASS,
                challenges=[challenge],
            )
        )

    state = _state(tmp_path, _report())
    state["lead_round"] = 1
    result = lead_verifier(state, {"configurable": {"llm_provider": provider}})

    assert result["status"] == "failed"
    assert "ambiguously targeted" in result["failure_reason"]


def test_lead_reject_and_unresolved_do_not_complete_as_accepted(tmp_path) -> None:
    for decision in (VerifierDecision.REJECT, VerifierDecision.UNRESOLVED):

        def provider(_tier, schema=None, *, decision=decision):
            assert schema is LeadVerifierOutput
            return RunnableLambda(
                lambda _messages: LeadVerifierOutput(
                    decision=decision,
                    feedback="semantic concern remains",
                )
            )

        result = lead_verifier(
            _state(tmp_path / decision.value, _report()),
            {"configurable": {"llm_provider": provider}},
        )
        assert result["status"] == "failed"
        assert result["lead_status"] == "complete"
        assert "did not pass" in result["failure_reason"]
