"""Data passed between pipeline stages. M1's output follows A3_ke_hoach_build.md 6.1, plus `remove` (Thy, M3:
the user can lift a constraint in words) and `clarify` (an ambiguous word the assistant must ask about)."""

from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal["search", "refine", "ask_detail", "out_of_scope", "chitchat"]
Scope = Literal["session", "turn"]
ALLERGENS = ["milk", "egg", "fish", "crustacean_shellfish", "tree_nuts", "peanut", "wheat", "soy", "sesame"]
DIETS = ["vegetarian", "vegan"]


class Constraints(BaseModel):
    allergens_exclude: list[str] = Field(default_factory=list)
    ingredients_exclude: list[str] = Field(default_factory=list)  # canonical names
    ingredients_include: list[str] = Field(default_factory=list)  # soft signal only (6.3)
    diet: str | None = None
    max_total_minutes: int | None = None
    max_calories: float | None = None
    category: str | None = None

    def is_empty(self) -> bool:
        return not (self.allergens_exclude or self.ingredients_exclude or self.ingredients_include or self.diet
                    or self.max_total_minutes or self.max_calories or self.category)

    def hard(self) -> bool:
        """Constraints the filter must enforce (an empty set needs no checker in M6)."""
        return bool(self.allergens_exclude or self.ingredients_exclude or self.diet)


class Removal(BaseModel):
    allergens: list[str] = Field(default_factory=list)
    ingredients: list[str] = Field(default_factory=list)
    diet: bool = False
    max_total_minutes: bool = False


class Understanding(BaseModel):
    intent: Intent = "search"
    lang: Literal["vi", "en"] = "en"
    query_en: str = ""
    constraints: Constraints = Field(default_factory=Constraints)
    session_scope: list[str] = Field(default_factory=list)  # constraint types the user made lasting ("từ giờ")
    remove: Removal = Field(default_factory=Removal)
    ref_recipe: int | None = None  # ask_detail: 1-based position in the last answer, or a Recipe id
    clarify: str | None = None  # a question to ask back instead of searching
    notes: list[str] = Field(default_factory=list)  # post-processing decisions, for the trace


class StateItem(BaseModel):
    type: Literal["allergen", "ingredient_exclude", "ingredient_include", "diet", "max_total_minutes",
                  "max_calories", "category"]
    value: str
    scope: Scope


class SessionState(BaseModel):
    items: list[StateItem] = Field(default_factory=list)
    last_recipe_ids: list[int] = Field(default_factory=list)  # Recipes of the last answer, in order
    notices: list[str] = Field(default_factory=list)  # e.g. include/exclude conflicts M2 resolved

    def constraints(self) -> Constraints:
        c = Constraints()
        for it in self.items:
            if it.type == "allergen":
                c.allergens_exclude.append(it.value)
            elif it.type == "ingredient_exclude":
                c.ingredients_exclude.append(it.value)
            elif it.type == "ingredient_include":
                c.ingredients_include.append(it.value)
            elif it.type == "diet":
                c.diet = it.value
            elif it.type == "max_total_minutes":
                c.max_total_minutes = int(it.value)
            elif it.type == "max_calories":
                c.max_calories = float(it.value)
            elif it.type == "category":
                c.category = it.value
        return c


class RecipeCard(BaseModel):
    id: int
    title: str
    total_minutes: int | None = None
    allergens: list[str] = Field(default_factory=list)  # definite tags
    allergens_may: list[str] = Field(default_factory=list)  # possible: warn, do not filter
    diet_flags: list[str] = Field(default_factory=list)
    diet_may: list[str] = Field(default_factory=list)
    score: float = 0.0
    summary: str = ""
    ingredients: list[str] = Field(default_factory=list)  # raw lines
    ingredients_norm: list[str] = Field(default_factory=list)  # canonical names: M7 checks, not shown to M6


class Verification(BaseModel):
    verified: bool
    citations: list[int] = Field(default_factory=list)
    removed: list[int] = Field(default_factory=list)  # cited ids outside the context or breaking a constraint
    regenerated: bool = False
