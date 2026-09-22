"""Database connection and SQL migration helpers for local ParadeDB."""

from pathlib import Path

from src.config import CONFIG


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = PROJECT_ROOT / "sql"


def connect(
    database_url: str = CONFIG.database_url,
    *,
    dict_rows: bool = False,
    register_vectors: bool = True,
):
    import psycopg
    from pgvector.psycopg import register_vector
    from psycopg.rows import dict_row

    kwargs = {"row_factory": dict_row} if dict_rows else {}
    connection = psycopg.connect(database_url, **kwargs)
    if register_vectors:
        register_vector(connection)
    return connection


def apply_migrations(database_url: str = CONFIG.database_url) -> list[str]:
    """Apply every numbered SQL migration exactly once, in filename order."""
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No SQL migrations found in {MIGRATIONS_DIR}")

    applied_now: list[str] = []
    with connect(database_url, register_vectors=False) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM public.schema_migrations"
            ).fetchall()
        }

        for migration_path in migration_files:
            version = migration_path.name
            if version in applied:
                continue
            connection.execute(migration_path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO public.schema_migrations (version) VALUES (%s)",
                (version,),
            )
            connection.commit()
            applied_now.append(version)

    return applied_now
