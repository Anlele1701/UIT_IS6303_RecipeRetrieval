# 08 — Evaluation

## Metrics

At minimum:

```text
Recall@5
Recall@10
MRR
nDCG@10
```

Optionally:

```text
Precision@K
Latency
```

## Metric definitions

**Recall@K** — whether the relevant recipe appears within the top K results.

**MRR** — how early the first relevant result appears in the ranking (mean reciprocal rank across queries).

**nDCG@K** — ranking quality, giving more weight to relevant results appearing earlier; useful once graded (not just binary) relevance labels exist.

## Evaluation protocol

All retrieval methods (BM25, Dense, Hybrid, Hybrid + Reranker) must be evaluated using:

- the same subset of the dataset (same corpus)
- the same constructed query set (see `03_DATASET.md`, §6.5)
- the same constructed ground truth
- the same K values

This is required because the dataset has no native ground truth — the query/relevance set is built by the project team, so consistent reuse across methods is the only way to make the comparison fair (see `03_DATASET.md`, §6.5, for how it is built).

## Status

TODO — no evaluation has been run yet. This document defines the protocol; `09_EXPERIMENTS.md` defines what will be run against it, and results should be filled in only after actual runs, never estimated.
