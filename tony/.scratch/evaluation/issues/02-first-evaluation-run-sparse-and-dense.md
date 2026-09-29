# 02: First Evaluation run: Sparse and Dense

**What to build:** One eval command scores Sparse and Dense retrieval on the Query set under every loaded Chunking strategy. It prints a markdown table (Recall@5/10/20, MRR, nDCG@5/10, latency p50/p95) and writes a run folder with the same numbers plus per-query ranks. This is the tracer bullet: all the plumbing lands here.

Spec: [../spec.md](../spec.md), "Implementation Decisions" (Four configs, Chunk → Recipe dedupe, Metrics, Latency, Run output, Eval command options).

**Blocked by:** 01 (Generate the Query set)

**Status:** done

- [x] Metrics module is pure: relevant Recipe per query + ranked Recipe ids per (config, strategy, query) in, metrics table out
- [x] Sparse and Dense pull 100 Chunks, dedupe to Recipes by first appearance, keep 20
- [x] Strategies default to every loaded one from the registry. Configs, strategies, query-set path and a query limit can be chosen
- [x] Latency is timed in process per stage (query embedding, Sparse, Dense), with one warm-up query not counted
- [x] The run folder holds settings (including the query-set file hash), metrics JSON and CSV, per-query ranks and latencies CSV, and the markdown table
- [x] Run folders are gitignored
- [x] Metric tests with hand-worked values: ranks 1 and 7, a missing Recipe, a duplicate Recipe counted once, an empty result counted as a miss
- [x] An end-to-end test on `recipe_test` with a fake embedder: two queries, the expected files, and a known-item query ranking its Recipe first
- [x] A real run over the 300 queries and 3 strategies finishes, and the table is pasted into the Done notes (298 queries: ticket 01 skipped Recipes 430 and 7150)

## Done (2026-09-28)

- `uv run scripts/evaluate.py [--configs sparse dense] [--strategies ...] [--queries PATH] [--limit N] [--out DIR]`. Runs in the project env (it calls `api.retrieval`), so no PEP 723 header.
- `scripts/metrics.py` is pure: `metrics_table(relevant, runs)` and `latency_summary`. It dedupes by first appearance and cuts to 20 itself, so a Chunk-level list gives the same answer as a Recipe-level one.
- Each query is embedded once and shared by every strategy. Dense latency = embed + dense. The first query runs once more as an uncounted warm-up.
- Run folder `eval/runs/<timestamp>/`: `settings.json` (configs, strategies, pool 100, depth 20, embed model, query-set sha256, git commit), `metrics.json`, `metrics.csv` (total and per-stage p50/p95), `per_query.csv` (rank, stage ms, the top 20 Recipe ids), `table.md`. `eval/runs/` is gitignored; keep one with `git add -f`.
- Tests: `tests/test_metrics.py` (ranks 1 and 7 and a miss, duplicate counted once, empty/missing = miss, top-20 cut, p50/p95), `tests/test_evaluate.py` (on `recipe_test`: files written, warm-up + one embed per query, known-item ranks 1st under Sparse and Dense, config/strategy/limit selection, unloaded strategy refused).

Real run `20260928-001149`: 298 queries, 3 strategies, 70 s.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| sparse | fixed | 0.631 | 0.732 | 0.789 | 0.506 | 0.523 | 0.557 | 7.6 | 19.8 |
| dense | fixed | 0.614 | 0.708 | 0.795 | 0.470 | 0.491 | 0.522 | 51.7 | 164.1 |
| sparse | semantic | 0.634 | 0.732 | 0.802 | 0.490 | 0.512 | 0.544 | 6.6 | 16.3 |
| dense | semantic | 0.634 | 0.721 | 0.799 | 0.488 | 0.511 | 0.540 | 55.4 | 170.6 |
| sparse | sentence | 0.641 | 0.732 | 0.805 | 0.488 | 0.513 | 0.543 | 6.8 | 20.0 |
| dense | sentence | 0.607 | 0.698 | 0.789 | 0.475 | 0.494 | 0.524 | 53.7 | 199.0 |

- Sparse and Dense are within a few points everywhere; Sparse is slightly ahead on MRR. Expected given word overlap 0.85 (see ticket 01).
- Chunking strategy barely moves the numbers (±0.02). Summary and Ingredients chunks are the same under every strategy, and a known-item query mostly hits those.
- Dense p50 splits into ~21 ms embedding (Ollama over HTTP) + ~31 ms vector search. Its p95 tail is the vector search, not the embedding (p95 29 ms).

Code review (2026-09-28), two axes against `ed834eb`:

- Spec: nothing wrong. Only gap was the 300 vs 298 checkbox, now noted above.
- Standards: the `recipes` fixture, `RECIPES` and the fake embed were copied from `test_ingest.py`. Moved to `tests/conftest.py`; both test files use them.
- Left for ticket 03: `CONFIGS` should become one record per config (function, uses embedding, stages), since Hybrid is what needs it. That also drops the unused `qvec` in `sparse()`.
- Report note: each query is embedded once and reused under every strategy, so Dense latency rows share the same embed samples.
