"""Independent low-cost challenger behavior for specialist verification."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.evidence import EvidenceReference, parse_locator
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.verification import (
    AdversarialCase,
    ChallengeResult,
    ChallengeStatus,
    ChallengeType,
    EvidenceGateResult,
    VerifierDecision,
)
from data_agent.review.ingestion.evidence_validator import EvidenceDisposition, EvidenceValidator
from data_agent.review.llm import AgentCapabilityError, ModelTier, run_bounded_structured_agent
from data_agent.review.orchestration.prompt_projection import finding_analysis_support_json
from data_agent.review.orchestration.specialist.prompts import (
    challenger_system_prompt,
)
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.schemas import (
    ChallengerChallenge,
    ChallengerOutput,
)
from data_agent.review.orchestration.specialist.scope import context_from_config
from data_agent.review.orchestration.specialist.state import (
    SpecialistState,
    loads_finding,
)
from data_agent.review.verification.rules import required_challenge_types
from data_agent.tools.research import build_research_tools


def _finding_projection(finding: Finding) -> dict[str, Any]:
    """Project a finding while hiding anchoring fields from the challenger."""

    raw = finding.model_dump(mode="json")
    hidden = {"severity", "confidence", "recommendation", "verifier_status"}
    return {key: value for key, value in raw.items() if key not in hidden}


def _strip_hidden(value: object) -> object:
    """Remove anchoring fields from nested deterministic prompt data."""

    hidden = {"severity", "confidence", "recommendation", "verifier_status"}
    if isinstance(value, Mapping):
        return {
            str(key): _strip_hidden(nested)
            for key, nested in value.items()
            if str(key).lower() not in hidden
        }
    if isinstance(value, list):
        return [_strip_hidden(item) for item in value]
    return value


def _reopened_payload(gate: EvidenceGateResult) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for reference in [*gate.reopened_primary, *gate.reopened_counter]:
        payload.append(
            {
                "locator": reference.locator,
                "snippet": gate.reopened_snippets.get(reference.locator, ""),
            }
        )
    return payload


def _assigned_paths_for_finding(finding: Finding, paths: Sequence[str]) -> list[str]:
    """Return every assigned path so the challenger can search independently.

    The finding's cited locators are an input to challenge analysis, not a
    restriction on the research population.  Searching only cited files would
    systematically miss contradictions in another assigned source.
    """

    del finding
    return list(paths)


def _evidence_validation(
    references: Sequence[EvidenceReference],
    *,
    validator: EvidenceValidator,
    assigned_paths: set[str],
) -> tuple[list[EvidenceReference], list[str], bool]:
    """Keep valid challenge evidence and return errors/fatality separately."""

    valid: list[EvidenceReference] = []
    errors: list[str] = []
    fatal = False
    summary = validator.validate_references(references)
    by_locator = {result.locator: result for result in summary.results}
    for reference in references:
        result = by_locator.get(reference.locator)
        try:
            path = parse_locator(reference.locator).path
        except ValueError as exc:
            errors.append(f"{reference.locator}: malformed locator: {exc}")
            continue
        if path not in assigned_paths:
            errors.append(f"{reference.locator}: source path is not assigned to this challenger")
            continue
        if result is None:
            errors.append(f"{reference.locator}: validator returned no result")
            continue
        if result.disposition is EvidenceDisposition.FATAL:
            fatal = True
            errors.append(f"{reference.locator}: {result.reason or 'fatal evidence failure'}")
        elif result.valid:
            valid.append(reference)
        else:
            errors.append(f"{reference.locator}: {result.reason or 'invalid evidence'}")
    return valid, errors, fatal


def _sanitize_challenge_case(
    output: ChallengerOutput,
    *,
    finding_id: str,
    validator: EvidenceValidator,
    assigned_paths: Sequence[str],
) -> AdversarialCase:
    """Validate challenge locators and make omissions material UNKNOWNs."""

    assigned = set(assigned_paths)
    unique: dict[ChallengeType, ChallengerChallenge] = {}
    for challenge in output.challenges:
        if challenge.challenge_type in unique:
            previous = unique[challenge.challenge_type]
            unique[challenge.challenge_type] = previous.model_copy(
                update={
                    "status": ChallengeStatus.UNKNOWN,
                    "material": True,
                    "explanation": (
                        previous.explanation + " Duplicate challenge category was returned."
                    ).strip(),
                    "evidence": [],
                }
            )
            continue
        unique[challenge.challenge_type] = challenge

    sanitized: list[ChallengeResult] = []
    for challenge in unique.values():
        evidence, errors, fatal = _evidence_validation(
            challenge.evidence,
            validator=validator,
            assigned_paths=assigned,
        )
        if fatal:
            raise RuntimeError("fatal evidence integrity failure in adversarial challenge")
        if errors:
            challenge = challenge.model_copy(
                update={
                    "status": ChallengeStatus.UNKNOWN,
                    "material": True,
                    "evidence": [],
                    "explanation": (
                        challenge.explanation + " Invalid challenge evidence: " + "; ".join(errors)
                    ).strip(),
                }
            )
        else:
            challenge = challenge.model_copy(update={"evidence": evidence})
        if challenge.status is ChallengeStatus.NOT_APPLICABLE and not challenge.explanation.strip():
            challenge = challenge.model_copy(
                update={
                    "status": ChallengeStatus.UNKNOWN,
                    "material": True,
                    "explanation": "NOT_APPLICABLE requires an explanation.",
                }
            )
        sanitized.append(challenge)

    required = required_challenge_types(cross_source_required=len(set(assigned_paths)) > 1)
    present = {challenge.challenge_type for challenge in sanitized}
    for challenge_type in required:
        if challenge_type not in present:
            sanitized.append(
                ChallengeResult(
                    challenge_type=challenge_type,
                    status=ChallengeStatus.UNKNOWN,
                    material=True,
                    explanation="Challenger omitted this required category.",
                )
            )

    contradictory, errors, fatal = _evidence_validation(
        output.contradictory_evidence,
        validator=validator,
        assigned_paths=assigned,
    )
    if fatal:
        raise RuntimeError("fatal evidence integrity failure in adversarial contradiction evidence")
    if errors:
        for index, challenge in enumerate(sanitized):
            if challenge.challenge_type is ChallengeType.COUNTER_EVIDENCE:
                sanitized[index] = challenge.model_copy(
                    update={
                        "status": ChallengeStatus.UNKNOWN,
                        "material": True,
                        "explanation": (
                            challenge.explanation
                            + " Invalid contradictory evidence: "
                            + "; ".join(errors)
                        ).strip(),
                        "evidence": [],
                    }
                )
                break

    complete = (
        all(
            bool(challenge.explanation.strip())
            and not (
                challenge.material
                and challenge.status in (ChallengeStatus.FAIL, ChallengeStatus.UNKNOWN)
            )
            for challenge in sanitized
            if challenge.challenge_type in required
        )
        and not errors
        and not output.unresolved_questions
    )
    return AdversarialCase(
        finding_id=finding_id,
        challenges=sanitized,
        strongest_counter_hypothesis=output.strongest_counter_hypothesis,
        contradictory_evidence=contradictory,
        unresolved_questions=list(output.unresolved_questions),
        assigned_source_paths=list(assigned_paths),
        # Completion is derived from recorded checks, not trusted from the
        # model's self-assessment. The output field remains a compatibility hint.
        research_complete=complete,
    )


def _challenger_prompt(
    runtime: SpecialistRuntime,
    finding: Finding,
    gate: EvidenceGateResult,
    state: SpecialistState,
    support: str,
    assigned_paths: Sequence[str],
) -> str:
    payload = {
        "finding": _finding_projection(finding),
        "reopened_evidence": _reopened_payload(gate),
        "assigned_source_paths": list(assigned_paths),
        "review_period": state.get("review_period", {}),
        "desk_context": state.get("desk_context", {}),
        "deterministic_support": _strip_hidden(json.loads(support)),
    }
    return json.dumps(payload, indent=2, default=str)[
        : runtime.adversarial_budget.max_context_chars
    ]


def adversarial_research(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict:
    """Run one independent low-cost challenger per evidence-valid finding."""

    ctx = context_from_config(config)
    validator = EvidenceValidator.source_backed(ctx.source_root, ctx.manifest)
    round_number = int(state.get("verifier_round", 0)) + 1
    revision = round_number > 1
    budget = runtime.adversarial_budget
    max_calls = budget.max_revision_tool_calls if revision else budget.max_initial_tool_calls
    max_cycles = budget.max_revision_cycles if revision else budget.max_initial_cycles
    cases: dict[str, dict] = {}
    traces: dict[str, list[dict]] = {
        str(finding_id): list(trace)
        for finding_id, trace in state.get("adversarial_trace", {}).items()
    }
    provider_errors: dict[str, str] = {}
    for raw in state.get("candidate_findings", []):
        finding = loads_finding(raw)
        gate_data = state.get("evidence_gates", {}).get(finding.finding_id)
        gate = EvidenceGateResult.model_validate(gate_data) if gate_data else None
        if gate is None or gate.decision is not VerifierDecision.PASS:
            continue
        assigned_paths = _assigned_paths_for_finding(finding, state.get("source_paths", []))
        trace: list[dict] = []
        tools = build_research_tools(
            ctx,
            assigned_paths,
            trace,
            max_calls=max_calls,
            research_round=round_number,
        )
        support = finding_analysis_support_json(finding, state.get("analyses", []))
        system = challenger_system_prompt(
            runtime.spec.domain_label,
            runtime.spec.policy_text,
            cross_source_required=len(set(assigned_paths)) > 1,
        )
        user = _challenger_prompt(runtime, finding, gate, state, support, assigned_paths)
        try:
            model = runtime.llm_provider(ModelTier.LOW_COST)
            output = run_bounded_structured_agent(
                model,
                tools=tools,
                system_prompt=system,
                user_prompt=user,
                schema=ChallengerOutput,
                max_cycles=max_cycles,
                name=f"{runtime.spec.domain.value}_challenger_{finding.finding_id}",
                config=config,
            )
            case = _sanitize_challenge_case(
                cast(ChallengerOutput, output),
                finding_id=finding.finding_id,
                validator=validator,
                assigned_paths=assigned_paths,
            )
        except AgentCapabilityError as exc:
            provider_errors[finding.finding_id] = str(exc)
            case = AdversarialCase(
                finding_id=finding.finding_id,
                assigned_source_paths=list(assigned_paths),
                research_complete=False,
                provider_error=True,
                unresolved_questions=["Challenger capability unavailable."],
            )
        except Exception as exc:  # noqa: BLE001 - provider failure is fail-closed
            provider_errors[finding.finding_id] = f"{type(exc).__name__}: {exc}"
            case = AdversarialCase(
                finding_id=finding.finding_id,
                assigned_source_paths=list(assigned_paths),
                research_complete=False,
                provider_error=True,
                unresolved_questions=["Challenger research failed."],
            )
        traces[finding.finding_id] = [*traces.get(finding.finding_id, []), *trace]
        cases[finding.finding_id] = case.model_dump(mode="json")

    result: dict[str, Any] = {"adversarial_cases": cases, "adversarial_trace": traces}
    if provider_errors:
        result["adversarial_errors"] = provider_errors
    return result


__all__ = [
    "_challenger_prompt",
    "_finding_projection",
    "_sanitize_challenge_case",
    "adversarial_research",
]
