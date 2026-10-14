"""D6-D8 on the real rules: hidden allergens, exceptions, diet flags and unknown lines."""

import pytest

from lexicon.tagger import default_rules, tag_recipe


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


GROUPS = {"tofu": "", "rice": "", "chicken": "poultry", "butter": "dairy", "honey": "honey",
          "worcestershire sauce": "fish", "margarine": ""}
ALLERGENS = {"tofu": {"soy": "direct"}, "butter": {"milk": "direct"},
             "worcestershire sauce": {"fish": "hidden"}, "margarine": {"milk": "hidden"}}


def test_vegan_recipe():
    t = tag_recipe([["tofu"], ["rice"]], GROUPS, ALLERGENS)
    assert t.diet_flags == ("vegetarian", "vegan") and t.allergens == ("soy",) and not t.has_unknown


def test_dairy_is_vegetarian_not_vegan():
    assert tag_recipe([["butter"], ["rice"]], GROUPS, ALLERGENS).diet_flags == ("vegetarian",)


def test_honey_is_vegetarian_not_vegan():
    assert tag_recipe([["honey"]], GROUPS, ALLERGENS).diet_flags == ("vegetarian",)


def test_meat_rules_out_both():
    assert tag_recipe([["chicken"], ["rice"]], GROUPS, ALLERGENS).diet_flags == ()


def test_an_allergen_tag_rules_out_a_diet_too():
    assert tag_recipe([["worcestershire sauce"]], GROUPS, ALLERGENS).diet_flags == ()
    assert tag_recipe([["margarine"]], GROUPS, ALLERGENS).diet_flags == ("vegetarian",)


def test_unknown_lines_are_counted_but_do_not_change_tags():
    t = tag_recipe([["tofu"], [], []], GROUPS, ALLERGENS)
    assert t.has_unknown and t.unknown_lines == 2 and t.diet_flags == ("vegetarian", "vegan")
