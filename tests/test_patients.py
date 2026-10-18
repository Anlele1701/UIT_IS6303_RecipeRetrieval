from datetime import date
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

import load_synthea
from api import config, dietary_rules, patients
from api.main import app
from conftest import SYNTHEA_MINI

P = {n: UUID(int=n) for n in range(1, 8)}  # the mini cohort: 00000000-0000-0000-0000-00000000000N


# --- loader ---------------------------------------------------------------------------------


def test_dead_patients_and_their_rows_are_skipped(ehr):
    ids = {r[0] for r in ehr.execute("SELECT id FROM ehr.patient").fetchall()}
    assert P[6] not in ids and len(ids) == 6
    assert ehr.execute("SELECT count(*) FROM ehr.condition WHERE patient_id = %s", [str(P[6])]).fetchone()[0] == 0
    assert ehr.execute("SELECT count(*) FROM ehr.medication WHERE patient_id = %s", [str(P[6])]).fetchone()[0] == 0


def test_display_names_lose_synthea_digits(ehr):
    assert ehr.execute("SELECT display_name FROM ehr.patient WHERE id = %s", [str(P[1])]).fetchone()[0] == "Ana Brown"


def test_only_whitelisted_observations_are_loaded_with_numeric_values(ehr):
    rows = ehr.execute("SELECT code, value_num, value_text FROM ehr.observation ORDER BY code").fetchall()
    assert [(c, float(n), t) for c, n, t in rows if c == "6298-4"] == [("6298-4", 4.2, None)]
    assert {c for c, _, _ in rows} == {"6298-4", "39156-5"}  # the survey row is gone, the dead patient's too
    assert len(rows) == 2


def test_the_reference_date_is_the_latest_condition_start_and_the_manifest_records_the_load(ehr):
    ref, manifest = ehr.execute("SELECT reference_date, manifest FROM ehr.cohort_run").fetchone()
    assert ref == date(2026, 1, 1)
    assert manifest["synthea_args"] == "-s 0 (hand-written)"
    assert manifest["rows"]["patient"] == 6 and manifest["rows"]["patients_skipped_dead"] == 1
    assert set(manifest["files_sha256"]) == set(load_synthea.FILES)


def test_loading_a_run_twice_is_refused_unless_replaced(ehr):
    with pytest.raises(RuntimeError, match="already loaded"):
        load_synthea.load(ehr, SYNTHEA_MINI, "mini")
    load_synthea.load(ehr, SYNTHEA_MINI, "mini", replace=True)
    assert ehr.execute("SELECT count(*) FROM ehr.patient").fetchone()[0] == 6


def test_a_folder_without_the_csvs_is_refused(ehr, tmp_path):
    with pytest.raises(FileNotFoundError, match="conditions.csv"):
        load_synthea.load(ehr, tmp_path, "empty")


def test_stats_lists_active_conditions(ehr):
    text = load_synthea.stats(ehr)
    assert "run mini: 6 patients" in text and "Essential hypertension" in text


# --- profiles -------------------------------------------------------------------------------


def test_profile_has_age_relative_to_the_reference_date_and_only_active_conditions(ehr):
    p = patients.get_profile(ehr, P[1])
    assert (p.display_name, p.gender, p.age, p.reference_date) == ("Ana Brown", "F", 65, date(2026, 1, 1))
    assert [(c.code, c.since) for c in p.active_conditions] == [
        ("160903007", date(2001, 1, 1)), ("59621000", date(2010, 3, 1))]


def test_profile_lists_only_active_allergies_with_their_category(ehr):
    assert [(a.code, a.category) for a in patients.get_profile(ehr, P[1]).active_allergies] == [
        ("102263004", "food")]  # the peanut allergy stopped in 2000
    assert [(a.code, a.category) for a in patients.get_profile(ehr, P[4]).active_allergies] == [("735029006", "food")]
    assert patients.get_profile(ehr, P[2]).active_allergies == []


def test_a_stopped_condition_is_not_active(ehr):
    assert [c.code for c in patients.get_profile(ehr, P[3]).active_conditions] == ["314529007"]


def test_unknown_patient(ehr):
    with pytest.raises(patients.PatientNotFound):
        patients.get_profile(ehr, UUID(int=999))


def test_list_patients_counts_active_conditions(ehr):
    rows = {r["patient_id"]: r for r in patients.list_patients(ehr)}
    assert len(rows) == 6 and rows[P[2]]["active_conditions"] == 2 and rows[P[4]]["active_conditions"] == 1
    assert len(patients.list_patients(ehr, limit=2)) == 2


def test_list_patients_can_search_by_name_and_sort_by_conditions(ehr):
    ana = patients.list_patients(ehr, q="ana")
    assert ana and all("ana" in r["display_name"].lower() for r in ana)
    assert patients.list_patients(ehr, q="%") == []  # a wildcard is text, not a pattern
    counts = [r["active_conditions"] for r in patients.list_patients(ehr, order="conditions")]
    assert counts == sorted(counts, reverse=True)
    with pytest.raises(ValueError):
        patients.list_patients(ehr, order="id; DROP TABLE x")


# --- the endpoints --------------------------------------------------------------------------


@pytest.fixture
def client(ehr_db_url, ehr):
    """The real app without its lifespan (no reranker): a pool on ehr_test and the shipped rules."""
    app.state.pool = ConnectionPool(ehr_db_url, min_size=1, max_size=2, open=True)
    app.state.rules = dietary_rules.load_rules(config.RULES_PATH)
    yield TestClient(app)
    app.state.pool.close()


def test_diet_plan_endpoint(client):
    r = client.get(f"/patients/{P[2]}/diet-plan")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "filtered" and body["filters"] == {"max_sodium_mg": 500.0}
    assert {e["rule_id"] for e in body["evidence"]} == {"htn-sodium", "chf-sodium"}


def test_diet_plan_reports_what_it_could_not_apply(client):
    body = client.get(f"/patients/{P[7]}/diet-plan").json()
    assert body["filters"] == {"max_carbohydrates_g": 60.0}
    assert [u["nutrient"] for u in body["unapplied_limits"]] == ["saturated_fat_g"]
    assert [u["rule_id"] for u in body["unsupported_conditions"]] == ["ckd-unsupported"]


def test_diet_plan_for_a_patient_with_nothing_to_apply(client):
    assert client.get(f"/patients/{P[4]}/diet-plan").json()["status"] == "no_applicable_rules"


def test_profile_and_list_endpoints(client):
    assert client.get(f"/patients/{P[1]}").json()["display_name"] == "Ana Brown"
    assert len(client.get("/patients?limit=3").json()) == 3


def test_unknown_and_malformed_patient_ids(client):
    assert client.get(f"/patients/{UUID(int=999)}").status_code == 404
    assert client.get(f"/patients/{UUID(int=999)}/diet-plan").status_code == 404
    assert client.get("/patients/not-a-uuid/diet-plan").status_code == 422


# --- active conditions by source -------------------------------------------------------------


def _fake_models(monkeypatch, pick="active_conditions"):
    import json
    import numpy as np

    def chat(http, messages, **kw):
        prompt = messages[-1]["content"]
        if "table of contents" in prompt:
            return json.dumps({"sections": [pick]})
        return json.dumps({"conditions": [{"code": "59621000", "description": "Essential hypertension (disorder)"},
                                          {"code": "11111", "description": "invented"}]})
    monkeypatch.setattr("api.main.llm.chat", chat)
    monkeypatch.setattr("api.main.embed_documents", lambda http, texts: np.ones((len(texts), 2), dtype=np.float32))
    monkeypatch.setattr("api.main.embed_query_array", lambda http, text: np.ones(2, dtype=np.float32))


def test_active_conditions_default_to_sql_and_need_no_document(client):
    body = client.get(f"/patients/{P[1]}/active-conditions").json()
    assert body["source"] == "sql" and {c["code"] for c in body["conditions"]} == {"59621000", "160903007"}
    assert body["missing_vs_sql"] == [] and body["llm_calls"] == 0


def test_tree_and_dense_are_compared_with_sql_and_invented_codes_are_dropped(client, ehr, monkeypatch):
    from api import ehr_document
    ehr.execute("INSERT INTO ehr.record_document VALUES (%s, %s) ON CONFLICT (patient_id) DO UPDATE SET markdown = "
                "EXCLUDED.markdown", [str(P[1]), ehr_document.render_patient(ehr, P[1])])
    _fake_models(monkeypatch)
    app.state.http = object()
    tree = client.get(f"/patients/{P[1]}/active-conditions?source=tree").json()
    assert [c["code"] for c in tree["conditions"]] == ["59621000"] and tree["invented_codes"] == ["11111"]
    assert tree["missing_vs_sql"] == ["160903007"] and tree["extra_vs_sql"] == [] and tree["selected"] == ["active_conditions"]
    dense = client.get(f"/patients/{P[1]}/active-conditions?source=dense").json()
    assert dense["source"] == "dense" and dense["llm_calls"] == 1 and dense["error"] is None


def test_a_patient_without_a_document_cannot_be_read_by_tree(client, ehr):
    ehr.execute("DELETE FROM ehr.record_document WHERE patient_id = %s", [str(P[2])])
    assert client.get(f"/patients/{P[2]}/active-conditions?source=tree").status_code == 409
    assert client.get(f"/patients/{UUID(int=999)}/active-conditions?source=tree").status_code == 404
    assert client.get(f"/patients/{P[2]}/active-conditions?source=oops").status_code == 422
