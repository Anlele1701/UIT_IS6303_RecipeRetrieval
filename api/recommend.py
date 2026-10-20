"""POST /recommend: a patient and a question in, safe Recipes and an explanation out.

    patient (SQL) -> Dietary Rule Engine -> Filters -> Hybrid retrieval -> Chunks grouped into Recipes
        -> nutrition re-check against recipe_nutrition -> LLM explanation

Only code decides what is safe. The Filters come from the rule book, the search applies them inside
the index, and every returned Recipe is checked again against recipe_nutrition before it is shown. The
LLM only writes the explanation: its failure leaves the Recipes in place, and its numbers are checked
against the data it was given. Filters are never relaxed to find more Recipes.

The embedder, reranker and LLM are passed in so tests can replace them.
"""

import logging
import re
import time
from collections.abc import Callable
from contextlib import contextmanager
from uuid import UUID

import psycopg
from pydantic import BaseModel, ConfigDict, Field

from . import allergens, config, dietary_rules, patients, retrieval
from .filters import SearchParams
from .llm import LLMError

log = logging.getLogger("recommend")

# Shown for every Recipe; the Filter nutrients are added on top when they are not in this list.
DISPLAY_NUTRIENTS = ("calories", "protein_g", "fat_g", "saturated_fat_g", "carbohydrates_g", "sugars_g", "sodium_mg")
MAX_INGREDIENT_LINES = 40  # shown per Recipe; the allergy screen reads them all


# ---------------------------------------------------------------------------
# Request and response
# ---------------------------------------------------------------------------


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    query: str = Field(min_length=1, max_length=500, description="What the patient wants to eat")
    strategy: str = Field(description="Chunking strategy to search; see /strategies")
    k: int = Field(config.DEFAULT_K, ge=1, le=config.RECOMMEND_MAX_K, description="Recipes to return")
    explain: bool = Field(True, description="Ask the LLM for an explanation; false returns the Recipes only")


class LimitCheck(BaseModel):
    nutrient: str
    limit: float
    value: float | None
    ok: bool


class BestChunk(BaseModel):
    kind: str
    position: int
    text: str
    rerank_score: float | None = None
    sparse_rank: int | None = None
    dense_rank: int | None = None


class RecipeResult(BaseModel):
    rank: int
    recipe_id: int
    title: str
    category: str
    url: str
    rating: float
    total_minutes: int | None
    servings: int
    nutrition: dict[str, float | None]  # per serving
    ingredients: list[str]
    best_chunk: BestChunk
    checks: list[LimitCheck]  # one per applied Filter, read from recipe_nutrition


class AllergyExclusion(BaseModel):
    recipe_id: int
    title: str
    allergen: str
    matched: str  # the word that matched
    where: str  # "title" or the ingredient line


class AllergyCheck(BaseModel):
    checked: list[str]  # allergens screened for (food allergies with a keyword list)
    unchecked: list[str]  # food allergies in the record that have no keyword list: NOT screened
    excluded: list[AllergyExclusion]


class RecommendResponse(BaseModel):
    patient: patients.PatientProfile
    query: str
    strategy: str
    k: int
    diet_plan: dietary_rules.DietPlan
    recipes: list[RecipeResult]
    dropped_by_nutrition_check: list[int]  # recipe_ids that the index returned but recipe_nutrition rejected
    allergy_check: AllergyCheck
    warnings: list[str]
    answer: str | None
    answer_error: str | None
    unverified_numbers: list[str]  # numbers in the answer that are not in the data the LLM was given
    timings_ms: dict[str, float]


# ---------------------------------------------------------------------------
# Steps (plain functions, testable without a server)
# ---------------------------------------------------------------------------


def group_recipes(hits: list[retrieval.Candidate]) -> list[retrieval.Candidate]:
    """One Chunk per Recipe: the best-ranked one, in rank order. `hits` is already ordered best first."""
    seen: set[int] = set()
    out = []
    for h in hits:
        if h.recipe_id not in seen:
            seen.add(h.recipe_id)
            out.append(h)
    return out


def nutrient_columns(plan_filters: dict[str, float]) -> list[str]:
    """Columns to read from recipe_nutrition. Names are checked against the known list: they go into SQL text."""
    wanted = list(DISPLAY_NUTRIENTS) + [k.removeprefix("max_") for k in plan_filters]
    return [c for c in dict.fromkeys(wanted) if c in dietary_rules.NUTRIENTS]


def fetch_recipes(conn: psycopg.Connection, recipe_ids: list[int], columns: list[str]) -> dict[int, dict]:
    """Recipe details, nutrition per serving and ingredient lines, keyed by recipe_id."""
    if not recipe_ids:
        return {}
    cols = ", ".join(f"n.{c}" for c in columns)
    rows = conn.execute(
        f"""SELECT r.id, r.title, c.name, r.url, r.rating, r.total_minutes, r.servings, {cols}
            FROM recipe r JOIN category c ON c.id = r.category_id
            LEFT JOIN recipe_nutrition n ON n.recipe_id = r.id
            WHERE r.id = ANY(%s)""", [recipe_ids]).fetchall()
    out = {}
    for rid, title, category, url, rating, minutes, servings, *values in rows:
        out[rid] = {"title": title, "category": category, "url": url, "rating": float(rating),
                    "total_minutes": minutes, "servings": servings,
                    "nutrition": {c: (float(v) if v is not None else None) for c, v in zip(columns, values)},
                    "ingredients": []}
    for rid, line in conn.execute(
            "SELECT recipe_id, line FROM recipe_ingredient WHERE recipe_id = ANY(%s) ORDER BY recipe_id, position",
            [recipe_ids]).fetchall():
        out[rid]["ingredients"].append(line)  # all of them: the allergy screen reads every line
    return out


def nutrition_checks(nutrition: dict[str, float | None], plan_filters: dict[str, float]) -> list[LimitCheck]:
    """Each applied Filter against the Recipe's real value. A missing value fails (the index does the same)."""
    out = []
    for key, limit in plan_filters.items():
        value = nutrition.get(key.removeprefix("max_"))
        out.append(LimitCheck(nutrient=key.removeprefix("max_"), limit=limit, value=value,
                              ok=value is not None and value <= limit))
    return out


def allergy_screen(book: allergens.AllergenBook, profile: patients.PatientProfile
                   ) -> tuple[list[allergens.Allergen], list[str]]:
    """The allergens to screen for, and the food allergies that have no keyword list (so cannot be screened)."""
    screened, unchecked = [], []
    for a in profile.active_allergies:
        if a.category != "food":
            continue
        allergen = book.for_code(a.code)
        if allergen is None:
            unchecked.append(a.description)
        elif allergen not in screened:
            screened.append(allergen)
    return screened, unchecked


def allergy_exclusions(screened: list[allergens.Allergen], recipe_id: int, d: dict) -> list[AllergyExclusion]:
    """Why this Recipe must not be shown to the patient; empty when it passes every screened allergen.
    A Recipe with no ingredient lines cannot be checked, so it fails (as a missing nutrient does)."""
    if not screened:
        return []
    if not d["ingredients"]:
        return [AllergyExclusion(recipe_id=recipe_id, title=d["title"], allergen=", ".join(a.name for a in screened),
                                 matched="", where="no ingredient lines to check")]
    return [AllergyExclusion(recipe_id=recipe_id, title=d["title"], allergen=m.allergen, matched=m.term, where=m.where)
            for a in screened for m in allergens.find_matches(a, d["title"], d["ingredients"])[:1]]


def warnings_for(plan: dietary_rules.DietPlan) -> list[str]:
    out = []
    if not plan.filters:
        out.append("No dietary Filter applies to this patient, so the results are not restricted by any limit.")
    for u in plan.unapplied_limits:
        out.append(f"The {u.nutrient} limit ({u.per_serving} per serving, from '{u.label}') could not be applied: "
                   f"the search has no Filter on {u.nutrient} yet.")
    by_rule: dict[str, list[dietary_rules.UnsupportedCondition]] = {}
    for c in plan.unsupported_conditions:
        by_rule.setdefault(c.rule_id, []).append(c)
    for group in by_rule.values():  # one line per rule, not per condition
        names = "; ".join(dict.fromkeys(c.description for c in group))
        out.append(f"{names}: {group[0].reason}")
    return out


def build_messages(query: str, plan: dietary_rules.DietPlan, recipes: list[RecipeResult]) -> list[dict]:
    applied = "\n".join(
        f"- {e.nutrient} <= {e.per_serving} per serving ({', '.join(c.description for c in e.conditions)})"
        for e in plan.evidence) or "- none"
    not_applied = "\n".join(f"- {u.nutrient} <= {u.per_serving} per serving ({u.label})" for u in plan.unapplied_limits)
    lines = []
    for r in recipes:
        values = ", ".join(f"{k} {v:g}" for k, v in r.nutrition.items() if v is not None)
        lines.append(f"{r.rank}. {r.title} ({r.category}): {values} per serving")
    user = (f"Question: {query}\n\n"
            f"Dietary limits that were applied to the search:\n{applied}\n\n"
            + (f"Limits that could NOT be applied:\n{not_applied}\n\n" if not_applied else "")
            + "Recipes (each one is already verified to meet the applied limits):\n" + "\n".join(lines)
            + "\n\nFor each recipe, write one or two sentences on why it suits the question and how it meets the "
              "applied limits, quoting the numbers above. If some limits could not be applied, say so in one "
              "final sentence.")
    system = ("You explain recipe suggestions to a person on a restricted diet. Use ONLY the facts you are given. "
              "Never mention a recipe or a number that is not in the data, and give no other medical advice. "
              "Answer in the language of the question. Be brief.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def unverified_numbers(answer: str, plan: dietary_rules.DietPlan, recipes: list[RecipeResult]) -> list[str]:
    """Numbers in the answer that match nothing the LLM was given. Whole numbers up to 10 are ignored
    (list numbering, 'one or two'); a whole number matches within 0.5 and a decimal within 0.05."""
    allowed: list[float] = []
    for e in plan.evidence + plan.unapplied_limits:
        allowed += [e.per_serving, e.daily]
    for r in recipes:
        allowed += [v for v in r.nutrition.values() if v is not None]
        allowed += [r.servings, r.rating, r.rank] + ([r.total_minutes] if r.total_minutes is not None else [])
    out = []
    for token in NUMBER_RE.findall(answer):
        v = float(token.replace(",", ""))
        whole = "." not in token
        if whole and v <= 10:
            continue
        tolerance = 0.5 if whole else 0.05
        if not any(abs(v - a) <= tolerance for a in allowed):
            out.append(token)
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------------------
# The orchestrator
# ---------------------------------------------------------------------------


def recommend(conn: psycopg.Connection, req: RecommendRequest, *, rules: dietary_rules.RuleBook,
              allergen_book: allergens.AllergenBook,
              embed: Callable[[str], str], scorer: Callable[[str, list[str]], list[float]],
              explain: Callable[[list[dict]], str] | None, search=None, fetch=None) -> RecommendResponse:
    """Run the pipeline. Raises patients.PatientNotFound for an unknown patient; anything the embedder raises
    propagates (the route turns it into a 503). `search` and `fetch` default to Hybrid retrieval and the DB."""
    search = search or retrieval.hybrid
    fetch = fetch or fetch_recipes
    timings: dict[str, float] = {}

    @contextmanager
    def stage(name: str):
        t = time.perf_counter()
        try:
            yield
        finally:
            timings[name] = round((time.perf_counter() - t) * 1000, 1)

    started = time.perf_counter()
    with stage("profile"):
        profile = patients.get_profile(conn, req.patient_id)
    with stage("rules"):
        plan = dietary_rules.derive_diet_plan(profile, rules, dietary_rules.filterable_nutrients(),
                                              config.MEALS_PER_DAY)
    warnings = warnings_for(plan)
    screened, unchecked = allergy_screen(allergen_book, profile)
    warnings += [f"The food allergy '{d}' cannot be screened (no keyword list for it), so recipes were not "
                 "checked for it." for d in unchecked]

    with stage("embed"):
        qvec = embed(req.query)
    # More Chunks when allergies will remove some Recipes; the reranker already scores that many.
    chunks = config.MAX_K if screened else config.RECOMMEND_CHUNKS
    # SearchParams rejects an unknown key, so a bad Filter name fails here instead of searching unfiltered.
    params = SearchParams(q=req.query, strategy=req.strategy, k=chunks, **plan.filters)
    with stage("search"):
        hits = search(conn, params, qvec, scorer)
    candidates = group_recipes(hits)

    with stage("assemble"):
        # Every candidate is read (at most one per Chunk asked for) so rejected ones still leave k.
        details = fetch(conn, [c.recipe_id for c in candidates], nutrient_columns(plan.filters))
        recipes: list[RecipeResult] = []
        dropped: list[int] = []
        excluded: list[AllergyExclusion] = []
        for c in candidates:
            if len(recipes) == req.k:
                break
            d = details.get(c.recipe_id)
            if d is None:
                continue
            found = allergy_exclusions(screened, c.recipe_id, d)
            if found:
                excluded += found
                continue
            checks = nutrition_checks(d["nutrition"], plan.filters)
            if not all(ch.ok for ch in checks):
                dropped.append(c.recipe_id)
                continue
            chunk_text = c.content.partition("\n")[2]  # content is "<title>\n<text>"
            recipes.append(RecipeResult(
                rank=len(recipes) + 1, recipe_id=c.recipe_id, title=d["title"], category=d["category"],
                url=d["url"], rating=d["rating"], total_minutes=d["total_minutes"], servings=d["servings"],
                nutrition=d["nutrition"], ingredients=d["ingredients"][:MAX_INGREDIENT_LINES], checks=checks,
                best_chunk=BestChunk(kind=c.kind, position=c.position, text=chunk_text,
                                     rerank_score=c.rerank_score, sparse_rank=c.sparse_rank,
                                     dense_rank=c.dense_rank)))
    if excluded:
        names = ", ".join(dict.fromkeys(e.allergen for e in excluded))
        n = len({e.recipe_id for e in excluded})
        warnings.append(f"Removed {n} Recipe(s) that contain an ingredient the patient is allergic to ({names}).")
    if dropped:
        warnings.append(f"Removed {len(dropped)} Recipe(s) that the search returned but the nutrition re-check "
                        "rejected.")
        log.error("nutrition re-check rejected recipes %s for patient %s; Filters %s",
                  dropped, req.patient_id, plan.filters)
    if not recipes:
        warnings.append("No Recipe satisfies every Filter and allergy screen for this query. Nothing was relaxed.")

    answer = answer_error = None
    unverified: list[str] = []
    if req.explain and recipes and explain is not None:
        with stage("explain"):
            try:
                answer = explain(build_messages(req.query, plan, recipes))
                unverified = unverified_numbers(answer, plan, recipes)
            except LLMError as e:
                answer_error = str(e)
        if unverified:
            warnings.append("The explanation quotes numbers that are not in the data: " + ", ".join(unverified))

    timings["total"] = round((time.perf_counter() - started) * 1000, 1)
    log.info("recommend patient=%s conditions=%d filters=%s chunks=%d recipes=%d dropped=%d allergy_excluded=%d explained=%s ms=%s",
             req.patient_id, len(profile.active_conditions), plan.filters, len(hits), len(recipes), len(dropped),
             len({e.recipe_id for e in excluded}),
             answer is not None, timings)
    return RecommendResponse(
        patient=profile, query=req.query, strategy=req.strategy, k=req.k, diet_plan=plan, recipes=recipes,
        dropped_by_nutrition_check=dropped,
        allergy_check=AllergyCheck(checked=[a.name for a in screened], unchecked=unchecked, excluded=excluded),
        warnings=warnings, answer=answer, answer_error=answer_error,
        unverified_numbers=unverified, timings_ms=timings)
