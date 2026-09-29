-- Drops the hnsw-dense Ablation run's indexes (see hnsw.sql). Run after runcheck.py passes.
DROP INDEX IF EXISTS chunk_fixed_embedding_hnsw, chunk_semantic_embedding_hnsw, chunk_sentence_embedding_hnsw;
