# Latency vs accuracy framing

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by: 01, 06
Parent: ../map.md

## Question

Hybrid is ~630 ms p50 against ~36 ms for the Fusion baseline, for +7–9 pts R@5. How does the report present that trade-off?

- What's shown: a scatter (p50 vs R@5/MRR per config and Chunking strategy), the per-stage breakdown (embed, Sparse, Dense, RRF, Reranking), p95 as well as p50.
- What's claimed: a recommendation per use (interactive search vs best quality), and whether the gain is significant.
- Caveats: measured on one M-series laptop, MPS reranker, one query at a time, one warm-up.
- Run-to-run variance: the clean run's Hybrid p50 was 751 ms vs 621 ms in the previous run, on the same code and data (all Reranking; see "Clean Evaluation run on a committed tree"). Repeat the timing (e.g. 3 runs, median) or report latency as a range?

## Answer

Two measurement problems found in the report run first:

- Run-to-run drift: Reranking p50 moved ~20% between runs on the same code (see "Clean Evaluation run on a committed tree").
- Stage times aren't comparable across configs. Solo Dense is 55 ms p50 vs 39 ms for the Fusion baseline, which also runs Dense. Two causes in `scripts/evaluate.py`: solo Sparse/Dense pull `POOL` = 100 Chunks while Fusion and Hybrid pull `HYBRID_CANDIDATES` = 50, and each query runs configs in a fixed order (sparse, dense, fusion, hybrid), so later configs hit a warm cache. Dense's stage is 32 ms solo vs 11 ms inside Fusion.

Decisions:

- Timing repeats: 3 timing repeats of the report run on the report commit. Accuracy comes from the report run (ranks are deterministic). Latency is the median p50/p95 across repeats, with min–max shown as a range. Running them is a build item.
- Measurement fix (build item): rotate config order per query. Keep the pool sizes (they affect metrics) and note the difference in §3.
- Headline comparison is Fusion baseline vs Hybrid totals. Per-stage breakdown shown for Hybrid only (Reranking is ~95% of it: embed 21, Sparse 5–6, Dense 10–11, RRF 0, Reranking ~714 ms p50 on fixed).
- §4.3 claim: "Hybrid costs ~20x the latency for +7–9 pts R@5; worth it when quality matters and ~0.75 s is acceptable", with the significance CI on the R@5 gain. The per-use recommendation stays in §7 (conclusion fog).
- Percentiles and metric: p50 as the point, p95 as a whisker (Hybrid's tail is 1.1–1.2 s). Latency is plotted against R@5 only; MRR stays in the table. Chart form goes to "Page layout and charts".
- Caveats in §3: one M-series laptop, reranker on MPS, one query at a time, one warm-up, the pool-size difference.
- §4.3 points to §5 for cheaper Reranking (MiniLM-L6 arm, `rerank_top` 20). A hosted reranker API goes in §7.4 future work, named and not measured (it adds a network hop and sends queries to a third party).
- Ablation latency: one run per arm, with the arm and the default config interleaved in that run. Report the arm's latency as a ratio to the default measured in the same run (e.g. "Reranking 0.2x bge-base"). Absolute ms go in the table, labelled same-run.
- Where the timing repeats are stored is not decided here. It joins "How ablation runs and timing repeats are stored".

## Amendment

[How ablation runs and timing repeats are stored](15-run-storage.md): the Timing repeats can't run "on the report commit", because config-order rotation is a code change. They run on the commit that has rotation, as 3 full run folders; the bundle fails unless their ranks equal the Report run's. The Report run's own latency is not used.

## Amended by "Page layout and charts" (2026-09-29)

With the 3 Timing repeats, the ratio is ~17× (Hybrid ~800 ms vs Fusion baseline ~47 ms median p50), not ~20×. The bundle computes it.
