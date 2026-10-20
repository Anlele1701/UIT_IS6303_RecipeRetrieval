-- Two levels of tags (Thy, M1 review): possible (brand-dependent) allergens are flagged, not filtered.
--   docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
--     -f /docker-entrypoint-initdb.d/sql/migrations/003-possible-tags.sql
\set ON_ERROR_STOP on

ALTER TABLE ingredient_allergen DROP CONSTRAINT IF EXISTS ingredient_allergen_kind_check;
ALTER TABLE ingredient_allergen ADD CONSTRAINT ingredient_allergen_kind_check
  CHECK (kind IN ('direct', 'hidden', 'possible'));

ALTER TABLE recipe_tag
  ADD COLUMN IF NOT EXISTS allergens_may text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS diet_may      text[] NOT NULL DEFAULT '{}';
