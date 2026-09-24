-- Built after chunk is loaded (bulk build is much faster than incremental).
-- One ParadeDB index serves BM25, vector search and every filter.
DROP INDEX IF EXISTS chunk_search_idx;

CREATE INDEX chunk_search_idx ON chunk
USING paradedb (
  id,
  (content::pdb.simple('stemmer=english')),  -- lowercase + English stemming, stopwords kept
  (category::pdb.literal),
  (kind::pdb.literal),
  (chunker::pdb.literal),
  recipe_id,
  total_minutes, prep_minutes, cook_minutes,
  rating, rating_count, servings,
  calories, protein_g, fat_g, carbohydrates_g, sodium_mg,
  embedding vector_cosine_ops
)
WITH (key_field = 'id');

ANALYZE chunk;
