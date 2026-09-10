"""
Build searchable text from raw recipe fields.

See docs/03_DATASET.md §6.4 for the rationale: `ingredients` is raw
recipe-style text (quantities, units, prep steps, sub-headers like
"Dressing:" or "For serving:"), not a clean list of ingredient nouns,
so it needs light normalization before being used for lexical/dense
retrieval.
"""

import re

from src.data.loader import Recipe


def normalize_ingredients(raw: str) -> str:
    """
    Collapse newlines and sub-header artifacts into plain text.

    This intentionally keeps quantities/units in place — whether to strip
    them is an open question for Ablation D (docs/10_ABLATION_STUDY.md)
    and should be tested experimentally, not decided here.
    """
    if not raw:
        return ""
    text = raw.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_searchable_text(recipe: Recipe, fields: tuple = ("name", "ingredients", "description")) -> str:
    """
    Concatenate the requested fields in a fixed order into one searchable
    string. `fields` lets Ablation D (docs/10_ABLATION_STUDY.md) test
    Name-only / Name+Ingredients / Name+Ingredients+Description without
    duplicating this function.
    """
    parts = []
    for field in fields:
        if field == "ingredients":
            value = normalize_ingredients(recipe.ingredients)
        else:
            value = getattr(recipe, field, "") or ""
        if value:
            parts.append(value)
    return " ".join(parts).strip()


def build_corpus(recipes: list[Recipe], fields: tuple = ("name", "ingredients", "description")) -> list[str]:
    """Index-aligned list of searchable text, one per recipe in `recipes`."""
    return [build_searchable_text(r, fields=fields) for r in recipes]
