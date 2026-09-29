# Spec: Chunking strategies side by side

Store the `semantic`, `fixed` and `sentence` Chunking strategies side by side, pick one per search, and keep each strategy's scores unaffected by the others.

Source of every decision: [map](map.md). This spec gathers them into build order. Build tickets: [../chunking-strategies-build/issues/](../chunking-strategies-build/issues/). Where a line needs its reason, it links the ticket.

## Background

- Today there's one `chunk` table and one ParadeDB index. Everything is `chunker = 'semantic-v1'`: 32,719 Recipes, 166,438 chunks, about 70 min to embed.
- BM25 stats cover the whole index, so rows from a second strategy in the same index would change the first strategy's scores ([research](issues/01-paradedb-stats-across-strategies.md)).
- The fix is one partition and one ParadeDB index per strategy ([ADR-0002](../../docs/adr/0002-partition-chunk-by-strategy.md)).

## Build order

Three slices. Each one leaves the system working.

1. **DB shape + rename.** Partition `chunk`, add the registry, migrate the live data, and rename `chunker` → `strategy` everywhere.
2. **Ingest.** Rewrite `scripts/ingest.py` around `chunk <name>`, then build `fixed` and `sentence`.
3. **API + UI.** Required `strategy` param, `/strategies`, and the picker.

## Slice 1: DB shape + rename

### Schema (`sql/schema.sql`, for fresh volumes)

`chunking_strategy`:

| column | type | notes |
|---|---|---|
| `name` | `text PRIMARY KEY` | `semantic`, `fixed`, `sentence` |
| `method` | `text NOT NULL` | `semantic` / `fixed` / `sentence`. Separate from `name` so a retune like `fixed-64` is still `method = fixed` |
| `parameters` | `jsonb NOT NULL` | validated in code only |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |
| `loaded_at` | `timestamptz NULL` | set only when every Recipe has all its chunks |

`chunk`:

- `PARTITION BY LIST (strategy)`. No DEFAULT partition.
- The `chunker` column becomes `strategy text NOT NULL REFERENCES chunking_strategy(name)`.
- `id bigint GENERATED ALWAYS AS IDENTITY`. PK `(id, strategy)`.
- `UNIQUE (recipe_id, strategy, kind, position)`.
- All other columns unchanged.
- The ParadeDB index `chunk_search_idx` goes on the parent, with `(strategy::pdb.literal)` replacing `(chunker::pdb.literal)`.

### One index definition (`sql/indexes.sql`)

- It becomes the only copy of the index column list, templated on table and index name (psql variables `:"tbl"` / `:"idx"`).
- psql callers (`schema.sql`, the migration) `\set` them. `ingest.py` substitutes them with `psycopg.sql.Identifier`.
- Why it matters: `ATTACH PARTITION` only adopts a staging index that matches the parent index. If they differ, Postgres tries to build a second index and fails on ParadeDB's one-index-per-table limit ([ingest ticket](issues/08-ingest-command-shape.md)).

### Migration (`sql/migrations/001-partition-chunk.sql`)

Run once against the live DB with `psql --single-transaction`. A failure leaves the DB as it was. Details: [migration ticket](issues/06-migrate-live-db-to-partitions.md).

1. Capture the "before" values from the old table: row counts per `kind`, and the top-10 ids and scores for one BM25 query and one dense query.
2. `ALTER TABLE chunk RENAME TO chunk_legacy` (its index and constraints get renamed out of the way too).
3. Create `chunking_strategy`, then insert `semantic`:
   - `method = semantic`
   - `parameters = {"min_chars": 80, "max_chars": 400, "break_percentile": 25}`
   - `loaded_at = now()`
4. Create the partitioned `chunk` and its partition `chunk_semantic FOR VALUES IN ('semantic')`.
5. `INSERT INTO chunk ... OVERRIDING SYSTEM VALUE SELECT ..., 'semantic', ... FROM chunk_legacy`, keeping ids. Then `setval` the new sequence to `max(id)`.
6. Build `chunk_search_idx` on the parent (from `indexes.sql`), then `ANALYZE chunk`.
7. Checks. Any failure raises and rolls back:
   - row counts per `kind` match (32,719 / 32,719 / 101,000);
   - the ADR-0001 consistency check returns 0;
   - top-10 ids and scores for both queries match exactly;
   - `EXPLAIN` of a `strategy = 'semantic'` search shows the partition's ParadeDB index;
   - the FK exists and `semantic` has `loaded_at` set.

`chunk_legacy` is the backup. Drop it by hand in a separate step once you're satisfied. No `pg_dump`.

Why copy and not attach: renaming the value in place moves BM25 scores until a `REINDEX`, so both paths cost one index build. Copy leaves the old table untouched.

### Rename, in the same change

After the migration, anything still filtering on `chunker = 'semantic-v1'` breaks. So all of these land together:

- `api/filters.py:43`: `strategy = %s`.
- `api/config.py:10`: `CHUNKER` default becomes `semantic`. Interim only: slice 3 removes it.
- `api/main.py:127-132` (`/health`): query `strategy`. The per-strategy shape comes in slice 3.
- `scripts/ingest.py`: `CHUNKER` → `"semantic"` as a stopgap. Slice 2 rewrites the file.
- `scripts/search.py:17,30`: takes a required `--strategy` and no longer imports `CHUNKER`.
- `sql/queries.sql`: examples use `strategy = 'semantic'`.
- `tests/test_retrieval.py:31`: expected SQL.

### Done when

- The migration runs clean on the live DB and every check passes.
- `pytest` passes, and all three search methods return the same top-10 as before the migration.
- A fresh `docker compose` volume comes up with the new `schema.sql`.

## Slice 2: Ingest

Details: [ingest ticket](issues/08-ingest-command-shape.md), [settings ticket](issues/03-fixed-and-sentence-settings.md), [registry ticket](issues/05-where-strategy-settings-live.md).

### Strategies in code

A `STRATEGIES` dict in `ingest.py` maps name → `method`, `parameters`, and the cut function. It's the only place a strategy is defined, and the registry row is written from it.

Every strategy shares these rules:

- The cut input is `split_sentences(normalize_fractions(directions))`, joined with single spaces.
- The title prefix (`title\n`) is added after cutting and doesn't count toward any size limit.
- No overlap.
- Summary and Ingredients chunks are built the same way as today, and every strategy embeds its own.

| name | method | parameters | cut |
|---|---|---|---|
| `semantic` | semantic | `{"min_chars": 80, "max_chars": 400, "break_percentile": 25}` | today's `semantic_chunks`, unchanged (needs sentence embeddings) |
| `fixed` | fixed | `{"tokens": 56, "tokenizer": "bert-base-uncased"}` | windows of 56 WordPiece tokens, cut only between words, ignores sentence ends |
| `sentence` | sentence | `{"sentences": 3}` | 3 consecutive sentences per chunk; the leftover 1–2 form their own chunk; no size cap |

- `fixed` adds `tokenizers` to the script's inline dependencies and loads `bert-base-uncased` (nomic-embed-text's tokenizer).
- Expected Step chunk counts, simulated in the settings ticket: `fixed` 100,536, `sentence` 110,314, `semantic` 101,000.

### Commands

`uv run scripts/ingest.py ...`

- `load`: as today, except it refuses while any `chunking_strategy` row exists ("drop strategies first: semantic, fixed"). A reload resets recipe ids.
- `chunk <name>`: builds one strategy end to end, index included. An unknown name exits with the list of known names.
- `drop <name>`: removes the strategy's partition (or its staging table) and its row. A loaded strategy needs `--yes`. Without it, the command prints the chunk count and exits.
- `index` is removed, since `chunk` does it now.

### `chunk <name>` flow

1. `pg_advisory_lock` on the name. A second concurrent run fails fast.
2. If the row exists and is loaded, refuse ("fixed is loaded; run `drop fixed` first"). If it exists but isn't loaded, drop its staging table and row, then continue fresh.
3. **Register** (one transaction):
   - insert the row with `loaded_at` NULL;
   - create `chunk_<name>_staging` with the same columns as `chunk`, plus `CHECK (strategy = '<name>')`;
   - no identity column on staging (Postgres 17 won't attach one): `id` defaults to `nextval` of the parent's sequence.
4. **Load**: batches of 200 Recipes, one commit per batch, reading only the recipe tables. Progress shows up as `count(*)` on staging.
5. **Check** against staging. On any failure, stay unloaded and exit non-zero, naming the check:
   - every Recipe has exactly 1 Summary, 1 Ingredients and at least 1 Step chunk;
   - Step positions run 1..n with no gaps;
   - no null embeddings;
   - the ADR-0001 consistency check returns 0.
6. **Finish** (one transaction):
   - build the ParadeDB index on staging from `indexes.sql`;
   - `ATTACH PARTITION ... FOR VALUES IN ('<name>')`, which adopts the index with no rebuild;
   - `ANALYZE`;
   - set `loaded_at`.

A partition only appears in `chunk` once it's complete. The attach takes a light lock, so searches on other strategies keep running.

### Done when

- `chunk fixed` and `chunk sentence` both finish, and their Step counts are close to the simulated ones.
- **Isolation holds.** Semantic's top-10 BM25 and dense ids and scores, captured before building `fixed`, are identical after both builds. This is what ADR-0002 exists for.
- Kill `chunk sentence` mid-load and rerun it: the rerun cleans up and finishes. `chunk fixed` on a loaded `fixed` refuses. `drop fixed` without `--yes` refuses.
- `load` refuses while strategies exist.
- `EXPLAIN` for each strategy shows its own partition's index.

## Slice 3: API + UI

Details: [API/UI ticket](issues/07-api-ui-contract.md).

### API

- `SearchParams` gets `strategy: str`, required with no default. This applies to `/search/sparse`, `/search/dense` and `/search/hybrid`. `extra="forbid"` turns a leftover `chunker=` into an error.
- `CHUNKER` is removed from `api/config.py`.
- Every request is validated against `chunking_strategy` (no cache, so a newly loaded strategy works without a restart). Both cases return 422:
  - `strategy: 'fixed' is not loaded yet`
  - `strategy: 'foo' is unknown; loaded: semantic, sentence`
- `GET /strategies` returns loaded strategies only, ordered by name: `[{name, method, parameters, loaded_at}]`. No counts.
- `/health` replaces `chunker` and `chunks` with `chunks: {"semantic": 166438, ...}`, one entry per loaded strategy.
- `SearchResponse` gets `strategy` next to `method`.

### UI

- A segmented control next to the search box, fed by `/strategies`. Changing it re-runs the current query right away.
- Pre-select `semantic` if it's loaded, otherwise the first one. Remember the last choice in `localStorage`.
- With no loaded strategies, search is disabled and a message says why.
- Each column header shows the strategy name.
- `ui/src/api.ts:29` and the `SettingsDrawer.tsx:179` Services section show counts per strategy instead of the single Chunker.
- Rebuild `api/static` (the built bundle still says "Chunker").

### Done when

- A search without `strategy`, or with an unknown or unloaded one, returns the 422s above.
- Switching the picker re-runs the query, and the results and headers show the new strategy.
- A strategy loaded while the API is running shows up in `/strategies` without a restart.

## Not in this spec

- **Evaluation** (test queries, judgments, metrics) is its own effort. Guardrail: chunk ids differ between strategies, so relevance is judged per Recipe (`recipe_id`), which every chunk carries.
- **Changing the embedding model** re-embeds every partition. Also its own effort.
