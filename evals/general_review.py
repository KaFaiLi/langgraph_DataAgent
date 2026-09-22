"""Separate, gold-free outcome/omission and usage audit of a live general-agent review.

This evaluator consumes reviewed artifacts and telemetry only. It reports structural
support and explicit omissions, not semantic precision against a hidden answer key.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from data_agent.review.agent_service import AgentReviewService
from data_agent.review.application.sealed_bundle import load_sealed_bundle


def evaluate(run_dir: Path) -> dict:
    status = AgentReviewService().status(run_dir)
    if status.status != "completed" or status.bundle_path is None:
        raise ValueError(
            f"evaluation requires a validated completed run: {status.failure_reason or status.status}"
        )
    bundle = load_sealed_bundle(status.bundle_path)
    domains = {}
    for domain, report in bundle.specialist_reports.items():
        audit = report.omission_audit
        verification = json.loads(
            (status.bundle_path / "specialists" / f"{domain.value}.verification.json").read_text()
        )
        outcomes = Counter(f.verifier_status.value for f in report.findings)
        outcomes["rejected"] = len(verification.get("rejected_findings", []))
        domains[domain.value] = {
            "finding_outcomes": dict(outcomes),
            "overview_count": len(report.data_overviews),
            "sources_reviewed": report.sources_reviewed,
            "covered_candidates": len(audit.covered_candidate_ids) if audit else 0,
            "uncovered_candidates": len(audit.uncovered_candidates) if audit else 0,
            "unresolved_omission_disclosures": audit.unresolved_disclosures if audit else [],
            "verification_rounds": sum(len(h) for h in report.verification_history.values()),
            "findings": [
                {
                    "id": f.finding_id,
                    "title": f.title,
                    "claim": f.claim,
                    "status": f.verifier_status.value,
                    "severity": f.severity.value,
                }
                for f in report.findings
            ],
        }
    usage = defaultdict(lambda: Counter())
    role_usage = defaultdict(lambda: Counter())
    trace_roles = {}
    trace_path = run_dir / "telemetry" / "execution_trace.jsonl"
    if trace_path.is_file():
        for line in trace_path.read_text().splitlines():
            event = json.loads(line)
            if event.get("event_type") == "model_started":
                trace_roles[event["callback_run_id"]] = event.get("agent_name") or "unknown"
    calls = {}
    durations = []
    usage_path = run_dir / "telemetry" / "llm_usage.jsonl"
    if usage_path.is_file():
        for line in usage_path.read_text().splitlines():
            item = json.loads(line)
            if item.get("event") == "llm_start":
                calls[item["run_id"]] = item
            if item.get("event") == "llm_end":
                start = calls.get(item["run_id"], {})
                model = start.get("model_id", "unknown")
                role = start.get("agent_name") or trace_roles.get(item["run_id"], "unknown")
                usage[model]["calls"] += 1
                role_usage[role]["calls"] += 1
                for key in ("input_tokens", "output_tokens", "total_tokens"):
                    usage[model][key] += item.get(key) or 0
                    role_usage[role][key] += item.get(key) or 0
                if item.get("duration_seconds") is not None:
                    durations.append(item["duration_seconds"])
    verified = {
        f.finding_id: f
        for report in bundle.specialist_reports.values()
        for f in report.verified_findings()
    }
    support_failures = [
        f.final_id
        for f in bundle.final_report.key_findings
        if not set(f.derived_from).intersection(verified)
    ]
    omissions_disclosed = all(
        not d["uncovered_candidates"] or d["unresolved_omission_disclosures"]
        for d in domains.values()
    )
    return {
        "schema_version": 1,
        "run_id": status.run_id,
        "status": status.status,
        "evaluation_type": "live synthetic review; gold-free structural and manual quality assessment",
        "scope": {"sources": len(bundle.catalog.sources), "domains": sorted(domains)},
        "domains": domains,
        "final_findings": len(bundle.final_report.key_findings),
        "unsupported_final_findings": support_failures,
        "unresolved_questions": len(bundle.final_report.unresolved_questions),
        "all_omissions_disclosed": omissions_disclosed,
        "coverage_complete": all(c.status != "pending" for c in bundle.run.coverage),
        "budget_used": status.budget_used,
        "usage_by_model": dict(usage),
        "usage_by_role": dict(role_usage),
        "sum_model_latency_seconds": round(sum(durations), 3),
        "cost_measurement": "provider-reported token usage; monetary cost not supplied by the provider",
        "limitations": [
            "Structural support is not a semantic precision score.",
            "Synthetic fixtures are small; results do not establish real-desk quality.",
            "Unresolved findings require human/source follow-up and are not passes.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.run_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "domains": result["scope"]["domains"],
                "final_findings": result["final_findings"],
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
