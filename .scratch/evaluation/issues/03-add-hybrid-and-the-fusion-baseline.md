# 03: Add Hybrid and the Fusion baseline

**What to build:** The Evaluation run gains Hybrid retrieval (RRF + Reranking, as the API serves it) and the Fusion baseline (RRF without Reranking, eval only), so one table compares all four configs and shows what Reranking adds.

Spec: [../spec.md](../spec.md), "Implementation Decisions" (Four configs, Glossary).

**Blocked by:** 02 (First Evaluation run: Sparse and Dense)

**Status:** done

- [x] First, `evaluate.CONFIGS` becomes one record per config (function, uses embedding, stages) so a new config is one entry, not edits to `STAGES`, `USES_EMBEDDING` and the stage checks (ticket 02 review)
- [x] Both configs reuse the existing retrieval functions and the API's candidate and rerank settings, not copies of them
- [x] The reranker loads once before timing. Latency adds RRF and Reranking stages
- [x] A config with fewer than 20 unique Recipes counts the missing positions as misses
- [x] `CONTEXT.md` adds **Fusion baseline**, **Query set** and **Evaluation run**. "Reranking is always part of Hybrid retrieval" still holds for served search
- [x] No API or UI changes
- [x] The end-to-end test covers all four configs with a fake reranker scorer
- [x] A real run of 4 configs × 3 strategies finishes, and the table is pasted into the Done notes

## Done (2026-09-28)

- `evaluate.CONFIGS` is one `EvalConfig(search, stages)` per config. "Uses embedding" is `"embed" in stages`, and a scorer is needed when `"rerank"` is in stages. A new config is one entry.
- No copy of Hybrid. `api/retrieval.py` now has `fused_candidates()` (Sparse + Dense + RRF, cut to `RERANK_TOP`) and `hybrid()` calls it. Both take an optional `watch(stage)` so the eval can time stages. The API passes no `watch`, so served search behaves as before.
- `fusion` = `retrieval.fused_candidates`, `hybrid` = `retrieval.hybrid` with `k=MAX_K`, so the eval gets the full reranked list to dedupe.
- Fusion ranks the same 50 candidates Hybrid reranks. Without that cut, Fusion deduped up to ~100 fused Chunks, and a Recipe in fused Chunks 51 to 100 would count for Fusion but never for Hybrid. That would have shown up as "Reranking hurt" when the real cause was the cut (review finding).
- The reranker loads once in `__main__`, only when a Reranking config runs, before any timing. The warm-up query warms it too.
- Settings add `hybrid_candidates`, `rerank_top`, `rrf_k`, `rerank_model`. Rows add `short_lists`: queries whose list had fewer than 20 unique Recipes. These are already counted as misses, and table.md adds a note when any exist.
- `CONTEXT.md`: **Fusion baseline**, **Query set**, **Evaluation run**. The Hybrid entry is unchanged, so "Reranking is always part of Hybrid retrieval" still holds for served search.
- Tests: the end-to-end test runs all four configs with a fake scorer that puts Toast first, so Hybrid ranks Garlic Shrimp 2nd where Fusion ranks it 1st. It also checks the per-config latency stages. A test with `RERANK_TOP=1` checks that Fusion and Hybrid see the same cut. A test checks that Hybrid without a scorer is refused.

Real run `20260928-002509`: 298 queries, 4 configs, 3 strategies, 658 s.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| sparse | fixed | 0.631 | 0.732 | 0.789 | 0.506 | 0.523 | 0.557 | 19.2 | 29.5 |
| dense | fixed | 0.614 | 0.708 | 0.795 | 0.470 | 0.491 | 0.522 | 70.3 | 113.1 |
| fusion | fixed | 0.644 | 0.758 | 0.859 | 0.507 | 0.525 | 0.561 | 36.4 | 47.3 |
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 621.3 | 1008.6 |
| sparse | semantic | 0.634 | 0.732 | 0.802 | 0.490 | 0.512 | 0.544 | 18.3 | 26.7 |
| dense | semantic | 0.634 | 0.721 | 0.799 | 0.488 | 0.511 | 0.540 | 59.3 | 102.9 |
| fusion | semantic | 0.668 | 0.779 | 0.852 | 0.522 | 0.544 | 0.579 | 35.7 | 46.8 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 633.1 | 962.2 |
| sparse | sentence | 0.641 | 0.732 | 0.805 | 0.488 | 0.513 | 0.543 | 18.5 | 27.8 |
| dense | sentence | 0.607 | 0.698 | 0.789 | 0.475 | 0.494 | 0.524 | 60.2 | 101.3 |
| fusion | sentence | 0.644 | 0.755 | 0.846 | 0.505 | 0.524 | 0.559 | 35.8 | 46.7 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 629.4 | 936.8 |

Queries short of 20 Recipes (counted as misses): 2 each for fixed and semantic, 6 for sentence, under both Fusion and Hybrid.

- Reranking adds about 0.08 to 0.09 R@5 and 0.04 to 0.05 MRR over Fusion under every strategy. It costs about 590 ms p50 (bge-reranker-base on MPS, 50 pairs), roughly 17 times Fusion's total.
- Fusion beats both single retrievers mostly at R@20 (+0.05 to 0.07), and only a little at R@5.
- Fusion is faster than Dense alone (36 vs 60 to 70 ms p50) because each retriever pulls 50 Chunks, not 100.
- Standalone Sparse p50 was 19 ms here vs 7 ms in ticket 02's run. Sparse inside Fusion is ~5 ms. My guess is contention from the reranker running between queries. Not investigated.

Code review (2026-09-28), two axes against `4af7928`:

- Spec: Fusion vs Hybrid pool mismatch, fixed as above. Naming drift: the spec says "Hybrid RRF" but the config is `fusion`. Ticket 04's "Rerank hurt" bucket should compare `hybrid` against `fusion`.
- Standards: a parity test reached into `CONFIGS[...]`, `Query` and `Stopwatch` internals. It's gone now that the eval calls `retrieval.hybrid` directly. Renamed `Query` to `SearchInput` and `Config` to `EvalConfig`, since they clashed with the domain "query" and the `config` module. Kept `stages` doubling as the capability flag (judgement call: one list, and it reads true).
