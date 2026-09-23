"""Versioned chunking strategies used by the Postgres indexing pipeline."""

import hashlib
import re
from dataclasses import dataclass

from src.data.loader import Recipe
from src.data.preprocessing import build_searchable_text, normalize_ingredients


@dataclass(frozen=True)
class RecipeChunk:
    recipe_idx: int
    field_name: str
    chunk_index: int
    text: str
    text_hash: str
    token_count: int


def _make_chunk(
    recipe_idx: int,
    text: str,
    *,
    field_name: str = "",
    chunk_index: int = 0,
) -> RecipeChunk:
    normalized = re.sub(r"\s+", " ", text).strip()
    return RecipeChunk(
        recipe_idx=recipe_idx,
        field_name=field_name,
        chunk_index=chunk_index,
        text=normalized,
        text_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        token_count=len(normalized.split()),
    )


# One combined chunk per recipe, varying only which fields go into it.
# The reduced profiles are Ablation D in docs/10_ABLATION_STUDY.md.
FULL_RECIPE_PROFILES = {
    "full_recipe_v1": ("name", "ingredients", "description"),
    "name_only_v1": ("name",),
    "name_ingredients_v1": ("name", "ingredients"),
}


def chunk_recipe(recipe: Recipe, profile_name: str) -> list[RecipeChunk]:
    if profile_name in FULL_RECIPE_PROFILES:
        text = build_searchable_text(recipe, fields=FULL_RECIPE_PROFILES[profile_name])
        return [_make_chunk(recipe.recipe_idx, text)] if text else []

    if profile_name == "field_chunk_v1":
        values = {
            "name": recipe.name.strip(),
            "ingredients": normalize_ingredients(recipe.ingredients),
            "description": recipe.description.strip(),
        }
        return [
            _make_chunk(recipe.recipe_idx, text, field_name=field_name)
            for field_name, text in values.items()
            if text
        ]

    raise ValueError(f"Unknown chunk profile: {profile_name}")


def chunk_recipes(
    recipes: list[Recipe],
    profile_name: str,
) -> list[RecipeChunk]:
    return [
        chunk
        for recipe in recipes
        for chunk in chunk_recipe(recipe, profile_name)
    ]
