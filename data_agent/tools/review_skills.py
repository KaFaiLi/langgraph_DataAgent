"""Trusted skill execution and typed candidate storage for the general agent.

The host binds roots and registered definitions. Model arguments select identities
and contained sources, never modules, filesystem roots or executable paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from threading import RLock
from typing import Literal

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from pydantic import BaseModel, ConfigDict, Field

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.source import SourceManifest
from data_agent.review.domain.verification import CandidateDispositionRecord
from data_agent.review.ingestion.catalog import build_catalog
from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.verification.finding_policy import normalize_findings
from data_agent.skills.loader import Skill
from data_agent.skills.references import text_page
from data_agent.skills.review import SkillDefinition, load_analysis_runner, load_skill
from data_agent.tools.review_context import ToolContext
from data_agent.tools.review_operations import AnalysisRequest, prepare_analysis
from data_agent.tools.source_tools import file_digest


class CandidateSubmission(BaseModel):
    """An analyst draft; verification is established separately by trusted records."""

    model_config = ConfigDict(extra="forbid")
    findings: list[Finding] = Field(default_factory=list, max_length=8)
    candidate_dispositions: list[CandidateDispositionRecord] = Field(
        default_factory=list, max_length=64
    )
    unresolved_items: list[str] = Field(default_factory=list, max_length=32)


class StoredAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    skill: str
    source_root: str
    manifest: SourceManifest
    source_paths: list[str]
    analyses: list[AnalysisResult]


class SkillExecution:
    """Shared in-process capability, scoped by application-owned dependencies."""

    def __init__(
        self, source_root: Path, workspace_root: Path, definitions: dict[str, SkillDefinition]
    ) -> None:
        self.source_root = source_root.resolve()
        self.workspace_root = workspace_root.resolve()
        if self.workspace_root == self.source_root or self.source_root.is_relative_to(
            self.workspace_root
        ):
            raise ValueError("analysis workspace must not contain the source root")
        self.definitions = dict(definitions)
        self._lock = RLock()

    def _definition(self, name: str) -> SkillDefinition:
        try:
            return self.definitions[name]
        except KeyError as exc:
            raise ValueError(f"Unknown executable skill {name!r}") from exc

    def _store(self, kind: str, payload: BaseModel | dict) -> str:
        data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        value = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        reference = kind + "-" + hashlib.sha256(value.encode()).hexdigest()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        target = self.workspace_root / f"{reference}.json"
        if target.is_symlink():
            raise ValueError("stored result must not be a symlink")
        with self._lock:
            fd, name = tempfile.mkstemp(prefix=".result-", dir=self.workspace_root)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(value)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(name, target)
            finally:
                Path(name).unlink(missing_ok=True)
        return reference

    def load(self, reference: str) -> StoredAnalysis:
        if not re.fullmatch(r"analysis-[0-9a-f]{64}", reference):
            raise ValueError("invalid analysis result reference")
        path = self.workspace_root / f"{reference}.json"
        if path.is_symlink() or not path.resolve().is_relative_to(self.workspace_root):
            raise ValueError("analysis result escapes storage")
        value = path.read_text(encoding="utf-8")
        if hashlib.sha256(value.encode()).hexdigest() != reference.removeprefix("analysis-"):
            raise ValueError("stored analysis integrity check failed")
        result = StoredAnalysis.model_validate_json(value)
        if result.source_root != str(self.source_root):
            raise ValueError("analysis belongs to another source scope")
        self._definition(result.skill)
        self._check_sources(result.manifest)
        return result

    def _check_sources(self, manifest: SourceManifest) -> None:
        from data_agent.tools.source_tools import resolve_source_path

        for source in manifest.sources:
            path = resolve_source_path(self.source_root, source.path)
            if file_digest(path)[0] != source.sha256:
                raise ValueError(f"source changed since analysis: {source.path}")
            if source.parse_error:
                raise ValueError(f"source parse failure: {source.path}: {source.parse_error}")

    def execute(self, skill_name: str, source_paths: list[str]) -> dict:
        definition = self._definition(skill_name)
        if (
            not source_paths
            or len(source_paths) > 256
            or len(set(source_paths)) != len(source_paths)
        ):
            raise ValueError("supply between 1 and 256 unique assigned source paths")
        manifest = build_catalog(self.source_root)
        selected = SourceManifest(sources=[manifest.by_path(path) for path in sorted(source_paths)])
        self._check_sources(selected)
        context = ToolContext(self.source_root, self.workspace_root, selected)
        analyses = prepare_analysis(
            AnalysisRequest(context, tuple(sorted(source_paths))), load_analysis_runner(definition)
        )
        self._check_sources(selected)
        stored = StoredAnalysis(
            skill=skill_name,
            source_root=str(self.source_root),
            manifest=selected,
            source_paths=sorted(source_paths),
            analyses=analyses,
        )
        reference = self._store("analysis", stored)
        return {
            "result_ref": reference,
            "skill": skill_name,
            "source_paths": stored.source_paths,
            "analyses": [
                {
                    "name": item.name,
                    "summary": item.summary[:800],
                    "summary_truncated": len(item.summary) > 800,
                    "candidate_count": len(item.flag_candidates),
                    "overview_ids": [overview.overview_id for overview in item.overviews],
                }
                for item in analyses
            ],
            "candidate_count": sum(len(item.flag_candidates) for item in analyses),
            "details_omitted": True,
            "coverage_complete": False,
            "next_action": "Inspect stored candidates and evidence before submit_candidate_result.",
        }

    def read(
        self, result_ref: str, section: str = "candidates", offset: int = 0, max_chars: int = 12000
    ) -> dict:
        result = self.load(result_ref)
        if section == "candidates":
            value = [{"analysis": a.name, "candidates": a.flag_candidates} for a in result.analyses]
        elif section == "overviews":
            value = [o.model_dump(mode="json") for a in result.analyses for o in a.overviews]
        elif section == "all":
            value = result.model_dump(mode="json")
        else:
            raise ValueError("section must be candidates, overviews or all")
        return text_page(
            json.dumps(value, ensure_ascii=False), offset=offset, max_chars=max_chars
        ) | {
            "result_ref": result_ref,
            "section": section,
            "coverage_complete": False,
        }

    def reopen(self, result_ref: str, locator: str) -> dict:
        result = self.load(result_ref)
        validator = EvidenceValidator.source_backed(self.source_root, result.manifest)
        return validator.validate(locator).model_dump(mode="json")

    def submit(self, result_ref: str, candidate: CandidateSubmission) -> dict:
        result = self.load(result_ref)
        definition = self._definition(result.skill)
        findings = candidate.findings
        if len({f.finding_id for f in findings}) != len(findings):
            raise ValueError("duplicate candidate finding IDs")
        if any(f.verifier_status is not VerificationStatus.PENDING for f in findings):
            raise ValueError("candidate submission cannot self-declare verification")
        ids = {str(c["candidate_id"]) for a in result.analyses for c in a.flag_candidates}
        if any(set(f.deterministic_candidate_ids) - ids for f in findings):
            raise ValueError("unknown deterministic candidate ID")
        if any(d.candidate_id not in ids for d in candidate.candidate_dispositions):
            raise ValueError("unknown disposition candidate ID")
        findings, _ = normalize_findings(
            findings,
            analyses=[a.model_dump(mode="json") for a in result.analyses],
            desk_context={},
            report_id=definition.report_id,
        )
        validator = EvidenceValidator.source_backed(self.source_root, result.manifest)
        references = [ref for f in findings for ref in [*f.evidence, *f.counter_evidence]]
        references += [ref for d in candidate.candidate_dispositions for ref in d.evidence]
        validation = validator.validate_references(references)
        if not validation.valid:
            raise ValueError(
                "invalid candidate evidence: "
                + "; ".join(
                    f"{failure.locator}: {failure.reason}" for failure in validation.failures
                )
            )
        for finding in findings:
            finding.assert_evidence_policy()
        candidate = candidate.model_copy(update={"findings": findings})
        reference = self._store(
            "candidate",
            {"analysis_ref": result_ref, "candidate": candidate.model_dump(mode="json")},
        )
        return {
            "candidate_ref": reference,
            "analysis_ref": result_ref,
            "status": "pending",
            "finding_ids": [f.finding_id for f in findings],
            "verified": False,
        }


def build_review_skill_tools(
    source_root: Path, workspace_root: Path, skills: list[Skill]
) -> list[BaseTool]:
    """Bind trusted execution capabilities to the host's configured source directory."""
    definitions = {
        s.name: load_skill(s.path, skills_root=s.path.parent.parent)
        for s in skills
        if s.kind == "specialist-review"
    }
    if not definitions:
        return []
    execution = SkillExecution(source_root, workspace_root, definitions)

    def execute_review_analysis(skill_name: str, source_paths: list[str]) -> dict:
        """Run a registered specialist's trusted analysis over selected contained source paths."""
        return execution.execute(skill_name, source_paths)

    def read_analysis_result(
        result_ref: str,
        section: Literal["candidates", "overviews", "all"] = "candidates",
        offset: int = 0,
        max_chars: int = 12000,
    ) -> dict:
        """Read bounded stored details. Follow next_offset; partial pages never establish coverage."""
        return execution.read(result_ref, section, offset, max_chars)

    def reopen_analysis_evidence(result_ref: str, locator: str) -> dict:
        """Reopen manifest-pinned evidence for one stored analysis; unauthorized paths fail."""
        return execution.reopen(result_ref, locator)

    def submit_candidate_result(result_ref: str, candidate: CandidateSubmission) -> dict:
        """Persist a typed, evidence-checked specialist draft for later independent verification."""
        return execution.submit(result_ref, candidate)

    def guarded(function):
        from functools import wraps

        @wraps(function)
        def call(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except (OSError, ValueError, KeyError) as exc:
                raise ToolException(str(exc)) from exc

        return call

    return [
        StructuredTool.from_function(guarded(function), handle_tool_error=True)
        for function in (
            execute_review_analysis,
            read_analysis_result,
            reopen_analysis_evidence,
            submit_candidate_result,
        )
    ]
