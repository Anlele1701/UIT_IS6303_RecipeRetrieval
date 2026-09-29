from ingest import index_sql


def test_index_sql_builds_the_named_index_on_the_named_table():
    text = index_sql("chunk_fixed_staging", "chunk_fixed_staging_search_idx").as_string()
    assert 'DROP INDEX IF EXISTS "chunk_fixed_staging_search_idx"' in text
    assert 'CREATE INDEX "chunk_fixed_staging_search_idx" ON "chunk_fixed_staging"' in text
    assert 'ANALYZE "chunk_fixed_staging"' in text
    assert ':"' not in text  # no psql variable left behind


def test_index_sql_quotes_names_instead_of_pasting_them():
    text = index_sql('chunk_"x', "idx").as_string()
    assert 'ON "chunk_""x"' in text
