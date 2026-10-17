"""Data passed between pipeline stages. M1's output follows A3_ke_hoach_build.md 6.1, plus `remove` (Thy, M3:
the user can lift a constraint in words) and `clarify` (an ambiguous word the assistant must ask about)."""

from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal["search", "refine", "ask_detail", "out_of_scope", "chitchat", "patient_info"]  # patient_info: MV3
Scope = Literal["session", "turn", "patient"]  # patient: from the record, not lifted by a chat message (MV3)
Limits = dict[str, tuple[str, float]]  # chunk column -> (max | min, per-serving value), ADR-0007
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
    nutrient_limits: Limits = Field(default_factory=dict)  # from a patient record: filtered in M4
    nutrient_soft: Limits = Field(default_factory=dict)  # from a patient record: ranked in M5, never filtered

    def is_empty(self) -> bool:
        return not (self.allergens_exclude or self.ingredients_exclude or self.ingredients_include or self.diet
                    or self.max_total_minutes or self.max_calories or self.category or self.nutrient_limits
                    or self.nutrient_soft)

    def hard(self) -> bool:
        """Constraints the filter must enforce (an empty set needs no checker in M6)."""
        return bool(self.allergens_exclude or self.ingredients_exclude or self.diet or self.nutrient_limits)


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
    needs_record_context: bool = False  # patient sessions only: the question needs a context node (V2)
    notes: list[str] = Field(default_factory=list)  # post-processing decisions, for the trace


class StateItem(BaseModel):
    type: Literal["allergen", "ingredient_exclude", "ingredient_include", "diet", "max_total_minutes",
                  "max_calories", "category", "nutrient", "nutrient_soft"]
    value: str  # nutrient / nutrient_soft: "<column><=<value>" or "<column>>=<value>"
    scope: Scope
    source: Literal["dialogue", "patient"] = "dialogue"
    evidence: list[dict] = Field(default_factory=list)  # patient items: node_id, entry_id, text


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
            elif it.type in {"nutrient", "nutrient_soft"}:
                col, op, value = parse_limit(it.value)
                (c.nutrient_limits if it.type == "nutrient" else c.nutrient_soft)[col] = (op, value)
        return c


def limit_value(column: str, op: str, value: float) -> str:
    return f"{column}{'<=' if op == 'max' else '>='}{value!r}"


def parse_limit(text: str) -> tuple[str, str, float]:
    for sign, op in (("<=", "max"), (">=", "min")):
        if sign in text:
            col, value = text.split(sign, 1)
            return col, op, float(value)
    raise ValueError(f"not a nutrient limit: {text!r}")


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
    nutrients: dict[str, float | None] = Field(default_factory=dict)  # per serving, the constrained columns (MV3)


class Verification(BaseModel):
    verified: bool
    citations: list[int] = Field(default_factory=list)
    removed: list[int] = Field(default_factory=list)  # cited ids outside the context or breaking a constraint
    regenerated: bool = False
    flags: list[str] = Field(default_factory=list)  # patient checks (MV3): text:<constraint>, node:<id>
    bad_nodes: list[str] = Field(default_factory=list)  # [H:..] ids not in the patient's tree
