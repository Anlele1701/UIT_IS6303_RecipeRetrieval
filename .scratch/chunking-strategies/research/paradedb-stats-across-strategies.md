# ParadeDB stats across Chunking strategies

Research for `issues/01-paradedb-stats-across-strategies.md`. Date: 2026-09-27.

## Version checked

Read-only query on the running container `recipe-paradedb`:

| extension | version |
| --- | --- |
| pg_search | 0.25.9 |
| vector (pgvector) | 0.8.4 |
| Postgres | 17.11 |

Source read at the matching tag: `paradedb/paradedb` `v0.25.9` (commit `c727757`), which pins the Tantivy fork
`paradedb/tantivy` at `de9405aaadcd9378bdeeea7a4247c7f72e25bbd5` (`Cargo.toml` line 61).

Current data: one strategy, `semantic-v1`, 166,438 chunks in 10 segments (`pdb.index_segments`).

Experiments marked "verified in a throwaway container" were run in a separate `paradedb/paradedb:pg17` container
(`pdb-research-tmp`, since removed). The real DB was only read.

## 1. BM25 statistics are whole-index, not per filter

**Answer:** IDF, doc count and average field length come from every segment of the index. A `WHERE chunker = ...`
filter doesn't narrow them. Adding a strategy changes the other strategies' BM25 scores, and can change their rankings.

Evidence:

- pg_search builds scoring with `EnableScoring::Enabled { searcher, statistics_provider: &self.searcher }`
  (`pg_search/src/index/reader/index.rs` lines 745-751, and `enable_scoring()` line 1878). No other statistics
  provider is used anywhere in `pg_search/src`.
- Tantivy's `impl Bm25StatisticsProvider for Searcher` (`src/query/bm25.rs` lines 33-63) sums over
  `self.segment_readers()`:
  - `total_num_docs` = sum of `max_doc()` per segment (includes deleted-but-not-merged docs)
  - `total_num_tokens(field)` = sum per segment, then `average_fieldnorm = total_num_tokens / total_num_docs`
    (`bm25.rs` line 124)
  - `doc_freq(term)` = sum per segment (`src/core/searcher.rs` lines 133-141)
- The filter is compiled as a sibling clause in a boolean query. `EXPLAIN` on the real DB shows
  `{"boolean":{"must":[{match content ...},{"term":{"field":"chunker","value":"semantic-v1"}}]}}`. It restricts which
  docs are scored, not the statistics.
- ParadeDB docs say dead rows affect scores until `VACUUM`, which only makes sense if stats are index-wide
  ([BM25 Scoring, "Score Refresh"](https://www.paradedb.com/docs/reference/full-text/score)).
- Verified in a throwaway container: 1,000 rows of strategy `a`, then 1,000 rows of strategy `b` containing
  "garlic". The same `a` doc's score for `content ||| 'garlic' AND strategy = 'a'` dropped from **2.2991 to 1.2910**.

Why rankings shift too, not only absolute scores: IDF is non-linear in `N` and `df`. The new strategies will also
have different step-chunk lengths, so the `content` average length moves, and length normalization for every
semantic-v1 chunk changes. Summary and Ingredients chunks are identical under every strategy, so their terms' `df`
roughly triples along with `N`. Step-chunk terms won't scale the same way. How big the effect is on our data is
**not measured**. That it happens is certain.

### Side finding: pushed-down filters add to the BM25 score

The `term` filter clause in `must` is scored too. On the real DB (read-only):

| query | top doc score |
| --- | --- |
| `content ||| 'garlic shrimp'` | 8.253869 (id 49367) |
| same + `kind = 'step'` | 8.753372 (id 49367) |

The difference, 0.4995, exactly equals `idf(kind=step) = ln(1 + (166438 - 101000 + 0.5)/(101000 + 0.5))`.
`chunker = 'semantic-v1'` adds about 0.000003 today because every row matches. With three strategies of about a third
each, it would add about `ln(3) ≈ 1.1`, and a different amount per strategy if row counts differ.

- It's the same for every doc in one query (literal field, one token), so it **doesn't change ranking** inside a
  query, and RRF in `api/retrieval.py` only uses ranks.
- It **does** matter for anything comparing raw `pdb.score` values across strategies or queries, like thresholds or
  plotting score distributions in the ablation.

## 2. Vector search: what the index is and how a filter interacts with the probe

**What the index is:** a SPANN-style index, "similar to an IVF index but with additional structures"
([Indexing Vectors, "Index Options"](https://www.paradedb.com/docs/reference/indexing/indexing-vectors)). It's built
per segment. Vectors are clustered with k-means (defaults `training_sample_ratio=0.32`, `max_leaf_size=100`), and
clusters are routed through a graph over centroids. Segments under `paradedb.vector_clustering_threshold` (500 docs)
are stored flat and scanned exactly. It doesn't use pgvector's HNSW/IVFFlat.

Our index (read-only `paradedb.vector_clusters('chunk_search_idx','embedding')`): 149-202 clusters per segment,
average 100 rows per cluster, no replicas (cluster sizes sum to the segment's doc count).

**How the probe budget works** (`paradedb/tantivy` `src/vector/ivf/params.rs`, `src/vector/backend.rs`):

- The filter is applied **before** scoring, not after. Each segment drains the filter into a bitset
  (`build_filter_bitset`, backend.rs line 526). Then the clusters are probed in centroid-rank order, and each row
  goes through `filter -> alive -> seen` before its vector is read (backend.rs lines 720-740).
- `paradedb.vector_cluster_max_probe` is a ceiling on **work units**, not clusters. Opening a cluster costs
  `x = 1.64 / (1.64 + n_avg)`. Each row that passes the filter costs `(1 - x) / n_avg`. **Filter-rejected rows cost
  nothing** ("A selective filter therefore probes deeper into the ranked list before the ceiling binds", params.rs
  doc comment on `AdaptiveProbeParams`).
- The budget per segment is `clamp(max_probe × C, min 16, max C)` units, with `C` = clusters in the segment
  (`resolved_work_budget`, params.rs). `min_probe_clusters` defaults to 16, and pg_search only overrides the fraction
  (`index.rs` line 1226, `..Default::default()`).
- A bounds check skips clusters that provably can't improve the top-k. The docs say this "never reduces recall"
  ([Tuning Recall and Latency](https://www.paradedb.com/docs/reference/vector/tuning)).

Worked numbers for our index (C ≈ 160, n_avg ≈ 100, so x ≈ 0.016 and a row costs ≈ 0.0098):

| case | budget per segment | clusters opened | rows scored |
| --- | --- | --- | --- |
| today, filter keeps 100% | max(0.02×160 = 3.2, 16) = 16 units | ~16 | ~1,600 |
| filter keeps 1/3 | 16 units | ~47 (each costs ≈ 0.34) | ~1,550 |
| filter keeps 1/10 | 16 units | ~140 (almost exhaustive) | ~1,400 |

`EXPLAIN ANALYZE` on the real DB matches: one segment opened 13 clusters and scored 1,744 rows.

**Does recall drop with a 1/3 filter?** Not the way post-filtering would drop it. The number of qualifying candidates
scored stays about the same, and the search reaches about 3x more clusters to find them. Whether recall@k is exactly
equal to today's is **not verified**. It depends on how the strategies' vectors spread over clusters. Their step
chunks come from the same recipes, so they'll be mixed into the same clusters.

**Is it equal across strategies with different row counts?** Not exactly. The budget is fixed per segment, so a
strategy with a smaller share of rows probes deeper (more clusters, same number of scored rows), and a bigger
strategy probes shallower. So the smaller strategy plausibly gets slightly *higher* recall. **Inferred from the
code, not measured.**

Two practical gotchas:

- At the current size, the 16-unit floor is what binds, not the 0.02 default. Any `max_probe` below about
  16/160 = 0.10 does nothing. The commented `SET paradedb.vector_cluster_max_probe = 0.05` in `sql/queries.sql` has
  no effect.
- The GUC help text in `pg_search/src/gucs.rs` (lines 247-256, 515) still says `ceil(fraction × cluster_count)`.
  The Tantivy code it calls works in work units with the 16 floor. Trust the code.

To measure it for the ablation: run each strategy's queries once with `SET paradedb.vector_cluster_max_probe = 1.0`
(exhaustive, exact) as ground truth, then at the setting you'll use, and compare recall@k per strategy.

## 3. Isolation options in pg_search 0.25.9

| option | works? | BM25 stats isolated? | vector clusters isolated? |
| --- | --- | --- | --- |
| One table, one index, filter on `strategy` (today) | yes | no | no (mixed clusters, filtered probe) |
| Partial ParadeDB indexes, one per strategy | **no**, only one per table | - | - |
| One table per strategy | yes | yes | yes |
| Declarative `PARTITION BY LIST (strategy)` | yes | yes | yes |

**One ParadeDB index per table is a hard limit.** Docs: "Only one ParadeDB index can exist per table"
([Create an Index](https://www.paradedb.com/docs/reference/indexing/create-index)). Source:
`pg_search/src/postgres/build.rs` lines 62-80 panics with `a relation may only have one ParadeDB index`. Verified in
a throwaway container: a second `CREATE INDEX ... USING paradedb ... WHERE strategy = 'b'` fails with that error.
(The check is skipped for `CONCURRENTLY` so that `REINDEX CONCURRENTLY` works. That's not a supported way to get two
indexes.)

A single partial index works, but a query must repeat its `WHERE` predicate or it falls back to a sequential scan
([Partial Indexes](https://www.paradedb.com/docs/reference/indexing/indexing-partial)). With only one allowed per
table, it can't isolate three strategies.

**Declarative partitioning works, and the planner picks the right index.** Postgres creates one child index per
partition, and each child is its own ParadeDB index with its own segments and stats. Verified in a throwaway
container:

- `PARTITION BY LIST (strategy)`, partitions `p_a` and `p_b`, one `CREATE INDEX ... USING paradedb` on the parent.
  Postgres created `p_a_id_content_strategy_embedding_idx` and `p_b_...`.
- Adding 1,000 `b` rows left the `a` doc's score unchanged at **2.2990966**. The single-table case above dropped it
  to 1.2910.
- `EXPLAIN` for BM25 and vector queries with `strategy = 'a'` shows one `ParadeDB Base Scan on p_a` using the `p_a`
  index (plan-time partition pruning).
- With a bound parameter (`PREPARE ... strategy = $1`, forced generic plan) it shows `Subplans Removed: 1`
  (run-time pruning). That's the shape psycopg's server-side parameters can end up in.
- Attaching an existing, already-indexed table as a new partition (`ATTACH PARTITION ... FOR VALUES IN ('c')` with a
  matching `CHECK`) **reused its ParadeDB index** as the child of the parent index, with no rebuild. That's relevant
  for keeping `semantic-v1` data without re-embedding. Tested on a small table only.

Partitioning costs:

- Postgres requires every unique constraint to include the partition key. `PRIMARY KEY (id)` has to become
  `PRIMARY KEY (id, strategy)`, and `UNIQUE (recipe_id, chunker, kind, position)` already includes it. `id` stays
  unique in practice because the identity sequence is shared across partitions.
- A query without a strategy filter hits every partition, and the scores come from different indexes, so they're not
  comparable. Our API always filters, so that's fine.
- ParadeDB's current docs say little about partitioned tables. Support is described in `docs/welcome/limitations.mdx`
  ("ParadeDB supports partitioned tables"), the legacy create-index page ("A BM25 index can be created over a
  partitioned table in the same way as a normal table"), and several changelog fixes (0.15.13, 0.18.0, 0.18.7). The
  `range_table.rs` planner code handles `RELKIND_PARTITIONED_TABLE`.

**Also seen, not researched:** a `partition_by` index option (`pg_search/src/postgres/options.rs`,
`build_partitioning.rs`). It partitions segments *inside one index* for MPP joins. The searcher still spans all
segments, so it presumably doesn't isolate BM25 stats. **Unverified.**

**Outside Postgres:** a dedicated search engine (OpenSearch/Elasticsearch, or Tantivy directly) would give one index
per strategy just as naturally. It doesn't fit here because the whole project is "everything in one ParadeDB
instance", and partitioning already gives full isolation.

## Sources

- ParadeDB docs: [BM25 Scoring](https://www.paradedb.com/docs/reference/full-text/score),
  [Partial Indexes](https://www.paradedb.com/docs/reference/indexing/indexing-partial),
  [Create an Index](https://www.paradedb.com/docs/reference/indexing/create-index),
  [Indexing Vectors](https://www.paradedb.com/docs/reference/indexing/indexing-vectors),
  [Querying Vectors](https://www.paradedb.com/docs/reference/vector/querying),
  [Tuning Recall and Latency](https://www.paradedb.com/docs/reference/vector/tuning),
  [How the ParadeDB Index Works](https://www.paradedb.com/docs/concepts/how-the-paradedb-index-works)
- ParadeDB source, tag `v0.25.9`: `pg_search/src/index/reader/index.rs`, `pg_search/src/postgres/build.rs`,
  `pg_search/src/gucs.rs`, `pg_search/src/postgres/customscan/range_table.rs`, `docs/welcome/limitations.mdx`,
  `docs/legacy/indexing/create-index.mdx`
- Tantivy fork `paradedb/tantivy@de9405a`: `src/query/bm25.rs`, `src/core/searcher.rs`, `src/vector/ivf/params.rs`,
  `src/vector/backend.rs`
- Read-only queries against `recipe-paradedb`: `pg_extension`, `pdb.index_segments`, `paradedb.vector_clusters`,
  `pg_settings`, `EXPLAIN (ANALYZE)` inside `BEGIN READ ONLY`
