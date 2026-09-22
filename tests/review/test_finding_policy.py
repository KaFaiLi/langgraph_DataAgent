"""Finding policy assertions retained from the retired specialist graphs."""

from datetime import date

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.outputs import MAX_ANALYST_FINDINGS, AnalystFinding, AnalystOutput
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.verification.finding_policy import (
    MAX_PERSISTED_FINDING_EVIDENCE,
    normalize_findings,
)

GOOD_EVIDENCE = EvidenceReference(locator="source://risk_metrics/risk.csv#rows=2:2")


def test_candidate_finding_count_is_bounded_in_analyst_priority_order() -> None:
    findings = [make_finding(f"RISK-{index:03d}") for index in range(20)]
    limited, _ = normalize_findings(findings, analyses=[], desk_context={}, report_id="RISK")
    assert len(limited) == MAX_ANALYST_FINDINGS
    assert [finding.finding_id for finding in limited] == [
        f"RISK-{index:03d}" for index in range(MAX_ANALYST_FINDINGS)
    ]


def test_analyst_output_schema_is_concise_and_matches_runtime_cap() -> None:
    assert MAX_ANALYST_FINDINGS == 8
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
    namespaced, _ = normalize_findings(findings, analyses=[], desk_context={}, report_id="RISK")
    assert [finding.finding_id for finding in namespaced] == [
        "RISK-F-001",
        "RISK-F-002",
    ]


def test_missing_finding_period_is_inferred_from_matching_deterministic_flag() -> None:
    finding = make_finding()
    finding.period = None
    normalized, _ = normalize_findings(
        [finding],
        analyses=[
            {
                "flag_candidates": [
                    {
                        "locator": GOOD_EVIDENCE.locator,
                        "event_date": "2025-03-11",
                    }
                ]
            }
        ],
        desk_context={},
        report_id="RISK",
    )
    inferred = normalized[0]

    assert inferred.period == DateRange(start=date(2025, 3, 11), end=date(2025, 3, 11))


def test_exact_python_flag_can_apply_policy_owned_severity_floor() -> None:
    finding = make_finding().model_copy(update={"severity": Severity.LOW})

    normalized, _ = normalize_findings(
        [finding],
        analyses=[
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
        desk_context={},
        report_id="RISK",
    )
    calibrated = normalized[0]

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

    normalized, _ = normalize_findings(
        [finding],
        analyses=[
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
        desk_context={},
        report_id="RISK",
    )
    calibrated = normalized[0]

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

    normalized, _ = normalize_findings(
        [finding], analyses=[], desk_context=context, report_id="RISK"
    )
    enriched = normalized[0]
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

    normalized, _ = normalize_findings(
        [finding],
        analyses=[
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
        desk_context={},
        report_id="RISK",
    )
    enriched = normalized[0]

    assert {reference.locator for reference in enriched.evidence} == set(locators)


def test_revision_omissions_retain_prior_candidates_in_original_order() -> None:
    first = make_finding("RISK-001")
    second = make_finding("RISK-002")
    revised_second = second.model_copy(update={"title": "Revised second"})

    merged, revised_ids = normalize_findings(
        [revised_second],
        analyses=[],
        desk_context={},
        report_id="RISK",
        previous=[first, second],
    )

    assert [finding.finding_id for finding in merged] == ["RISK-001", "RISK-002"]
    assert merged[0].title == first.title
    assert merged[1].title == "Revised second"
    assert revised_ids == {"RISK-002"}


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
