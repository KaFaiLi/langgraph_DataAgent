"""Version-bound verification, omission handling and specialist report capabilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.outputs import AdjudicatorOutput, ChallengerOutput
from data_agent.review.domain.verification import AdjudicationResult, VerificationRound
from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.verification.challenge_validation import _sanitize_challenge_case
from data_agent.review.verification.identity import content_digest, finding_version
from data_agent.review.verification.reducer import reduce_verification
from data_agent.review.verification.rules import guard_adjudication
from data_agent.review.verification.severity import _severity_ceiling
from data_agent.tools.review_context import ToolContext
from data_agent.tools.review_operations import (
    EvidenceRequest,
    OmissionRequest,
    ReportRequest,
    audit_candidates,
    construct_report,
    validate_evidence,
)

if TYPE_CHECKING:
    from data_agent.tools.review_runs import RunCapabilities


class VerificationCapabilities:
    """Apply shared domain rules to stored facts; this class never invokes a model or graph."""

    def __init__(self, access: RunCapabilities) -> None:
        self.access = access

    def _context(self, record, assignment):
        from data_agent.review.domain.source import SourceManifest

        return ToolContext(
            self.access.store.source_root,
            self.access.store.output_dir / "workspace",
            SourceManifest(sources=[record.manifest.by_id(s) for s in assignment.source_ids]),
        )

    def evidence(self, assignment_id: str, finding_id: str) -> dict:
        record = self.access.store.read()
        assignment = self.access._assignment(record, assignment_id)
        self.access.store.check_sources(record)
        finding = Finding.model_validate(assignment.findings[finding_id])
        gate = validate_evidence(
            EvidenceRequest(
                self._context(record, assignment),
                finding,
                round_number=min(
                    len(assignment.verification.get(finding_id, [])) + 1, record.max_verifier_rounds
                ),
                max_rounds=record.max_verifier_rounds,
            )
        )
        return {"finding_version": finding_version(finding), "gate": gate.model_dump(mode="json")}

    @staticmethod
    def role_result(record, reference: str, role: str) -> dict:
        result = record.role_results.get(reference)
        if not result or result.get("role") != role:
            raise ValueError(f"stored {role} result required")
        raw = {k: v for k, v in result.items() if k != "result_ref"}
        if reference != "role-" + content_digest(raw) or result.get("result_ref") != reference:
            raise ValueError("role result integrity check failed")
        child = record.child_runs.get(result["child_id"], {})
        if child.get("status") != "completed" or child.get("result_ref") != reference:
            raise ValueError("role result lacks a completed independent child")
        return result

    def apply(self, assignment_id: str, adjudicator_ref: str) -> dict:
        """Only independent, stored, current-version outputs can change verification state."""
        self.access._root()
        record = self.access.store.read()
        self.access.store.check_sources(record)
        assignment = self.access._assignment(record, assignment_id)
        adjudicator = self.role_result(record, adjudicator_ref, "review-adjudicator")
        challenger_ref = adjudicator.get("challenger_result_ref")
        challenger = self.role_result(record, challenger_ref, "review-challenger")
        finding_id = adjudicator["finding_id"]
        finding = Finding.model_validate(assignment.findings[finding_id])
        version = finding_version(finding)
        for role in (adjudicator, challenger):
            if (
                role["assignment_id"] != assignment_id
                or role["finding_id"] != finding_id
                or role["finding_version"] != version
            ):
                raise ValueError("verification result is stale or belongs to another finding")
        if adjudicator["child_id"] == challenger["child_id"]:
            raise ValueError("challenge and adjudication require independent children")
        previous = assignment.verification.get(finding_id, [])
        existing = next((r for r in previous if r["adjudicator_ref"] == adjudicator_ref), None)
        if existing:
            return self._receipt(finding_id, existing)
        if any(r["challenger_ref"] == challenger_ref for r in previous):
            raise ValueError(
                "a fresh independent challenge is required for another verification round"
            )
        round_number = len(previous) + 1
        if round_number > record.max_verifier_rounds:
            raise ValueError("verification revision budget exhausted; retain the terminal outcome")
        ctx = self._context(record, assignment)
        gate = validate_evidence(
            EvidenceRequest(ctx, finding, round_number, record.max_verifier_rounds)
        )
        case = _sanitize_challenge_case(
            ChallengerOutput.model_validate(challenger["output"]),
            finding_id=finding_id,
            validator=EvidenceValidator.source_backed(ctx.source_root, ctx.manifest),
            assigned_paths=[s.path for s in ctx.manifest.sources],
        )
        output = AdjudicatorOutput.model_validate(adjudicator["output"])
        result = AdjudicationResult(
            **output.model_dump(mode="json"),
            evidence_gate=gate,
            adversarial_case=case,
            challenge_summary=case.challenges,
        )
        if not assignment.analysis_ref:
            raise ValueError("stored deterministic analysis required")
        analyses = self.access._execution(assignment).load(assignment.analysis_ref).analyses
        result = guard_adjudication(
            finding,
            result,
            evidence_gate=gate,
            cross_source_required=len(assignment.source_ids) > 1,
            severity_ceiling=_severity_ceiling(
                finding, [a.model_dump(mode="json") for a in analyses]
            ),
        )
        transition = reduce_verification(
            [finding],
            [result],
            round_number=round_number,
            max_verifier_rounds=record.max_verifier_rounds,
            research_mode="independent_react_peers",
        )
        updated = (
            transition.pending + transition.verified + transition.rejected + transition.unresolved
        )[0]
        entry = {
            "finding_version": version,
            "adjudicator_ref": adjudicator_ref,
            "challenger_ref": challenger_ref,
            "status": updated.verifier_status.value,
            "round": transition.history[finding_id][-1].model_dump(mode="json"),
        }

        def persist(current):
            target = self.access._assignment(current, assignment_id)
            if finding_version(target.findings[finding_id]) != version:
                raise ValueError("finding changed before verification could be applied")
            history = target.verification.setdefault(finding_id, [])
            if any(r["adjudicator_ref"] == adjudicator_ref for r in history):
                return
            if len(history) != len(previous):
                raise ValueError("verification changed concurrently; inspect the current record")
            target.findings[finding_id] = updated.model_dump(mode="json")
            history.append(entry)
            target.report = None

        self.access.store.update(persist)
        return self._receipt(finding_id, entry)

    @staticmethod
    def _receipt(finding_id, entry):
        return {
            "finding_id": finding_id,
            "finding_version": entry["finding_version"],
            "status": entry["status"],
            "decision": entry["round"]["decision"],
            "feedback": entry["round"]["feedback"],
            "round_number": entry["round"]["round_number"],
            "adjudicator_ref": entry["adjudicator_ref"],
        }

    def _audit(self, record, assignment):
        if not assignment.analysis_ref:
            raise ValueError("stored analysis required for omission audit")
        stored = self.access._execution(assignment).load(assignment.analysis_ref)
        findings = [Finding.model_validate(f) for f in assignment.findings.values()]
        audit = audit_candidates(
            OmissionRequest(
                self._context(record, assignment),
                tuple(stored.source_paths),
                stored.analyses,
                verified=findings,
                dispositions=list(assignment.candidate_dispositions.values()),
            )
        )
        if assignment.omission_disclosure:
            audit = audit.model_copy(
                update={
                    "rescue_required": False,
                    "rescue_used": bool(assignment.rescue_attempts),
                    "unresolved_disclosures": [
                        f"Unresolved deterministic candidate {c.candidate_id}: {assignment.omission_disclosure}"
                        for c in audit.uncovered_candidates
                    ],
                }
            )
        return audit

    def omissions(
        self,
        assignment_id: str,
        action: Literal["inspect", "rescue", "disclose"] = "inspect",
        reason: str = "",
    ) -> dict:
        self.access._root()
        record = self.access.store.read()
        self.access.store.check_sources(record)
        assignment = self.access._assignment(record, assignment_id)
        if action != "inspect":
            if not reason.strip() or len(reason) > 2000:
                raise ValueError("rescue or disclosure requires a bounded reason")

            def persist(current):
                target = self.access._assignment(current, assignment_id)
                if action == "rescue":
                    if target.rescue_attempts >= 1:
                        raise ValueError(
                            "omission rescue budget exhausted; explicitly disclose remaining omissions"
                        )
                    target.rescue_attempts += 1
                    target.omission_disclosure = None
                else:
                    target.omission_disclosure = reason
                target.report = None

            self.access.store.update(persist)
            record = self.access.store.read()
            assignment = self.access._assignment(record, assignment_id)
        audit = self._audit(record, assignment)
        return {
            "assignment_id": assignment_id,
            "audit": audit.model_dump(mode="json"),
            "rescue_attempts": assignment.rescue_attempts,
            "next_action": "Investigate uncovered candidates or explicitly disclose unresolved omissions."
            if audit.uncovered_candidates and not audit.unresolved_disclosures
            else None,
        }

    def finalize(self, assignment_id: str) -> dict:
        self.access._root()
        record = self.access.store.read()
        self.access.store.check_sources(record)
        assignment = self.access._assignment(record, assignment_id)
        if assignment.report:
            return {
                "report_id": assignment.report["report_id"],
                "assignment_id": assignment_id,
                "stored": True,
            }
        if not assignment.candidate_ref or not assignment.analysis_ref:
            raise ValueError("analysis and typed candidate required before specialist report")
        if set(assignment.source_ids) - set(assignment.dispositions):
            raise ValueError("assigned sources need explicit dispositions before specialist report")
        groups = {status: [] for status in VerificationStatus}
        history = {}
        for finding_id, raw in assignment.findings.items():
            finding = Finding.model_validate(raw)
            records = assignment.verification.get(finding_id, [])
            if not records or records[-1]["finding_version"] != finding_version(finding):
                raise ValueError(
                    f"{finding_id}: independent verification required for current version"
                )
            if records[-1]["status"] != finding.verifier_status.value:
                raise ValueError(f"{finding_id}: self-declared verification status")
            if finding.verifier_status is VerificationStatus.PENDING:
                raise ValueError(f"{finding_id}: revise and independently verify pending finding")
            groups[finding.verifier_status].append(finding)
            history[finding_id] = [VerificationRound.model_validate(r["round"]) for r in records]
        audit = self._audit(record, assignment)
        if audit.uncovered_candidates and not audit.unresolved_disclosures:
            raise ValueError(
                "unaccounted deterministic candidates: rescue, disposition or explicitly disclose omissions"
            )
        stored = self.access._execution(assignment).load(assignment.analysis_ref)
        definition = self.access.definitions[assignment.skill_name]
        report = construct_report(
            ReportRequest(
                self._context(record, assignment),
                definition.domain,
                definition.label,
                definition.report_id,
                record.review_period,
                assignment.rationale,
                assignment.source_ids,
                analyses=stored.analyses,
                verified=groups[VerificationStatus.PASSED] + groups[VerificationStatus.REVISED],
                unresolved=groups[VerificationStatus.UNRESOLVED],
                rejected=groups[VerificationStatus.REJECTED],
                history=history,
                omission_audit=audit,
                unresolved_items=assignment.unresolved_items,
            )
        )
        expected = assignment.model_dump(mode="json")

        def persist(current):
            target = self.access._assignment(current, assignment_id)
            if target.model_dump(mode="json") != expected:
                raise ValueError("assignment changed during report construction")
            target.report = report.model_dump(mode="json")

        self.access.store.update(persist)
        return {
            "assignment_id": assignment_id,
            "report_id": report.report_id,
            "stored": True,
            "verified_findings": len(report.verified_findings()),
            "unresolved_items": report.unresolved_items,
            "overview_count": len(report.data_overviews),
        }
