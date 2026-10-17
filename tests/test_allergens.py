import pytest

from api import allergens, config

BOOK = allergens.load_allergens(config.ALLERGENS_PATH)


def hits(name, title="Dish", lines=()):
    a = next(x for x in BOOK.allergens if x.name == name)
    return [(m.term, m.where) for m in allergens.find_matches(a, title, list(lines))]


def test_every_food_allergy_in_the_cohort_has_a_keyword_list():
    codes = {"735029006": "Shellfish", "102263004": "Egg", "3718001": "Cow's milk", "735971005": "Fish",
             "412071004": "Wheat", "442571000124108": "Tree nut", "256355007": "Soy", "762952008": "Peanut"}
    assert {c: BOOK.for_code(c).name for c in codes} == codes
    assert BOOK.for_code("0") is None


@pytest.mark.parametrize("allergen, line, term", [
    ("Egg", "2 large eggs, beaten", "eggs"),
    ("Egg", "1/2 cup mayonnaise", "mayonnaise"),
    ("Cow's milk", "1 cup whole milk", "milk"),
    ("Cow's milk", "2 tablespoons butter, softened", "butter"),
    ("Cow's milk", "1/2 cup grated Parmesan cheese", "parmesan"),
    ("Cow's milk", "1 cup half-and-half", "half-and-half"),
    ("Shellfish", "1 pound large shrimp, peeled", "shrimp"),
    ("Shellfish", "2 cans clams", "clams"),
    ("Fish", "4 anchovies", "anchovies"),
    ("Fish", "1 salmon fillet", "salmon"),
    ("Wheat", "2 cups all-purpose flour", "flour"),
    ("Wheat", "8 ounces spaghetti", "spaghetti"),
    ("Wheat", "1 cup bread crumbs", "bread crumbs"),
    ("Wheat", "1 cup bread-crumbs", "bread-crumbs"),
    ("Tree nut", "1/2 cup chopped walnuts", "walnuts"),
    ("Tree nut", "1 cup mixed nuts", "nuts"),
    ("Tree nut", "1 cup almond milk", "almond"),
    ("Soy", "2 tablespoons soy sauce", "soy"),
    ("Soy", "1 block firm tofu", "tofu"),
    ("Peanut", "1/4 cup peanut butter", "peanut"),
    ("Peanut", "1 tablespoon PEANUT oil", "peanut"),
])
def test_an_allergen_named_in_an_ingredient_line_is_found(allergen, line, term):
    assert hits(allergen, lines=[line]) == [(term, line)]


@pytest.mark.parametrize("allergen, line", [
    ("Egg", "1 eggplant, sliced"),
    ("Cow's milk", "1 can coconut milk"),
    ("Cow's milk", "1 cup almond milk"),
    ("Cow's milk", "1/2 cup peanut butter"),
    ("Cow's milk", "1 teaspoon cream of tartar"),
    ("Cow's milk", "1 butternut squash"),
    ("Shellfish", "2 crab apples"),
    ("Shellfish", "1 scalloped potato"),
    ("Wheat", "1 cup rice flour"),
    ("Wheat", "1 cup almond flour"),
    ("Tree nut", "1 cup coconut"),
    ("Tree nut", "1 teaspoon nutmeg"),
    ("Tree nut", "1 butternut squash"),
    ("Tree nut", "1 can water chestnuts"),
    ("Tree nut", "1/2 cup peanuts"),
    ("Soy", "1 cup rice"),
    ("Fish", "1 goldfish cracker"),
    ("Peanut", "1/2 cup almonds"),
])
def test_look_alikes_are_not_mistaken_for_the_allergen(allergen, line):
    assert hits(allergen, lines=[line]) == []


def test_the_title_is_searched_and_reported_as_the_place():
    assert hits("Peanut", title="Classic Peanut Butter Cookies", lines=["1 cup sugar"]) == [("peanut", "title")]


def test_only_the_exception_is_ignored_not_the_whole_line():
    assert hits("Cow's milk", lines=["1 cup coconut milk and 1 cup milk"]) == [("milk", "1 cup coconut milk and 1 cup milk")]


def test_bad_files_are_refused():
    ok = {"name": "X", "snomed_codes": ["1"], "terms": ["x"]}
    with pytest.raises(allergens.AllergenFileError, match="version"):
        allergens.parse_allergens({"version": 2, "allergens": [ok]})
    with pytest.raises(allergens.AllergenFileError, match="non-empty"):
        allergens.parse_allergens({"version": 1, "allergens": []})
    with pytest.raises(allergens.AllergenFileError, match="terms"):
        allergens.parse_allergens({"version": 1, "allergens": [{**ok, "terms": []}]})
    with pytest.raises(allergens.AllergenFileError, match="both"):
        allergens.parse_allergens({"version": 1, "allergens": [ok, {**ok, "name": "Y"}]})
    with pytest.raises(allergens.AllergenFileError, match="list of non-empty"):
        allergens.parse_allergens({"version": 1, "allergens": [{**ok, "except": [""]}]})
