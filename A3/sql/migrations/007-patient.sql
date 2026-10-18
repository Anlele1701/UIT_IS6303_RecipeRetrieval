-- Patient tables and the chat columns that point at them (MV1), on a database built before them.
-- A fresh volume gets them from schema.sql. Adds tables and columns only; no row is changed.
--   docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
--     -f /docker-entrypoint-initdb.d/sql/migrations/007-patient.sql
\set ON_ERROR_STOP on
\ir ../patient.sql
