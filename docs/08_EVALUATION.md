# 08 — Evaluation

## Metrics

Reported for every configuration:

```text
Recall@1, Recall@5, Recall@10
MRR (over the retrieved depth)
nDCG@10
Latency p50 / p95, split into query-encoding and search time
```

**Recall@K** — the share of relevant recipes inside the top K. Almost every
query has exactly one relevant recipe, so in practice this is a hit rate.

**MRR** — how early the first relevant result appears, averaged over queries.

**nDCG@10** — ranking quality with position discounting.

Recall@10 carries a 95% percentile-bootstrap confidence interval, and
configurations are compared against each other with a paired bootstrap over
per-query differences (`src/evaluation/metrics.py`). With 300 queries a gap
of one or two points is inside the noise floor, so a bare mean is not enough
to claim a configuration is better.

## Ground truth

The dataset has no native retrieval ground truth (see `03_DATASET.md` §3.5),
so the query set is constructed by the project team and versioned at
`experiments/queries_v1.json` (300 queries, seed 42). It is built by
`src/evaluation/queries.py` directly from `raw.recipes`, which guarantees the
queries are labelled against exactly the documents that are indexed.

Queries come in four families of 75, from disjoint source recipes:

| family | how the query is built |
|---|---|
| `name_kw` | recipe title, stopwords and serial numerals removed |
| `ingredient_combo` | the 4 most discriminative ingredient terms of the recipe |
| `desc_short` | description, truncated to 12 words, with title words removed |
| `synonym_hard` | `ingredient_combo` with at least two terms swapped for synonyms absent from the source recipe |

Ingredient terms are extracted by stripping quantities, units, preparation
words and sub-headers from each ingredient line. Terms are then filtered by
corpus document frequency: pantry staples (present in over 10% of recipes)
and terms unique to a single recipe are both dropped, so a query is neither
generic noise nor a trivially unique key.

The labelled recipe is the one the query was derived from. Recipes whose
ingredient sets overlap the source with Jaccard ≥ 0.8 are added as also
relevant (8 of 300 queries), so a duplicated dish is not scored as an error.

### Limitations of this ground truth

These must be stated in the report; they shape every number in
`09_EXPERIMENTS.md`.

1. **Lexical bias.** Three of the four families are derived from the text
   that is indexed, so a lexical matcher sees near-verbatim overlap. This is
   why BM25 scores so high, and why the per-family split matters more than
   the average.
2. **`synonym_hard` does not fully remove that bias.** Swapping 2 of 4 terms
   still leaves one or two rare ingredients, and in a 5000-recipe corpus one
   rare ingredient is almost a unique key — BM25 still reaches Recall@10
   0.947 on this family.
3. **Single-label relevance.** For a generic query such as `sugar cookies`
   the corpus holds many equally valid recipes, but only the source recipe
   counts as correct. Some recorded misses are labelling gaps rather than
   retrieval failures; `experiments/error_cases.md` surfaces them for manual
   review.

## Evaluation protocol

All configurations are evaluated by `src/evaluation/run_experiments.py` on:

- the same corpus (5000 recipes, `train`, seed 42, revision `ddfbf91`)
- the same query set file and the same constructed relevance labels
- the same retrieval depth (50) and the same K values
- the same tie-breaking (`score DESC, recipe_idx ASC`, applied in both the
  SQL functions and the Python fusion)

Three warm-up queries run before timing starts, so lazy model loading and
cold caches are not charged to whichever configuration runs first. Image
loading is disabled during evaluation (`load_images=False`): decoding a JPEG
per candidate costs more than the retrieval itself at a pool of 100 and would
dominate the latency comparison.

Each run writes `experiments/runs/<config>.json` (metrics plus provenance:
git commit, dataset revision, subset size and seed, model names, parameters)
and `experiments/runs/<config>.per_query.jsonl` (the ranking, the rank of the
labelled recipe, and split timings for every query). Tables are regenerated
from those files with `run_experiments report`, without re-running retrieval.

## Results

See `09_EXPERIMENTS.md` for the main comparison, `10_ABLATION_STUDY.md` for
the ablations, and `experiments/report.md` for the generated tables.
