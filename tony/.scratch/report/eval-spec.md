# Eval spec: Timing repeats and Ablation runs

Part 1 of the map's destination. Everything here was decided in closed tickets; this file only gathers it and orders the work. Part 2 (the page spec) waits on "Page layout and charts" and doesn't block this.

Sources: "How ablation runs and timing repeats are stored", "Which ablations to run", "What to do about approximate Dense search", "Latency vs accuracy framing", "Significance tests", "Explaining rerank_hurt", "Failure cases and the synthetic-query bias", "Dataset section stats", "Pick the case studies and label the every-config misses".

## Critical path

Only step 1 blocks running. Steps 3–4 read finished run folders, so they can be built while runs go.

1. `evaluate.py` changes (below), with tests. Commit. This is the "rotation commit".
2. Runs on that commit: 3 Timing repeats, then 8 Ablation runs.
3. `significance.py`, `failures.py` additions, labels files. Run over the folders.
4. Manifest `eval/report.json`.

Rough runtime (estimate from the Report run's 758 s and stage p50s): each Timing repeat ~13 min; Ablation runs ~2–3 h in total, bge-reranker-v2-m3 and `rerank-top-100` the longest. Inside the 8 h budget.

## 1. `scripts/evaluate.py` (and a small `api/retrieval.py` change)

### Knobs as arguments, not globals

Today `fused_candidates` reads `config.HYBRID_CANDIDATES` / `config.RERANK_TOP` and `rrf()` binds `k=config.RRF_K` at def time, so one process can't run two values side by side.

- `retrieval.rrf`, `fused_candidates` and `hybrid` take `rrf_k`, `rerank_top` as keyword args defaulting to the `config` values. The served API passes nothing, so its behaviour doesn't change (retrieval changes stay out of scope).
- `RRF_K` becomes env-settable like the others, for parity.

### Arms

```python
ARMS = {
    "reranker-minilm-l6":  {"configs": ["hybrid"], "set": {"rerank_model": "cross-encoder/ms-marco-MiniLM-L6-v2"}},
    "reranker-mxbai-base": {"configs": ["hybrid"], "set": {"rerank_model": "mixedbread-ai/mxbai-rerank-base-v1"}},
    "reranker-bge-v2-m3":  {"configs": ["hybrid"], "set": {"rerank_model": "BAAI/bge-reranker-v2-m3"}},
    "rrf-k-10":            {"configs": ["fusion"], "set": {"rrf_k": 10}},
    "rrf-k-100":           {"configs": ["fusion"], "set": {"rrf_k": 100}},
    "rerank-top-20":       {"configs": ["hybrid"], "set": {"rerank_top": 20}},
    "rerank-top-100":      {"configs": ["hybrid"], "set": {"rerank_top": 100}},
    "exact-dense":         {"configs": ["dense", "fusion", "hybrid"], "set": {"probe": 1.0}},
}
```

- `--arm <key>` runs each listed config twice per query, as `default` and `arm`, on all 3 Chunking strategies. No free-form overrides.
- Reranker arms load both models once, before any timing (default bge-reranker-base plus the arm's).
- Probe: `SET paradedb.vector_cluster_max_probe` on the session before each call, for both variants (default sets 0.02 explicitly), so both pay the same overhead. The served API is untouched.
- `--arm` and `--configs` are mutually exclusive.

### Config-order rotation

- Per query, rotate the order of (config, variant) pairs by query index: query i starts at pair `i mod n`. Applies to normal runs and Ablation runs.
- Pool sizes stay as they are (they affect metrics); §3 notes the difference.

### Outputs

- `per_query.csv`: new `variant` column (`default` / `arm`; `default` in normal runs), and `best_kind`: the Chunk kind (Summary, Ingredients, Step) of the top-ranked Chunk of the known Recipe, empty on a miss.
- `metrics.json` / `metrics.csv`: `variant` on each row.
- `settings.json`: `arm` block `{key, configs, set}` or `null`; `config_order: "rotated"`. `rerank_model` records the default; the arm's model is in `arm.set`.
- `recipes.csv` (recipe_id, url, title) for every Recipe in any top-20 list.
- `corpus.json`: Recipe and category counts, strategy × kind Chunk counts, Step length stats and bins in characters, strategy parameters, recipe_id → category for the queried Recipes.

### Tests (`tests/test_evaluate.py`)

- An arm run writes both variants for its configs and nothing else.
- Default-variant ranks in an arm run equal a normal run's ranks (on the test fixture DB).
- Rotation: over n consecutive queries, each pair appears first once.
- Served `retrieval.hybrid` with no knobs returns the same as before.

## 2. Runs

```
uv run scripts/evaluate.py                    # ×3: the Timing repeats
uv run scripts/evaluate.py --arm <key>        # ×8, one per ARMS key
```

- All on the rotation commit, clean tree, pinned ParadeDB image, same laptop, nothing else heavy running.
- One-off backfill of `recipes.csv` and `corpus.json` into the Report run `eval/runs/20260928-122309` (corpus facts unchanged since `fbb3947`, checked in "Dataset section stats").
- The Report run has no `best_kind`. Take it from the first Timing repeat; its ranks are verified equal, and retrieval is deterministic.

### Check each run right after it finishes

Hard rule from "How ablation runs and timing repeats are stored": ranks must equal the Report run's, no tolerance.

- Timing repeat: every (config, strategy, query) rank equals the Report run's.
- Ablation run: every `default` rank equals the Report run's for the same config.
- The check is one function the bundle script later imports. Build it with step 1 and run it by hand after each run, so a bad run is caught now, not when the page is built.
- A mismatch stops the batch. If it's MPS float noise flipping a near-tie, it's a §3 finding, not something to tolerate.

## 3. Post-run scripts (parallel with runs)

- `scripts/significance.py <run>`: paired bootstrap, 10k resamples, 95% percentile CI, two-sided raw p, seeded. Normal run: the 15 fixed comparisons (4 per strategy × 3, plus 3 strategy pairs under Hybrid) plus a plain bootstrap CI per config on R@5 and MRR. Ablation run: arm vs default per config × strategy. Writes `significance.json` with raw p only; Holm is the bundle's job.
- `scripts/failures.py`: `rerank_help` bucket; net-effect block (help/hurt counts, top-5 crossings each way, drop sizes, out-of-top-20); JSON output alongside `failures.md`; split rerank_hurt by `best_kind`.
- `eval/query_edits.csv` (query_id, reason) and `eval/error_groups.csv` (query_id, group), from `research/case-picks-and-labels.md`.

## 4. Manifest

`eval/report.json`, paths only, as fixed in "How ablation runs and timing repeats are stored". Filled in as runs land.

## 5. HNSW arm (added 2026-09-28, after steps 1–4 shipped in `ff8486f`)

From "Compare Dense against pgvector HNSW". A 9th Ablation run, on a new commit. The 11 runs in `eval/report.json` stay valid: the arm adds code, it doesn't change the served path.

### `scripts/evaluate.py`

- New `ARMS` entry: `"hnsw-dense": {"configs": ["dense", "fusion", "hybrid"], "set": {"dense_index": "hnsw", "ef_search": 200}}`.
- For the `arm` variant only, Dense uses a SQL variant without `id @@@ pdb.all()`, and runs `SET LOCAL hnsw.ef_search = 200` in its transaction, outside the stopwatch. `default` keeps the served SQL. `api/retrieval.py` doesn't change.
- Before any timing: `EXPLAIN` the arm's Dense SQL once per partition and stop unless the plan uses the HNSW index.
- Test: the arm's default ranks equal a normal run's (the existing arm test covers it once the key is added); the EXPLAIN guard fails when the index is missing.
- As built (2026-09-29): Dense SQL is `hnsw_dense` in `evaluate.py`. To reach it from Fusion and Hybrid, `retrieval.fused_candidates` / `hybrid` got a `dense_search` keyword that defaults to the served `dense`, the same pattern as `rrf_k` / `rerank_top`. So `api/retrieval.py` did change, but the served path didn't. The guard records each partition's index name, size and options in the `arm` block as `hnsw_indexes`.

### `sql/ablation/hnsw.sql`

Outside the init folder, so a fresh DB never gets it.

- `SET maintenance_work_mem = '2GB'`, then per partition (`chunk_fixed`, `chunk_semantic`, `chunk_sentence`): `CREATE INDEX … USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`.
- Drop is its own file, `sql/ablation/hnsw-drop.sql`, so running the build file never drops what it just built.
- Record each build's time (`\timing`) and `pg_relation_size` in the run's `settings.json` arm block or a note next to the run.

### Order

1. Build the indexes.
2. `uv run scripts/evaluate.py --arm hnsw-dense`. Roughly like `exact-dense` (~45 min) plus builds.
3. `runcheck.py` on the arm's default rows, with the index still present. A mismatch means the new index changed the served query's plan: stop and report it.
4. Drop the indexes.
5. `significance.py`, `failures.py` on the folder; add it to `ablation_runs` in `eval/report.json`.

### Ran (2026-09-29)

- Index builds, single-threaded (`max_parallel_maintenance_workers = 0`; a parallel build needs the whole graph in `/dev/shm`, 64 MB in Docker): fixed 1:49, semantic 1:38, sentence 1:32; 648–687 MB each.
- `eval/runs/20260929-012200` on `d0f71d4`, run from a clean worktree on an idle machine. Ranks match the Report run with the indexes present. Indexes dropped after. In the manifest.
- `eval/runs/20260929-004523` is a first run of the same arm that overlapped with other work on the laptop. Same ranks, unreliable latency. Not in the manifest; gitignored, delete when convenient.

### Report impact (for the page spec)

- §5: three-way Dense table, ParadeDB clusters served / HNSW / exact (`exact-dense`), on Dense, Fusion baseline and Hybrid × 3 strategies. R@5 and MRR absolute; Dense-stage latency as a same-run ratio to `default`, absolute p50 as a note.
- Holm family 81 → 90.
- §3: one line on why the served index isn't HNSW (ADR 0003), next to the probe line.

## Not in this spec

The bundle script, Holm across runs, the freshness test, the `/report` route and the page. Part 2.
