-- Confirmed lifts of record constraints (MV5): the only way a constraint that comes from a patient's record leaves
-- a chat session (a chat message cannot lift it, M2). Written by Assistant.lift_record_constraint, which the UI's
-- PATCH /chat/{session}/constraints/{id} with confirm=true calls (M4). Adds a table only; no row is changed.
--   docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
--     -f /docker-entrypoint-initdb.d/sql/migrations/009-record-lift.sql
\set ON_ERROR_STOP on
\ir ../record_lift.sql
