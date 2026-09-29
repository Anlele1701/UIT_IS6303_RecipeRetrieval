# 04: Failure analyzer

**What to build:** A command reads an Evaluation run's folder, without searching again, and lists the queries where the methods disagree: Sparse found the Recipe and Dense didn't, the reverse, and where Reranking made the rank worse. The output is ready to use for report case studies.

Spec: [../spec.md](../spec.md), "Implementation Decisions" (Failure analyzer).

**Blocked by:** 03 (Add Hybrid and the Fusion baseline)

**Status:** done

- [x] Sparse win = Sparse rank ≤ 10 and Dense rank > 10. Dense win is the reverse
- [x] Rerank hurt = Hybrid rank worse than Fusion baseline rank
- [x] Counts per bucket per Chunking strategy
- [x] Markdown case lists with query, Recipe title and ranks, in a stable order (first N by query id)
- [x] Metrics are also split by low vs high word overlap, to show the synthetic-query bias
- [x] Tests use a hand-written per-query ranks file and check bucket membership and counts

## Done (2026-09-28)

- `scripts/failures.py <run folder> [--cases N] [--queries PATH]`. Reads `per_query.csv` and the Query set named in `settings.json`, never the DB. Prints markdown and writes `<run>/failures.md`.
- Buckets are one `Bucket(first, second, holds, meaning)` each, like `EvalConfig`. A miss ranks as 21, so a Hybrid miss after a Fusion hit is "hurt", and two misses are in no bucket. Rank exactly 10 counts as found. A tie isn't "hurt". A bucket is left out if the run lacks one of its two configs.
- `rerank_hurt` compares `hybrid` against `fusion` (the spec's "Hybrid RRF").
- High word overlap means 1.0: every content word of the query appears in the Recipe's text. That's the Query set's median (154 of 298), so the two groups are about the same size. My call, the spec gives no cut.
- It covers only the queries the run holds, so a `--limit` run isn't padded with misses.
- It refuses a Query set whose hash differs from the run's, since titles and overlap would be wrong. `--queries` overrides.
- `metrics.average()` and `metrics.LABELS` are now shared with `evaluate.py` (review: duplicated averaging, hand-typed headers).

Run `20260928-002509`, 298 queries:

| Strategy | sparse_win | dense_win | rerank_hurt |
|---|---:|---:|---:|
| fixed | 40 | 33 | 58 |
| semantic | 35 | 32 | 62 |
| sentence | 41 | 31 | 67 |

- The bias shows clearly. Sparse fixed R@5 is 0.825 on high overlap and 0.424 on low. Dense drops less, from 0.740 to 0.479. On low-overlap queries Dense beats Sparse under every strategy.
- Hybrid is best in both groups. Its lead over Sparse is small on high overlap (0.864 vs 0.825 R@5) and large on low (0.597 vs 0.424).
- Reranking hurts 58 to 67 queries per strategy but still wins overall (+0.08 R@5). Most hurt cases are small: 35 to 43 per strategy drop 1 or 2 places. Only 5 to 8 per strategy fall out of the top 10, and those are the ones worth a case study.

Code review (2026-09-28), two axes:

- Spec: a `--limit` run was analyzed over the whole Query set, which gave wrong counts and diluted overlap metrics. Fixed, with a test. nDCG was missing from the overlap table. Added. Extras not asked for (hash check, writing `failures.md`, all four ranks per case) are kept.
- Standards: bucket rule split across a tuple and a string check → `Bucket`. Averaging duplicated `metrics_table` → `metrics.average`. Hand-typed header drifting from `COLUMNS` → `metrics.LABELS` in both scripts. `markdown()` re-derived facts → report carries `bucket_names` and `group_sizes`. Test fixture tuples → dicts. Kept: the one-line Query set reader duplicates `evaluate.read_queries`. Sharing it would mean importing `evaluate` (psycopg, `api`) or putting file IO in the pure metrics module.
