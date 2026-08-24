# Attribution

This skill is a curated derivative of
[`hugohe3/ppt-master`](https://github.com/hugohe3/ppt-master) (MIT License,
Copyright (c) 2025-2026 Hugo He), version 4.8.0 at commit
`10ec12e518615dde0b303d60c140a330f0a92703`. The upstream MIT license is
reproduced verbatim in `LICENSE`.

## Retained from upstream without modification

- The SVG authoring, canvas, shared-standard, visual-review, preset-shape, and
  SVG-effects references under `references/`.
- `references/data-journalism.md`, `references/operating-review.md`,
  `references/modes/briefing.md`, and `references/modes/pyramid.md`.
- The files below `vendor/ppt-master/`, which are the import and resource
  closure needed by `svg_quality.checker.SVGQualityChecker` and
  `svg_to_pptx.pptx_package.builder.create_pptx_with_native_svg`. The exact
  source-relative path and SHA-256 of every copied file is recorded in
  `vendor/ppt-master/UPSTREAM_MANIFEST.json`.
- `vendor/ppt-master/scripts/pptx_shapes/data/` includes the upstream Open XML
  SDK and Apache notices for its bundled preset-shape resources.

## Project-owned or adapted files

- `SKILL.md` is rewritten for this repository's bounded, reviewed-output-only
  presentation workflow.
- `scripts/runtime.py` is a narrow project-owned adapter around the unmodified
  upstream checker and flat DrawingML converter. It adds run containment,
  strict offline SVG rules, source fingerprints, 1280x720 PNG rendering,
  stale-report rejection, and hard-disabled optional features. Because this is
  an attributed MIT derivative rather than the complete official distribution,
  the adapter supplies minimal in-process canvas/console shims and does not
  invoke upstream's official-distribution CLI identity gate.
- `assets/templates/report-core/template.yaml` is a project-specific trusted
  runtime manifest derived from the upstream report-core structural vocabulary
  and the repository's operating-review requirements.
- The 18 SVG prototypes and `design_spec.md` under
  `assets/templates/report-core/` are project-owned rewrites. They retain the
  compatible report-core layout IDs while adapting the visual grammar of the
  user-supplied debt-investor PDF. They copy no company marks or report content,
  and the source PDF is not a runtime dependency.
- Production orchestration, evidence injection, and PPTX validation live under
  `src/risk_analysis_agent/ppt/` and are not upstream files.

## Deliberately excluded or disabled capabilities

The project does not expose upstream TTS/narration/audio, video, web search,
web-to-markdown, AI image generation/search, native PPT enhancement,
image-to-PPT reconstruction, the interactive SVG editor, native chart/table
replacement, formula outlining, shape booleans, animations, or transitions.

Some unmodified animation, transition, narration, and native-object support
modules are present solely because the upstream converter imports them eagerly.
The project adapter never enables those capabilities, rejects their SVG
markers, and verifies that generated packages contain no media or external
payloads.

## PPTX conversion

The exact validated SVGs are converted to editable slide-local DrawingML by
the pinned upstream converter in `pptx_structure="flat"` mode. Optional
XlsxWriter, skia-pathops, and uharfbuzz paths are not used: images, native
chart/table replacement, formula outlines, shape booleans, animation,
transitions, and narration are rejected or disabled by the project adapter.
