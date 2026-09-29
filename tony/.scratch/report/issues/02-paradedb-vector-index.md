# What vector index does ParadeDB build for our embeddings?

Type: research
Status: resolved
Blocked by:
Parent: ../map.md

## Question

`sql/indexes.sql` puts `embedding vector_cosine_ops` inside the one `USING paradedb` index, next to the BM25 fields. The brief expects HNSW (or IVFFlat) for vectors and GIN/`tsvector` for text.

- Does that index answer `ORDER BY embedding <=> $1 LIMIT n` with an ANN structure (HNSW?) or an exact scan? Which ParadeDB version are we on, and what does its documentation say?
- If ANN: which build parameters apply (m, ef_construction, ef_search), and is recall below exact a factor to mention?
- How does `pg_search` BM25 differ from the brief's `tsvector` + `ts_rank_cd` + GIN (real BM25 vs a tf-idf-like rank, tokenizer, stemming)?

This feeds the logic placement and system sections, and whether Dense latency (~60 ms p50) can be explained.

## Answer

Full findings and sources: [research/paradedb-vector-index.md](../research/paradedb-vector-index.md).

- Versions: pg_search 0.25.9, pgvector 0.8.4, image `paradedb/paradedb:pg17`. That tag floats.
- The vector part of the `paradedb` index is ANN: ParadeDB's own SPANN-style (IVF-like) cluster index. It is not HNSW and not pgvector's IVFFlat. EXPLAIN shows a top-K scan over 10 segments, each scoring ~1.6k of ~16.6k vectors.
- Build parameters are all at defaults (`centroid_ratio` 0.01, `training_samples_per_centroid` 32, `cluster_replication` 1). Query time: `paradedb.vector_cluster_max_probe` 0.02, where 1.0 is exhaustive.
- Recall proxy (30 synthetic query vectors, unfiltered): recall@50 ~0.78 at default (min 0.34), 0.90 at probe 0.2. Warm latency ~8 ms default, ~52 ms exhaustive. A `category` filter gave 1.00. Not measured on the real Query set, at LIMIT 100, or with the eval's settings.
- BM25: `pdb.score` is real BM25 (Tantivy, k1=1.2, b=0.75). The brief's `ts_rank_cd` has no IDF or length normalization and rewards proximity. Both use the Snowball English stemmer. Ours keeps stopwords.
- Open: why probe 0.02 and 0.05 gave the same recall, and why the eval's dense stage (~39 ms) is slower than the warm test (6–9 ms). Likely filters, LIMIT 100 and cold segments. Not measured.
- New decision surfaced: [What to do about approximate Dense search](12-approximate-dense-search.md).
