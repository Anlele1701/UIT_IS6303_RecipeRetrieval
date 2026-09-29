---
status: accepted
---

# Serve Dense retrieval from ParadeDB's index, not pgvector HNSW

The brief asks for HNSW (or IVFFlat) for vectors. We serve Dense retrieval from the `embedding` field inside each partition's one ParadeDB index, which also holds the BM25 fields. ParadeDB builds a cluster (IVF-style) index for it, searched at `vector_cluster_max_probe` 0.02. One engine and one index per partition serves both Sparse and Dense retrieval, and the Report run and every Ablation run were measured on it. Switching the served index would invalidate all of them. pgvector HNSW is measured instead as an Ablation run (`hnsw-dense`), next to exact Dense search (`exact-dense`).

## Considered Options

- **ParadeDB's own vector index (chosen):** one index per partition for text and vectors, and the numbers already measured. It is approximate: at probe 0.02 Dense loses 2.0–3.4 pts R@5 against exact search.
- **pgvector HNSW as the served index:** what the brief names and the usual choice. A second index per partition (~0.5–0.6 GB each), and every run redone.
- **pgvector IVFFlat:** the same cluster idea as ParadeDB's index, so it adds nothing as a contrast.

## Consequences

- The report says Dense is approximate and shows the served index against HNSW and exact search in §5.
- The HNSW index exists only while its Ablation run is measured. Its DDL lives in `sql/ablation/`, outside the init scripts.
- If §5 shows HNSW clearly better at similar latency, switching the served index is a new effort with fresh runs, not a patch.
