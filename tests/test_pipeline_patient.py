"""MV3: the pipeline with a patient record, on the test DB with fake models (no Ollama).

Recipes (conftest): 1 Garlic Shrimp (crustacean), 2 Toast (wheat), 3 Tea. The patient is the sample record:
food allergies wheat and shellfish, so only Tea may come back.
"""

import json
from pathlib import Path

import numpy as np
import pytest

import ingest
import patient_ingest
import tag
from api.patient.models import PatientNode
from api.pipeline import m4_retrieve as m4
from api.pipeline import m7_verify as m7
from api.pipeline import orchestrator as orch
from api.pipeline.flags import PRESETS, S, preset
from api.pipeline.lexicon import RuntimeLexicon
from api.pipeline.m5_postprocess import top_recipes
from api.pipeline.schemas import Constraints, RecipeCard, Removal, Understanding
from api.retrieval import Candidate

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


def fake_models(monkeypatch, understood, answers, prompts=None):
    def understand(client, lex, message, history, current, patient=False):
        assert patient, "a patient session must use the patient schema"
        return understood.pop(0)

    def generate(client, messages, usage=None):
        if prompts is not None:
            prompts.append(messages)
        return iter([answers.pop(0)])
    monkeypatch.setattr(orch, "understand", understand)
    monkeypatch.setattr(orch.m6, "generate", generate)


def events(bot, sid, msg, name="S"):
    return [(e.type, e.data) for e in bot.run_turn(sid, msg, preset(name))]


def test_a_patient_turn_sends_the_profile_first_and_filters_by_the_record(bot, monkeypatch):
    fake_models(monkeypatch, [Understanding(lang="vi", query_en="tea toast shrimp")], ["Thử [R3] [H:allergies]."])
    sid = bot.new_session("S", PID)
    evs = events(bot, sid, "gợi ý món")
    types = [t for t, _ in evs]
    assert types[:2] == ["patient_profile", "constraints"]
    prof = dict(evs)["patient_profile"]
    assert prof["allergens_exclude"] == ["crustacean_shellfish", "wheat"] and prof["llm_calls"] == 0
    c = dict(evs)["constraints"]["constraints"]
    assert set(c["allergens_exclude"]) == {"crustacean_shellfish", "wheat"} and "sodium_mg" in c["nutrient_limits"]
    assert [r["id"] for r in dict(evs)["recipes"]] == [3]  # sodium unknown in the test DB: kept (unknown_strict off)
    done = dict(evs)["done"]
    assert done["verified"] and done["flags"] == [] and done["citations"] == [3]
    stages = [s for (s,) in bot.conn.execute("SELECT stage FROM retrieval_trace WHERE message_id = %s ORDER BY id",
                                             [done["message_id"]])]
    assert stages == ["v1", "v3", "m1", "v2", "m2", "m3", "m4", "m5", "m6", "m7"]
    rows = bot.conn.execute("SELECT scope, source FROM session_constraint WHERE session_id = %s AND type = 'allergen'",
                            [sid]).fetchall()
    assert set(rows) == {("patient", "patient")}


def test_lifting_a_record_allergy_in_words_keeps_it(bot, monkeypatch):
    lift = Understanding(lang="vi", intent="refine", query_en="shrimp", remove=Removal(allergens=["crustacean_shellfish"]))
    prompts = []
    fake_models(monkeypatch, [lift], ["Món tôm chưa dùng được."], prompts)
    evs = dict(events(bot, bot.new_session("S", PID), "tôi ăn được tôm rồi"))
    assert "crustacean_shellfish" in evs["constraints"]["constraints"]["allergens_exclude"]
    assert "from_record:allergen:crustacean_shellfish" in evs["constraints"]["notices"]
    assert evs["constraints"]["record_locked"][0]["constraint"] == "allergen:crustacean_shellfish"
    assert "cần xác nhận trên giao diện" in evs["constraints"]["record_locked"][0]["message"]
    assert "stays until confirmed in the interface" in prompts[0][0]["content"]
    m2 = bot.conn.execute("SELECT payload FROM retrieval_trace WHERE stage = 'm2' AND message_id = %s",
                          [evs["done"]["message_id"]]).fetchone()[0]
    assert m2["refused_removals"] == ["allergen:crustacean_shellfish"]


def test_m7_flags_a_suggested_allergen_and_a_made_up_record_node(bot, monkeypatch):
    fake_models(monkeypatch, [Understanding(query_en="tea")], ["Add shrimp to [R3] [H:labs.1999].", "Try [R3]."])
    done = dict(events(bot, bot.new_session("S", PID), "tea"))["done"]
    assert done["regenerated"] and done["answer"] == "Try [R3]."


def test_patient_info_route_answers_from_the_record_without_recipes(bot, monkeypatch):
    prompts = []
    u = Understanding(lang="vi", intent="patient_info", query_en="")
    fake_models(monkeypatch, [u], ["Dị ứng lúa mì và giáp xác [H:allergies]."], prompts)
    from api.patient import navigate
    monkeypatch.setattr(navigate, "chat_json", lambda client, schema, messages, **kw: {"node_ids": ["results.2021"]})
    evs = dict(events(bot, bot.new_session("S", PID), "bệnh nhân dị ứng gì?"))
    assert evs["constraints"]["route"] == "patient_info" and "recipes" not in evs
    assert evs["patient_profile"]["nodes_read"][-1] == "results.2021" and evs["patient_profile"]["llm_calls"] == 1
    assert evs["done"]["verified"]
    record = prompts[0][0]["content"]
    assert "Wheat (substance)" in record and "Latex" not in record  # food allergies only (allow-list)


def test_no_name_in_events_traces_or_prompts(bot, monkeypatch):
    prompts = []
    fake_models(monkeypatch, [Understanding(query_en="tea")], ["[R3]"], prompts)
    evs = events(bot, bot.new_session("S", PID), "tea")
    traces = bot.conn.execute("SELECT payload::text FROM retrieval_trace").fetchall()
    text = json.dumps(evs, default=str) + json.dumps(prompts) + json.dumps(traces)
    for name in NAMES:
        assert name not in text


def test_a_deceased_or_unknown_patient_gets_no_session(bot):
    bot.conn.execute("UPDATE patient SET deceased = true WHERE patient_id = %s", [PID])
    with pytest.raises(orch.PatientUnavailable, match="deceased"):
        bot.new_session("S", PID)
    with pytest.raises(orch.PatientUnavailable, match="unknown"):
        bot.new_session("S", "no-such-patient")


def test_s_profile_ignores_the_record(bot, monkeypatch):
    def understand(client, lex, message, history, current):  # the M3 call: no patient argument at all
        return Understanding(query_en="tea toast shrimp")
    monkeypatch.setattr(orch, "understand", understand)
    monkeypatch.setattr(orch.m6, "generate", lambda client, messages, usage=None: iter(["ok"]))
    evs = events(bot, bot.new_session("S-Profile", PID), "món", "S-Profile")
    assert "patient_profile" not in [t for t, _ in evs]
    assert dict(evs)["constraints"]["constraints"]["allergens_exclude"] == []


def test_patient_presets_differ_from_s_in_profile_flags_only():
    import dataclasses
    for name in ["S-Profile", "P-Direct", "P-Vectorless", "P-Vectorless-Fixed", "P-Vector"]:
        diff = {f.name for f in dataclasses.fields(S) if getattr(S, f.name) != getattr(PRESETS[name], f.name)}
        assert diff <= {"profile", "profile_mode"}, (name, diff)


# ---- M4, M5, M7 pieces -------------------------------------------------------------------------------------

def test_m4_nutrient_limits_run_inside_the_index_and_keep_unknowns(recipes, fake_embed):
    tag.write_tables(recipes, tag.tag_all(recipes)[1])
    recipes.execute("UPDATE recipe_nutrition SET sodium_mg = 900 WHERE recipe_id = 1")
    recipes.execute("UPDATE recipe_nutrition SET sodium_mg = 100 WHERE recipe_id = 2")
    ingest.run(recipes, ["chunk", "sentence"])
    lim = Constraints(nutrient_limits={"sodium_mg": ("max", 666.67)})
    kept = {c.recipe_id for c in m4.search(recipes, "garlic shrimp toast tea", QVEC, lim, filter_on=True, norm=True,
                                           strategy="sentence")}
    strict = {c.recipe_id for c in m4.search(recipes, "garlic shrimp toast tea", QVEC, lim, filter_on=True, norm=True,
                                             unknown_strict=True, strategy="sentence")}
    assert kept == {2, 3} and strict == {2}  # 1 breaks the limit; 3 has no sodium value


def test_m5_soft_limits_reorder_but_never_drop():
    chunks = [Candidate(i, rid, "step", 1, "x", 1.0 - i / 10) for i, rid in enumerate([10, 20, 30])]
    values = {10: {"sat_fat_pct_kcal": 9.0}, 20: {"sat_fat_pct_kcal": 3.0}, 30: {"sat_fat_pct_kcal": None}}
    ranked = top_recipes("q", chunks, None, k=3, use_rerank=False, soft={"sat_fat_pct_kcal": ("max", 6.0)}, values=values)
    assert [r for r, _ in ranked] == [20, 10, 30]  # the one that meets the soft limit first, the rest keep their order


def test_m7_nutrient_break_and_negated_mentions():
    card = RecipeCard(id=7, title="Soup", nutrients={"sodium_mg": 900.0})
    c = Constraints(nutrient_limits={"sodium_mg": ("max", 666.67)})
    assert m7.violations(card, c) == ["nutrient:sodium_mg"]
    check = m7.PatientCheck(node_ids={"allergies"}, avoid_terms={"allergen:crustacean_shellfish": ["shrimp", "tôm"]})
    ok = m7.verify("Món này không có tôm, shrimp-free [H:allergies].", [], Constraints(), check)
    bad = m7.verify("Thêm tôm vào cho ngon.", [], Constraints(), check)
    assert ok.verified and not ok.flags
    assert not bad.verified and bad.flags == ["text:allergen:crustacean_shellfish"]


# ---- route patient_info: values only, every number from the facts read (Thy, after MV3) ------------------------

PE02 = "Were the patient's last blood tests normal for kidney function?"


def test_m7_numbers_must_come_from_the_record():
    allowed = m7.numbers_in([{"value": "67.68", "unit": "mg/dL", "date": "2026-08-16"}])
    assert m7.unknown_numbers("Glucose 67.68 mg/dL on 2026-08-16 [H:results.2026] [R12].", allowed) == []
    assert m7.unknown_numbers("Glucose about 67.7 mg/dL.", allowed) == []  # the precision the answer writes
    assert m7.unknown_numbers("1. Glucose 67.68\n2. eGFR 95 mL/min", allowed) == ["95"]  # list marks are not values
    assert m7.unknown_numbers("Glucose 70 mg/dL", allowed) == ["70"]


def test_pe02_a_made_up_value_is_regenerated_and_the_prompt_forbids_interpreting(bot, monkeypatch):
    from api.patient import navigate
    monkeypatch.setattr(navigate, "chat_json", lambda client, schema, messages, **kw: {"node_ids": ["results.2021"]})
    facts = bot.conn.execute("SELECT facts FROM patient_node WHERE patient_id = %s AND node_id = 'results.2021'",
                             [PID]).fetchone()[0]
    obs = facts[0]["observations"][0]
    honest = (f"Interpreting results needs a doctor. The record has {obs['display']} {obs['value']} {obs['unit']} "
              f"on {obs['date']} [H:results.2021].")
    prompts = []
    fake_models(monkeypatch, [Understanding(lang="en", intent="patient_info", needs_record_context=True)],
                ["Kidney function looks normal: eGFR 95 mL/min [H:results.2021].", honest], prompts)
    done = dict(events(bot, bot.new_session("S", PID), PE02))["done"]
    assert done["regenerated"] and done["verified"] and done["answer"] == honest
    system = prompts[0][0]["content"]
    assert "interpreting results needs a doctor" in system and "no trend" in system
    assert "Delete these numbers, which are not in RECORD: 95" in prompts[1][-1]["content"]
    assert "interpreting them needs a doctor" in prompts[1][-1]["content"]  # "looks normal" was flagged too


def test_m7_flags_a_copied_profile_block_and_numbers_only_from_the_record_facts():
    check = m7.PatientCheck(node_ids={"results.2026"}, numbers=m7.numbers_in([{"value": "140.1", "unit": "mmol/L"}]))
    echo = m7.verify("PATIENT_PROFILE:\n<patient_profile>\n- limit: sodium\n</patient_profile>", [], Constraints(), check)
    assert "echo:prompt_block" in echo.flags and not echo.verified
    made_up_range = m7.verify("Sodium 140.1 mmol/L (normal 135-145) [H:results.2026].", [], Constraints(), check)
    assert set(made_up_range.flags) == {"number:135", "number:145", "interpret:normal"}


# ---- after MV3, round 2 (Thy): interpretation words, title masking, values_answer fallback ----------------------

def test_m7_interpretation_only_in_sentences_with_a_number_and_condition_names_masked():
    names = ["Essential hypertension (disorder)", "Essential hypertension"]
    assert m7.interpretations("Bệnh nhân bị tăng huyết áp. Natri 140.1 mmol/L ngày 2026-08-16.", names) == []
    assert m7.interpretations("Essential hypertension; sodium 140.1 mmol/L on 2026-08-16.", names) == []
    assert m7.interpretations("Sodium 140.1 mmol/L is normal.", names) == ["normal"]
    assert m7.interpretations("Glucose 67.68 mg/dL, hơi thấp.", names) == ["thấp"]
    assert m7.interpretations("Không có gì bất thường, cần bác sĩ diễn giải.", names) == []  # no number in it


def test_m7_masks_cited_titles_but_not_the_rest_of_the_text():
    card = RecipeCard(id=31477, title="Creamy Mustard Dipping Sauce for Shellfish")
    check = m7.PatientCheck(node_ids=set(), avoid_terms={"allergen:crustacean_shellfish": ["shellfish", "shrimp", "tôm"]})
    ok = m7.verify("[R31477] Creamy Mustard Dipping Sauce for Shellfish is ready in 35 minutes.", [card],
                   Constraints(), check)
    bad = m7.verify("[R31477] Creamy Mustard Dipping Sauce for Shellfish: serve it with shrimp.", [card],
                    Constraints(), check)
    assert ok.verified and bad.flags == ["text:allergen:crustacean_shellfish"]


def test_values_answer_lists_the_record_values_with_their_nodes():
    views = [{"node_id": "results.2025", "facts": [{"display": "BMP", "date": "2025-02-01", "observations": [
                 {"display": "Sodium", "value": "140.1", "unit": "mmol/L", "date": "2025-02-01"}]}]},
             {"node_id": "results.2026", "facts": [{"display": "BMP", "date": "2026-08-16", "observations": [
                 {"display": "Sodium", "value": "139", "unit": "mmol/L", "date": "2026-08-16"}]}]}]
    text = m7.values_answer(views, "vi")
    assert text.splitlines()[0] == "Việc diễn giải kết quả cần bác sĩ. Hồ sơ ghi:"
    assert text.splitlines()[1] == "- Sodium: 139 mmol/L (2026-08-16) [H:results.2026]"  # newest first
    allowed = m7.numbers_in([v["facts"] for v in views])
    assert m7.unknown_numbers(text, allowed) == [] and m7.interpretations(text, []) == []


def test_a_patient_info_answer_still_interpreting_after_regeneration_is_replaced_and_traced(bot, monkeypatch):
    from api.patient import navigate
    monkeypatch.setattr(navigate, "chat_json", lambda client, schema, messages, **kw: {"node_ids": ["results.2021"]})
    facts = bot.conn.execute("SELECT facts FROM patient_node WHERE patient_id = %s AND node_id = 'results.2021'",
                             [PID]).fetchone()[0]
    obs = facts[0]["observations"][0]
    judging = f"{obs['display']} {obs['value']} {obs['unit']} is normal [H:results.2021]."
    fake_models(monkeypatch, [Understanding(lang="en", intent="patient_info", needs_record_context=True)],
                [judging, judging])
    done = dict(events(bot, bot.new_session("S", PID), PE02))["done"]
    assert done["fallback"] and done["verified"] and done["regenerated"]
    assert done["answer"].startswith("Interpreting these results needs a doctor.") and "[H:results.2021]" in done["answer"]
    row = bot.conn.execute("SELECT payload FROM retrieval_trace WHERE stage = 'fallback' AND message_id = %s",
                           [done["message_id"]]).fetchone()[0]
    assert row["kind"] == "values_answer" and "interpret:normal" in row["model_flags"]
