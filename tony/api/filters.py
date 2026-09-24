"""Query parameters shared by every search endpoint: the query, k, and the Filters.

Every Filter maps to a column copied onto `chunk` (ADR-0001), so it runs inside
chunk_search_idx before ranking.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from . import config

# chunk column -> type of its min_/max_ bounds
RANGE_COLUMNS = {
    "total_minutes": int, "prep_minutes": int, "cook_minutes": int,
    "rating": float, "rating_count": int, "servings": int,
    "calories": float, "protein_g": float, "fat_g": float,
    "carbohydrates_g": float, "sodium_mg": float,
}


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a misspelled filter is an error, not ignored

    q: str = Field(min_length=1, max_length=500, description="Search text")
    k: int = Field(config.DEFAULT_K, ge=1, le=config.MAX_K, description="Number of Chunks to return")
    category: list[str] = Field(default_factory=list, description="Repeatable; any of these categories")
    kind: list[Literal["summary", "ingredients", "step"]] = Field(
        default_factory=list, description="Repeatable; any of these Chunk kinds")


SearchParams = create_model(
    "SearchParams",
    __base__=_Base,
    **{f"{bound}_{col}": (t | None, Field(None, description=f"{col} {op} value"))
       for col, t in RANGE_COLUMNS.items()
       for bound, op in (("min", ">="), ("max", "<="))},
)


def where_clause(p: _Base) -> tuple[str, list]:
    """SQL conditions (joined with AND) and their parameters, always scoped to the Chunker."""
    conds, params = ["chunker = %s"], [config.CHUNKER]
    if p.category:
        conds.append("category = ANY(%s)")
        params.append(p.category)
    if p.kind:
        conds.append("kind = ANY(%s)")
        params.append(p.kind)
    for col in RANGE_COLUMNS:
        for bound, op in (("min", ">="), ("max", "<=")):
            value = getattr(p, f"{bound}_{col}")
            if value is not None:
                conds.append(f"{col} {op} %s")
                params.append(value)
    return " AND ".join(conds), params
