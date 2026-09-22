"""Public contracts for the conversational sub-agent runner.

The package deliberately keeps its import surface small.  Bootstrap code imports
the concrete runner modules, while applications can import the trusted
``SubagentSpec`` contract without constructing a graph at import time.
"""

from data_agent.agent.subagents.contracts import (
    DelegationPolicy,
    DelegationRequest,
    DelegationResult,
    InvocationContext,
    RunScope,
    SubagentSpec,
)

__all__ = [
    "DelegationPolicy",
    "DelegationRequest",
    "DelegationResult",
    "InvocationContext",
    "RunScope",
    "SubagentSpec",
]
