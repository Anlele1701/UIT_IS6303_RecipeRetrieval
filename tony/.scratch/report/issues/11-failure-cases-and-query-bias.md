# Failure cases and the synthetic-query bias

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by: 01, 10
Parent: ../map.md

## Question

- Which qualitative cases go in (the brief asks for case studies): e.g. one where Dense rescues a Sparse miss, one where Sparse beats Dense, one rerank_hurt case, one that all configs miss. Pick by rule or by hand?
- How to show the synthetic-query bias: queries were written from their own Recipe, so they share its words. The high/low word-overlap split is ready. Is that the main exhibit, and what does it claim (e.g. R@5 for Sparse falls ~40 pts from high to low overlap, Dense ~19–26)?
- Error categories specific to this dataset, like the old report's §6.4.

## Answer

Facts from the report run (`20260928-122309`), R@5:

| | Sparse − Dense, high overlap | Sparse − Dense, low overlap | Drop high→low: Sparse / Dense / Hybrid |
|---|---:|---:|---:|
| fixed | +8.5 | −5.5 | 40 / 26 / 27 |
| semantic | +9.1 | −9.7 | 39 / 21 / 21 |
| sentence | +13.0 | −6.9 | 39 / 19 / 24 |

- High overlap: 154 queries, low: 144 (split at 1.0, the median).
- Same bucket under all 3 Chunking strategies: sparse_win 23, dense_win 21, rerank_hurt 30, every config misses the top 20: 29. Rescued by Reranking from outside the top 20 into the top 5: 1.
- `recipe_id` is the DB serial id, assigned after `scripts/ingest.py` skips duplicate URLs. It is not the row index of `data/recipe.csv`: a row-index lookup gets 2400 of 3576 target titles wrong. Position after URL dedupe, 1-based, matches all 3576.

Decisions:

- **Cases (§6.4)**: 5. Dense rescues a Sparse miss (dense_win), Sparse beats Dense (sparse_win), one rerank_hurt, one rerank_help, one every-config miss. The §6.3 rerank_hurt case is this one; the rerank_help case balances it. Everything else is left to the per-query drill-down.
- **Selection**: the rule makes a shortlist, a person picks from it and writes one line on why. Rule: the query is in its bucket under all 3 Chunking strategies. rerank_help loosens to "Hybrid in the top 5 and above the Fusion baseline on all 3 strategies", since only 1 query meets the strict rescue rule. Cases are shown on semantic (the search UI's default strategy), with the other two strategies' ranks beside them.
- **Overlap exhibit (§6.2)**: the claim is the sign flip. Sparse leads Dense by 8–13 pts R@5 on high-overlap queries and trails by 5–10 on low-overlap ones. About half the Query set is high overlap, so the headline Sparse vs Dense comparison is tilted toward Sparse. Drop sizes stay in the table as support, not as the claim, because Hybrid also drops 21–27: low-overlap queries are harder for every config. Keep the binary split at 1.0.
- **Error groups (§6.5)**: hand-label the 29 queries every config misses under all 3 strategies into near-duplicate Recipes (top hits are arguably right, e.g. "herb-roasted chicken breast" → "Orange Herb Roasted Chicken"), opaque title (the name doesn't describe the dish: Macarons, Wedding Cake, Salata), lexical trap (one shared word pulls a wrong dish: "cola" → "Coca-Cola Cake"), and other. Labels are a committed file in `eval/` that the bundle script reads. Provisional claim: most every-config misses come from the one-correct-Recipe ground truth, not from retrieval. Ties back to §2.4.
- **Title lookup (amends "Page data contract")**: `scripts/evaluate.py` writes `recipes.csv` (recipe_id, url, title) into the run folder for every Recipe in any top-20 list. The bundle takes titles from there. Case text is joined from `data/recipe.csv` on `url`, never by row position. No second copy of ingest's dedupe rule.

Build items: `recipes.csv` in the run folder from `evaluate.py`; the error-group labels file in `eval/`; `cases` and `error_groups` blocks in the bundle.

New ticket: [Pick the case studies and label the every-config misses](16-pick-cases-and-label-misses.md).
