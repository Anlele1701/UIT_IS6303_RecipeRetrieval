"""A throwaway `recipe_test` database, built from sql/schema.sql inside the recipe-paradedb container.

Tests that use it are skipped when the container isn't running.
"""

import subprocess

import numpy as np
import psycopg
import pytest

import ingest
from api import config

CONTAINER = "recipe-paradedb"
TEST_DB = "recipe_test"
TEST_URL = config.DATABASE_URL.rsplit("/", 1)[0] + f"/{TEST_DB}"


@pytest.fixture(scope="session")
def test_db_url():
    try:
        admin = psycopg.connect(config.DATABASE_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("recipe-paradedb is not running")
    with admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {TEST_DB}")
    subprocess.run(["docker", "exec", CONTAINER, "psql", "-q", "-U", "recipe", "-d", TEST_DB,
                    "-v", "ON_ERROR_STOP=1", "-f", "/docker-entrypoint-initdb.d/sql/schema.sql"],
                   check=True, capture_output=True)
    return TEST_URL


@pytest.fixture
def db(test_db_url):
    """A connection to the test DB with an empty registry and no chunk partitions."""
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        for (name,) in conn.execute("SELECT name FROM chunking_strategy").fetchall():
            conn.execute(f'DROP TABLE IF EXISTS "chunk_{name}", "chunk_{name}_staging"')
        conn.execute("DELETE FROM chunking_strategy")
        yield conn


def add_strategy(conn, name, loaded=True):
    conn.execute("INSERT INTO chunking_strategy (name, method, parameters, loaded_at) "
                 "VALUES (%s, %s, '{}', CASE WHEN %s THEN now() END)", [name, name, loaded])


RECIPES = [  # title, directions, ingredient lines
    ("Garlic Shrimp", "Heat oil. Add garlic. Stir. Add shrimp. Cook 3 minutes.", ["1 lb shrimp", "4 cloves garlic"]),
    ("Toast", "Toast the bread.", ["2 slices bread"]),
    ("Tea", "Boil water. Steep ½ hour. Pour.", ["1 tea bag"]),
]


@pytest.fixture
def recipes(db):
    """The test DB holding just RECIPES, ids 1..3 in order."""
    db.execute("TRUNCATE category, author, recipe, recipe_nutrition, recipe_ingredient RESTART IDENTITY CASCADE")
    db.execute("INSERT INTO category (name) VALUES ('Main')")
    for i, (title, directions, lines) in enumerate(RECIPES):
        rid = db.execute(
            """INSERT INTO recipe (url, title, description, directions, category_id, rating,
                 rating_count, review_count, total_minutes, servings)
               VALUES (%s, %s, 'Nice.', %s, 1, 4.5, 10, 3, 20, 2) RETURNING id""",
            [f"u{i}", title, directions]).fetchone()[0]
        db.execute("INSERT INTO recipe_nutrition (recipe_id, calories) VALUES (%s, 100)", [rid])
        for pos, line in enumerate(lines, 1):
            db.execute("INSERT INTO recipe_ingredient VALUES (%s, %s, %s)", [rid, pos, line])
    return db


@pytest.fixture
def fake_embed(monkeypatch):
    """ingest.embed without Ollama: random unit vectors, the same for the same batch size."""
    def embed(texts):
        v = np.random.default_rng(len(texts)).random((len(texts), 768), dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)
    monkeypatch.setattr(ingest, "embed", embed)
