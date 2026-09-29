# Page layout and charts

Type: prototype
Status: resolved
Assignee: Tony Trinh
Blocked by: 09, 10, 11, 13
Parent: ../map.md

## Question

"Page data contract" fixed what the Report page reads. Now decide what it shows, section by section, against the outline in "Report outline".

- For each subsection: table, chart, or prose only. Which chart form (e.g. latency-vs-accuracy scatter, per-stage bar, overlap split).
- Per-query drill-down: where it sits, what it lists (query, known Recipe, rank per config, top-20 titles), how it filters.
- Header: run folder, `git_commit`, `query_set_sha256` from the bundle's `meta`.
- Light/dark: reuse `useTheme.ts`.
- Is a rough prototype of one or two sections worth it before the spec? Call the Skill tool with "prototype" and "dataviz".

## Progress (2026-09-28, paused)

Waiting on the human's pick. Not resolved.

- Layout draft: [research/page-layout-draft.md](../research/page-layout-draft.md). Settled so far: strategies shown all 3 always (rows/facets), drill-down is an appendix after §7, hand-drawn SVG.
- Prototype: branch `prototype/report-layout` (commit `13e88b9`), `ui/src/prototype/`. Run `npm run dev` in `ui/`, open `/prototype/report`, switch with `?lat=A|B|C&drill=A|B|C`. Data: `.venv/bin/python ui/src/prototype/build_prototype_data.py`.
  - §4.3: A scatter, B aligned panels, C headline step. Drill-down: A expanding table, B list + detail, C rank strips.
  - Agent's lean: §4.3 C over A; drill-down A plus a rank-strip column.
- Finding: Sparse `#2f6bd6` and Hybrid `#6a4fd6` fail CVD all-pairs (deutan ΔE 1.3, normal 8.8). Charts need marker shape + direct label per config. Fusion baseline colour `#c2571a` light / `#ec8a4f` dark passes adjacent checks. Existing dark tokens sit above the lightness band.

## Answer

Picked by the human (2026-09-29): **§4.3 B, aligned panels** and **drill-down B, list + detail**. Prototype revised to match, branch `prototype/report-layout` (commit `b7d67c9`, on top of `13e88b9`); data now from the 3 Timing repeats and the Report run's `significance.json`. The rest of [research/page-layout-draft.md](../research/page-layout-draft.md) stands as the section-by-section layout.

§4.3, aligned panels:
- One row per config × Chunking strategy, grouped by config. Fixed columns: strategy label, R@5 panel, R@5 value, latency panel, latency value. Values right-aligned in their own column, never placed after a bar.
- Both panels have tick labels and faint gridlines. R@5 50–80%; latency log 10–3000 ms.
- R@5: tick plus shaded 95% CI. Latency: tick at median p50 of the Timing repeats, shaded bar p50 min–max, thin line to p95.
- Hybrid stage bar below, same label column width as the panels.
- "Show table": grouped by strategy; the highest-R@5 row per strategy highlighted (ties all marked), with a one-line key. The bundle carries the flag, since the page computes nothing ("Page data contract").

Drill-down, list + detail:
- One labelled filter panel, sticky: Chunking strategy (3-way toggle), Show (chips with plain names and counts per strategy, full sentence on hover), Word overlap (Any / High / Low, one-line meaning), query search, "Only hand-rewritten queries". Footer "N of M queries" and "Clear filters". State in the URL.
- Chip names: Sparse beat Dense, Dense beat Sparse, Reranking moved it up, Reranking moved it down, Every config missed. Bucket keys never show in the UI.
- List: header row (Id / Query / Hybrid), mono id column, selected row marked, empty state.
- Detail: query text, then a label/value list (id, known Recipe, word overlap with high/low, hand-rewritten, patterns as pills); rank table for all 3 strategies with the current one highlighted; the four top-20 lists 2×2.

Copy rules for the whole page:
- Full plain sentences. No fragment captions ("Same rows, two scales"), no "Claim:" labels, no filler.
- Numbers in prose come from bundle fields, not typed into the page.
- Strategy names capitalised in the UI; glossary names for configs.

Amends "Latency vs accuracy framing": with the Timing repeats, the §4.3 claim is ~17× (Hybrid ~800 ms vs Fusion baseline ~47 ms median p50), not ~20×. The bundle computes the ratio.
