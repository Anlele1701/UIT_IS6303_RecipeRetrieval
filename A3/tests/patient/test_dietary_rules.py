"""Dietary Rule Engine (api/patient/dietary_rules.py): active conditions -> per-serving Filters. Pure."""

import copy
import json
from datetime import date

import psycopg
import pytest

from api import config
from api.filters import SearchParams
from api.patient.dietary_rules import (NUTRIENTS, RULES_FILE, ActiveCondition, ConditionProfile, RuleBook,
                                       RuleFileError, derive_diet_plan, filterable_nutrients, floor_tenth,
                                       load_rules, parse_rules, profile_from_nodes)
from api.patient.models import PatientNode

RULES = load_rules()
FILTERABLE = filterable_nutrients()

HTN, CHF, T2DM, PREDIABETES = "59621000", "88805009", "44054006", "714628002"
HYPERLIPIDEMIA, GOUT, CKD3, SOCIAL = "55822004", "90560007", "433144002", "160903007"


def profile(*codes) -> ConditionProfile:
    return ConditionProfile("p1", [ActiveCondition(c, f"condition {c}", date(2010, 1, 1)) for c in codes])


def plan(*codes, meals=3):
    return derive_diet_plan(profile(*codes), RULES, FILTERABLE, meals)


# --- the plan -------------------------------------------------------------------------------


def test_hypertension_limits_sodium_per_serving():
    p = plan(HTN)
    assert p.status == "filtered"
    assert p.filters == {"max_sodium_mg": 500.0}
    (e,) = p.evidence
    assert (e.rule_id, e.nutrient, e.daily, e.per_serving, e.binding) == ("htn-sodium", "sodium_mg", 1500.0, 500.0, True)
    assert [c.code for c in e.conditions] == [HTN]


def test_smallest_limit_wins_and_every_contributor_is_listed():
    p = plan(HTN, CHF)
    assert p.filters == {"max_sodium_mg": 500.0}
    by_rule = {e.rule_id: e for e in p.evidence}
    assert by_rule["htn-sodium"].binding is True
    assert by_rule["chf-sodium"].binding is False and by_rule["chf-sodium"].per_serving == 666.6


def test_different_nutrients_give_separate_filters():
    p = plan(HTN, T2DM)
    assert p.filters == {"max_carbohydrates_g": 60.0, "max_sodium_mg": 500.0}


def test_two_conditions_of_one_rule_make_one_limit_with_both_conditions():
    p = plan(T2DM, PREDIABETES)
    assert len(p.evidence) == 1
    assert {c.code for c in p.evidence[0].conditions} == {T2DM, PREDIABETES}


def test_limit_on_a_nutrient_that_cannot_be_filtered_is_reported_not_dropped():
    p = plan(HYPERLIPIDEMIA)
    assert p.filters == {} and p.status == "no_applicable_rules"
    (u,) = p.unapplied_limits
    assert (u.nutrient, u.rule_id, u.per_serving) == ("saturated_fat_g", "lipid-satfat", 4.3)


def test_the_same_limit_applies_once_the_nutrient_becomes_filterable():
    p = derive_diet_plan(profile(HYPERLIPIDEMIA), RULES, FILTERABLE | {"saturated_fat_g"}, 3)
    assert p.filters == {"max_saturated_fat_g": 4.3} and p.unapplied_limits == []


def test_known_but_unsupported_conditions_are_listed_with_a_reason():
    p = plan(GOUT, CKD3)
    assert p.filters == {} and p.status == "no_applicable_rules"
    assert {u.code: u.rule_id for u in p.unsupported_conditions} == {GOUT: "gout-unsupported", CKD3: "ckd-unsupported"}
    assert all(u.reason for u in p.unsupported_conditions)
    assert p.unmatched_conditions == 0


def test_conditions_no_rule_mentions_are_counted_not_listed():
    p = plan(HTN, SOCIAL, "1234")
    assert p.unmatched_conditions == 2
    assert p.unsupported_conditions == []


def test_a_patient_with_no_conditions_is_not_an_error():
    p = plan()
    assert p.status == "no_applicable_rules" and p.filters == {} and p.evidence == []


def test_filter_values_round_down_not_up():
    assert floor_tenth(13 / 3) == 4.3  # 4.333...
    assert floor_tenth(2000 / 3) == 666.6  # not 666.7
    assert floor_tenth(1500 / 3) == 500.0  # float error must not give 499.9
    assert floor_tenth(0.35 / 1) == 0.3


def test_meals_per_day_scales_the_limit():
    assert plan(HTN, meals=2).filters == {"max_sodium_mg": 750.0}
    with pytest.raises(ValueError):
        plan(HTN, meals=0)


def test_adding_a_condition_never_loosens_a_filter():
    codes = [HTN, CHF, T2DM, PREDIABETES, HYPERLIPIDEMIA, GOUT, CKD3, SOCIAL]
    for i in range(len(codes)):
        before, after = plan(*codes[:i]).filters, plan(*codes[:i + 1]).filters
        for key, value in before.items():
            assert after[key] <= value


def test_filters_are_accepted_by_the_search_params():
    every = [c for r in RULES.rules for c in r.snomed_codes]
    p = plan(*every)
    assert p.filters  # something to pass
    SearchParams(q="soup", strategy="semantic", **p.filters)  # extra="forbid" rejects a wrong key


# --- from a patient tree --------------------------------------------------------------------


def tree(problems):
    return [PatientNode("patient:p1", None, "root", "Patient", None, [], []),
            PatientNode("allergies", "patient:p1", "fixed", "Allergies", None, [{"code": "ignored"}], []),
            PatientNode("problems.active", "patient:p1", "fixed", "Active problems", None, list(problems), [])]


def problem(code, display, entry="e1"):
    return {"entry_id": entry, "code": code, "display": display}


def test_conditions_come_from_the_problems_node_only_and_without_a_date():
    prof = profile_from_nodes("p1", tree([problem(HTN, "Hypertension (disorder)")]))
    assert prof.patient_id == "p1"
    assert prof.active_conditions == [ActiveCondition(HTN, "Hypertension (disorder)", None)]


def test_a_code_recorded_twice_is_one_condition_and_a_missing_code_is_skipped():
    prof = profile_from_nodes("p1", tree([problem(HTN, "Hypertension", "e1"), problem(None, "No code", "e2"),
                                          problem(T2DM, None, "e3"), problem(HTN, "Hypertension again", "e4")]))
    assert [(c.code, c.description) for c in prof.active_conditions] == [(HTN, "Hypertension"), (T2DM, T2DM)]


def test_a_tree_without_problems_gives_an_empty_plan():
    p = derive_diet_plan(profile_from_nodes("p1", tree([])), RULES, FILTERABLE, 3)
    assert p.status == "no_applicable_rules" and p.patient_id == "p1"


def test_a_plan_from_a_tree_has_no_onset_date():
    p = derive_diet_plan(profile_from_nodes("p1", tree([problem(HTN, "Hypertension")])), RULES, FILTERABLE, 3)
    assert p.filters == {"max_sodium_mg": 500.0}
    assert p.evidence[0].conditions[0].since is None


# --- the chat pipeline must know every column the engine can limit -----------------------------------


def test_every_filterable_nutrient_is_known_to_the_chat_pipeline():
    """A limit on a column M4, M5 or M7 does not know would raise (ValueError / KeyError) in the middle of a chat."""
    from api.patient.nutrition import COLUMN_SQL
    from api.pipeline.m4_retrieve import NUTRIENT_COLUMNS, conditions
    from api.pipeline.schemas import Constraints
    assert FILTERABLE <= set(COLUMN_SQL) and FILTERABLE <= NUTRIENT_COLUMNS
    for col in FILTERABLE:
        conditions(Constraints(nutrient_limits={col: ("max", 1.0)}), True, True)  # M4 raises for an unknown column


def test_every_hard_limit_of_the_diet_rules_leaves_at_least_half_of_the_recipes():
    """ADR-0007's gate, for this rule book: a per-serving limit that fails over half of the Recipes would be soft.
    Measured on the live recipe table (read only); skipped when it is not there."""
    try:
        conn = psycopg.connect(config.DATABASE_URL, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("the recipe database is not running")
    with conn:
        if conn.execute("SELECT count(*) FROM recipe_nutrition").fetchone()[0] < 30000:
            pytest.skip("the full recipe table is not loaded")
        for rule in RULES.rules:
            for lim in rule.limits:
                if lim.nutrient not in FILTERABLE:  # name checked against NUTRIENTS at load
                    continue
                per_serving = floor_tenth(lim.daily / config.MEALS_PER_DAY)
                ok, known = conn.execute(f"SELECT count(*) FILTER (WHERE {lim.nutrient} <= %s), count({lim.nutrient}) "
                                         "FROM recipe_nutrition", [per_serving]).fetchone()
                assert ok / known >= 0.5, (rule.rule_id, lim.nutrient, per_serving, round(ok / known, 3))


# --- the rule file --------------------------------------------------------------------------


def test_the_shipped_rule_file_loads_and_only_names_known_nutrients():
    assert isinstance(RULES, RuleBook)
    for rule in RULES.rules:
        assert {lim.nutrient for lim in rule.limits} <= NUTRIENTS


def test_each_snomed_code_belongs_to_one_rule_in_the_shipped_file():
    seen = {}
    for rule in RULES.rules:
        for code in rule.snomed_codes:
            assert code not in seen, f"{code} is in {seen[code]} and {rule.rule_id}"
            seen[code] = rule.rule_id


def test_filterable_nutrients_today():
    assert FILTERABLE == {"calories", "protein_g", "fat_g", "carbohydrates_g", "sodium_mg"}


def _file():
    return copy.deepcopy(json.load(open(RULES_FILE)))


@pytest.mark.parametrize("break_it, message", [
    (lambda d: d.update(version=2), "version"),
    (lambda d: d["rules"][0]["limits"][0].update(nutrient="sodium"), "unknown nutrient"),
    (lambda d: d["rules"][0]["limits"][0].update(op="min"), "only op 'max'"),
    (lambda d: d["rules"][0]["limits"][0].update(daily=0), "positive number"),
    (lambda d: d["rules"][0]["limits"][0].update(daily=True), "positive number"),
    (lambda d: d["rules"][0]["limits"][0].update(when={"egfr": "<30"}), "exactly"),
    (lambda d: d["rules"][0]["limits"].append(dict(d["rules"][0]["limits"][0])), "limited twice"),
    (lambda d: d["rules"][0].update(snomed_codes=[]), "snomed_codes"),
    (lambda d: d["rules"][0].update(snomed_codes=["hypertension"]), "snomed_codes"),
    (lambda d: d["rules"][0].update(status="approved"), "status"),
    (lambda d: d["rules"][0].update(colour="red"), "unknown keys"),
    (lambda d: d["rules"][1].update(rule_id=d["rules"][0]["rule_id"]), "duplicate"),
    (lambda d: d["rules"][-1].pop("unsupported_reason"), "unsupported_reason"),
    (lambda d: d["rules"][0].update(unsupported_reason="x"), "must not have"),
    (lambda d: d.update(rules=[]), "no rules"),
])
def test_a_bad_rule_file_is_refused_at_load(break_it, message):
    data = _file()
    break_it(data)
    with pytest.raises(RuleFileError, match=message):
        parse_rules(data)
