"""Persist the deterministic Hugging Face subset and local image files."""

from pathlib import Path

from src.config import CONFIG
from src.data.loader import Recipe


def _save_image(recipe: Recipe) -> str | None:
    if recipe.image is None:
        return None

    relative_path = Path(CONFIG.data_cache_dir) / "images" / f"{recipe.recipe_idx}.jpg"
    relative_path.parent.mkdir(parents=True, exist_ok=True)
    image = recipe.image
    if getattr(image, "mode", "RGB") != "RGB":
        image = image.convert("RGB")
    image.save(relative_path, format="JPEG", quality=90)
    return str(relative_path)


def upsert_raw_recipes(connection, recipes: list[Recipe]) -> int:
    rows = [
        (
            recipe.recipe_idx,
            recipe.name,
            recipe.ingredients,
            recipe.description,
            _save_image(recipe),
            CONFIG.corpus_split,
            CONFIG.dataset_revision,
            CONFIG.seed,
        )
        for recipe in recipes
    ]

    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO raw.recipes (
                recipe_idx,
                name,
                ingredients,
                description,
                image_path,
                dataset_split,
                dataset_revision,
                subset_seed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (recipe_idx) DO UPDATE SET
                name = EXCLUDED.name,
                ingredients = EXCLUDED.ingredients,
                description = EXCLUDED.description,
                image_path = EXCLUDED.image_path,
                dataset_split = EXCLUDED.dataset_split,
                dataset_revision = EXCLUDED.dataset_revision,
                subset_seed = EXCLUDED.subset_seed,
                updated_at = now()
            """,
            rows,
        )

    # recipe_idx is contiguous for the deterministic subset built by loader.py.
    connection.execute(
        "DELETE FROM raw.recipes WHERE recipe_idx >= %s",
        (len(recipes),),
    )
    return len(rows)
