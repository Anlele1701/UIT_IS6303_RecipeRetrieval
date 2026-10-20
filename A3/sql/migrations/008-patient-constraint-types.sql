-- Constraint types a patient record adds to a chat session (MV3): per-serving nutrient limits, hard and soft.
-- A fresh volume gets them from chat.sql. Changes a CHECK constraint only; no row is changed.
--   docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
--     -f /docker-entrypoint-initdb.d/sql/migrations/008-patient-constraint-types.sql
\set ON_ERROR_STOP on
ALTER TABLE session_constraint DROP CONSTRAINT IF EXISTS session_constraint_type_check;
ALTER TABLE session_constraint ADD CONSTRAINT session_constraint_type_check
  CHECK (type IN ('allergen', 'ingredient_exclude', 'ingredient_include', 'diet', 'max_total_minutes', 'max_calories',
                  'category', 'nutrient', 'nutrient_soft'));
