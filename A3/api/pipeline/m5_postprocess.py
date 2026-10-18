"""M5 post-retrieval: rerank the fused Chunks, group them by Recipe (parent), keep the top k, best first.

Grouping avoids the "blinkered chunk" effect [R08]: the generator sees whole Recipes, not stray steps. A Recipe
scores as its best Chunk. The context card carries only what the answer needs (focus mode [R09]), including the
possible allergens so the answer can warn about them; the best Recipe goes first ([S14]).

Patient sessions (MV3, ADR-0007): soft nutrient limits never filter; after rerank and grouping, Recipes meeting
more soft limits move ahead (stable sort, so the rerank order holds within each group), then the top k is taken.
Cards then carry the constrained nutrient values, so M6 can say "natri 540 mg/khẩu phần" and M7 can check them.
"""

import psycopg

from .. import config
from ..patient.nutrition import COLUMN_SQL, meets
from ..retrieval import Candidate, rerank
from .schemas import Limits, RecipeCard


def top_recipes(query: str, chunks: list[Candidate], scorer, k: int = config.CONTEXT_RECIPES,
                use_rerank: bool = True, soft: Limits | None = None,
                values: dict[int, dict[str, float | None]] | None = None) -> list[tuple[int, float]]:
    ranked = rerank(query, chunks, scorer) if use_rerank and chunks else chunks
    best: dict[int, float] = {}
    for c in ranked:  # ranked best first, so the first Chunk seen is the Recipe's best
        best.setdefault(c.recipe_id, c.score)
    items = list(best.items())
    if soft:
        items.sort(key=lambda it: -soft_met((values or {}).get(it[0], {}), soft))  # stable: rerank order within ties
    return items[:k]


def soft_met(vals: dict[str, float | None], soft: Limits) -> int:
    """How many soft limits a Recipe keeps (an unknown value does not count)."""
    return sum(bool(meets(vals.get(col), op, limit)) for col, (op, limit) in soft.items())


def nutrient_values(conn: psycopg.Connection, recipe_ids: list[int], columns) -> dict[int, dict[str, float | None]]:
    """Per-serving values of the given chunk columns, computed from recipe_nutrition (same SQL as migration 006)."""
    cols = sorted(set(columns))
    if not recipe_ids or not cols:
        return {}
    exprs = ", ".join(f"({COLUMN_SQL[c]})::real" for c in cols)  # names checked against COLUMN_SQL
    rows = conn.execute(f"SELECT r.id, {exprs} FROM recipe r LEFT JOIN recipe_nutrition n ON n.recipe_id = r.id "
                        "WHERE r.id = ANY(%s)", [list(recipe_ids)]).fetchall()
    return {r[0]: dict(zip(cols, r[1:])) for r in rows}


def cards(conn: psycopg.Connection, ranked: list[tuple[int, float]], nutrients=()) -> list[RecipeCard]:
    if not ranked:
        return []
    ids = [rid for rid, _ in ranked]
    rows = {r[0]: r for r in conn.execute(
        """SELECT r.id, r.title, r.total_minutes, coalesce(t.allergens, '{}'), coalesce(t.allergens_may, '{}'),
                  coalesce(t.diet_flags, '{}'), coalesce(t.diet_may, '{}'), r.description, coalesce(t.ingredients_norm, '{}'),
                  (SELECT array_agg(line ORDER BY position) FROM recipe_ingredient i WHERE i.recipe_id = r.id)
           FROM recipe r LEFT JOIN recipe_tag t ON t.recipe_id = r.id WHERE r.id = ANY(%s)""", [ids]).fetchall()}
    values = nutrient_values(conn, ids, nutrients) if nutrients else {}
    return [RecipeCard(id=rid, title=rows[rid][1], total_minutes=rows[rid][2], allergens=rows[rid][3],
                       allergens_may=rows[rid][4], diet_flags=rows[rid][5], diet_may=rows[rid][6], score=round(score, 4),
                       summary=(rows[rid][7] or "")[:400], ingredients=rows[rid][9] or [],
                       ingredients_norm=rows[rid][8], nutrients=values.get(rid, {}))
            for rid, score in ranked if rid in rows]


def recipe_detail(conn: psycopg.Connection, recipe_id: int, nutrients=()) -> tuple[RecipeCard | None, str]:
    """ask_detail: the card and the full directions of one Recipe."""
    found = cards(conn, [(recipe_id, 0.0)], nutrients)
    if not found:
        return None, ""
    directions = conn.execute("SELECT directions FROM recipe WHERE id = %s", [recipe_id]).fetchone()[0]
    return found[0], directions
