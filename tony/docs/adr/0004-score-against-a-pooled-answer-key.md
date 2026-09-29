---
status: accepted
---

# Score against a pooled answer key, not one Recipe per query

Each query in the Query set was written from one Recipe, and the first Report run counted only that Recipe as right. A check of all 298 queries found that about half had another Recipe in Hybrid's top 5 that fit the query just as well, so the numbers undercounted every config, and 17 of the 29 queries "every config missed" were near-duplicates rather than failures. We now score against an Answer key (`eval/qrels.csv`). The top 5 of every config, Chunking strategy and Ablation arm were pooled, and each pooled Recipe was judged against its query by an LLM with one strict rule: someone typing the query would be as happy with it as with the written-from Recipe. A query is scored at the rank of its first right Recipe, so every metric keeps its formula.

## Considered Options

- **Pooled answer key (chosen):** fair across configs, because every config's top 5 is judged under the same rule. It is complete only to rank 5, so R@5 is exact while R@10, R@20 and MRR are slight underestimates.
- **Keep one Recipe per query:** simple and fully reproducible, but it measures how often a config finds one exact Recipe, not whether it answers the query. It also hid that most "misses" were right answers.
- **Judge only Hybrid's top 5:** the first check did this. It credits Hybrid's alternatives and none of the other configs', so the comparison leans toward Hybrid.
- **Graded relevance by people:** the strongest option, but out of reach for this project. It stays as future work.

## Consequences

- Retrieval is deterministic, so no search reran. `scripts/rescore.py` rescored every run the report names into `eval/pooled/`; the original runs stay as the single-answer record. A fresh `evaluate.py` run that scores with the answer key itself (the manifest's `check_run`) ranks every query identically.
- `evaluate.py` scores with `eval/qrels.csv` by default; `--qrels none` gives the single-answer scoring.
- A blind re-judge of 120 pairs agreed on 110 (κ 0.83), which is in `eval/qrels_check.json`. The label check of every written-from Recipe is in `eval/label_check.csv`.
- A new config or arm puts Recipes into its top 5 that were never judged. Judge them and add them to `eval/qrels.csv` before comparing, or the new run is scored against a key that never saw its results.
