"""M1: deterministic post-processing (no model) and the golden set (slow: real qwen2.5:7b)."""

import json
from pathlib import Path

import pytest

from api.pipeline import m1_understand as m1
from api.pipeline.lexicon import Alias, RuntimeLexicon
from api.textmatch import key

ROOT = Path(__file__).resolve().parent.parent


def lex() -> RuntimeLexicon:
    lx = RuntimeLexicon()
    for name in ["peanut", "cilantro", "milk", "butter", "avocado", "onion", "green onion", "shallot", "coconut",
                 "garlic", "clam", "squid"]:
        lx.canonical[key(name)] = name
    lx.aliases = {"đậu phộng": Alias("fixed", ("peanut",), ("peanut",)), "ngò": Alias("fixed", ("cilantro",), ()),
                  "sữa": Alias("fixed", ("milk",), ("milk",)), "bơ": Alias("context", ("butter", "avocado"), ()),
                  "hành": Alias("ask", ("onion", "green onion", "shallot"), ()),
                  "hành lá": Alias("fixed", ("green onion",), ()), "tỏi": Alias("fixed", ("garlic",), ()),
                  "hải sản": Alias("all", ("clam", "squid"), ("fish", "crustacean_shellfish"))}
    return lx


def raw(**kw) -> dict:
    base = {"intent": "search", "query_en": "", "allergens_exclude": [], "ingredients_exclude": [],
            "ingredients_include": [], "diet": "none", "max_total_minutes": 0, "lasting": [], "remove_allergens": [],
            "remove_ingredients": [], "remove_diet": False, "remove_time": False, "ref_recipe": 0}
    return {**base, **kw}


def test_unknown_codes_and_ungrounded_allergens_are_dropped():
    u = m1.postprocess(raw(allergens_exclude=["peanut", "gluten", "milk"]), "Tôi dị ứng đậu phộng", lex())
    assert u.constraints.allergens_exclude == ["peanut"]
    assert any("not named" in n for n in u.notes) and any("unknown allergen" in n for n in u.notes)


def test_vietnamese_names_map_to_canonical_and_unknown_ones_are_noted():
    u = m1.postprocess(raw(ingredients_exclude=["ngò", "dragonfruit skin"]), "món gà không ngò", lex())
    assert u.constraints.ingredients_exclude == ["cilantro"] and any("unknown ingredient" in n for n in u.notes)


def test_unaccented_message_still_grounds_the_ingredient():
    u = m1.postprocess(raw(ingredients_exclude=["cilantro"]), "mon ga khong co ngo", lex())
    assert u.constraints.ingredients_exclude == ["cilantro"]


def test_an_alias_for_a_group_brings_codes_and_ingredients():
    u = m1.postprocess(raw(ingredients_exclude=["hải sản"]), "món canh không có hải sản", lex())
    assert u.constraints.allergens_exclude == ["fish", "crustacean_shellfish"]
    assert u.constraints.ingredients_exclude == ["clam", "squid"]


def test_negation_never_reaches_the_query():
    assert m1.strip_negation("chicken soup without onions") == "chicken soup"
    u = m1.postprocess(raw(query_en="cookies with no peanuts"), "no peanuts cookies", lex())
    assert "peanut" not in u.query_en


def test_removal_needs_a_cue_and_wins_in_its_own_turn():
    assert m1.postprocess(raw(remove_allergens=["peanut"]), "món chay", lex()).remove.allergens == []
    u = m1.postprocess(raw(remove_allergens=["peanut"], allergens_exclude=["peanut"]), "giờ ăn được đậu phộng rồi", lex())
    assert u.remove.allergens == ["peanut"] and u.constraints.allergens_exclude == []


def test_rule_adds_what_the_model_skipped():
    u = m1.postprocess(raw(intent="refine"), "thêm điều kiện không sữa", lex())
    assert u.constraints.allergens_exclude == ["milk"]


def test_a_time_limit_needs_a_number_or_time_word():
    assert m1.postprocess(raw(max_total_minutes=60), "quick pasta", lex()).constraints.max_total_minutes is None
    assert m1.postprocess(raw(max_total_minutes=30), "pasta under 30 minutes", lex()).constraints.max_total_minutes == 30


def test_include_and_exclude_conflict_exclude_wins():
    u = m1.postprocess(raw(ingredients_exclude=["garlic"], ingredients_include=["garlic"]), "không tỏi, có tỏi", lex())
    assert u.constraints.ingredients_exclude == ["garlic"] and u.constraints.ingredients_include == []


def test_ask_words_trigger_a_question_unless_the_precise_form_is_used():
    u = m1.postprocess(raw(), "món có hành", lex())
    assert m1.ask_back("món có hành", lex(), u) is not None
    assert m1.ask_back("món có hành lá", lex(), u) is None


def test_language_is_detected_by_rule():
    assert m1.detect_lang("mon ga nuong khong co ngo") == "vi" and m1.detect_lang("roast chicken") == "en"


def test_context_words_are_spelled_out_to_the_model():
    msgs = m1.build_messages("món có bơ", [], m1.Constraints(), lex().hints("món có bơ"))
    assert "butter or avocado" in msgs[1]["content"]


# ---------------------------------------------------------------------------- golden set, real model

CASES = [json.loads(l) for l in (ROOT / "tests" / "golden" / "m1_cases.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.slow
def test_golden_set():
    import httpx
    import psycopg

    from api import config
    from api.pipeline.schemas import Constraints
    try:
        with httpx.Client(timeout=5) as h:
            h.get(f"{config.OLLAMA_URL}/api/version").raise_for_status()
        conn = psycopg.connect(config.DATABASE_URL, connect_timeout=3)
    except Exception:
        pytest.skip("needs Ollama and the A3 database")
    with conn:
        lx = RuntimeLexicon.load(conn)
    results = []
    with httpx.Client(timeout=600) as h:
        for c in CASES:
            u = m1.understand(h, lx, c["message"], [], Constraints())
            got = {"intent": u.intent, "allergens": sorted(u.constraints.allergens_exclude),
                   "excl": sorted(u.constraints.ingredients_exclude), "diet": u.constraints.diet,
                   "minutes": u.constraints.max_total_minutes, "remove_allergens": sorted(u.remove.allergens),
                   "ref": u.ref_recipe}
            ok = {"intent": got["intent"] == c["intent"], "allergens": got["allergens"] == sorted(c["allergens"]),
                  "excl": set(c["excl"]) <= set(got["excl"]), "diet": got["diet"] == c["diet"],
                  "minutes": got["minutes"] == c["minutes"],
                  "remove": got["remove_allergens"] == sorted(c.get("remove_allergens", []))}
            if "ref" in c:
                ok["ref"] = got["ref"] == c["ref"]
            results.append({"id": c["id"], "message": c["message"], "ok": ok, "got": got, "all_ok": all(ok.values())})
    slots = [v for r in results for v in r["ok"].values()]
    report = {"cases": len(results), "all_slots_ok": sum(r["all_ok"] for r in results),
              "slot_accuracy": round(sum(slots) / len(slots), 4),
              "failures": [r for r in results if not r["all_ok"]]}
    (ROOT / "eval" / "m1_golden.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert report["slot_accuracy"] >= 0.9, report["failures"]


def test_thuan_chay_means_vegan_and_a_plain_nut_covers_peanuts():
    assert m1.postprocess(raw(diet="vegetarian"), "món thuần chay", lex()).constraints.diet == "vegan"
    assert m1.postprocess(raw(diet="vegetarian"), "món chay", lex()).constraints.diet == "vegetarian"
    u = m1.postprocess(raw(allergens_exclude=["tree_nuts"]), "nut-free cookies", lex())
    assert u.constraints.allergens_exclude == ["tree_nuts", "peanut"]
    u = m1.postprocess(raw(allergens_exclude=["tree_nuts"]), "no tree nuts please", lex())
    assert u.constraints.allergens_exclude == ["tree_nuts"]
