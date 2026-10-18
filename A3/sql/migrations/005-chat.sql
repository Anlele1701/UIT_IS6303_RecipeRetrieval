-- Chat tables for the M3 pipeline on a database built before M3. A fresh volume gets them from schema.sql.
--   docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
--     -f /docker-entrypoint-initdb.d/sql/migrations/005-chat.sql
\set ON_ERROR_STOP on
\ir ../chat.sql
