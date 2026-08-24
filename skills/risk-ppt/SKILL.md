---
name: risk-ppt
description: >
  Controlled presentation capability for the Trading Desk Risk Analysis Agent.
  Converts completed reviewed Markdown and JSON into an evidence-linked,
  financial-editorial, editable PowerPoint through report-core semantic SVGs.
  Use only for decks derived from completed risk-review outputs; never for raw
  source material.
metadata:
  kind: presentation
  license: "MIT"
  upstream: "https://github.com/hugohe3/ppt-master"
  upstream_version: "4.8.0"
  upstream_commit: "10ec12e518615dde0b303d60c140a330f0a92703"
  copyright: "Copyright (c) 2025-2026 Hugo He (upstream); derivative per MIT"
  default_template: report-core
  default_style: operating-review
  planning_references:
    - references/operating-review.md
    - references/data-journalism.md
    - references/modes/briefing.md
    - references/modes/pyramid.md
  authoring_references:
    - references/semantic-svg.md
    - references/canvas-formats.md
    - references/shared-standards-core.md
    - references/preset-shape-vocabulary.md
  validator_entrypoint: scripts/runtime.py:check_svg_deck
  renderer_entrypoint: scripts/runtime.py:render_svg_previews
  converter_entrypoint: scripts/runtime.py:convert_svg_deck
---

# Risk-PPT Skill

A curated, offline-safe derivative of
[hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) (MIT, v4.8.0),
adapted for the Trading Desk Risk Analysis Agent. It turns completed reviewed
outputs into an editable financial operating-review deck. Read
`ATTRIBUTION.md` for the exact upstream inventory and exclusions.

## Controlled workflow

1. **Plan** with deepseek-v4-pro from `final_report.json` and validated
   `specialists/*.json` only. Exclude duplicate Markdown and verification artifacts.
   Use a balanced typed corpus that keeps overview metadata and statistics but omits
   large point arrays. Use concise finding-led titles, explicit evidence and
   limitations, analytical density, and a complete technical appendix. Never create a
   finding, comparison, metric, overview ID, or locator.
2. **Author** with deepseek-v4-flash as flat 1280x720 semantic SVG. The
   selected `report-core` prototype is a visual scaffold, not a reusable
   PowerPoint master. Follow its white/red/navy editorial system, short title
   rules, square-edged analytical fields, and evidence-led page hierarchy.
   Prefer its text-led layouts when prose carries the reviewed evidence most
   faithfully. When a visual is justified, use one visual with an interpretive
   commentary rail on the selected left or right side. Use stable top-level
   group IDs, `data-pptx-bounds`, one scan path, and reserved header/footer
   regions. Never copy third-party corporate marks.
3. **Control traceability** in code. The runtime replaces the visible evidence
   footer and writes every approved finding ID and `source://` locator to
   speaker notes; model text is never trusted for that obligation.
   Code also hydrates every selected overview ID with the exact report-backed data,
   overlays deterministic editable chart/table geometry, and records the overview ID
   and canonical data fingerprint in speaker notes.
4. **Validate and render** the complete SVG deck through the vendored upstream
   checker plus the project offline guard. A source-fingerprinted quality
   report must pass before conversion. Render every accepted SVG to a
   1280x720 PNG for visual review.
5. **Convert the exact SVGs** to editable DrawingML in flat mode through the
   vendored upstream core. Do not redraw the plan. Keep animations,
   transitions, narration, audio, images, external assets, native enhancement,
   and native chart/table replacement disabled.
6. **Verify** the exported slide text and deterministic SVG/PPTX reports with
   deepseek-v4-pro. Fail explicitly after the bounded graph exhausts revision.

## Entry rules

- Input must be a completed run containing `final_findings.md`; only reviewed
  Markdown and JSON outputs may be opened.
- Every active specialist requires one primary overview page before the closing slide.
  Available overview data cannot be replaced by prose. Older runs without overview data
  receive an explicit rerun-required data-quality page.
- Raw sources are out of scope. The PPT pipeline cannot access or cite them
  except through approved `source://` locator strings copied from reports.
- All LLM calls use the project's DeepSeek factory: pro for planning and deck
  verification, flash for SVG authoring.
- `report-core` is the only supported template and layout vocabulary.
- References, assets, and executable entrypoints are validated as relative,
  repository-contained, version-controlled paths. Review inputs never select
  executable code.
- All PPT artifacts remain beneath the completed run directory.

## Progressive routing

- For storyline, prioritization, page density, and decision flow, load the
  `planning_references` declared in front matter. `briefing` governs compact
  operating reviews; `pyramid` governs finding-led titles and answer-first
  structure.
- For SVG markup and conversion safety, load the declared
  `authoring_references` plus the chosen prototype and `design_spec.md` under
  `assets/templates/report-core/`.
- Load `references/visual-review.md` only when inspecting rendered previews.
- `references/svg-effects.md` documents upstream effects, but this project
  permits only the basic flat subset accepted by `scripts/runtime.py`.

## References

- `references/operating-review.md` - evidence-led recurring-review method
- `references/data-journalism.md` - restrained financial visual language
- `references/modes/briefing.md` - compact briefing flow
- `references/modes/pyramid.md` - answer-first argument structure
- `references/semantic-svg.md` - SVG authoring contract
- `references/canvas-formats.md` - canvas/viewBox conventions
- `references/shared-standards-core.md` - shared presentation standards
- `references/visual-review.md` - visual review checklist
- `references/preset-shape-vocabulary.md` - allowed shape vocabulary
- `assets/templates/report-core/` - project-owned 18-layout SVG template workspace
- `vendor/ppt-master/UPSTREAM_MANIFEST.json` - copied-file inventory and checksums
