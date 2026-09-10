# 13 — README Specification

The final README is generated after the other documentation is stable and after real experiments have run. It summarizes; it is not the source of truth for design decisions (those live in `01`–`12`).

## Required README structure

```text
# IS6303_RecipeImageRetrieval

## Overview
## Problem
## Dataset            (ANDREEEWW/recipe-with-images — real fields/sizes from 03_DATASET.md)
## System Architecture
## Retrieval Methods
### BM25
### Dense Retrieval
### Hybrid Retrieval
### Reranking
## Installation
## Dataset Setup
## Usage
### Run Gradio
### Text Search
## Experiments
## Results             (only real numbers from actual runs)
## Ablation Study
## Error Analysis
## Project Structure
## Team
## References
```

It should answer:

1. What is this project?
2. What problem does it solve?
3. What dataset does it use (name, size, fields — no invented ones)?
4. How does the system work?
5. How do I install it?
6. How do I run it?
7. What retrieval methods are implemented?
8. What are the results (real, not estimated)?
9. What are the limitations (including: no native ground truth, constructed evaluation set, no cuisine label)?

Keep it concise and practical; verify every shell command in it is actually runnable before publishing.
