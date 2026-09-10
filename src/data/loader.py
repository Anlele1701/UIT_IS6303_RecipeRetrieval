"""
Dataset loading for ANDREEEWW/recipe-with-images.

Real schema (verified via HF datasets-server, see docs/03_DATASET.md):
    image        : PIL Image
    name         : str
    ingredients  : str  (raw multi-line recipe text)
    description  : str

There is no native `id` field, so a stable `recipe_idx` is assigned here
at subset-build time and must be reused everywhere downstream (indexes,
evaluation, UI) instead of re-deriving indices later.
"""

from dataclasses import dataclass
from typing import Optional

from src.config import CONFIG


@dataclass
class Recipe:
    recipe_idx: int
    name: str
    ingredients: str
    description: str
    image: object  # PIL.Image.Image at runtime; left untyped to avoid a hard PIL import here


def load_subset(
    split: str = CONFIG.corpus_split,
    subset_size: int = CONFIG.subset_size,
    seed: int = CONFIG.seed,
) -> list[Recipe]:
    """
    Load a deterministic subset of the dataset as a list of Recipe objects
    with a stable `recipe_idx` assigned in shuffle order.

    NOTE: requires the `datasets` package. Not executed/tested as part of
    this scaffold — see docs/03_DATASET.md §6.3 for subset-size rationale.
    """
    from datasets import load_dataset

    ds = load_dataset(
        CONFIG.dataset_name,
        revision=CONFIG.dataset_revision,
        split=split,
    )
    ds = ds.shuffle(seed=seed)

    if subset_size is not None and subset_size < len(ds):
        ds = ds.select(range(subset_size))

    recipes: list[Recipe] = []
    for idx, row in enumerate(ds):
        recipes.append(
            Recipe(
                recipe_idx=idx,
                name=row.get("name", "") or "",
                ingredients=row.get("ingredients", "") or "",
                description=row.get("description", "") or "",
                image=row.get("image"),
            )
        )
    return recipes


def get_recipe_by_idx(recipes: list[Recipe], recipe_idx: int) -> Optional[Recipe]:
    """Lookup helper — recipes list is expected to be index-aligned with recipe_idx."""
    if 0 <= recipe_idx < len(recipes):
        r = recipes[recipe_idx]
        if r.recipe_idx == recipe_idx:
            return r
    # Fallback to linear search if list is not index-aligned (e.g. filtered subset).
    for r in recipes:
        if r.recipe_idx == recipe_idx:
            return r
    return None
