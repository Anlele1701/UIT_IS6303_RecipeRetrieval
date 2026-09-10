# 07 — Retrieval Methods

Four configurations to be evaluated, all operating over the searchable text built from `name + ingredients + description` (see `03_DATASET.md`).

## 7.1 BM25

```mermaid
flowchart LR
    Q[Query] --> B[BM25] --> K[Top-k]
```

Purpose: baseline sparse/lexical retrieval.

## 7.2 Dense Retrieval

```mermaid
flowchart LR
    Q[Query] --> E[Text Encoder] --> V[Embedding] --> S[Vector Search] --> K[Top-k]
```

Purpose: evaluate semantic similarity, e.g. matching "vegetarian breakfast" to a yogurt bowl recipe with no literal keyword overlap.

## 7.3 Hybrid Retrieval

```mermaid
flowchart TB
    Q[Query] --> B[BM25] --> RA[Rank A]
    Q --> D[Dense] --> RB[Rank B]
    RA --> RRF[RRF]
    RB --> RRF
    RRF --> K[Top-k]
```

Purpose: combine lexical (exact ingredient/name terms) and semantic signals.

## 7.4 Hybrid + Reranker

```mermaid
flowchart LR
    Q[Query] --> H[BM25 + Dense] --> RRF[RRF] --> N[Top-N candidates] --> CE[Cross-Encoder] --> K[Final Top-k]
```

Purpose: test whether a more expensive second-stage reranker improves retrieval quality over hybrid alone. Candidate pool size N (20/50/100) is varied in Experiment 3 (`09_EXPERIMENTS.md`).
