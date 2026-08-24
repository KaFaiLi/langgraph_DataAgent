"""Parent graph: the LangGraph that controls the whole review (spec 18).

preflight -> build_catalog -> build_desk_context -> create_review_tasks ->
LangGraph Send fan-out -> deterministic merge -> coverage gate -> synthesis -> END.

Any node may mark the run failed; failure routes to a terminal fail node
and is never silently continued (spec section 41).
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.orchestration.nodes import (
    build_catalog,
    build_desk_context,
    coverage_gate,
    create_review_tasks,
    preflight,
)
from data_agent.review.orchestration.nodes.correlate import correlate
from data_agent.review.orchestration.nodes.finalize import finalize
from data_agent.review.orchestration.nodes.fanout import (
    merge_specialist_outcomes,
    run_specialist_task,
)
from data_agent.review.orchestration.state import ParentState
from data_agent.review.synthesis.lead_review import lead_review
from data_agent.review.synthesis.lead_verifier import lead_verifier


def _ok_or_fail(state: ParentState) -> str:
    return "fail" if state.get("status") == "failed" else "ok"


def _route_lead(state: ParentState) -> str:
    if state.get("status") == "failed":
        return "fail"
    if state.get("lead_status") == "complete":
        return "finalize"
    return "lead_review"


def _dispatch_specialists(state: ParentState) -> str | list[Send]:
    tasks = list(state.get("tasks", []))
    if not tasks:
        return "merge_specialists"
    return [Send("run_specialist", {**state, "active_task": task}) for task in tasks]


def build_parent_graph(
    llm_provider: ReviewLLMProvider = DEFAULT_LLM_PROVIDER,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the parent review graph.

    preflight -> build_catalog -> build_desk_context -> create_review_tasks ->
    Send specialist branches -> merge_specialists -> coverage_gate -> correlate -> lead_review ->
    lead_verification (bounded 2 rounds) -> finalize -> END.

    ``config["configurable"]`` must provide: ``desk_template`` (DeskContext or
    dict) and ``review_period`` (DateRange); ``llm_provider`` is optional
    (injected for tests).
    """
    graph = StateGraph(ParentState)

    graph.add_node("preflight", preflight)
    graph.add_node("build_catalog", build_catalog)
    graph.add_node("build_desk_context", build_desk_context)
    graph.add_node("create_review_tasks", create_review_tasks)
    graph.add_node("run_specialist", run_specialist_task)
    graph.add_node("merge_specialists", merge_specialist_outcomes)
    graph.add_node("coverage_gate", coverage_gate)
    graph.add_node("correlate", correlate)
    graph.add_node("lead_review", lead_review)
    graph.add_node("lead_verifier", lead_verifier)
    graph.add_node("finalize", finalize)
    graph.add_node("fail", lambda state, config: {})

    graph.add_edge(START, "preflight")
    graph.add_conditional_edges("preflight", _ok_or_fail, {"ok": "build_catalog", "fail": "fail"})
    graph.add_conditional_edges(
        "build_catalog", _ok_or_fail, {"ok": "build_desk_context", "fail": "fail"}
    )
    graph.add_conditional_edges(
        "build_desk_context", _ok_or_fail, {"ok": "create_review_tasks", "fail": "fail"}
    )
    graph.add_conditional_edges(
        "create_review_tasks",
        _dispatch_specialists,
        ["run_specialist", "merge_specialists"],
    )
    graph.add_edge("run_specialist", "merge_specialists")
    graph.add_conditional_edges(
        "merge_specialists", _ok_or_fail, {"ok": "coverage_gate", "fail": "fail"}
    )
    graph.add_conditional_edges("coverage_gate", _ok_or_fail, {"ok": "correlate", "fail": "fail"})
    graph.add_edge("correlate", "lead_review")
    graph.add_edge("lead_review", "lead_verifier")
    graph.add_conditional_edges(
        "lead_verifier",
        _route_lead,
        {"finalize": "finalize", "lead_review": "lead_review", "fail": "fail"},
    )
    graph.add_conditional_edges("finalize", _ok_or_fail, {"ok": END, "fail": "fail"})
    graph.add_edge("fail", END)

    return graph.compile(checkpointer=checkpointer)
