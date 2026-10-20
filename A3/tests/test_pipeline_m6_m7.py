from api.pipeline import m6_generate as m6
from api.pipeline import m7_verify as m7
from api.pipeline.schemas import Constraints, RecipeCard

CARDS = [RecipeCard(id=11, title="Peanut Noodles", allergens=["peanut"], ingredients=["1 cup peanut"],
                    ingredients_norm=["peanut"]),
         RecipeCard(id=22, title="Veggie Curry", allergens_may=["milk"], diet_flags=["vegetarian", "vegan"],
                    ingredients=["1 can coconut milk"], ingredients_norm=["coconut milk"])]
NO_PEANUT = Constraints(allergens_exclude=["peanut"])


def test_context_is_fenced_best_first_with_possible_tags():
    msgs = m6.answer_messages("món không đậu phộng", "vi", NO_PEANUT, CARDS)
    system = msgs[0]["content"]
    assert "Answer in Vietnamese" in system and "no peanut (allergy)" in system
    assert system.index("[R11]") < system.index("[R22]") and "may contain: milk" in system
    assert "<context>" in system and msgs[-1] == {"role": "user", "content": "món không đậu phộng"}


def test_empty_context_is_said_to_be_empty():
    assert "(empty)" in m6.answer_messages("x", "en", Constraints(), [])[0]["content"]


def test_m7_removes_citations_outside_the_context_and_breaking_definite_tags():
    v = m7.verify("Try [R11] or [R22], or [R99].", CARDS, NO_PEANUT)
    assert v.citations == [22] and v.removed == [11, 99] and not v.verified
    assert m7.strip("Try [R11] or [R22].", v.removed) == "Try or [R22]."


def test_possible_tags_are_not_a_break_and_citing_nothing_passes():
    assert m7.verify("[R22]", CARDS, Constraints(allergens_exclude=["milk"], diet="vegan")).verified
    assert m7.verify("None of these fit, try fewer conditions.", CARDS, NO_PEANUT).verified
    assert m7.verify("Nothing found.", [], NO_PEANUT).verified


def test_retry_note_lists_only_allowed_recipes():
    note = m7.retry_note(m7.verify("[R11]", CARDS, NO_PEANUT), CARDS, NO_PEANUT)
    assert "[R22]" in note.split("only:")[1] and "[R11]" not in note.split("only:")[1]
