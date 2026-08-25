"""Offline runner for the compact adversarial evaluation suite.

The runner evaluates completed run directories only.  It discovers case
fixtures and gold manifests under ``evals/cases`` and pairs each case with a
run directory supplied by the caller.  No provider, source tree, checkpoint,
or network access is required, making this safe for CI and pre-merge checks.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.metrics import EvaluationMetrics, aggregate_metrics, evaluate_run


@dataclass(frozen=True)
class CaseDefinition:
    """An evaluation-only fixture plus its sealed expected-outcome manifest."""

    case_id: str
    scenario: str
    case_dir: Path
    fixture: Mapping[str, Any]
    gold: Mapping[str, Any]


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def load_case(case_dir: str | Path) -> CaseDefinition:
    """Load one ``fixture.json`` and ``gold_manifest.json`` pair."""

    root = Path(case_dir)
    fixture_path = root / "fixture.json"
    if not fixture_path.is_file():
        fixture_path = root / "case.json"
    if not fixture_path.is_file():
        raise FileNotFoundError(f"missing fixture.json in {root}")
    gold_path = root / "gold_manifest.json"
    if not gold_path.is_file():
        raise FileNotFoundError(f"missing gold_manifest.json in {root}")
    fixture = _read_json(fixture_path)
    gold = _read_json(gold_path)
    case_id = str(fixture.get("case_id", gold.get("case_id", root.name)))
    scenario = str(fixture.get("scenario", fixture.get("name", case_id)))
    if gold.get("case_id", case_id) != case_id:
        raise ValueError(
            f"case ID mismatch in {root}: fixture={case_id!r}, gold={gold.get('case_id')!r}"
        )
    return CaseDefinition(
        case_id=case_id,
        scenario=scenario,
        case_dir=root,
        fixture=fixture,
        gold=gold,
    )


def discover_cases(cases_root: str | Path) -> list[CaseDefinition]:
    """Discover all numbered adversarial cases, sorted by case ID."""

    root = Path(cases_root)
    cases = []
    for path in sorted(root.glob("case_*")):
        if path.is_dir() and (path / "gold_manifest.json").is_file():
            cases.append(load_case(path))
    return cases


def evaluate_case(case: CaseDefinition, run_dir: str | Path) -> EvaluationMetrics:
    """Evaluate one completed run against one case's isolated gold."""

    return evaluate_run(run_dir, case.gold, case_id=case.case_id)


def run_suite(
    runs_root: str | Path,
    *,
    cases_root: str | Path | None = None,
    run_map: Mapping[str, str | Path] | None = None,
    require_all: bool = False,
) -> dict[str, Any]:
    """Evaluate available completed runs and return the JSON report."""

    root = Path(cases_root) if cases_root is not None else Path(__file__).resolve().parent / "cases"
    suite = AdversarialSuite(root)
    return suite.report(suite.evaluate(runs_root, run_map=run_map, require_all=require_all))


class AdversarialSuite:
    """Discover, score, and serialize offline adversarial evaluation runs."""

    def __init__(self, cases_root: str | Path) -> None:
        self.cases_root = Path(cases_root)
        self.cases = tuple(discover_cases(self.cases_root))

    def evaluate(
        self,
        runs_root: str | Path,
        *,
        run_map: Mapping[str, str | Path] | None = None,
        require_all: bool = False,
    ) -> list[EvaluationMetrics]:
        """Score available runs without creating output directories.

        ``run_map`` can point case IDs to arbitrary completed run directories.
        Otherwise ``runs_root/<case_id>`` and ``runs_root/<case_id>/latest``
        are tried.  Missing runs are skipped unless ``require_all`` is true.
        """

        root = Path(runs_root)
        results: list[EvaluationMetrics] = []
        missing: list[str] = []
        for case in self.cases:
            configured = run_map.get(case.case_id) if run_map else None
            candidates = [Path(configured)] if configured else [root / case.case_id]
            if not configured:
                candidates.append(root / case.case_id / "latest")
            run_dir = next((candidate for candidate in candidates if candidate.is_dir()), None)
            if run_dir is None:
                missing.append(case.case_id)
                continue
            results.append(evaluate_case(case, run_dir))
        if require_all and missing:
            raise FileNotFoundError("missing completed runs: " + ", ".join(missing))
        return results

    @staticmethod
    def report(results: list[EvaluationMetrics]) -> dict[str, Any]:
        """Return JSON-serializable per-case and aggregate metrics."""

        return {
            "schema_version": 1,
            "cases": [result.to_dict() for result in results],
            "aggregate": aggregate_metrics(results),
        }

    @classmethod
    def from_default_location(cls) -> AdversarialSuite:
        return cls(Path(__file__).resolve().parent / "cases")


def _main() -> int:
    parser = argparse.ArgumentParser(description="Score completed adversarial review runs offline")
    parser.add_argument(
        "--cases-root",
        type=Path,
        default=Path(__file__).resolve().parent / "cases",
        help="directory containing case_02..case_10 fixtures",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        required=True,
        help="directory containing completed run directories by case ID",
    )
    parser.add_argument("--output", type=Path, help="write a JSON report; stdout is always emitted")
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()
    suite = AdversarialSuite(args.cases_root)
    report = suite.report(suite.evaluate(args.runs_root, require_all=args.require_all))
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
