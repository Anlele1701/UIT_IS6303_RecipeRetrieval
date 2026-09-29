# Clean Evaluation run on a committed tree

Type: task
Status: resolved
Assignee: Tony Trinh
Blocked by:
Parent: ../map.md

## Question

Produce the Evaluation run whose numbers the report will use.

- Pin the ParadeDB image in `docker-compose.yml` to `paradedb/paradedb@sha256:8da5d202fe31875af32a49e802ce17cfbc146b0672306f4109809efee1e6f916` (`pg_search 0.25.9`) and commit it first (ask before committing). See "What to do about approximate Dense search".
- Make `settings.json` record the `pg_search` version and `paradedb.vector_cluster_max_probe` (stays at the default 0.02).
- Clean working tree on current `main` (the Hybrid, failure-analyzer and README commits all landed after `4af7928`).
- Run the full eval: 4 configs × every loaded Chunking strategy, 298 queries, default settings. Then `scripts/failures.py` on it.
- Check `settings.json` records the new commit.
- Diff `metrics.json` against `eval/runs/20260928-002509`. Record any metric that moved, and by how much. If none moved, say so: that confirms the old run was already on the final code.
- Keep the folder with `git add -f` (ask before committing).

Record in the answer: run folder name, commit, wall time, and the diff.

## Answer

- Run folder: `eval/runs/20260928-122309`, committed in `2cb6c50`. This is the report run.
- Recorded commit: `466b46a` (ParadeDB pinned by digest; `settings.json` now records `pg_search_version` 0.25.9 and `vector_cluster_max_probe` 0.02). The digest matched the image already running, so no data changed.
- Wall time: 757.7 s (the old run took 657.7 s).
- `failures.md` was written by `scripts/failures.py`. It's identical to the old run's.
- Diff against `20260928-002509`:
  - No metric moved. All 3,576 per-query ranks and top-20 lists are identical. The old run was already on the final retrieval code; only its commit label was wrong.
  - Latency moved. Hybrid p50 went up ~20% (621→751 ms fixed, 633→757 semantic, 629→758 sentence) and p95 went from ~1.0 to ~1.2 s. It's all in the Reranking stage (584→714 ms p50 on fixed). Dense p50 dropped 8–15 ms. Sparse and the Fusion baseline were within ±4 ms.
- Consequence: same code and data, but the reranker's latency moved 20% between runs on the same day, so one run's latency isn't stable enough to report on its own. Added to "Latency vs accuracy framing".
- Side finding: `.venv` was copied from `UIT_IS6303_RecipeRetrieval/tony`, so `uv run pytest` fails (bad shebang). `uv run python -m pytest` works. Fix with `uv sync --reinstall`.
