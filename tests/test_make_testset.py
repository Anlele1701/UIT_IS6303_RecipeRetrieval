"""M5: test set generation and the V1-V5 filters (no DB, no model)."""

import random
from types import SimpleNamespace

import make_testset as mt


def test_templates_are_seeded_balanced_and_carry_their_gold():
    a, b = mt.t2_items(random.Random(42), 28), mt.t2_items(random.Random(42), 28)
    assert a == b and {it["lang"] for it in a} == {"vi", "en"} and {it["kind"] for it in a} == set(mt.T2_TEMPLATES)
    combo = next(it for it in a if it["kind"] == "allergen+time")
    c = combo["gold"]["constraints"]
    assert c["allergens_exclude"] and c["max_total_minutes"] and str(c["max_total_minutes"]) in combo["template"]


def test_t4_gold_follows_the_dialogue_state():
    d = next(it for it in mt.t4_items(random.Random(1), 10) if it["kind"] == "script4")  # allergy, then lifted
    first, second = d["turns"]
    assert first["gold"]["constraints"]["allergens_exclude"] and second["gold"]["constraints"]["allergens_exclude"] == []
    detail = next(it for it in mt.t4_items(random.Random(1), 10) if it["kind"] == "script1")["turns"][-1]["gold"]
    assert detail["intent"] == "ask_detail" and detail["ref_recipe"] == 2 and detail["constraints"]["ingredients_exclude"]


def test_t3_has_conflicts_and_out_of_scope_in_both_languages():
    items = mt.t3_items()
    assert {(it["kind"], it["lang"]) for it in items} == {("conflict", "vi"), ("conflict", "en"),
                                                         ("out_of_scope", "vi"), ("out_of_scope", "en")}
    assert all(it["gold"]["intent"] == "out_of_scope" for it in items if it["kind"] == "out_of_scope")


def test_v1_v3_v4_v5():
    titles = ["chicken stir fry with thai peanut sauce"]
    assert mt.v1_copies_title("my Chicken Stir-Fry with Thai Peanut Sauce, no nuts", titles)
    assert not mt.v1_copies_title("chicken stir fry without peanuts", titles)
    assert mt.lang_ok("gợi ý món gà", "vi") and not mt.lang_ok("goi y mon ga", "vi") and mt.lang_ok("the soup", "en")
    assert mt.lang_ok("suggest the soup for the dinner", "en")  # M1's detector calls this Vietnamese ("the" = thế)
    assert mt.jaccard("suggest a soup without onions", "suggest a soup without onions please") >= 0.8
    items = [{"set": "t2", "lang": "en", "text": t} for t in
             ["suggest a soup without onions", "suggest a soup without onions please", "soup", "gợi ý món súp"]]
    kept, counts = mt.apply_filters(items, titles, None)
    assert [it["text"] for it in kept] == ["suggest a soup without onions"]
    assert counts == {"V4": 1, "V5": 1, "V3": 1}


def test_handwritten_unaccented_vietnamese_is_kept_with_a_warning():
    items = [{"set": "t2", "lang": "vi", "text": "minh di ung tom nau gi cho bua toi"}]
    kept, counts = mt.apply_filters(items, [], None, strict_lang=False)
    assert kept and kept[0]["v3_warning"] and not counts


def test_paraphrase_guard():
    t = "suggest a soup without onions"
    assert mt.keeps("could you suggest a soup without onions?", t, "en", ["soup", "onions"])
    assert not mt.keeps("suggest a vegan soup without onions", t, "en", ["soup", "onions"])  # added a diet
    assert not mt.keeps("gợi ý món súp không có hành tây", t, "en", ["soup"])  # changed language
    assert not mt.keeps("suggest a soup in 20 minutes without onions", t, "en", ["soup", "onions"])  # added a number


def test_v2_asks_the_independent_checker_not_the_tags():
    calls = []

    def check(rid, cons):
        calls.append((rid, tuple(cons)))
        return {c: SimpleNamespace(contains="yes" if rid == 1 else "no") for c in cons}

    class Conn:
        def execute(self, sql, params):
            assert "recipe_tag" in sql  # tags only pick candidates
            return [(1,), (2,), (3,)]
    item = {"gold": {"intent": "search", "constraints": {**mt.empty_constraints(), "allergens_exclude": ["milk"]}},
            "dish_keyword": "soup"}
    res = mt.v2_fits(Conn(), check, item)
    assert res == {"ok": True, "recipe_id": 2, "read": [1, 2]} and calls[0] == (1, ("allergen:milk",))
