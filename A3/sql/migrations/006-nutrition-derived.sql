-- Derived nutrition columns on chunk (MV2, ADR-0007), so patient nutrient limits filter inside the ParadeDB index.
-- Adds nullable columns only: every partition gets them, empty. Fill one strategy (and rebuild the index with the
-- new sql/indexes.sql) by rebuilding it: `uv run scripts/ingest.py retag <strategy>`.
--   docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
--     -f /docker-entrypoint-initdb.d/sql/migrations/006-nutrition-derived.sql
\set ON_ERROR_STOP on
ALTER TABLE chunk
  ADD COLUMN IF NOT EXISTS sat_fat_pct_kcal   real,
  ADD COLUMN IF NOT EXISTS sugar_pct_kcal     real,
  ADD COLUMN IF NOT EXISTS fiber_per_1000kcal real,
  ADD COLUMN IF NOT EXISTS potassium_mg       real;
