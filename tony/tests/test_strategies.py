import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import strategies
from api.filters import SearchParams
from api.main import app, get_conn
from conftest import add_strategy


# --- which names can be searched --------------------------------------------

def test_a_loaded_strategy_has_no_problem():
    assert strategies.strategy_problem("semantic", {"semantic": True}) is None


def test_an_unloaded_strategy_says_so():
    assert strategies.strategy_problem("fixed", {"semantic": True, "fixed": False}) == "'fixed' is not loaded yet"


def test_an_unknown_strategy_lists_the_loaded_ones_by_name():
    registry = {"sentence": True, "fixed": False, "semantic": True}
    assert strategies.strategy_problem("foo", registry) == "'foo' is unknown; loaded: semantic, sentence"


def test_search_params_require_a_strategy():
    with pytest.raises(ValidationError):
        SearchParams(q="x")


def test_the_old_chunker_parameter_is_rejected():
    with pytest.raises(ValidationError):
        SearchParams(q="x", strategy="semantic", chunker="semantic")


# --- against a real registry (test DB) ---------------------------------------

@pytest.fixture
def client(db):
    def conn():
        yield db
    app.dependency_overrides[get_conn] = conn
    yield TestClient(app)  # no `with`: skips startup, so no reranker or embedding service
    app.dependency_overrides.clear()


def test_strategies_lists_only_loaded_ones_ordered_by_name(client, db):
    add_strategy(db, "sentence")
    add_strategy(db, "fixed", loaded=False)
    add_strategy(db, "semantic")
    body = client.get("/strategies").json()
    assert [s["name"] for s in body] == ["semantic", "sentence"]
    assert set(body[0]) == {"name", "method", "parameters", "loaded_at"}


def test_a_strategy_loaded_while_running_shows_up_without_a_restart(client, db):
    add_strategy(db, "semantic")
    assert [s["name"] for s in client.get("/strategies").json()] == ["semantic"]
    add_strategy(db, "fixed", loaded=False)
    db.execute("UPDATE chunking_strategy SET loaded_at = now() WHERE name = 'fixed'")
    assert [s["name"] for s in client.get("/strategies").json()] == ["fixed", "semantic"]


@pytest.mark.parametrize("query, message", [
    ({}, "Field required"),
    ({"strategy": "fixed"}, "'fixed' is not loaded yet"),
    ({"strategy": "foo"}, "'foo' is unknown; loaded: semantic"),
])
def test_search_rejects_a_missing_unloaded_or_unknown_strategy(client, db, query, message):
    add_strategy(db, "semantic")
    add_strategy(db, "fixed", loaded=False)
    for method in ("sparse", "dense", "hybrid"):
        r = client.get(f"/search/{method}", params={"q": "garlic", **query})
        assert r.status_code == 422
        [error] = r.json()["detail"]
        assert error["loc"][-1] == "strategy" and error["msg"] == message


def test_search_echoes_the_strategy(client, db):
    add_strategy(db, "semantic")
    db.execute("CREATE TABLE chunk_semantic PARTITION OF chunk FOR VALUES IN ('semantic')")
    body = client.get("/search/sparse", params={"q": "garlic", "strategy": "semantic"}).json()
    assert (body["method"], body["strategy"], body["results"]) == ("sparse", "semantic", [])


def test_chunk_counts_cover_every_loaded_strategy_even_when_empty(db):
    add_strategy(db, "semantic")
    add_strategy(db, "fixed", loaded=False)
    assert strategies.chunk_counts(db) == {"semantic": 0}
