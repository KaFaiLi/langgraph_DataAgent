---
layout_id: report_core
kind: layout
category: financial-review
summary: An 18-layout, 16:9 editorial system for evidence-led trading-desk risk reviews.
keywords: [risk, financial, editorial, red, navy, evidence, text-led, commentary]
canvas_format: ppt169
canvas_width: 1280
canvas_height: 720
canvas_viewbox: "0 0 1280 720"
replication_mode: standard
native_structure_mode: structured
page_count: 18
page_types:
  - cover
  - section_divider
  - agenda
  - title_content
  - two_content
  - three_block
  - kpi_row
  - chart_insight
  - table_summary
  - process_timeline
  - matrix_2x2
  - appendix
  - closing
  - text_statement
  - text_analysis
  - text_columns
  - viz_commentary_left
  - viz_commentary_right
placeholders:
  01_cover: ["{{TITLE}}", "{{SUBTITLE}}", "{{DATE}}"]
  02_section_divider: ["{{CHAPTER_NUM}}", "{{CHAPTER_TITLE}}", "{{CHAPTER_DESC}}"]
  03_agenda: ["{{PAGE_TITLE}}", "{{ITEM_1}}", "{{ITEM_2}}", "{{ITEM_3}}", "{{ITEM_4}}", "{{ITEM_5}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  04_title_content: ["{{PAGE_TITLE}}", "{{CONTENT_AREA}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  05_two_content: ["{{PAGE_TITLE}}", "{{LEFT_CONTENT}}", "{{RIGHT_CONTENT}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  06_three_block: ["{{PAGE_TITLE}}", "{{BLOCK_1}}", "{{BLOCK_2}}", "{{BLOCK_3}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  07_kpi_row: ["{{PAGE_TITLE}}", "{{KPI_1}}", "{{KPI_2}}", "{{KPI_3}}", "{{KPI_4}}", "{{CONTENT_AREA}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  08_chart_insight: ["{{PAGE_TITLE}}", "{{KEY_MESSAGE}}", "{{SOURCE}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  09_table_summary: ["{{PAGE_TITLE}}", "{{KEY_MESSAGE}}", "{{SOURCE}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  10_process_timeline: ["{{PAGE_TITLE}}", "{{STEP_1}}", "{{STEP_2}}", "{{STEP_3}}", "{{STEP_4}}", "{{KEY_MESSAGE}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  11_matrix_2x2: ["{{PAGE_TITLE}}", "{{Y_AXIS}}", "{{X_AXIS}}", "{{QUADRANT_1}}", "{{QUADRANT_2}}", "{{QUADRANT_3}}", "{{QUADRANT_4}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  12_appendix: ["{{PAGE_TITLE}}", "{{LEFT_CONTENT}}", "{{RIGHT_CONTENT}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  13_closing: ["{{CLOSING_MESSAGE}}", "{{CONTACT_LINE}}"]
  14_text_statement: ["{{PAGE_TITLE}}", "{{LEAD_STATEMENT}}", "{{SUPPORTING_TEXT}}", "{{KEY_MESSAGE}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  15_text_analysis: ["{{PAGE_TITLE}}", "{{OBSERVATION}}", "{{EVIDENCE}}", "{{IMPLICATION}}", "{{LIMITATION}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  16_text_columns: ["{{PAGE_TITLE}}", "{{LEFT_HEADING}}", "{{LEFT_CONTENT}}", "{{RIGHT_HEADING}}", "{{RIGHT_CONTENT}}", "{{KEY_MESSAGE}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  17_viz_commentary_left: ["{{PAGE_TITLE}}", "{{KEY_MESSAGE}}", "{{COMMENTARY}}", "{{LIMITATION}}", "{{VISUAL}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
  18_viz_commentary_right: ["{{PAGE_TITLE}}", "{{VISUAL}}", "{{KEY_MESSAGE}}", "{{COMMENTARY}}", "{{LIMITATION}}", "{{FOOTER_NOTE}}", "{{PAGE_NUM}}"]
---

# Report Core Design Specification

## Design provenance and boundary

This project-owned revision adapts the visual grammar of the supplied 2019 debt-investor
presentation: decisive red headings, deep-navy analytical text, short title underlines,
full-red numbered section breaks, square-edged financial tables and charts, and a compact
identity/footer rail. It does not copy the source deck's company marks, slogans, content,
or proprietary identity. The supplied PDF is a design reference only and is not a runtime
dependency.

The communication job is: by the end, a risk committee or accountable desk leader should
understand which reviewed findings are material, what evidence supports them, what remains
unresolved, and which follow-up decision is required.

## Visual system

| Role | Value | Use |
|---|---|---|
| Field | `#FFFFFF` | Default reading plane |
| Signal red | `#E60028` | Conclusions, title underline, adverse focus, section planes |
| Deep navy | `#07073F` | Body copy, chart structure, decision text |
| Mid navy | `#282C63` | Secondary analytical fields |
| Teal | `#31575A` | One contrasting evidence field, never status by itself |
| Surface | `#F2F2F5` | Table headers, comparison bands, quiet grouping |
| Rule | `#D9D9DF` | Grids, dividers, baselines |
| On plan | `#00A957` | Confirmed pass/compliant status, paired with a label or mark |
| Watch | `#D99000` | Confirmed watch status, paired with a label or mark |

- Use Arial throughout, with tabular figures when available.
- Render content-page titles in signal red, bold, and upper-case. Place a 6 px red rule
  directly below the title; its length follows the title zone, not the page width.
- Prefer open editorial composition, rules, columns, and bands. Avoid rounded cards,
  dashboard chrome, gradients, shadows, and decorative containers.
- Red is semantic. Do not color a neutral fact red merely for variety.
- Use square corners. The only circles are chart marks, timeline nodes, or explicit status
  symbols.

## Structural contract

The roster uses three background masters:

1. `report_core_cover_master` - white, minimal identity plane for cover and closing.
2. `report_core_divider_master` - full signal-red section plane without content chrome.
3. `report_core_content_master` - white analytical plane with a bottom rule and the
   `INDEPENDENT RISK REVIEW` identity rail.

Content pages reserve y=80..650 for the title and evidence field. The deterministic runtime
owns y=654..720 for reviewed finding IDs, the primary `source://` locator, and page number.
The prototype footer slots remain structural PowerPoint placeholders, but model-authored
slides must not create their own evidence footer.

Titles normally occupy `48 82 1184 64`. Analytical content begins at y=178. Dense appendix
copy may use 15 px; normal body copy uses 18-21 px; compact labels use 13-15 px. Headline
metrics use 30-44 px. Shorten copy before reducing these sizes.

## Text-led composition

Text is a primary evidence format, not leftover content. A text-led page should state one
conclusion, then let prose carry the reasoning in a deliberate reading order. Use short
paragraphs, sentence-length bullets, strong section labels, white space, and rules. Do not
turn each paragraph into a card.

- `text_statement` gives one conclusion visual priority, then supports it with concise
  evidence and one decision implication.
- `text_analysis` separates observation, evidence, implication, and limitation so the
  audience can distinguish fact from interpretation.
- `text_columns` supports two linked narrative threads or a longer assessment that still
  benefits from an explicit closing implication.

## One visual with commentary

`viz_commentary_left` and `viz_commentary_right` are mirrored layouts. Each contains exactly
one visual field and one commentary rail. The visual may be a chart, table, matrix, or simple
process view only when the reviewed reports contain enough evidence for it. The commentary
must say what the visual shows, why it matters, and what material limitation remains. Choose
the side that makes the deck flow; alternate sides when consecutive visual pages would
otherwise repeat the same silhouette.

## Layout roster

| SVG | Layout | Intended use |
|---|---|---|
| `01_cover.svg` | Cover | Minimal review title, period, and date on white |
| `02_section_divider.svg` | Section Divider | Full-red numbered transition for a genuine narrative break |
| `03_agenda.svg` | Agenda | Five numbered questions or review sections separated by rules |
| `04_title_content.svg` | Title and Content | One evidence field with a red left rail |
| `05_two_content.svg` | Two Content | Deep-navy narrative rail at left, detailed evidence at right |
| `06_three_block.svg` | Three Block | Three high-value executive highlights on red, teal, and navy fields |
| `07_kpi_row.svg` | KPI Row | Four comparable metrics in vertical columns plus one conclusion band |
| `08_chart_insight.svg` | Chart and Insight | Dominant chart at left, decision implication at right |
| `09_table_summary.svg` | Table and Summary | Financial table at left, concise exception summary at right |
| `10_process_timeline.svg` | Process Timeline | Four dated or owned follow-up steps on one axis |
| `11_matrix_2x2.svg` | Two-by-Two Matrix | Four risk/decision quadrants with explicit axes |
| `12_appendix.svg` | Appendix | Dense methodology, definitions, limitations, and source detail |
| `13_closing.svg` | Closing | Minimal decision or owned next action on white |
| `14_text_statement.svg` | Text Statement | Lead conclusion, supporting prose, and one decision implication |
| `15_text_analysis.svg` | Text Analysis | Observation, evidence, implication, and limitation in one reading path |
| `16_text_columns.svg` | Text Columns | Two balanced narrative columns plus an implication band |
| `17_viz_commentary_left.svg` | Visual with Left Commentary | Commentary rail at left and one dominant visual at right |
| `18_viz_commentary_right.svg` | Visual with Right Commentary | One dominant visual at left and commentary rail at right |

## Content rules

- A page title states the reviewed conclusion, not merely the topic.
- Place the result, evidence, implication, and limitation on the same page when possible.
- Prefer a text-led layout when prose is more faithful than a chart or diagram.
- Use `three_block` for executive highlights, not for an inventory of equal-weight facts.
- Use `kpi_row` only for metrics with a consistent comparison basis and visible units.
- Use `two_content` when narrative context is necessary to interpret a detailed evidence
  field; the navy rail must remain shorter than the evidence side.
- Use a `viz_commentary` layout for exactly one visual. Never add a decorative second chart,
  and never leave the visual unexplained.
- Use red section dividers sparingly. A compact deck normally needs at most two.
- The closing page resolves the opening with an explicit decision or owned action; never
  finish on a generic thank-you message.
