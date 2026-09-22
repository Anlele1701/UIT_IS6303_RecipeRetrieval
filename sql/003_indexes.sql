CREATE INDEX IF NOT EXISTS recipe_chunks_profile_recipe_idx
    ON retrieval.recipe_chunks (profile_id, recipe_idx);

CREATE INDEX IF NOT EXISTS chunk_embeddings_profile_chunk_idx
    ON retrieval.chunk_embeddings (embedding_profile_id, chunk_id);

CREATE INDEX IF NOT EXISTS recipe_chunks_search_idx
    ON retrieval.recipe_chunks
    USING paradedb (chunk_id, recipe_idx, profile_id, field_name, chunk_text)
    WITH (key_field = 'chunk_id');
