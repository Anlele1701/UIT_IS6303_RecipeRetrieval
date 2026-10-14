"""D6-D8: food group and allergens per canonical ingredient (data/lexicon/rules.csv), tags per Recipe.

Rules are phrases matched on a canonical name with the same longest-first scan as D5, so a longer
phrase is an exception for the words inside it ("peanut butter" -> peanut, not milk). A Recipe has
allergen X when any of its lines maps to an ingredient with X (conservative: alternatives in
"butter or margarine" all count). Diet flags (D7):
  vegetarian: no ingredient in an animal group (meat, poultry, fish, shellfish, gelatin) or tagged fish/crustacean
  vegan:      vegetarian and no dairy, egg or honey, and nothing tagged milk or egg
D8: a line with no canonical ingredient is `unknown`; `has_unknown` marks the Recipe. Unknown lines
do not change allergens or diet flags here; the S+Unknown ablation decides what to do with them.
"""

import csv
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from .normalize import LEXICON, MAX_WORDS, words

ALLERGENS = ["milk", "egg", "fish", "crustacean_shellfish", "tree_nuts", "peanut", "wheat", "soy", "sesame"]
ANIMAL = {"meat", "poultry", "fish", "shellfish", "gelatin"}
NOT_VEGAN = ANIMAL | {"dairy", "egg", "honey"}
ANIMAL_ALLERGENS = {"fish", "crustacean_shellfish"}
NOT_VEGAN_ALLERGENS = ANIMAL_ALLERGENS | {"milk", "egg"}
GROUP_PRIORITY = ["meat", "poultry", "fish", "shellfish", "gelatin", "dairy", "egg", "honey", "nonfood"]


@dataclass(frozen=True)
class Rule:
    phrase: str
    group: str
    allergens: tuple[str, ...]
    kind: str
    note: str


@dataclass(frozen=True)
class IngredientTags:
    group: str  # "" when no rule gives one
    allergens: dict[str, str]  # code -> direct | hidden
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
                allergens = tuple(a for a in row["allergens"].split("|") if a)
                unknown = set(allergens) - set(ALLERGENS)
                if unknown:
                    raise ValueError(f"rules.csv {row['phrase']!r}: unknown allergen {unknown}")
                rules.by_key[" ".join(words(row["phrase"]))] = Rule(
                    row["phrase"], row["group"], allergens, row["kind"], row["note"] or "")
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
        groups = {r.group for r in fired if r.group}
        group = next((g for g in GROUP_PRIORITY if g in groups), "")
        allergens: dict[str, str] = {}
        for r in fired:
            for a in r.allergens:
                if allergens.get(a) != "direct":
                    allergens[a] = r.kind or "direct"
        return IngredientTags(group, allergens, tuple(r.phrase for r in fired))


@cache
def default_rules() -> Rules:
    return Rules.from_csv()


@dataclass(frozen=True)
class RecipeTags:
    allergens: tuple[str, ...]  # in ALLERGENS order
    ingredients_norm: tuple[str, ...]
    diet_flags: tuple[str, ...]
    has_unknown: bool
    unknown_lines: int


def tag_recipe(lines: list[list[str]], groups: dict[str, str], allergens: dict[str, dict[str, str]]) -> RecipeTags:
    """lines: the canonical ingredients of each line ([] = unknown); groups/allergens: per canonical."""
    found = {c for line in lines for c in line}
    codes = {a for c in found for a in allergens.get(c, {})}
    used_groups = {groups.get(c, "") for c in found}
    flags = []
    # An allergen tag also rules a diet out: worcestershire (fish), margarine (milk)
    if not used_groups & ANIMAL and not codes & ANIMAL_ALLERGENS:
        flags.append("vegetarian")
        if not used_groups & NOT_VEGAN and not codes & NOT_VEGAN_ALLERGENS:
            flags.append("vegan")
    unknown = sum(1 for line in lines if not line)
    return RecipeTags(tuple(a for a in ALLERGENS if a in codes), tuple(sorted(found)), tuple(flags),
                      unknown > 0, unknown)
