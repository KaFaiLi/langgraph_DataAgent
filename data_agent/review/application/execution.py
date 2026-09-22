"""Durable execution accounting around the ordinary ReAct loop, without review routing."""

from __future__ import annotations

import fcntl
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from data_agent.agent.subagents.contracts import DelegationResult
from data_agent.review.verification.identity import content_digest
from data_agent.tools.review_runs import RunStore


class RunBudgetExceeded(RuntimeError):
    """The persisted aggregate allowance cannot authorize another dispatch."""


class RunBusyError(RuntimeError):
    """Another process owns this run's root invocation."""


class ReviewExecution:
    """One process lease; committed reservations survive exceptions and process death."""

    def __init__(self, store: RunStore, limits: dict[str, float]) -> None:
        self.store, self.limits = store, limits
        self.lease = None

    def __enter__(self):
        path = self.store.output_dir / "execution.lock"
        if path.is_symlink():
            raise ValueError("execution lease must not be a symlink")
        self.lease = path.open("a+")
        try:
            fcntl.flock(self.lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lease.close()
            self.lease = None
            raise RunBusyError("review already has an active root invocation") from exc
        try:
            self.store.update(self._begin)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args):
        if self.lease is not None:
            fcntl.flock(self.lease.fileno(), fcntl.LOCK_UN)
            self.lease.close()
            self.lease = None

    def _begin(self, record):
        if not record.budget_limits:
            record.budget_limits = dict(self.limits)
        # Never reset persisted limits/counters when settings or processes change.
        if record.invocation.get("status") == "running":
            self._charge_time(record)
            record.failures.append(self.failure("process_interrupted", retryable=True))
            for child in record.child_runs.values():
                if child.get("status") == "running":
                    child.update(status="interrupted", failure_reason="process_interrupted")
        record.invocation = {
            "id": str(uuid4()),
            "status": "running",
            "started_at": datetime.now(UTC).isoformat(),
        }
        record.status = "running"

    @staticmethod
    def failure(code: str, *, retryable: bool, operation: str | None = None) -> dict:
        return {
            "code": code,
            "retryable": retryable,
            "operation": operation,
            "at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _elapsed(record) -> float:
        start = record.invocation.get("started_at")
        return (
            max(0.0, (datetime.now(UTC) - datetime.fromisoformat(start)).total_seconds())
            if start
            else 0.0
        )

    def _charge_time(self, record):
        limit = record.budget_limits["active_seconds"]
        record.budget_used["active_seconds"] = min(
            limit, record.budget_used.get("active_seconds", 0) + self._elapsed(record)
        )

    def remaining_seconds(self) -> float:
        record = self.store.read()
        return max(
            0.0,
            record.budget_limits["active_seconds"]
            - record.budget_used.get("active_seconds", 0)
            - self._elapsed(record),
        )

    def reserve(self, kind: str, *, child_id: str | None = None) -> None:
        def update(record):
            if (
                record.budget_used.get("active_seconds", 0) + self._elapsed(record)
                >= record.budget_limits["active_seconds"]
            ):
                raise RunBudgetExceeded("aggregate active execution time exhausted")
            used, limit = record.budget_used.get(kind, 0), record.budget_limits[kind]
            if used >= limit:
                raise RunBudgetExceeded(f"aggregate {kind} limit {limit:g} exhausted")
            record.budget_used[kind] = used + 1
            if child_id:
                child = record.child_runs.setdefault(child_id, {"status": "running"})
                child[kind] = child.get(kind, 0) + 1

        self.store.update(update)

    def begin_child(
        self, key: str, request: Any, child_id: str
    ) -> tuple[str, DelegationResult | None]:
        signature = content_digest(request.model_dump(mode="json", exclude={"tool_call_id"}))

        def update(record):
            previous = record.delegations.get(key)
            if previous:
                if previous["request_digest"] != signature:
                    raise ValueError("replayed tool call changed its delegation request")
                if previous.get("result"):
                    return previous["child_id"], DelegationResult.model_validate(previous["result"])
                prior_id = previous["child_id"]
                child = record.child_runs.get(prior_id, {})
                ref = child.get("result_ref")
                if child.get("status") == "completed" and ref:
                    from data_agent.tools.review_verification import VerificationCapabilities

                    role = VerificationCapabilities.role_result(record, ref, request.agent_name)
                    receipt = {
                        "result_ref": ref,
                        "role": role["role"],
                        "candidate_ref": role.get("candidate_ref"),
                        "finding_id": role.get("finding_id"),
                        "finding_version": role.get("finding_version"),
                        "verified": False,
                    }
                    result = DelegationResult(
                        child_id=prior_id,
                        agent_name=request.agent_name,
                        status="completed",
                        output=json.dumps(receipt),
                        result_ref=ref,
                        structured_output=receipt,
                        model_calls=child.get("model_calls", 0),
                        tool_calls=child.get("tool_calls", 0),
                    )
                else:
                    # Child conversations are not checkpointed. Return explicit interruption
                    # under the original tool identity; the model may select a fresh attempt.
                    result = DelegationResult(
                        child_id=prior_id,
                        agent_name=request.agent_name,
                        status="failed",
                        output="",
                        error="process_interrupted: child has no accepted result",
                        model_calls=child.get("model_calls", 0),
                        tool_calls=child.get("tool_calls", 0),
                    )
                previous["result"] = result.model_dump(mode="json")
                return prior_id, result
            used = record.budget_used.get("child_runs", 0)
            if used >= record.budget_limits["child_runs"]:
                raise RunBudgetExceeded("aggregate child attempt budget exhausted")
            record.budget_used["child_runs"] = used + 1
            record.delegations[key] = {"child_id": child_id, "request_digest": signature}
            record.child_runs[child_id] = {"role": request.agent_name, "status": "running"}
            return child_id, None

        return self.store.update(update)

    def finish_child(self, key: str, result: DelegationResult) -> None:
        def update(record):
            record.delegations[key]["result"] = result.model_dump(mode="json")
            child = record.child_runs.setdefault(result.child_id, {})
            child.update(
                status=result.status,
                model_calls=result.model_calls,
                tool_calls=result.tool_calls,
                error=result.error,
            )
            if result.status != "completed":
                record.failures.append(
                    self.failure(
                        "child_" + result.status, retryable=True, operation=result.agent_name
                    )
                )

        self.store.update(update)

    def tool_failure(self, name: str) -> None:
        self.store.update(
            lambda r: r.failures.append(self.failure("tool_error", retryable=True, operation=name))
        )

    def finish(self, code: str | None = None, *, retryable: bool = True) -> None:
        def update(record):
            self._charge_time(record)
            record.invocation.update(status="finished", finished_at=datetime.now(UTC).isoformat())
            if code:
                record.failures.append(self.failure(code, retryable=retryable))
            if record.status != "completed":
                record.status = "interrupted" if retryable else "failed"

        self.store.update(update)


class PersistentBudgetMiddleware(AgentMiddleware):
    """Count every root/child dispatch, surface bounded tool errors, never decide review routes."""

    def __init__(self, execution: ReviewExecution, child_id: str | None = None) -> None:
        self.execution, self.child_id = execution, child_id

    async def awrap_model_call(self, request, handler):
        self.execution.reserve("model_calls", child_id=self.child_id)
        return await handler(request)

    async def awrap_tool_call(self, request, handler):
        self.execution.reserve("tool_calls", child_id=self.child_id)
        try:
            result = await handler(request)
        except RunBudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - tool errors must be recoverable by the root
            from data_agent.agent.subagents.runner import _sanitize_error

            self.execution.tool_failure(request.tool_call["name"])
            return ToolMessage(
                content=f"{type(exc).__name__}: {_sanitize_error(exc)}",
                tool_call_id=request.tool_call["id"],
                status="error",
            )
        if isinstance(result, ToolMessage) and result.status == "error":
            self.execution.tool_failure(request.tool_call["name"])
        return result
