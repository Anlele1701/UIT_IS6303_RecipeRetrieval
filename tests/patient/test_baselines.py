"""MV4c: the text baselines with a fake model and fake embeddings (no Ollama)."""

import numpy as np
import pytest

from api.patient import baselines, rules
from api.pipeline.llm import LLMError

TERM = {"allergy": {"peanut": "762952008", "latex": "111088007"}, "problem": {"essential hypertension": "59621000"},
        "medication": {"lisinopril 10 mg oral tablet": "314076"}}


@pytest.fixture(autouse=True)
def fake_terminology(monkeypatch):
    monkeypatch.setattr(baselines, "terminology", lambda: TERM)


def test_extract_reads_the_schema_and_counts_calls(monkeypatch):
    replies = iter([LLMError("bad"), {"food_allergies": ["Peanut (substance)"], "conditions": [], "medications": []}])

    def fake(client, schema, messages, **kw):
        r = next(replies)
        if isinstance(r, Exception):
            raise r
        assert kw["num_ctx"] == baselines.EXTRACT_CTX and "2026-10-23" in messages[0]["content"]
        return r
    monkeypatch.setattr(baselines, "chat_json", fake)
    items, calls = baselines.extract(None, "Allergies: Peanut (substance)", "2026-10-23")
    assert calls == 2 and items["food_allergies"] == ["Peanut (substance)"]


def test_nothing_read_means_no_call(monkeypatch):
    monkeypatch.setattr(baselines, "chat_json", lambda *a, **k: pytest.fail("called the model on empty text"))
    assert baselines.extract(None, "  ", "2026-10-23") == ({k: [] for k in baselines.SCHEMA["required"]}, 0)


def test_descriptions_map_to_codes_and_unknown_ones_stay_visible():
    ent = baselines.entities({"food_allergies": ["Peanut (substance)"], "conditions": ["Essential hypertension"],
                              "medications": ["Aspirin"]})
    assert ent == {"food_allergy_substances": ["762952008"], "conditions": ["59621000"], "medications": ["?aspirin"]}


def test_profile_from_items_goes_through_the_rule_tables_and_points_at_the_narrative():
    rs = rules.load_rules()
    prof = baselines.profile_from_items({"food_allergies": ["Peanut"], "conditions": ["Essential hypertension"],
                                         "medications": []}, None, rs, "2026-10-23", "p1", "vectorless",
                                        baselines.FIXED_ID)
    assert "peanut" in prof.allergens_exclude
    assert {e.node_id for e in prof.evidence["allergen:peanut"]} == {"narrative.allergies"}
    assert prof.nutrient_limits or prof.nutrient_soft  # hypertension has sodium rows


def test_chunks_carry_their_node_ids_and_top_k_is_deterministic():
    lines = [("allergies", "Allergy: Peanut"), ("meds.active", "Current medication: X")] + \
        [("results.2020", f"Lab panel {i}") for i in range(9)]
    table = baselines.chunk_table(lines, size=4)
    assert [ids for _, ids in table] == [["allergies", "meds.active", "results.2020"], ["results.2020"], ["results.2020"]]

    def embed(texts):  # the query is closest to the second chunk, then the first
        if texts[0].startswith("search_query"):
            return np.array([[0.0, 1.0]])
        return np.array([[0.6, 0.8], [0.0, 1.0], [1.0, 0.0]])
    assert baselines.top_chunks(None, [t for t, _ in table], "q", k=2, embed=embed) == [1, 0]


def test_weight_from_either_text_form():
    assert baselines.weight_from_text("Vital Signs: 2024-01-01 -> no end date: Body Weight (80 kg)\n"
                                      "Vital Signs: 2025-08-19 -> no end date: Body Weight (83.6 kg)")["value"] == "83.6"
    assert baselines.weight_from_text("Vital sign: Body Weight 70 kg (2025-01-01)")["date"] == "2025-01-01"
    assert baselines.weight_from_text("Allergy: Peanut") is None


def test_a_copied_narrative_row_maps_like_its_description():
    ent = baselines.entities({"food_allergies": [], "conditions": ["1993-03-05 -> no end date: Essential hypertension (disorder)"],
                              "medications": ["2016-07-15 -> 2017-07-21: lisinopril 10 MG Oral Tablet"]})
    assert ent["conditions"] == ["59621000"] and ent["medications"] == ["314076"]


def test_embeddings_go_in_small_batches_and_keep_their_order():
    import httpx
    sizes = []

    def handler(request):
        import json
        texts = json.loads(request.content)["input"]
        sizes.append(len(texts))
        return httpx.Response(200, json={"embeddings": [[float(t.split()[-1]), 1.0] for t in texts]})
    v = baselines._embed(httpx.Client(transport=httpx.MockTransport(handler)), [f"doc {i}" for i in range(70)])
    assert sizes == [32, 32, 6] and v.shape == (70, 2) and v[69, 0] > v[1, 0]
