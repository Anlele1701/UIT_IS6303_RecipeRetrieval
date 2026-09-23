# IS6303_RecipeImageRetrieval

Skeleton README — to be filled in once experiments have run. Full design docs live in `docs/01_PROJECT_OVERVIEW.md` through `docs/13_README_SPECIFICATION.md`; this file only summarizes.

## Overview

Semantic search system: free-text query -> top-k recipe images, over the [`ANDREEEWW/recipe-with-images`](https://huggingface.co/datasets/ANDREEEWW/recipe-with-images) dataset. See `docs/01_PROJECT_OVERVIEW.md`.

## Problem

See `docs/01_PROJECT_OVERVIEW.md` §1.1–1.2.

## Dataset

`ANDREEEWW/recipe-with-images` — fields: `image`, `name`, `ingredients`, `description`. Train 36,404 / test 15,603 rows. No native ground truth or category label. Full details: `docs/03_DATASET.md`.

## System Architecture

See `docs/05_SYSTEM_ARCHITECTURE.md`.

## Retrieval Methods

- **BM25** — `src/retrieval/bm25.py`
- **Dense Retrieval** — `src/retrieval/dense.py`
- **Hybrid Retrieval (RRF)** — `src/retrieval/hybrid.py`
- **Reranking** — `src/retrieval/reranker.py`

Details: `docs/07_RETRIEVAL_METHODS.md`.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Dataset Setup

The source dataset is downloaded/cached by Hugging Face Datasets. The
retrieval corpus, versioned chunks, and embeddings are stored in local
ParadeDB (Postgres + `pg_search` + `pgvector`).

```bash
npm run data:migrate
```

This starts the pinned ParadeDB Docker image, applies SQL migrations, ingests
the deterministic subset, creates embeddings, and validates sparse/dense
search. The default local connection is
`postgresql://recipe:recipe@localhost:5432/recipes`; override it with
`DATABASE_URL`.

## Usage

### Run Gradio

```bash
python -m src.app
```

### Text Search

```python
from src.retrieval.postgres import PostgresSparseRetriever

bm25 = PostgresSparseRetriever()
results = bm25.search("quick vegetarian breakfast", top_k=10)
```

## Evaluation

The dataset ships no retrieval ground truth, so the query set is constructed
by the project team: 300 queries in four families (recipe name keywords,
discriminative ingredient combinations, shortened descriptions, and
ingredient combinations rewritten with synonyms), versioned at
`experiments/queries_v1.json`. Construction and its limitations:
`docs/08_EVALUATION.md`.

```bash
npm run eval:queries   # rebuild the query set from the indexed corpus
npm run eval:all       # run every configuration, then error analysis
npm run eval:report    # regenerate tables from cached runs
```

Outputs land in `experiments/`: `results.csv`, `report.md`,
`error_cases.md`, and one JSON summary plus per-query JSONL per
configuration under `runs/`.

## Results

5000 recipes (`train`, seed 42, revision `ddfbf91`), 300 queries, depth 50.

| config | R@1 | R@10 | R@10 95% CI | MRR | nDCG@10 | p50 ms |
|---|---|---|---|---|---|---|
| BM25 | 0.824 | 0.973 | [0.955, 0.989] | 0.896 | 0.911 | 23.9 |
| Dense | 0.412 | 0.613 | [0.558, 0.670] | 0.490 | 0.512 | 29.8 |
| Hybrid (RRF) | 0.579 | 0.857 | [0.817, 0.895] | 0.679 | 0.712 | 47.3 |
| Hybrid + Reranker | 0.888 | 0.983 | [0.970, 0.995] | 0.934 | 0.942 | 263.1 |

BM25 is the strongest single stage: the constructed queries are derived from
the indexed text, and in a 5000-recipe corpus one rare ingredient term is
almost a unique key. Unweighted RRF makes it worse (-11.6 points of
Recall@10) by giving a much weaker dense list equal vote; the cross-encoder
then repairs the ordering (MRR 0.679 to 0.934) without a significant recall
gain over BM25 alone (p = 0.155). Details and caveats:
`docs/09_EXPERIMENTS.md`.

## Ablation Study

Seven ablations, one variable each; full tables in
`docs/10_ABLATION_STUDY.md`. The largest effects:

- **Indexed fields** — name only 0.367, name + ingredients 0.757, all three
  fields 0.973 Recall@10 for BM25.
- **Chunk strategy** — one chunk per field instead of one per recipe lifts
  dense Recall@10 from 0.613 to 0.801, because a single pooled embedding per
  recipe is dominated by the longest field.
- **Embedding model** — `e5-small-v2` 0.758 > `bge-small-en-v1.5` 0.733 >
  `all-MiniLM-L6-v2` 0.613, all 384-dimensional so no schema change.
- **Where fusion runs** — RRF in SQL and RRF in the service layer produce
  identical rankings on 300/300 queries; SQL is 15% faster at p50 with one
  round trip instead of two. The cross-encoder stays out of the database on
  purpose.

## Error Analysis

`python -m src.evaluation.error_analysis` selects cases from the saved
per-query records; interpretation in `docs/11_ERROR_ANALYSIS.md`. Dense
retrieval contributes something BM25 missed on only 2 of 300 queries, RRF
never drops a document both inputs found, and the single query that every
configuration misses combines a synonym substitution with a diluted pooled
embedding.

## Project Structure

```text
docs/            13 design documents (01-13)
sql/             numbered ParadeDB schema/index/search migrations
src/
├── config.py
├── db.py
├── pipeline.py
├── data/
│   ├── loader.py
│   ├── preprocessing.py
│   ├── chunking.py
│   ├── ingest_postgres.py
│   ├── embed_chunks.py
│   └── validate_pipeline.py
├── retrieval/
│   ├── base.py
│   ├── bm25.py
│   ├── dense.py
│   ├── hybrid.py
│   ├── postgres.py
│   └── reranker.py
├── evaluation/
│   ├── metrics.py          Recall/MRR/nDCG + bootstrap significance tests
│   ├── queries.py          constructed query set and ground truth
│   ├── evaluator.py        per-query records, metrics, latency
│   ├── run_experiments.py  configuration registry, runner, report tables
│   └── error_analysis.py   case selection for docs/11
└── app.py
experiments/     query set, per-run metrics and rankings, generated tables
docker-compose.yml
package.json
requirements.txt
```

## Team

TODO

## References

- Dataset: https://huggingface.co/datasets/ANDREEEWW/recipe-with-images
