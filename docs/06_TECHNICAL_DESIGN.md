# 06 — Technical Design

## Module structure

```text
src/
├── data/
│   ├── loader.py          # load ANDREEEWW/recipe-with-images via `datasets`, sample subset
│   ├── preprocessing.py   # normalize source fields
│   ├── chunking.py        # versioned full-recipe and field chunk strategies
│   ├── ingest_postgres.py # persist recipes and local image paths
│   ├── embed_chunks.py    # persist chunks and versioned vectors
│   └── validate_pipeline.py
│
├── retrieval/
│   ├── bm25.py
│   ├── dense.py
│   ├── hybrid.py          # RRF fusion of bm25.py + dense.py rankings
│   ├── postgres.py        # ParadeDB BM25, pgvector, and SQL RRF
│   └── reranker.py        # cross-encoder over top-N hybrid candidates
│
├── evaluation/
│   ├── queries.py         # generate/load the constructed query + ground-truth set
│   ├── metrics.py         # Recall@K, MRR, nDCG@K
│   └── evaluator.py       # run all retrieval methods over the same query set
│
├── db.py                  # connection and numbered SQL migrations
├── pipeline.py            # npm-invoked indexing pipeline
└── app.py                 # Gradio UI
```

## Search interface

All retrieval methods expose a consistent interface:

```python
def search(query: str, top_k: int = 10, mode: str = "hybrid") -> list[SearchResult]:
    ...
```

## Standard result

Every retrieval method returns a list of:

```text
recipe_idx   # position/id within the sampled subset (dataset has no native id field)
rank
score
name
image
text         # full candidate text used by the cross-encoder
```

Fields are deliberately based on what the dataset actually provides (`name`, `image`) — there is no `metadata` field to carry through (see `03_DATASET.md`, §6.2). `recipe_idx` should be a stable index assigned when the subset is built, not re-derived at query time.

This consistent result shape lets `evaluation/evaluator.py` compare BM25 / Dense / Hybrid / Hybrid+Reranker using the same metric code.

The main application modes use `src/retrieval/postgres.py`. The original
Python BM25/FAISS/RRF modules remain available as experiment baselines.
