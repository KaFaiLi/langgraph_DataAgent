"""Topology for the generic bounded specialist graph."""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from data_agent.review.orchestration.specialist.drafting import draft_findings
from data_agent.review.orchestration.specialist.omission import (
    audit_omission_candidates,
    route_omission,
)
from data_agent.review.orchestration.specialist.reporting import finalize, render_markdown
from data_agent.review.orchestration.specialist.research import react_research
from data_agent.review.orchestration.specialist.routing import route
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.scope import (
    inspect_material,
    prepare_scope,
    run_deterministic_analysis,
)
from data_agent.review.orchestration.specialist.state import SpecialistState
from data_agent.review.orchestration.specialist.verification import (
    adjudicate,
    adversarial_research,
    evidence_gate,
)


def build_specialist_graph(runtime: SpecialistRuntime) -> CompiledStateGraph:
    """Build one skill-configured specialist graph from frozen runtime data."""
    graph = StateGraph(SpecialistState)
    graph.add_node("prepare_scope", partial(prepare_scope, runtime))
    graph.add_node("inspect_material", partial(inspect_material, runtime))
    graph.add_node("run_deterministic_analysis", partial(run_deterministic_analysis, runtime))
    graph.add_node("react_research", partial(react_research, runtime))
    graph.add_node("draft_findings", partial(draft_findings, runtime))
    graph.add_node("evidence_gate", partial(evidence_gate, runtime))
    graph.add_node("adversarial_research", partial(adversarial_research, runtime))
    graph.add_node("adjudicate", partial(adjudicate, runtime))
    graph.add_node("omission_audit", partial(audit_omission_candidates, runtime))
    graph.add_node("finalize", partial(finalize, runtime))
    graph.add_node("render_markdown", partial(render_markdown, runtime))

    graph.add_edge(START, "prepare_scope")
    graph.add_edge("prepare_scope", "inspect_material")
    graph.add_edge("inspect_material", "run_deterministic_analysis")
    graph.add_edge("run_deterministic_analysis", "react_research")
    graph.add_edge("react_research", "draft_findings")
    graph.add_edge("draft_findings", "evidence_gate")
    graph.add_edge("evidence_gate", "adversarial_research")
    graph.add_edge("adversarial_research", "adjudicate")
    graph.add_conditional_edges(
        "adjudicate",
        route,
        {"react_research": "react_research", "omission_audit": "omission_audit"},
    )
    graph.add_conditional_edges(
        "omission_audit",
        route_omission,
        {"react_research": "react_research", "finalize": "finalize"},
    )
    graph.add_edge("finalize", "render_markdown")
    graph.add_edge("render_markdown", END)
    return graph.compile()


__all__ = ["build_specialist_graph"]
