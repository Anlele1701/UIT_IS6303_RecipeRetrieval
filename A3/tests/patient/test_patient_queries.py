"""MV4b: P8 draw, paraphrase guard, answer key (no DB, no model)."""

from pathlib import Path

import make_patient_queries as mq
import patient_sample as psm
from api.patient import ccda, rules
from api.patient.tree import build_tree

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"


def test_draw_takes_every_constrained_patient_then_seeded_none_ones():
    pts = [{"patient_id": f"c{i}", "primary": "ckd"} for i in range(5)]
    pts += [{"patient_id": f"n{i:02d}", "primary": "none"} for i in range(30)]
    a = psm.draw(pts, total=12)
    assert len(a) == 12 and sum(p["primary"] == "ckd" for p in a) == 5
    assert a == psm.draw(list(reversed(pts)), total=12)  # seeded, independent of the input order


def test_primary_stratum_priority():
    assert psm.primary({"hypertension", "ckd", "multi", "diabetes"}) == "multi"
    assert psm.primary({"food_allergy", "hypertension"}) == "hypertension" and psm.primary(set()) == "none"


def test_a_paraphrase_must_keep_numbers_ingredients_patient_and_language():
    assert mq.keeps("Gợi ý món gà nấu dưới 30 phút cho bệnh nhân", "vi", ["30"])
    assert not mq.keeps("Gợi ý món gà nhanh cho bệnh nhân", "vi", ["30"])  # lost the number
    assert not mq.keeps("Suggest a quick chicken dish for the patient", "vi", [])  # wrong language
    assert not mq.keeps("Suggest a mushroom-free soup", "en", ["mushroom"])  # lost the patient
    assert mq.paraphrase(None, "gợi ý món súp cho bệnh nhân này", "vi", []) == ("gợi ý món súp cho bệnh nhân này", False)


def test_answer_key_comes_from_the_coded_entries():
    rs = rules.load_rules()
    nodes = build_tree(ccda.read_record(FIXTURE, "sample", rs.p7)[0])
    g = mq.gold_of("887e4b4e", nodes)
    assert g["food_allergy_substances"] == ["412071004", "735029006"]
    assert len(g["medications"]) == 2 and g["latest_node"]["results"] == "results.2021"
    assert g["latest_node"]["encounters"] == "encounters.2026"


def test_a_frozen_set_has_not_changed():
    import json

    import pytest

    import freeze_patient_set as fz
    frozen = fz.DIR / "frozen.json"
    if not frozen.exists():
        pytest.skip("the patient question set is not frozen yet")
    assert json.loads(frozen.read_text(encoding="utf-8"))["sha256"] == fz.digests()


def test_a_paraphrase_may_not_add_a_constraint_or_a_recipe():
    t = "suggest a soup for this patient"
    assert mq.keeps("Could you suggest a soup for this patient?", "en", [], t)
    assert not mq.keeps("I need a vegetarian soup recipe for this patient.", "en", [], t)  # added a diet
    v = "gợi ý món salad chay cho bệnh nhân này"
    assert not mq.keeps("Gợi ý món salad chay cho bệnh nhân này có thể là salad với 200g bắp cải, 20g hạt điều", "vi", [], v)


def test_a_paraphrase_may_not_bring_in_a_food_the_template_does_not_name(monkeypatch):
    monkeypatch.setattr(mq, "FOOD_WORDS", {"avocado", "vegetable", "cilantro"})
    t = "suggest a salad for this patient"
    assert not mq.keeps("I recommend a mixed greens salad with roasted vegetables and avocado for this patient.", "en", [], t)
    assert mq.keeps("Please suggest a salad for this patient.", "en", [], t)
    t2 = "suggest a soup without cilantro for this patient"
    assert mq.keeps("Could you suggest a cilantro-free soup for this patient?", "en", ["cilantro"], t2)
