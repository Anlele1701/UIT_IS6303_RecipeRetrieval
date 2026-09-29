# How the live DB moves to partitions without re-embedding

Type: grilling
Status: resolved
Assignee: tonytrinh
Blocked by: 05
Parent: ../map.md

## Question

How does the existing `chunk` table (semantic-v1, ~70 min of embeddings) become the first partition of a list-partitioned `chunk`: rename `chunker` → `strategy`, change PK to `(id, strategy)`, then attach the existing table (index reused; only tested on a small table) or copy rows into a new partition (`INSERT ... SELECT`, index rebuilt)? How is it applied, given `schema.sql` only runs on a fresh Docker volume, and how is the result checked (row counts, the ADR-0001 consistency check, one query's scores before and after)? Include the foreign key to the strategy registry if ticket 05 adds one.

Also rename the strategy value `semantic-v1` → `semantic` as part of the move (decided in [Settings for fixed-size and sentence-based](03-fixed-and-sentence-settings.md)).

Registry (from [Where a strategy's name and settings live](05-where-strategy-settings-live.md)): create `chunking_strategy`, insert `semantic` with `method = semantic`, `parameters = {"min_chars": 80, "max_chars": 400, "break_percentile": 25}` and `loaded_at` set (the data was verified complete on 2026-09-27), then add the foreign key from `chunk.strategy`.

## Answer

Copy into a new partitioned table, not attach. Resolved 2026-09-27.

Facts checked in a throwaway DB on `paradedb/paradedb:pg17`:

- Attach works but needs prep: Postgres 17 refuses a table with its own identity column ("The new partition may not contain an identity column"), and the PK must be widened to `(id, strategy)` first. After that the attach is instant and the ParadeDB index is reused (same oid), scores identical.
- The value rename forces a rebuild anyway. An in-place `UPDATE` of the strategy value moved a BM25 score 7.3848 → 7.5716; `VACUUM` didn't fix it, `REINDEX` restored 7.3848 exactly. So attach and copy both cost one index build, and neither re-embeds.
- Disk: `chunk` is 1.7 GB (961 MB of it the index), 215 GB free.

Decision:

- **Copy.** Create the new list-partitioned `chunk` and its `semantic` partition, `INSERT ... SELECT` from the old table with `'semantic'` as the value, then build the ParadeDB index on the parent after the load. The old table stays untouched until checks pass, and it's the same path a new strategy takes (bulk load, then index).
- **Applied by** a one-off `sql/migrations/001-partition-chunk.sql`, run with `psql` as one transaction (a failure leaves the DB as it was). The same change updates `schema.sql` and `indexes.sql` to the new shape so a fresh volume matches. No `ingest.py` command for it.
- **Ids kept**: `OVERRIDING SYSTEM VALUE`, then `setval` the new sequence to `max(id)`.
- **Old table** renamed to `chunk_legacy` inside the migration; dropped by hand in a separate step after the checks pass. It is the backup, so no `pg_dump`.
- **Registry** in the same transaction: create `chunking_strategy`, insert `semantic` (`method = semantic`, `parameters = {"min_chars": 80, "max_chars": 400, "break_percentile": 25}`, `loaded_at` set), add the FK from `chunk.strategy`.
- **Verified** when all hold, with "before" values captured from the old table by the same script:
  - row counts per `kind` match (32,719 / 32,719 / 101,000);
  - the ADR-0001 consistency check returns 0;
  - top-10 ids and scores for one BM25 and one dense query match exactly (the rebuilt index was bit-identical in the test, so any difference is a bug);
  - `EXPLAIN` shows the partition's ParadeDB index;
  - the FK exists and `semantic` has `loaded_at` set.

Consequence: after the migration, `api/` and `sql/queries.sql` still filter on `chunker = 'semantic-v1'` and break. The migration and the `chunker` → `strategy` code rename land together.

