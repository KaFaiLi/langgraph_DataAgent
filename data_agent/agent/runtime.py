"""Invocation ownership and isolated runtime configuration for chat graphs."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from langchain_core.callbacks import BaseCallbackManager
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import set_config_context
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.runtime import Runtime

from data_agent.agent.subagents.contracts import DelegationPolicy, InvocationContext, RunScope

if TYPE_CHECKING:
    from data_agent.agent.subagents.runner import DelegationRunner


async def invoke_scoped_graph(
    graph: Any,
    state: dict[str, Any] | None,
    *,
    config: RunnableConfig,
    context: InvocationContext,
    checkpoint_thread_id: str | None = None,
) -> dict[str, Any]:
    """Run a nested graph without inheriting checkpoint or application configuration.

    LangGraph merges ambient configurable values even when explicitly given an
    empty dict. Start the invocation in a copied, sanitized Runnable context.
    Only the installed runtime's streaming handles cross this seam; its store,
    previous state, host identity and parent checkpoint coordinates do not.
    """
    clean: RunnableConfig = {
        "callbacks": config.get("callbacks"),
        "tags": list(config.get("tags", [])),
        "metadata": dict(config.get("metadata", {})),
        "recursion_limit": config["recursion_limit"],
        "configurable": {},
    }
    callbacks = clean.get("callbacks")
    if context.depth > 0 and isinstance(callbacks, BaseCallbackManager):
        # Managers also carry inherited metadata, independently of RunnableConfig.
        # Preserve handlers and trace ancestry while isolating that second path.
        callbacks = callbacks.copy()
        callbacks.metadata = dict(clean["metadata"])
        callbacks.inheritable_metadata = dict(clean["metadata"])
        clean["callbacks"] = callbacks
    if "max_concurrency" in config:
        clean["max_concurrency"] = config["max_concurrency"]
    inherited = config.get("configurable", {})
    runtime = inherited.get("__pregel_runtime")
    if "__pregel_stream" in inherited and isinstance(runtime, Runtime):
        clean["configurable"] = {
            "__pregel_stream": inherited["__pregel_stream"],
            "__pregel_runtime": Runtime(stream_writer=runtime.stream_writer),
        }
    if checkpoint_thread_id is not None:
        if context.depth != 0:
            raise ValueError("only the root may reconnect to a host checkpoint")
        clean["configurable"]["thread_id"] = checkpoint_thread_id
    with set_config_context(clean) as isolated_context:
        task = asyncio.create_task(
            graph.ainvoke(state, config=clean, context=context),
            context=isolated_context,
        )
        return await task


def build_lifecycle_graph(
    parent_agent: Any,
    runner: DelegationRunner,
    policy: DelegationPolicy,
    *,
    checkpoint_thread_id: str | None = None,
) -> Any:
    """Create fresh root scope beneath every public asynchronous entrypoint."""

    async def invoke_parent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
        scope = RunScope(policy=policy)
        runner.register_scope(scope)
        context = InvocationContext(
            scope=scope,
            runner=runner,
            agent_id=scope.root_agent_id,
            agent_name=scope.root_agent_name,
            parent_agent_id=None,
            depth=0,
            graph="chat",
        )
        parent_config: RunnableConfig = {
            **config,
            "metadata": {
                **config.get("metadata", {}),
                "data_agent_id": scope.root_agent_id,
                "data_agent_parent_id": None,
                "data_agent_name": scope.root_agent_name,
                "data_agent_depth": 0,
                "data_agent_graph": "chat",
            },
        }
        try:
            result = await invoke_scoped_graph(
                parent_agent,
                None
                if checkpoint_thread_id and config.get("configurable", {}).get("resume_pending")
                else state,
                config=parent_config,
                context=context,
                checkpoint_thread_id=checkpoint_thread_id,
            )
            return {"messages": result["messages"]}
        finally:
            try:
                await scope.close()
            finally:
                runner.unregister_scope(scope)

    graph = StateGraph(MessagesState)
    graph.add_node("parent", invoke_parent)
    graph.add_edge(START, "parent")
    graph.add_edge("parent", END)
    # The lifetime wrapper always reconstructs its scope. A host-supplied saver
    # checkpoints the inner root ReAct loop; children never inherit that saver.
    compiled = graph.compile(name="chat_lifecycle")
    return compiled.with_config(recursion_limit=runner.max_iterations * 3 + 2)


__all__ = ["build_lifecycle_graph", "invoke_scoped_graph"]
