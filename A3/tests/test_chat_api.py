"""M4: the chat API over the pipeline, on the throwaway test DB with fake models (no Ollama)."""

import json
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import ingest
import patient_ingest
import tag
from api.chat_api import assistant_factory
from api.main import app
from api.pipeline import orchestrator as orch
from api.pipeline.lexicon import RuntimeLexicon
from api.pipeline.schemas import Understanding

FIXTURE = Path(__file__).parent / "patient" / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"
PID = "887e4b4e-a3e1-b573-4a16-38386d3e0b88"
QVEC = "[" + ",".join(["0.036"] * 768) + "]"
NAMES = ["Barton704", "Upton904"]


@pytest.fixture
def bot(recipes, fake_embed, monkeypatch, tmp_path):
    report, tables = tag.tag_all(recipes)
    tag.write_tables(recipes, tables)
    ingest.run(recipes, ["chunk", "sentence"])
    recipes.execute("TRUNCATE patient CASCADE")
    folder = tmp_path / "sample"
    folder.mkdir()
    (folder / FIXTURE.name).write_bytes(FIXTURE.read_bytes())
    patient_ingest.cmd_load(recipes, [(folder, "sample")])
    monkeypatch.setattr(orch, "embed_query", lambda client, text: QVEC)
    return orch.Assistant(recipes, client=None, scorer=lambda q, texts: np.zeros(len(texts)), lex=RuntimeLexicon(),
                          strategy="sentence")


@pytest.fixture
def client(bot):
    @contextmanager
    def make():
        yield bot
    app.dependency_overrides[assistant_factory] = lambda: make
    yield TestClient(app)  # no `with`: skips startup (no pool, reranker or Ollama)
    app.dependency_overrides.clear()


def fake(monkeypatch, understood: list, answers: list):
    def understand(client, lex, message, history, current, patient=False):
        return understood.pop(0)
    monkeypatch.setattr(orch, "understand", understand)
    monkeypatch.setattr(orch.m6, "generate", lambda client, messages, usage=None, **kw: iter([answers.pop(0)]))


def events(resp) -> list[tuple[str, object]]:
    out = []
    for block in resp.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_a_patient_turn_streams_the_events_in_order(client, monkeypatch):
    fake(monkeypatch, [Understanding(lang="vi", query_en="tea toast shrimp")], ["Thử [R3] [H:allergies]."])
    r = client.post("/chat", json={"message": "gợi ý món", "patient_id": PID})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    evs = events(r)
    assert [t for t, _ in evs] == ["patient_profile", "constraints", "recipes", "token", "done"]
    assert evs[3][1] == "Thử [R3] [H:allergies]." and evs[4][1]["citations"] == [3]
    assert r.headers["x-session-id"] == evs[1][1]["session_id"]
    for name in NAMES:
        assert name not in r.text


def test_a_second_turn_keeps_the_session_and_its_preset(client, monkeypatch, bot):
    fake(monkeypatch, [Understanding(query_en="tea"), Understanding(query_en="toast")], ["[R3]", "ok"])
    sid = dict(events(client.post("/chat", json={"message": "tea", "preset": "B0"})))["constraints"]["session_id"]
    client.post("/chat", json={"message": "toast", "session_id": sid})
    view = client.get(f"/sessions/{sid}").json()
    assert view["preset"] == "B0" and [m["role"] for m in view["messages"]] == ["user", "assistant"] * 2


def test_bad_requests_are_http_errors(client, bot):
    assert client.post("/chat", json={"message": "x", "preset": "nope"}).status_code == 422
    assert client.post("/chat", json={"message": "x", "session_id": "not-a-uuid"}).status_code == 404
    bot.conn.execute("UPDATE patient SET deceased = true WHERE patient_id = %s", [PID])
    assert client.post("/chat", json={"message": "x", "patient_id": PID}).status_code == 409


def test_a_model_failure_ends_the_stream_with_an_error_event(client, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("ollama is down")
    monkeypatch.setattr(orch, "understand", broken)
    evs = events(client.post("/chat", json={"message": "tea"}))
    assert evs[-1][0] == "error" and "ollama is down" in evs[-1][1]["detail"]


def test_session_view_names_constraints_and_patch_removes_a_dialogue_one(client, monkeypatch):
    fake(monkeypatch, [Understanding(query_en="tea", constraints={"ingredients_exclude": ["onion"]},
                                     session_scope=["ingredients_exclude"]),
                       Understanding(intent="refine", query_en="tea")], ["[R3]", "[R3]"])
    sid = dict(events(client.post("/chat", json={"message": "tea, no onion"})))["constraints"]["session_id"]
    ids = [c["constraint_id"] for c in client.get(f"/sessions/{sid}").json()["constraints"]]
    assert "ingredient:onion" in ids
    r = client.patch(f"/chat/{sid}/constraints/ingredient:onion", json={"action": "remove"})
    assert r.status_code == 200 and r.json()["kind"] == "dialogue"
    second = dict(events(client.post("/chat", json={"message": "more tea", "session_id": sid})))
    assert "onion" not in second["constraints"]["constraints"]["ingredients_exclude"]
    assert client.patch(f"/chat/{sid}/constraints/diet:vegan", json={}).status_code == 404


def test_a_record_constraint_needs_confirm_and_a_group_goes_at_once(client, monkeypatch):
    fake(monkeypatch, [Understanding(lang="vi", query_en="tea")], ["[R3]"])
    sid = dict(events(client.post("/chat", json={"message": "gợi ý", "patient_id": PID})))["constraints"]["session_id"]
    assert client.patch(f"/chat/{sid}/constraints/allergen:wheat", json={}).status_code == 409
    r = client.patch(f"/chat/{sid}/constraints/record:allergy/735029006", json={"confirm": True, "reason": "bác sĩ"})
    assert r.status_code == 200 and r.json()["kind"] == "record" and len(r.json()["members"]) == 21
    view = client.get(f"/sessions/{sid}").json()
    assert [g["group_id"] for g in view["groups"]] == ["record:allergy/412071004"]
    assert view["lifted"][0]["reason"] == "bác sĩ" and view["warnings"]
    assert not any(c["value"] == "crustacean_shellfish" for c in view["constraints"])


def test_patch_preset_recipe_detail_and_feedback(client, monkeypatch, bot):
    fake(monkeypatch, [Understanding(query_en="tea")], ["[R3]"])
    evs = dict(events(client.post("/chat", json={"message": "tea"})))
    sid, mid = evs["constraints"]["session_id"], evs["done"]["message_id"]
    assert client.patch(f"/sessions/{sid}", json={"preset": "S-Rerank"}).json()["preset"] == "S-Rerank"
    assert client.patch(f"/sessions/{sid}", json={"preset": "nope"}).status_code == 422
    recipe = client.get("/recipes/3").json()
    assert recipe["id"] == 3 and recipe["directions"] and "ingredients_norm" not in recipe
    assert client.get("/recipes/999999").status_code == 404
    assert client.post("/feedback", json={"message_id": mid, "rating": 1}).status_code == 201
    assert client.post("/feedback", json={"message_id": mid, "rating": 5}).status_code == 422
    assert client.post("/feedback", json={"message_id": evs["constraints"]["message_id"], "rating": -1}).status_code == 404
    assert bot.conn.execute("SELECT rating FROM feedback").fetchall() == [(1,)]
