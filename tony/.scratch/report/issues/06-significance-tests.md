# Significance tests

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by:
Parent: ../map.md

## Question

The old report used a 95% percentile bootstrap CI on Recall@10 and a paired bootstrap on per-query differences. Chunking strategy differences here are ~1 pt on 298 queries, likely noise. Hybrid vs Fusion baseline is +7–9 pts R@5.

- Test or not? If yes, which method (paired bootstrap, permutation, McNemar on hit/miss at k)?
- Which comparisons (Hybrid vs Fusion baseline, Sparse vs Dense, every Chunking strategy pair, ablation arms vs default), and which metrics?
- Multiple comparisons: correct for them or not?
- Where it's computed (the eval script, a separate script, or the page) and what gets stored in the run folder for the page to show.

## Answer

- Test, yes. Without it the Chunking strategy claim in §4 is a guess. Caveat for the report: resampling queries generalises only to queries like the synthetic Query set, not to real users (ties to the query bias in §6).
- Method: paired bootstrap on per-query differences, 10,000 resamples, 95% percentile CI on the difference, two-sided p from the share of resamples on the far side of 0. Paired works because `per_query.csv` has the known Recipe's rank for every config × Chunking strategy × query, and all configs see the same 298 queries.
- Also a plain bootstrap CI on each config's own R@5 and MRR, shown in the main results table.
- Comparisons, a fixed list (15), plus one per ablation arm:
  - per Chunking strategy: Hybrid vs Fusion baseline, Fusion baseline vs Sparse, Fusion baseline vs Dense, Sparse vs Dense (4 × 3);
  - Chunking strategy pairs under Hybrid only (3);
  - each ablation arm vs its default, same method.
- Metrics tested: R@5 and MRR. R@10/20 and nDCG appear in tables without CIs.
- Multiple comparisons: Holm over every test in the report, α 0.05. Store raw and adjusted p. CIs stay unadjusted and are labelled that way.
- Where: a separate `scripts/significance.py`, like `scripts/failures.py`. Reads a run's `per_query.csv`, writes `significance.json` into the run folder with the seed and resample count. Works on old runs without re-running the eval. The page only reads it. Exact JSON shape goes to "Page data contract". Writing the script is a build item for the spec, not work on this map.
- Wording: a non-significant gap is "no detectable difference at this sample size", with the CI next to it (e.g. "+0.9 pts, 95% CI −2.6 to +4.4"). Never "the same". Expected for Chunking strategy pairs: a 1 pt gap is ~3 net queries, and the CI is roughly ±3–4 pts. §4 then picks a Chunking strategy on other grounds (latency, Chunk count).

## Amendment

[How ablation runs and timing repeats are stored](15-run-storage.md): the Holm family spans the Report run and 8 Ablation runs, so no one folder can adjust it. `significance.json` stores raw p only; the bundle script applies Holm over every test in the runs the manifest names. Arm tests compare the arm with its default inside the same Ablation run.
