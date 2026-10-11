-- Recipe retrieval schema. See CONTEXT.md for terms and docs/adr/ for decisions.
CREATE EXTENSION IF NOT EXISTS pg_search;
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Source of truth (3NF), loaded once from Shengtao/recipe
-- ---------------------------------------------------------------------------

CREATE TABLE category (
  id    smallint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name  text NOT NULL UNIQUE
);

CREATE TABLE author (
  id    integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name  text NOT NULL UNIQUE
);

CREATE TABLE recipe (
  id             integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  url            text NOT NULL UNIQUE,
  title          text NOT NULL,
  description    text NOT NULL,
  directions     text NOT NULL,
  image_url      text,
  category_id    smallint NOT NULL REFERENCES category(id),
  author_id      integer REFERENCES author(id),
  rating         real NOT NULL,
  rating_count   integer NOT NULL,
  review_count   integer NOT NULL,
  prep_minutes   integer,   -- parsed from "1 hr 10 mins"; null when unknown
  cook_minutes   integer,
  total_minutes  integer,
  servings       integer NOT NULL,
  yields         text
);

-- Per serving. The 13 columns that are >99% empty in the source are dropped.
CREATE TABLE recipe_nutrition (
  recipe_id          integer PRIMARY KEY REFERENCES recipe(id) ON DELETE CASCADE,
  calories           real,
  calories_from_fat  real,
  fat_g              real,
  saturated_fat_g    real,
  carbohydrates_g    real,
  sugars_g           real,
  dietary_fiber_g    real,
  protein_g          real,
  cholesterol_mg     real,
  sodium_mg          real,
  calcium_mg         real,
  iron_mg            real,
  magnesium_mg       real,
  potassium_mg       real,
  folate_mcg         real,
  thiamin_mg         real,
  niacin_mg          real,
  vitamin_a_iu       real,
  vitamin_c_mg       real
);

-- Raw ingredient lines exactly as in the source (no quantity/unit parsing).
CREATE TABLE recipe_ingredient (
  recipe_id  integer NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
  position   smallint NOT NULL,
  line       text NOT NULL,
  PRIMARY KEY (recipe_id, position)
);

-- ---------------------------------------------------------------------------
-- Chunking strategies (ADR-0002). A strategy is searchable only once loaded_at
-- is set: every Recipe has its complete set of Chunks under it.
-- ---------------------------------------------------------------------------

CREATE TABLE chunking_strategy (
  name        text PRIMARY KEY,
  method      text NOT NULL,          -- semantic / fixed / sentence; a retune keeps its method
  parameters  jsonb NOT NULL,         -- validated in code only
  created_at  timestamptz NOT NULL DEFAULT now(),
  loaded_at   timestamptz
);

-- ---------------------------------------------------------------------------
-- Search table: derived from the tables above, rebuilt only, never edited.
-- Filter columns are deliberately copied here (ADR-0001) so the ParadeDB
-- index can apply them during the search.
-- One partition per Chunking strategy (ADR-0002), so each has its own index
-- and BM25 stats. No DEFAULT partition: a strategy gets one when it's built.
-- ---------------------------------------------------------------------------

CREATE TABLE chunk (
  id               bigint GENERATED ALWAYS AS IDENTITY,
  recipe_id        integer NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
  strategy         text NOT NULL REFERENCES chunking_strategy(name),
  kind             text NOT NULL CHECK (kind IN ('summary', 'ingredients', 'step')),
  position         smallint NOT NULL,          -- 0 for summary/ingredients, 1..n for steps
  content          text NOT NULL,              -- title + chunk text, fractions normalized
  embedding        vector(768) NOT NULL,       -- nomic-embed-text, "search_document: " + content
  -- copied filter attributes
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
  PRIMARY KEY (id, strategy),                  -- a partitioned table's keys must include the partition key
  UNIQUE (recipe_id, strategy, kind, position)
) PARTITION BY LIST (strategy);

-- The ParadeDB index on the parent; each partition gets its own child index.
\set tbl chunk
\set idx chunk_search_idx
\ir indexes.sql
