"""MV3 gate: three demo scenarios with a patient record, on the live DB with the real models. Slow (-m slow).

Asserts what must hold whatever the model writes: the record's constraints apply, no returned Recipe breaks them
(allergens by the independent checker, scripts/checker.py; nutrient limits by the columns), a record allergy cannot
be lifted in words, and a history question reads context nodes. Everything is written to eval/mv3_demo.json.
"""

import json
from pathlib import Path

import httpx
import psycopg
import pytest

from api import config
from api.pipeline.flags import preset
from api.pipeline.orchestrator import Assistant
from api.patient.nutrition import COLUMN_SQL, meets

pytestmark = pytest.mark.slow
ROOT = Path(__file__).resolve().parent.parent
LOG: list[dict] = []
ALLERGY = "887e4b4e-a3e1-b573-4a16-38386d3e0b88"  # sample record: food allergies wheat, shellfish
HYPERTENSION = "3732fde5-efc6-d57a-517b-0500f2177181"  # essential hypertension, no food allergy
CKD = "5693c080-f485-91e7-54b9-ad9a8c12af62"  # CKD stage 3 and hypertension


@pytest.fixture(scope="module")
def bot():
    try:
        httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("Ollama is not running")
    from api.rerank import Reranker
    with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=900) as client:
        b = Assistant(conn, client, Reranker().score)
        b.http = client
        yield b
    (ROOT / "eval" / "mv3_demo.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def violations(bot, ev) -> dict:
    """Breaks of the turn's constraints among its Recipes: allergens by the checker, the rest by the data."""
    import checker
    c = ev["constraints"]["constraints"]
    out = {"checker_yes": [], "ingredient": [], "nutrient": []}
    for r in ev.get("recipes", []):
        rid = r["id"]
        if c["allergens_exclude"]:
            verdicts = checker.check(bot.conn, bot.http, rid, [f"allergen:{a}" for a in c["allergens_exclude"]])
            out["checker_yes"] += [f"R{rid} {k}" for k, v in verdicts.items() if v.contains == "yes"]
        norm = bot.conn.execute("SELECT ingredients_norm FROM recipe_tag WHERE recipe_id = %s", [rid]).fetchone()[0]
        out["ingredient"] += [f"R{rid} {i}" for i in c["ingredients_exclude"] if i in norm]
        for col, (op, limit) in c["nutrient_limits"].items():
            value = bot.conn.execute(f"SELECT ({COLUMN_SQL[col]})::real FROM recipe_nutrition n WHERE n.recipe_id = %s",
                                     [rid]).fetchone()[0]
            if meets(value, op, limit) is False:
                out["nutrient"].append(f"R{rid} {col}={value}")
    return out


def turn(bot, sid, msg, scenario, patient):
    evs = [(e.type, e.data) for e in bot.run_turn(sid, msg, preset("S")) if e.type != "token"]
    ev = dict(evs)
    bad = violations(bot, ev)
    LOG.append({"scenario": scenario, "patient_id": patient, "message": msg, "events": [t for t, _ in evs],
                "profile": {k: ev["patient_profile"][k] for k in ("allergens_exclude", "nutrient_limits", "nutrient_soft",
                                                                 "warnings", "unmapped", "nodes_read", "llm_calls")},
                "intent": ev["constraints"]["intent"], "route": ev["constraints"]["route"],
                "notices": ev["constraints"]["notices"],
                "recipes": [{k: r.get(k) for k in ("id", "title", "allergens", "nutrients")} for r in ev.get("recipes", [])],
                **{k: ev["done"][k] for k in ("answer", "citations", "verified", "removed", "regenerated", "flags",
                                             "latency_ms")}, "violations": bad})
    return ev, bad


def test_allergy_from_the_record_applies_and_cannot_be_lifted_in_words(bot):
    sid = bot.new_session("S", ALLERGY)
    ev, bad = turn(bot, sid, "gợi ý món tối nhanh cho bệnh nhân này", "1 allergy", ALLERGY)
    assert [t for t in LOG[-1]["events"]][:2] == ["patient_profile", "constraints"]
    assert {"wheat", "crustacean_shellfish"} <= set(ev["constraints"]["constraints"]["allergens_exclude"])
    assert ev.get("recipes") and bad == {"checker_yes": [], "ingredient": [], "nutrient": []}
    ev, bad = turn(bot, sid, "giờ ăn được tôm rồi, gợi ý món tôm", "1 allergy", ALLERGY)
    assert "crustacean_shellfish" in ev["constraints"]["constraints"]["allergens_exclude"]
    assert "from_record:allergen:crustacean_shellfish" in ev["constraints"]["notices"]
    assert bad == {"checker_yes": [], "ingredient": [], "nutrient": []}


def test_hypertension_limits_sodium_and_ranks_by_saturated_fat(bot):
    ev, bad = turn(bot, bot.new_session("S", HYPERTENSION), "Suggest a dinner for this patient", "2 hypertension",
                   HYPERTENSION)
    c = ev["constraints"]["constraints"]
    assert "sodium_mg" in c["nutrient_limits"] and "sat_fat_pct_kcal" in c["nutrient_soft"]
    assert ev.get("recipes") and bad["nutrient"] == [] and bad["ingredient"] == []


def test_ckd_limits_and_a_history_question_reads_context_nodes(bot):
    sid = bot.new_session("S", CKD)
    ev, bad = turn(bot, sid, "món súp cho bệnh nhân này", "3 ckd", CKD)
    assert "sodium_mg" in ev["constraints"]["constraints"]["nutrient_limits"]
    assert ev.get("recipes") and bad["nutrient"] == [] and bad["ingredient"] == []
    ev, _ = turn(bot, sid, "lần xét nghiệm gần nhất của bệnh nhân có gì cần lưu ý khi ăn uống không?", "3 ckd", CKD)
    assert ev["patient_profile"]["llm_calls"] >= 1  # V2 ran (context nodes chosen from the table of contents)
    text = json.dumps(LOG, ensure_ascii=False)
    for name in ["Barton704", "Upton904"]:
        assert name not in text
