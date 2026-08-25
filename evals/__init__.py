"""Evaluation-only helpers for the adversarial review suite.

The package intentionally has no dependency on :mod:`data_agent`.  Evaluation
fixtures and completed run bundles are an external contract, so the evaluator
can score historical runs even while the production review models evolve.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evals.adversarial_suite import (
        AdversarialSuite,
        CaseDefinition,
        evaluate_case,
        load_case,
    )
    from evals.metrics import EvaluationMetrics, evaluate_run

__all__ = [
    "AdversarialSuite",
    "CaseDefinition",
    "EvaluationMetrics",
    "evaluate_case",
    "evaluate_run",
    "load_case",
]


def __getattr__(name: str) -> object:
    if name in {"AdversarialSuite", "CaseDefinition", "evaluate_case", "load_case"}:
        from evals import adversarial_suite

        return getattr(adversarial_suite, name)
    if name in {"EvaluationMetrics", "evaluate_run"}:
        from evals import metrics

        return getattr(metrics, name)
    raise AttributeError(name)
