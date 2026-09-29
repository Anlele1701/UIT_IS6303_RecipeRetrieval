-- One-off: move the live `chunk` table to the partitioned layout (ADR-0002).
-- Copies the semantic-v1 rows into the `semantic` partition. No re-embedding.
--
--   psql "$DATABASE_URL" --single-transaction -f sql/migrations/001-partition-chunk.sql
--
-- Use -f, not stdin: it pulls in ../indexes.sql by relative path.
--
-- Any failure (including a check below) rolls the whole thing back.
-- chunk_legacy is the backup; drop it by hand once you're satisfied.
-- Decisions: .scratch/chunking-strategies/issues/06-migrate-live-db-to-partitions.md

\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------
-- 1. "Before" values, from the old table, in the same query shape the API uses
--    (plus an id tie-break for BM25). The filter term adds to the BM25 score, so
--    before and after must both filter on their strategy column.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE before_counts ON COMMIT DROP AS
SELECT kind, count(*) AS n FROM chunk GROUP BY kind;

CREATE TEMP TABLE before_bm25 ON COMMIT DROP AS
SELECT row_number() OVER () AS rank, id, score FROM (
  SELECT id, pdb.score(id) AS score FROM chunk
  WHERE content ||| 'garlic shrimp' AND chunker = 'semantic-v1'
  ORDER BY score DESC, id LIMIT 10) t;  -- id breaks exact ties, which otherwise follow physical order

-- An existing chunk's embedding stands in for a query vector.
SELECT embedding::text AS qvec FROM chunk ORDER BY id LIMIT 1 \gset

CREATE TEMP TABLE before_dense ON COMMIT DROP AS
SELECT row_number() OVER () AS rank, id, score FROM (
  SELECT id, 1 - (embedding <=> :'qvec'::vector) AS score FROM chunk
  WHERE id @@@ pdb.all() AND chunker = 'semantic-v1'
  ORDER BY embedding <=> :'qvec'::vector LIMIT 10) t;

-- ---------------------------------------------------------------------------
-- 2. Move the old table and every name it owns out of the way
-- ---------------------------------------------------------------------------

ALTER TABLE chunk RENAME TO chunk_legacy;
ALTER INDEX chunk_search_idx RENAME TO chunk_legacy_search_idx;
ALTER INDEX chunk_pkey RENAME TO chunk_legacy_pkey;
ALTER INDEX chunk_recipe_id_chunker_kind_position_key RENAME TO chunk_legacy_recipe_id_chunker_kind_position_key;
ALTER SEQUENCE chunk_id_seq RENAME TO chunk_legacy_id_seq;

-- ---------------------------------------------------------------------------
-- 3. Registry
-- ---------------------------------------------------------------------------

CREATE TABLE chunking_strategy (
  name        text PRIMARY KEY,
  method      text NOT NULL,
  parameters  jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  loaded_at   timestamptz
);

INSERT INTO chunking_strategy (name, method, parameters, loaded_at)
VALUES ('semantic', 'semantic', '{"min_chars": 80, "max_chars": 400, "break_percentile": 25}', now());

-- ---------------------------------------------------------------------------
-- 4. Partitioned chunk, same shape as sql/schema.sql
-- ---------------------------------------------------------------------------

CREATE TABLE chunk (
  id               bigint GENERATED ALWAYS AS IDENTITY,
  recipe_id        integer NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
  strategy         text NOT NULL REFERENCES chunking_strategy(name),
  kind             text NOT NULL CHECK (kind IN ('summary', 'ingredients', 'step')),
  position         smallint NOT NULL,
  content          text NOT NULL,
  embedding        vector(768) NOT NULL,
  category         text NOT NULL,
  total_minutes    integer,
  prep_minutes     integer,
  cook_minutes     integer,
  rating           real NOT NULL,
  rating_count     integer NOT NULL,
  servings         integer NOT NULL,
  calories         real,
  protein_g        real,
  fat_g            real,
  carbohydrates_g  real,
  sodium_mg        real,
  PRIMARY KEY (id, strategy),
  UNIQUE (recipe_id, strategy, kind, position)
) PARTITION BY LIST (strategy);

CREATE TABLE chunk_semantic PARTITION OF chunk FOR VALUES IN ('semantic');

-- ---------------------------------------------------------------------------
-- 5. Copy, keeping ids
-- ---------------------------------------------------------------------------

INSERT INTO chunk (id, recipe_id, strategy, kind, position, content, embedding, category,
                   total_minutes, prep_minutes, cook_minutes, rating, rating_count, servings,
                   calories, protein_g, fat_g, carbohydrates_g, sodium_mg)
OVERRIDING SYSTEM VALUE
SELECT id, recipe_id, 'semantic', kind, position, content, embedding, category,
       total_minutes, prep_minutes, cook_minutes, rating, rating_count, servings,
       calories, protein_g, fat_g, carbohydrates_g, sodium_mg
FROM chunk_legacy;

SELECT setval(pg_get_serial_sequence('chunk', 'id'), (SELECT max(id) FROM chunk));

-- ---------------------------------------------------------------------------
-- 6. Index (built after the load: bulk build is much faster) + ANALYZE
-- ---------------------------------------------------------------------------

\set tbl chunk
\set idx chunk_search_idx
\ir ../indexes.sql

-- ---------------------------------------------------------------------------
-- 7. Checks. Any failure raises, and --single-transaction rolls everything back.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE after_bm25 ON COMMIT DROP AS
SELECT row_number() OVER () AS rank, id, score FROM (
  SELECT id, pdb.score(id) AS score FROM chunk
  WHERE content ||| 'garlic shrimp' AND strategy = 'semantic'
  ORDER BY score DESC, id LIMIT 10) t;

CREATE TEMP TABLE after_dense ON COMMIT DROP AS
SELECT row_number() OVER () AS rank, id, score FROM (
  SELECT id, 1 - (embedding <=> :'qvec'::vector) AS score FROM chunk
  WHERE id @@@ pdb.all() AND strategy = 'semantic'
  ORDER BY embedding <=> :'qvec'::vector LIMIT 10) t;

DO $$
DECLARE
  bad bigint;
  plan text := '';
  line text;
  part_idx text;
BEGIN
  -- row counts per kind
  SELECT count(*) INTO bad FROM (
    (SELECT kind, n FROM before_counts EXCEPT SELECT kind, count(*) FROM chunk GROUP BY kind)
    UNION ALL
    (SELECT kind, count(*) FROM chunk GROUP BY kind EXCEPT SELECT kind, n FROM before_counts)) d;
  IF bad > 0 THEN RAISE EXCEPTION 'check failed: row counts per kind differ from chunk_legacy'; END IF;

  -- ADR-0001 consistency check
  SELECT count(*) INTO bad
  FROM chunk c
  JOIN recipe r ON r.id = c.recipe_id
  JOIN category cat ON cat.id = r.category_id
  LEFT JOIN recipe_nutrition nu ON nu.recipe_id = r.id
  WHERE (c.category, c.total_minutes, c.prep_minutes, c.cook_minutes, c.rating, c.rating_count,
         c.servings, c.calories, c.protein_g, c.fat_g, c.carbohydrates_g, c.sodium_mg)
        IS DISTINCT FROM
        (cat.name, r.total_minutes, r.prep_minutes, r.cook_minutes, r.rating, r.rating_count,
         r.servings, nu.calories, nu.protein_g, nu.fat_g, nu.carbohydrates_g, nu.sodium_mg);
  IF bad > 0 THEN RAISE EXCEPTION 'check failed: ADR-0001 consistency check found % mismatches', bad; END IF;

  -- top-10 ids and scores, exactly
  SELECT count(*) INTO bad FROM before_bm25 b FULL JOIN after_bm25 a USING (rank)
  WHERE (b.id, b.score) IS DISTINCT FROM (a.id, a.score);
  IF bad > 0 THEN RAISE EXCEPTION 'check failed: BM25 top-10 differs in % ranks', bad; END IF;
  SELECT count(*) INTO bad FROM before_bm25;
  IF bad <> 10 THEN RAISE EXCEPTION 'check failed: BM25 check query returned % rows, not 10', bad; END IF;

  SELECT count(*) INTO bad FROM before_dense b FULL JOIN after_dense a USING (rank)
  WHERE (b.id, b.score) IS DISTINCT FROM (a.id, a.score);
  IF bad > 0 THEN RAISE EXCEPTION 'check failed: dense top-10 differs in % ranks', bad; END IF;
  SELECT count(*) INTO bad FROM before_dense;
  IF bad <> 10 THEN RAISE EXCEPTION 'check failed: dense check query returned % rows, not 10', bad; END IF;

  -- the plan uses the semantic partition's own ParadeDB index
  SELECT c.relname INTO part_idx
  FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid JOIN pg_index x ON x.indexrelid = c.oid
  WHERE i.inhparent = 'chunk_search_idx'::regclass AND x.indrelid = 'chunk_semantic'::regclass;
  IF part_idx IS NULL THEN RAISE EXCEPTION 'check failed: chunk_semantic has no child of chunk_search_idx'; END IF;
  FOR line IN EXECUTE $q$EXPLAIN SELECT id, pdb.score(id) FROM chunk
                         WHERE content ||| 'garlic shrimp' AND strategy = 'semantic'
                         ORDER BY pdb.score(id) DESC LIMIT 10$q$ LOOP
    plan := plan || line || E'\n';
  END LOOP;
  IF position('ParadeDB' IN plan) = 0 OR position(part_idx IN plan) = 0 THEN
    RAISE EXCEPTION E'check failed: EXPLAIN does not use %:\n%', part_idx, plan;
  END IF;

  -- FK and registry row
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'chunk'::regclass AND contype = 'f'
                 AND confrelid = 'chunking_strategy'::regclass) THEN
    RAISE EXCEPTION 'check failed: no FK from chunk.strategy to chunking_strategy';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM chunking_strategy WHERE name = 'semantic' AND loaded_at IS NOT NULL) THEN
    RAISE EXCEPTION 'check failed: semantic is not marked loaded';
  END IF;

  RAISE NOTICE 'all checks passed';
END $$;

SELECT kind, count(*) FROM chunk GROUP BY kind ORDER BY kind;
