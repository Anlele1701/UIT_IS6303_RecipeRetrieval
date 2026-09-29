# What the conclusion recommends

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by:
Parent: ../map.md

## Question

§7 was left open by "Report outline" and "Latency vs accuracy framing". All main and Ablation numbers are in (`eval/report.json`), except the HNSW arm.

- Which config does §7 recommend, and for which use? For example Hybrid when quality matters and ~0.8 s is fine, the Fusion baseline when latency matters.
- Does any Ablation arm change that (a cheaper cross-encoder, `rerank_top` 20)?
- Which Chunking strategy, given the differences don't reach significance?
- Does §7 wait for the HNSW arm, or say "pending" for it?
- Limits and future work: which ones, one line each.

## Answer

Decided with the human (2026-09-29), from the Report run and the 8 Ablation runs in `eval/report.json`. HNSW not run yet.

Facts behind it (Hybrid arms vs bge-base default, same run, raw p):

- mxbai-rerank-base-v1: R@5 +5.4 to +6.4 pts (p 0.003–0.013), MRR +10 to +12 (p≈0), latency ~1.25×.
- bge-reranker-v2-m3: R@5 +3.7 to +5.0, MRR +7, latency ~3×.
- MiniLM-L6: R@5 +0.3 to +2.0 (n.s.), MRR +3 to +5 (p 0.003–0.05), latency ~0.26×.
- `rerank_top` 20: R@5 n.s., but 294–295 of 298 lists come back with fewer than 20 Recipes. `rerank_top` 100: n.s. on R@5, MRR slightly worse, ~1.6× latency.
- `rrf_k` 10 on the Fusion baseline: R@5 +3 to +4, MRR +1.5 (p≤0.0002), same latency. `rrf_k` 100: no change.
- Hybrid across Chunking strategies: every pair p ≥ 0.34.

Decisions:

- §7 recommends in three tiers, one short row each with R@5 and p50: quality → Hybrid with mxbai-rerank-base-v1 (headline); latency matters → Hybrid with MiniLM-L6 (today's R@5 at about a quarter of the latency); latency critical → Fusion baseline. Arm latency is the same-run ratio applied to the Report run's median p50, per "Latency vs accuracy framing".
- §7 recommends switching the reranker but doesn't do it. Main tables stay on bge-base because it was served when they ran. The switch is a follow-up outside this map.
- Claim strength follows "Significance tests": lead with MRR (survives Holm). R@5 is stated with its Holm-adjusted p from the bundle; if that isn't significant, the wording is "+5–6 pts R@5, not significant after Holm", never "better".
- `rerank_top` stays at 50: 20 breaks the 20-Recipe list, 100 costs more for nothing. `rrf_k` 10 is a one-line note on the Fusion tier, not a Hybrid change.
- Chunking strategy: "no detectable difference, pick on cost". No winner. Strategy is chosen per request, so there's no served default to change.
- HNSW: §7 doesn't wait for it and has no "pending" line. It's a Dense index question (§3, §5). Exact Dense barely moves Hybrid, so it can't change the Hybrid recommendation.
- Limits, one line each: synthetic queries (§6.2 bias); one relevant Recipe per query; short lists counted as misses; one machine, with Hybrid p50 varying ~±15% across Timing repeats (702–973 ms semantic); text-only.
- Future work, one line each: serve mxbai; real user queries with graded relevance; re-time on a GPU, where the reranker latency ranking may change.
