# ANN vs exact Dense on the real Query set

Answers the measurement in `issues/12-approximate-dense-search.md`. Run 2026-09-28 against the local `recipe-paradedb` container (`pg_search 0.25.9`, image digest `sha256:8da5d202fe31875af32a49e802ce17cfbc146b0672306f4109809efee1e6f916`).

## Method

- Script: [ann_recall.py](ann_recall.py). Read-only. Calls the API's own `retrieval.dense()` with LIMIT 100 (the eval's `chunk_pool`).
- All 298 queries in `eval/queries.jsonl`, embedded once with `nomic-embed-text` (`search_query:` prefix), shared by every setting.
- For each Chunking strategy, `SET paradedb.vector_cluster_max_probe` to 0.02, 0.05, 0.2 and 1.0. 1.0 is exact (see `paradedb-vector-index.md`).
- Chunk recall = overlap of the ANN top 100 with the exact top 100. Recipe metrics use `metrics.rank_of` (top 20 unique Recipes), same as the eval.
- "Lost" = the known Recipe is in the exact top 20 but not the ANN top 20. "Gained" = the reverse.
- Latency is the `dense()` call only (no embed), one warm-up per setting. The 0.02 p95 on `fixed` (113 ms) includes cold segments, since it ran first.

## Results

| Strategy | probe | Chunk recall@100 mean (min) | recall@50 | R@5 | R@20 | MRR | lost / gained | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|
| fixed | 0.02 | 0.780 (0.38) | 0.800 | 0.614 | 0.795 | 0.470 | 7 / 2 | 18.9 | 113.5 |
| fixed | 0.05 | 0.780 (0.38) | 0.800 | 0.614 | 0.795 | 0.470 | 7 / 2 | 8.8 | 9.9 |
| fixed | 0.2 | 0.888 (0.47) | 0.901 | 0.621 | 0.819 | 0.476 | 0 / 2 | 15.6 | 20.0 |
| fixed | 1.0 | 1.000 | 1.000 | 0.634 | 0.812 | 0.483 | 0 / 0 | 55.5 | 62.6 |
| semantic | 0.02 | 0.784 (0.35) | 0.802 | 0.634 | 0.799 | 0.488 | 8 / 2 | 10.0 | 18.7 |
| semantic | 0.05 | 0.784 (0.35) | 0.802 | 0.634 | 0.799 | 0.488 | 8 / 2 | 8.3 | 13.1 |
| semantic | 0.2 | 0.888 (0.52) | 0.898 | 0.644 | 0.812 | 0.497 | 4 / 2 | 13.1 | 15.0 |
| semantic | 1.0 | 1.000 | 1.000 | 0.654 | 0.819 | 0.497 | 0 / 0 | 49.1 | 52.9 |
| sentence | 0.02 | 0.769 (0.31) | 0.789 | 0.607 | 0.789 | 0.475 | 15 / 7 | 11.5 | 58.5 |
| sentence | 0.05 | 0.769 (0.31) | 0.789 | 0.607 | 0.789 | 0.475 | 15 / 7 | 9.0 | 10.4 |
| sentence | 0.2 | 0.889 (0.44) | 0.902 | 0.638 | 0.826 | 0.486 | 3 / 6 | 16.7 | 19.7 |
| sentence | 1.0 | 1.000 | 1.000 | 0.641 | 0.815 | 0.490 | 0 / 0 | 63.5 | 68.2 |

## Takeaways

- The default ANN (0.02) returns ~78% of the exact top 100 Chunks on real queries, the same as the synthetic spot check.
- Dense pays for it: −2.0 (fixed), −2.0 (semantic), −3.4 (sentence) pts R@5; −1.7 to −2.6 pts R@20. No significance test run.
- The known Recipe drops out of the top 20 in 7–15 queries where exact search keeps it. ANN also finds it in 2–7 queries where exact search doesn't, because a different Chunk set changes the Recipe order.
- 0.05 is identical to 0.02, so the ceiling isn't what limits the work at those values (matches the inference in `paradedb-vector-index.md`).
- Exact costs about +40 to +50 ms per Dense call. That's small next to Hybrid's ~630 ms, but it roughly doubles Dense.
- Not measured: the effect on the Fusion baseline and Hybrid (the Hybrid pool is 50 per retriever, then RRF and Reranking). The exact-Dense ablation arm measures that.
