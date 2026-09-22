"""Lead verifier: independent check of the final synthesis (high-cost model).

The verifier has one semantic revision opportunity.  Deterministic report and
evidence gates always fail closed; a persistent semantic objection is never
accepted merely because the round budget was exhausted.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.reports import (
    CrossSourceCluster,
    FinalReport,
    SpecialistReport,
)
from data_agent.review.domain.verification import (
    LeadChallenge,
    VerifierDecision,
)
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.llm.models import ModelTier
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.state import ParentState
from data_agent.review.synthesis.lead_policy import (
    _apply_final_round_challenges as apply_final_challenges,
)
from data_agent.review.synthesis.lead_policy import (
    _challenge_feedback,
    _needs_semantic_revision,
)
from data_agent.review.synthesis.validation import (
    FatalEvidenceIntegrityError,
    FinalValidationRequest,
)
from data_agent.review.synthesis.validation import (
    _specialist_findings as _index_specialist_findings,
)
from data_agent.review.synthesis.validation import (
    validate_final_report as validate_report,
)
from data_agent.skills.review import load_lead_review_skill
from data_agent.tools.review_context import ToolContext

MAX_LEAD_ROUNDS = 2
MAX_LEAD_CHALLENGES = 32
MAX_LEAD_CHECKS = 64
MAX_LEAD_FEEDBACK = 4_000


def __getattr__(name: str):
    if name == "LEAD_VERIFIER_SYSTEM":
        return load_lead_review_skill().verifier_policy
    raise AttributeError(name)


from data_agent.review.domain.lead_outputs import LeadVerifierOutput


def _provider(config: RunnableConfig) -> ReviewLLMProvider:
    provider = (config or {}).get("configurable", {}).get("llm_provider")
    if provider is None:
        return DEFAULT_LLM_PROVIDER
    return provider


def _ctx(state: ParentState) -> ToolContext:
    """Build the run tool context from parent state (no config dependency)."""
    from pathlib import Path

    from data_agent.review.domain.source import SourceManifest

    manifest = SourceManifest.model_validate(state["manifest"])
    return ToolContext(
        source_root=Path(state["source_root"]),
        workspace_root=Path(state["output_dir"]) / "workspace",
        manifest=manifest,
    )


def _validation_request(state: ParentState) -> FinalValidationRequest:
    return FinalValidationRequest(
        _ctx(state),
        [SpecialistReport.model_validate(r) for r in state.get("specialist_reports", {}).values()],
        [CrossSourceCluster.model_validate(c) for c in state.get("clusters", [])],
    )


def _specialist_findings(state: ParentState):
    return _index_specialist_findings(_validation_request(state))


def validate_final_report(state: ParentState, report: FinalReport) -> list[str]:
    return validate_report(_validation_request(state), report)


def _prior_lead_history(state: ParentState) -> list[dict]:
    """Return prior lead rounds as plain JSON-compatible mappings.

    Parent checkpoints intentionally contain primitives rather than Pydantic
    instances.  Be defensive when resuming an older checkpoint that did not
    have a lead history field yet.
    """
    history = state.get("lead_verification_history", [])
    if not isinstance(history, list):
        return []
    return [dict(entry) for entry in history if isinstance(entry, dict)]


def _history_entry(
    round_number: int,
    *,
    decision: VerifierDecision,
    feedback: str = "",
    checks: Iterable[str] = (),
    challenges: Iterable[LeadChallenge] = (),
) -> dict:
    """Serialize one lead-verifier result without leaking Pydantic objects."""
    return {
        "round_number": round_number,
        "decision": decision.value,
        "feedback": feedback[:MAX_LEAD_FEEDBACK],
        "checks": [str(check)[:500] for check in list(checks)[:MAX_LEAD_CHECKS]],
        "challenges": [
            challenge.model_dump(mode="json")
            for challenge in list(challenges)[:MAX_LEAD_CHALLENGES]
        ],
    }


def _with_history(state: ParentState, entry: dict) -> list[dict]:
    return [*_prior_lead_history(state), entry]


def _apply_final_round_challenges(state, report, challenges):
    return apply_final_challenges(list(state.get("clusters") or []), report, challenges)


def lead_verifier(state: ParentState, config: RunnableConfig) -> dict:
    """Verify the final report; returns the next-state update."""
    report_data = state.get("final_report")
    if not report_data:
        return {"status": "failed", "failure_reason": "lead review produced no report"}
    report = FinalReport.model_validate(report_data)
    round_number = int(state.get("lead_round", 0)) + 1
    try:
        feedback_parts = validate_final_report(state, report)
    except FatalEvidenceIntegrityError as exc:
        failure_reason = str(exc)
        history = _with_history(
            state,
            _history_entry(
                round_number,
                decision=VerifierDecision.UNRESOLVED,
                feedback=failure_reason,
                checks=["deterministic evidence integrity gate failed"],
            ),
        )
        return {
            "lead_round": round_number,
            "lead_feedback": "",
            "lead_status": "complete",
            "status": "failed",
            "failure_reason": failure_reason,
            "lead_verification_history": history,
        }
    if feedback_parts:
        feedback = "\n".join(feedback_parts)
        history = _with_history(
            state,
            _history_entry(
                round_number,
                decision=VerifierDecision.REVISE,
                feedback=feedback,
                checks=["deterministic final-report validation"],
            ),
        )
        if round_number >= MAX_LEAD_ROUNDS:
            return {
                "lead_round": round_number,
                "lead_feedback": "",
                "lead_status": "complete",
                "status": "failed",
                "failure_reason": "lead verification deterministic checks failed: " + feedback,
                "lead_verification_history": history,
            }
        return {
            "lead_round": round_number,
            "lead_feedback": feedback,
            "lead_status": "running",
            "lead_verification_history": history,
        }

    _verified, _unresolved_ids, _all_ids, _index_feedback, all_findings = _specialist_findings(
        state
    )
    specialist_findings = [
        {
            "finding_id": finding.finding_id,
            "title": finding.title,
            "verifier_status": finding.verifier_status.value,
        }
        for finding in sorted(all_findings.values(), key=lambda item: item.finding_id)
    ]

    user = (
        f"Verification round: {round_number}\n\nFINAL REPORT (JSON):\n"
        + json.dumps(report.model_dump(mode="json"), indent=2, default=str)
        + "\n\nSPECIALIST FINDINGS (verified and explicitly unresolved):\n"
        + json.dumps(specialist_findings, indent=2)
        + "\n\nReturn your structured verdict."
    )
    runnable = _provider(config)(ModelTier.HIGH_COST, LeadVerifierOutput)
    output = invoke_structured(
        runnable,
        [
            SystemMessage(content=load_lead_review_skill().verifier_policy),
            HumanMessage(content=user),
        ],
        schema=LeadVerifierOutput,
    )
    verdict = (
        output
        if isinstance(output, LeadVerifierOutput)
        else LeadVerifierOutput.model_validate(output)
    )
    challenge_feedback = _challenge_feedback(verdict.challenges)
    feedback = "\n".join(part for part in (verdict.feedback.strip(), challenge_feedback) if part)[
        :MAX_LEAD_FEEDBACK
    ]
    history = _with_history(
        state,
        _history_entry(
            round_number,
            decision=verdict.decision,
            feedback=verdict.feedback,
            checks=verdict.checks,
            challenges=verdict.challenges,
        ),
    )

    if verdict.decision in (VerifierDecision.REJECT, VerifierDecision.UNRESOLVED):
        # A semantic rejection is not a successful lead review.  Keeping the
        # report in state for diagnostics is fine, but parent routing must stop
        # with a failed run rather than finalize it as accepted.
        reason = verdict.feedback.strip() or (f"lead verifier returned {verdict.decision.value}")
        return {
            "final_report": report.model_dump(mode="json"),
            "lead_round": round_number,
            "lead_feedback": "",
            "lead_status": "complete",
            "status": "failed",
            "failure_reason": f"lead verification did not pass: {reason}",
            "lead_verification_history": history,
        }

    if verdict.decision is VerifierDecision.REVISE:
        if round_number >= MAX_LEAD_ROUNDS:
            # The one revision budget is exhausted. Apply the structured
            # final-round policy: disclose low objections, suppress precisely
            # targeted material conclusions, and fail only when safe targeting
            # is unavailable.
            final_report, clusters, _suppressed, blockers = _apply_final_round_challenges(
                state,
                report,
                verdict.challenges,
            )
            if not verdict.challenges:
                blockers.append("lead verifier requested revision without structured challenges")
            if blockers:
                reason = feedback or "lead verifier requested another revision"
                return {
                    "final_report": final_report.model_dump(mode="json"),
                    "clusters": clusters,
                    "lead_round": round_number,
                    "lead_feedback": "",
                    "lead_status": "complete",
                    "status": "failed",
                    "failure_reason": (
                        "lead verification remained unresolved after one revision: "
                        + reason
                        + "; "
                        + "; ".join(blockers)
                    ),
                    "lead_verification_history": history,
                }
            return {
                "final_report": final_report.model_dump(mode="json"),
                "clusters": clusters,
                "lead_round": round_number,
                "lead_feedback": "",
                "lead_status": "complete",
                "lead_verification_history": history,
            }
        return {
            "lead_round": round_number,
            "lead_feedback": feedback or "Lead verifier requested a concrete report revision.",
            "lead_status": "running",
            "lead_verification_history": history,
        }

    # A first-round PASS with a material objection is not final: the lead must
    # receive one opportunity to address it.  Low/informational objections can
    # be disclosed immediately because they do not block acceptance.
    if round_number < MAX_LEAD_ROUNDS and _needs_semantic_revision(verdict.challenges):
        return {
            "lead_round": round_number,
            "lead_feedback": feedback or "Lead verifier identified a material objection.",
            "lead_status": "running",
            "lead_verification_history": history,
        }

    final_report, clusters, _suppressed, blockers = _apply_final_round_challenges(
        state,
        report,
        verdict.challenges,
    )
    if blockers:
        return {
            "final_report": final_report.model_dump(mode="json"),
            "clusters": clusters,
            "lead_round": round_number,
            "lead_feedback": "",
            "lead_status": "complete",
            "status": "failed",
            "failure_reason": "lead verification failed closed: " + "; ".join(blockers),
            "lead_verification_history": history,
        }

    return {
        "final_report": final_report.model_dump(mode="json"),
        "clusters": clusters,
        "lead_round": round_number,
        "lead_feedback": "",
        "lead_status": "complete",
        "lead_verification_history": history,
    }
