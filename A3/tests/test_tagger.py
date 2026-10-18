"""D6-D8 on the real rules: hidden allergens, exceptions, diet flags and unknown lines."""

import pytest

from lexicon.tagger import IngredientTags, Line, default_rules, free_of, tag_recipe


@pytest.mark.parametrize("canonical,allergens", [
    ("butter", {"milk"}),
    ("unsalted butter", {"milk"}),
    ("peanut butter", {"peanut"}),  # not milk
    ("almond butter", {"tree_nuts"}),
    ("apple butter", set()),
    ("coconut milk", set()),  # coconut is not a tree nut (FDA 2025), and not milk
    ("coconut", set()),
    ("cream of tartar", set()),
    ("eggplant", set()),
    ("nutmeg", set()),
    ("water chestnut", set()),
    ("butternut squash", set()),
    ("mayonnaise", {"egg"}),
    ("soy sauce", {"soy", "wheat"}),
    ("worcestershire sauce", {"fish"}),
    ("pesto", {"tree_nuts", "milk"}),
    ("tahini", {"sesame"}),
    ("all purpose flour", {"wheat"}),
    ("almond flour", {"tree_nuts"}),  # not wheat
    ("rice flour", set()),
    ("corn tortilla", set()),
    ("flour tortilla", {"wheat"}),
    ("spaghetti squash", set()),
    ("spaghetti sauce", set()),
    ("shrimp", {"crustacean_shellfish"}),
    ("clam", set()),  # mollusc: not one of the FDA nine
    ("oyster mushroom", set()),
    ("pistachio nut", {"tree_nuts"}),  # not peanut
    ("mixed nut", {"tree_nuts", "peanut"}),
])
def test_allergens(canonical, allergens):
    assert set(default_rules().tags(canonical).allergens) == allergens


def test_hidden_and_direct_kinds():
    rules = default_rules()
    assert rules.tags("soy sauce").allergens == {"soy": "hidden", "wheat": "hidden"}
    assert rules.tags("milk").allergens == {"milk": "direct"}


@pytest.mark.parametrize("canonical,group", [
    ("chicken breast", "poultry"), ("beef broth", "meat"), ("salmon fillet", "fish"),
    ("shrimp", "shellfish"), ("marshmallow", "gelatin"), ("honey", "honey"),
    ("cheddar cheese", "dairy"), ("egg", "egg"), ("aluminum foil", "nonfood"), ("carrot", ""),
    ("steak sauce", ""), ("peanut butter", ""),
])
def test_groups(canonical, group):
    assert default_rules().tags(canonical).group == group


def it(group="", allergens=None, possible_groups=()):
    return IngredientTags(group, frozenset(possible_groups), allergens or {}, ())


TAGS = {"tofu": it(allergens={"soy": "direct"}), "rice": it(), "chicken": it("poultry"),
        "butter": it("dairy", {"milk": "direct"}), "honey": it("honey"),
        "worcestershire sauce": it("fish", {"fish": "hidden"}), "margarine": it(allergens={"milk": "possible"}),
        "chocolate chip": it(allergens={"milk": "possible", "soy": "possible"}),
        "refried bean": it(possible_groups={"meat"}), "pasta": it(allergens={"wheat": "hidden"})}


def test_vegan_recipe():
    t = tag_recipe([["tofu"], ["rice"]], TAGS)
    assert t.diet_flags == ("vegetarian", "vegan") and t.allergens == ("soy",) and not t.has_unknown


def test_dairy_is_vegetarian_not_vegan():
    assert tag_recipe([["butter"], ["rice"]], TAGS).diet_flags == ("vegetarian",)


def test_honey_is_vegetarian_not_vegan():
    assert tag_recipe([["honey"]], TAGS).diet_flags == ("vegetarian",)


def test_meat_rules_out_both():
    assert tag_recipe([["chicken"], ["rice"]], TAGS).diet_flags == ()


def test_a_definite_allergen_tag_rules_out_a_diet_too():
    assert tag_recipe([["worcestershire sauce"]], TAGS).diet_flags == ()


def test_possible_tags_are_flagged_not_filtered():
    t = tag_recipe([["chocolate chip"], ["rice"]], TAGS)
    assert t.allergens == () and t.allergens_may == ("milk", "soy")
    assert t.diet_flags == ("vegetarian", "vegan") and t.diet_may == ("vegan",)


def test_a_definite_tag_wins_over_a_possible_one():
    t = tag_recipe([["chocolate chip"], ["butter"]], TAGS)
    assert t.allergens == ("milk",) and t.allergens_may == ("soy",)


def test_a_possible_group_keeps_the_flag_but_marks_it():
    t = tag_recipe([["refried bean"]], TAGS)
    assert t.diet_flags == ("vegetarian", "vegan") and t.diet_may == ("vegetarian", "vegan")


def test_unknown_lines_are_counted_but_do_not_change_tags():
    t = tag_recipe([["tofu"], [], []], TAGS)
    assert t.has_unknown and t.unknown_lines == 2 and t.diet_flags == ("vegetarian", "vegan")


@pytest.mark.parametrize("line,free", [
    ("8 ounces gluten-free elbow pasta", {"wheat"}),
    ("1 cup dairy free chocolate chips", {"milk", "group:dairy"}),
    ("½ cup eggless mayonnaise", {"egg", "group:egg"}),
    ("2 tablespoons vegan butter", {"milk", "egg", "fish", "crustacean_shellfish", "group:dairy", "group:egg"}),
    ("1 cup non-dairy creamer", set()),  # non-dairy creamers still contain casein
    ("1 cup lactose-free milk", set()),  # still milk
])
def test_free_of(line, free):
    assert free <= free_of(line) and (free or not free_of(line))


def test_a_free_of_line_drops_only_its_own_tag():
    t = tag_recipe([Line(("pasta",), free_of("gluten-free pasta")), Line(("butter",))], TAGS)
    assert t.allergens == ("milk",) and t.free_of_lines == 1
    t = tag_recipe([Line(("pasta",), free_of("gluten-free pasta")), Line(("pasta",))], TAGS)
    assert t.allergens == ("wheat",)  # another line still has wheat
