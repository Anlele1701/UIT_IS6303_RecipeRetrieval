-- The only copy of the ParadeDB index definition. One index serves BM25, vector
-- search and every filter.
-- Templated on :"tbl" and :"idx" so a staging table gets exactly the parent's
-- definition; otherwise ATTACH PARTITION can't adopt it (spec: "One index definition").
--   psql:      \set tbl chunk  \set idx chunk_search_idx  then \ir indexes.sql
--   ingest.py: index_sql(table, index)
DROP INDEX IF EXISTS :"idx";

CREATE INDEX :"idx" ON :"tbl"
USING paradedb (
  id,
  (content::pdb.simple('stemmer=english')),  -- lowercase + English stemming, stopwords kept
  (category::pdb.literal),
  (kind::pdb.literal),
  (strategy::pdb.literal),
  recipe_id,
  total_minutes, prep_minutes, cook_minutes,
  rating, rating_count, servings,
  calories, protein_g, fat_g, carbohydrates_g, sodium_mg,
  embedding vector_cosine_ops
)
WITH (key_field = 'id');

ANALYZE :"tbl";
