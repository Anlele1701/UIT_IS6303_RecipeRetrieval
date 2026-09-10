# 12 — Implementation Plan

## Phase 1 — Repository

```text
Create repository
Create environment
Create project structure
Create README skeleton
```

## Phase 2 — Dataset

```text
Load ANDREEEWW/recipe-with-images via `datasets` library
Confirm schema (image, name, ingredients, description)
Select subset (fixed seed; diversity spot-check since no cuisine label exists)
Clean/normalize ingredients text
Build searchable text (name + ingredients + description)
```

## Phase 3 — BM25

```text
Build corpus from searchable text
Build BM25 index
Implement search()
Evaluate
```

## Phase 4 — Dense

```text
Select embedding model (Experiment 2)
Encode corpus
Build FAISS index
Implement search()
Evaluate
```

## Phase 5 — Hybrid

```text
Retrieve BM25 candidates
Retrieve dense candidates
Apply RRF
Evaluate
```

## Phase 6 — Reranking

```text
Retrieve Top-N (Experiment 3)
Apply Cross-Encoder
Return Top-k
Evaluate
```

## Phase 7 — UI

```text
Build Gradio app
Add query input
Add retrieval-mode selector (BM25/Dense/Hybrid/Hybrid+Reranker)
Add Top-k selector
Display recipe images + name
```

## Phase 8 — Experiments

```text
Build constructed query/ground-truth set (03_DATASET.md §6.5)
Run all four retrieval configurations
Run ablations
Collect metrics
Analyze errors
```

## Phase 9 — Finalization

```text
Freeze implementation
Write report (fill actual results into 08/09/10/11)
Prepare slides
Prepare demo
```
