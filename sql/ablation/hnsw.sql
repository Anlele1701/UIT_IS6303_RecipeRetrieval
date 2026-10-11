-- pgvector HNSW indexes for the hnsw-dense Ablation run (ADR 0003). Not in the init scripts: a fresh DB never
-- gets them, and the served Dense SQL never uses them.
--   docker exec -i recipe-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 < sql/ablation/hnsw.sql
-- Order: build (this file) -> evaluate.py --arm hnsw-dense -> runcheck.py with the indexes present -> drop
-- (sql/ablation/hnsw-drop.sql). Note each build time and size next to the run; evaluate.py records the sizes.

\timing on
SET maintenance_work_mem = '2GB';  -- each index is ~0.5-0.6 GB; this session only
SET max_parallel_maintenance_workers = 0;  -- a parallel build puts the graph in /dev/shm, 64 MB in Docker

CREATE INDEX chunk_fixed_embedding_hnsw ON chunk_fixed
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX chunk_semantic_embedding_hnsw ON chunk_semantic
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX chunk_sentence_embedding_hnsw ON chunk_sentence
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

SELECT relname, pg_size_pretty(pg_relation_size(oid)) AS size
FROM pg_class WHERE relname LIKE 'chunk_%_embedding_hnsw' ORDER BY relname;
