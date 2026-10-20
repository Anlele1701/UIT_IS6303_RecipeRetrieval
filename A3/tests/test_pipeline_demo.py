"""The four demo scenarios (sườn báo cáo chương 5) on the live DB with the real models. Slow: run with -m slow.

Asserts only what must hold whatever the model writes (filters, state, routes, citations); the answers
themselves are written to eval/m3_demo.json for Thy to read at gate M3.
"""

import json
from pathlib import Path

import httpx
import psycopg
import pytest

from api import config
from api.pipeline import m7_verify as m7
from api.pipeline.flags import preset
from api.pipeline.orchestrator import Assistant

pytestmark = pytest.mark.slow
ROOT = Path(__file__).resolve().parent.parent
LOG: list[dict] = []


@pytest.fixture(scope="module")
def bot():
    try:
        httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("Ollama is not running")
    from api.rerank import Reranker
    with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=900) as client:
        yield Assistant(conn, client, Reranker().score)
    (ROOT / "eval" / "m3_demo.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=2), encoding="utf-8")


def turn(bot, sid, msg, name="S", scenario=""):
    ev = {e.type: e.data for e in bot.run_turn(sid, msg, preset(name)) if e.type != "token"}
    LOG.append({"scenario": scenario, "preset": name, "message": msg, "intent": ev["constraints"]["intent"],
                "route": ev["constraints"]["route"], "constraints": ev["constraints"]["constraints"],
                "recipes": ev.get("recipes", []), **{k: ev["done"][k] for k in
                                                       ("answer", "citations", "verified", "removed", "latency_ms")}})
    return ev


def cards_of(bot, ev):
    from api.pipeline.m5_postprocess import cards
    return cards(bot.conn, [(r["id"], r["score"]) for r in ev["recipes"]])


def test_1_vietnamese_allergy_baseline_leaks_the_system_filters(bot):
    msg = "Tôi dị ứng đậu phộng, gợi ý món gà xào sốt đậu phộng kiểu Thái"
    b0 = turn(bot, bot.new_session("B0"), msg, "B0", "1 allergy")
    s = turn(bot, bot.new_session(), msg, "S", "1 allergy")
    assert "peanut" in s["constraints"]["constraints"]["allergens_exclude"]
    assert not any("peanut" in r["allergens"] for r in s["recipes"]) and s["recipes"]
    assert s["done"]["verified"] and s["done"]["citations"]
    LOG[-1]["b0_peanut_recipes"] = sum("peanut" in r["allergens"] for r in b0["recipes"])


def test_2_three_turns_add_a_constraint_then_ask_about_one_recipe(bot):
    sid = bot.new_session()
    turn(bot, sid, "gợi ý món gà cho bữa tối", scenario="2 three turns")
    t2 = turn(bot, sid, "không dùng sữa nhé", scenario="2 three turns")
    assert t2["constraints"]["intent"] == "refine" and "milk" in t2["constraints"]["constraints"]["allergens_exclude"]
    assert not any("milk" in c.allergens for c in cards_of(bot, t2))
    t3 = turn(bot, sid, "món thứ 2 làm thế nào?", scenario="2 three turns")
    assert t3["constraints"]["route"] == "detail" and t3["recipes"][0]["id"] == t2["recipes"][1]["id"]


def test_3_a_question_without_an_answer_cites_nothing_wrong(bot):
    sid = bot.new_session()
    ev = turn(bot, sid, "công thức bánh chưng thuần chay không gạo nếp, không đậu xanh", scenario="3 no answer")
    assert ev["constraints"]["constraints"]["diet"] == "vegan"
    assert not any(m7.violations(c, bot.state(sid).constraints()) for c in cards_of(bot, ev))
    assert ev["done"]["verified"]
    out = turn(bot, bot.new_session(), "dự báo thời tiết Hà Nội ngày mai", scenario="3 no answer")
    assert out["constraints"]["route"] == "chat" and "recipes" not in out


def test_4_lifting_a_constraint_changes_the_results(bot):
    sid = bot.new_session()
    t1 = turn(bot, sid, "I'm allergic to shellfish, suggest a quick pasta dinner", scenario="4 lift")
    assert "crustacean_shellfish" in t1["constraints"]["constraints"]["allergens_exclude"]
    t2 = turn(bot, sid, "actually I can eat shellfish now, shrimp pasta please", scenario="4 lift")
    assert "crustacean_shellfish" not in t2["constraints"]["constraints"]["allergens_exclude"]
    assert any("crustacean_shellfish" in r["allergens"] for r in t2["recipes"])
