"""D6-D8: food group and allergens per canonical ingredient (data/lexicon/rules.csv), tags per Recipe.

Rules are phrases matched on a canonical name with the same longest-first scan as D5, so a longer
phrase is an exception for the words inside it ("peanut butter" -> peanut, not milk).

Two levels (Thy, gate M1 review): a tag is either definite (kind direct or hidden: butter -> milk,
soy sauce -> wheat) or possible, written with "?" in rules.csv (chocolate -> milk?, kimchi -> fish?):
brand- or recipe-dependent, so the cook can pick a product without it. Definite tags drive the hard
filter (chunk.allergens); possible ones are kept apart (recipe_tag.allergens_may) for a warning.
A group can be possible too ("meat?" for canned refried beans).

A Recipe has allergen X when any line maps to an ingredient with X (alternatives in "butter or
margarine" all count), unless that line says it is free of X ("gluten-free pasta"; D6b). Diet (D7):
  vegetarian: no animal group (meat, poultry, fish, shellfish, gelatin) and no fish/crustacean tag
  vegan:      vegetarian and no dairy, egg or honey group and no milk/egg tag
`diet_may` lists the flags that hold only because possible tags were left out.
D8: a line with no canonical ingredient is `unknown`; `has_unknown` marks the Recipe. Unknown lines
do not change any tag here; the S+Unknown ablation decides what to do with them.
"""

import csv
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from .normalize import LEXICON, MAX_WORDS, words

ALLERGENS = ["milk", "egg", "fish", "crustacean_shellfish", "tree_nuts", "peanut", "wheat", "soy", "sesame"]
ANIMAL = {"meat", "poultry", "fish", "shellfish", "gelatin", "rennet"}  # rennet: animal-rennet cheeses (Thy, gate M2)
NOT_VEGAN = ANIMAL | {"dairy", "egg", "honey"}
ANIMAL_ALLERGENS = {"fish", "crustacean_shellfish"}
NOT_VEGAN_ALLERGENS = ANIMAL_ALLERGENS | {"milk", "egg"}
GROUP_PRIORITY = ["meat", "poultry", "fish", "shellfish", "gelatin", "rennet", "dairy", "egg", "honey", "nonfood"]

# D6b: what a line says it is free of. Not "non-dairy" (non-dairy creamers contain casein) and not
# "lactose-free" (still milk).
FREE_OF = [
    (re.compile(r"\b(?:gluten|wheat)[\s-]*free\b"), {"wheat"}),
    (re.compile(r"\b(?:dairy|milk)[\s-]*free\b"), {"milk", "group:dairy"}),
    (re.compile(r"\begg[\s-]*free\b|\beggless\b"), {"egg", "group:egg"}),
    (re.compile(r"\bnut[\s-]*free\b"), {"tree_nuts", "peanut"}),
    (re.compile(r"\bpeanut[\s-]*free\b"), {"peanut"}),
    (re.compile(r"\bsoy[\s-]*free\b"), {"soy"}),
    (re.compile(r"\bsesame[\s-]*free\b"), {"sesame"}),
    (re.compile(r"\bvegan\b"), {"milk", "egg", "fish", "crustacean_shellfish", *(f"group:{g}" for g in NOT_VEGAN)}),
    (re.compile(r"\bvegetarian\b|\bmeatless\b|\bplant[\s-]*based\b"),
     {"fish", "crustacean_shellfish", *(f"group:{g}" for g in ANIMAL)}),
]


def free_of(text: str) -> frozenset[str]:
    """Allergen codes and "group:<g>" markers a line says it is free of."""
    text = text.lower()
    return frozenset(x for pattern, xs in FREE_OF if pattern.search(text) for x in xs)


@dataclass(frozen=True)
class Rule:
    phrase: str
    groups: tuple[tuple[str, bool], ...]  # (group, possible); "dairy|rennet?" gives two
    allergens: tuple[tuple[str, bool], ...]  # (code, possible)
    kind: str
    note: str


@dataclass(frozen=True)
class IngredientTags:
    group: str  # definite group; "" when no rule gives one
    possible_groups: frozenset[str]
    allergens: dict[str, str]  # code -> direct | hidden | possible
    rules: tuple[str, ...]  # phrases that fired, for review


@dataclass
class Rules:
    by_key: dict[str, Rule] = field(default_factory=dict)

    @classmethod
    def from_csv(cls, path: Path = LEXICON / "rules.csv") -> "Rules":
        rules = cls()
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if not row["phrase"] or row["phrase"].startswith("#"):
                    continue
                allergens = tuple((a.rstrip("?"), a.endswith("?")) for a in row["allergens"].split("|") if a)
                unknown = {a for a, _ in allergens} - set(ALLERGENS)
                if unknown:
                    raise ValueError(f"rules.csv {row['phrase']!r}: unknown allergen {unknown}")
                rules.by_key[" ".join(words(row["phrase"]))] = Rule(
                    row["phrase"], tuple((g.rstrip("?"), g.endswith("?")) for g in row["group"].split("|") if g),
                    allergens,
                    row["kind"], row["note"] or "")
        return rules

    def tags(self, canonical: str) -> IngredientTags:
        ws, i, fired = words(canonical), 0, []
        while i < len(ws):
            for n in range(min(MAX_WORDS, len(ws) - i), 0, -1):
                rule = self.by_key.get(" ".join(ws[i:i + n]))
                if rule:
                    fired.append(rule)
                    i += n
                    break
            else:
                i += 1
        definite = {g for r in fired for g, may in r.groups if not may}
        group = next((g for g in GROUP_PRIORITY if g in definite), "")
        possible = frozenset(g for r in fired for g, may in r.groups if may) - definite
        allergens: dict[str, str] = {}
        rank = {"direct": 0, "hidden": 1, "possible": 2}
        for r in fired:
            for a, may in r.allergens:
                kind = "possible" if may else (r.kind or "direct")
                if a not in allergens or rank[kind] < rank[allergens[a]]:
                    allergens[a] = kind
        return IngredientTags(group, possible, allergens, tuple(r.phrase for r in fired))


@cache
def default_rules() -> Rules:
    return Rules.from_csv()


@dataclass(frozen=True)
class RecipeTags:
    allergens: tuple[str, ...]  # definite, in ALLERGENS order: the hard filter
    allergens_may: tuple[str, ...]  # possible only (not also definite)
    ingredients_norm: tuple[str, ...]
    diet_flags: tuple[str, ...]
    diet_may: tuple[str, ...]  # flags that hold only because possible tags were left out
    has_unknown: bool
    unknown_lines: int
    free_of_lines: int  # lines where an "X-free" mention removed a tag (D6b)


@dataclass(frozen=True)
class Line:
    canonicals: tuple[str, ...]
    free: frozenset[str] = frozenset()


def _diet(groups: set[str], codes: set[str]) -> list[str]:
    if groups & ANIMAL or codes & ANIMAL_ALLERGENS:
        return []
    if groups & NOT_VEGAN or codes & NOT_VEGAN_ALLERGENS:
        return ["vegetarian"]
    return ["vegetarian", "vegan"]


def tag_recipe(lines: list, tags: dict[str, IngredientTags]) -> RecipeTags:
    """lines: Line per raw line (a plain list of canonicals counts as a Line with nothing free)."""
    lines = [ln if isinstance(ln, Line) else Line(tuple(ln)) for ln in lines]
    definite, possible, groups, groups_may = set(), set(), set(), set()
    removed = 0
    for ln in lines:
        line_removed = False
        for c in ln.canonicals:
            t = tags.get(c)
            if t is None:
                continue
            for a, kind in t.allergens.items():
                if a in ln.free:
                    line_removed = True
                elif kind == "possible":
                    possible.add(a)
                else:
                    definite.add(a)
            if t.group:
                if f"group:{t.group}" in ln.free:
                    line_removed = True
                else:
                    groups.add(t.group)
            groups_may |= {g for g in t.possible_groups if f"group:{g}" not in ln.free}
        removed += line_removed
    possible -= definite
    flags = _diet(groups, definite)
    strict = _diet(groups | groups_may, definite | possible)
    found = {c for ln in lines for c in ln.canonicals}
    unknown = sum(1 for ln in lines if not ln.canonicals)
    return RecipeTags(tuple(a for a in ALLERGENS if a in definite), tuple(a for a in ALLERGENS if a in possible),
                      tuple(sorted(found)), tuple(flags), tuple(f for f in flags if f not in strict),
                      unknown > 0, unknown, removed)
