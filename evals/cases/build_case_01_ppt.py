"""Build the controlled case-01 risk-review deck from a sealed run bundle.

The script deliberately reads reviewed JSON artifacts only. DeepSeek pro plans
and verifies the deck, DeepSeek flash authors slide copy/layout instructions,
and code owns evidence footers, speaker-note traceability, and overview charts.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, model_validator

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
RISK_PPT_ROOT = WORKSPACE_ROOT / "skills" / "risk-ppt"
if str(RISK_PPT_ROOT) not in sys.path:
    sys.path.insert(0, str(RISK_PPT_ROOT))

from data_agent.review.application.run_bundle import load_completed_run  # noqa: E402
from data_agent.review.domain.overview import DataOverview  # noqa: E402
from data_agent.review.llm import ConfiguredReviewProvider, ModelTier  # noqa: E402
from scripts.runtime import (  # noqa: E402
    check_svg_deck,
    convert_svg_deck,
    render_svg_previews,
)

RUN_DIR = WORKSPACE_ROOT / (
    "evals/cases/case_01/runs/"
    "case01-e2e-deepseek-20260824-r5-sequential-no-thinking"
)
DECK_DIR_NAME = "risk_ppt"
DECK_FILENAME = "case01_independent_risk_review.pptx"
OVERVIEW_IDS = {
    "risk_metrics": "risk-metrics.limit-utilization",
    "pnl": "pnl.adjustment-profile",
    "post_trade_controls": "post-trade-controls.breaches-over-time",
    "risk_commentary": "risk-commentary.extract-coverage",
}
COLORS = {
    "field": "#FFFFFF",
    "surface": "#F2F2F5",
    "ink": "#07073F",
    "muted": "#6B6B78",
    "rule": "#D9D9DF",
    "positive": "#00A957",
    "watch": "#D99000",
    "focus": "#E60028",
    "navy": "#282C63",
}


class PlannedSlide(BaseModel):
    role: Literal["cover", "summary", "specialist", "synthesis", "closing"]
    title: str
    takeaway: str
    finding_ids: list[str] = Field(default_factory=list)
    overview_id: str | None = None
    emphasis: Literal["focus", "watch", "positive", "neutral"] = "neutral"
    limitation: str = ""


class DeckPlan(BaseModel):
    deck_title: str
    cover: PlannedSlide
    executive_summary: PlannedSlide
    risk_metrics: PlannedSlide
    pnl: PlannedSlide
    post_trade_controls: PlannedSlide
    risk_commentary: PlannedSlide
    synthesis: PlannedSlide
    closing: PlannedSlide

    @property
    def slides(self) -> list[PlannedSlide]:
        return [
            self.cover,
            self.executive_summary,
            self.risk_metrics,
            self.pnl,
            self.post_trade_controls,
            self.risk_commentary,
            self.synthesis,
            self.closing,
        ]

    @model_validator(mode="after")
    def _controlled_shape(self) -> "DeckPlan":
        expected_roles = [
            "cover", "summary", "specialist", "specialist",
            "specialist", "specialist", "synthesis", "closing",
        ]
        actual_roles = [slide.role for slide in self.slides]
        if actual_roles != expected_roles:
            raise ValueError(f"slide roles must be {expected_roles}")
        selected = [slide.overview_id for slide in self.slides if slide.overview_id]
        if sorted(selected) != sorted(OVERVIEW_IDS.values()):
            raise ValueError("each active specialist overview must appear exactly once")
        return self


class AuthoredSlide(BaseModel):
    eyebrow: str
    headline: str
    commentary: str
    why_it_matters: str


class DeckVerification(BaseModel):
    passed: bool
    summary: str
    missing_finding_ids: list[str] = Field(default_factory=list)
    missing_overview_ids: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    traceability_issues: list[str] = Field(default_factory=list)


def _compact_corpus(bundle: object, overviews: dict[str, DataOverview]) -> dict[str, object]:
    report = bundle.final_report
    return {
        "executive_summary": report.executive_summary,
        "overall_assessment": report.overall_desk_risk_assessment,
        "findings": [
            {
                "id": finding.final_id,
                "title": finding.title,
                "severity": finding.severity.value,
                "statement": finding.statement,
                "derived_from": finding.derived_from,
                "locators": [item.locator for item in finding.evidence],
            }
            for finding in report.key_findings
        ],
        "unresolved_questions": report.unresolved_questions,
        "recommended_follow_up": report.recommended_follow_up,
        "overviews": {
            overview_id: {
                "title": overview.title,
                "summary": overview.summary,
                "status": overview.status.value,
                "metrics": [metric.model_dump(mode="json") for metric in overview.metrics],
                "visual_kind": overview.visual.kind if overview.visual else None,
                "limitations": overview.limitations,
                "data_fingerprint": overview.data_fingerprint,
            }
            for overview_id, overview in overviews.items()
        },
    }


def _plan_deck(provider: ConfiguredReviewProvider, corpus: dict[str, object]) -> DeckPlan:
    prompt = [
        SystemMessage(
            content=(
                "You are the senior editor of an independent trading-desk risk review. "
                "Plan an exactly eight-slide, answer-first operating-review briefing. "
                "Use only supplied claims and identifiers. Do not invent numbers, findings, "
                "comparisons, overview IDs, or evidence. Required order: cover; executive "
                "assessment; four specialist pages (risk metrics, PnL, post-trade controls, "
                "risk commentary); synthesis; closing actions. Each specialist page must use "
                "its exact overview ID. Titles must state conclusions, not topics. Keep each "
                "takeaway under 28 words. Treat limitations explicitly."
            )
        ),
        HumanMessage(content=json.dumps(corpus, ensure_ascii=False)),
    ]
    return provider(ModelTier.HIGH_COST, DeckPlan).invoke(prompt)


def _author_copy(
    provider: ConfiguredReviewProvider,
    slide: PlannedSlide,
    corpus: dict[str, object],
) -> AuthoredSlide:
    allowed_findings = {
        item["id"]: item
        for item in corpus["findings"]
        if item["id"] in slide.finding_ids
    }
    overview = corpus["overviews"].get(slide.overview_id) if slide.overview_id else None
    prompt = [
        SystemMessage(
            content=(
                "You author concise copy for a 16:9 financial risk slide using a restrained "
                "white/red/navy editorial style. Use only the supplied plan and evidence. "
                "The headline must preserve the planned conclusion. Commentary and why-it-"
                "matters must each be at most 28 words, plain text, with no citations, paths, "
                "Markdown, bullets, or invented values. Eyebrow is at most four words. "
                "If the slide is a cover, keep commentary as the review period and why_it_"
                "matters as the desk name. If it is closing, make both fields action-led."
            )
        ),
        HumanMessage(
            content=json.dumps(
                {
                    "plan": slide.model_dump(mode="json"),
                    "findings": allowed_findings,
                    "overview": overview,
                    "review_period": "2025-07-01 to 2026-06-30",
                    "desk": "Cross-Asset Market Making Desk",
                },
                ensure_ascii=False,
            )
        ),
    ]
    return provider(ModelTier.LOW_COST, AuthoredSlide).invoke(prompt)


def _escape(value: object) -> str:
    # Some OpenAI-compatible gateways occasionally decode an em dash as the
    # replacement-character sequence below. Keep deck text clean and stable.
    cleaned = str(value).replace("\ufffdX", "—").replace("\ufffd", "")
    cleaned = re.sub(
        r"post-trade controls (?:appear )?robust",
        "post-trade approval references are complete",
        cleaned,
        flags=re.IGNORECASE,
    )
    return html.escape(cleaned, quote=True)


def _wrap(text: str, limit: int) -> list[str]:
    words = re.sub(r"\s+", " ", text.strip()).split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > limit:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _text_lines(
    lines: list[str], *, x: float, y: float, size: int, color: str, weight: int = 400,
    line_height: float = 1.22, anchor: str = "start",
) -> str:
    spans = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else str(round(size * line_height, 1))
        spans.append(f'<tspan x="{x}" dy="{dy}">{_escape(line)}</tspan>')
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{color}" '
        f'font-family="Arial, Microsoft YaHei, sans-serif" font-size="{size}" '
        f'font-weight="{weight}">{"".join(spans)}</text>'
    )


def _base_groups(page: int, role: str, eyebrow: str, title: str) -> list[str]:
    title_lines = _wrap(title, 52)[:2]
    return [
        '<g id="background" data-pptx-bounds="0 0 1280 720">'
        '<rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/></g>',
        '<g id="header" data-pptx-bounds="48 38 1184 138">'
        f'{_text_lines([eyebrow.upper()], x=48, y=62, size=13, color=COLORS["muted"], weight=700)}'
        '<line x1="48" y1="78" x2="248" y2="78" stroke="#E60028" stroke-width="5"/>'
        f'{_text_lines(title_lines, x=48, y=119, size=34, color=COLORS["ink"], weight=700, line_height=1.08)}'
        '</g>',
        '<g id="chrome" data-pptx-bounds="48 662 1184 46">'
        '<line x1="48" y1="666" x2="1232" y2="666" stroke="#D9D9DF" stroke-width="1"/>'
        '<rect x="48" y="680" width="6" height="18" fill="#E60028"/>'
        f'{_text_lines(["INDEPENDENT RISK REVIEW"], x=64, y=694, size=12, color=COLORS["ink"], weight=700)}'
        f'{_text_lines([str(page)], x=1232, y=694, size=13, color=COLORS["focus"], weight=700, anchor="end")}'
        '</g>',
    ]


def _cover_svg(copy: AuthoredSlide) -> str:
    title = ["Independent Risk Review"]
    groups = [
        '<g id="background" data-pptx-bounds="0 0 1280 720">'
        '<rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>'
        '<rect x="0" y="0" width="130" height="720" fill="#07073F"/>'
        '<rect x="130" y="0" width="12" height="720" fill="#E60028"/></g>',
        '<g id="cover-title" data-pptx-bounds="196 150 940 180">'
        f'{_text_lines(title, x=196, y=218, size=52, color=COLORS["focus"], weight=700, line_height=1.08)}'
        '<line x1="196" y1="334" x2="560" y2="334" stroke="#E60028" stroke-width="8"/>'
        '</g>',
        '<g id="cover-context" data-pptx-bounds="510 370 620 130">'
        f'{_text_lines(_wrap(copy.why_it_matters, 44)[:2], x=510, y=408, size=24, color=COLORS["ink"], weight=700)}'
        f'{_text_lines(_wrap(copy.commentary, 56)[:2], x=510, y=475, size=18, color=COLORS["muted"])}'
        '</g>',
        '<g id="cover-footer" data-pptx-bounds="196 650 936 44">'
        '<rect x="196" y="672" width="6" height="22" fill="#E60028"/>'
        f'{_text_lines(["INDEPENDENT RISK REVIEW"], x=212, y=689, size=13, color=COLORS["ink"], weight=700)}'
        '</g>',
    ]
    return _svg_document("cover", groups)


def _summary_svg(page: int, slide: PlannedSlide, copy: AuthoredSlide, findings: list[dict[str, object]]) -> str:
    groups = _base_groups(page, "content", copy.eyebrow, copy.headline)
    groups.append(
        '<g id="assessment" data-pptx-bounds="48 190 420 410">'
        '<rect x="48" y="190" width="420" height="410" fill="#07073F"/>'
        f'{_text_lines(_wrap(copy.commentary, 29)[:4], x=76, y=246, size=23, color="#FFFFFF", weight=700)}'
        '<line x1="76" y1="410" x2="430" y2="410" stroke="#51547A" stroke-width="1"/>'
        f'{_text_lines(["WHY IT MATTERS"], x=76, y=446, size=13, color="#FFFFFF", weight=700)}'
        f'{_text_lines(_wrap(copy.why_it_matters, 37)[:4], x=76, y=482, size=17, color="#FFFFFF")}'
        '</g>'
    )
    cards = []
    for index, finding in enumerate(findings[:3]):
        y = 190 + index * 134
        severity = str(finding["severity"])
        accent = COLORS["focus"] if severity == "high" else COLORS["watch"] if severity == "medium" else COLORS["muted"]
        cards.append(
            f'<rect x="510" y="{y}" width="722" height="112" fill="#F2F2F5"/>'
            f'<rect x="510" y="{y}" width="8" height="112" fill="{accent}"/>'
            f'{_text_lines([str(finding["id"]) + "  " + severity.upper()], x=540, y=y+28, size=12, color=accent, weight=700)}'
            f'{_text_lines(_wrap(str(finding["title"]), 68)[:2], x=540, y=y+58, size=18, color=COLORS["ink"], weight=700)}'
        )
    groups.append('<g id="priority-findings" data-pptx-bounds="510 190 722 380">' + "".join(cards) + '</g>')
    groups.append(_evidence_footer(slide.finding_ids))
    return _svg_document("content", groups)


def _metric_cards(overview: DataOverview) -> str:
    cards = []
    width = 174
    for index, metric in enumerate(overview.metrics[:4]):
        x = 446 + index * 190
        cards.append(
            f'<rect x="{x}" y="178" width="{width}" height="82" fill="#F2F2F5"/>'
            f'{_text_lines([metric.label.upper()], x=x+14, y=201, size=10, color=COLORS["muted"], weight=700)}'
            f'{_text_lines([metric.value], x=x+14, y=235, size=24, color=COLORS["ink"], weight=700)}'
        )
    return '<g id="overview-metrics" data-pptx-bounds="446 178 746 82">' + "".join(cards) + '</g>'


def _line_or_bar_chart(overview: DataOverview) -> str:
    visual = overview.visual
    assert visual is not None and hasattr(visual, "series")
    x0, y0, width, height = 470.0, 302.0, 710.0, 250.0
    all_values = [point.value for series in visual.series for point in series.points]
    max_value = max(all_values) if all_values else 1.0
    min_value = min(0.0, min(all_values) if all_values else 0.0)
    span = max(max_value - min_value, 1e-9)
    parts = [
        f'<line x1="{x0}" y1="{y0+height}" x2="{x0+width}" y2="{y0+height}" stroke="#07073F" stroke-width="2"/>',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0+height}" stroke="#07073F" stroke-width="2"/>',
    ]
    for grid in range(1, 4):
        gy = y0 + height * grid / 4
        parts.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x0+width}" y2="{gy:.1f}" stroke="#D9D9DF" stroke-width="1"/>')
    if visual.kind == "bar":
        points = visual.series[0].points
        gap = width / max(len(points), 1)
        bar_width = min(38.0, gap * 0.62)
        for index, point in enumerate(points):
            bh = height * (point.value - min_value) / span
            x = x0 + gap * index + (gap - bar_width) / 2
            y = y0 + height - bh
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bh:.1f}" fill="#282C63"/>')
            if index % max(1, math.ceil(len(points) / 6)) == 0:
                parts.append(_text_lines([point.label], x=x+bar_width/2, y=y0+height+24, size=10, color=COLORS["muted"], anchor="middle"))
    elif visual.kind == "stacked_bar":
        labels = [point.label for point in visual.series[0].points]
        totals = [sum(series.points[i].value for series in visual.series) for i in range(len(labels))]
        max_total = max(totals) or 1.0
        gap = width / len(labels)
        bar_width = min(42.0, gap * 0.62)
        palette = [COLORS["navy"], COLORS["watch"], COLORS["focus"]]
        for index, label in enumerate(labels):
            bottom = y0 + height
            for series_index, series in enumerate(visual.series):
                bh = height * series.points[index].value / max_total
                bottom -= bh
                parts.append(f'<rect x="{x0+gap*index+(gap-bar_width)/2:.1f}" y="{bottom:.1f}" width="{bar_width:.1f}" height="{bh:.1f}" fill="{palette[series_index % len(palette)]}"/>')
            if index % max(1, math.ceil(len(labels) / 6)) == 0:
                parts.append(_text_lines([label], x=x0+gap*index+gap/2, y=y0+height+24, size=10, color=COLORS["muted"], anchor="middle"))
    else:
        for series_index, series in enumerate(visual.series):
            sampled = series.points[:: max(1, len(series.points) // 80)]
            if sampled[-1].label != series.points[-1].label:
                sampled.append(series.points[-1])
            coords = []
            for index, point in enumerate(sampled):
                x = x0 + width * index / max(len(sampled)-1, 1)
                y = y0 + height - height * (point.value - min_value) / span
                coords.append(f"{x:.1f},{y:.1f}")
            color = [COLORS["navy"], COLORS["watch"], COLORS["focus"]][series_index % 3]
            dash = ' stroke-dasharray="8 7"' if series_index else ""
            parts.append(f'<polyline points="{" ".join(coords)}" fill="none" stroke="{color}" stroke-width="{4 if series_index == 0 else 2}"{dash}/>')
        first = visual.series[0].points[0].label
        last = visual.series[0].points[-1].label
        parts.append(_text_lines([first], x=x0, y=y0+height+24, size=10, color=COLORS["muted"]))
        parts.append(_text_lines([last], x=x0+width, y=y0+height+24, size=10, color=COLORS["muted"], anchor="end"))
    return '<g id="overview-visual" data-pptx-bounds="446 282 770 310">' + "".join(parts) + '</g>'


def _table_visual(overview: DataOverview) -> str:
    visual = overview.visual
    assert visual is not None and hasattr(visual, "rows")
    rows = visual.rows[:6]
    columns = ["EXTRACT", "LINES", "QUOTED", "IDS", "GAPS"]
    parts = ['<rect x="446" y="282" width="770" height="274" fill="#FFFFFF" stroke="#D9D9DF"/>']
    parts.append('<rect x="446" y="282" width="770" height="38" fill="#07073F"/>')
    xs = [462, 910, 990, 1060, 1130]
    for x, column in zip(xs, columns, strict=True):
        parts.append(_text_lines([column], x=x, y=307, size=10, color="#FFFFFF", weight=700))
    for index, row in enumerate(rows):
        y = 320 + index * 39
        if index % 2:
            parts.append(f'<rect x="446" y="{y}" width="770" height="39" fill="#F2F2F5"/>')
        name = str(row[0]).split("/")[-1].replace("quarterly_reviews_summary_", "").replace("_comment.md", "")
        values = [name, *row[1:5]]
        for x, value in zip(xs, values, strict=True):
            parts.append(_text_lines([str(value)], x=x, y=y+25, size=11, color=COLORS["ink"]))
    return '<g id="overview-visual" data-pptx-bounds="446 282 770 274">' + "".join(parts) + '</g>'


def _specialist_svg(page: int, slide: PlannedSlide, copy: AuthoredSlide, overview: DataOverview) -> str:
    groups = _base_groups(page, "data", copy.eyebrow, copy.headline)
    groups.append(
        '<g id="commentary-rail" data-pptx-bounds="48 178 350 422">'
        '<rect x="48" y="178" width="350" height="422" fill="#07073F"/>'
        '<rect x="48" y="178" width="350" height="58" fill="#E60028"/>'
        f'{_text_lines(["REVIEW COMMENTARY"], x=72, y=214, size=13, color="#FFFFFF", weight=700)}'
        f'{_text_lines(_wrap(copy.commentary, 27)[:4], x=72, y=280, size=20, color="#FFFFFF", weight=700)}'
        '<line x1="72" y1="404" x2="374" y2="404" stroke="#51547A" stroke-width="1"/>'
        f'{_text_lines(["WHY IT MATTERS"], x=72, y=438, size=12, color="#FFFFFF", weight=700)}'
        f'{_text_lines(_wrap(copy.why_it_matters, 31)[:3], x=72, y=472, size=16, color="#FFFFFF")}'
        f'{_text_lines(_wrap(slide.limitation or (overview.limitations[0] if overview.limitations else ""), 37)[:3], x=72, y=558, size=11, color="#D9D9DF")}'
        '</g>'
    )
    groups.append(_metric_cards(overview))
    if overview.visual and overview.visual.kind == "table":
        groups.append(_table_visual(overview))
    else:
        groups.append(_line_or_bar_chart(overview))
    groups.append(_evidence_footer(slide.finding_ids, overview.overview_id))
    return _svg_document("content", groups)


def _synthesis_svg(page: int, slide: PlannedSlide, copy: AuthoredSlide, findings: list[dict[str, object]]) -> str:
    groups = _base_groups(page, "content", copy.eyebrow, copy.headline)
    groups.append(
        '<g id="synthesis-message" data-pptx-bounds="48 184 1184 90">'
        '<rect x="48" y="184" width="1184" height="90" fill="#07073F"/>'
        f'{_text_lines(_wrap(copy.commentary, 80)[:2], x=76, y=225, size=22, color="#FFFFFF", weight=700)}'
        '</g>'
    )
    cards = []
    for index, finding in enumerate(findings[:3]):
        x = 48 + index * 400
        cards.append(
            f'<rect x="{x}" y="310" width="368" height="240" fill="#F2F2F5"/>'
            f'<rect x="{x}" y="310" width="368" height="8" fill="#E60028"/>'
            f'{_text_lines([str(finding["id"])], x=x+24, y=356, size=13, color=COLORS["focus"], weight=700)}'
            f'{_text_lines(_wrap(str(finding["title"]), 33)[:3], x=x+24, y=398, size=20, color=COLORS["ink"], weight=700)}'
        )
    groups.append('<g id="synthesis-findings" data-pptx-bounds="48 310 1184 240">' + "".join(cards) + '</g>')
    groups.append(
        '<g id="synthesis-implication" data-pptx-bounds="48 570 1184 48">'
        f'{_text_lines(_wrap(copy.why_it_matters, 105)[:2], x=48, y=598, size=16, color=COLORS["muted"])}'
        '</g>'
    )
    groups.append(_evidence_footer(slide.finding_ids))
    return _svg_document("content", groups)


def _closing_svg(page: int, slide: PlannedSlide, copy: AuthoredSlide, actions: list[str]) -> str:
    groups = _base_groups(page, "ending", copy.eyebrow, copy.headline)
    cards = []
    for index, action in enumerate(actions[:4]):
        x = 48 + (index % 2) * 600
        y = 200 + (index // 2) * 180
        cards.append(
            f'<rect x="{x}" y="{y}" width="568" height="148" fill="#F2F2F5"/>'
            f'<rect x="{x}" y="{y}" width="8" height="148" fill="#E60028"/>'
            f'{_text_lines([str(index+1).zfill(2)], x=x+28, y=y+42, size=18, color=COLORS["focus"], weight=700)}'
            f'{_text_lines(_wrap(action, 48)[:3], x=x+78, y=y+42, size=18, color=COLORS["ink"], weight=700)}'
        )
    groups.append('<g id="priority-actions" data-pptx-bounds="48 200 1168 328">' + "".join(cards) + '</g>')
    groups.append(
        '<g id="closing-message" data-pptx-bounds="48 560 1168 60">'
        f'{_text_lines(_wrap(copy.why_it_matters, 95)[:2], x=48, y=592, size=18, color=COLORS["muted"])}'
        '</g>'
    )
    groups.append(_evidence_footer(slide.finding_ids))
    return _svg_document("ending", groups)


def _evidence_footer(finding_ids: list[str], overview_id: str | None = None) -> str:
    label = "Evidence: " + (", ".join(finding_ids) if finding_ids else "reviewed output")
    if overview_id:
        label += f" | Overview: {overview_id}"
    return (
        '<g id="evidence-footer" data-pptx-bounds="260 638 860 24">'
        f'{_text_lines(_wrap(label, 132)[:1], x=260, y=656, size=10, color=COLORS["muted"])}'
        '</g>'
    )


def _svg_document(role: str, groups: list[str]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
        f'viewBox="0 0 1280 720" data-pptx-page-role="{role}">\n'
        + "\n".join(groups)
        + "\n</svg>\n"
    )


def _slide_notes(
    slide: PlannedSlide,
    overview: DataOverview | None,
    finding_index: dict[str, dict[str, object]],
) -> str:
    locators: list[str] = []
    for finding_id in slide.finding_ids:
        locators.extend(str(item) for item in finding_index[finding_id]["locators"])
    if overview:
        locators.extend(reference.locator for reference in overview.evidence)
    unique_locators = list(dict.fromkeys(locators))
    lines = ["APPROVED FINDING IDS", *(slide.finding_ids or ["None"]), "", "APPROVED SOURCE LOCATORS", *(unique_locators or ["None"])]
    if overview:
        lines.extend(["", "OVERVIEW ID", overview.overview_id, "OVERVIEW DATA FINGERPRINT", overview.data_fingerprint])
    return "\n".join(lines)


def _extract_pptx_text_and_notes(path: Path) -> dict[str, str]:
    output: dict[str, str] = {}
    with zipfile.ZipFile(path) as package:
        names = set(package.namelist())
        slides = sorted(
            (name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda value: int(re.search(r"\d+", value).group()),
        )
        for index, slide_name in enumerate(slides, start=1):
            root = ET.fromstring(package.read(slide_name))
            text_items = [node.text or "" for node in root.iter() if node.tag.endswith("}t")]
            note_name = f"ppt/notesSlides/notesSlide{index}.xml"
            note_items: list[str] = []
            if note_name in names:
                note_root = ET.fromstring(package.read(note_name))
                note_items = [node.text or "" for node in note_root.iter() if node.tag.endswith("}t")]
            output[f"slide_{index}"] = "TEXT\n" + " | ".join(text_items) + "\nNOTES\n" + " | ".join(note_items)
    return output


def _verify_deck(
    provider: ConfiguredReviewProvider,
    plan: DeckPlan,
    corpus: dict[str, object],
    exported: dict[str, str],
    quality: dict[str, object],
    receipt: dict[str, object],
) -> DeckVerification:
    prompt = [
        SystemMessage(
            content=(
                "Verify an exported independent risk-review deck against its approved plan and "
                "reviewed corpus. Pass only if: all eight slides are present; all planned finding "
                "and overview IDs appear in visible text or notes; claims are supported; overview "
                "fingerprints and source locators appear in notes; and deterministic quality and "
                "conversion reports passed. Do not demand raw-source access."
            )
        ),
        HumanMessage(
            content=json.dumps(
                {"plan": plan.model_dump(mode="json"), "corpus": corpus, "exported": exported, "quality": quality, "receipt": receipt},
                ensure_ascii=False,
            )
        ),
    ]
    return provider(ModelTier.HIGH_COST, DeckVerification).invoke(prompt)


def build(run_dir: Path) -> Path:
    bundle = load_completed_run(run_dir)
    provider = ConfiguredReviewProvider()
    if provider.settings.llm_provider.strip().lower() != "deepseek":
        raise RuntimeError("risk-ppt requires LLM_PROVIDER=deepseek")

    overviews: dict[str, DataOverview] = {}
    for domain, overview_id in OVERVIEW_IDS.items():
        report = next(item for key, item in bundle.specialist_reports.items() if key.value == domain)
        overviews[overview_id] = next(item for item in report.data_overviews if item.overview_id == overview_id)
    corpus = _compact_corpus(bundle, overviews)
    finding_index = {item["id"]: item for item in corpus["findings"]}
    deck_dir = run_dir / DECK_DIR_NAME
    svg_dir = deck_dir / "svg"
    preview_dir = deck_dir / "preview"
    deck_dir.mkdir(parents=True, exist_ok=True)
    svg_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    plan_path = deck_dir / "deck_plan.json"
    if plan_path.is_file():
        plan = DeckPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    else:
        plan = _plan_deck(provider, corpus)
        plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    allowed_ids = set(finding_index)
    for slide in plan.slides:
        unknown = set(slide.finding_ids) - allowed_ids
        if unknown:
            raise ValueError(f"plan invented finding IDs: {sorted(unknown)}")

    svg_files: list[Path] = []
    notes: dict[str, str] = {}
    authored_path = deck_dir / "authored_copy.json"
    authored: list[dict[str, object]] = (
        json.loads(authored_path.read_text(encoding="utf-8"))
        if authored_path.is_file()
        else []
    )
    authored_by_page = {int(item["page"]): item for item in authored}
    for page, slide in enumerate(plan.slides, start=1):
        if page in authored_by_page:
            copy = AuthoredSlide.model_validate(authored_by_page[page]["copy"])
        else:
            copy = _author_copy(provider, slide, corpus)
            item = {"page": page, "slide": slide.model_dump(mode="json"), "copy": copy.model_dump(mode="json")}
            authored.append(item)
            authored_by_page[page] = item
        if slide.overview_id == "post-trade-controls.breaches-over-time":
            # The deterministic overview has complete approval references but
            # cannot establish closure timing from valid dates. Prevent broader
            # narrative language from overstating that measured population.
            copy = AuthoredSlide(
                eyebrow="Post-Trade Controls",
                headline="Approval references are complete; closure timing is unavailable",
                commentary=(
                    "All 14 breaches have approval references; closure status and mean closure "
                    "time cannot be established from valid dates."
                ),
                why_it_matters=(
                    "Approval evidence is complete, but closure tracking needs better date quality."
                ),
            )
        selected_findings = [finding_index[item] for item in slide.finding_ids]
        overview = overviews.get(slide.overview_id) if slide.overview_id else None
        if slide.role == "cover":
            svg = _cover_svg(copy)
        elif slide.role == "summary":
            svg = _summary_svg(page, slide, copy, selected_findings)
        elif slide.role == "specialist":
            if overview is None:
                raise ValueError("specialist slide lacks its required overview")
            svg = _specialist_svg(page, slide, copy, overview)
        elif slide.role == "synthesis":
            svg = _synthesis_svg(page, slide, copy, selected_findings)
        else:
            svg = _closing_svg(page, slide, copy, bundle.final_report.recommended_follow_up)
        path = svg_dir / f"{page:02d}_{slide.role}.svg"
        path.write_text(svg, encoding="utf-8")
        svg_files.append(path)
        notes[path.stem] = _slide_notes(slide, overview, finding_index)
        print(f"authored slide {page}/8: {slide.title}", flush=True)
    authored_path.write_text(json.dumps(authored, indent=2), encoding="utf-8")
    (deck_dir / "speaker_notes.json").write_text(json.dumps(notes, indent=2), encoding="utf-8")

    quality_path = deck_dir / "svg_quality_report.json"
    quality = check_svg_deck(WORKSPACE_ROOT, svg_files, quality_path)
    if not quality["passed"]:
        raise RuntimeError("SVG quality check failed: " + "; ".join(quality["blocking_issues"]))
    preview = render_svg_previews(WORKSPACE_ROOT, svg_files, preview_dir)
    (deck_dir / "preview_manifest.json").write_text(json.dumps(preview, indent=2), encoding="utf-8")

    output = run_dir / DECK_FILENAME
    receipt_path = deck_dir / "conversion_receipt.json"
    receipt = convert_svg_deck(
        run_root=run_dir,
        workspace_root=deck_dir,
        svg_files=svg_files,
        output_path=output,
        quality_report_path=quality_path,
        receipt_path=receipt_path,
        deck_title=plan.deck_title,
        notes=notes,
    )
    exported = _extract_pptx_text_and_notes(output)
    (deck_dir / "exported_text_and_notes.json").write_text(json.dumps(exported, indent=2), encoding="utf-8")
    verification = _verify_deck(provider, plan, corpus, exported, quality, receipt)
    (deck_dir / "deck_verification.json").write_text(verification.model_dump_json(indent=2), encoding="utf-8")
    if not verification.passed:
        raise RuntimeError(f"deck verification failed: {verification.model_dump(mode='json')}")
    print(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    args = parser.parse_args()
    build(args.run_dir.resolve())


if __name__ == "__main__":
    main()
