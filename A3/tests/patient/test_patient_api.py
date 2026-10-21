"""MV5: the patient endpoints on the throwaway test DB (tests/conftest.py; skipped without the container)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import patient_ingest as pi
from api.main import app, get_conn

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"
PID = "887e4b4e-a3e1-b573-4a16-38386d3e0b88"
NAMES = ["Barton704", "Upton904"]


@pytest.fixture
def client(db, tmp_path):
    db.execute("TRUNCATE patient CASCADE")
    folder = tmp_path / "sample"
    folder.mkdir()
    (folder / FIXTURE.name).write_bytes(FIXTURE.read_bytes())
    pi.cmd_load(db, [(folder, "sample")])

    def conn():
        yield db
    app.dependency_overrides[get_conn] = conn
    yield TestClient(app)  # no `with`: skips startup, so no reranker or embedding service
    app.dependency_overrides.clear()


def test_list_shows_the_patient_and_a_summary_of_its_constraints(client):
    rows = client.get("/patients").json()
    assert [r["patient_id"] for r in rows] == [PID]
    assert rows[0]["name"] == "Barton Upton"  # from the file name; the raw Synthea tokens stay out
    s = rows[0]["summary"]
    assert {"wheat", "crustacean_shellfish"} <= set(s["allergens"]) and "sodium_mg" in s["nutrient_limits"]


def test_the_tree_shows_prompt_views_only(client):
    nodes = client.get(f"/patients/{PID}/tree").json()
    allergies = next(n for n in nodes if n["node_id"] == "allergies")
    shown = {f["substance"] for f in allergies["facts"]}
    assert any("Wheat" in s for s in shown) and not any("Latex" in s for s in shown)  # food allergies only
    assert all(set(n) == {"node_id", "parent_id", "kind", "title", "summary", "facts"} for n in nodes)  # no entry ids
    assert all("code" not in f and "entry_id" not in f for n in nodes for f in n["facts"])


def test_the_profile_carries_evidence_without_entry_ids(client):
    p = client.get(f"/patients/{PID}/profile").json()
    assert "wheat" in p["allergens_exclude"] and p["ruleset_version"]
    ev = p["evidence"]["allergen:wheat"]
    assert ev and all(set(e) == {"node_id", "text"} for e in ev) and ev[0]["node_id"] == "allergies"


def test_unknown_is_404_and_deceased_is_409(client, db):
    assert client.get("/patients/nobody/tree").status_code == 404
    db.execute("UPDATE patient SET deceased = true WHERE patient_id = %s", [PID])
    assert client.get(f"/patients/{PID}/profile").status_code == 409
    assert client.get("/patients").json() == []
    assert client.get("/patients?alive_only=false").json()[0]["deceased"] is True


def test_no_name_in_any_patient_endpoint(client):
    listed = json.dumps(client.get("/patients").json())
    assert "Barton Upton" in listed  # the picker name only
    record = json.dumps([client.get(u).json() for u in
                         ("/patients", f"/patients/{PID}/tree", f"/patients/{PID}/profile")])
    for name in NAMES:  # the file's raw tokens never leave the API, including the list
        assert name not in record
    tree = json.dumps([client.get(u).json() for u in (f"/patients/{PID}/tree", f"/patients/{PID}/profile")])
    assert "Barton" not in tree and "Upton" not in tree


def test_the_profile_lists_one_group_per_allergy_entry(client):
    groups = {g["group_id"]: g for g in client.get(f"/patients/{PID}/profile").json()["groups"]}
    assert set(groups) == {"record:allergy/735029006", "record:allergy/412071004"}
    assert len(groups["record:allergy/735029006"]["members"]) == 21 and groups["record:allergy/412071004"]["text"]
