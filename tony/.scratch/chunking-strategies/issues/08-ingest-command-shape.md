# Ingest command shape for one strategy

Type: grilling
Status: resolved
Assignee: tonytrinh
Blocked by:
Parent: ../map.md

## Question

What does `scripts/ingest.py` look like when it builds one Chunking strategy? Covers: the argument (e.g. `chunk --strategy fixed`), how the code keeps each strategy's name, method and parameters, the register step (row + partition in one transaction), the rollback-and-rerun rule (drop an unloaded strategy's partition and row, refuse a loaded one), the explicit drop command, when the partition's ParadeDB index is built (before or after the bulk load), and setting `loaded_at`. Known: `fixed` and `sentence` skip sentence embeddings, so they run much faster than semantic's ~70 min.

Known from [How the live DB moves to partitions without re-embedding](06-migrate-live-db-to-partitions.md): an in-place `UPDATE` on an indexed partition shifts BM25 scores until a `REINDEX` (deleted docs stay in the stats), so a loaded partition's rows are never updated in place. Whether building the index before the load (incremental inserts) gives the same scores as a bulk build after it is untested.

## Answer

Resolved 2026-09-27.

Why not create the partition first: the ParadeDB index lives on the `chunk` parent, so Postgres gives a new partition an empty child index the moment it's created, and every insert would be indexed one at a time (untested for score equality). Attaching an already-indexed table reuses its index (verified in the research), so the load goes through a staging table.

Commands (`uv run scripts/ingest.py ...`):

- `chunk <name>`: build one strategy end to end, index included. Positional name, not a flag.
- `drop <name>`: remove the strategy's partition (or staging table) and its registry row. A loaded strategy needs `--yes`; without it, print its chunk count and exit.
- `index` is removed (folded into `chunk`).
- `load` refuses while any `chunking_strategy` row exists ("drop strategies first: semantic, fixed"). Reloading resets recipe ids, so kept chunks would point at the wrong Recipes.

Strategy definitions: a `STRATEGIES` dict in `ingest.py`, name → method, parameters, cut function. It's the only place a strategy is defined in code; the registry row is written from it. An unknown name exits with the list of known names.

`chunk <name>` flow:

1. Take `pg_advisory_lock` on the name; a second concurrent run fails fast.
2. If the row exists and `loaded_at` is set: refuse ("fixed is loaded; run `drop fixed` first"). If it exists with `loaded_at` NULL: drop its staging table and row (rollback-and-rerun from [Where a strategy's name and settings live](05-where-strategy-settings-live.md)).
3. **Register** in one transaction: insert the `chunking_strategy` row (`loaded_at` NULL) and create `chunk_<name>_staging` with `CHECK (strategy = '<name>')`. No own identity column (Postgres 17 won't attach one); `id` defaults to `nextval` of the parent's sequence.
4. **Load** in batches of 200 Recipes, one commit per batch (progress visible via `count(*)`; a crash costs the same as one big transaction since the rerun drops staging). Every strategy re-embeds its own Summary and Ingredients chunks: builds read only `recipe`, never another strategy's rows.
5. **Check** against staging; any failure leaves the strategy unloaded and exits non-zero naming the check:
   - every Recipe has exactly 1 Summary, 1 Ingredients, at least 1 Step chunk;
   - Step positions run 1..n with no gaps;
   - no null embeddings;
   - the ADR-0001 consistency check returns 0.
6. **Finish** in one transaction: build the ParadeDB index on staging, `ATTACH PARTITION ... FOR VALUES IN ('<name>')` (adopts the index, no rebuild), `ANALYZE`, set `loaded_at`. Attach takes only a light lock on `chunk`, so searches on other strategies keep running. A partition only appears in `chunk` once complete.

One index definition: `indexes.sql` is the single source of the column list, templated by table name, used for the parent index (migration and `schema.sql`) and every staging index. If the two differ, the attach tries to build a second index and fails on ParadeDB's one-index-per-table limit.

This refines the register rule from ticket 05: the row is created with a staging table, not a partition; the partition exists only for loaded strategies.
