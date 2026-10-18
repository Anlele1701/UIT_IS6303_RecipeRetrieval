from api.pipeline.flags import PRESETS, preset
from api.pipeline.m2_state import merge
from api.pipeline.m3_router import detail_recipe, route
from api.pipeline.schemas import Constraints, Removal, SessionState, StateItem, Understanding


def u(intent="search", **c) -> Understanding:
    extra = {k: c.pop(k) for k in ("remove", "session_scope", "ref_recipe", "clarify") if k in c}
    return Understanding(intent=intent, constraints=Constraints(**c), **extra)


def kinds(state: SessionState) -> set[tuple[str, str, str]]:
    return {(it.type, it.value, it.scope) for it in state.items}


def test_allergens_last_for_the_session_other_constraints_for_one_turn():
    s1 = merge(SessionState(), u(allergens_exclude=["peanut"], max_total_minutes=30))
    assert kinds(s1) == {("allergen", "peanut", "session"), ("max_total_minutes", "30", "turn")}
    s2 = merge(s1, u(ingredients_exclude=["cilantro"]))  # a new search drops the turn ones
    assert kinds(s2) == {("allergen", "peanut", "session"), ("ingredient_exclude", "cilantro", "turn")}


def test_refine_keeps_the_previous_turn_and_adds():
    s1 = merge(SessionState(), u(max_total_minutes=30))
    s2 = merge(s1, u("refine", allergens_exclude=["milk"]))
    assert kinds(s2) == {("max_total_minutes", "30", "turn"), ("allergen", "milk", "session")}


def test_lasting_makes_a_constraint_session_scope():
    s = merge(SessionState(), u(diet="vegetarian", session_scope=["diet"]))
    assert kinds(merge(s, u())) == {("diet", "vegetarian", "session")}


def test_removal_lifts_a_constraint():
    s1 = merge(SessionState(), u(allergens_exclude=["peanut", "milk"]))
    s2 = merge(s1, u("refine", remove=Removal(allergens=["peanut"])))
    assert kinds(s2) == {("allergen", "milk", "session")}


def test_single_valued_constraints_are_replaced():
    s1 = merge(SessionState(), u(max_total_minutes=30))
    assert kinds(merge(s1, u("refine", max_total_minutes=60))) == {("max_total_minutes", "60", "turn")}


def test_include_against_exclude_exclude_wins_and_is_noticed():
    s1 = merge(SessionState(), u(ingredients_exclude=["garlic"], session_scope=["ingredients_exclude"]))
    s2 = merge(s1, u("refine", ingredients_include=["garlic"]))
    assert ("ingredient_include", "garlic", "turn") not in kinds(s2) and s2.notices == ["include_and_exclude:garlic"]


def test_detail_and_chitchat_leave_the_state_alone_and_conv_off_forgets():
    s1 = merge(SessionState(), u(allergens_exclude=["egg"]))
    assert kinds(merge(s1, u("ask_detail", ref_recipe=2))) == kinds(s1)
    assert kinds(merge(s1, u(ingredients_exclude=["garlic"]), conv=False)) == {("ingredient_exclude", "garlic", "turn")}


def test_routes():
    state = SessionState(last_recipe_ids=[11, 22, 33])
    assert route(u(), state) == "retrieve"
    assert route(u("chitchat"), state) == route(u("out_of_scope"), state) == "chat"
    assert route(u(clarify="which onion?"), state) == "clarify"
    assert route(u("ask_detail", ref_recipe=2), state) == "detail" and detail_recipe(u("ask_detail", ref_recipe=2), state) == 22
    assert route(u("ask_detail", ref_recipe=2), SessionState()) == "retrieve"  # nothing shown yet


def test_presets_change_one_thing_each():
    s = preset("S")
    for name, f in PRESETS.items():
        if name.startswith("S-") or name.startswith("S+"):
            assert sum(getattr(f, k) != getattr(s, k) for k in vars(s)) == 1, name
    assert not preset("B0").generate and preset("B1").generate and not preset("B1").filter
