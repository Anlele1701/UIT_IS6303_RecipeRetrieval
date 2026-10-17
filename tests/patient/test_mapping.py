"""V3: build_profile (spec section 8, test_mapping). Pure: synthetic trees plus the sample record."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from api.patient import ccda, rules
from api.patient.mapping import build_profile
from api.patient.models import PatientNode
from api.patient.tree import build_tree

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"
TODAY = date(2026, 8, 25)
MOLLUSCS = {"clam", "oyster", "mussel", "scallop", "squid", "octopus", "conch"}


@pytest.fixture(scope="module")
def rs():
    return rules.load_rules()


def tree(allergies=(), problems=(), meds=(), vitals=()):
    def node(nid, facts):
        return PatientNode(nid, "patient:p1", "fixed", nid, None, list(facts), [])
    return [PatientNode("patient:p1", None, "root", "Patient", None, [], []), node("allergies", allergies),
            node("problems.active", problems), node("meds.active", meds), node("vitals.latest", vitals)]


def food(code, name, entry="a1"):
    return {"entry_id": entry, "kind_code": "414285001", "kind": "Allergy to food", "substance_code": code,
            "substance": name, "reactions": ["Hives (finding)"], "severity": "Mild"}


def problem(code, name, entry="p1"):
    return {"entry_id": entry, "code": code, "display": name}


def weight(kg, when="2026-01-10"):
    return {"entry_id": "w1", "loinc": "29463-7", "display": "Body Weight", "value": str(kg), "unit": "kg", "date": when}


def test_sample_patient_meets_the_gate(rs):
    record, _ = ccda.read_record(FIXTURE, "sample", rs.p7)
    p = build_profile(build_tree(record), rs, record.record_date)
    assert p.allergens_exclude == {"wheat", "crustacean_shellfish"}
    assert MOLLUSCS <= p.ingredients_exclude
    assert set(p.nutrient_limits) == {"sodium_mg"}
    assert p.nutrient_limits["sodium_mg"] == ("max", pytest.approx(2000 / 3))  # exact, not rounded
    assert p.evidence["allergen:wheat"][0].entry_id == "887e4b4e-a3e1-b573-e91f-98d891253e61"  # the act id
    assert p.evidence["allergen:wheat"][0].node_id == "allergies"
    assert p.unmapped == [] and p.ruleset_version == rs.version


def test_shellfish_widens_to_molluscs(rs):
    p = build_profile(tree(allergies=[food("735029006", "Shellfish (substance)")]), rs, TODAY)
    assert p.allergens_exclude == {"crustacean_shellfish"}
    assert MOLLUSCS <= p.ingredients_exclude
    assert p.evidence["ingredient:conch"][0].text.startswith("Shellfish")


def test_food_substance_without_a_rule_is_unmapped(rs):
    p = build_profile(tree(allergies=[food("000000", "Kiwi (substance)")]), rs, TODAY)
    assert p.allergens_exclude == frozenset() and p.unmapped == ["allergy:000000 Kiwi (substance)"]


def test_non_food_allergy_yields_nothing(rs):
    latex = {**food("111088007", "Latex (substance)"), "kind_code": "419199007"}
    p = build_profile(tree(allergies=[latex]), rs, TODAY)
    assert not p.allergens_exclude and not p.unmapped


def test_strictest_limit_wins_and_the_overridden_rule_stays_in_evidence(rs):
    p = build_profile(tree(problems=[problem("59621000", "Essential hypertension (disorder)")]), rs, TODAY)
    assert p.nutrient_limits["sodium_mg"] == ("max", pytest.approx(2000 / 3))  # default 2000 mg beats DASH 2300 mg
    sources = [e.text for e in p.evidence["nutrient:sodium_mg"]]
    assert any("WHO" in s for s in sources) and any("DASH" in s for s in sources)
    assert "sat_fat_pct_kcal" not in p.nutrient_limits  # soft since v2 (ADR-0007): ranking + warning
    assert p.nutrient_soft["sat_fat_pct_kcal"] == ("max", 6.0)
    assert any("chất béo bão hòa" in w for w in p.warnings) and "soft:sat_fat_pct_kcal" in p.evidence


def test_t2d_complication_triggers_the_fiber_rule(rs):
    p = build_profile(tree(problems=[problem("90781000119102", "Microalbuminuria due to type 2 diabetes mellitus (disorder)")]),
                      rs, TODAY)
    assert p.nutrient_soft["fiber_per_1000kcal"] == ("min", 14.0) and "fiber_per_1000kcal" not in p.nutrient_limits


def test_ckd_protein_uses_a_recent_weight(rs):
    p = build_profile(tree(problems=[problem("433144002", "Chronic kidney disease stage 3 (disorder)")],
                           vitals=[weight(75)]), rs, TODAY)
    assert p.nutrient_limits["protein_g"] == ("max", pytest.approx(20.0))  # 0.8 * 75 / 3
    assert any(e.node_id == "vitals.latest" for e in p.evidence["nutrient:protein_g"])


@pytest.mark.parametrize("vitals", [[], [weight(75, when="2023-01-01")]])
def test_ckd_protein_without_a_recent_weight_is_a_warning(rs, vitals):
    p = build_profile(tree(problems=[problem("433144002", "CKD 3")], vitals=vitals), rs, TODAY)
    assert "protein_g" not in p.nutrient_limits
    assert any("đạm" in w for w in p.warnings) and "warning:protein_g_per_kg" in p.evidence


def test_ckd_stage_1_gets_sodium_but_not_protein(rs):
    p = build_profile(tree(problems=[problem("431855005", "CKD 1")], vitals=[weight(75)]), rs, TODAY)
    assert "protein_g" not in p.nutrient_limits and not any("đạm" in w for w in p.warnings)
    assert any("KDIGO" in e.text and e.node_id == "problems.active" for e in p.evidence["nutrient:sodium_mg"])


def test_nutrient_without_a_column_is_a_warning(rs):
    p = build_profile(tree(problems=[problem("431857002", "CKD 4")], vitals=[weight(70)]), rs, TODAY)
    assert "phosphorus_mg" not in p.nutrient_limits and any("phospho" in w for w in p.warnings)


def test_opposite_rules_on_one_nutrient_give_a_warning_not_a_filter(rs):
    up = rules.NutrientRule(("1",), "A", "sodium_mg", "max", 2000, "mg", "filter", "s1")
    down = rules.NutrientRule(("2",), "B", "sodium_mg", "min", 1000, "mg", "filter", "s2")
    custom = replace(rs, nutrient=[up, down])
    p = build_profile(tree(problems=[problem("1", "A"), problem("2", "B", "p2")]), custom, TODAY)
    assert "sodium_mg" not in p.nutrient_limits and any("trái chiều" in w for w in p.warnings)


def test_hyperglycemia_is_unmapped_not_filtered(rs):
    p = build_profile(tree(problems=[problem("80394007", "Hyperglycemia (disorder)")]), rs, TODAY)
    assert p.unmapped == ["condition:80394007 Hyperglycemia"]
    assert "fiber_per_1000kcal" not in p.nutrient_limits


def test_simvastatin_excludes_grapefruit_warfarin_warns(rs):
    meds = [{"entry_id": "m1", "code": "312961", "display": "Simvastatin 20 MG Oral Tablet"},
            {"entry_id": "m2", "code": "855332", "display": "Warfarin Sodium 5 MG Oral Tablet"}]
    p = build_profile(tree(meds=meds), rs, TODAY)
    assert "grapefruit" in p.ingredients_exclude
    assert p.evidence["ingredient:grapefruit"][0].entry_id == "m1"
    assert any("vitamin K" in w for w in p.warnings)


def test_round_trip_through_json(rs):
    record, _ = ccda.read_record(FIXTURE, "sample", rs.p7)
    p = build_profile(build_tree(record), rs, record.record_date)
    from api.patient.models import PatientProfile
    assert PatientProfile.from_dict(p.to_dict()) == p


def test_soft_and_hard_limits_on_one_nutrient_are_kept_apart(rs):
    hard = rules.NutrientRule(("1",), "A", "sodium_mg", "max", 2300, "mg", "filter", "s1")
    pref = rules.NutrientRule(("1",), "A", "sodium_mg", "max", 1500, "mg", "soft", "s2")
    p = build_profile(tree(problems=[problem("1", "A")]), replace(rs, nutrient=[hard, pref]), TODAY)
    assert p.nutrient_limits["sodium_mg"] == ("max", pytest.approx(2300 / 3))
    assert p.nutrient_soft["sodium_mg"] == ("max", pytest.approx(500))
