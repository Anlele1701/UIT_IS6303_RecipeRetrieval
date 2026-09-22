"""Integrity and smoke-query checks for the retrieval database."""


def validate_pipeline(
    connection,
    *,
    expected_recipe_count: int,
    chunk_profile_id: int,
    embedding_profile_id: int,
) -> dict[str, int]:
    recipe_count = int(
        connection.execute("SELECT count(*) FROM raw.recipes").fetchone()[0]
    )
    chunk_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM retrieval.recipe_chunks
            WHERE profile_id = %s
            """,
            (chunk_profile_id,),
        ).fetchone()[0]
    )
    embedding_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM retrieval.chunk_embeddings AS e
            JOIN retrieval.recipe_chunks AS c ON c.chunk_id = e.chunk_id
            WHERE c.profile_id = %s
              AND e.embedding_profile_id = %s
            """,
            (chunk_profile_id, embedding_profile_id),
        ).fetchone()[0]
    )

    if recipe_count != expected_recipe_count:
        raise RuntimeError(
            f"Expected {expected_recipe_count} recipes, found {recipe_count}"
        )
    if chunk_count == 0:
        raise RuntimeError("Chunking produced no rows")
    if embedding_count != chunk_count:
        raise RuntimeError(
            f"Expected one embedding per chunk, found {embedding_count}/{chunk_count}"
        )

    smoke = connection.execute(
        """
        WITH sample AS (
            SELECT r.name, e.embedding
            FROM raw.recipes AS r
            JOIN retrieval.recipe_chunks AS c ON c.recipe_idx = r.recipe_idx
            JOIN retrieval.chunk_embeddings AS e ON e.chunk_id = c.chunk_id
            WHERE c.profile_id = %s
              AND e.embedding_profile_id = %s
            ORDER BY r.recipe_idx
            LIMIT 1
        )
        SELECT
            (
                SELECT count(*)
                FROM retrieval.match_sparse(
                    (SELECT name FROM sample),
                    %s,
                    1
                )
            ) AS sparse_count,
            (
                SELECT count(*)
                FROM retrieval.match_dense(
                    (SELECT embedding FROM sample),
                    %s,
                    %s,
                    1
                )
            ) AS dense_count
        """,
        (
            chunk_profile_id,
            embedding_profile_id,
            chunk_profile_id,
            chunk_profile_id,
            embedding_profile_id,
        ),
    ).fetchone()
    if smoke is None or smoke[0] < 1 or smoke[1] < 1:
        raise RuntimeError(f"Retrieval smoke test failed: {smoke}")

    return {
        "recipe_count": recipe_count,
        "chunk_count": chunk_count,
        "embedding_count": embedding_count,
    }
