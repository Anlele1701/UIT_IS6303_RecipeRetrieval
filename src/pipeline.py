"""Command-line entry point for the reproducible retrieval indexing pipeline."""

import argparse
import sys

from src.config import CONFIG
from src.data.chunking import chunk_recipes
from src.data.embed_chunks import (
    embed_missing_chunks,
    ensure_embedding_profile,
    get_chunk_profile_id,
    upsert_chunks,
)
from src.data.ingest_postgres import upsert_raw_recipes
from src.data.loader import load_subset
from src.data.validate_pipeline import validate_pipeline
from src.db import apply_migrations, connect


def _start_run(
    connection,
    *,
    chunk_profile_name: str,
    embedding_profile_name: str,
) -> int:
    return int(
        connection.execute(
            """
            INSERT INTO retrieval.pipeline_runs (
                dataset_revision,
                dataset_split,
                subset_size,
                subset_seed,
                chunk_profile_name,
                embedding_profile_name,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'running')
            RETURNING run_id
            """,
            (
                CONFIG.dataset_revision,
                CONFIG.corpus_split,
                CONFIG.subset_size,
                CONFIG.seed,
                chunk_profile_name,
                embedding_profile_name,
            ),
        ).fetchone()[0]
    )


def _finish_run(
    connection,
    run_id: int,
    *,
    status: str,
    counts: dict[str, int] | None = None,
    error_message: str | None = None,
) -> None:
    counts = counts or {}
    connection.execute(
        """
        UPDATE retrieval.pipeline_runs
        SET status = %s,
            recipe_count = %s,
            chunk_count = %s,
            embedding_count = %s,
            error_message = %s,
            finished_at = now()
        WHERE run_id = %s
        """,
        (
            status,
            counts.get("recipe_count"),
            counts.get("chunk_count"),
            counts.get("embedding_count"),
            error_message,
            run_id,
        ),
    )


def migrate(
    *,
    chunk_profile_name: str,
    embedding_profile_name: str,
    model_name: str,
    rebuild: bool = False,
) -> dict[str, int]:
    applied = apply_migrations()
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")

    with connect() as connection:
        run_id = _start_run(
            connection,
            chunk_profile_name=chunk_profile_name,
            embedding_profile_name=embedding_profile_name,
        )
        connection.commit()

    try:
        recipes = load_subset(
            split=CONFIG.corpus_split,
            subset_size=CONFIG.subset_size,
            seed=CONFIG.seed,
        )
        chunks = chunk_recipes(recipes, chunk_profile_name)

        with connect() as connection:
            upsert_raw_recipes(connection, recipes)
            chunk_profile_id = get_chunk_profile_id(
                connection,
                chunk_profile_name,
            )
            if rebuild:
                connection.execute(
                    """
                    DELETE FROM retrieval.recipe_chunks
                    WHERE profile_id = %s
                    """,
                    (chunk_profile_id,),
                )

            chunk_profile_id, _ = upsert_chunks(
                connection,
                chunks,
                chunk_profile_name,
            )
            embedding_profile_id = ensure_embedding_profile(
                connection,
                profile_name=embedding_profile_name,
                model_name=model_name,
                dimension=CONFIG.embedding_dimension,
                normalize_embeddings=True,
            )
            embedded_count = embed_missing_chunks(
                connection,
                chunk_profile_id=chunk_profile_id,
                embedding_profile_id=embedding_profile_id,
                model_name=model_name,
            )
            counts = validate_pipeline(
                connection,
                expected_recipe_count=len(recipes),
                chunk_profile_id=chunk_profile_id,
                embedding_profile_id=embedding_profile_id,
            )
            _finish_run(connection, run_id, status="completed", counts=counts)

        print(
            "Pipeline complete: "
            f"{counts['recipe_count']} recipes, "
            f"{counts['chunk_count']} chunks, "
            f"{counts['embedding_count']} embeddings "
            f"({embedded_count} encoded in this run)"
        )
        return counts
    except Exception as exc:
        with connect() as connection:
            _finish_run(
                connection,
                run_id,
                status="failed",
                error_message=str(exc)[:4000],
            )
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Migrate schema and index the configured Hugging Face subset",
    )
    migrate_parser.add_argument(
        "--chunk-profile",
        default=CONFIG.chunk_profile_name,
    )
    migrate_parser.add_argument(
        "--embedding-profile",
        default=CONFIG.embedding_profile_name,
    )
    migrate_parser.add_argument(
        "--model",
        default=CONFIG.embedding_model_name,
    )
    migrate_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Recreate chunks and embeddings for the selected chunk profile",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "migrate":
        migrate(
            chunk_profile_name=args.chunk_profile,
            embedding_profile_name=args.embedding_profile,
            model_name=args.model,
            rebuild=args.rebuild,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
