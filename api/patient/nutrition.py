"""Per-serving nutrient values and limits (spec 4.4, ADR-0007).

recipe_nutrition is per serving. A daily limit in mg or g becomes daily * PER_MEAL_FRACTION; a share of energy
(% kcal, g per 1000 kcal) is computed on the Recipe's own calories and is not scaled; a per-kg limit is
value * weight_kg * PER_MEAL_FRACTION. No calories (null or 0) -> the ratio is unknown (null), never 0.
"""

from .. import config
from .rules import NutrientRule

RATIO = {"sat_fat_pct_kcal", "sugar_pct_kcal", "fiber_per_1000kcal"}  # not scaled by the meal fraction

# SQL over recipe_nutrition AS n; null when an input is missing. sugars_g is TOTAL sugars (no free-sugar column).
SQL = {
    "sodium_mg": "n.sodium_mg",
    "sugar_pct_kcal": "n.sugars_g * 4 / nullif(n.calories, 0) * 100",
    "sat_fat_pct_kcal": "n.saturated_fat_g * 9 / nullif(n.calories, 0) * 100",
    "fiber_per_1000kcal": "n.dietary_fiber_g / nullif(n.calories, 0) * 1000",
    "protein_g_per_kg": "n.protein_g",  # compared with a limit already multiplied by the weight
    "potassium_mg": "n.potassium_mg",
}


# chunk column a patient limit names -> the same value over recipe_nutrition AS n (M5 ranking, pass-rate counts)
COLUMN_SQL = {"sodium_mg": SQL["sodium_mg"], "sat_fat_pct_kcal": SQL["sat_fat_pct_kcal"],
              "fiber_per_1000kcal": SQL["fiber_per_1000kcal"], "sugar_pct_kcal": SQL["sugar_pct_kcal"],
              "protein_g": "n.protein_g", "potassium_mg": SQL["potassium_mg"]}


def meets(value: float | None, op: str, limit: float) -> bool | None:
    """Whether a per-serving value keeps a limit; None when the value is unknown."""
    if value is None:
        return None
    return value <= limit if op == "max" else value >= limit


# Columns copied onto chunk by scripts/ingest.py (migration 006), so M4 can filter on them inside the index
DERIVED_COLUMNS = ["sat_fat_pct_kcal", "sugar_pct_kcal", "fiber_per_1000kcal", "potassium_mg"]


def derived_sql(alias: str) -> list[str]:
    """SQL for DERIVED_COLUMNS over recipe_nutrition AS <alias>, in that order; cast to the column type (real)."""
    return [f"({SQL[c].replace('n.', f'{alias}.')})::real" for c in DERIVED_COLUMNS]


def per_serving_limit(rule: NutrientRule, weight_kg: float | None = None,
                      fraction: float = config.PER_MEAL_FRACTION) -> float | None:
    """The limit one serving is held to; None when it cannot be set (warn-only rule, or no weight for g/kg)."""
    if rule.daily_value is None:
        return None
    if rule.nutrient in RATIO:
        return rule.daily_value
    if rule.nutrient == "protein_g_per_kg":
        return None if weight_kg is None else rule.daily_value * weight_kg * fraction
    return rule.daily_value * fraction
