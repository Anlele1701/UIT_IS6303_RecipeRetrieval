-- Chunk profiles for Ablation D (text representation) in
-- docs/10_ABLATION_STUDY.md. Same 'full_recipe' strategy as
-- full_recipe_v1, but fewer source fields, so the ablation isolates which
-- fields carry the retrieval signal. retrieval.match_sparse and
-- retrieval.match_dense are already parameterised by profile_id, so no
-- search function changes are needed.

INSERT INTO retrieval.chunk_profiles (
    profile_name, strategy, fields, config
) VALUES
    (
        'name_only_v1',
        'full_recipe',
        ARRAY['name'],
        '{"description":"One chunk per recipe, recipe name only"}'::jsonb
    ),
    (
        'name_ingredients_v1',
        'full_recipe',
        ARRAY['name', 'ingredients'],
        '{"description":"One chunk per recipe, name plus normalized ingredients"}'::jsonb
    )
ON CONFLICT (profile_name) DO NOTHING;
