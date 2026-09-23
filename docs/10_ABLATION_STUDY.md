# 10 — Ablation Study

Each ablation changes one thing and holds the rest fixed: same corpus (5000
recipes, seed 42), same query set (`experiments/queries_v1.json`, 300
queries), same depth (50), same tie-breaking. Reproduce with
`python -m src.evaluation.run_experiments run --groups A,B,C,D,E,F,G`;
full tables in `experiments/report.md`.

The baseline configuration is chunk profile `full_recipe_v1`, embedding
profile `minilm_l6_v2_v1`, fusion pool 100, RRF k = 60.

## Ablation A — Sparse vs dense vs hybrid vs rerank

| config          | R@10  | MRR   | nDCG@10 | p50 ms |
| --------------- | ----- | ----- | ------- | ------ |
| `bm25`          | 0.973 | 0.896 | 0.911   | 23.9   |
| `dense`         | 0.613 | 0.490 | 0.512   | 29.8   |
| `hybrid_rrf`    | 0.857 | 0.679 | 0.712   | 47.3   |
| `hybrid_rerank` | 0.983 | 0.934 | 0.942   | 263.1  |

Covered in detail in `09_EXPERIMENTS.md` Experiment 1. Short version: on this
query set lexical retrieval is the strongest single stage, unweighted RRF
degrades it, and the cross-encoder recovers the ordering but not a
significant amount of recall.

## Ablation B — Where the fusion logic lives

Identical RRF, identical inputs, different tier: `retrieval.match_hybrid`
fuses inside Postgres and returns only the final top-k, while
`PythonRRFHybridRetriever` pulls both candidate lists to the service layer
and fuses there.

| config                        | R@10  | MRR   | p50 ms | p95 ms | round trips |
| ----------------------------- | ----- | ----- | ------ | ------ | ----------- |
| `hybrid_rrf` (SQL)            | 0.857 | 0.679 | 47.3   | 56.6   | 1           |
| `hybrid_rrf_python` (service) | 0.857 | 0.679 | 55.5   | 62.2   | 2           |

The rankings are byte-identical: 300/300 queries agree on both top-1 and the
full top-10, verified by
`python -m src.evaluation.run_experiments equivalence hybrid_rrf hybrid_rrf_python`.
Matching them required giving the Python fusion the same tie-break as the SQL
(`fused_score DESC, recipe_idx ASC`); RRF produces exact ties often enough
that without it the two paths disagree on ordering while computing the same
scores.

So the choice is purely operational. Fusing in SQL costs 8 ms less at p50
(-15%), needs one round trip instead of two, and moves 10 rows over the wire
instead of 200. Fusing in the service layer keeps the ranking logic in
application code, where it is easier to unit-test, log and change without a
migration.

The reranker is the opposite case and is deliberately **not** placed in the
database: it runs a cross-encoder over every candidate, which needs batched
model inference and ideally a GPU. Its 263 ms p50 is model time, not query
time, and belongs in a service that can be scaled and batched separately.

## Ablation C — Reranker candidate pool

| pool | R@1   | R@10  | MRR   | p50 ms |
| ---- | ----- | ----- | ----- | ------ |
| 20   | 0.861 | 0.927 | 0.898 | 156.1  |
| 50   | 0.888 | 0.983 | 0.934 | 338.7  |
| 100  | 0.888 | 0.987 | 0.934 | 639.9  |

Diminishing returns past 50: the last 50 candidates add 0.4 points of
Recall@10 and nothing at all to R@1 or MRR, for 1.9x the latency.

## Ablation D — Text representation

Which fields go into the indexed chunk. Chunk profiles `name_only_v1` and
`name_ingredients_v1` (see `sql/005_ablation_profiles.sql`) against the
baseline `full_recipe_v1`.

| fields                           | bm25 R@10 | dense R@10 | hybrid R@10 |
| -------------------------------- | --------- | ---------- | ----------- |
| name                             | 0.367     | 0.348      | 0.355       |
| name + ingredients               | 0.757     | 0.603      | 0.683       |
| name + ingredients + description | 0.973     | 0.613      | 0.857       |

Every field earns its place. Adding ingredients doubles BM25 Recall@10, and
adding the description adds another 21.6 points. Part of that is by
construction — one of the four query families is derived from the
description, another from the ingredients — so the honest reading is that
each field is what makes its own query family answerable, and dropping it
costs roughly the weight of that family.

The interesting asymmetry is dense retrieval: adding the description moves it
by only 1.0 point (0.603 to 0.613) while it moves BM25 by 21.6. The
description is being indexed but not embedded, which is what Ablation E
isolates.

## Ablation E — Chunk representation

`full_recipe_v1` (one combined chunk per recipe) vs `field_chunk_v1` (one
chunk per field, scores aggregated per recipe with MAX so recipes with more
chunks gain no advantage). Embedding profile held fixed.

| config                     | R@10  | MRR   | nDCG@10 | p50 ms |
| -------------------------- | ----- | ----- | ------- | ------ |
| `bm25` / full recipe       | 0.973 | 0.896 | 0.911   | 23.9   |
| `bm25` / field chunk       | 0.987 | 0.937 | 0.945   | 28.9   |
| `dense` / full recipe      | 0.613 | 0.490 | 0.512   | 29.8   |
| `dense` / field chunk      | 0.801 | 0.675 | 0.698   | 39.4   |
| `hybrid_rrf` / full recipe | 0.857 | 0.679 | 0.712   | 47.3   |
| `hybrid_rrf` / field chunk | 0.932 | 0.832 | 0.850   | 62.8   |

**This is the largest single improvement in the study: +18.8 points of dense
Recall@10 for no model change.** The cause is truncation. A combined chunk is
`name + ingredients + description`, and a full recipe ingredient list often
exceeds the 256-token window of MiniLM-L6-v2, so the description — the last
field — is silently dropped before it is ever embedded. Splitting by field
guarantees each field is embedded in full.

BM25 gains too (+1.4 points), for a different reason: a short per-field chunk
has a much smaller length normalisation penalty than a chunk containing an
entire ingredient list.

The cost is 3x the rows (15,000 chunks and embeddings instead of 5,000) and
about 30% more query latency.

## Ablation F — Embedding model

Chunk profile `full_recipe_v1` fixed; only the encoder changes. All three
models are 384-dimensional, so no schema change is required.

| model               | dense R@10 | dense MRR | hybrid R@10 | dense p50 ms |
| ------------------- | ---------- | --------- | ----------- | ------------ |
| `all-MiniLM-L6-v2`  | 0.613      | 0.490     | 0.857       | 29.8         |
| `bge-small-en-v1.5` | 0.733      | 0.596     | 0.907       | 31.9         |
| `e5-small-v2`       | 0.758      | 0.648     | 0.930       | 36.0         |

E5-small-v2 wins by 14.5 points of Recall@10 over the MiniLM baseline for
about 6 ms more per query. Both stronger models are asymmetric and need their
prefixes on the correct side, which is why `retrieval.embedding_profiles`
stores `query_prefix` and `document_prefix` per profile rather than assuming
symmetry.

## Ablation G — RRF constant k

| k            | R@1   | R@10  | MRR   | nDCG@10 |
| ------------ | ----- | ----- | ----- | ------- |
| 20           | 0.586 | 0.943 | 0.712 | 0.762   |
| 60 (default) | 0.579 | 0.857 | 0.679 | 0.712   |
| 120          | 0.576 | 0.843 | 0.672 | 0.703   |

Smaller k helps, by 8.6 points of Recall@10 from 60 down to 20. The constant
controls how quickly `1/(k + rank)` decays: a small k makes the top of each
input list dominate, a large k flattens the contributions so deep positions
in a weak list can outvote the top of a strong one. Because BM25 is far
stronger than dense here, anything that lets the strong list dominate helps.
The widely-copied default of 60 is not a good fit for a pair of retrievers
this unbalanced — weighting the two lists explicitly would be the more direct
fix, and is left as future work.

## Ablation H — Retrieval backend (not run)

`rank_bm25` and FAISS `IndexFlatIP` remain in `src/retrieval/bm25.py` and
`src/retrieval/dense.py` as in-process baselines. Both are exact methods over
the same corpus, so the comparison would measure process-local latency and
operational trade-offs rather than retrieval quality. Not run; recorded here
so the omission is deliberate rather than silent.

## Summary of what matters

Ranked by effect on Recall@10, holding everything else fixed:

1. Which fields are indexed (Ablation D): up to +60.6 points.
2. Chunking per field instead of per recipe (E): +18.8 for dense.
3. Embedding model (F): +14.5 for dense.
4. RRF constant (G): +8.6.
5. Reranker pool 20 to 50 (C): +5.6.
6. Where fusion runs (B): 0.0 — latency and operations only.
