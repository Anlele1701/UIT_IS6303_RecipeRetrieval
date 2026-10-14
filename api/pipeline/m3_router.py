"""M3 router (conditional flow, sườn báo cáo 3.4): which path a turn takes. Linear otherwise ([R02 §6.6]: no loops
with a 7B model). Pure."""

from typing import Literal

from .schemas import SessionState, Understanding

Route = Literal["retrieve", "detail", "clarify", "chat"]


def route(u: Understanding, state: SessionState) -> Route:
    if u.clarify:
        return "clarify"
    if u.intent in {"chitchat", "out_of_scope"}:
        return "chat"
    if u.intent == "ask_detail":
        return "detail" if detail_recipe(u, state) else "retrieve"
    return "retrieve"


def detail_recipe(u: Understanding, state: SessionState) -> int | None:
    """The Recipe an ask_detail turn is about: a position in the last answer (1-based) or a Recipe id."""
    ref = u.ref_recipe
    if not ref:
        return state.last_recipe_ids[0] if state.last_recipe_ids else None
    if 1 <= ref <= len(state.last_recipe_ids):
        return state.last_recipe_ids[ref - 1]
    return ref if ref > 100 else None  # a small number outside the list is a position we cannot resolve
