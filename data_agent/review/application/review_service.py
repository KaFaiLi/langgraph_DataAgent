"""Review service: parent graph + SQLite checkpoints + resume (spec section 43)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

from data_agent.review.application.run_bundle import (
    RunBundleError,
    load_completed_run,
    load_resume_context,
    load_run_context,
    write_run_context,
)
from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.review import RunContext
from data_agent.review.domain.source import DateRange
from data_agent.review.orchestration.graph import build_parent_graph
from data_agent.review.orchestration.specialist_graph import (
    DEFAULT_LLM_PROVIDER,
    LLMProvider,
)


@dataclass
class ReviewService:
    """Runs the full review pipeline with checkpointing and resume."""

    llm_provider: LLMProvider = DEFAULT_LLM_PROVIDER
    checkpoint_db_name: str = "checkpoints.sqlite"
    callbacks: list[BaseCallbackHandler] = field(default_factory=list)

    def build_graph(self, checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
        return build_parent_graph(llm_provider=self.llm_provider, checkpointer=checkpointer)

    def run(
        self,
        *,
        source: str | Path,
        output_dir: str | Path,
        run_id: str,
        desk_template: DeskContext,
        review_period: DateRange,
        resume: bool = False,
    ) -> dict[str, Any]:
        """Compatibility wrapper for callers using the original service API."""
        if resume:
            return self.resume(
                output_dir,
                source=source,
                run_id=run_id,
                desk_template=desk_template,
                review_period=review_period,
            )
        return self.start(
            source=source,
            output_dir=output_dir,
            run_id=run_id,
            desk_template=desk_template,
            review_period=review_period,
        )

    def _config(self, context: RunContext) -> RunnableConfig:
        return {
            "configurable": {
                "thread_id": context.run_id,
                "desk_template": context.desk_template.model_dump(mode="json"),
                "review_period": context.review_period,
                "llm_provider": self.llm_provider,
            },
            "metadata": {"risk_agent_graph": "parent"},
            "callbacks": self.callbacks,
        }

    def start(
        self,
        *,
        source: str | Path,
        output_dir: str | Path,
        run_id: str,
        desk_template: DeskContext,
        review_period: DateRange,
    ) -> dict[str, Any]:
        """Persist fresh inputs then invoke the parent graph exactly once."""
        context = write_run_context(
            output_dir,
            run_id=run_id,
            source_root=source,
            desk_template=desk_template,
            review_period=review_period,
        )
        output = Path(context.output_dir)
        db_path = output / self.checkpoint_db_name
        config = self._config(context)
        with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            graph = self.build_graph(checkpointer=checkpointer)
            return graph.invoke(
                {
                    "run_id": context.run_id,
                    "source_root": context.source_root,
                    "output_dir": str(output),
                },
                config=config,
            )

    def resume(
        self,
        run_dir: str | Path,
        *,
        source: str | Path | None = None,
        run_id: str | None = None,
        desk_template: DeskContext | None = None,
        review_period: DateRange | None = None,
    ) -> dict[str, Any]:
        """Resume from persisted authoritative context, never rebuilt CLI inputs."""
        root = Path(run_dir).resolve()
        manifest_path = root / "run_manifest.json"
        if manifest_path.is_file():
            bundle = load_completed_run(root)
            try:
                context = load_run_context(root)
            except RunBundleError as exc:
                if exc.code != "run_context_missing":
                    raise
                # Legacy completed archives never had a persisted invocation
                # context. Their reviewed artifacts remain valid and usable.
                context = RunContext(
                    run_id=bundle.run.run_id,
                    source_root=bundle.run.source_root,
                    output_dir=str(bundle.run_dir),
                    desk_template=bundle.desk_context,
                    review_period=DateRange(
                        start=bundle.desk_context.review_start,
                        end=bundle.desk_context.review_end,
                    ),
                )
            self._assert_consistency(
                context,
                source=source,
                run_id=run_id,
                desk_template=desk_template,
                review_period=review_period,
            )
            return {
                "status": "completed",
                "run_id": bundle.run.run_id,
                "source_root": bundle.run.source_root,
                "output_dir": str(bundle.run_dir),
                "final_report": bundle.final_report.model_dump(mode="json"),
                "specialist_reports": {
                    domain.value: report.model_dump(mode="json")
                    for domain, report in bundle.specialist_reports.items()
                },
            }

        context = load_resume_context(root, checkpoint_db_name=self.checkpoint_db_name)
        self._assert_consistency(
            context,
            source=source,
            run_id=run_id,
            desk_template=desk_template,
            review_period=review_period,
        )
        db_path = root / self.checkpoint_db_name
        with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            graph = self.build_graph(checkpointer=checkpointer)
            return graph.invoke(None, config=self._config(context))

    @staticmethod
    def _assert_consistency(
        context: RunContext,
        *,
        source: str | Path | None,
        run_id: str | None,
        desk_template: DeskContext | None,
        review_period: DateRange | None,
    ) -> None:
        if run_id is not None and run_id != context.run_id:
            raise RunBundleError(
                "resume_run_id_mismatch", "provided run ID differs from run_context.json"
            )
        if source is not None and Path(source).resolve() != Path(context.source_root).resolve():
            raise RunBundleError(
                "resume_source_mismatch", "provided source differs from run_context.json"
            )
        if desk_template is not None and desk_template != context.desk_template:
            raise RunBundleError(
                "resume_desk_mismatch", "provided desk context differs from run_context.json"
            )
        if review_period is not None and review_period != context.review_period:
            raise RunBundleError(
                "resume_period_mismatch", "provided review period differs from run_context.json"
            )


