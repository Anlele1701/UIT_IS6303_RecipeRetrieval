# Dataset section stats

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by:
Parent: ../map.md

## Question

"Report outline" fixed §2's slots: 2.1 source and schema, 2.2 Chunks and Chunking strategies, 2.3 Query set. Decide what fills them and where each number comes from.

- 2.1: Recipe count (loaded vs in the source dataset), fields used, category spread. Chart or table?
- 2.2: Chunk count per Chunking strategy and per Chunk kind, Step chunk length distribution, each strategy's parameters.
- 2.3: how queries were generated (model, prompt), the 57 hand rewrites and why, word-overlap distribution.
- Source for each: a DB query at eval time written into the run folder, a separate stats script, or a committed file. The page must work without the DB (see "Page data contract").

## Answer

§2's numbers come from a `corpus.json` that `evaluate.py` writes into the run folder from the DB at the start of a run. The bundle reads it like any other run file, so its hash is checked too. Nothing in §2 is hand-typed.

- **Scope**: this ticket fixes which numbers §2 shows and where they come from. Table vs chart vs prose is "Page layout and charts".
- **2.1 Source and schema**: loaded count with the dedupe line (32,719 of 32,722 rows, 3 duplicate URLs dropped); fields used, each mapped to the Chunk kind it feeds (title + description → Summary, ingredients → Ingredients, directions → Step, category → filter only); category count (22); top 10 categories by Recipe count plus "other".
- **2.2 Chunks and Chunking strategies**: strategy × Chunk kind counts (Summary and Ingredients equal across strategies, which shows only Step chunks differ); each strategy's parameters from `ingest.STRATEGIES`; Step chunk length in characters per strategy (p10, median, p90, max, histogram bins). Characters because fixed cuts by tokens and semantic by characters.
- **2.3 Query set**: the generation prompt verbatim (bundle imports `make_queries.PROMPT`); model `qwen2.5:7b`, seed 603, stratified by category, 2 Recipes skipped after 3 bad tries; 57 hand rewrites with a per-reason breakdown; word-overlap histogram and mean before vs after rewrites (0.80 → 0.84, computed from `edited_from`); query length in words; category spread of the 298 queries vs the corpus.
- **Rewrite reasons**: not stored per query today. A new `eval/query_edits.csv` (query_id, reason) holds them. `queries.jsonl` is not touched, because its hash is in the report run's `settings.json`. Labelling goes into "Pick the case studies and label the every-config misses" (agent proposes from `edited_from` vs `text`, human confirms).

Facts checked (local DB, 2026-09-28): 32,719 Recipes, 22 categories; Step chunks: fixed 100,536, semantic 101,000, sentence 110,314; every Recipe has one Summary and one Ingredients chunk under every strategy. `ingest.py` last changed in `fbb3947` (before `466b46a`) and no chunk run since Sep 23, so backfilling `corpus.json` into `20260928-122309` from the current DB is valid.

Build items for the spec:
- `evaluate.py` writes `corpus.json` (Recipe and category counts, strategy × kind Chunk counts, Step chunk length stats and bins, strategy parameters, recipe_id → category for the queried Recipes).
- One-off backfill of `corpus.json` into `eval/runs/20260928-122309`.
- `eval/query_edits.csv`, and the bundle computes rewrite counts, overlap before/after and query-length stats from it and `queries.jsonl`.
- Bundle gains a `corpus` block and `prompt` text.
