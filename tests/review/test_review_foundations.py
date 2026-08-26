from __future__ import annotations

from datetime import date
from pathlib import Path

from data_agent.config import Settings
from data_agent.review import ReviewRequest, ReviewResult, ReviewStatus


def test_review_models_have_stable_public_contract(tmp_path: Path) -> None:
    request = ReviewRequest(
        source_root=tmp_path / "sources",
        output_dir=tmp_path / "run",
        run_id="RUN-001",
        review_start=date(2025, 1, 1),
        review_end=date(2025, 12, 31),
        desk_context={"desk_name": "Test Desk"},
    )

    assert request.review_period.start == date(2025, 1, 1)
    assert request.review_period.end == date(2025, 12, 31)
    assert (
        ReviewResult(status=ReviewStatus.RUNNING, run_id="RUN-001").status is ReviewStatus.RUNNING
    )


def test_socgenai_review_models_have_role_defaults_and_env_overrides() -> None:
    defaults = Settings(_env_file=None)
    assert defaults.socgenai_low_cost_model == "gpt-5-mini"
    assert defaults.socgenai_high_cost_model == "gpt-5.4"
    assert defaults.socgenai_max_completion_tokens == 128_000

    overridden = Settings(
        _env_file=None,
        socgenai_low_cost_model="internal-low",
        socgenai_high_cost_model="internal-high",
        socgenai_max_completion_tokens=64_000,
    )
    assert overridden.socgenai_low_cost_model == "internal-low"
    assert overridden.socgenai_high_cost_model == "internal-high"
    assert overridden.socgenai_max_completion_tokens == 64_000


def test_deepseek_review_models_have_cost_tier_defaults_and_env_overrides() -> None:
    defaults = Settings(_env_file=None)
    assert defaults.deepseek_low_cost_model == "deepseek-v4-flash"
    assert defaults.deepseek_high_cost_model == "deepseek-v4-pro"
    assert defaults.deepseek_max_tokens == 384_000

    overridden = Settings(
        _env_file=None,
        deepseek_low_cost_model="deepseek-low",
        deepseek_high_cost_model="deepseek-high",
        deepseek_max_tokens=192_000,
    )
    assert overridden.deepseek_low_cost_model == "deepseek-low"
    assert overridden.deepseek_high_cost_model == "deepseek-high"
    assert overridden.deepseek_max_tokens == 192_000
