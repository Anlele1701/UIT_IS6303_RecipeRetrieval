# Pick the case studies and label the every-config misses

Type: task
Status: resolved
Assignee: Tony Trinh
Blocked by:
Parent: ../map.md

## Question

Lock the data "Failure cases and the synthetic-query bias" said a person picks, from the report run `20260928-122309` (semantic for cases):

- Shortlist each of the 5 case buckets by its rule (dense_win, sparse_win, rerank_hurt: in the bucket under all 3 Chunking strategies; rerank_help: Hybrid in the top 5 and above the Fusion baseline on all 3; every-config miss: outside the top 20 for all 4 configs on all 3). Pick one query per bucket, one line on why.
- Label all 29 every-config misses: near-duplicate Recipes, opaque title, lexical trap, or other. Record the counts and check the provisional §6.5 claim (most misses come from the one-correct-Recipe ground truth) against them.
- Map `recipe_id` to titles by position after URL dedupe (1-based), not by `recipe.csv` row.
- Label the 57 hand rewrites (query_id, reason: wrong facts, broken, too vague, copies title, odd wording), proposed from `edited_from` vs `text`. Old totals to check against: 23 / 10 / 10 / 6 / 8, plus 6 swapped twice. Added by "Dataset section stats"; goes into `eval/query_edits.csv` as a build item.
- HITL: the agent builds the shortlists and proposes labels; the human confirms. Picks and labels go in `research/`; the committed `eval/` labels file is a build item.

## Answer

Confirmed as proposed (2026-09-28). Full lists, ranks and runners-up: [research/case-picks-and-labels.md](../research/case-picks-and-labels.md); shortlists from `research/pick_cases.py`.

- Shortlists (all 3 Chunking strategies): dense_win 21, sparse_win 23, rerank_hurt 30, rerank_help 42, every-config miss 29.
- Cases (§6.4, semantic): dense_win q155 (stew vs soup), sparse_win q012 (exact ingredients), rerank_hurt q048 (typical 1-rank swap with a near-duplicate), rerank_help q076 (Fusion baseline misses on all 3, Hybrid first on all 3), every-config miss q066 Wedding Cake (overlap 1.0, opaque title). The rerank_hurt case is picked as typical, not worst, to match the §6 claim; q229 is left to the drill-down.
- Every-config misses (§6.5): near-duplicate 17, opaque title 8, lexical trap 3, other 1. The claim holds narrowly; wording becomes "17 of the 29 are near-duplicates", not "most". Opaque titles are reported as their own cause, not a ground-truth artifact.
- Rewrites (§2.3): wrong facts 25, broken 7, too vague 12, copies title 6, odd wording 7. The report prints these, not the old review totals (23/10/10/6/8), which were never stored per query. "6 swapped twice" can't be recovered from `edited_from`; cite it from the review notes or drop it.
- Stale text: "Dataset section stats" says overlap 0.80 → 0.84; after the accent fix it's 0.85. The bundle computes it, so only the ticket text is off.

Build items: `eval/query_edits.csv` (query_id, reason) and the error-group labels file in `eval/`, both from the lists in the research file.
