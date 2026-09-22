"""Deterministic handling of bounded independent lead objections."""

from __future__ import annotations

from collections.abc import Iterable

from data_agent.review.domain.lead_outputs import MAX_LEAD_FEEDBACK
from data_agent.review.domain.reports import CrossSourceCluster, FinalReport
from data_agent.review.domain.verification import LeadChallenge, ObjectionMateriality

_MATERIALITY_ORDER = {
    ObjectionMateriality.INFORMATIONAL: 0,
    ObjectionMateriality.LOW: 1,
    ObjectionMateriality.MEDIUM: 2,
    ObjectionMateriality.HIGH: 3,
    ObjectionMateriality.CRITICAL: 4,
}
_MATERIAL_OBJECTION_LEVEL = _MATERIALITY_ORDER[ObjectionMateriality.MEDIUM]


def _challenge_feedback(challenges: Iterable[LeadChallenge]) -> str:
    """Render concise, concrete structured objections for lead revision."""
    parts: list[str] = []
    for challenge in challenges:
        targets = ", ".join(challenge.affected_finding_ids) or "report-wide"
        explanation = challenge.explanation.strip() or "No explanation was supplied."
        resolution = (
            f" Proposed resolution: {challenge.proposed_resolution.strip()}"
            if challenge.proposed_resolution and challenge.proposed_resolution.strip()
            else ""
        )
        parts.append(
            f"[{challenge.materiality.value}] {challenge.challenge_type.value} "
            f"(affected: {targets}): {explanation}{resolution}"
        )
    return "\n".join(parts)[:MAX_LEAD_FEEDBACK]


def _challenge_disclosure(challenge: LeadChallenge, *, suppressed: bool) -> str:
    targets = ", ".join(challenge.affected_finding_ids) or "report-wide"
    action = "suppressed" if suppressed else "disclosed"
    explanation = challenge.explanation.strip() or "No explanation was supplied."
    return (
        f"Lead verification {action} {challenge.materiality.value} "
        f"{challenge.challenge_type.value} objection (affected: {targets}): {explanation}"
    )


def _rebuild_synthesis_after_suppression(
    clusters: list[dict],
    report: FinalReport,
    suppressed_ids: set[str],
) -> list[dict]:
    """Remove challenged conclusions and rebuild dependent cluster/index data.

    The lead model is not allowed to leave a stale cluster or evidence index
    referring to a semantically suppressed final finding.  Deterministic
    clusters are filtered in parallel because the final hard gate validates
    their relationship to the parent state.
    """
    suppressed_locators = {
        reference.locator
        for finding in report.key_findings
        if finding.final_id in suppressed_ids
        for reference in finding.evidence
    }
    retained_final_locators = {
        reference.locator
        for finding in report.key_findings
        if finding.final_id not in suppressed_ids
        for reference in finding.evidence
    }
    filtered_state_clusters: list[dict] = []
    state_cluster_ids: set[str] = set()
    for raw_cluster in clusters:
        try:
            cluster = CrossSourceCluster.model_validate(raw_cluster)
        except ValueError:
            # validate_final_report already reports malformed deterministic
            # clusters before semantic review.  Keep malformed data untouched
            # here so that the hard gate remains authoritative if encountered.
            continue
        cluster.findings = [
            finding_id for finding_id in cluster.findings if finding_id not in suppressed_ids
        ]
        if not cluster.findings:
            continue
        cluster.supporting_evidence = [
            reference
            for reference in cluster.supporting_evidence
            if reference.locator not in suppressed_locators
            or reference.locator in retained_final_locators
        ]
        state_cluster_ids.add(cluster.cluster_id)
        filtered_state_clusters.append(cluster.model_dump(mode="json"))

    retained_clusters: list[CrossSourceCluster] = []
    for cluster in report.cross_source_findings:
        cluster.findings = [
            finding_id for finding_id in cluster.findings if finding_id not in suppressed_ids
        ]
        if not cluster.findings or cluster.cluster_id not in state_cluster_ids:
            continue
        cluster.supporting_evidence = [
            reference
            for reference in cluster.supporting_evidence
            if reference.locator not in suppressed_locators
            or reference.locator in retained_final_locators
        ]
        retained_clusters.append(cluster)
    retained_cluster_ids = {cluster.cluster_id for cluster in retained_clusters}

    retained_findings = []
    for finding in report.key_findings:
        if finding.final_id in suppressed_ids:
            continue
        finding.cross_source_cluster_ids = [
            cluster_id
            for cluster_id in finding.cross_source_cluster_ids
            if cluster_id in retained_cluster_ids
        ]
        retained_findings.append(finding)

    report.key_findings = retained_findings
    report.cross_source_findings = retained_clusters

    evidence_index = []
    seen_locators: set[str] = set()
    for reference in [
        *(reference for finding in report.key_findings for reference in finding.evidence),
        *(reference for cluster in retained_clusters for reference in cluster.supporting_evidence),
    ]:
        if reference.locator in seen_locators:
            continue
        seen_locators.add(reference.locator)
        evidence_index.append(reference)
    report.evidence_index = evidence_index
    return filtered_state_clusters


def _apply_final_round_challenges(
    clusters: list[dict],
    report: FinalReport,
    challenges: list[LeadChallenge],
) -> tuple[FinalReport, list[dict], set[str], list[str]]:
    """Apply final-round materiality rules to structured semantic objections.

    High/critical report-wide or ambiguously targeted objections fail closed.
    Medium-or-higher targeted objections suppress only the explicitly named
    final findings.  Informational/low objections are retained as disclosures.
    """
    report_ids = {finding.final_id for finding in report.key_findings}
    suppressed_ids: set[str] = set()
    blockers: list[str] = []
    disclosures: list[str] = []

    for challenge in challenges:
        targets = list(dict.fromkeys(challenge.affected_finding_ids))
        unknown_targets = sorted(set(targets) - report_ids)
        materiality = _MATERIALITY_ORDER[challenge.materiality]
        if materiality < _MATERIAL_OBJECTION_LEVEL:
            disclosures.append(_challenge_disclosure(challenge, suppressed=False))
            continue

        # A material objection without a precise final-finding target cannot
        # be safely repaired by deleting arbitrary synthesis.  We fail closed
        # for medium as well as high/critical; high/critical is called out in
        # the user-facing reason because it is the strongest safety boundary.
        if not targets or unknown_targets:
            qualifier = "report-wide" if not targets else f"unknown targets {unknown_targets}"
            blockers.append(
                f"{challenge.materiality.value} {challenge.challenge_type.value} objection "
                f"is ambiguously targeted ({qualifier})"
            )
            continue

        if materiality >= _MATERIAL_OBJECTION_LEVEL:
            suppressed_ids.update(targets)
            disclosures.append(_challenge_disclosure(challenge, suppressed=True))

    if blockers:
        return report, list(clusters), suppressed_ids, blockers

    filtered_clusters = _rebuild_synthesis_after_suppression(clusters, report, suppressed_ids)
    report.unresolved_questions = [*report.unresolved_questions, *disclosures]
    return report, filtered_clusters, suppressed_ids, []


def _needs_semantic_revision(challenges: Iterable[LeadChallenge]) -> bool:
    return any(
        _MATERIALITY_ORDER[challenge.materiality] >= _MATERIAL_OBJECTION_LEVEL
        for challenge in challenges
    )
