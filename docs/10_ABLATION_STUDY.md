# 10 — Ablation Study

Identifies the contribution of each component. No results reported yet (TODO — fill in after running).

## Ablation A — Sparse vs Dense

```text
BM25
vs
Dense
```

Question: does semantic retrieval outperform lexical retrieval on this dataset's queries?

## Ablation B — Hybrid contribution

```text
BM25
Dense
BM25 + Dense (RRF)
```

Question: does combining lexical and semantic retrieval improve results over either alone?

## Ablation C — Reranker contribution

```text
Hybrid
vs
Hybrid + Reranker
```

Question: does reranking improve final ranking quality over hybrid alone?

## Ablation D — Text representation

Configurations (updated from the original CMIngre template to match this dataset's actual fields — there is no separate `metadata` field here, see `03_DATASET.md` §6.2):

```text
Name only
Name + Ingredients
Name + Ingredients + Description
```

Question: which combination of `name`, `ingredients`, and `description` contributes most to retrieval quality?

## Ablation E — Chunk representation

```text
full_recipe_v1 (one combined chunk per recipe)
vs
field_chunk_v1 (name / ingredients / description chunks, MAX score per recipe)
```

Keep the embedding profile fixed while changing the chunk profile. This
isolates the effect of chunking and avoids giving recipes with more chunks an
unfair advantage.

## Ablation F — Retrieval backend

```text
Python rank_bm25 vs ParadeDB pg_search BM25
FAISS IndexFlatIP vs pgvector exact cosine
Python RRF vs SQL RRF
```

Use the same corpus, chunk profile, embeddings, query set, candidate pool,
and tie-breaking rules. Backend comparisons primarily measure latency and
operational trade-offs; exact vector backends should have nearly identical
retrieval quality.
