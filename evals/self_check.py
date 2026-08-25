"""Credential-free smoke check for the evaluation harness.

Run with ``uv run python -m evals.self_check``.  The temporary run bundle is
created outside the repository and is removed automatically.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.metrics import evaluate_run


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def main() -> None:
    gold = {
        "case_id": "self-check",
        "expected": {
            "required_findings": [{"finding_id": "TP", "severity": "medium"}],
            "forbidden_findings": [{"finding_id": "FP"}],
            "contradictions": [{"finding_id": "TP", "challenge_type": "causality"}],
            "verifier_rescue": ["TP"],
            "revision_required": ["TP"],
            "omission_candidates": [{"candidate_id": "OM", "required_disposition": "finding"}],
        },
    }
    with TemporaryDirectory(prefix="adversarial-eval-") as temporary:
        run = Path(temporary)
        _write(
            run / "final_report.json",
            {
                "key_findings": [
                    {"final_id": "TP", "severity": "medium"},
                    {"final_id": "FP", "severity": "high", "verifier_status": "passed"},
                ]
            },
        )
        _write(
            run / "specialists" / "sample.verification.json",
            {
                "verifier_round": 2,
                "initial_candidates": [{"finding_id": "TP", "verifier_status": "revise"}],
                "verification_history": [
                    {"finding_id": "TP", "round_number": 1, "decision": "revise"},
                    {"finding_id": "TP", "round_number": 2, "decision": "pass"},
                ],
                "adversarial_cases": [
                    {
                        "finding_id": "TP",
                        "challenges": [
                            {
                                "challenge_type": "causality",
                                "status": "fail",
                                "explanation": "Attribution is not present in the source.",
                            }
                        ],
                    }
                ],
                "omission_audit": {
                    "rescue_used": True,
                    "candidate_dispositions": [{"candidate_id": "OM", "disposition": "finding"}],
                },
            },
        )
        telemetry = run / "telemetry" / "llm_usage.jsonl"
        telemetry.parent.mkdir(parents=True, exist_ok=True)
        telemetry.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "event": "llm_start",
                            "run_id": "a",
                            "node": "adversarial_research",
                            "tier": "low_cost",
                        }
                    ),
                    json.dumps(
                        {
                            "event": "llm_end",
                            "run_id": "a",
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                            "duration_seconds": 1.25,
                            "tool_calls": 3,
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )
        result = evaluate_run(run, gold)
        assert result.finding_precision == 0.5
        assert result.unsupported_pass_rate == 0.5
        assert result.true_positive_preservation == 1.0
        assert result.contradiction_recall == 1.0
        assert result.verifier_rescue == 1.0
        assert result.omission_rescue == 1.0
        assert result.revision_success == 1.0
        assert result.severity_calibration == 1.0
        assert result.average_rounds == 2.0
        assert result.adversarial_tool_calls_per_finding == 1.5
        assert result.tier_token_totals["low_cost"]["total_tokens"] == 15
        assert result.latency_seconds == 1.25
    print("adversarial evaluation self-check passed")


if __name__ == "__main__":
    main()
