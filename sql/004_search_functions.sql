CREATE OR REPLACE FUNCTION retrieval.match_sparse(
    p_query_text TEXT,
    p_chunk_profile_id BIGINT,
    p_match_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    recipe_idx BIGINT,
    score DOUBLE PRECISION,
    name TEXT,
    image_path TEXT,
    searchable_text TEXT
)
LANGUAGE sql
STABLE
AS $$
    WITH chunk_hits AS (
        SELECT
            c.recipe_idx,
            pdb.score(c.chunk_id)::DOUBLE PRECISION AS chunk_score
        FROM retrieval.recipe_chunks AS c
        WHERE c.profile_id = p_chunk_profile_id
          AND c.chunk_text ||| p_query_text
        ORDER BY chunk_score DESC, c.chunk_id ASC
        LIMIT GREATEST(p_match_count * 5, p_match_count)
    ),
    recipe_hits AS (
        SELECT ch.recipe_idx, MAX(ch.chunk_score) AS recipe_score
        FROM chunk_hits AS ch
        GROUP BY ch.recipe_idx
    )
    SELECT
        r.recipe_idx,
        rh.recipe_score,
        r.name,
        r.image_path,
        concat_ws(' ', r.name, r.ingredients, r.description)
    FROM recipe_hits AS rh
    JOIN raw.recipes AS r ON r.recipe_idx = rh.recipe_idx
    ORDER BY rh.recipe_score DESC, r.recipe_idx ASC
    LIMIT p_match_count;
$$;

CREATE OR REPLACE FUNCTION retrieval.match_dense(
    p_query_embedding vector(384),
    p_chunk_profile_id BIGINT,
    p_embedding_profile_id BIGINT,
    p_match_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    recipe_idx BIGINT,
    score DOUBLE PRECISION,
    name TEXT,
    image_path TEXT,
    searchable_text TEXT
)
LANGUAGE sql
STABLE
AS $$
    WITH chunk_hits AS (
        SELECT
            c.recipe_idx,
            (1 - (e.embedding <=> p_query_embedding))::DOUBLE PRECISION AS chunk_score
        FROM retrieval.chunk_embeddings AS e
        JOIN retrieval.recipe_chunks AS c ON c.chunk_id = e.chunk_id
        WHERE c.profile_id = p_chunk_profile_id
          AND e.embedding_profile_id = p_embedding_profile_id
        ORDER BY e.embedding <=> p_query_embedding, c.chunk_id ASC
        LIMIT GREATEST(p_match_count * 5, p_match_count)
    ),
    recipe_hits AS (
        SELECT ch.recipe_idx, MAX(ch.chunk_score) AS recipe_score
        FROM chunk_hits AS ch
        GROUP BY ch.recipe_idx
    )
    SELECT
        r.recipe_idx,
        rh.recipe_score,
        r.name,
        r.image_path,
        concat_ws(' ', r.name, r.ingredients, r.description)
    FROM recipe_hits AS rh
    JOIN raw.recipes AS r ON r.recipe_idx = rh.recipe_idx
    ORDER BY rh.recipe_score DESC, r.recipe_idx ASC
    LIMIT p_match_count;
$$;

CREATE OR REPLACE FUNCTION retrieval.match_hybrid(
    p_query_text TEXT,
    p_query_embedding vector(384),
    p_chunk_profile_id BIGINT,
    p_embedding_profile_id BIGINT,
    p_match_count INTEGER DEFAULT 10,
    p_candidate_count INTEGER DEFAULT 100,
    p_rrf_k INTEGER DEFAULT 60
)
RETURNS TABLE (
    recipe_idx BIGINT,
    score DOUBLE PRECISION,
    name TEXT,
    image_path TEXT,
    searchable_text TEXT
)
LANGUAGE sql
STABLE
AS $$
    WITH sparse_ranked AS (
        SELECT
            s.recipe_idx,
            ROW_NUMBER() OVER (ORDER BY s.score DESC, s.recipe_idx ASC) AS rank
        FROM retrieval.match_sparse(
            p_query_text,
            p_chunk_profile_id,
            p_candidate_count
        ) AS s
    ),
    dense_ranked AS (
        SELECT
            d.recipe_idx,
            ROW_NUMBER() OVER (ORDER BY d.score DESC, d.recipe_idx ASC) AS rank
        FROM retrieval.match_dense(
            p_query_embedding,
            p_chunk_profile_id,
            p_embedding_profile_id,
            p_candidate_count
        ) AS d
    ),
    fused AS (
        SELECT
            COALESCE(s.recipe_idx, d.recipe_idx) AS recipe_idx,
            COALESCE(1.0 / (p_rrf_k + s.rank), 0.0)
              + COALESCE(1.0 / (p_rrf_k + d.rank), 0.0) AS fused_score
        FROM sparse_ranked AS s
        FULL OUTER JOIN dense_ranked AS d USING (recipe_idx)
    )
    SELECT
        r.recipe_idx,
        f.fused_score::DOUBLE PRECISION,
        r.name,
        r.image_path,
        concat_ws(' ', r.name, r.ingredients, r.description)
    FROM fused AS f
    JOIN raw.recipes AS r ON r.recipe_idx = f.recipe_idx
    ORDER BY f.fused_score DESC, r.recipe_idx ASC
    LIMIT p_match_count;
$$;
