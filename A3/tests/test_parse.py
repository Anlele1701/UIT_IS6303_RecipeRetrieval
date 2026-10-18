"""D4 golden lines: real lines from recipe_ingredient and what the parser must make of them."""

import pytest

from lexicon.parse import parse_line

GOLDEN = [
    # line, quantity, unit, name, status
    ("1 (8 ounce) package cream cheese, softened", "1", "package", "cream cheese", "ok"),
    ("½ teaspoon salt", "1/2", "teaspoon", "salt", "ok"),
    ("1 ½ tablespoons chopped onion", "1 1/2", "tablespoons", "chopped onion", "ok"),
    ("2  eggs", "2", None, "eggs", "ok"),
    ("2 cloves garlic, minced", "2", "cloves", "garlic", "ok"),
    ("salt and ground black pepper to taste", None, None, "salt and ground black pepper", "partial"),
    ("salt to taste", None, None, "salt", "partial"),
    ("cooking spray", None, None, "cooking spray", "partial"),
    ("water to cover", None, None, "water", "partial"),
    ("vegetable oil for frying", None, None, "vegetable oil", "partial"),
    ("1 (15 ounce) can black beans, drained", "1", "can", "black beans", "ok"),
    ("4  skinless, boneless chicken breast halves - lightly pounded", "4", None,
     "skinless boneless chicken breast halves", "ok"),
    ("1  onion, finely chopped  (Optional)", "1", None, "onion", "ok"),
    ("2 tablespoons vegetable oil, divided, or as needed", "2", "tablespoons", "vegetable oil", "ok"),
    ("15  crimini mushrooms, sliced, or more to taste", "15", None, "crimini mushrooms", "ok"),
    ("1 tablespoon lemon pepper, or to taste", "1", "tablespoon", "lemon pepper", "ok"),
    ("1 pound bay scallops (about 36 small scallops)", "1", "pound", "bay scallops", "ok"),
    ("½ (16 ounce) can diced tomatoes and green chiles (such as RO*TEL®)", "1/2", "can",
     "diced tomatoes and green chiles", "ok"),
    ("1 (15 ounce) can CONTADINA® Tomato Sauce", "1", "can", "contadina tomato sauce", "ok"),
    ("¾ cup butter or margarine", "3/4", "cup", "butter or margarine", "ok"),
    ("¾ cup butter, or more as needed", "3/4", "cup", "butter", "ok"),
    ("1 teaspoon hot sauce  (Optional)", "1", "teaspoon", "hot sauce", "ok"),
    ("2  whole cloves", "2", None, "cloves", "ok"),
    ("1 pinch salt", "1", "pinch", "salt", "ok"),
    ("2 fluid ounces vodka", "2", "ounces", "vodka", "ok"),
    ("1 large red bell pepper, cut into 1 inch pieces", "1", None, "red bell pepper", "ok"),
    ("4  large lemons, juiced", "4", None, "lemons", "ok"),
    ("1 to 2 tablespoons honey", "1 to 2", "tablespoons", "honey", "ok"),
    ("2-3 cups chicken broth", "2-3", "cups", "chicken broth", "ok"),
    ("42 ounces chicken broth", "42", "ounces", "chicken broth", "ok"),
    ("1 (3 pound) boneless beef round steak, 2 inches thick", "1", None, "boneless beef round steak", "ok"),
    ("12  mint leaves, sliced thinly", "12", None, "mint leaves", "ok"),
    ("2  hard-boiled eggs, quartered", "2", None, "hard-boiled eggs", "ok"),
    ("¼ cup hot pepper sauce (such as Frank's RedHot®), or to taste", "1/4", "cup", "hot pepper sauce", "ok"),
    ("1 cup cooked, sliced carrots", "1", "cup", "cooked sliced carrots", "ok"),
    ("Paprika", None, None, "paprika", "partial"),
    ("1 cup", "1", "cup", "", "fail"),
    ("®), or to taste", None, None, "", "fail"),
    ("1 cup half-and-half", "1", "cup", "half-and-half", "ok"),
    ("1 (.25 ounce) package active dry yeast", "1", "package", "active dry yeast", "ok"),
    ("2  grilled skinless, boneless chicken breasts, cut into 1-inch pieces", "2", None,
     "grilled skinless boneless chicken breasts", "ok"),
    ("4 each skinless, boneless chicken breast halves", "4", None, "each skinless boneless chicken breast halves", "ok"),
]


@pytest.mark.parametrize("line,quantity,unit,name,status", GOLDEN)
def test_golden_line(line, quantity, unit, name, status):
    p = parse_line(line)
    assert (p.quantity, p.unit, p.name, p.status) == (quantity, unit, name, status)


def test_preparation_and_size_go_to_the_note():
    p = parse_line("1 (8 ounce) package cream cheese, softened")
    assert "8 ounce" in p.note and "softened" in p.note
