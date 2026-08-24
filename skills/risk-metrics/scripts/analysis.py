"""Public entrypoint for the deterministic risk-metrics review skill."""

from __future__ import annotations

if __package__:
    from .risk_metrics_analysis.runner import run_analysis
else:  # pragma: no cover - supports direct trusted-script inspection in tests/tools.
    from pathlib import Path

    from data_agent.skills.review import _load_module

    run_analysis = _load_module(
        Path(__file__).with_name("risk_metrics_analysis") / "runner.py",
        Path(__file__).parents[1],
    ).run_analysis

__all__ = ["run_analysis"]
