"""Trusted review roles on the ordinary one-level ReAct delegation host."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from data_agent.agent.subagents.contracts import ChildPreparation, DelegationRequest, SubagentSpec
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.lead_outputs import LeadDraft, LeadVerifierOutput
from data_agent.review.domain.outputs import AdjudicatorOutput, ChallengerOutput
from data_agent.review.domain.source import SourceManifest
from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.synthesis.collection import collect_reports, report_projection
from data_agent.review.verification.challenge_validation import _sanitize_challenge_case
from data_agent.review.verification.identity import finding_version
from data_agent.review.verification.projection import _strip_hidden
from data_agent.review.verification.rules import required_challenge_types
from data_agent.skills.review import SkillDefinition
from data_agent.tools.research import build_research_tools
from data_agent.tools.review_context import ToolContext
from data_agent.tools.review_operations import EvidenceRequest, analyze_reports, validate_evidence
from data_agent.tools.review_runs import ReviewWorkspace, _digest, build_review_run_tools
from data_agent.tools.review_skills import CandidateSubmission


class SpecialistInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignment_id: str = Field(min_length=1)


class FindingInput(SpecialistInput):
    finding_id: str = Field(min_length=1)


class LeadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


def review_profiles(definitions: dict[str, SkillDefinition]) -> tuple[SubagentSpec, ...]:
    """Registered roles expose fixed contracts, never caller-selected code or models."""
    specialists = tuple(
        SubagentSpec(
            name=f"review-{name}",
            description=f"Analyze a stored {name} assignment; context JSON: assignment_id.",
            system_prompt="Investigate the assigned sources using the specialist skill and deterministic analysis. "
            "Interpret evidence, counter-evidence and uncertainty. Return a typed pending candidate draft. "
            "Every evidence locator must be an exact source:// URI emitted by the source tools. "
            "Analysis references and overview IDs belong in analysis_performed, never in evidence. "
            "Copy deterministic candidate IDs exactly from stored analysis when linking findings.",
            tool_names=(
                "review_inventory",
                "execute_assigned_analysis",
                "read_assigned_analysis",
                "review_source_tool",
            ),
            skill_names=(name,),
            input_schema=SpecialistInput,
            result_schema=CandidateSubmission,
            model_role="low_cost",
            max_model_calls=18,
            max_tool_calls=32,
        )
        for name in definitions
    )
    skill_names = tuple(definitions)
    return specialists + (
        SubagentSpec(
            name="review-challenger",
            description="Independently challenge one stored finding; context JSON: assignment_id, finding_id.",
            system_prompt="Independently test the claim using assigned evidence and the policy. "
            "Search for contrary evidence and alternative explanations; do not issue a verifier decision. "
            "Cover every required challenge category and disclose incomplete research.",
            tool_names=("review_inventory", "review_source_tool"),
            skill_names=skill_names,
            input_schema=FindingInput,
            result_schema=ChallengerOutput,
            model_role="low_cost",
            max_model_calls=12,
            max_tool_calls=16,
        ),
        SubagentSpec(
            name="review-adjudicator",
            description="Adjudicate a finding after independent challenge; context JSON: assignment_id, finding_id.",
            system_prompt="Decide PASS, REVISE, REJECT or UNRESOLVED using only the supplied finding, "
            "evidence gate, independent challenge and policy. You have no research tools. "
            "Do not overlook failed or incomplete challenges; explain required revisions.",
            input_schema=FindingInput,
            result_schema=AdjudicatorOutput,
            model_role="high_cost",
            max_model_calls=2,
            max_tool_calls=0,
        ),
        SubagentSpec(
            name="review-lead",
            description="Synthesize stored validated specialist reports; context JSON: {}.",
            system_prompt="Synthesize validated specialist reports and deterministic cross-report analysis. "
            "Preserve finding-specific evidence and derived_from links, severity ceilings and unresolved disclosures. "
            "Do not read raw sources.",
            tool_names=("read_specialist_report",),
            skill_names=("lead-review",),
            input_schema=LeadInput,
            result_schema=LeadDraft,
            model_role="high_cost",
            max_model_calls=6,
            max_tool_calls=4,
        ),
        SubagentSpec(
            name="review-lead-verifier",
            description="Independently verify a stored lead draft; context JSON: {}.",
            system_prompt="Independently challenge the lead draft against supplied validated specialist reports. "
            "Test derivation, evidence specificity, severity and omissions. Do not read raw sources.",
            tool_names=("read_specialist_report",),
            skill_names=("lead-review",),
            input_schema=LeadInput,
            result_schema=LeadVerifierOutput,
            model_role="high_cost",
            max_model_calls=6,
            max_tool_calls=4,
        ),
    )


class ReviewRoleAdapter:
    """Rebuild peer contexts from authoritative records, ignoring parent prose."""

    def __init__(self, workspace: ReviewWorkspace, run_id: str) -> None:
        self.workspace, self.run_id = workspace, run_id

    def prepare(
        self, spec: SubagentSpec, request: DelegationRequest, child_id: str
    ) -> ChildPreparation:
        if spec.input_schema is None:
            raise ValueError("review role requires a typed input contract")
        role_input = spec.input_schema.model_validate_json(request.context)
        access = self.workspace.access(self.run_id)
        record = access.store.read()
        access.store.check_sources(record)
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "review_period": record.review_period.model_dump(mode="json"),
            "desk_context": record.desk_context.model_dump(mode="json"),
        }
        assignment_id = getattr(role_input, "assignment_id", None)
        finding_id = getattr(role_input, "finding_id", None)
        version = None
        tools = ()
        selected_skills = spec.skill_names
        if assignment_id:
            assignment = access._assignment(record, assignment_id)
            definition = self.workspace.definitions[assignment.skill_name]
            if (
                spec.name.startswith("review-")
                and spec.name not in {"review-challenger", "review-adjudicator"}
                and spec.name != "review-" + assignment.skill_name
            ):
                raise ValueError("specialist profile does not match the assignment")
            scoped = ReviewWorkspace(
                self.workspace.source_root,
                self.workspace.workspace_root,
                self.workspace.definitions,
                self.run_id,
                assignment_id,
                trace_context={"agent_id": child_id, "role": spec.name, "finding_id": finding_id},
                output_dir=self.workspace.output_dir,
            )
            tools = tuple(t for t in build_review_run_tools(scoped) if t.name in spec.tool_names)
            selected_skills = (assignment.skill_name,) if spec.skill_names else ()
            payload.update(
                {
                    "assignment_id": assignment_id,
                    "skill": assignment.skill_name,
                    "source_paths": [record.manifest.by_id(s).path for s in assignment.source_ids],
                }
            )
            if tools:
                research = build_research_tools(
                    ToolContext(
                        access.store.source_root,
                        access.store.output_dir / "workspace",
                        record.manifest,
                    ),
                    payload["source_paths"],
                    [],
                    max_calls=spec.max_tool_calls or 0,
                )
                payload["research_tool_contracts"] = {
                    tool.name: {
                        "description": tool.description,
                        "arguments": tool.args_schema.model_json_schema(),
                    }
                    for tool in research
                }
                payload["sql_tables"] = (
                    "Use SELECT table_name FROM information_schema.tables to discover registered table names. "
                    "Names use src_ plus sanitized relative path (for example src_sgmr_csv). "
                    "File paths and read_csv functions are not SQL table names and cannot be used."
                )
            if finding_id:
                if finding_id not in assignment.findings:
                    raise ValueError("unknown stored finding")
                finding = Finding.model_validate(assignment.findings[finding_id])
                version = finding_version(finding)
                source_manifest = SourceManifest(
                    sources=[record.manifest.by_id(s) for s in assignment.source_ids]
                )
                gate = validate_evidence(
                    EvidenceRequest(
                        ToolContext(
                            access.store.source_root,
                            access.store.output_dir / "workspace",
                            source_manifest,
                        ),
                        finding,
                    )
                )
                payload.update(
                    {
                        "finding": finding.model_dump(mode="json"),
                        "evidence_gate": gate.model_dump(mode="json"),
                        "policy": definition.verifier_policy,
                        "required_challenge_types": [
                            kind.value
                            for kind in required_challenge_types(
                                cross_source_required=len(assignment.source_ids) > 1
                            )
                        ],
                    }
                )
                if spec.name == "review-challenger":
                    # The parent task/context prose is deliberately absent. Source research
                    # tools cannot expose the analyst's severity or earlier decisions.
                    payload = _strip_hidden(payload)
                elif spec.name == "review-adjudicator":
                    cases = [
                        r
                        for r in record.role_results.values()
                        if r["role"] == "review-challenger"
                        and r["assignment_id"] == assignment_id
                        and r["finding_id"] == finding_id
                        and r["finding_version"] == version
                    ]
                    if not cases:
                        raise ValueError("independent challenge required before adjudication")
                    payload["independent_challenge"] = _sanitize_challenge_case(
                        ChallengerOutput.model_validate(cases[-1]["output"]),
                        finding_id=finding_id,
                        validator=EvidenceValidator.source_backed(
                            access.store.source_root, source_manifest
                        ),
                        assigned_paths=payload["source_paths"],
                    ).model_dump(mode="json")
                    payload["challenger_result_ref"] = cases[-1]["result_ref"]
            else:
                payload["existing_findings"] = assignment.findings
                payload["verification_feedback"] = assignment.verification
                payload["omission_disclosure"] = assignment.omission_disclosure
                payload["revision_instruction"] = (
                    "Preserve stable finding IDs; submit changed findings with pending status. "
                    "The host retains unchanged findings and enforces two verification rounds."
                )
        else:
            reports, identities = collect_reports(record)
            payload["specialist_reports"] = report_projection(reports)
            payload["finding_identities"] = identities
            payload["cross_report_analysis"] = analyze_reports(reports).model_dump(mode="json")
            payload["lead_feedback"] = record.lead_state.get("blockers", [])
            payload["previous_lead_draft"] = record.lead_state.get("final_report")
            payload["lead_rounds_remaining"] = 2 - len(record.lead_history)
            tools = tuple(
                t for t in build_review_run_tools(self.workspace) if t.name in spec.tool_names
            )
            version = _digest([a.report for a in record.assignments.values() if a.report])
            if spec.name == "review-lead-verifier":
                if (
                    record.lead_state.get("status") != "draft"
                    or record.lead_state.get("reports_version") != version
                ):
                    raise ValueError(
                        "prepare a current structurally valid lead draft before verification"
                    )
                payload["final_report"] = record.lead_state["final_report"]
                payload["lead_result_ref"] = record.lead_state["lead_ref"]

        def accept(output: BaseModel) -> dict:
            current = access.store.read()
            access.store.check_sources(current)
            if assignment_id and finding_id:
                current_finding = access._assignment(current, assignment_id).findings[finding_id]
                if finding_version(current_finding) != version:
                    raise ValueError("finding changed during independent role execution")
                if getattr(output, "finding_id", None) != finding_id:
                    raise ValueError("role result has the wrong finding identity")
            if assignment_id is None:
                current_reports = [a.report for a in current.assignments.values() if a.report]
                if _digest(current_reports) != version:
                    raise ValueError("specialist reports changed during lead execution")
            candidate_ref = None
            if isinstance(output, CandidateSubmission):
                candidate_ref = access.submit(assignment_id, output)["candidate_ref"]
            value = {
                "role": spec.name,
                "model_role": spec.model_role,
                "child_id": child_id,
                "assignment_id": assignment_id,
                "finding_id": finding_id,
                "finding_version": version,
                "output": output.model_dump(mode="json"),
                "candidate_ref": candidate_ref,
                "challenger_result_ref": payload.get("challenger_result_ref"),
                "lead_result_ref": payload.get("lead_result_ref"),
            }
            reference = "role-" + _digest(value)
            value["result_ref"] = reference

            def persist(record):
                if (
                    assignment_id
                    and finding_id
                    and finding_version(record.assignments[assignment_id].findings[finding_id])
                    != version
                ):
                    raise ValueError("finding changed before verification result could be stored")
                if (
                    assignment_id is None
                    and _digest([a.report for a in record.assignments.values() if a.report])
                    != version
                ):
                    raise ValueError(
                        "specialist reports changed before lead result could be stored"
                    )
                if (
                    spec.name == "review-lead-verifier"
                    and record.lead_state.get("lead_ref") != value["lead_result_ref"]
                ):
                    raise ValueError("lead draft changed during independent verification")
                record.role_results[reference] = value
                record.child_runs[child_id] = {
                    **record.child_runs.get(child_id, {}),
                    "role": spec.name,
                    "status": "completed",
                    "result_ref": reference,
                    "at": datetime.now(UTC).isoformat(),
                }

            access.store.update(persist)
            return {
                "result_ref": reference,
                "role": spec.name,
                "candidate_ref": candidate_ref,
                "finding_id": finding_id,
                "finding_version": version,
                "verified": False,
            }

        return ChildPreparation(
            prompt="Complete the trusted role using this authoritative context:\n"
            + json.dumps(payload),
            tools=tools,
            skill_names=selected_skills,
            accept=accept,
        )
