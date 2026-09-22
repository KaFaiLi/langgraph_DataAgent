"""Model-facing adapter for one-level conversational delegation."""

from __future__ import annotations

import json
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from data_agent.agent.subagents.contracts import (
    DelegationRequest,
    DelegationResult,
    InvocationContext,
)


class _DelegationInput(BaseModel):
    """Public model schema; runtime is injected and never model-controlled."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    agent_name: str = Field(description="Exact trusted child agent name.")
    task: str = Field(description="One concrete outcome for the child to complete.")
    context: str = Field(
        default="",
        description="Selected facts and source references relevant to the task.",
    )
    runtime: ToolRuntime = Field(exclude=True)


def _serialize(result: DelegationResult) -> str:
    return json.dumps(result.envelope(), ensure_ascii=False, separators=(",", ":"))


def _agent_name(value: object) -> str:
    """Keep malformed model input out of host-generated error details."""

    if isinstance(value, str):
        value = value.strip()
        if value:
            return value[:128]
    return "unknown"


def build_delegation_tool(runner: Any) -> BaseTool:
    """Create the local ``run_subagent`` tool bound to one reusable runner."""

    async def _run_subagent(
        agent_name: str,
        task: str,
        runtime: ToolRuntime,
        context: str = "",
    ) -> ToolMessage:
        tool_call_id = getattr(runtime, "tool_call_id", None) or "unknown"
        safe_agent_name = _agent_name(agent_name)
        try:
            request = DelegationRequest(
                agent_name=agent_name,
                task=task,
                context=context,
                tool_call_id=tool_call_id,
            )
        except Exception:  # noqa: BLE001 - malformed model input is a bounded result
            result = DelegationResult(
                output="",
                status="rejected",
                child_id="unbound",
                agent_name=safe_agent_name,
                error="invalid delegation request",
            )
        else:
            if runtime is None or not isinstance(runtime.context, InvocationContext):
                result = DelegationResult(
                    output="",
                    status="rejected",
                    child_id="unbound",
                    agent_name=safe_agent_name,
                    error="run_subagent requires an active root invocation",
                )
            else:
                try:
                    result = await runner.run(
                        request,
                        scope=runtime.context.scope,
                        config=runtime.config,
                        tool_call_id=tool_call_id,
                        parent_depth=runtime.context.depth,
                    )
                except Exception:  # noqa: BLE001 - adapter normalizes host failures
                    result = DelegationResult(
                        output="",
                        status="failed",
                        child_id="unbound",
                        agent_name=safe_agent_name,
                        error="child execution failed",
                    )
        return ToolMessage(
            content=_serialize(result),
            name="run_subagent",
            tool_call_id=tool_call_id,
            status="success" if result.status == "completed" else "error",
        )

    return StructuredTool.from_function(
        coroutine=_run_subagent,
        name="run_subagent",
        description=(
            "Delegate one focused, read-only task to a trusted child agent and wait "
            "for its bounded result. Use independent calls for independent work."
        ),
        args_schema=_DelegationInput,
        handle_tool_error=True,
    )


__all__ = ["build_delegation_tool"]
