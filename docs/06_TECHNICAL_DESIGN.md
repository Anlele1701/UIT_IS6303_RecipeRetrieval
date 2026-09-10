# 06 — Technical Design

## Module structure

```text
src/
├── data/
│   ├── loader.py          # load ANDREEEWW/recipe-with-images via `datasets`, sample subset
│   └── preprocessing.py   # build searchable text from name+ingredients+description
│
├── retrieval/
│   ├── bm25.py
│   ├── dense.py
│   ├── hybrid.py          # RRF fusion of bm25.py + dense.py rankings
│   └── reranker.py        # cross-encoder over top-N hybrid candidates
│
├── evaluation/
│   ├── queries.py         # generate/load the constructed query + ground-truth set
│   ├── metrics.py         # Recall@K, MRR, nDCG@K
│   └── evaluator.py       # run all retrieval methods over the same query set
│
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
```

Fields are deliberately based on what the dataset actually provides (`name`, `image`) — there is no `metadata` field to carry through (see `03_DATASET.md`, §6.2). `recipe_idx` should be a stable index assigned when the subset is built, not re-derived at query time.

This consistent result shape lets `evaluation/evaluator.py` compare BM25 / Dense / Hybrid / Hybrid+Reranker using the same metric code.
