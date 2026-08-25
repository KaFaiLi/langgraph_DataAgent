"""Thin graph-node adapters for specialist verification."""

from __future__ import annotations

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.scope import context_from_config
from data_agent.review.orchestration.specialist.state import SpecialistState, loads_finding
from data_agent.review.verification.adjudication import adjudicate
from data_agent.review.verification.challenger import adversarial_research
from data_agent.review.verification.evidence import evaluate_evidence_gate


def evidence_gate(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict:
    """Run the pure evidence gate at the graph state seam."""

    ctx = context_from_config(config)
    validator = EvidenceValidator.source_backed(ctx.source_root, ctx.manifest)
    round_number = int(state.get("verifier_round", 0)) + 1
    gates: dict[str, dict] = {}
    for raw in state.get("candidate_findings", []):
        result = evaluate_evidence_gate(
            loads_finding(raw),
            validator,
            round_number=round_number,
            max_verifier_rounds=runtime.max_verifier_rounds,
            raise_on_fatal=True,
        )
        gates[result.finding_id] = result.model_dump(mode="json")
    return {
        "evidence_gates": gates,
        "research_mode": "revision" if round_number > 1 else "initial",
    }


verify_evidence_gate = evidence_gate
run_adversarial_research = adversarial_research

__all__ = [
    "adjudicate",
    "adversarial_research",
    "evidence_gate",
    "run_adversarial_research",
    "verify_evidence_gate",
]
