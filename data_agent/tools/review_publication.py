"""Model-selected lead validation and atomic publication of compatible review artifacts."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from data_agent.review.application.run_bundle import load_completed_run
from data_agent.review.application.sealed_bundle import (
    file_hash,
    load_sealed_bundle,
    seal_bundle,
    validate_seal,
)
from data_agent.review.domain.lead_outputs import LeadDraft, LeadVerifierOutput
from data_agent.review.domain.reports import CrossSourceCluster, FinalReport
from data_agent.review.domain.review import ReviewRun, ReviewTask, RunContext, SourceCoverage
from data_agent.review.domain.verification import VerifierDecision
from data_agent.review.reporting.markdown import render_final_report, render_specialist_report
from data_agent.review.synthesis.collection import collect_reports
from data_agent.review.synthesis.lead_policy import (
    _apply_final_round_challenges,
    _needs_semantic_revision,
)
from data_agent.review.synthesis.validation import FinalValidationRequest, validate_final_report
from data_agent.review.verification.identity import content_digest, finding_version
from data_agent.tools.review_context import ToolContext
from data_agent.tools.review_operations import analyze_reports
from data_agent.tools.review_verification import VerificationCapabilities

if TYPE_CHECKING:
    from data_agent.tools.review_runs import RunCapabilities


def reports_version(record) -> str:
    return content_digest([a.report for a in record.assignments.values() if a.report])


def publication_fingerprint(record) -> str:
    return content_digest(
        {
            "assignments": {k: a.model_dump(mode="json") for k, a in record.assignments.items()},
            "lead": record.lead_state,
            "lead_history": record.lead_history,
            "classifications": record.classifications,
            "source_dispositions": {
                k: v.model_dump(mode="json") for k, v in record.source_dispositions.items()
            },
            "manifest_digest": record.manifest_digest,
        }
    )


class PublicationCapabilities:
    """Validate what the model selected; never choose a workflow or invoke a review graph."""

    def __init__(self, access: RunCapabilities) -> None:
        self.access = access

    def _request(self, record, reports, clusters):
        return FinalValidationRequest(
            ToolContext(
                self.access.store.source_root,
                self.access.store.output_dir / "workspace",
                record.manifest,
            ),
            reports,
            [CrossSourceCluster.model_validate(c) for c in clusters],
        )

    def inspect(self) -> dict:
        self.access._root()
        record = self.access.store.read()
        self.access.store.check_sources(record)
        reports, identities = collect_reports(record)
        return {
            "reports_version": reports_version(record),
            "finding_identities": identities,
            "analysis": analyze_reports(reports).model_dump(mode="json"),
            "lead_state": record.lead_state,
            "lead_history": record.lead_history,
        }

    def prepare(self, lead_ref: str) -> dict:
        self.access._root()
        record = self.access.store.read()
        self.access.store.check_sources(record)
        role = VerificationCapabilities.role_result(record, lead_ref, "review-lead")
        version = reports_version(record)
        if role["finding_version"] != version:
            raise ValueError("lead draft uses stale specialist reports")
        if record.lead_state.get("lead_ref") == lead_ref:
            return self._lead_receipt(record.lead_state)
        if len(record.lead_history) >= 2 or record.lead_state.get("status") == "failed":
            raise ValueError("lead verification revision budget exhausted")
        reports, _identities = collect_reports(record)
        analysis = analyze_reports(reports)
        draft = LeadDraft.model_validate(role["output"])
        report = FinalReport.model_validate(
            {
                **draft.model_dump(mode="json"),
                "cross_source_findings": [c.model_dump(mode="json") for c in analysis.clusters],
                "specialist_report_references": [
                    f"{r.domain.value}: {r.report_id}" for r in reports
                ],
            }
        )
        # These are code-owned disclosures and indexes, never new model conclusions.
        disclosures = [u for r in reports for u in r.unresolved_items]
        disclosures += [
            f"Unresolved specialist finding {f.finding_id}: {f.title}"
            for r in reports
            for f in r.unresolved_findings()
        ]
        disclosures += [
            f"{source_id}: {d.status}: {d.reason}"
            for source_id, d in record.source_dispositions.items()
        ]
        disclosures += [
            f"{a.assignment_id}/{source_id}: {d.status}: {d.reason}"
            for a in record.assignments.values()
            for source_id, d in a.dispositions.items()
            if d.status != "reviewed"
        ]
        report.unresolved_questions = list(
            dict.fromkeys([*report.unresolved_questions, *disclosures])
        )
        references = [ref for f in report.key_findings for ref in f.evidence]
        references += [ref for c in report.cross_source_findings for ref in c.supporting_evidence]
        report.evidence_index = list({r.locator: r for r in references}.values())
        clusters = [c.model_dump(mode="json") for c in analysis.clusters]
        blockers = validate_final_report(self._request(record, reports, clusters), report)
        state = {
            "lead_ref": lead_ref,
            "reports_version": version,
            "final_report": report.model_dump(mode="json"),
            "clusters": clusters,
            "status": "invalid" if blockers else "draft",
            "blockers": blockers,
        }

        def persist(current):
            if reports_version(current) != version:
                raise ValueError("reports changed while constructing the lead draft")
            current.lead_state = state

        self.access.store.update(persist)
        return self._lead_receipt(state)

    @staticmethod
    def _lead_receipt(state):
        return {
            "lead_ref": state.get("lead_ref"),
            "reports_version": state.get("reports_version"),
            "status": state.get("status"),
            "blockers": state.get("blockers", []),
            "verifier_ref": state.get("verifier_ref"),
            "accepted": state.get("status") == "accepted",
        }

    def apply(self, verifier_ref: str) -> dict:
        self.access._root()
        record = self.access.store.read()
        self.access.store.check_sources(record)
        if record.lead_state.get("verifier_ref") == verifier_ref:
            return self._lead_receipt(record.lead_state)
        state = dict(record.lead_state)
        if state.get("status") != "draft":
            raise ValueError("prepare a structurally valid current lead draft before verification")
        if len(record.lead_history) >= 2:
            raise ValueError("lead verification revision budget exhausted")
        verifier = VerificationCapabilities.role_result(
            record, verifier_ref, "review-lead-verifier"
        )
        lead = VerificationCapabilities.role_result(record, state["lead_ref"], "review-lead")
        if (
            verifier.get("lead_result_ref") != state["lead_ref"]
            or verifier["finding_version"] != reports_version(record)
            or lead["child_id"] == verifier["child_id"]
        ):
            raise ValueError("lead verification is stale or lacks an independent child")
        reports, _identities = collect_reports(record)
        report = FinalReport.model_validate(state["final_report"])
        blockers = validate_final_report(self._request(record, reports, state["clusters"]), report)
        verdict = LeadVerifierOutput.model_validate(verifier["output"])
        round_number = len(record.lead_history) + 1
        # Independent lead objections may cite only already-approved report evidence.
        approved = {
            ref.locator
            for r in reports
            for f in r.findings
            for ref in [*f.evidence, *f.counter_evidence]
        }
        if any(ref.locator not in approved for c in verdict.challenges for ref in c.evidence):
            blockers.append("lead challenge contains non-specialist evidence")
        status = "draft"
        if blockers or verdict.decision in (VerifierDecision.REJECT, VerifierDecision.UNRESOLVED):
            status = "failed"
            blockers += [verdict.feedback or "independent lead verification did not pass"]
        elif round_number < 2 and (
            verdict.decision is VerifierDecision.REVISE
            or _needs_semantic_revision(verdict.challenges)
        ):
            status = "revise"
            blockers = [verdict.feedback or "independent verifier requires revision"]
            blockers += [c.explanation for c in verdict.challenges]
        else:
            report, clusters, _suppressed, objections = _apply_final_round_challenges(
                state["clusters"], report, verdict.challenges
            )
            if verdict.decision is VerifierDecision.REVISE and not verdict.challenges:
                objections.append(
                    "revision budget exhausted without structured resolvable objections"
                )
            blockers += objections
            blockers += validate_final_report(self._request(record, reports, clusters), report)
            status = "failed" if blockers else "accepted"
            state.update(final_report=report.model_dump(mode="json"), clusters=clusters)
        state.update(status=status, blockers=blockers, verifier_ref=verifier_ref)
        entry = {
            "round_number": round_number,
            **verdict.model_dump(mode="json"),
            "lead_ref": state["lead_ref"],
            "verifier_ref": verifier_ref,
            "status": status,
        }

        def persist(current):
            if (
                current.lead_state != record.lead_state
                or reports_version(current) != state["reports_version"]
            ):
                raise ValueError("lead state changed during independent verification")
            current.lead_state = state
            current.lead_history.append(entry)

        self.access.store.update(persist)
        return self._lead_receipt(state)

    def requirements(self) -> list[str]:
        record = self.access.store.read()
        self.access.store.check_sources(record)
        coverage = self.access.coverage()
        blockers = list(coverage["blockers"])
        for assignment in record.assignments.values():
            if not assignment.report:
                blockers.append(f"{assignment.assignment_id}: finalize the specialist report")
                continue
            for identifier, finding in assignment.findings.items():
                history = assignment.verification.get(identifier, [])
                if (
                    not history
                    or history[-1]["finding_version"] != finding_version(finding)
                    or history[-1]["status"] != finding["verifier_status"]
                    or finding["verifier_status"] == "pending"
                ):
                    blockers.append(f"{identifier}: current independent verification required")
                if history:
                    VerificationCapabilities.role_result(
                        record, history[-1]["adjudicator_ref"], "review-adjudicator"
                    )
                    VerificationCapabilities.role_result(
                        record, history[-1]["challenger_ref"], "review-challenger"
                    )
                if finding["verifier_status"] in ("passed", "revised"):
                    gate = VerificationCapabilities(self.access).evidence(
                        assignment.assignment_id, identifier
                    )
                    if gate["gate"]["decision"] != "pass":
                        blockers.append(f"{identifier}: evidence gate no longer passes")
            audit = VerificationCapabilities(self.access)._audit(record, assignment)
            if audit.uncovered_candidates and not audit.unresolved_disclosures:
                blockers.append(
                    f"{assignment.assignment_id}: account for or disclose uncovered candidates"
                )
        if not record.assignments:
            blockers.append("at least one specialist report is required")
        if record.lead_state.get("status") != "accepted":
            blockers.append("prepare and independently verify the lead report")
            blockers.extend(record.lead_state.get("blockers", []))
        elif record.lead_state.get("reports_version") != reports_version(record):
            blockers.append("lead acceptance is stale after specialist report changes")
        else:
            lead = VerificationCapabilities.role_result(
                record, record.lead_state["lead_ref"], "review-lead"
            )
            verifier = VerificationCapabilities.role_result(
                record, record.lead_state["verifier_ref"], "review-lead-verifier"
            )
            if (
                verifier.get("lead_result_ref") != record.lead_state["lead_ref"]
                or verifier["finding_version"] != reports_version(record)
                or lead["child_id"] == verifier["child_id"]
                or not record.lead_history
                or record.lead_history[-1].get("status") != "accepted"
                or record.lead_history[-1].get("verifier_ref") != record.lead_state["verifier_ref"]
            ):
                blockers.append("current independent lead verification required")
            reports, _identities = collect_reports(record)
            blockers.extend(
                validate_final_report(
                    self._request(record, reports, record.lead_state["clusters"]),
                    FinalReport.model_validate(record.lead_state["final_report"]),
                )
            )
        return list(dict.fromkeys(blockers))

    def publish(self) -> dict:
        self.access._root()
        blockers = self.requirements()
        if blockers:
            return {
                "published": False,
                "blockers": blockers[:100],
                "total_blockers": len(blockers),
                "truncated": len(blockers) > 100,
            }
        record = self.access.store.read()
        fingerprint = publication_fingerprint(record)
        root = self.access.store.output_dir
        target = root / "bundle"
        if target.is_symlink():
            raise ValueError("published bundle must not be a symlink")
        if target.exists():
            receipt = validate_seal(target, record.artifacts.get("bundle_seal"))
            if receipt["input_fingerprint"] != fingerprint:
                raise ValueError(
                    "existing sealed bundle differs from current authoritative results"
                )
            load_sealed_bundle(target, record.artifacts.get("bundle_seal"))
            seal = file_hash(target / "bundle_receipt.json")
        else:
            stage = Path(tempfile.mkdtemp(prefix=".bundle-", dir=root))
            try:
                self._write_bundle(stage, target, record)
                load_completed_run(stage)
                seal = seal_bundle(stage, fingerprint)
                load_sealed_bundle(stage, seal)

                # Serialize the filesystem commit with state changes. A crash after rename
                # is recovered by validating and adopting this exact seal on replay.
                def commit(current):
                    self.access.store.check_sources(current)
                    if publication_fingerprint(current) != fingerprint:
                        raise ValueError(
                            "review changed while publishing; retry after inspecting state"
                        )
                    os.rename(stage, target)
                    current.status = "completed"
                    current.artifacts.update(bundle=str(target), bundle_seal=seal)

                self.access.store.update(commit)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)

        def adopt(current):
            if publication_fingerprint(current) != fingerprint:
                raise ValueError("review changed before completion could be sealed")
            current.status = "completed"
            current.artifacts.update(bundle=str(target), bundle_seal=seal)

        self.access.store.update(adopt)
        return {
            "published": True,
            "bundle_path": str(target),
            "status": "completed",
            "unresolved_items": len(record.lead_state["final_report"]["unresolved_questions"]),
            "seal": seal,
        }

    def _write_bundle(self, root, final_root, record):
        reports, identities = collect_reports(record)
        root.joinpath("specialists").mkdir()

        def write(name, value):
            path = root / name
            text = value if isinstance(value, str) else json.dumps(value, indent=2, default=str)
            with path.open("w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())

        report = FinalReport.model_validate(record.lead_state["final_report"])
        write("catalog.json", record.manifest.model_dump(mode="json"))
        write("desk_context.json", record.desk_context.model_dump(mode="json"))
        write("final_report.json", report.model_dump(mode="json"))
        write("final_findings.md", render_final_report(report))
        write("finding_identities.json", identities)
        write(
            "lead_verification.json",
            {"lead_round": len(record.lead_history), "history": record.lead_history},
        )
        write(
            "run_context.json",
            RunContext(
                run_id=record.run_id,
                source_root=record.source_root,
                output_dir=str(final_root),
                desk_template=record.desk_context,
                review_period=record.review_period,
            ).model_dump(mode="json"),
        )
        for specialist in reports:
            stem = specialist.domain.value
            assignments = [
                a
                for a in record.assignments.values()
                if self.access.definitions[a.skill_name].domain == specialist.domain
            ]

            def mapped_findings(initial=False, status=None, assignments=assignments):
                values = []
                for a in assignments:
                    candidates = (
                        a.initial_findings if initial and a.initial_findings else a.findings
                    )
                    for key, raw in candidates.items():
                        if status is not None and raw["verifier_status"] not in status:
                            continue
                        value = dict(raw, finding_id=identities[a.assignment_id][key])
                        if initial:
                            value["verifier_status"] = "pending"
                        values.append(value)
                return values

            write(f"specialists/{stem}.json", specialist.model_dump(mode="json"))
            write(f"specialists/{stem}.md", render_specialist_report(specialist))
            history = specialist.verification_history
            write(
                f"specialists/{stem}.verification.json",
                {
                    "initial_candidates": mapped_findings(initial=True),
                    "initial_candidates_provenance": "original_drafts"
                    if all(a.initial_findings for a in assignments)
                    else "legacy_latest_draft_snapshot",
                    "verified_findings": mapped_findings(status={"passed", "revised"}),
                    "rejected_findings": mapped_findings(status={"rejected"}),
                    "unresolved_findings": mapped_findings(status={"unresolved"}),
                    "verifier_round": max((len(h) for h in history.values()), default=0),
                    "omission_audit": specialist.omission_audit.model_dump(mode="json")
                    if specialist.omission_audit
                    else None,
                    "evidence_gates": {
                        k: v[-1].evidence_gate.model_dump(mode="json")
                        for k, v in history.items()
                        if v and v[-1].evidence_gate
                    },
                    "adversarial_cases": {
                        k: v[-1].adversarial_case.model_dump(mode="json")
                        for k, v in history.items()
                        if v and v[-1].adversarial_case
                    },
                    "adjudications": {
                        k: v[-1].adjudication.model_dump(mode="json")
                        for k, v in history.items()
                        if v and v[-1].adjudication
                    },
                    "version_records": {a.assignment_id: a.verification for a in assignments},
                },
            )
            assignment_ids = {a.assignment_id for a in assignments}
            trace = [t for t in record.trace if t.get("assignment_id") in assignment_ids]
            write(f"specialists/{stem}.research_trace.json", trace)
            write(
                f"specialists/{stem}.adversarial_trace.json",
                {
                    finding_id: [t for t in trace if t.get("finding_id") == original]
                    for aid in assignment_ids
                    for original, finding_id in identities[aid].items()
                },
            )
        coverage = []
        for source in record.manifest.sources:
            disposition = record.source_dispositions.get(source.source_id)
            required = record.classifications.get(source.source_id, [])
            coverage.append(
                SourceCoverage(
                    source_id=source.source_id,
                    required_reviewers=required,
                    completed_reviewers=[] if disposition else required,
                    status=disposition.status if disposition else "reviewed",
                    notes=disposition.reason if disposition else None,
                )
            )
        run = ReviewRun(
            run_id=record.run_id,
            status="completed",
            created_at=record.created_at,
            source_root=record.source_root,
            output_dir=str(final_root),
            manifest=record.manifest,
            coverage=coverage,
            tasks=[
                ReviewTask(
                    task_id=a.assignment_id,
                    domain=self.access.definitions[a.skill_name].domain,
                    source_ids=a.source_ids,
                    scope=record.review_period,
                )
                for a in record.assignments.values()
            ],
        )
        write("run_manifest.json", run.model_dump(mode="json"))
