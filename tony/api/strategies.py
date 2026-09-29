"""The Chunking strategy registry (`chunking_strategy`). Read on every request, never cached,
so a strategy that finishes loading is searchable without a restart."""

import psycopg
from psycopg.rows import dict_row


def registry(conn: psycopg.Connection) -> dict[str, bool]:
    """Every registered name -> whether it is loaded."""
    return dict(conn.execute("SELECT name, loaded_at IS NOT NULL FROM chunking_strategy").fetchall())


def strategy_problem(name: str, registry: dict[str, bool]) -> str | None:
    """Why `name` can't be searched, or None if it can."""
    if name not in registry:
        loaded = ", ".join(sorted(n for n, ok in registry.items() if ok))
        return f"'{name}' is unknown; loaded: {loaded}"
    if not registry[name]:
        return f"'{name}' is not loaded yet"
    return None


def loaded(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute("""SELECT name, method, parameters, loaded_at FROM chunking_strategy
                              WHERE loaded_at IS NOT NULL ORDER BY name""").fetchall()


def chunk_counts(conn: psycopg.Connection) -> dict[str, int]:
    """Chunks per loaded strategy; a loaded strategy with 0 is a problem worth seeing."""
    return dict(conn.execute("""SELECT s.name, count(c.id) FROM chunking_strategy s
                                LEFT JOIN chunk c ON c.strategy = s.name
                                WHERE s.loaded_at IS NOT NULL GROUP BY s.name ORDER BY s.name""").fetchall())
