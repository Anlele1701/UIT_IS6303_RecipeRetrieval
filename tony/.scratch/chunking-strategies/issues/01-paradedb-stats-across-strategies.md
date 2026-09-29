# Does ParadeDB mix corpus stats across strategies?

Type: research
Status: resolved
Blocked by:
Parent: ../map.md

## Question

With all strategies in one `chunk` table and one ParadeDB index (`sql/indexes.sql`), filtered by a `strategy` column:

1. Are BM25 statistics (IDF, average document length) computed over the whole index, or only over rows matching the filter? If whole-index, adding a strategy changes the others' BM25 scores.
2. For vector search with a filter, does `paradedb.vector_cluster_max_probe` recall degrade when the filter keeps only ~1/3 of rows? Is the effect equal across strategies with different row counts?
3. What isolation options exist in this ParadeDB version (`paradedb/paradedb:pg17`): partial indexes (`WHERE strategy = ...`), one index per table/partition, anything else, and does the planner pick the right one?

Primary sources: ParadeDB docs/source, Tantivy BM25 docs.

## Findings

Full write-up: [../research/paradedb-stats-across-strategies.md](../research/paradedb-stats-across-strategies.md) (pg_search 0.25.9, checked against source at `v0.25.9`).

- BM25 stats (doc count, doc freq, average length) cover the whole index, all segments. The `strategy` filter doesn't narrow them. Adding a strategy changes the other strategies' scores and can change their ranking. Verified: one doc's score went from 2.30 to 1.29 after another strategy's rows were added.
- Pushed-down equality filters add their own IDF to `pdb.score`, the same amount for every row in a query. Ranking and RRF are unaffected, but raw scores can't be compared across strategies.
- The vector index is SPANN/IVF-style per segment. The filter is applied before scoring, and rejected rows don't use up the probe budget, so a 1/3 filter probes about 3x more clusters for the same number of scored rows, instead of losing recall to post-filtering. A strategy with fewer rows probes deeper, so recall probably differs slightly by strategy (inferred from code, not measured). At our size the 16-cluster floor binds, so `vector_cluster_max_probe` below about 0.10 has no effect.
- Only one ParadeDB index per table (hard error), so per-strategy partial indexes aren't possible.
- `PARTITION BY LIST (strategy)` gives one ParadeDB index per partition. Verified: BM25 scores stay isolated, the planner prunes to the right partition (including with a bound parameter), and an already-indexed table can be attached as a partition without rebuilding its index. Cost: the PK becomes `(id, strategy)`.

## Answer

Yes, scores leak. BM25 stats (doc count, doc freq, avg length) are index-wide, so a `strategy` filter does not isolate them; adding rows of another strategy changed an existing score (2.2991 → 1.2910). Only one ParadeDB index per table, so partial indexes per strategy are impossible. Isolation needs one index per strategy: separate tables, or `PARTITION BY LIST (strategy)` (tested: scores unchanged, planner prunes to the right partition, PK becomes `(id, strategy)`). Filtered vector search is pre-filtered, so recall should hold (unmeasured). Details: [research note](../research/paradedb-stats-across-strategies.md).
