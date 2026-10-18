"""MV4c: eval_patient.py metrics on hand-built data (no DB, no model)."""

import pytest

import eval_patient as ep


def test_prf_and_node_hit():
    assert ep.prf(["a", "b"], ["b", "c"]) == {"tp": 1, "fp": 1, "fn": 1}
    assert ep.node_hit(["allergies", "results.2026"], ["results.2026"], "coded")
    assert not ep.node_hit(["allergies"], ["results.2026"], "coded")
    assert ep.node_hit(["narrative.results"], ["results.2026"], "narrative")
    assert not ep.node_hit(["narrative.encounters"], ["results.2026"], "narrative")


def test_h_citations_count_tree_and_read_nodes():
    h = ep.h_citations("Tránh đậu phộng [H:allergies] [H:made.up] [H:results.2020]",
                       {"allergies", "results.2020"}, {"allergies"})
    assert h == {"h_cites": 3, "h_valid": 2, "h_read": 1}


def test_nutrition_violation_known_values_only():
    limits = {"sodium_mg": ("max", 600.0), "fiber_per_1000kcal": ("min", 10.0)}
    values = {1: {"sodium_mg": 700, "fiber_per_1000kcal": 20}, 2: {"sodium_mg": 100, "fiber_per_1000kcal": None},
              3: {"sodium_mg": 100, "fiber_per_1000kcal": 12}}
    assert ep.nutrition_viol([1, 2, 3], limits, values) == {"viol": 1, "unknown": 1}


def test_holm():
    assert ep.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_questions_of_a_patient_are_averaged_first():
    rows = [{"patient_id": "a", "m": 1}, {"patient_id": "a", "m": 0}, {"patient_id": "b", "m": 1},
            {"patient_id": "c", "m": None}]
    assert ep.per_patient(rows, "m") == {"a": 0.5, "b": 1.0}


def test_compare_is_paired_by_patient():
    a = {f"p{i}": 1.0 for i in range(10)}
    b = {f"p{i}": 0.0 for i in range(10)} | {"extra": 1.0}
    c = ep.compare(a, b)
    assert c["patients"] == 10 and c["diff"] == 1.0 and c["p_wilcoxon"] < 0.05
    assert ep.compare(a, dict(a))["p_wilcoxon"] == 1.0


def test_a_limited_run_meets_every_stratum_and_is_seeded():
    qs = [{"qid": f"q{i:03d}", "primary": s} for i, s in enumerate(["none"] * 50 + ["multi"] * 5 + ["food_allergy"] * 5)]
    a = ep.pick(qs, 6)
    assert len(a) == 6 and {q["primary"] for q in a} == {"none", "multi", "food_allergy"}
    assert a == ep.pick(list(reversed(qs)), 6) or [q["qid"] for q in a] == sorted(q["qid"] for q in a)
    assert ep.pick(qs, None) == qs


def test_a_changed_frozen_set_stops_the_run(monkeypatch):
    import freeze_patient_set as fz
    monkeypatch.setattr(fz, "digests", lambda: {"queries.jsonl": "x", "gold.jsonl": "y"})
    with pytest.raises(SystemExit):
        ep.check_frozen()


def test_named_ingredients_match_whole_words_only():
    lines = ["2 cups chicken broth", "3 large leeks, sliced", "1 cup chopped onions"]
    assert ep.names_in(lines, ["clam juice", "leek", "onion", "garlic"]) == ["leek", "onion"]
    assert ep.names_in(["1 tbsp scallion"], ["scallop"]) == []


def test_s_profile_runs_once_and_stands_for_both_inputs():
    t = [{"qid": "q1", "preset": "S-Profile", "input": "coded"}, {"qid": "q1", "preset": "S-Profile", "input": "narrative", "old": 1},
         {"qid": "q1", "preset": "P-Vector", "input": "narrative"}]
    out = ep.shared_turns(t)
    narr = [x for x in out if x["preset"] == "S-Profile" and x["input"] == "narrative"]
    assert len(out) == 3 and narr == [{"qid": "q1", "preset": "S-Profile", "input": "narrative", "shared_from": "coded"}]
    only_narrative = [{"qid": "q1", "preset": "S-Profile", "input": "narrative"}]
    assert ep.shared_turns(only_narrative) == only_narrative


def test_a_food_that_only_shares_the_name_is_not_a_violation():
    assert ep.names_in(["4 ounces chopped fresh oyster mushrooms"], ["oyster"]) == []
    assert ep.names_in(["1 dozen fresh oysters", "1 cup oyster crackers"], ["oyster"]) == ["oyster"]
