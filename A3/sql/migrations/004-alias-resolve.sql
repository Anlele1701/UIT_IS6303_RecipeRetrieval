-- How an ambiguous Vietnamese alias is resolved (Thy, M1 review): fixed / all / context / ask.
--   docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
--     -f /docker-entrypoint-initdb.d/sql/migrations/004-alias-resolve.sql
\set ON_ERROR_STOP on
ALTER TABLE ingredient_alias_vi ADD COLUMN IF NOT EXISTS resolve text NOT NULL DEFAULT 'fixed'
  CHECK (resolve IN ('fixed', 'all', 'context', 'ask'));
