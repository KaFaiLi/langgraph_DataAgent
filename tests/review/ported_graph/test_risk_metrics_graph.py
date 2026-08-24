"""Graph tests for the risk_metrics specialist: bounded loop, verifier rules.

All LLM calls are fakes (LangChain RunnableLambdas) - no network, no API.
"""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
from langchain_core.runnables import RunnableLambda

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.overview import DataOverview, OverviewStatus, TableVisual
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import VerifierDecision
from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.llm.models import ModelTier
from data_agent.review.orchestration.nodes.fanout import _sanitize_verification_collection
from data_agent.review.orchestration.specialist_graph import (
    MAX_ANALYSIS_PROMPT_CHARS,
    MAX_CANDIDATE_FINDINGS,
    MAX_PERSISTED_FINDING_EVIDENCE,
    MAX_REVISION_ANALYSIS_CHARS,
    MAX_VERIFIER_SUPPORT_CHARS,
    SpecialistSpec,
    _add_deterministic_candidate_evidence,
    _add_relevant_context_evidence,
    _apply_deterministic_severity_floor,
    _bounded_analyses_json,
    _bounded_revision_feedback,
    _finding_analysis_support_json,
    _infer_finding_period,
    _limit_candidate_findings,
    _merge_revision_findings,
    _namespace_finding_ids,
    _revision_candidates_json,
    build_specialist_graph,
)
from data_agent.review.orchestration.specialist_schemas import (
    MAX_ANALYST_FINDINGS,
    AnalystFinding,
    AnalystOutput,
    VerifierOutput,
)
from data_agent.skills.registry import build_specialist
from data_agent.tools.review_context import ToolContext

GOOD_EVIDENCE = EvidenceReference(locator="source://risk_metrics/risk.csv#rows=2:2")
BAD_EVIDENCE = EvidenceReference(locator="source://missing.csv#rows=1:1")


def test_analysis_prompt_projection_is_bounded_and_fair() -> None:
    analyses = [
        {
            "name": name,
            "summary": "summary",
            "flag_candidates": [
                {"kind": f"{name}-{index}", "detail": "x" * 5_000} for index in range(40)
            ],
            "tables": [{"rows": list(range(1_000))}],
        }
        for name in ("first", "second", "third")
    ]
    encoded = _bounded_analyses_json(analyses)
    payload = json.loads(encoded)

    assert len(encoded) <= MAX_ANALYSIS_PROMPT_CHARS
    assert [item["name"] for item in payload] == ["first", "second", "third"]
    assert all(item["flag_candidates"] for item in payload)
    assert all(item["flag_candidate_count"] == 40 for item in payload)

    revision_encoded = _bounded_analyses_json(analyses, max_chars=MAX_REVISION_ANALYSIS_CHARS)
    assert len(revision_encoded) <= MAX_REVISION_ANALYSIS_CHARS


def test_verifier_support_is_locator_matched_and_bounded() -> None:
    finding = make_finding()
    analyses = [
        {
            "name": "limit_consumption",
            "summary": "Python population calculation",
            "flag_candidates": [
                {
                    "kind": "persistent_breach",
                    "locator": GOOD_EVIDENCE.locator,
                    "breach_count": 12,
                    "detail": "x" * 30_000,
                },
                {
                    "kind": "unrelated",
                    "locator": "source://risk_metrics/risk.csv#rows=3:3",
                    "breach_count": 99,
                },
            ],
        },
        {
            "name": "workflow",
            "summary": "No matching evidence",
            "flag_candidates": [{"locator": "source://risk_metrics/risk.csv#rows=4:4"}],
        },
    ]

    encoded = _finding_analysis_support_json(finding, analyses)
    payload = json.loads(encoded)

    assert len(encoded) <= MAX_VERIFIER_SUPPORT_CHARS
    assert [item["name"] for item in payload] == ["limit_consumption"]
    assert payload[0]["matching_flag_candidates"][0]["breach_count"] == 12
    assert "unrelated" not in encoded


def test_verifier_prompt_receives_python_support_and_reopened_evidence(
    tool_ctx: ToolContext,
) -> None:
    captured: list[str] = []

    def capture_and_pass(text: str) -> VerifierOutput:
        captured.append(text)
        return pass_responder(text)

    spec = SpecialistSpec(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="risk_metrics",
        domain_label="Risk Metrics",
        policy_text="",
        analyses_runner=lambda _ctx, _paths: [
            AnalysisResult(
                name="limit_consumption",
                summary="Population-level limit calculation",
                flag_candidates=[
                    {
                        "kind": "persistent_breach",
                        "locator": GOOD_EVIDENCE.locator,
                        "population_breach_count": 12,
                    }
                ],
            )
        ],
        analyst_system_prompt=lambda *_args: "analyst",
        verifier_system_prompt=lambda _policy: "verifier",
    )
    provider = FakeProvider([AnalystOutput(findings=[make_finding()])], capture_and_pass)
    graph = build_specialist_graph(spec, llm_provider=provider)

    result = graph.invoke(initial_state(), config={"configurable": {"tool_ctx": tool_ctx}})

    assert result["report"]["findings"][0]["verifier_status"] == "passed"
    assert len(captured) == 1
    assert "REOPENED EVIDENCE:" in captured[0]
    assert "MATCHED DETERMINISTIC SUPPORT:" in captured[0]
    assert '"population_breach_count": 12' in captured[0]


def test_candidate_finding_count_is_bounded_in_analyst_priority_order() -> None:
    findings = [make_finding(f"RISK-{index:03d}") for index in range(20)]
    limited = _limit_candidate_findings(findings)
    assert len(limited) == MAX_CANDIDATE_FINDINGS
    assert [finding.finding_id for finding in limited] == [
        f"RISK-{index:03d}" for index in range(MAX_CANDIDATE_FINDINGS)
    ]


def test_analyst_output_schema_is_concise_and_matches_runtime_cap() -> None:
    assert MAX_CANDIDATE_FINDINGS == MAX_ANALYST_FINDINGS == 8
    schema = AnalystFinding.model_json_schema()
    output_schema = AnalystOutput.model_json_schema()

    assert schema["properties"]["claim"]["maxLength"] == 700
    assert schema["properties"]["evidence"]["maxItems"] == 4
    assert output_schema["properties"]["findings"]["maxItems"] == 8


def test_analyst_output_deterministically_bounds_verbose_live_model_values() -> None:
    payload = make_finding().model_dump(mode="json")
    payload["claim"] = "x" * 1_000
    payload["analysis_performed"] = ["y" * 500] * 7
    payload["alternative_explanations"] = ["z" * 500] * 6
    payload["evidence"] = [GOOD_EVIDENCE.model_dump(mode="json")] * 7

    output = AnalystOutput(findings=[payload] * 11, revision_notes="n" * 900)

    assert len(output.findings) == 8
    assert len(output.findings[0].claim) == 700
    assert len(output.findings[0].analysis_performed) == 4
    assert all(len(item) == 300 for item in output.findings[0].analysis_performed)
    assert len(output.findings[0].alternative_explanations) == 3
    assert len(output.findings[0].evidence) == 4
    assert len(output.revision_notes) == 600


def test_specialist_finding_ids_are_globally_namespaced() -> None:
    findings = [make_finding("F-001"), make_finding("RISK-F-002")]
    namespaced = _namespace_finding_ids(findings, "RISK")
    assert [finding.finding_id for finding in namespaced] == [
        "RISK-F-001",
        "RISK-F-002",
    ]


def test_missing_finding_period_is_inferred_from_matching_deterministic_flag() -> None:
    finding = make_finding()
    finding.period = None
    inferred = _infer_finding_period(
        finding,
        [
            {
                "flag_candidates": [
                    {
                        "locator": GOOD_EVIDENCE.locator,
                        "event_date": "2025-03-11",
                    }
                ]
            }
        ],
    )

    assert inferred.period == DateRange(start=date(2025, 3, 11), end=date(2025, 3, 11))


def test_exact_python_flag_can_apply_policy_owned_severity_floor() -> None:
    finding = make_finding().model_copy(update={"severity": Severity.LOW})

    calibrated = _apply_deterministic_severity_floor(
        finding,
        [
            {
                "flag_candidates": [
                    {
                        "locator": GOOD_EVIDENCE.locator,
                        "kind": "material_representation_divergence",
                        "severity_floor": "high",
                        "measured_observation": True,
                    },
                    {
                        "locator": "source://risk_metrics/risk.csv#rows=3:3",
                        "severity_floor": "critical",
                    },
                ]
            }
        ],
    )

    assert calibrated.severity is Severity.HIGH
    assert calibrated.is_observation is True


def test_severity_floor_does_not_leak_across_a_shared_evidence_row() -> None:
    finding = make_finding().model_copy(
        update={
            "severity": Severity.LOW,
            "title": "Non-final validation state on adjustment date",
            "category": "validation",
            "claim": "A validation workflow state coincides with an adjustment date.",
        }
    )

    calibrated = _apply_deterministic_severity_floor(
        finding,
        [
            {
                "flag_candidates": [
                    {
                        "locator": GOOD_EVIDENCE.locator,
                        "kind": "adjustment_offsets_unusual_daily_pnl",
                        "severity_floor": "high",
                        "severity_match_terms": ["offset", "reversal"],
                    },
                    {
                        "locator": GOOD_EVIDENCE.locator,
                        "kind": "non_final_validation_near_adjustment",
                        "severity_floor": "medium",
                        "severity_match_terms": ["validation", "non-final"],
                    },
                ]
            }
        ],
    )

    assert calibrated.severity is Severity.MEDIUM


def test_source_backed_context_facts_enrich_unit_dependent_evidence() -> None:
    finding = make_finding()
    finding.title = "AIR DTD and adjustment offset in MEUR"
    finding.claim = "AIR DTD is in MEUR and adjustment AMOUNTINEUR converts from EUR."
    context = {
        "source_backed_facts": [
            {
                "statement": "AIR DTD amounts are reported in MEUR.",
                "evidence": [{"locator": "source://desk_context/desk.md#lines=20:20"}],
            },
            {
                "statement": "Adjustment AMOUNTINEUR is reported in EUR for conversion.",
                "evidence": [{"locator": "source://desk_context/desk.md#lines=21:21"}],
            },
            {
                "statement": "Unrelated control framework fact.",
                "evidence": [{"locator": "source://desk_context/desk.md#lines=3:3"}],
            },
        ]
    }

    enriched = _add_relevant_context_evidence(finding, context)
    locators = {reference.locator for reference in enriched.evidence}

    assert len(enriched.evidence) <= MAX_PERSISTED_FINDING_EVIDENCE
    assert "source://desk_context/desk.md#lines=20:20" in locators
    assert "source://desk_context/desk.md#lines=21:21" in locators
    assert "source://desk_context/desk.md#lines=3:3" not in locators


def test_measured_candidate_persists_complete_bounded_population_evidence() -> None:
    finding = make_finding().model_copy(
        update={
            "title": "Repeated control override population",
            "category": "control override",
            "claim": "Six control overrides recur in one perimeter.",
        }
    )
    locators = [
        f"source://post_trade_controls/breaches.csv#rows={row}:{row}"
        for row in (4, 7, 11, 15, 18, 21)
    ]
    finding.evidence = [EvidenceReference(locator=locators[0])]

    enriched = _add_deterministic_candidate_evidence(
        finding,
        [
            {
                "flag_candidates": [
                    {
                        "kind": "recurring_override_perimeter",
                        "locator": locators[-1],
                        "locators": locators,
                        "severity_floor": "high",
                        "severity_match_terms": ["override", "control"],
                        "measured_observation": True,
                    }
                ]
            }
        ],
    )

    assert {reference.locator for reference in enriched.evidence} == set(locators)


def test_revision_omissions_retain_prior_candidates_in_original_order() -> None:
    first = make_finding("RISK-001")
    second = make_finding("RISK-002")
    revised_second = second.model_copy(update={"title": "Revised second"})

    merged, revised_ids = _merge_revision_findings([first, second], [revised_second])

    assert [finding.finding_id for finding in merged] == ["RISK-001", "RISK-002"]
    assert merged[0].title == first.title
    assert merged[1].title == "Revised second"
    assert revised_ids == {"RISK-002"}


def test_revision_context_retains_every_candidate_and_feedback_section() -> None:
    candidates = [
        make_finding(f"RISK-{index:03d}").model_dump(mode="json")
        for index in range(MAX_CANDIDATE_FINDINGS)
    ]
    encoded = _revision_candidates_json(candidates)
    assert all(f"RISK-{index:03d}" in encoded for index in range(MAX_CANDIDATE_FINDINGS))

    sections = [f"[RISK-{index:03d}] " + "x" * 5_000 for index in range(12)]
    bounded = _bounded_revision_feedback("\n\n---\n\n".join(sections), max_chars=12_000)
    assert len(bounded) <= 12_000
    assert all(f"RISK-{index:03d}" in bounded for index in range(12))


def make_finding(
    finding_id: str = "RISK-001",
    *,
    evidence: list[EvidenceReference] | None = None,
    is_observation: bool = False,
) -> Finding:
    return Finding(
        finding_id=finding_id,
        title="VaR breach cluster",
        category="limit_breach",
        severity=Severity.HIGH,
        confidence=0.8,
        claim="Exposure exceeded the effective limit for three consecutive days.",
        period=DateRange(start=date(2025, 1, 2), end=date(2025, 1, 6)),
        evidence=evidence if evidence is not None else [GOOD_EVIDENCE],
        is_observation=is_observation,
    )


class FakeProvider:
    """Records (tier, schema) usage and answers with canned outputs."""

    def __init__(self, analyst_queue, verifier_responder):
        self.analyst_queue = list(analyst_queue)
        self.verifier_responder = verifier_responder
        self.calls: list[tuple[str, ModelTier]] = []
        self.analyst_system_prompts: list[str] = []

    def __call__(self, tier, schema=None):
        from data_agent.review.orchestration.specialist_schemas import (
            AnalystOutput as AO,
        )
        from data_agent.review.orchestration.specialist_schemas import (
            VerifierOutput as VO,
        )

        if schema is AO:
            self.calls.append(("analyst", tier))
            assert tier is ModelTier.LOW_COST, "analyst must use the low-cost model"
            assert self.analyst_queue, "fake analyst queue exhausted"
            output = self.analyst_queue.pop(0)
            return RunnableLambda(lambda messages: self._analyst(messages, output))
        if schema is VO:
            self.calls.append(("verifier", tier))
            assert tier is ModelTier.HIGH_COST, "verifier must use the high-cost model"
            return RunnableLambda(lambda messages: self.verifier_responder(_user_text(messages)))
        raise AssertionError(f"unexpected schema {schema}")

    def _analyst(self, messages, output):
        system = "\n".join(
            str(getattr(message, "content", "")) for message in messages if message.type == "system"
        )
        self.analyst_system_prompts.append(system)
        return output


def _user_text(messages) -> str:
    return "\n".join(
        str(getattr(message, "content", "")) for message in messages if message.type != "system"
    )


def _finding_id_from(text: str) -> str:
    match = re.search(r'"finding_id":\s*"([^"]+)"', text)
    return match.group(1) if match else "RISK-001"


def _round_from(text: str) -> int:
    match = re.search(r"Verification round:\s*(\d+)", text)
    return int(match.group(1)) if match else 1


def pass_responder(text: str) -> VerifierOutput:
    return VerifierOutput(
        finding_id=_finding_id_from(text),
        decision=VerifierDecision.PASS,
        questions=[],
        checks=["locators reopened by code"],
    )


def revise_once_then_pass(text: str) -> VerifierOutput:
    if _round_from(text) == 1:
        return VerifierOutput(
            finding_id=_finding_id_from(text),
            decision=VerifierDecision.REVISE,
            feedback="Add the missing alternative explanations.",
        )
    return pass_responder(text)


def always_revise(text: str) -> VerifierOutput:
    return VerifierOutput(
        finding_id=_finding_id_from(text),
        decision=VerifierDecision.REVISE,
        feedback="Still not good enough.",
    )


def reject_responder(text: str) -> VerifierOutput:
    return VerifierOutput(
        finding_id=_finding_id_from(text),
        decision=VerifierDecision.REJECT,
        feedback="Claim unsupported by cited evidence.",
    )


def initial_state() -> dict:
    return {
        "task_id": "T-1",
        "domain": "risk_metrics",
        "report_id": "RISK",
        "domain_label": "Risk Metrics",
        "source_ids": [],
        "source_paths": ["risk_metrics/risk.csv"],
        "desk_context": DeskContext(
            desk_name="EM Rates",
            business_description="EM rates market making.",
            review_start=date(2025, 1, 1),
            review_end=date(2025, 6, 30),
        ).model_dump(mode="json"),
        "review_period": {"start": "2025-01-01", "end": "2025-06-30"},
    }


def run_graph(tool_ctx: ToolContext, provider: FakeProvider):
    graph = build_specialist(SpecialistDomain.RISK_METRICS, llm_provider=provider)
    return graph.invoke(initial_state(), config={"configurable": {"tool_ctx": tool_ctx}})


def test_happy_path_pass(tool_ctx: ToolContext) -> None:
    provider = FakeProvider([AnalystOutput(findings=[make_finding()])], pass_responder)
    result = run_graph(tool_ctx, provider)

    assert result["loop_status"] == "complete"
    assert result["verifier_round"] == 1
    report_findings = result["report"]["findings"]
    assert len(report_findings) == 1
    assert report_findings[0]["verifier_status"] == "passed"
    assert len(result["initial_candidates"]) == 1  # eval telemetry (D7)
    assert result["error"] is None
    assert [view["overview_id"] for view in result["report"]["data_overviews"]] == [
        "risk-metrics.limit-utilization"
    ]


def test_markdown_matches_standard_template(tool_ctx: ToolContext) -> None:
    provider = FakeProvider([AnalystOutput(findings=[make_finding()])], pass_responder)
    result = run_graph(tool_ctx, provider)
    markdown = result["markdown"]
    for heading in (
        "## Review Metadata",
        "## Scope",
        "## Sources Reviewed",
        "## Analysis Performed",
        "## Data Overview",
        "## Findings",
        "### RISK-001 — VaR breach cluster",
        "#### Observation",
        "#### Evidence",
        "#### Analysis",
        "#### Alternative Explanations",
        "#### Counter Evidence",
        "#### Verifier Questions",
        "#### Analyst Response",
        "#### Verifier Conclusion",
        "#### Recommendation",
        "## Unresolved Items",
        "## Overall Conclusion",
    ):
        assert heading in markdown, f"missing heading {heading!r}"


def test_revise_then_pass_records_history(tool_ctx: ToolContext) -> None:
    revised = make_finding()
    revised.alternative_explanations = ["Seasonal rebalancing could explain the move."]
    provider = FakeProvider(
        [
            AnalystOutput(findings=[make_finding()]),
            AnalystOutput(
                findings=[revised],
                revision_notes="Added alternative explanations per feedback.",
            ),
        ],
        revise_once_then_pass,
    )
    result = run_graph(tool_ctx, provider)

    assert result["loop_status"] == "complete"
    assert result["verifier_round"] == 2
    history = result["verification_history"]["RISK-001"]
    assert len(history) == 2
    assert history[0]["decision"] == "revise"
    assert history[0]["analyst_response"] == "Added alternative explanations per feedback."
    assert history[1]["decision"] == "pass"
    assert result["report"]["findings"][0]["verifier_status"] == "passed"


def test_exhausted_rounds_become_unresolved(tool_ctx: ToolContext) -> None:
    provider = FakeProvider(
        [AnalystOutput(findings=[make_finding()]), AnalystOutput(findings=[make_finding()])],
        always_revise,
    )
    result = run_graph(tool_ctx, provider)

    assert result["loop_status"] == "complete"
    assert result["verifier_round"] == 2  # bounded: exactly max rounds
    verifier_calls = sum(1 for kind, _ in provider.calls if kind == "verifier")
    assert verifier_calls == 2  # one per round, never more
    assert result["report"]["findings"][0]["verifier_status"] == "unresolved"
    assert result["report"]["unresolved_items"]
    assert "Still not good enough" in result["report"]["unresolved_items"][0]


def test_rejected_finding_removed(tool_ctx: ToolContext) -> None:
    provider = FakeProvider([AnalystOutput(findings=[make_finding()])], reject_responder)
    result = run_graph(tool_ctx, provider)

    assert result["loop_status"] == "complete"
    assert result["report"]["findings"] == []
    assert len(result["rejected_findings"]) == 1
    assert result["rejected_findings"][0]["verifier_status"] == "rejected"
    assert "RISK-001" in result["verification_history"]


def test_inaccessible_evidence_never_consults_llm(tool_ctx: ToolContext) -> None:
    def _explode(_text: str) -> VerifierOutput:
        raise AssertionError("verifier LLM must not be called for inaccessible evidence")

    provider = FakeProvider(
        [AnalystOutput(findings=[make_finding(evidence=[BAD_EVIDENCE])])], _explode
    )
    result = run_graph(tool_ctx, provider)

    assert result["loop_status"] == "complete"
    assert result["report"]["findings"][0]["verifier_status"] == "unresolved"
    assert result["report"]["findings"][0]["evidence"] == []
    history = result["verification_history"]["RISK-001"]
    assert history[0]["decision"] == "unresolved"
    assert "locator reopened: FAILED" in history[0]["checks"][0]
    assert sum(1 for kind, _ in provider.calls if kind == "verifier") == 0


def test_verification_artifact_separates_bad_citations(tool_ctx: ToolContext) -> None:
    finding = make_finding(evidence=[BAD_EVIDENCE])
    validator = EvidenceValidator.source_backed(tool_ctx.source_root, tool_ctx.manifest)

    sanitized, failures = _sanitize_verification_collection(
        [finding.model_dump(mode="json")], validator
    )

    assert sanitized[0]["evidence"] == []
    assert failures[0]["finding_id"] == "RISK-001"
    assert failures[0]["locator"] == BAD_EVIDENCE.locator


def test_inaccessible_counter_evidence_never_consults_llm(tool_ctx: ToolContext) -> None:
    def _explode(_text: str) -> VerifierOutput:
        raise AssertionError("verifier LLM must not be called for inaccessible counter evidence")

    finding = make_finding()
    finding.counter_evidence = [BAD_EVIDENCE]
    provider = FakeProvider([AnalystOutput(findings=[finding])], _explode)

    result = run_graph(tool_ctx, provider)

    assert result["report"]["findings"][0]["verifier_status"] == "unresolved"
    assert sum(1 for kind, _ in provider.calls if kind == "verifier") == 0


def test_changed_overview_evidence_fails_specialist_run(tool_ctx: ToolContext) -> None:
    source = tool_ctx.source_root / "risk_metrics" / "risk.csv"
    source.write_bytes(source.read_bytes().replace(b"3.1", b"9.9", 1))
    overview = DataOverview(
        overview_id="risk-metrics.changed-source",
        domain=SpecialistDomain.RISK_METRICS,
        source_family="risk_metrics",
        title="Changed source overview",
        summary="A deterministic overview.",
        status=OverviewStatus.AVAILABLE,
        visual=TableVisual(columns=["value"], rows=[["1"]]),
        evidence=[GOOD_EVIDENCE],
    )
    spec = SpecialistSpec(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="risk_metrics",
        domain_label="Risk Metrics",
        policy_text="",
        analyses_runner=lambda _ctx, _paths: [
            AnalysisResult(name="overview", summary="summary", overviews=[overview])
        ],
        analyst_system_prompt=lambda *_args: "analyst",
        verifier_system_prompt=lambda _policy: "verifier",
    )
    provider = FakeProvider([AnalystOutput(findings=[])], pass_responder)
    graph = build_specialist_graph(spec, llm_provider=provider)

    with pytest.raises(RuntimeError, match="fatal evidence integrity failure"):
        graph.invoke(initial_state(), config={"configurable": {"tool_ctx": tool_ctx}})


def test_pass_without_evidence_is_forced_to_revise(tool_ctx: ToolContext) -> None:
    # Verifier says PASS, but the finding has no evidence: the deterministic
    # guard must convert PASS -> REVISE; the analyst then adds evidence.
    without_evidence = make_finding(evidence=[])
    with_evidence = make_finding(evidence=[GOOD_EVIDENCE])
    provider = FakeProvider(
        [
            AnalystOutput(findings=[without_evidence]),
            AnalystOutput(
                findings=[with_evidence],
                revision_notes="Added evidence locator per verifier.",
            ),
        ],
        pass_responder,
    )
    result = run_graph(tool_ctx, provider)

    assert result["verifier_round"] == 2
    history = result["verification_history"]["RISK-001"]
    assert history[0]["decision"] == "revise"
    assert "evidence" in history[0]["feedback"].lower()
    assert history[1]["decision"] == "pass"
    assert result["report"]["findings"][0]["verifier_status"] == "passed"


def test_model_allocation_flash_analyst_pro_verifier(tool_ctx: ToolContext) -> None:
    provider = FakeProvider([AnalystOutput(findings=[make_finding()])], pass_responder)
    run_graph(tool_ctx, provider)
    assert ("analyst", ModelTier.LOW_COST) in provider.calls
    assert ("verifier", ModelTier.HIGH_COST) in provider.calls
    assert "Review SGMR limit-consumption history" in provider.analyst_system_prompts[0]


def test_no_findings_still_produces_report(tool_ctx: ToolContext) -> None:
    provider = FakeProvider([AnalystOutput(findings=[])], pass_responder)
    result = run_graph(tool_ctx, provider)
    assert result["loop_status"] == "complete"
    assert result["report"]["findings"] == []
    assert "No findings." in result["markdown"]


def test_observation_without_evidence_can_pass(tool_ctx: ToolContext) -> None:
    observation = make_finding(evidence=[], is_observation=True)
    provider = FakeProvider([AnalystOutput(findings=[observation])], pass_responder)
    result = run_graph(tool_ctx, provider)
    assert result["verifier_round"] == 1
    assert result["report"]["findings"][0]["verifier_status"] == "passed"


def test_verifier_status_enum_mapping(tool_ctx: ToolContext) -> None:
    provider = FakeProvider([AnalystOutput(findings=[make_finding()])], pass_responder)
    result = run_graph(tool_ctx, provider)
    finding = Finding.model_validate(result["report"]["findings"][0])
    assert finding.verifier_status is VerificationStatus.PASSED
