"""Per-serving limits (spec 4.4) and the condition_nutrient.csv loader."""

import pytest

from api.patient import nutrition, rules
from api.patient.rules import NutrientRule


def rule(nutrient, value, op="max", mode="filter"):
    return NutrientRule(("*",), "t", nutrient, op, value, "", mode, "")


def test_absolute_limits_are_a_third_of_the_daily_one():
    assert nutrition.per_serving_limit(rule("sodium_mg", 2000), fraction=1 / 3) == pytest.approx(666.67, abs=0.01)


def test_shares_of_energy_are_not_scaled():
    assert nutrition.per_serving_limit(rule("sat_fat_pct_kcal", 6)) == 6
    assert nutrition.per_serving_limit(rule("fiber_per_1000kcal", 14, op="min")) == 14


def test_per_kg_needs_a_weight():
    r = rule("protein_g_per_kg", 0.8)
    assert nutrition.per_serving_limit(r) is None
    assert nutrition.per_serving_limit(r, 70, fraction=1 / 3) == pytest.approx(18.67, abs=0.01)


def test_warn_only_rule_has_no_limit():
    assert nutrition.per_serving_limit(rule("potassium_mg", None, op=None, mode="warn")) is None


def test_ratios_are_null_without_calories():
    for name in nutrition.RATIO:
        assert "nullif(n.calories, 0)" in nutrition.SQL[name]


def test_loader_reads_the_draft_and_refuses_unknown_nutrients(tmp_path):
    loaded = rules.load_condition_nutrient()
    assert {r.nutrient for r in loaded if r.mode != "unmapped"} <= rules.NUTRIENTS
    assert any(r.mode == "unmapped" and "80394007" in r.conditions for r in loaded)  # hyperglycemia: no rule yet
    assert any(r.conditions == ("*",) and r.nutrient == "sodium_mg" for r in loaded)
    (tmp_path / "condition_nutrient.csv").write_text(
        "condition_codes,label,nutrient,op,daily_value,unit,mode,source\n*,x,vitamin_z,max,1,mg,filter,s\n",
        encoding="utf-8")
    with pytest.raises(rules.RuleError, match="unknown nutrient"):
        rules.load_condition_nutrient(tmp_path)


def test_every_hard_nutrient_rule_leaves_at_least_half_of_the_recipes():
    """ADR-0007: a rule leaving under 50% of Recipes is soft. Reads the measured pass rates."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "eval" / "patient_corpus.json"
    if not path.exists():
        pytest.skip("patient_corpus.json not built")
    measured = json.loads(path.read_text(encoding="utf-8"))["nutrient_rule_pass"]["per_rule"]
    for r in measured:
        if r["mode"] == "filter" and r.get("pass_rate_known") is not None:
            assert r["pass_rate_known"] >= 0.5, r
    assert any(r["mode"] == "soft" and r["pass_rate_known"] < 0.5 for r in measured)
