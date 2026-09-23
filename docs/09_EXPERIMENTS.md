# 09 — Experiments

All numbers below are produced by
`python -m src.evaluation.run_experiments run --groups A` over
`experiments/queries_v1.json` (300 constructed queries, 4 families of 75)
against 5000 recipes from the `train` split (seed 42, revision `ddfbf91`),
retrieval depth 50. Protocol and caveats: `08_EVALUATION.md`.

## Experiment 1 — Retrieval comparison

| config | R@1 | R@5 | R@10 | R@10 95% CI | MRR | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|
| `bm25` | 0.824 | 0.956 | 0.973 | [0.955, 0.989] | 0.896 | 0.911 | 23.9 | 27.8 |
| `dense` | 0.412 | 0.563 | 0.613 | [0.558, 0.670] | 0.490 | 0.512 | 29.8 | 37.5 |
| `hybrid_rrf` | 0.579 | 0.766 | 0.857 | [0.817, 0.895] | 0.679 | 0.712 | 47.3 | 56.6 |
| `hybrid_rerank` | 0.888 | 0.973 | 0.983 | [0.970, 0.995] | 0.934 | 0.942 | 263.1 | 487.4 |

Paired bootstrap on Recall@10 against `bm25` (2000 resamples):

| comparison | mean diff | 95% CI | p |
|---|---|---|---|
| `dense` vs `bm25` | -0.359 | [-0.416, -0.303] | 0.000 |
| `hybrid_rrf` vs `bm25` | -0.116 | [-0.157, -0.077] | 0.000 |
| `hybrid_rerank` vs `bm25` | +0.011 | [-0.003, 0.027] | 0.155 |

Recall@10 split by query family:

| config | name_kw | ingredient_combo | desc_short | synonym_hard |
|---|---|---|---|---|
| `bm25` | 0.958 | 1.000 | 0.987 | 0.947 |
| `dense` | 0.960 | 0.613 | 0.347 | 0.533 |
| `hybrid_rrf` | 0.974 | 0.853 | 0.880 | 0.720 |
| `hybrid_rerank` | 0.974 | 1.000 | 0.973 | 0.987 |

### What the numbers say

**BM25 is the strongest single stage, and hybrid fusion makes it worse.**
Plain RRF loses 11.6 points of Recall@10 against BM25 alone
(CI excludes zero). RRF weights both input lists equally, so fusing a strong
ranking with a much weaker one pulls the strong one down. This is a property
of the query set as much as of the method: three of the four families are
derived from the indexed text, which is exactly the situation lexical
matching is best at.

**The only configuration that beats BM25 is BM25 plus a reranker**, and even
then the Recall@10 gain is not significant (p = 0.155). The reranker's real
contribution is at the top of the ranking: MRR rises from 0.679 to 0.934 and
R@1 from 0.579 to 0.888 relative to plain hybrid, i.e. it repairs the damage
fusion did to the ordering rather than finding new documents. It costs about
11x the latency of BM25.

**Dense retrieval on its own is weak here, but not uniformly.** It matches
BM25 on `name_kw` (0.960 vs 0.958) and collapses on `desc_short` (0.347).
Experiment 4 explains why: with one combined chunk per recipe, a single
embedding has to represent name, ingredients and description together, and
the description is only about a third of the text. A query derived from the
description is matched against a vector dominated by the ingredient list.

## Experiment 2 — Embedding model comparison

Chunk profile `full_recipe_v1` held fixed; only the embedding profile
changes. All three models are 384-dimensional, so the `vector(384)` column
and the `match_dense` signature are unchanged.

| model | dense R@10 | dense MRR | hybrid R@10 | dense p50 ms |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 0.613 | 0.490 | 0.857 | 29.8 |
| `BAAI/bge-small-en-v1.5` | 0.733 | 0.596 | 0.907 | 31.9 |
| `intfloat/e5-small-v2` | 0.758 | 0.648 | 0.930 | 36.0 |

E5-small-v2 is the best dense encoder on this corpus, 14.5 points of
Recall@10 above the MiniLM baseline for about 6 ms more per query. Both BGE
and E5 are asymmetric models and are indexed with their prescribed prefixes
(`query: ` / `passage: ` for E5, the retrieval instruction on the query side
for BGE); the prefixes are stored on the embedding profile so query encoding
at search time matches how the documents were embedded.

## Experiment 3 — Top-N candidate size for reranking

RRF always fuses over 100 candidates per sub-retriever; only the number
handed to the cross-encoder changes, so the three pools are nested subsets of
one candidate list.

| pool | R@1 | R@10 | MRR | p50 ms | p95 ms |
|---|---|---|---|---|---|
| 20 | 0.861 | 0.927 | 0.898 | 156.1 | 226.1 |
| 50 | 0.888 | 0.983 | 0.934 | 338.7 | 627.0 |
| 100 | 0.888 | 0.987 | 0.934 | 639.9 | 971.8 |

Going from 20 to 50 buys 5.6 points of Recall@10 for 2.2x the latency. Going
from 50 to 100 buys 0.4 points for another 1.9x, and leaves R@1 and MRR
unchanged — the cross-encoder finds nothing new in candidates 51-100. Pool 50
is the operating point; `CONFIG.rerank_candidate_pool` already uses it.

Note that the pool bounds what the configuration can return: at pool 20 no
metric can see past rank 20 regardless of the evaluation depth.

## Experiment 4 — Chunk strategy

See Ablation E in `10_ABLATION_STUDY.md`. Splitting each recipe into one
chunk per field raises dense Recall@10 from 0.613 to 0.801, the single
largest quality change in the whole study, because each field gets its own
vector instead of being averaged into one pooled recipe vector.

## Recording results

```text
experiments/
├── queries_v1.json                     versioned query set + metadata
├── results.csv                         one row per configuration
├── report.md                           generated tables
├── error_cases.md                      generated error-analysis cards
└── runs/
    ├── <config>.json                   metrics + provenance
    └── <config>.per_query.jsonl        per-query rankings and timings
```

Each run records the dataset revision (`ddfbf91`), subset size and seed,
git commit, model names, configuration parameters, the query-set hash, the
metrics, and per-query latency.
