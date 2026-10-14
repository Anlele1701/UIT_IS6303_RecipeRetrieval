"""D4: split a raw ingredient line into quantity, unit, ingredient name and note. Rule-based, no model.

    "1 (8 ounce) package cream cheese, softened" -> quantity "1", unit "package", name "cream cheese",
                                                    note "(8 ounce); softened", status "ok"

The name keeps the words that say what the ingredient is ("ground black pepper"); D5 maps it to a
canonical ingredient. Status: ok (quantity and name), partial (name but no quantity, e.g. "salt to
taste"), fail (no name left).
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingest import normalize_fractions  # noqa: E402

UNITS = {
    "cup", "cups", "c", "teaspoon", "teaspoons", "tsp", "tablespoon", "tablespoons", "tbsp",
    "pound", "pounds", "lb", "lbs", "ounce", "ounces", "oz", "gram", "grams", "g", "kilogram", "kilograms",
    "kg", "milliliter", "milliliters", "ml", "liter", "liters", "l", "quart", "quarts", "pint", "pints",
    "gallon", "gallons", "pinch", "pinches", "dash", "dashes", "drop", "drops", "clove", "cloves",
    "slice", "slices", "stalk", "stalks", "sprig", "sprigs", "bunch", "bunches", "head", "heads",
    "piece", "pieces", "cube", "cubes", "fillet", "fillets", "leaf", "leaves", "strip", "strips",
    "sheet", "sheets", "stick", "sticks", "ear", "ears", "link", "links", "loaf", "loaves", "wedge", "wedges",
    "envelope", "envelopes", "packet", "packets", "package", "packages", "can", "cans", "jar", "jars",
    "container", "containers", "bottle", "bottles", "bag", "bags", "box", "boxes", "carton", "cartons",
    "tube", "tubes", "pouch", "pouches", "scoop", "scoops", "handful", "handfuls", "square", "squares",
    "bar", "bars", "shot", "shots", "jigger", "jiggers", "splash", "fluid", "fl", "inch", "inches",
}
SIZES = {"large", "small", "medium", "extra-large", "jumbo", "heaping", "level", "rounded", "scant",
         "generous", "big", "whole", "half"}
# Words that describe how an ingredient is bought or prepared, not what it is. D5 drops them too.
DESCRIPTORS = {
    "fresh", "freshly", "frozen", "thawed", "dried", "dry", "chopped", "finely", "coarsely", "roughly",
    "minced", "diced", "sliced", "thinly", "thickly", "grated", "shredded", "crushed", "ground", "peeled",
    "seeded", "pitted", "cored", "trimmed", "halved", "quartered", "cubed", "julienned", "mashed", "melted",
    "softened", "cold", "warm", "room", "temperature", "boiling", "cooked", "uncooked", "raw",
    "toasted", "roasted", "packed", "lightly", "firmly", "loosely", "beaten", "lean", "extra", "skinless",
    "boneless", "bone-in", "skin-on", "rinsed", "drained", "canned", "prepared", "organic", "ripe",
    "sifted", "unsifted", "unpeeled", "deveined", "shelled", "cut", "torn", "stemmed", "zested", "juiced",
}
QUANTITY_RE = re.compile(
    r"^\s*(?P<q>\d+(?:[.,]\d+)?(?:\s+\d+/\d+|/\d+)?(?:\s*(?:-|to|or)\s*\d+(?:[.,]\d+)?(?:\s+\d+/\d+|/\d+)?)?)\s*")
PAREN_RE = re.compile(r"\([^)]*\)")
TRAILING_RE = re.compile(
    r"\b(?:to taste|to cover|or (?:more|less)?\s*(?:as needed|to taste)|as needed|or more|if needed|divided|"
    r"for garnish|for (?:dusting|frying|serving|decoration|brushing|greasing)|optional|plus more)\b.*$")


@dataclass(frozen=True)
class ParsedLine:
    quantity: str | None
    unit: str | None
    name: str
    note: str
    status: str  # ok | partial | fail


def _clean(s: str) -> str:
    s = s.replace("®", "").replace("™", "").replace("*", "")
    s = re.sub(r"[^\w\s'&/-]", " ", s)
    return re.sub(r"\s+", " ", s).strip(" -/")


def parse_line(line: str) -> ParsedLine:
    text = normalize_fractions(line).replace(" ", " ").strip().lower()
    notes = [p.strip("() ") for p in PAREN_RE.findall(text)]
    text = PAREN_RE.sub(" ", text)

    quantity = None
    m = QUANTITY_RE.match(text)
    if m:
        quantity = m.group("q").strip()
        text = text[m.end():]

    words = text.split()
    unit = None
    # "1 (8 ounce) package", "2 fluid ounces", "1 large can": units and sizes before the name
    while words and (words[0].strip(",") in UNITS or words[0].strip(",") in SIZES or words[0] in {"of", "a", "an"}):
        w = words.pop(0).strip(",")
        if w in UNITS and unit is None and w not in {"fluid", "fl", "inch", "inches"}:
            unit = w
    if not words and unit and unit not in {"cup", "cups"}:
        # "2 whole cloves", "1 head": the unit word is the ingredient itself
        words, unit = [unit], None
    text = " ".join(words)

    # After the first comma comes the preparation ("minced", "softened"), unless everything before it is
    # a descriptor: "skinless, boneless chicken breast halves" keeps going to the next comma.
    parts = text.split(",")
    cut = 1
    while cut < len(parts) and all(w in DESCRIPTORS for w in _clean(" ".join(parts[:cut])).split()):
        cut += 1
    name, rest = " ".join(parts[:cut]), ",".join(parts[cut:])
    if rest.strip():
        notes.append(rest.strip(" ,"))
    name, dash, after = name.partition(" - ")  # "chicken breast halves - lightly pounded"
    if dash:
        notes.append(after.strip())
    trailing = TRAILING_RE.search(name)
    if trailing:
        notes.append(trailing.group(0).strip())
        name = name[:trailing.start()]
    name = _clean(re.sub(r"\b(?:or|and)\s*$", "", name.strip()))

    status = "fail" if not name else "ok" if quantity else "partial"
    return ParsedLine(quantity, unit, name, "; ".join(n for n in notes if n), status)
