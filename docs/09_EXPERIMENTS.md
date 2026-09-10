# 09 — Experiments

Experiments are defined before running them. No results are reported here yet (TODO — fill in after running, with actual numbers only).

## Experiment 1 — Retrieval comparison

Compare:

```text
BM25
Dense
Hybrid (RRF)
Hybrid + Reranker
```

Research question: which retrieval configuration gives the best retrieval quality on the constructed query set for `recipe-with-images`?

## Experiment 2 — Embedding model comparison

Compare a small number of embedding models (do not use too many):

```text
all-MiniLM-L6-v2
BGE-small
E5-small
```

Compare: retrieval quality, inference time, embedding dimension, resource requirements. Final model selection must be based on this experiment's actual results, not assumed in advance.

## Experiment 3 — Top-N candidate size for reranking

```text
RRF Top-20  → Reranker
RRF Top-50  → Reranker
RRF Top-100 → Reranker
```

Research question: how does candidate pool size affect final retrieval quality and latency?

## Recording results

Following `17.3` reproducibility conventions:

```text
experiments/
├── results.csv
├── bm25.json
├── dense.json
├── hybrid.json
└── reranker.json
```

Each run records: dataset version/commit (`ddfbf91`), subset size and seed, model + version, parameters, query set used, metric, result, execution time.
