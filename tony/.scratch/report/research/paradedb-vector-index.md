# What vector index does ParadeDB build for our embeddings?

Answers `issues/02-paradedb-vector-index.md`. Checked 2026-09-28 against the running `recipe-paradedb` container and the ParadeDB docs at the matching git tag.

## Short answer

- Dense search is ANN, not exact. The `USING paradedb` index stores `embedding` in a SPANN-style (IVF-like) cluster index, not HNSW and not pgvector's IVFFlat.
- Build parameters are ParadeDB's own: `centroid_ratio` (0.01), `training_samples_per_centroid` (32), `cluster_replication` (1). We set none, so all defaults. The query knob is `paradedb.vector_cluster_max_probe` (0.02). HNSW's `m` / `ef_construction` / `ef_search` do not apply.
- Recall below exact is real and worth a line in the report: about 0.78 recall@50 at the default setting in a local spot check (details below).
- `pg_search` scores with real BM25 (Tantivy, k1=1.2, b=0.75, IDF from index stats). `ts_rank_cd` has no IDF and no global corpus stats.

## Versions (verified, local)

- Image `paradedb/paradedb:pg17` (floating tag, built 2026-09-11), from `docker-compose.yml`.
- `select extversion from pg_extension`: `pg_search 0.25.9`, `vector 0.8.4`. `select version()`: PostgreSQL 17.11.
- `pg_am` lists `paradedb` and `bm25`, both with handler `bm25_handler`. Also `hnsw` and `ivfflat` from pgvector, but no index on `chunk` uses them.
- Index reloptions on all partitions are only `{key_field=id}`, so every vector build option is at its default.
- Inference: `pg17` is a floating tag, so a re-pull can change the version. Pin a tag if the report quotes version-specific behaviour.

## Vector index: verified facts

Docs source: ParadeDB repo at tag `v0.25.9`, `docs/documentation/...` (published at the canonical URLs below).

- Vector search in the ParadeDB index is "a beta feature available in versions 0.25.0 and above." (https://www.paradedb.com/docs/documentation/vector/overview)
- "Vectors are indexed with a SPANN-style index." (same page)
- "ParadeDB uses pgvector's vector types, but not its HNSW or IVF indexes." (https://www.paradedb.com/docs/documentation/indexing/indexing-vectors)
- "ParadeDB uses a SPANN-style vector index, which is similar to an IVF index but with additional structures to improve recall and latency." Build options (same page):
  - `centroid_ratio` default 0.01: `num_centroids = centroid_ratio * num_vectors`.
  - `training_samples_per_centroid` default 32: k-means training sample size.
  - `cluster_replication` default 1: how many clusters each vector is written into; higher helps filtered recall.
  - The distance function (`vector_cosine_ops`) is fixed at build time.
- "Vector search is approximate: it probes a subset of the index's vector clusters rather than scanning every vector." `paradedb.vector_cluster_max_probe` default 0.02 is "a ceiling on how much probe work a query may spend, expressed as a fraction of each segment's clusters"; `1.0` allows an exhaustive scan. Clusters that "provably cannot improve the current top-K are skipped", which never reduces recall. (https://www.paradedb.com/docs/documentation/vector/tuning)
- The index is only used when a ParadeDB operator is at the same level as `ORDER BY ... LIMIT`; `pdb.all()` is the documented way to do unfiltered search. Look for `TopKScanExecState` in EXPLAIN. (https://www.paradedb.com/docs/documentation/vector/querying) This matches `api/retrieval.py` `dense()`, which uses `id @@@ pdb.all()`.
- Local `pg_settings` has `paradedb.vector_cluster_max_probe = 0.02` and `paradedb.vector_clustering_threshold = 500` ("Doc-count boundary at which merged segments switch from flat to IVF vector storage").

## Vector index: what EXPLAIN shows (verified, local)

`EXPLAIN (ANALYZE, VERBOSE)` of the `dense()` SQL, strategy `semantic`, LIMIT 50, a stored chunk embedding as the query:

- Plan: `Custom Scan (ParadeDB Base Scan)` on `chunk_semantic`, `Exec Method: TopKScanExecState`, `TopK Order By: embedding <=> vector asc`. The `strategy = 'semantic'` filter is pushed into the Tantivy query as a term.
- `Segment Count: 10`, about 16.6k vectors per segment (166,438 rows).
- Per segment: `candidates_scored` about 1,620 to 1,690, `termination: "Ceiling"` (stopped at the probe ceiling), `exact_rows_read: 0`. Cluster routing is a small graph search over centroids (`routing.graph.visited_count` about 125 to 160, `termination_reason: SearchConverged`).
- Timing: first (cold) run 747 ms; warm repeats 6 to 9 ms.

## Recall spot check (verified, local; method is a proxy)

Script: 30 query vectors, each the sum of two random `semantic` chunk embeddings (not real `search_query:` embeddings). Ground truth = same query at `vector_cluster_max_probe = 1.0`. `1.0` matched a plain seq-scan sort (pdb custom scan off) 50/50 on one check, so `1.0` is exact.

| Filter | probe | recall@50 mean (min) | warm p50 |
| --- | --- | --- | --- |
| none | 0.02 (default) | 0.78 (0.34) | 7.8 ms |
| none | 0.05 | 0.78 (0.34) | 6.2 ms |
| none | 0.2 | 0.90 (0.62) | 11.1 ms |
| none | 1.0 (exact) | 1.00 | 52 ms |
| category = salad | 0.02 to 1.0 | 1.00 | 7 to 9 ms |

- Plain seq scan without the ParadeDB index: about 3.3 s for the same query.

## BM25 (`pg_search`) vs `tsvector` + `ts_rank_cd` + GIN

Verified:

- `pdb.score(id)` "produces a BM25 score". (https://www.paradedb.com/docs/documentation/sorting/score)
- Defaults k1=1.2, b=0.75, tunable per field via `pdb.simple('k1=...')` / `('b=...')`. Source: regression test `pg_search/tests/pg_regress/sql/bm25-params.sql` at tag v0.25.9 (https://github.com/paradedb/paradedb/blob/v0.25.9/pg_search/tests/pg_regress/sql/bm25-params.sql).
- `|||` is match disjunction: a row matches if it has any query token. (https://www.paradedb.com/docs/documentation/full-text/match)
- `pdb.simple` splits on non-alphanumerics and lowercases. (https://www.paradedb.com/docs/documentation/tokenizers/available-tokenizers/simple) `stemmer=english` uses Snowball. (https://www.paradedb.com/docs/documentation/token-filters/stemming) Stopwords are removed only with `stopwords_language=...`, which we don't set. (https://www.paradedb.com/docs/documentation/token-filters/stopwords)
- PostgreSQL: `ts_rank` ranks "based on the frequency of their matching lexemes"; `ts_rank_cd` is cover density, which also weighs how close matches are to each other. "The ranking functions do not use any global information." Length normalization is off by default (flag 0). (https://www.postgresql.org/docs/17/textsearch-controls.html)
- Local tokenizer check on `'The creamy mushrooms, baking 1/2 cup'`:
  - `pdb.simple('stemmer=english')`: `{the,creami,mushroom,bake,1,2,cup}`
  - `to_tsvector('english', ...)`: `'1/2' 'bake' 'creami' 'mushroom' 'cup'`. It drops `the` and keeps `1/2` as one token.

Differences to state in the report:

- Scoring: BM25 has IDF (rare terms count more), term-frequency saturation (k1) and length normalization (b). `ts_rank_cd` has no IDF, no saturation, no length normalization by default, but it does reward proximity.
- Tokens: same Snowball English stemmer on both sides. We keep stopwords, `english` tsvector drops them. The parsers split fractions differently.
- Index: GIN over `tsvector` only finds matching rows, and `ts_rank_cd` then scores each match from its tsvector. The ParadeDB index is a Tantivy inverted index that scores and does top-K inside the index, with the filters pushed down.

## Inference (not verified)

- Recall at 0.02 and 0.05 came out identical, so above some point the per-segment cluster count or skip logic, not the ceiling, may set the work done. I didn't confirm this against source.
- The filtered case hit 1.00 recall. Likely reason: a selective filter leaves few candidates per segment, so the scan covers all of them. `cluster_replication` and the docs' "improve latency/recall for selective queries" point the same way. Tested only on `category = salad`.
- Where the eval's Dense p50 comes from (latest run `eval/runs/20260928-002509`, semantic): total 59 ms = embed 21 ms + dense stage 39 ms. My warm unfiltered LIMIT 50 took 6 to 9 ms. The gap probably comes from the eval's filtered queries, the LIMIT it uses (`chunk_pool` 100), and cold-segment cost (the first query cost 747 ms). Not measured separately.
- The centroid count per segment isn't shown directly. With `centroid_ratio` 0.01 it would be about 166 per 16.6k-vector segment if the ratio applies per segment. The `postings_row` of about 14 doesn't match 2% of that, so the meaning of that EXPLAIN field is unclear.
- Newer ParadeDB work (PR #6391, one global centroid set trained at CREATE INDEX, `paradedb.vector_min_training_rows`) is not in 0.25.9: that GUC isn't in local `pg_settings`, and routing shows up per segment in EXPLAIN. https://github.com/paradedb/paradedb/pull/6391

## For contrast: pgvector's own indexes

- With no index pgvector does exact search. HNSW defaults: `m` 16, `ef_construction` 64, `hnsw.ef_search` 40. IVFFlat: `lists` (rows/1000 suggested), `ivfflat.probes` default 1. Both "trade some recall for speed". (https://github.com/pgvector/pgvector)
- None of these apply to `chunk_search_idx`.
