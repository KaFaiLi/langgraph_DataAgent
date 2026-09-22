"""Persistent run capabilities and source access bound by the application host."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar

from langchain_core.tools import BaseTool, StructuredTool, ToolException

from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.run_record import AssignmentRecord, ReviewRecord, SourceDisposition
from data_agent.review.domain.source import DateRange, SourceManifest
from data_agent.review.domain.verification import CandidateDispositionRecord
from data_agent.review.ingestion.catalog import build_catalog
from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.verification.identity import finding_version
from data_agent.skills.review import SkillDefinition
from data_agent.tools.research import build_research_tools
from data_agent.tools.review_context import ToolContext
from data_agent.tools.review_operations import OmissionRequest, audit_candidates
from data_agent.tools.review_skills import CandidateSubmission, SkillExecution
from data_agent.tools.source_tools import discover_sources, file_digest, resolve_source_path

T = TypeVar("T")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class RunStore:
    """Transactional state for one host-authorized run, with immutable input binding."""

    def __init__(self, source_root: Path, output_dir: Path, run_id: str) -> None:
        self.source_root = source_root.resolve()
        self.output_dir = output_dir.resolve()
        self.run_id = run_id
        if self.source_root.is_relative_to(self.output_dir) or self.output_dir.is_relative_to(
            self.source_root
        ):
            raise ValueError("review source and output directories must be separate")
        self.path = self.output_dir / "review_record.sqlite"

    def _connection(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise ValueError("review record must not be a symlink")
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _validate(self, record: ReviewRecord) -> ReviewRecord:
        if (
            record.run_id != self.run_id
            or record.source_root != str(self.source_root)
            or record.output_dir != str(self.output_dir)
        ):
            raise ValueError("run record is outside the host-authorized scope")
        if _digest(record.manifest.model_dump(mode="json")) != record.manifest_digest:
            raise ValueError("immutable source manifest integrity check failed")
        return record

    def initialize(
        self, desk: DeskContext, definitions: dict[str, SkillDefinition]
    ) -> ReviewRecord:
        if self.path.exists():
            record = self.read()
            if record.desk_context != desk:
                raise ValueError("run already exists with different immutable context")
            return record
        manifest = build_catalog(self.source_root)
        owners = {
            domain: name
            for name, definition in definitions.items()
            for domain in definition.source_domains
        }
        classifications = {}
        for source in manifest.sources:
            names = sorted({owners[d] for d in source.candidate_domains if d in owners})
            if len(names) == 1:
                classifications[source.source_id] = names
        record = ReviewRecord(
            run_id=self.run_id,
            source_root=str(self.source_root),
            output_dir=str(self.output_dir),
            created_at=datetime.now(UTC),
            review_period=DateRange(start=desk.review_start, end=desk.review_end),
            desk_context=desk,
            manifest=manifest,
            manifest_digest=_digest(manifest.model_dump(mode="json")),
            classifications=classifications,
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS run_record (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO run_record VALUES (1, ?)", (record.model_dump_json(),)
            )
        existing = self.read()
        if existing.desk_context != desk:
            raise ValueError("concurrent initialization selected different immutable context")
        return existing

    def read(self) -> ReviewRecord:
        if not self.path.is_file():
            raise ValueError("review run is not initialized")
        with self._connection() as connection:
            row = connection.execute("SELECT payload FROM run_record WHERE id=1").fetchone()
        if row is None:
            raise ValueError("review run record is missing")
        return self._validate(ReviewRecord.model_validate_json(row[0]))

    def update(self, operation: Callable[[ReviewRecord], T]) -> T:
        if not self.path.is_file():
            raise ValueError("review run is not initialized")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload FROM run_record WHERE id=1").fetchone()
            if row is None:
                raise ValueError("review run record is missing")
            record = self._validate(ReviewRecord.model_validate_json(row[0]))
            immutable = (
                record.run_id,
                record.source_root,
                record.output_dir,
                record.manifest_digest,
                record.desk_context.model_dump_json(),
                record.review_period.model_dump_json(),
            )
            result = operation(record)
            self._validate(record)
            if immutable != (
                record.run_id,
                record.source_root,
                record.output_dir,
                record.manifest_digest,
                record.desk_context.model_dump_json(),
                record.review_period.model_dump_json(),
            ):
                raise ValueError("operation changed immutable run context")
            connection.execute(
                "UPDATE run_record SET payload=? WHERE id=1", (record.model_dump_json(),)
            )
            return result

    def check_sources(self, record: ReviewRecord, source_ids: list[str] | None = None) -> None:
        sources = (
            record.manifest.sources
            if source_ids is None
            else [record.manifest.by_id(s) for s in source_ids]
        )
        for source in sources:
            path = resolve_source_path(self.source_root, source.path)
            if file_digest(path)[0] != source.sha256:
                raise ValueError(f"source changed since run initialization: {source.path}")
        if source_ids is None:
            current, truncated = discover_sources(self.source_root, max_sources=None)
            if truncated or {s.path for s in current} != {s.path for s in sources}:
                raise ValueError("source inventory changed since run initialization")


class RunCapabilities:
    """Operations whose authority comes from a host-created store and optional assignment."""

    def __init__(
        self,
        store: RunStore,
        definitions: dict[str, SkillDefinition],
        assignment_id: str | None = None,
        *,
        trace_context: dict | None = None,
    ) -> None:
        self.trace_context = dict(trace_context or {})
        self.store, self.definitions, self.bound_assignment = (
            store,
            dict(definitions),
            assignment_id,
        )

    def _root(self) -> None:
        if self.bound_assignment is not None:
            raise ValueError("operation requires the root review role")

    def _assignment(self, record: ReviewRecord, assignment_id: str) -> AssignmentRecord:
        if self.bound_assignment is not None and assignment_id != self.bound_assignment:
            raise ValueError("assignment is outside the host-authorized scope")
        try:
            return record.assignments[assignment_id]
        except KeyError as exc:
            raise ValueError("unknown review assignment") from exc

    def _execution(self, assignment: AssignmentRecord) -> SkillExecution:
        return SkillExecution(
            self.store.source_root,
            self.store.output_dir / "workspace" / assignment.assignment_id,
            {assignment.skill_name: self.definitions[assignment.skill_name]},
        )

    def inventory(self, offset: int = 0, limit: int = 50) -> dict:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("invalid inventory page; limit must be 1..100")
        record = self.store.read()
        sources = record.manifest.sources
        if self.bound_assignment is not None:
            assignment = self._assignment(record, self.bound_assignment)
            sources = [s for s in sources if s.source_id in assignment.source_ids]
        values = []
        for source in sources:
            required = record.classifications.get(source.source_id, [])
            assigned = [
                a
                for a in record.assignments.values()
                if source.source_id in a.source_ids
                and (self.bound_assignment is None or a.assignment_id == self.bound_assignment)
            ]
            if self.bound_assignment:
                required = [self._assignment(record, self.bound_assignment).skill_name]
            dispositions = {
                a.assignment_id: a.dispositions[source.source_id].model_dump(mode="json")
                for a in assigned
                if source.source_id in a.dispositions
            }
            global_disposition = record.source_dispositions.get(source.source_id)
            settled = bool(global_disposition) or (
                bool(required)
                and all(
                    any(
                        a.skill_name == name and source.source_id in a.dispositions
                        for a in assigned
                    )
                    for name in required
                )
            )
            values.append(
                {
                    **source.model_dump(mode="json"),
                    "required_reviewers": required,
                    "classification_required": source.source_id not in record.classifications
                    and not global_disposition,
                    "disposition_required": not settled,
                    "dispositions": dispositions,
                    "source_disposition": global_disposition.model_dump(mode="json")
                    if global_disposition
                    else None,
                }
            )
        end = min(len(values), offset + limit)
        return {
            "run_id": record.run_id,
            "sources": values[offset:end],
            "total_sources": len(values),
            "truncated": offset > 0 or end < len(values),
            "next_offset": end if end < len(values) else None,
            "manifest_digest": record.manifest_digest,
        }

    def classify(self, source_id: str, skill_names: list[str], rationale: str) -> dict:
        self._root()
        if (
            not skill_names
            or len(skill_names) != len(set(skill_names))
            or set(skill_names) - set(self.definitions)
        ):
            raise ValueError("classification requires unique registered specialist names")
        if not rationale.strip() or len(rationale) > 2000:
            raise ValueError("classification requires a bounded rationale")

        def update(record):
            record.manifest.by_id(source_id)
            if any(source_id in a.source_ids for a in record.assignments.values()) and set(
                record.classifications.get(source_id, [])
            ) != set(skill_names):
                raise ValueError("classification cannot change after assignment")
            record.classifications[source_id] = sorted(skill_names)
            record.classification_reasons[source_id] = rationale

        self.store.update(update)
        return {"source_id": source_id, "required_reviewers": sorted(skill_names)}

    def assign(self, skill_name: str, source_ids: list[str], rationale: str) -> dict:
        self._root()
        if skill_name not in self.definitions:
            raise ValueError("unknown specialist skill")
        if (
            not source_ids
            or len(source_ids) > 256
            or len(source_ids) != len(set(source_ids))
            or not rationale.strip()
        ):
            raise ValueError("assignment requires unique source IDs and a rationale")
        identifier = "task-" + _digest([skill_name, sorted(source_ids)])[:20]

        def update(record):
            for source_id in source_ids:
                record.manifest.by_id(source_id)
                if skill_name not in record.classifications.get(source_id, []):
                    raise ValueError(f"classify {source_id} for {skill_name} before assigning it")
            if identifier not in record.assignments:
                if len(record.assignments) >= 32:
                    raise ValueError("assignment budget exhausted")
                record.assignments[identifier] = AssignmentRecord(
                    assignment_id=identifier,
                    skill_name=skill_name,
                    source_ids=sorted(source_ids),
                    rationale=rationale[:2000],
                )
            return record.assignments[identifier].model_dump(mode="json")

        return self.store.update(update)

    def execute(self, assignment_id: str) -> dict:
        record = self.store.read()
        assignment = self._assignment(record, assignment_id)
        self.store.check_sources(record, assignment.source_ids)
        execution = self._execution(assignment)
        summary = execution.execute(
            assignment.skill_name, [record.manifest.by_id(s).path for s in assignment.source_ids]
        )
        self.store.check_sources(record, assignment.source_ids)

        def update(current):
            target = self._assignment(current, assignment_id)
            if target.analysis_ref is not None and target.analysis_ref != summary["result_ref"]:
                raise ValueError("deterministic result changed within immutable assignment")
            target.analysis_ref = summary["result_ref"]
            target.artifacts["analysis"] = str(
                execution.workspace_root / (target.analysis_ref + ".json")
            )

        self.store.update(update)
        return summary | {"assignment_id": assignment_id}

    def result(
        self, assignment_id: str, section: str, offset: int = 0, max_chars: int = 12000
    ) -> dict:
        record = self.store.read()
        assignment = self._assignment(record, assignment_id)
        if assignment.analysis_ref is None:
            raise ValueError("assignment has no stored analysis")
        self.store.check_sources(record, assignment.source_ids)
        return self._execution(assignment).read(assignment.analysis_ref, section, offset, max_chars)

    def submit(self, assignment_id: str, candidate: CandidateSubmission) -> dict:
        record = self.store.read()
        assignment = self._assignment(record, assignment_id)
        if assignment.analysis_ref is None:
            raise ValueError("run trusted analysis before submitting a draft")
        self.store.check_sources(record, assignment.source_ids)
        execution = self._execution(assignment)
        result = execution.submit(assignment.analysis_ref, candidate)
        stored = execution.load_candidate(result["candidate_ref"], assignment.analysis_ref)

        def update(current):
            target = self._assignment(current, assignment_id)
            incoming = {f.finding_id: f.model_dump(mode="json") for f in stored.findings}
            for finding_id, value in incoming.items():
                target.initial_findings.setdefault(finding_id, value)
                previous = target.findings.get(finding_id)
                if previous and finding_version(previous) == finding_version(value):
                    continue  # Idempotent replay retains authoritative verification.
                if len(target.verification.get(finding_id, [])) >= current.max_verifier_rounds:
                    raise ValueError("verification revision budget exhausted for " + finding_id)
                target.findings[finding_id] = value
            if len(target.findings) > 16:
                raise ValueError("assignment finding budget exhausted (16 including rescue)")
            target.candidate_ref = result["candidate_ref"]
            target.unresolved_items = list(
                dict.fromkeys([*target.unresolved_items, *stored.unresolved_items])
            )
            target.report = None
            target.candidate_dispositions.update(
                {d.candidate_id: d for d in stored.candidate_dispositions}
            )
            target.artifacts["candidate"] = str(
                execution.workspace_root / (target.candidate_ref + ".json")
            )

        self.store.update(update)
        return result

    def source_tool(self, assignment_id: str, tool_name: str, arguments: dict) -> dict:
        record = self.store.read()
        assignment = self._assignment(record, assignment_id)
        self.store.check_sources(record, assignment.source_ids)
        sources = [record.manifest.by_id(s) for s in assignment.source_ids]
        context = ToolContext(
            self.store.source_root,
            self.store.output_dir / "workspace",
            SourceManifest(sources=sources),
        )
        trace: list[dict] = []
        tools = {
            t.name: t
            for t in build_research_tools(context, [s.path for s in sources], trace, max_calls=1)
        }
        if tool_name not in tools:
            raise ValueError("unknown or prohibited review source tool")

        def reserve(current):
            if current.tool_calls >= current.max_tool_calls:
                raise ValueError("aggregate review tool budget exhausted")
            current.tool_calls += 1

        self.store.update(reserve)
        try:
            unknown = set(arguments) - set(tools[tool_name].args)
            if unknown:
                raise ValueError("unsupported source tool arguments: " + ", ".join(sorted(unknown)))
            value = tools[tool_name].invoke(arguments)
            self.store.check_sources(record, assignment.source_ids)
        except Exception as exc:
            failure = {
                "code": "source_tool_error",
                "assignment_id": assignment_id,
                "tool": tool_name,
                "message": str(exc)[:2000],
            }
            self.store.update(lambda r: r.failures.append(failure))
            raise
        finally:
            self.store.update(
                lambda r: r.trace.extend(
                    {**entry, "assignment_id": assignment_id, **self.trace_context}
                    for entry in trace
                )
            )
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            decoded = None
        truncated = bool(trace and trace[-1]["truncated"])
        if isinstance(decoded, dict):
            truncated = truncated or bool(decoded.get("truncated"))
        return {"result": value, "truncated": truncated, "coverage_complete": False}

    def dispose_source(
        self, source_id: str, disposition: SourceDisposition, assignment_id: str | None = None
    ) -> dict:
        if assignment_id is None:
            self._root()
            if disposition.status == "reviewed":
                raise ValueError("reviewed disposition requires an analyzed specialist assignment")
        record = self.store.read()
        source = record.manifest.by_id(source_id)
        assignment = self._assignment(record, assignment_id) if assignment_id else None
        if assignment and source_id not in assignment.source_ids:
            raise ValueError("source is outside the assignment")
        if disposition.status == "reviewed" and (
            assignment is None or not assignment.analysis_ref or not assignment.candidate_ref
        ):
            raise ValueError(
                "reviewed disposition requires stored analysis and candidate submission"
            )
        validator = EvidenceValidator.source_backed(
            self.store.source_root, SourceManifest(sources=[source])
        )
        if not validator.validate_references(disposition.evidence).valid:
            raise ValueError("invalid source disposition evidence")

        def update(current):
            target = (
                self._assignment(current, assignment_id).dispositions
                if assignment_id
                else current.source_dispositions
            )
            target[source_id] = disposition
            if assignment_id:
                self._assignment(current, assignment_id).report = None

        self.store.update(update)
        return {"source_id": source_id, "status": disposition.status}

    def dispose_candidate(
        self, assignment_id: str, disposition: CandidateDispositionRecord
    ) -> dict:
        record = self.store.read()
        assignment = self._assignment(record, assignment_id)
        if not assignment.analysis_ref:
            raise ValueError("analysis required before candidate disposition")
        result = self._execution(assignment).load(assignment.analysis_ref)
        ids = {str(c["candidate_id"]) for a in result.analyses for c in a.flag_candidates}
        if disposition.candidate_id not in ids:
            raise ValueError("unknown candidate ID")
        validator = EvidenceValidator.source_backed(self.store.source_root, result.manifest)
        if (
            not disposition.reason.strip()
            or not disposition.evidence
            or not validator.validate_references(disposition.evidence).valid
        ):
            raise ValueError(
                "candidate disposition requires a reason and assigned source-backed evidence"
            )

        def update(current):
            target = self._assignment(current, assignment_id)
            target.candidate_dispositions[disposition.candidate_id] = disposition
            target.report = None

        self.store.update(update)
        current = self.store.read()
        audit = audit_candidates(
            OmissionRequest(
                ToolContext(
                    self.store.source_root, self.store.output_dir / "workspace", result.manifest
                ),
                tuple(result.source_paths),
                result.analyses,
                verified=[
                    Finding.model_validate(f)
                    for f in current.assignments[assignment_id].findings.values()
                ],
                dispositions=list(
                    current.assignments[assignment_id].candidate_dispositions.values()
                ),
            )
        )
        covered = disposition.candidate_id in audit.covered_candidate_ids
        return {
            "candidate_id": disposition.candidate_id,
            "recorded": True,
            "covered": covered,
            "next_action": None
            if covered
            else "Link the candidate ID to an actual stored finding, or record a source-backed non-finding disposition.",
        }

    def coverage(self) -> dict:
        self._root()
        record = self.store.read()
        self.store.check_sources(record)
        blockers = []
        disclosures = []
        for source in record.manifest.sources:
            source_id = source.source_id
            global_disposition = record.source_dispositions.get(source_id)
            if global_disposition:
                disclosures.append(
                    f"{source_id}: {global_disposition.status}: {global_disposition.reason}"
                )
                continue
            if source.parse_error:
                blockers.append(
                    f"{source_id}: parse failure requires explicit unsupported disposition"
                )
            if source_id not in record.classifications:
                blockers.append(
                    f"{source_id}: ambiguous/unclassified source requires classification or explicit disposition"
                )
            for name in record.classifications.get(source_id, []):
                matches = [
                    a
                    for a in record.assignments.values()
                    if a.skill_name == name and source_id in a.source_ids
                ]
                if not matches:
                    blockers.append(f"{source_id}: missing {name} assignment")
                elif any(source_id not in a.dispositions for a in matches):
                    blockers.append(f"{source_id}: missing {name} source disposition")
                for assignment in matches:
                    disposition = assignment.dispositions.get(source_id)
                    if disposition and disposition.status != "reviewed":
                        disclosures.append(
                            f"{source_id}/{name}: {disposition.status}: {disposition.reason}"
                        )
        candidates = {}
        for identifier, assignment in record.assignments.items():
            if not assignment.analysis_ref:
                blockers.append(f"{identifier}: mandatory deterministic analysis missing")
                continue
            result = self._execution(assignment).load(assignment.analysis_ref)
            audit = audit_candidates(
                OmissionRequest(
                    ToolContext(
                        self.store.source_root, self.store.output_dir / "workspace", result.manifest
                    ),
                    tuple(result.source_paths),
                    result.analyses,
                    verified=[Finding.model_validate(f) for f in assignment.findings.values()],
                    dispositions=list(assignment.candidate_dispositions.values()),
                )
            )
            candidates[identifier] = {
                "total": len(audit.covered_candidate_ids) + len(audit.uncovered_candidate_ids),
                "uncovered": audit.uncovered_candidate_ids[:10],
                "uncovered_count": len(audit.uncovered_candidate_ids),
                "material_uncovered": audit.material_candidate_ids[:10],
                "material_uncovered_count": len(audit.material_candidate_ids),
                "truncated": len(audit.uncovered_candidate_ids) > 10,
            }
            if not assignment.candidate_ref:
                blockers.append(f"{identifier}: typed candidate submission missing")
        return {
            "run_id": record.run_id,
            "source_count": len(record.manifest.sources),
            "blockers": blockers[:100],
            "total_blockers": len(blockers),
            "truncated": len(blockers) > 100,
            "source_coverage_complete": not blockers,
            "candidates": candidates,
            "candidate_coverage_complete": all(
                not c["uncovered_count"] for c in candidates.values()
            ),
            "disclosures": [item[:500] for item in disclosures[:20]],
            "disclosures_truncated": len(disclosures) > 20
            or any(len(item) > 500 for item in disclosures[:20]),
            "tool_calls": record.tool_calls,
            "max_tool_calls": record.max_tool_calls,
            "budget_used": record.budget_used,
            "budget_limits": record.budget_limits,
            "run_status": record.status,
            "last_failure": record.failures[-1] if record.failures else None,
            "publication_ready": record.status == "completed",
        }


class ReviewWorkspace:
    """Select runs within one host-authorized workspace, never by arbitrary filesystem path."""

    def __init__(
        self,
        source_root: Path,
        workspace_root: Path,
        definitions: dict[str, SkillDefinition],
        run_id: str | None = None,
        assignment_id: str | None = None,
        *,
        trace_context: dict | None = None,
        output_dir: Path | None = None,
    ) -> None:
        if output_dir is not None and (not run_id or output_dir.is_symlink()):
            raise ValueError("explicit output directory requires a host-bound run and no symlink")
        self.output_dir = output_dir.resolve() if output_dir is not None else None
        self.trace_context = dict(trace_context or {})
        self.source_root, self.workspace_root = source_root.resolve(), workspace_root.resolve()
        self.definitions, self.bound_run, self.bound_assignment = definitions, run_id, assignment_id
        if assignment_id and not run_id:
            raise ValueError("assignment binding requires a host-bound run")

    def access(self, run_id: str) -> RunCapabilities:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
            raise ValueError("invalid review run ID")
        if self.bound_run is not None and self.bound_run != run_id:
            raise ValueError("run is outside the host-authorized scope")
        output = self.output_dir or self.workspace_root / "runs" / run_id
        if output.is_symlink() or (
            self.output_dir is None and not output.resolve().is_relative_to(self.workspace_root)
        ):
            raise ValueError("run directory escapes the authorized workspace")
        return RunCapabilities(
            RunStore(self.source_root, output, run_id),
            self.definitions,
            self.bound_assignment,
            trace_context=self.trace_context,
        )


def build_review_run_tools(workspace: ReviewWorkspace) -> list[BaseTool]:
    """Same bounded operations are used by local agents and MCP adapters."""

    def initialize_review_run(run_id: str, desk_context: DeskContext) -> dict:
        """Initialize immutable sources and desk/period context under host-configured roots."""
        access = workspace.access(run_id)
        access._root()
        record = access.store.initialize(desk_context, workspace.definitions)
        return {
            "run_id": record.run_id,
            "source_count": len(record.manifest.sources),
            "status": record.status,
        }

    def review_inventory(run_id: str, offset: int = 0, limit: int = 50) -> dict:
        """Inspect every discovered source in pages, including parse errors and required dispositions."""
        return workspace.access(run_id).inventory(offset, limit)

    def read_review_assignment(
        run_id: str, assignment_id: str, offset: int = 0, max_chars: int = 12000
    ) -> dict:
        """Read stored findings with their stable IDs, verification and outstanding assignment state in pages."""
        from data_agent.skills.references import text_page

        access = workspace.access(run_id)
        assignment = access._assignment(access.store.read(), assignment_id)
        return text_page(assignment.model_dump_json(), offset=offset, max_chars=max_chars)

    def classify_review_source(
        run_id: str, source_id: str, skill_names: list[str], rationale: str
    ) -> dict:
        """Resolve ambiguous/unclassified sources into registered reviewer obligations with a rationale."""
        return workspace.access(run_id).classify(source_id, skill_names, rationale)

    def assign_review_work(
        run_id: str, skill_name: str, source_ids: list[str], rationale: str
    ) -> dict:
        """Create a stable specialist assignment after explicit source classification."""
        return workspace.access(run_id).assign(skill_name, source_ids, rationale)

    def execute_assigned_analysis(run_id: str, assignment_id: str) -> dict:
        """Run the assignment's registered deterministic skill and persist its result reference."""
        return workspace.access(run_id).execute(assignment_id)

    def read_assigned_analysis(
        run_id: str,
        assignment_id: str,
        section: Literal["candidates", "overviews", "all"] = "candidates",
        offset: int = 0,
        max_chars: int = 12000,
    ) -> dict:
        """Read paginated authoritative analysis details for an authorized assignment."""
        return workspace.access(run_id).result(assignment_id, section, offset, max_chars)

    def submit_assigned_candidate(
        run_id: str, assignment_id: str, candidate: CandidateSubmission
    ) -> dict:
        """Persist an assignment's typed pending draft; never establish independent verification."""
        return workspace.access(run_id).submit(assignment_id, candidate)

    def review_source_tool(
        run_id: str, assignment_id: str, tool_name: str, arguments: dict
    ) -> dict:
        """Use scoped list_assigned_sources, inspect_table, read_rows, describe_columns, group_by,
        join_tables, run_duckdb_query, search_text, read_lines, reopen_evidence, zscore,
        outlier_detection, change_point_candidates or pearson_correlation.
        read_rows arguments: path, start, end (1-based data rows), optional sheet.
        reopen_evidence arguments: locator. inspect_table: path, optional preview_rows/sheet.
        search_text: pattern, optional max_results/case_insensitive. run_duckdb_query: sql, max_rows.
        join_tables: left, right, on (column list), how. Every read is hash-checked and scoped.
        """
        return workspace.access(run_id).source_tool(assignment_id, tool_name, arguments)

    def record_source_disposition(
        run_id: str,
        source_id: str,
        disposition: SourceDisposition,
        assignment_id: str | None = None,
    ) -> dict:
        """Record reviewed, irrelevant or unsupported source handling with an explicit reason."""
        return workspace.access(run_id).dispose_source(source_id, disposition, assignment_id)

    def record_candidate_disposition(
        run_id: str, assignment_id: str, disposition: CandidateDispositionRecord
    ) -> dict:
        """Account for a deterministic candidate with a reason and assigned, reopenable evidence."""
        return workspace.access(run_id).dispose_candidate(assignment_id, disposition)

    def validate_review_evidence(
        run_id: str, assignment_id: str, finding_id: str, offset: int = 0, max_chars: int = 12000
    ) -> dict:
        """Reopen current finding evidence and inspect its version-bound gate in bounded pages."""
        from data_agent.skills.references import text_page
        from data_agent.tools.review_verification import VerificationCapabilities

        result = VerificationCapabilities(workspace.access(run_id)).evidence(
            assignment_id, finding_id
        )
        return text_page(json.dumps(result["gate"]), offset=offset, max_chars=max_chars) | {
            "finding_id": finding_id,
            "finding_version": result["finding_version"],
            "decision": result["gate"]["decision"],
        }

    def apply_review_verification(run_id: str, assignment_id: str, adjudicator_ref: str) -> dict:
        """Apply evidence/challenge/severity rules to a stored independent adjudicator result; no self-verification."""
        from data_agent.tools.review_verification import VerificationCapabilities

        return VerificationCapabilities(workspace.access(run_id)).apply(
            assignment_id, adjudicator_ref
        )

    def audit_review_omissions(
        run_id: str,
        assignment_id: str,
        action: Literal["inspect", "rescue", "disclose"] = "inspect",
        reason: str = "",
        offset: int = 0,
        max_chars: int = 12000,
    ) -> dict:
        """Inspect paginated coverage, reserve one rescue, or disclose omissions. Use inspect for subsequent pages."""
        from data_agent.skills.references import text_page
        from data_agent.tools.review_verification import VerificationCapabilities

        if action != "inspect" and offset:
            raise ValueError("use inspect to page an already recorded omission action")
        result = VerificationCapabilities(workspace.access(run_id)).omissions(
            assignment_id, action, reason
        )
        audit = result.pop("audit")
        return (
            text_page(json.dumps(audit), offset=offset, max_chars=max_chars)
            | result
            | {
                "uncovered_count": len(audit["uncovered_candidates"]),
                "material_uncovered_count": len(audit["material_candidate_ids"]),
                "rescue_required": audit["rescue_required"],
                "disclosures_recorded": bool(audit["unresolved_disclosures"]),
            }
        )

    def finalize_specialist_report(run_id: str, assignment_id: str) -> dict:
        """Construct the stored typed specialist report after source coverage and independent verification."""
        from data_agent.tools.review_verification import VerificationCapabilities

        return VerificationCapabilities(workspace.access(run_id)).finalize(assignment_id)

    def read_specialist_report(
        run_id: str, assignment_id: str, offset: int = 0, max_chars: int = 12000
    ) -> dict:
        """Read a validated stored specialist report in bounded pages; no raw-source access."""
        from data_agent.skills.references import text_page

        access = workspace.access(run_id)
        assignment = access._assignment(access.store.read(), assignment_id)
        if not assignment.report:
            raise ValueError("validated specialist report required")
        return text_page(json.dumps(assignment.report), offset=offset, max_chars=max_chars)

    def read_lead_review(run_id: str, offset: int = 0, max_chars: int = 12000) -> dict:
        """Inspect deterministic cross-report analysis, lead draft, feedback and history in pages."""
        from data_agent.skills.references import text_page
        from data_agent.tools.review_publication import PublicationCapabilities

        value = PublicationCapabilities(workspace.access(run_id)).inspect()
        return text_page(json.dumps(value), offset=offset, max_chars=max_chars)

    def prepare_lead_review(run_id: str, lead_ref: str) -> dict:
        """Build and validate a stored lead draft, returning actionable evidence/derivation/severity blockers."""
        from data_agent.tools.review_publication import PublicationCapabilities

        return PublicationCapabilities(workspace.access(run_id)).prepare(lead_ref)

    def apply_lead_verification(run_id: str, verifier_ref: str) -> dict:
        """Apply an independent stored lead verdict with bounded revision and material-objection rules."""
        from data_agent.tools.review_publication import PublicationCapabilities

        return PublicationCapabilities(workspace.access(run_id)).apply(verifier_ref)

    def publish_review(run_id: str) -> dict:
        """Validate source/candidate coverage, independent verification and the complete bundle; atomically publish or return blockers."""
        from data_agent.tools.review_publication import PublicationCapabilities

        return PublicationCapabilities(workspace.access(run_id)).publish()

    def review_coverage(run_id: str) -> dict:
        """Read authoritative missing source, assignment and candidate obligations; summaries cannot override it."""
        return workspace.access(run_id).coverage()

    functions = [
        initialize_review_run,
        review_inventory,
        read_review_assignment,
        classify_review_source,
        assign_review_work,
        execute_assigned_analysis,
        read_assigned_analysis,
        submit_assigned_candidate,
        review_source_tool,
        record_source_disposition,
        record_candidate_disposition,
        review_coverage,
        validate_review_evidence,
        apply_review_verification,
        audit_review_omissions,
        finalize_specialist_report,
        read_specialist_report,
        read_lead_review,
        prepare_lead_review,
        apply_lead_verification,
        publish_review,
    ]
    if workspace.bound_assignment:
        functions = [
            review_inventory,
            execute_assigned_analysis,
            read_assigned_analysis,
            submit_assigned_candidate,
            review_source_tool,
            record_source_disposition,
            record_candidate_disposition,
        ]

    def guarded(function):
        from functools import wraps

        @wraps(function)
        def call(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except (OSError, ValueError, KeyError, RuntimeError, sqlite3.Error) as exc:
                raise ToolException(str(exc)) from exc

        return call

    return [StructuredTool.from_function(guarded(f), handle_tool_error=True) for f in functions]
