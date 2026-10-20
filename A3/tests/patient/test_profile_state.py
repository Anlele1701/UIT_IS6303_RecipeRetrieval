"""M2 with a patient layer (spec 8, test_profile_state). Pure."""

from api.patient.models import Evidence, PatientProfile
from api.pipeline.m2_state import merge
from api.pipeline.schemas import Constraints, Removal, SessionState, Understanding


def profile(pid="p1", allergens=("crustacean_shellfish",), limits=None, soft=None):
    ev = {f"allergen:{a}": [Evidence("allergies", "act1", "Shellfish – Mild")] for a in allergens}
    return PatientProfile(pid, frozenset(allergens), frozenset({"clam"}),
                          limits if limits is not None else {"sodium_mg": ("max", 2000 / 3)}, [], [], ev, "v", "vectorless",
                          soft or {})


def test_record_constraints_come_first_with_scope_source_and_evidence():
    s = merge(SessionState(), Understanding(query_en="pasta"), profile=profile())
    first = s.items[0]
    assert (first.type, first.value, first.scope, first.source) == ("allergen", "crustacean_shellfish", "patient", "patient")
    assert first.evidence[0]["entry_id"] == "act1"
    c = s.constraints()
    assert c.allergens_exclude == ["crustacean_shellfish"] and c.ingredients_exclude == ["clam"]
    assert c.nutrient_limits["sodium_mg"][0] == "max" and abs(c.nutrient_limits["sodium_mg"][1] - 666.6667) < 1e-3


def test_a_chat_message_cannot_lift_a_record_constraint():
    s1 = merge(SessionState(), Understanding(query_en="pasta"), profile=profile())
    lift = Understanding(intent="refine", query_en="shrimp pasta", remove=Removal(allergens=["crustacean_shellfish"]))
    s2 = merge(s1, lift, profile=profile())
    assert "crustacean_shellfish" in s2.constraints().allergens_exclude
    assert "from_record:allergen:crustacean_shellfish" in s2.notices


def test_a_dialogue_constraint_lifts_normally_beside_the_record():
    s1 = merge(SessionState(), Understanding(constraints=Constraints(allergens_exclude=["peanut"])), profile=profile())
    s2 = merge(s1, Understanding(intent="refine", remove=Removal(allergens=["peanut"])), profile=profile())
    assert s2.constraints().allergens_exclude == ["crustacean_shellfish"] and not s2.notices


def test_the_same_constraint_from_dialogue_and_record_is_kept_once_as_the_record_one():
    u = Understanding(constraints=Constraints(allergens_exclude=["crustacean_shellfish"]))
    s = merge(SessionState(), u, profile=profile())
    shellfish = [it for it in s.items if it.value == "crustacean_shellfish"]
    assert len(shellfish) == 1 and shellfish[0].source == "patient" and shellfish[0].evidence


def test_two_patients_never_share_record_constraints():
    a = merge(SessionState(), Understanding(), profile=profile("a", allergens=("egg",)))
    b = merge(a, Understanding(), profile=profile("b", allergens=("milk",)))  # a stale state from another session
    assert b.constraints().allergens_exclude == ["milk"]


def test_soft_limits_go_to_nutrient_soft_and_conv_off_keeps_the_record():
    p = profile(limits={}, soft={"sat_fat_pct_kcal": ("max", 6.0)})
    s = merge(SessionState(), Understanding(), conv=False, profile=p)
    c = s.constraints()
    assert c.nutrient_soft == {"sat_fat_pct_kcal": ("max", 6.0)} and not c.nutrient_limits
    assert c.allergens_exclude == ["crustacean_shellfish"]  # S-Conv forgets the dialogue, not the record


def test_without_a_profile_merge_is_the_m3_function():
    u = Understanding(constraints=Constraints(allergens_exclude=["peanut"], max_total_minutes=30))
    assert merge(SessionState(), u) == merge(SessionState(), u, profile=None)
    assert all(it.source == "dialogue" and it.scope != "patient" for it in merge(SessionState(), u).items)
