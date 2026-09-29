# Page spec: the Report page

Part 2 of the map's destination. Everything here was decided in closed tickets; this file gathers it and orders the build. Where a ticket holds the detail, this file names it and doesn't restate it.

## What gets built

1. `scripts/report_bundle.py`: reads `eval/report.json`, checks ranks, computes everything, writes `ui/public/report.json`.
2. `tests/test_report_bundle.py`: freshness (input hashes in the committed bundle match the files) plus unit tests for the pure parts (Holm, latency aggregation, best-row flags).
3. `ui/src/report/`: the page, one component per section, reading only the bundle.
4. Route `/report`: `main.tsx` picks the Report page on `location.pathname`; `api/main.py` serves `index.html` at `/report` and the bundle at `/report.json`.
5. `evaluate.py`: `recipes.csv` also lists each query's known Recipe (a Recipe missed by every config has no row today, so case text for q066 can't be joined). One-off backfill into the Report run.
6. README: "Report", "Results", "Demo" sections ("What the hand-in includes besides the page").

## Bundle (`ui/public/report.json`)

Shape from "Page data contract", with the blocks later tickets added. Python computes, the page formats.

| Block | Holds | Source |
|---|---|---|
| `meta` | manifest, each run's `settings.json`, input file hashes, `built_at` | manifest |
| `metrics` | 12 rows: all metrics from the Report run, R@5/MRR bootstrap CI, latency (total and per stage) as median p50, median p95, p50 min–max over the 3 Timing repeats, `best_r5` flag per strategy | Report run, Timing repeats |
| `significance` | every test in every manifest run, raw p and Holm p over the whole family | `significance.json` per run |
| `ablations` | per arm × config × strategy: default and arm metrics, R@5/MRR diff with CI and Holm p, same-run latency ratio (total and changed stage), arm latency applied to the Report run's median p50 | Ablation runs |
| `failures` | bucket counts per strategy, all-3-strategies counts, overlap split, rerank net effect, Hybrid kind split | `failures.analyze_run` on the Report run |
| `per_query` | Report run rows: config, strategy, query id, rank, top-20 ids, buckets per strategy | Report run |
| `queries` | text, known Recipe id and title, overlap, hand-rewritten, edit reason, error group | `queries.jsonl`, labels |
| `recipes` | id → title | `recipes.csv` |
| `cases` | the 5 case ids with bucket and why-line, Recipe description and ingredients | "Pick the case studies…", `data/recipe.csv` |
| `corpus`, `query_set` | §2 numbers; prompt, rewrite reasons, overlap before/after, length stats, category spread | `corpus.json`, `make_queries.PROMPT` |
| `headline` | the numbers prose quotes (latency ratio, R@5 gains, net into top 5, …) | computed from the blocks above |

Hard fails: any Timing repeat or Ablation default rank differs from the Report run's (`runcheck.rank_mismatches`), a manifest path is missing, or a label file names an unknown query.

## Sections

Order and claims from "Report outline"; wording rules from "Page layout and charts" (plain full sentences, numbers only from the bundle, glossary names).

| § | Content | Decided in |
|---|---|---|
| Header | title, run · commit · query-set hash · built_at, theme toggle | Page layout draft |
| 1 | problem, text-only, system diagram and logic placement, brief-name → glossary-name table with the eval-only note | Report outline, Fusion baseline ticket |
| 2 | 2.1 counts, fields → Chunk kind, top 10 categories; 2.2 strategy × kind table, parameters, Step length; 2.3 prompt, rewrite reasons, overlap before/after; 2.4 limits | Dataset section stats |
| 3 | metrics, protocol, settings table, ANN probe and why not HNSW (ADR 0003), pool sizes, Timing repeats, significance method | Significance tests, Latency framing, HNSW ticket |
| 4.1 | 12-row table with CIs, R@5 → R@20 dumbbells | Report outline |
| 4.2 | Hybrid strategy pairs as forest rows | Significance tests |
| 4.3 | aligned panels, table toggle with best row, Hybrid stage bar | Page layout and charts |
| 5 | per arm group forest rows ΔR@5/ΔMRR with Holm p and latency ratio; three-way Dense table (served / HNSW / exact) | Which ablations, HNSW ticket |
| 6 | 6.1 counts; 6.2 overlap sign flip; 6.3 net-effect table; 6.4 five case cards; 6.5 error groups | Explaining rerank_hurt, Failure cases, Pick the cases |
| 7 | three tiers, Chunking strategy line, limits, future work | What the conclusion recommends |
| Appendix | drill-down, list + detail, URL state | Page layout and charts |
| References | dataset, RRF, nomic-embed-text, BGE reranker, ParadeDB, pgvector | Report outline |

## Not in this spec

Print stylesheet, PDF, hosting, slides ("What the hand-in includes besides the page"). Switching the served reranker.
