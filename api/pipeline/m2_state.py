"""M2 session state (A3_ke_hoach_build.md 6.2): merge what M1 understood into the constraints the session holds.

- Allergens are `session` scope: they stay until the user lifts them (in words via M1 `remove`, or a chip).
- Everything else is `turn` scope unless the user made it lasting ("từ giờ", "from now on").
- `refine` keeps the previous turn's constraints and adds to them; a new `search` drops the old `turn` ones.
- ask_detail, chitchat and out_of_scope leave the state as it is.
- Include vs exclude of the same ingredient: exclude wins, and the user is told (notice).
With the conv flag off (S-Conv) every turn starts from an empty state. Pure: no I/O.

Patient sessions (MV3, docs/plan/A3_vectorless_ho_so.md 5.6) add a `patient` layer from the PatientProfile:
- its items have scope `patient` and source `patient`, with their evidence; they are rebuilt from the profile on
  every turn (the profile is the source of truth) and come first;
- a chat message cannot lift them: "tôi ăn được tôm" against a record allergy keeps it and adds the notice
  `from_record:allergen:crustacean_shellfish` (lifting needs a confirmed PATCH in the UI, milestone M4);
- a dialogue constraint the record also holds is kept once, as the patient item.
Without a profile, merge() is exactly the M3 function.
"""

from dataclasses import asdict

from .schemas import SessionState, StateItem, Understanding, limit_value

SINGLE = {"diet", "max_total_minutes", "max_calories", "category"}  # one value at a time
LASTING_TYPE = {"allergens": "allergen", "ingredients_exclude": "ingredient_exclude", "diet": "diet",
                "max_total_minutes": "max_total_minutes"}


def merge(state: SessionState, u: Understanding, conv: bool = True, profile=None) -> SessionState:
    if profile is None:
        return _merge(state, u, conv)
    dialogue = state.model_copy(update={"items": [it for it in state.items if it.scope != "patient"]})
    out = _merge(dialogue, u, conv)
    record = patient_items(profile)
    held = {(it.type, it.value) for it in record}
    notices = [f"from_record:{t}:{v}" for t, v in requested_removals(u) if (t, v) in held]
    kept = [it for it in out.items if (it.type, it.value) not in held]
    return SessionState(items=record + kept, last_recipe_ids=out.last_recipe_ids, notices=out.notices + notices)


def patient_items(profile) -> list[StateItem]:
    """The record's constraints as state items (scope and source `patient`), each with its evidence."""
    def item(t, value, key):
        return StateItem(type=t, value=value, scope="patient", source="patient",
                         evidence=[asdict(e) for e in profile.evidence.get(key, [])])
    items = [item("allergen", a, f"allergen:{a}") for a in sorted(profile.allergens_exclude)]
    items += [item("ingredient_exclude", i, f"ingredient:{i}") for i in sorted(profile.ingredients_exclude)]
    items += [item("nutrient", limit_value(c, op, v), f"nutrient:{c}") for c, (op, v) in sorted(profile.nutrient_limits.items())]
    items += [item("nutrient_soft", limit_value(c, op, v), f"soft:{c}") for c, (op, v) in sorted(profile.nutrient_soft.items())]
    return items


def requested_removals(u: Understanding) -> list[tuple[str, str]]:
    r = u.remove
    return [("allergen", a) for a in r.allergens] + [("ingredient_exclude", i) for i in r.ingredients]


def _merge(state: SessionState, u: Understanding, conv: bool = True) -> SessionState:
    base = state if conv else SessionState()
    if u.intent in {"ask_detail", "chitchat", "out_of_scope", "patient_info"} or u.clarify:
        return base.model_copy(update={"notices": []})
    items = [it for it in base.items if u.intent == "refine" or it.scope == "session"]
    items = remove(items, u)
    lasting = {LASTING_TYPE[s] for s in u.session_scope if s in LASTING_TYPE}
    notices = []

    def scope(t: str) -> str:
        return "session" if t == "allergen" or t in lasting else "turn"

    c = u.constraints
    new = ([("allergen", a) for a in c.allergens_exclude] + [("ingredient_exclude", i) for i in c.ingredients_exclude]
           + [("ingredient_include", i) for i in c.ingredients_include]
           + ([("diet", c.diet)] if c.diet else []) + ([("max_total_minutes", str(c.max_total_minutes))]
                                                       if c.max_total_minutes else [])
           + ([("max_calories", str(c.max_calories))] if c.max_calories else [])
           + ([("category", c.category)] if c.category else []))
    for t, v in new:
        if t in SINGLE:
            items = [it for it in items if it.type != t]
        if not any(it.type == t and it.value == v for it in items):
            items.append(StateItem(type=t, value=v, scope=scope(t)))
    excluded = {it.value for it in items if it.type == "ingredient_exclude"}
    clash = [it.value for it in items if it.type == "ingredient_include" and it.value in excluded]
    if clash:
        notices.append(f"include_and_exclude:{','.join(sorted(set(clash)))}")
        items = [it for it in items if not (it.type == "ingredient_include" and it.value in excluded)]
    return SessionState(items=items, last_recipe_ids=base.last_recipe_ids, notices=notices)


def remove(items: list[StateItem], u: Understanding) -> list[StateItem]:
    r = u.remove
    drop_ing = set(r.ingredients)
    return [it for it in items if not (
        (it.type == "allergen" and it.value in r.allergens)
        or (it.type in {"ingredient_exclude", "ingredient_include"} and it.value in drop_ing)
        or (it.type == "diet" and r.diet) or (it.type == "max_total_minutes" and r.max_total_minutes))]
