"""Food allergies: which Recipes a patient must not be given.

The patient's active food allergies (SNOMED codes, from the record) are mapped to keyword lists in
api/food_allergens.json. A Recipe is excluded when its title or any ingredient line names one of the
keywords. This is code, never the LLM, and it runs on every Recipe before it is shown.

It is a screen, not a guarantee: it only sees what the ingredient lines say. An allergy whose code has no
entry in the file is reported as unchecked, so the caller can warn instead of silently passing it.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path


class AllergenFileError(ValueError):
    pass


@dataclass(frozen=True)
class Allergen:
    name: str
    snomed_codes: frozenset[str]
    terms: tuple[str, ...]
    exceptions: tuple[str, ...]
    pattern: re.Pattern
    exception_pattern: re.Pattern | None


@dataclass(frozen=True)
class AllergenBook:
    allergens: tuple[Allergen, ...]

    def for_code(self, code: str) -> Allergen | None:
        return next((a for a in self.allergens if code in a.snomed_codes), None)


@dataclass(frozen=True)
class Match:
    allergen: str
    term: str  # the text that matched
    where: str  # "title" or the ingredient line


def _phrase(text: str) -> str:
    """A phrase as a regex: spaces match any run of spaces or hyphens."""
    return r"[\s-]+".join(re.escape(w) for w in text.split())


def _compile(entry: dict, where: str) -> Allergen:
    for key in ("name", "snomed_codes", "terms"):
        if not entry.get(key):
            raise AllergenFileError(f"{where}: '{key}' is missing or empty")
    for key in ("snomed_codes", "terms", "except"):
        if not isinstance(entry.get(key, []), list) or not all(isinstance(x, str) and x.strip() for x in entry.get(key, [])):
            raise AllergenFileError(f"{where}: '{key}' must be a list of non-empty strings")
    terms = tuple(t.lower().strip() for t in entry["terms"])
    exceptions = tuple(t.lower().strip() for t in entry.get("except", []))
    # Whole words, with an optional plural: "egg" matches "eggs" but not "eggplant".
    # Longest first, so "bread crumbs" is reported rather than "bread".
    def alternatives(words):
        return "|".join(_phrase(t) for t in sorted(words, key=len, reverse=True))
    pattern = re.compile(r"\b(?:" + alternatives(terms) + r")(?:e?s)?\b")
    exc = re.compile(r"\b(?:" + alternatives(exceptions) + r")(?:e?s)?\b") if exceptions else None
    return Allergen(entry["name"], frozenset(entry["snomed_codes"]), terms, exceptions, pattern, exc)


def parse_allergens(data: dict) -> AllergenBook:
    if data.get("version") != 1:
        raise AllergenFileError(f"unsupported version {data.get('version')!r}")
    entries = data.get("allergens")
    if not isinstance(entries, list) or not entries:
        raise AllergenFileError("'allergens' must be a non-empty list")
    allergens = tuple(_compile(e, f"allergens[{i}]") for i, e in enumerate(entries))
    seen: dict[str, str] = {}
    for a in allergens:
        for code in a.snomed_codes:
            if code in seen:
                raise AllergenFileError(f"code {code} is listed under both {seen[code]} and {a.name}")
            seen[code] = a.name
    return AllergenBook(allergens)


def load_allergens(path: Path) -> AllergenBook:
    try:
        return parse_allergens(json.loads(Path(path).read_text()))
    except json.JSONDecodeError as e:
        raise AllergenFileError(f"{path}: not valid JSON ({e})") from e


def find_matches(allergen: Allergen, title: str, lines: list[str]) -> list[Match]:
    """Every place the Recipe names this allergen. Empty means the Recipe passes this allergen."""
    out = []
    for where, text in [("title", title), *[(line, line) for line in lines]]:
        text = text.lower()
        if allergen.exception_pattern:
            text = allergen.exception_pattern.sub(" ", text)
        m = allergen.pattern.search(text)
        if m:
            out.append(Match(allergen.name, m.group(0), where))
    return out
