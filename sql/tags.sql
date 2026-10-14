-- Ingredient normalization and Recipe tags (rules D4-D8). Written by scripts/tag.py from the recipe
-- tables and the committed lexicon in data/lexicon/; never edited by hand. Shared by schema.sql (a fresh
-- volume) and migrations/002-tags.sql (an existing one).

CREATE TABLE IF NOT EXISTS allergen (
  code     text PRIMARY KEY,           -- FDA major allergen: milk, egg, fish, crustacean_shellfish, ...
  name_en  text NOT NULL,
  name_vi  text NOT NULL,
  source   text NOT NULL CHECK (source IN ('FDA', 'EU'))
);

CREATE TABLE IF NOT EXISTS ingredient (
  id              integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  canonical_name  text NOT NULL UNIQUE,  -- lowercase, singular: what chunk.ingredients_norm holds
  synonyms        text[] NOT NULL DEFAULT '{}',
  grp             text NOT NULL DEFAULT ''  -- food group for diet flags (D7); '' = none
);

CREATE TABLE IF NOT EXISTS ingredient_allergen (
  ingredient_id  integer NOT NULL REFERENCES ingredient(id) ON DELETE CASCADE,
  allergen_code  text NOT NULL REFERENCES allergen(code),
  kind           text NOT NULL CHECK (kind IN ('direct', 'hidden', 'possible')),
                 -- hidden: soy sauce -> wheat; possible: brand-dependent (chocolate -> milk), flagged not filtered
  PRIMARY KEY (ingredient_id, allergen_code)
);

-- Vietnamese words a user may type, pointing at an ingredient or straight at an allergen group.
CREATE TABLE IF NOT EXISTS ingredient_alias_vi (
  alias          text NOT NULL,
  ingredient_id  integer REFERENCES ingredient(id) ON DELETE CASCADE,
  allergen_code  text REFERENCES allergen(code),
  resolve        text NOT NULL DEFAULT 'fixed' CHECK (resolve IN ('fixed', 'all', 'context', 'ask')),
                 -- several rows per alias: all apply / M1 picks by dish / ask the user
  CHECK ((ingredient_id IS NULL) <> (allergen_code IS NULL))
);
CREATE INDEX IF NOT EXISTS ingredient_alias_vi_alias_idx ON ingredient_alias_vi (alias);

-- One row per raw line (recipe_ingredient), with what D4 parsed and D5 mapped.
CREATE TABLE IF NOT EXISTS recipe_ingredient_norm (
  recipe_id       integer NOT NULL,
  position        smallint NOT NULL,
  parsed_name     text NOT NULL,
  quantity        text,
  unit            text,
  parse_status    text NOT NULL CHECK (parse_status IN ('ok', 'partial', 'fail')),
  ingredient_ids  integer[] NOT NULL DEFAULT '{}',  -- empty = unknown (D8)
  PRIMARY KEY (recipe_id, position),
  FOREIGN KEY (recipe_id, position) REFERENCES recipe_ingredient(recipe_id, position) ON DELETE CASCADE
);

-- Materialized per Recipe; copied onto chunk (ADR-0001, ADR-0005).
CREATE TABLE IF NOT EXISTS recipe_tag (
  recipe_id         integer PRIMARY KEY REFERENCES recipe(id) ON DELETE CASCADE,
  allergens         text[] NOT NULL,   -- definite allergen codes (D6): the hard filter
  allergens_may     text[] NOT NULL DEFAULT '{}',  -- possible only (D6): a warning, not a filter
  ingredients_norm  text[] NOT NULL,   -- canonical names, D5
  diet_flags        text[] NOT NULL,   -- vegetarian, vegan, D7
  diet_may          text[] NOT NULL DEFAULT '{}',  -- flags that hold only if possible tags are ignored
  has_unknown       boolean NOT NULL,  -- some line maps to no ingredient, D8
  unknown_lines     smallint NOT NULL
);
