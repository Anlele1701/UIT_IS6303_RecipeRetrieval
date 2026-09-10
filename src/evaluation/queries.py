"""
Constructed query + ground-truth set. See docs/03_DATASET.md §6.5.

The dataset (ANDREEEWW/recipe-with-images) has no native retrieval
ground truth, so the query/relevance set here is built by the project
team and must be saved to a versioned file so all retrieval methods in
docs/08_EVALUATION.md are evaluated against the identical set.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from src.data.loader import Recipe


@dataclass
class EvalQuery:
    query_id: int
    query_text: str
    source_recipe_idx: int          # recipe the query was derived from
    relevant_recipe_ids: list[int]  # includes source_recipe_idx at minimum


def generate_queries_from_descriptions(recipes: list[Recipe], n: int, seed: int = 42) -> list[EvalQuery]:
    """
    Placeholder query-generation strategy (method (b) in docs/03_DATASET.md
    §6.5): treat the recipe's own `description` as a stand-in query, since
    it is a short, natural-language string.

    This is a simple, reproducible baseline generator — NOT a validated
    ground truth. TODO: replace/augment with manual or LLM-paraphrased
    queries and manual spot-checking before reporting real results,
    per docs/03_DATASET.md §6.5.
    """
    import random

    rng = random.Random(seed)
    candidates = [r for r in recipes if r.description]
    sampled = rng.sample(candidates, min(n, len(candidates)))

    queries = []
    for qid, recipe in enumerate(sampled):
        queries.append(
            EvalQuery(
                query_id=qid,
                query_text=recipe.description,
                source_recipe_idx=recipe.recipe_idx,
                relevant_recipe_ids=[recipe.recipe_idx],
            )
        )
    return queries


def save_queries(queries: list[EvalQuery], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(q) for q in queries], f, indent=2, ensure_ascii=False)


def load_queries(path: str) -> list[EvalQuery]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [EvalQuery(**item) for item in raw]
