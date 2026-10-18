-- Group lifts of record constraints (MV5, after Thy's review): a lift row lists the constraint ids it took out.
-- Adds a column only; no row is changed (no lift existed before it).
--   docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
--     -f /docker-entrypoint-initdb.d/sql/migrations/010-record-lift-groups.sql
\set ON_ERROR_STOP on
ALTER TABLE session_record_lift ADD COLUMN IF NOT EXISTS members text[] NOT NULL DEFAULT '{}';
