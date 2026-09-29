-- Fresh-volume entry point for docker-compose. Runs schema.sql from its own
-- folder so its \ir finds indexes.sql (mounting indexes.sql next to this file
-- would make the image run it on its own, without its variables).
\i /docker-entrypoint-initdb.d/sql/schema.sql
