"""M5 post-retrieval: rerank the fused Chunks, group them by Recipe (parent), keep the top k, best first.

Grouping avoids the "blinkered chunk" effect [R08]: the generator sees whole Recipes, not stray steps. A Recipe
scores as its best Chunk. The context card carries only what the answer needs (focus mode [R09]), including the
possible allergens so the answer can warn about them; the best Recipe goes first ([S14]).
"""

import psycopg

from .. import config
from ..retrieval import Candidate, rerank
from .schemas import RecipeCard


def top_recipes(query: str, chunks: list[Candidate], scorer, k: int = config.CONTEXT_RECIPES,
                use_rerank: bool = True) -> list[tuple[int, float]]:
    ranked = rerank(query, chunks, scorer) if use_rerank and chunks else chunks
    best: dict[int, float] = {}
    for c in ranked:  # ranked best first, so the first Chunk seen is the Recipe's best
        best.setdefault(c.recipe_id, c.score)
    return list(best.items())[:k]


def cards(conn: psycopg.Connection, ranked: list[tuple[int, float]]) -> list[RecipeCard]:
    if not ranked:
        return []
    ids = [rid for rid, _ in ranked]
    rows = {r[0]: r for r in conn.execute(
        """SELECT r.id, r.title, r.total_minutes, coalesce(t.allergens, '{}'), coalesce(t.allergens_may, '{}'),
                  coalesce(t.diet_flags, '{}'), coalesce(t.diet_may, '{}'), r.description,
                  (SELECT array_agg(line ORDER BY position) FROM recipe_ingredient i WHERE i.recipe_id = r.id)
           FROM recipe r LEFT JOIN recipe_tag t ON t.recipe_id = r.id WHERE r.id = ANY(%s)""", [ids]).fetchall()}
    return [RecipeCard(id=rid, title=rows[rid][1], total_minutes=rows[rid][2], allergens=rows[rid][3],
                       allergens_may=rows[rid][4], diet_flags=rows[rid][5], diet_may=rows[rid][6], score=round(score, 4),
                       summary=(rows[rid][7] or "")[:400], ingredients=rows[rid][8] or [])
            for rid, score in ranked if rid in rows]


def recipe_detail(conn: psycopg.Connection, recipe_id: int) -> tuple[RecipeCard | None, str]:
    """ask_detail: the card and the full directions of one Recipe."""
    found = cards(conn, [(recipe_id, 0.0)])
    if not found:
        return None, ""
    directions = conn.execute("SELECT directions FROM recipe WHERE id = %s", [recipe_id]).fetchone()[0]
    return found[0], directions
