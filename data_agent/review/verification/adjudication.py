"""High-cost no-tool adjudication behavior for specialist verification."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.finding import Finding
from data_agent.review.domain.severity import SEVERITY_ORDER, Severity
from data_agent.review.domain.verification import (
    AdjudicationResult,
    AdversarialCase,
    EvidenceGateResult,
    VerificationRound,
    VerifierDecision,
)
from data_agent.review.llm import ModelTier
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.prompt_projection import finding_analysis_support_json
from data_agent.review.orchestration.specialist.prompts import (
    adjudicator_system_prompt,
)
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.schemas import (
    AdjudicatorOutput,
)
from data_agent.review.orchestration.specialist.state import (
    SpecialistState,
    dumps_finding,
    loads_finding,
)
from data_agent.review.verification.candidates import candidate_locators
from data_agent.review.verification.reducer import reduce_verification
from data_agent.review.verification.rules import guard_adjudication, required_challenge_types


def _severity_ceiling(finding: Finding, analyses: Sequence[dict]) -> Severity | None:
    """Read an optional skill-owned ceiling from locator-matched candidates."""

    locators = {reference.locator for reference in [*finding.evidence, *finding.counter_evidence]}
    ceilings: list[Severity] = []
    for analysis in analyses:
        flags = analysis.get("flag_candidates", [])
        if not isinstance(flags, list):
            continue
        for flag in flags:
            if not isinstance(flag, dict):
                continue
            raw_locators = candidate_locators(flag)
            if not raw_locators.intersection(locators):
                continue
            value = flag.get("severity_ceiling", flag.get("max_severity"))
            try:
                if value is not None:
                    ceilings.append(Severity(str(value).lower()))
            except ValueError:
                continue
    return min(ceilings, key=lambda severity: SEVERITY_ORDER[severity]) if ceilings else None


def adjudicate(runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig) -> dict:
    """Adjudicate challenge cases, apply PASS guards, and reduce one round."""

    candidates = [loads_finding(data) for data in state.get("candidate_findings", [])]
    round_number = int(state.get("verifier_round", 0)) + 1
    raw_gates = state.get("evidence_gates", {})
    raw_cases = state.get("adversarial_cases", {})
    adjudications: dict[str, dict] = {}
    typed_results: dict[str, AdjudicationResult] = {}
    for finding in candidates:
        gate_data = raw_gates.get(finding.finding_id)
        gate = EvidenceGateResult.model_validate(gate_data) if gate_data else None
        case_data = raw_cases.get(finding.finding_id)
        case = AdversarialCase.model_validate(case_data) if case_data else None
        if gate is not None and gate.decision is not VerifierDecision.PASS:
            result = AdjudicationResult(
                finding_id=finding.finding_id,
                decision=gate.decision,
                feedback=gate.feedback or "Evidence gate did not pass.",
                checks=["evidence gate evaluated"],
                evidence_gate=gate,
                adversarial_case=case,
            )
        elif case is None:
            result = AdjudicationResult(
                finding_id=finding.finding_id,
                decision=VerifierDecision.UNRESOLVED,
                feedback="Independent adversarial research produced no case.",
                checks=["adversarial case missing"],
                evidence_gate=gate,
            )
        else:
            support = finding_analysis_support_json(finding, state.get("analyses", []))
            user = (
                f"Verification round: {round_number}\n\n"
                f"FINDING:\n{json.dumps(dumps_finding(finding), indent=2, default=str)}\n\n"
                f"EVIDENCE GATE:\n{json.dumps(gate.model_dump(mode='json') if gate else {}, indent=2)}\n\n"
                f"ADVERSARIAL CASE:\n{json.dumps(case.model_dump(mode='json'), indent=2)}\n\n"
                f"MATCHED DETERMINISTIC SUPPORT:\n{support}\n\n"
                "Return only the adjudicator schema."
            )
            try:
                runnable = runtime.llm_provider(
                    ModelTier.HIGH_COST,
                    AdjudicatorOutput,
                )
                output = cast(
                    AdjudicatorOutput,
                    invoke_structured(
                        runnable,
                        [
                            SystemMessage(
                                content=adjudicator_system_prompt(
                                    runtime.spec.domain_label,
                                    runtime.spec.policy_text,
                                )
                            ),
                            HumanMessage(content=user),
                        ],
                        schema=AdjudicatorOutput,
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - provider errors fail closed
                case = case.model_copy(
                    update={
                        "provider_error": True,
                        "research_complete": False,
                        "unresolved_questions": [
                            *case.unresolved_questions,
                            "Adjudicator provider failed.",
                        ],
                    }
                )
                result = AdjudicationResult(
                    finding_id=finding.finding_id,
                    decision=VerifierDecision.UNRESOLVED,
                    feedback=(
                        "Adjudicator provider failed; finding cannot be finalized: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    checks=["adjudicator provider failure"],
                    challenge_summary=list(case.challenges),
                    evidence_gate=gate,
                    adversarial_case=case,
                )
            else:
                result = AdjudicationResult(
                    finding_id=finding.finding_id,
                    decision=output.decision,
                    feedback=output.feedback,
                    checks=list(output.checks),
                    analyst_response=output.analyst_response,
                    challenge_summary=list(case.challenges),
                    evidence_gate=gate,
                    adversarial_case=case,
                )

        result = guard_adjudication(
            finding,
            result,
            evidence_gate=gate,
            required_types=required_challenge_types(
                cross_source_required=bool(case and len(set(case.assigned_source_paths)) > 1)
            ),
            severity_ceiling=_severity_ceiling(finding, state.get("analyses", [])),
            research_complete=case.research_complete if case else False,
            provider_error=case.provider_error if case else True,
        )
        typed_results[finding.finding_id] = result
        adjudications[finding.finding_id] = result.model_dump(mode="json")

    history: dict[str, list[VerificationRound]] = {
        finding_id: [VerificationRound.model_validate(record) for record in records]
        for finding_id, records in state.get("verification_history", {}).items()
    }
    transition = reduce_verification(
        candidates,
        typed_results,
        history,
        round_number=round_number,
        max_verifier_rounds=runtime.max_verifier_rounds,
        evidence_gates={
            finding_id: result.evidence_gate
            for finding_id, result in typed_results.items()
            if result.evidence_gate is not None
        },
        research_mode="revision" if round_number > 1 else "initial",
    )
    verified = {
        finding.finding_id: finding
        for finding in (loads_finding(item) for item in state.get("verified_findings", []))
    }
    rejected = {
        finding.finding_id: finding
        for finding in (loads_finding(item) for item in state.get("rejected_findings", []))
    }
    unresolved = {
        finding.finding_id: finding
        for finding in (loads_finding(item) for item in state.get("unresolved_findings", []))
    }
    verified.update({finding.finding_id: finding for finding in transition.verified})
    rejected.update({finding.finding_id: finding for finding in transition.rejected})
    unresolved.update({finding.finding_id: finding for finding in transition.unresolved})
    return {
        "candidate_findings": [dumps_finding(finding) for finding in transition.pending],
        "verification_history": {
            finding_id: [record.model_dump(mode="json") for record in records]
            for finding_id, records in transition.history.items()
        },
        "adjudications": adjudications,
        "verifier_round": round_number,
        "verifier_feedback": transition.feedback,
        "loop_status": "complete" if transition.complete else "running",
        "verified_findings": [dumps_finding(finding) for finding in verified.values()],
        "rejected_findings": [dumps_finding(finding) for finding in rejected.values()],
        "unresolved_findings": [dumps_finding(finding) for finding in unresolved.values()],
    }


__all__ = ["_severity_ceiling", "adjudicate"]
