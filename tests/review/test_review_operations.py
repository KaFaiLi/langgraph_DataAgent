"""Graph-independent operations preserve deterministic and evidence behavior."""

from __future__ import annotations

import subprocess
import sys
from datetime import date

import pytest

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.source import DateRange
from data_agent.skills.review import discover_skills, load_analysis_runner
from data_agent.tools.review_operations import (
    AnalysisRequest,
    OmissionRequest,
    ReportRequest,
    analyze_reports,
    audit_candidates,
    construct_report,
    prepare_analysis,
)


def test_capability_imports_do_not_import_workflows_or_discover_skills():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
import data_agent.tools.review_operations
import data_agent.skills.registry as registry
import data_agent.skills.runtime
assert registry._build_registry.cache_info().currsize == 0
assert registry._build_source_domain_owners.cache_info().currsize == 0
assert "data_agent.review.service" not in sys.modules
assert "data_agent.review.orchestration.graph" not in sys.modules
assert "data_agent.review.orchestration.specialist.graph" not in sys.modules
""",
        ],
        check=True,
    )


def test_typed_analysis_and_reports_preserve_skill_results(tool_ctx):
    definition = next(skill for skill in discover_skills() if skill.name == "risk-metrics")
    paths = tuple(
        source.path
        for source in tool_ctx.manifest.sources
        if SpecialistDomain.RISK_METRICS in source.candidate_domains
    )
    runner = load_analysis_runner(definition)
    results = prepare_analysis(AnalysisRequest(tool_ctx, paths), runner)
    originals = list(runner(tool_ctx, list(paths)))
    assert len(results) == len(originals) > 0
    for result, original in zip(results, originals, strict=True):
        assert result.summary == original.summary
        assert result.tables == original.tables
        assert result.overviews == original.overviews
        assert len(result.flag_candidates) == len(original.flag_candidates)
        assert all(candidate.get("candidate_id") for candidate in result.flag_candidates)
    assert results == prepare_analysis(AnalysisRequest(tool_ctx, paths), runner)
    audit = audit_candidates(OmissionRequest(tool_ctx, paths, results, rescue_used=True))
    report = construct_report(
        ReportRequest(
            context=tool_ctx,
            domain=definition.domain,
            domain_label=definition.label,
            report_id=definition.report_id,
            period=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)),
            scope="Typed capability test",
            source_ids=[s.source_id for s in tool_ctx.manifest.sources if s.path in paths],
            analyses=results,
            omission_audit=audit,
        )
    )
    assert report.analysis_performed == [result.name for result in results]
    assert report.data_overviews == [
        overview for result in results for overview in result.overviews
    ]
    assert report.omission_audit == audit
    assert analyze_reports([report]).clusters == []


def test_analysis_rejects_paths_outside_manifest_before_calling_runner(tool_ctx):
    called = False

    def runner(*args):
        nonlocal called
        called = True
        return []

    with pytest.raises(ValueError, match="outside"):
        prepare_analysis(AnalysisRequest(tool_ctx, ("../private.csv",)), runner)
    assert not called
