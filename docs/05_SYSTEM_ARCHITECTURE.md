# 05 — System Architecture

The architecture stays simple — this is a course project, not a production system.

```mermaid
flowchart TB
    UI[Gradio UI] --> SI[Search Interface]
    SI --> PG[(ParadeDB)]
    PG --> BM25[pg_search BM25]
    PG --> Dense[pgvector cosine]
    BM25 --> RRF[RRF in SQL]
    Dense --> RRF
    RRF --> Reranker
    BM25 --> TopK[Top-k Results]
    Dense --> TopK
    Reranker --> TopK
    TopK --> Img[Recipe Images + Name/Ingredients]
```

## Technology decisions

```text
Language:            Python
Dataset:             Hugging Face Datasets — ANDREEEWW/recipe-with-images
Database:            ParadeDB 0.25.6 / PostgreSQL 17 (Docker)
Sparse Retrieval:    pg_search BM25 (rank_bm25 retained as ablation baseline)
Dense Retrieval:     Sentence Transformers
Vector Search:       pgvector exact cosine (FAISS retained as ablation baseline)
Hybrid:              Reciprocal Rank Fusion (RRF) in SQL
Reranking:           Cross-Encoder in Python
Frontend:            Gradio
```

A separate backend/API service is **not required**. Gradio calls Python
retrievers in-process; they query the local ParadeDB container. Query
embedding and cross-encoder inference remain in Python.

## Data flow at index time

```mermaid
flowchart LR
    HF[HF dataset] --> Sub[Deterministic subset]
    Sub --> Raw[raw.recipes]
    Sub --> ImgStore[Local JPEG files]
    Raw --> Chunk[Versioned chunk profiles]
    Chunk --> BM25idx[ParadeDB BM25 index]
    Chunk --> Emb[Versioned embedding profiles]
    Emb --> Vec[pgvector]
```

`npm run data:migrate` starts ParadeDB, applies numbered SQL migrations,
ingests the subset, creates chunks/embeddings, and validates both sparse and
dense retrieval. The pipeline is idempotent and records each run in
`retrieval.pipeline_runs`.
