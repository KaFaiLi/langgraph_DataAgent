"""Typed collection of specialist reports for synthesis and compatible domain bundles."""

from __future__ import annotations

from collections import defaultdict

from data_agent.review.domain.reports import SpecialistReport
from data_agent.review.domain.run_record import ReviewRecord
from data_agent.review.domain.verification import OmissionAuditResult


def collect_reports(
    record: ReviewRecord,
) -> tuple[list[SpecialistReport], dict[str, dict[str, str]]]:
    """Merge assignments within a domain using stable namespaces when identities overlap."""
    grouped = defaultdict(list)
    for assignment in record.assignments.values():
        if not assignment.report:
            raise ValueError(f"{assignment.assignment_id}: validated specialist report required")
        grouped[assignment.skill_name].append(assignment)
    if not grouped:
        raise ValueError("at least one validated specialist report required")
    reports, identities = [], {}
    for assignments in grouped.values():
        assignments = sorted(assignments, key=lambda a: a.assignment_id)
        values = []
        for assignment in assignments:
            report = SpecialistReport.model_validate(assignment.report)
            mapping = {
                identifier: identifier + "--" + assignment.assignment_id[5:13]
                if len(assignments) > 1
                else identifier
                for identifier in assignment.findings
            }
            identities[assignment.assignment_id] = mapping
            if len(assignments) > 1:
                raw = report.model_dump(mode="json")

                def namespace(value, mapping=mapping):
                    if isinstance(value, dict):
                        return {
                            mapping.get(k, k): (
                                mapping.get(v, v)
                                if k == "finding_id" and isinstance(v, str)
                                else namespace(v)
                            )
                            for k, v in value.items()
                        }
                    if isinstance(value, list):
                        return [namespace(v) for v in value]
                    return value

                raw = namespace(raw)
                raw["unresolved_items"] = [
                    assignment.assignment_id + ": " + item for item in raw["unresolved_items"]
                ]
                for item in raw["data_overviews"]:
                    item["overview_id"] += "." + assignment.assignment_id[5:13]
                report = SpecialistReport.model_validate(raw)
            values.append(report)
        first = values[0]
        audits = [r.omission_audit for r in values if r.omission_audit]
        omission = OmissionAuditResult(
            covered_candidate_ids=list(
                dict.fromkeys(i for a in audits for i in a.covered_candidate_ids)
            ),
            uncovered_candidates=[c for a in audits for c in a.uncovered_candidates],
            material_candidate_ids=list(
                dict.fromkeys(i for a in audits for i in a.material_candidate_ids)
            ),
            candidate_dispositions=[d for a in audits for d in a.candidate_dispositions],
            material_omission_exists=any(a.material_omission_exists for a in audits),
            rescue_required=any(a.rescue_required for a in audits),
            rescue_used=any(a.rescue_used for a in audits),
            unresolved_disclosures=[d for a in audits for d in a.unresolved_disclosures],
        )
        reports.append(
            first.model_copy(
                update={
                    "scope": "; ".join(r.scope for r in values),
                    "sources_reviewed": sorted({s for r in values for s in r.sources_reviewed}),
                    "analysis_performed": list(
                        dict.fromkeys(a for r in values for a in r.analysis_performed)
                    ),
                    "findings": [f for r in values for f in r.findings],
                    "data_overviews": [o for r in values for o in r.data_overviews],
                    "unresolved_items": [u for r in values for u in r.unresolved_items],
                    "verification_history": {
                        k: v for r in values for k, v in r.verification_history.items()
                    },
                    "overall_conclusion": "\n".join(r.overall_conclusion for r in values),
                    "omission_audit": omission,
                }
            )
        )
    return sorted(reports, key=lambda r: r.domain.value), identities


def report_projection(reports: list[SpecialistReport]) -> list[dict]:
    """Retain every claim, locator and disclosure; omit bulky verification process history."""
    values = []
    for report in reports:
        raw = report.model_dump(mode="json", exclude={"verification_history", "data_overviews"})
        raw["projection_omitted_fields"] = [
            "verification_history",
            "data_overviews",
            "evidence.quote",
        ]
        for finding in raw["findings"]:
            for reference in [*finding["evidence"], *finding["counter_evidence"]]:
                reference.pop("quote", None)
        values.append(raw)
    return values
