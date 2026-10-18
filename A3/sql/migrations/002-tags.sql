-- One-off for a database built before M1 (e.g. restored from A1's dump): add the tag tables and the
-- tag columns on chunk. A fresh volume gets both from schema.sql.
--
--   docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
--     -f /docker-entrypoint-initdb.d/sql/migrations/002-tags.sql
--
-- Nullable columns on the partitioned parent: metadata only, every partition gets them, nothing is
-- rewritten. They stay NULL until `scripts/tag.py run` fills recipe_tag and `ingest.py retag <strategy>`
-- rebuilds a partition with them (ADR-0001: chunk is rebuilt, never updated in place).

\set ON_ERROR_STOP on
\ir ../tags.sql

ALTER TABLE chunk
  ADD COLUMN IF NOT EXISTS allergens        text[],
  ADD COLUMN IF NOT EXISTS ingredients_norm text[],
  ADD COLUMN IF NOT EXISTS diet_flags       text[],
  ADD COLUMN IF NOT EXISTS has_unknown      boolean;
