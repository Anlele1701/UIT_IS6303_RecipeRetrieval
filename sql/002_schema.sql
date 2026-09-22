CREATE TABLE IF NOT EXISTS raw.recipes (
    recipe_idx BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    ingredients TEXT NOT NULL,
    description TEXT NOT NULL,
    image_path TEXT,
    dataset_split TEXT NOT NULL,
    dataset_revision TEXT NOT NULL,
    subset_seed INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retrieval.chunk_profiles (
    profile_id BIGSERIAL PRIMARY KEY,
    profile_name TEXT NOT NULL UNIQUE,
    strategy TEXT NOT NULL CHECK (strategy IN ('full_recipe', 'field_chunk')),
    fields TEXT[] NOT NULL,
    chunk_size INTEGER,
    chunk_overlap INTEGER,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retrieval.recipe_chunks (
    chunk_id BIGSERIAL PRIMARY KEY,
    recipe_idx BIGINT NOT NULL REFERENCES raw.recipes(recipe_idx) ON DELETE CASCADE,
    profile_id BIGINT NOT NULL REFERENCES retrieval.chunk_profiles(profile_id) ON DELETE CASCADE,
    field_name TEXT NOT NULL DEFAULT '',
    chunk_index INTEGER NOT NULL DEFAULT 0,
    chunk_text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (recipe_idx, profile_id, field_name, chunk_index)
);

CREATE TABLE IF NOT EXISTS retrieval.embedding_profiles (
    embedding_profile_id BIGSERIAL PRIMARY KEY,
    profile_name TEXT NOT NULL UNIQUE,
    model_name TEXT NOT NULL,
    model_revision TEXT,
    dimension INTEGER NOT NULL,
    normalize_embeddings BOOLEAN NOT NULL DEFAULT TRUE,
    query_prefix TEXT NOT NULL DEFAULT '',
    document_prefix TEXT NOT NULL DEFAULT '',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retrieval.chunk_embeddings (
    chunk_id BIGINT NOT NULL REFERENCES retrieval.recipe_chunks(chunk_id) ON DELETE CASCADE,
    embedding_profile_id BIGINT NOT NULL REFERENCES retrieval.embedding_profiles(embedding_profile_id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,
    text_hash TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chunk_id, embedding_profile_id)
);

CREATE TABLE IF NOT EXISTS retrieval.pipeline_runs (
    run_id BIGSERIAL PRIMARY KEY,
    dataset_revision TEXT NOT NULL,
    dataset_split TEXT NOT NULL,
    subset_size INTEGER NOT NULL,
    subset_seed INTEGER NOT NULL,
    chunk_profile_name TEXT NOT NULL,
    embedding_profile_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    recipe_count INTEGER,
    chunk_count INTEGER,
    embedding_count INTEGER,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

INSERT INTO retrieval.chunk_profiles (
    profile_name, strategy, fields, config
) VALUES
    (
        'full_recipe_v1',
        'full_recipe',
        ARRAY['name', 'ingredients', 'description'],
        '{"description":"One searchable chunk per recipe"}'::jsonb
    ),
    (
        'field_chunk_v1',
        'field_chunk',
        ARRAY['name', 'ingredients', 'description'],
        '{"description":"One searchable chunk per non-empty recipe field"}'::jsonb
    )
ON CONFLICT (profile_name) DO NOTHING;
