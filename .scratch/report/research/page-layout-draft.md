# Page layout draft (for "Page layout and charts")

Draft for review. Nothing here is decided until the ticket's resolution says so.

## Page-wide

- One long column, ~760 px text width, charts can go wider (~1000 px). Sticky section list on the left at wide screens, none on phones.
- Header: title, then one mono line: run folder · `git_commit` (short) · `query_set_sha256` (first 12) · bundle `built_at`. Theme button reuses `useTheme.ts`.
- Config colours: reuse `--sparse`, `--dense`, `--hybrid` from `index.css`, add `--fusion` for the Fusion baseline. Validate the 4 with the dataviz script in both modes.
- Chunking strategies never get a colour. They are rows, facets or a label.
- Charts: hand-drawn SVG in React, no chart library (the app already draws SVG in `Connectors.tsx`, the charts are few, and theme tokens work directly).
- Every chart has a "Show table" toggle under it. Tooltips add detail, never hold the only copy of a number.
- One shared "forest row" component (difference, 95% CI bar, zero line, Holm p) for §4.2, §4.3's CI, §5 and any significance line.

## Section by section

| § | Shows | Form |
|---|---|---|
| 1.1 Problem | prose | - |
| 1.2 System | ParadeDB / Ollama / FastAPI / reranker boxes, logic placement | static SVG diagram + prose |
| 1.3 Four configs | brief name → glossary name, eval-only note | table |
| 2.1 Source | 32,719 Recipes, 22 categories, dedupe line | 3 stat tiles; fields → Chunk kind table; top 10 categories + other as one-hue horizontal bars |
| 2.2 Chunks | strategy × kind counts, parameters, Step length | table; 3 small-multiple Step-length histograms (one hue, p10/median/p90 ticks) |
| 2.3 Query set | prompt, 57 rewrites by reason, overlap before/after, length, category spread | prompt in a collapsed block; reasons as a 5-row table; overlap histogram with before/after mean marked; category spread as prose + table |
| 2.4 Ground-truth limits | prose, links to §6 | - |
| 3 Setup | metrics, protocol, settings, caveats | prose; full `settings.json` as a collapsed table |
| 4.1 Configs | 12-row main table, R@5 and MRR with CI | table first; then a dumbbell per config (R@5 dot → R@20 dot), 3 strategies as 3 rows per config |
| 4.2 Chunking strategy | 3 Hybrid pair differences | forest rows (all cross zero, that's the picture) |
| 4.3 Latency vs accuracy | Fusion baseline vs Hybrid totals, Hybrid stages | scatter: x = p50 ms (log), y = R@5, p95 whisker, repeat range; Hybrid stages as one stacked bar |
| 5 Ablation | 8 arms × 3 strategies | per arm group: forest rows ΔR@5 vs default + a "same-run latency ratio" column |
| 6.1 Buckets | counts per strategy | table |
| 6.2 Overlap bias | Sparse, Dense, Hybrid R@5 at high vs low overlap | slope chart per strategy (3 facets); Sparse and Dense lines cross = the sign flip |
| 6.3 rerank_hurt | net-effect table | table (decided) |
| 6.4 Cases | 5 cases | one card each: query, known Recipe, rank grid (4 configs × 3 strategies), top 5 titles per config with the right one marked, why-line, Recipe text collapsed |
| 6.5 Error groups | 29 misses in 3 groups + other | table with counts and one example per group |
| 7 Conclusion | prose | - |
| Appendix: All queries | per-query drill-down | see below |

## Drill-down

- Where: an appendix after §7, linked from §6 and from each case card ("see in all queries").
- Row: query id, text, known Recipe title, rank under each of the 4 configs for the chosen strategy (miss shown as "–"), overlap high/low, hand-rewritten mark.
- Expand a row: top-20 titles per config side by side, the right Recipe highlighted, plus the other two strategies' ranks.
- Filters in one row: strategy, bucket (sparse_win, dense_win, rerank_hurt, rerank_help, every-config miss), overlap, hand-rewritten, text search. State in the URL so a link can open one query.
