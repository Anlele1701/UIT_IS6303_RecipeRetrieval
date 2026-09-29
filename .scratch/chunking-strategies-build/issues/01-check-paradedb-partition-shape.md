# 01: Check that ParadeDB accepts the partition shape

**What to build:** Two facts confirmed in a throwaway `paradedb/paradedb:pg17` container before any real code is written. Each is recorded here with the exact statements used and what happened.

1. A ParadeDB index can be created on a list-partitioned `chunk` that has **no partitions yet**. This is what a fresh volume does. The research only tested it with partitions already present.
2. A standalone staging table, indexed with the same definition as the parent, is adopted on `ATTACH PARTITION`: same index oid, no rebuild, scores unchanged. The staging table has no identity column, and its `id` defaults to the parent's sequence.

If (1) fails, write down the order the schema must use instead (for example, index created by the first `chunk <name>` run). Ticket 02 builds on that.

Spec: [../../chunking-strategies/spec.md](../../chunking-strategies/spec.md), "One index definition" and "`chunk <name>` flow".

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Index on an empty partitioned parent: works or fails, with the error if it fails
- [x] Staging table attach adopts its index (oid before = oid after), with one BM25 score checked before and after
- [x] Findings and the SQL used are recorded in this file
- [x] The container is removed; the live DB is not touched

## Findings (2026-09-27)

Run in a throwaway `paradedb/paradedb:pg17` container (`paradedb-probe-01`): no published port, no volume, driven through `docker exec psql`. Versions: PostgreSQL 17.11, pg_search 0.25.9, pgvector 0.8.4. The container was removed afterwards. `recipe-paradedb` wasn't queried.

Test table: the real `chunk` column list from `sql/schema.sql`, with `strategy` in place of `chunker`, `PRIMARY KEY (id, strategy)`, `UNIQUE (recipe_id, strategy, kind, position)`, and `embedding vector(3)` to keep the rows small. The index uses the column list from `sql/indexes.sql`, with `strategy::pdb.literal` in place of `chunker::pdb.literal`.

### 1. Index on an empty partitioned parent: works

- `CREATE INDEX chunk_search_idx ON chunk USING paradedb (...)` on the parent with 0 partitions returns `CREATE INDEX`, and `indisvalid = t`.
- A partition created afterwards (`CREATE TABLE chunk_semantic PARTITION OF chunk FOR VALUES IN ('semantic')`) gets its own valid ParadeDB child index automatically.
- So `schema.sql` can create the parent and its index on a fresh volume. No ordering workaround is needed for ticket 02.

```sql
CREATE TABLE chunk (
  id bigint GENERATED ALWAYS AS IDENTITY,
  recipe_id integer NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
  strategy text NOT NULL,
  -- ... rest of the columns as in schema.sql ...
  PRIMARY KEY (id, strategy),
  UNIQUE (recipe_id, strategy, kind, position)
) PARTITION BY LIST (strategy);

SELECT count(*) FROM pg_inherits WHERE inhparent = 'chunk'::regclass;  -- 0

CREATE INDEX chunk_search_idx ON chunk USING paradedb (
  id, (content::pdb.simple('stemmer=english')), (category::pdb.literal),
  (kind::pdb.literal), (strategy::pdb.literal), recipe_id,
  total_minutes, prep_minutes, cook_minutes, rating, rating_count, servings,
  calories, protein_g, fat_g, carbohydrates_g, sodium_mg,
  embedding vector_cosine_ops
) WITH (key_field = 'id');                                              -- CREATE INDEX, valid
```

### 2. Staging table attach adopts its index: works

Set up with `chunk_semantic` already attached and holding rows, so this is the real case (a new strategy next to a live one).

```sql
SELECT pg_get_serial_sequence('chunk', 'id') AS parent_seq \gset       -- public.chunk_id_seq
CREATE TABLE chunk_fixed_staging (LIKE chunk INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
  CHECK (strategy = 'fixed'));
ALTER TABLE chunk_fixed_staging ALTER COLUMN id SET DEFAULT nextval(:'parent_seq');
-- id: no identity, default nextval('chunk_id_seq'); inserted rows got ids 3, 4, 5 (after semantic's 1, 2)

CREATE INDEX chunk_fixed_staging_search_idx ON chunk_fixed_staging USING paradedb (...same list...)
WITH (key_field = 'id');

SELECT id, pdb.score(id) FROM chunk_fixed_staging WHERE content ||| 'onion';
ALTER TABLE chunk ATTACH PARTITION chunk_fixed_staging FOR VALUES IN ('fixed');
SELECT id, pdb.score(id) FROM chunk_fixed_staging WHERE content ||| 'onion';
```

| | before attach | after attach |
|---|---|---|
| index oid | 25261 | 25261 |
| index filenode | 25261 | 25261 (not rewritten) |
| attached to | none | `chunk_search_idx` |
| ParadeDB indexes on the partition | 1 | 1 |
| score, id 4 | 0.58317155 | 0.58317155 |
| score, id 3 | 0.48527452 | 0.48527452 |

- The PK and unique btree indexes don't exist on staging, so the attach built them (`chunk_fixed_staging_pkey`, `..._key`). That's a normal btree build, and it's fine.
- After the attach, `EXPLAIN` of `SELECT ... FROM chunk WHERE strategy = 'fixed' AND content ||| 'onion'` shows `ParadeDB Base Scan` on `chunk_fixed_staging` using `chunk_fixed_staging_search_idx`, so only that partition is scanned.

### Other findings for later tickets

- **A pushed-down filter changes the BM25 score.** Through the parent, `WHERE strategy = 'fixed' AND content ||| 'onion'` returned 0.716703 / 0.61880594, not 0.583 / 0.485. ParadeDB turns `strategy = 'fixed'` into a scored Tantivy `term` clause (seen in the `EXPLAIN` "Tantivy Query"), so its score gets added. The same filter on the partition directly gives the same 0.716703, so the attach isn't the cause. An `id IN (...)` filter added +1.0. What this means:
  - Tickets 06 (migration) and the slice 2 isolation check must compare scores from the **same query shape**, filters included. Comparing a query without a filter to one with a filter will fail even when nothing is wrong.
  - Migration step 1 captures from the old table filtered on `chunker = 'semantic-v1'`, and step 7 compares against the new table filtered on `strategy = 'semantic'`. Both filters match every row in their index, so the added term score should come out the same, but that's not verified. If the exact-match check fails, look here first.
- **Identity on staging is refused**, as the spec says: `ERROR: table "chunk_ident_staging" being attached contains an identity column "id"` / `DETAIL: The new partition may not contain an identity column.` (with `LIKE chunk ... INCLUDING IDENTITY`).
- **A staging table with no ParadeDB index still attaches.** Postgres builds the child index during the `ATTACH`, so there's no one-index-per-table error. But then the full index build happens while the attach holds its lock. The "build on staging first" step in the `chunk <name>` flow is still the right order.
