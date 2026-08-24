"""Completed-run archive validation through the public run-bundle seam."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from data_agent.review.application.review_service import ReviewService
from data_agent.review.application.run_bundle import (
    RunBundleError,
    load_completed_run,
    load_resume_context,
    load_run_context,
    write_run_context,
)
from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.reports import FinalReport, SpecialistReport
from data_agent.review.domain.review import ReviewRun, ReviewTask, RunStatus, SourceCoverage
from data_agent.review.domain.source import DateRange, Source, SourceManifest, SourceType


def _write_completed_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    specialists = run_dir / "specialists"
    specialists.mkdir(exist_ok=True)
    manifest = SourceManifest(
        sources=[
            Source(
                source_id="SRC-1",
                path="risk.csv",
                source_type=SourceType.CSV,
                sha256="a" * 64,
                size_bytes=12,
                candidate_domains=[SpecialistDomain.RISK_METRICS],
            )
        ]
    )
    period = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))
    report = SpecialistReport(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="RISK",
        title="Risk metrics review",
        review_period=period,
        generated_at=datetime.now(UTC),
        scope="Risk material",
        sources_reviewed=["SRC-1"],
        overall_conclusion="Completed.",
    )
    final = FinalReport(
        executive_summary="Completed review.",
        overall_desk_risk_assessment="Controlled.",
    )
    review = ReviewRun(
        run_id="ARCHIVED-RUN",
        status=RunStatus.COMPLETED,
        created_at=datetime.now(UTC),
        source_root="C:/historical/source",
        output_dir="C:/historical/output",
        manifest=manifest,
        coverage=[SourceCoverage(source_id="SRC-1", status="reviewed")],
        tasks=[
            ReviewTask(
                task_id="risk", domain=SpecialistDomain.RISK_METRICS, source_ids=["SRC-1"]
            )
        ],
    )
    (run_dir / "catalog.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    (run_dir / "desk_context.json").write_text(
        DeskContext(
            desk_name="Desk",
            business_description="",
            review_start=period.start,
            review_end=period.end,
        ).model_dump_json(),
        encoding="utf-8",
    )
    (run_dir / "final_report.json").write_text(final.model_dump_json(), encoding="utf-8")
    (run_dir / "final_findings.md").write_text("# Final\n", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(review.model_dump_json(), encoding="utf-8")
    (specialists / "risk_metrics.json").write_text(report.model_dump_json(), encoding="utf-8")
    (specialists / "risk_metrics.md").write_text("# Risk\n", encoding="utf-8")
    (specialists / "risk_metrics.verification.json").write_text(
        json.dumps(
            {
                "initial_candidates": [],
                "verified_findings": [],
                "rejected_findings": [],
                "unresolved_findings": [],
                "verifier_round": 0,
            }
        ),
        encoding="utf-8",
    )


def test_completed_bundle_is_relocatable_and_ignores_stale_specialist_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "renamed-archive"
    _write_completed_run(run_dir)
    (run_dir / "specialists" / "pnl.json").write_text("not json", encoding="utf-8")

    bundle = load_completed_run(run_dir)

    assert bundle.run.run_id == "ARCHIVED-RUN"
    assert list(bundle.specialist_reports) == [SpecialistDomain.RISK_METRICS]
    assert bundle.final_markdown == "# Final\n"


def test_completed_bundle_rejects_unsettled_coverage_before_reading_presentation_inputs(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    _write_completed_run(run_dir)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["coverage"][0]["status"] = "pending"
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RunBundleError, match="coverage"):
        load_completed_run(run_dir)


def test_completed_bundle_rejects_missing_corrupt_and_mismatched_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_completed_run(run_dir)
    (run_dir / "final_findings.md").unlink()
    with pytest.raises(RunBundleError, match="artifact_missing"):
        load_completed_run(run_dir)

    _write_completed_run(run_dir)
    (run_dir / "catalog.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(RunBundleError, match="artifact_invalid_json"):
        load_completed_run(run_dir)

    _write_completed_run(run_dir)
    catalog = json.loads((run_dir / "catalog.json").read_text(encoding="utf-8"))
    catalog["sources"][0]["sha256"] = "b" * 64
    (run_dir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(RunBundleError, match="catalog_manifest_mismatch"):
        load_completed_run(run_dir)

    _write_completed_run(run_dir)
    verification_path = run_dir / "specialists" / "risk_metrics.verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["verified_findings"] = [{"finding_id": "BROKEN"}]
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    with pytest.raises(RunBundleError, match="artifact_invalid_schema"):
        load_completed_run(run_dir)


def test_completed_bundle_rejects_task_source_and_approved_evidence_mismatches(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    _write_completed_run(run_dir)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["tasks"][0]["source_ids"] = []
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RunBundleError, match="specialist_sources_mismatch"):
        load_completed_run(run_dir)

    _write_completed_run(run_dir)
    final = json.loads((run_dir / "final_report.json").read_text(encoding="utf-8"))
    final["key_findings"] = [
        {
            "final_id": "KF-1",
            "title": "Unsupported output citation",
            "severity": "medium",
            "confidence": 0.8,
            "statement": "This must not be admitted to the reviewed output set.",
            "derived_from": ["FIND-1"],
            "evidence": [{"locator": "source://unapproved.csv#rows=1:1"}],
        }
    ]
    (run_dir / "final_report.json").write_text(json.dumps(final), encoding="utf-8")
    with pytest.raises(RunBundleError, match="approved_evidence_invalid"):
        load_completed_run(run_dir)


def test_run_context_round_trip_is_atomic_and_versioned(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    run_dir = tmp_path / "run"
    desk = DeskContext(
        desk_name="Desk",
        business_description="",
        review_start=date(2025, 1, 1),
        review_end=date(2025, 1, 31),
    )
    written = write_run_context(
        run_dir,
        run_id="RUN-1",
        source_root=source,
        desk_template=desk,
        review_period=DateRange(start=desk.review_start, end=desk.review_end),
    )

    assert load_run_context(run_dir) == written
    assert not list(run_dir.glob(".run_context.json.*.tmp"))

    raw = json.loads((run_dir / "run_context.json").read_text(encoding="utf-8"))
    raw["schema_version"] = 2
    (run_dir / "run_context.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(RunBundleError, match="artifact_invalid_schema"):
        load_run_context(run_dir)


def test_interrupted_resume_requires_context_and_matching_checkpoint_thread(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with pytest.raises(RunBundleError, match="run_context_missing"):
        load_resume_context(run_dir)

    source = tmp_path / "source"
    source.mkdir()
    desk = DeskContext(
        desk_name="Desk",
        business_description="",
        review_start=date(2025, 1, 1),
        review_end=date(2025, 1, 31),
    )
    write_run_context(
        run_dir,
        run_id="RUN-1",
        source_root=source,
        desk_template=desk,
        review_period=DateRange(start=desk.review_start, end=desk.review_end),
    )
    with sqlite3.connect(run_dir / "checkpoints.sqlite") as connection:
        connection.execute("CREATE TABLE checkpoints (thread_id TEXT NOT NULL)")
        connection.execute("INSERT INTO checkpoints (thread_id) VALUES ('OTHER')")
    with pytest.raises(RunBundleError, match="checkpoint_thread_mismatch"):
        load_resume_context(run_dir)


def test_interrupted_resume_rejects_checkpoint_state_that_disagrees_with_context(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    source = tmp_path / "source"
    source.mkdir()
    desk = DeskContext(
        desk_name="Desk",
        business_description="",
        review_start=date(2025, 1, 1),
        review_end=date(2025, 1, 31),
    )
    context = write_run_context(
        run_dir,
        run_id="RUN-1",
        source_root=source,
        desk_template=desk,
        review_period=DateRange(start=desk.review_start, end=desk.review_end),
    )
    with SqliteSaver.from_conn_string(str(run_dir / "checkpoints.sqlite")) as saver:
        saver.put(
            {"configurable": {"thread_id": "RUN-1", "checkpoint_ns": ""}},
            {
                "v": 1,
                "id": "checkpoint-1",
                "ts": datetime.now(UTC).isoformat(),
                "channel_values": {
                    "run_id": "OTHER-RUN",
                    "source_root": context.source_root,
                    "output_dir": context.output_dir,
                },
            },
            {"source": "input", "step": 0, "writes": {}},
            {},
        )

    with pytest.raises(RunBundleError, match="checkpoint_context_mismatch"):
        load_resume_context(run_dir)


def test_completed_resume_uses_validated_bundle_without_a_checkpoint_or_model_call(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "relocated-legacy-completed"
    _write_completed_run(run_dir)

    def forbidden_provider(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("completed resume must not invoke a model")

    result = ReviewService(llm_provider=forbidden_provider).resume(run_dir)

    assert result["status"] == "completed"
    assert result["run_id"] == "ARCHIVED-RUN"


def test_completed_resume_treats_optional_inputs_as_consistency_checks(tmp_path: Path) -> None:
    run_dir = tmp_path / "completed"
    _write_completed_run(run_dir)
    source = tmp_path / "source"
    source.mkdir()
    desk = DeskContext(
        desk_name="Desk",
        business_description="",
        review_start=date(2025, 1, 1),
        review_end=date(2025, 1, 31),
    )
    write_run_context(
        run_dir,
        run_id="ARCHIVED-RUN",
        source_root=source,
        desk_template=desk,
        review_period=DateRange(start=desk.review_start, end=desk.review_end),
    )

    with pytest.raises(RunBundleError, match="resume_source_mismatch"):
        ReviewService().resume(run_dir, source=tmp_path / "other-source")
    with pytest.raises(RunBundleError, match="resume_period_mismatch"):
        ReviewService().resume(
            run_dir,
            review_period=DateRange(start=date(2025, 2, 1), end=date(2025, 2, 28)),
        )


