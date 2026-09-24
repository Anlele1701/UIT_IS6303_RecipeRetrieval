-- Example queries. Run after `ingest.py index`.
-- psql: docker exec -it recipe-paradedb psql -U recipe -d recipe

-- Sparse retrieval: BM25 over chunks, filters applied inside the index.
SELECT id, recipe_id, kind, pdb.score(id) AS score, content
FROM chunk
WHERE content ||| 'creamy mushroom risotto'
  AND chunker = 'semantic-v1'
  AND category = 'main-dish' AND total_minutes <= 60
ORDER BY score DESC
LIMIT 10;

-- Dense retrieval: nearest chunks by cosine distance. The query vector must be
-- nomic-embed-text of 'search_query: <text>' (scripts/search.py does this).
-- Here an existing chunk's embedding stands in for it; with a subquery the
-- sort is not pushed into the index, so pass a literal/parameter in practice.
SELECT id, recipe_id, kind, 1 - (embedding <=> q.v) AS similarity, content
FROM chunk, (SELECT embedding AS v FROM chunk WHERE id = 1) q
WHERE id @@@ pdb.all()
  AND chunker = 'semantic-v1'
  AND category = 'salad'
ORDER BY embedding <=> q.v
LIMIT 10;

-- Recall/latency knob for vector search (default 0.02, 1.0 = exhaustive).
-- SET paradedb.vector_cluster_max_probe = 0.05;

-- Best chunk per recipe (recipe-level results).
SELECT DISTINCT ON (recipe_id) recipe_id, kind, score, content
FROM (
  SELECT recipe_id, kind, pdb.score(id) AS score, content
  FROM chunk
  WHERE content ||| 'garlic shrimp' AND chunker = 'semantic-v1'
  ORDER BY score DESC
  LIMIT 50
) top
ORDER BY recipe_id, score DESC;

-- ADR-0001 consistency check: copied filter columns must match the source. Expect 0.
SELECT count(*) AS mismatches
FROM chunk c
JOIN recipe r ON r.id = c.recipe_id
JOIN category cat ON cat.id = r.category_id
LEFT JOIN recipe_nutrition n ON n.recipe_id = r.id
WHERE (c.category, c.total_minutes, c.prep_minutes, c.cook_minutes, c.rating, c.rating_count,
       c.servings, c.calories, c.protein_g, c.fat_g, c.carbohydrates_g, c.sodium_mg)
      IS DISTINCT FROM
      (cat.name, r.total_minutes, r.prep_minutes, r.cook_minutes, r.rating, r.rating_count,
       r.servings, n.calories, n.protein_g, n.fat_g, n.carbohydrates_g, n.sodium_mg);
