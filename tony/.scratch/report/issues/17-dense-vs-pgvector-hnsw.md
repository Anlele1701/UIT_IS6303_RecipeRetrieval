# Compare Dense against pgvector HNSW

Type: task
Assignee: Tony Trinh
Status: resolved
Blocked by:
Parent: ../map.md

## Question

The brief (Phase 3) asks for "HNSW for vectors". We serve ParadeDB's own cluster (IVF-style) index, so the report must show how it compares. Decided with the human (2026-09-28): add HNSW as an Ablation arm, don't switch the served Dense index (that would invalidate the Report run and all 11 runs, and is out of scope). IVFFlat is left out: it is the same cluster idea as the served index, so HNSW is the real contrast.

Run only after the 3 Timing repeats finish: building an index during them would skew their latency.

To settle and do:

- Index: pgvector `hnsw (embedding vector_cosine_ops)` on the `chunk` partitions, default `m` 16 / `ef_construction` 64 unless the build is too slow. Record build time and index size.
- `hnsw.ef_search`: must be at least the rows Dense pulls (100 solo, 50 in Hybrid); the default 40 silently truncates. Pick the value (100 or 200) and say why.
- Arm `hnsw-dense` on dense, fusion, hybrid, all 3 strategies, like `exact-dense`. Needs a Dense SQL variant without `id @@@ pdb.all()` so the planner can use HNSW, set only for the arm.
- Served path check: `runcheck.py` on the arm's default rows must still match the Report run. If the new index changes the planner's choice for the served query, that shows here. Decide whether to drop the HNSW index after the run.
- Report: §5 gets a three-way Dense table (ParadeDB clusters served, HNSW, exact from `exact-dense`) with R@5, MRR and dense stage latency; §1 or §3 says why the served index isn't HNSW.

## Answer

Decided with the human (2026-09-28). Planning only, per the map's Notes: the build and run are step 5 of the [Eval spec](../eval-spec.md), not done here.

Facts checked on the running DB: pgvector 0.8.4 is already in the pinned image. Partitions hold 165,974 (fixed), 166,438 (semantic) and 175,752 (sentence) Chunks, 768 dims. `maintenance_work_mem` is 496 MB. Eval queries filter only on `strategy`, which is partition pruning, so HNSW never post-filters and can't lose rows that way.

- Index: pgvector defaults `m 16 / ef_construction 64`, one per partition. `SET maintenance_work_mem = '2GB'` for the build session only (each index is ~0.5–0.6 GB, over the current limit). Record build time and `pg_relation_size` per partition. No smaller `m`: HNSW would look worse than a normal setup.
- `hnsw.ef_search = 200`, one value for both pools (100 solo, 50 in Hybrid). At ef = LIMIT the tail ranks lose recall; 200 is headroom and a normal setting. `SET LOCAL` inside the arm's call only. §3 says why in one line.
- Arm `"hnsw-dense": {"configs": ["dense", "fusion", "hybrid"], "set": {"dense_index": "hnsw", "ef_search": 200}}`. The arm's Dense SQL drops `id @@@ pdb.all()`; `default` keeps the served SQL. Before timing, `EXPLAIN` the arm SQL once per partition and fail the run unless it uses the HNSW index.
- DDL in `sql/ablation/hnsw.sql`, outside the init folder. Order: build → arm run → `runcheck.py` with the index present (catches a planner change on the served query) → drop.
- Report: §5 three-way Dense table (ParadeDB clusters served, HNSW, exact from `exact-dense`): R@5 and MRR absolute, Dense-stage latency as a same-run ratio to `default` with absolute p50 as a note. Holm family 81 → 90. §3 gets one line on why the served index isn't HNSW, backed by ADR 0003.
