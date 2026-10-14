"""M2 session state (A3_ke_hoach_build.md 6.2): merge what M1 understood into the constraints the session holds.

- Allergens are `session` scope: they stay until the user lifts them (in words via M1 `remove`, or a chip).
- Everything else is `turn` scope unless the user made it lasting ("từ giờ", "from now on").
- `refine` keeps the previous turn's constraints and adds to them; a new `search` drops the old `turn` ones.
- ask_detail, chitchat and out_of_scope leave the state as it is.
- Include vs exclude of the same ingredient: exclude wins, and the user is told (notice).
With the conv flag off (S-Conv) every turn starts from an empty state. Pure: no I/O.
"""

from .schemas import SessionState, StateItem, Understanding

SINGLE = {"diet", "max_total_minutes", "max_calories", "category"}  # one value at a time
LASTING_TYPE = {"allergens": "allergen", "ingredients_exclude": "ingredient_exclude", "diet": "diet",
                "max_total_minutes": "max_total_minutes"}


def merge(state: SessionState, u: Understanding, conv: bool = True) -> SessionState:
    base = state if conv else SessionState()
    if u.intent in {"ask_detail", "chitchat", "out_of_scope"} or u.clarify:
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
