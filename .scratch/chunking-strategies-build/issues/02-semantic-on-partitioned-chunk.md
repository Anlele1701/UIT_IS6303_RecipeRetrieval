# 02: Semantic search runs on the partitioned `chunk`

**What to build:** The live DB moves to the partitioned layout with the `chunking_strategy` registry, and search works exactly as before. The existing semantic data is copied into the `semantic` partition with no re-embedding, and `chunker` is renamed to `strategy` everywhere at once: schema, index definition, API, the search script, SQL examples and tests. A fresh Docker volume comes up with the same shape.

This is a wide refactor that can't land in parts: once the column is renamed, every query breaks until all callers move. So it's one ticket. The API keeps an interim `CHUNKER` default of `semantic`, which ticket 03 removes.

Spec: [../../chunking-strategies/spec.md](../../chunking-strategies/spec.md), "Slice 1". Decisions: migration ticket 06 and ADR-0002.

The migration runs against the live DB: **ask before running it.**

**Blocked by:** 01 (Check that ParadeDB accepts the partition shape)

**Status:** done

- [x] The migration runs as one transaction, and every check in it passes: counts per kind 32,719 / 32,719 / 101,000, ADR-0001 check 0, identical top-10 ids and scores for one BM25 and one dense query, `EXPLAIN` uses the partition's index, FK present, `semantic` loaded
- [x] The old table remains as `chunk_legacy` (it's dropped by hand later, not by this ticket)
- [x] Sparse, dense and hybrid return the same top-10 through the API as before the migration
- [x] The search script requires `--strategy`
- [x] Tests pass
- [x] A fresh volume builds with the new schema, and the index definition exists in one place, templated by table and index name

## Progress (2026-09-27)

Code and SQL are done. The live migration hasn't run yet (needs a go-ahead).

- Tests at three seams: `where_clause` (strategy filter), `index_sql` (renders `indexes.sql` for any table/index), `search.py --strategy`. 8 pass.
- Fresh volume checked in a throwaway container: partitioned `chunk`, `chunking_strategy`, `chunk_search_idx` on the parent, 0 partitions. `docker-compose.yml` now mounts `sql/` as a folder plus `sql/docker-init.sql`, so `schema.sql` can `\ir indexes.sql`.
- Migration rehearsed on a `pg_dump` copy of the live DB: all checks pass, in about 15 s.
  - The first run failed on BM25 top-10: chunks 51024 and 25640 have the exact same score (8.045499) and swapped places. All scores were bit-identical. The check now orders by `score DESC, id`.
  - The old and new strategy filters add the same term score (8.489528 both sides), so the filtered before/after comparison is fair (open question from ticket 01).
  - A failing check rolled everything back: no `chunk_legacy`, no registry, 166,438 rows still in `chunk`.

Left open:

- Run `sql/migrations/001-partition-chunk.sql` on the live DB, then check the API top-10s. Tied scores can swap places in the API too, since `api/retrieval.py` has no id tie-break.
- `/health` still returns the key `chunker` (value `semantic`), because the built UI reads `r.chunker`. Ticket 03 reshapes it.
- `ingest.py chunk` on a fresh volume fails until slice 2: there's no `semantic` partition or registry row to insert into.
- The running `recipe-paradedb` container still has the old mounts. Only matters for a new volume; `docker compose up -d` recreates it (data volume kept).

## Live migration (2026-09-27)

- Ran `001-partition-chunk.sql` on the live DB with `-f`, one transaction, 14 s. All checks passed: 32,719 / 32,719 / 101,000, `chunk_semantic` partition, FK to `chunking_strategy`, `semantic` loaded. `chunk_legacy` kept.
- A first try piped the file over stdin. `\ir ../indexes.sql` couldn't resolve, psql stopped, and everything rolled back (checked: no `chunk_legacy`, 166,438 rows in the old `chunk`). The header now says to use `-f`.
- API top-10 before vs after, 4 queries (one with a `kind` filter, one with `max_total_minutes`) x sparse/dense/hybrid, k=10. Dense and hybrid are identical. Sparse has the same ids and bit-identical scores at every position; the only differences are 3 pairs of tied scores that swapped places ("chocolate cake" ranks 6/7 and 9/10, "quick vegan curry" ranks 4/5).
- Container recreated with the new mounts, on the same data volume `is603_recipe-pgdata`. `docker-compose.yml` now pins `name: is603`: without it, compose names the project after the folder (`retrivalsystem`) and attaches a different, existing volume.

Still open, for later tickets:

- `api/retrieval.py` sparse has no id tie-break, so tied results can come back in a different order. Worth adding `, id` in 03 if stable ordering matters for the UI.
- `/health` still returns `chunker` (ticket 03).
- Drop `chunk_legacy` by hand once you're happy.
