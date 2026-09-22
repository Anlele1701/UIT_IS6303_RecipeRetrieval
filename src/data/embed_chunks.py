"""Store versioned chunks and their sentence-transformer embeddings."""

import numpy as np

from src.config import CONFIG
from src.data.chunking import RecipeChunk


def get_chunk_profile_id(connection, profile_name: str) -> int:
    row = connection.execute(
        """
        SELECT profile_id
        FROM retrieval.chunk_profiles
        WHERE profile_name = %s
        """,
        (profile_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Chunk profile is not registered: {profile_name}")
    return int(row[0])


def upsert_chunks(
    connection,
    chunks: list[RecipeChunk],
    profile_name: str,
) -> tuple[int, int]:
    profile_id = get_chunk_profile_id(connection, profile_name)
    connection.execute(
        """
        CREATE TEMP TABLE chunk_stage (
            recipe_idx BIGINT,
            field_name TEXT,
            chunk_index INTEGER,
            chunk_text TEXT,
            text_hash TEXT,
            token_count INTEGER
        ) ON COMMIT DROP
        """
    )

    with connection.cursor().copy(
        """
        COPY chunk_stage (
            recipe_idx,
            field_name,
            chunk_index,
            chunk_text,
            text_hash,
            token_count
        ) FROM STDIN
        """
    ) as copy:
        for chunk in chunks:
            copy.write_row(
                (
                    chunk.recipe_idx,
                    chunk.field_name,
                    chunk.chunk_index,
                    chunk.text,
                    chunk.text_hash,
                    chunk.token_count,
                )
            )

    connection.execute(
        """
        INSERT INTO retrieval.recipe_chunks (
            recipe_idx,
            profile_id,
            field_name,
            chunk_index,
            chunk_text,
            text_hash,
            token_count
        )
        SELECT
            s.recipe_idx,
            %s,
            s.field_name,
            s.chunk_index,
            s.chunk_text,
            s.text_hash,
            s.token_count
        FROM chunk_stage AS s
        ON CONFLICT (recipe_idx, profile_id, field_name, chunk_index)
        DO UPDATE SET
            chunk_text = EXCLUDED.chunk_text,
            text_hash = EXCLUDED.text_hash,
            token_count = EXCLUDED.token_count,
            updated_at = now()
        """,
        (profile_id,),
    )
    connection.execute(
        """
        DELETE FROM retrieval.recipe_chunks AS c
        WHERE c.profile_id = %s
          AND NOT EXISTS (
              SELECT 1
              FROM chunk_stage AS s
              WHERE s.recipe_idx = c.recipe_idx
                AND s.field_name = c.field_name
                AND s.chunk_index = c.chunk_index
          )
        """,
        (profile_id,),
    )
    return profile_id, len(chunks)


def ensure_embedding_profile(
    connection,
    *,
    profile_name: str,
    model_name: str,
    dimension: int,
    normalize_embeddings: bool = True,
    query_prefix: str = "",
    document_prefix: str = "",
) -> int:
    connection.execute(
        """
        INSERT INTO retrieval.embedding_profiles (
            profile_name,
            model_name,
            dimension,
            normalize_embeddings,
            query_prefix,
            document_prefix
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (profile_name) DO NOTHING
        """,
        (
            profile_name,
            model_name,
            dimension,
            normalize_embeddings,
            query_prefix,
            document_prefix,
        ),
    )
    row = connection.execute(
        """
        SELECT
            embedding_profile_id,
            model_name,
            dimension,
            normalize_embeddings,
            query_prefix,
            document_prefix
        FROM retrieval.embedding_profiles
        WHERE profile_name = %s
        """,
        (profile_name,),
    ).fetchone()
    expected = (
        model_name,
        dimension,
        normalize_embeddings,
        query_prefix,
        document_prefix,
    )
    if row is None or tuple(row[1:]) != expected:
        raise ValueError(
            f"Embedding profile {profile_name!r} exists with different settings; "
            "create a new versioned profile name"
        )
    if dimension != CONFIG.embedding_dimension:
        raise ValueError(
            f"Database column is vector({CONFIG.embedding_dimension}), "
            f"but profile requests dimension {dimension}"
        )
    return int(row[0])


def embed_missing_chunks(
    connection,
    *,
    chunk_profile_id: int,
    embedding_profile_id: int,
    model_name: str,
    document_prefix: str = "",
    batch_size: int = 64,
) -> int:
    pending = connection.execute(
        """
        SELECT c.chunk_id, c.chunk_text, c.text_hash
        FROM retrieval.recipe_chunks AS c
        LEFT JOIN retrieval.chunk_embeddings AS e
          ON e.chunk_id = c.chunk_id
         AND e.embedding_profile_id = %s
        WHERE c.profile_id = %s
          AND (e.chunk_id IS NULL OR e.text_hash <> c.text_hash)
        ORDER BY c.chunk_id
        """,
        (embedding_profile_id, chunk_profile_id),
    ).fetchall()
    if not pending:
        return 0

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    texts = [f"{document_prefix}{row[1]}" for row in pending]
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    embeddings = np.asarray(embeddings, dtype="float32")
    if embeddings.shape[1] != CONFIG.embedding_dimension:
        raise ValueError(
            f"Model produced {embeddings.shape[1]} dimensions; "
            f"expected {CONFIG.embedding_dimension}"
        )

    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO retrieval.chunk_embeddings (
                chunk_id,
                embedding_profile_id,
                embedding,
                text_hash
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (chunk_id, embedding_profile_id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                text_hash = EXCLUDED.text_hash,
                updated_at = now()
            """,
            [
                (
                    row[0],
                    embedding_profile_id,
                    embedding,
                    row[2],
                )
                for row, embedding in zip(pending, embeddings)
            ],
        )
    return len(pending)
