# 02 — Requirements

## Functional requirements

### FR-01 — Text Search

The system shall accept a free-text query.

```text
"chicken with mushroom"
"quick vegetarian breakfast"
"spicy Moroccan salad"
```

### FR-02 — Retrieval

The system shall retrieve the most relevant recipes from `ANDREEEWW/recipe-with-images` given a text query.

### FR-03 — Top-k

The system shall return a configurable top-k number of results (default e.g. 10).

### FR-04 — Image Display

The system shall display the recipe image(s) corresponding to retrieved items, alongside the recipe name and (optionally) ingredients/description.

### FR-05 — Retrieval Method Selection

The system should support switching between:

```text
BM25
Dense Retrieval
Hybrid Retrieval
Hybrid + Reranking
```

### FR-06 — Evaluation

The system shall support offline evaluation using standard retrieval metrics (Recall@K, MRR, nDCG@K) over a constructed query/ground-truth set (see `03_DATASET.md`, §6.5).

## Non-functional requirements

- Easy to run locally (single Python environment, no external services required).
- Reproducible experiments (fixed dataset subset, fixed seeds, logged configs).
- Reasonable execution time on a laptop/course-project budget (subset of the dataset, not necessarily the full 52,007 rows).
- Simple user interface (Gradio).
- Clear separation between preprocessing, retrieval, evaluation, and UI code.

## Traceability

| Requirement | Addressed in |
|---|---|
| FR-01, FR-04 | `05_SYSTEM_ARCHITECTURE.md`, `06_TECHNICAL_DESIGN.md` |
| FR-02, FR-03 | `06_TECHNICAL_DESIGN.md`, `07_RETRIEVAL_METHODS.md` |
| FR-05 | `04_SEARCH_CONCEPT.md`, `07_RETRIEVAL_METHODS.md` |
| FR-06 | `08_EVALUATION.md`, `09_EXPERIMENTS.md` |
