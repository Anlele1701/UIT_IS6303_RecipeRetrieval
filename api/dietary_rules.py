"""Dietary Rule Engine: a patient's active conditions -> Filters for the recipe search.

Pure code: no database, no LLM, no environment reads. The rules live in dietary_rules.json and
every number in a Filter comes from there. A condition is matched by SNOMED code.

    plan = derive_diet_plan(profile, rules, filterable_nutrients(), config.MEALS_PER_DAY)
    params = SearchParams(q=query, strategy=strategy, **plan.filters)

Guidelines are per day and recipes are per serving, so a daily limit is divided by the number of
meals per day and rounded DOWN to one decimal (these are ceilings; rounding up could let a
too-large Recipe through). When several conditions limit the same nutrient the smallest limit wins.

A limit on a nutrient the search cannot Filter yet lands in `unapplied_limits`, never silently
dropped. A condition we know is diet-relevant but cannot turn into a limit (gout, kidney disease)
lands in `unsupported_conditions`, with the reason.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal
from uuid import UUID

from . import filters

# recipe_nutrition columns a rule may name; a typo in the rule file fails at load.
NUTRIENTS = frozenset({
    "calories", "calories_from_fat", "fat_g", "saturated_fat_g", "carbohydrates_g", "sugars_g",
    "dietary_fiber_g", "protein_g", "cholesterol_mg", "sodium_mg", "calcium_mg", "iron_mg",
    "magnesium_mg", "potassium_mg", "folate_mcg", "thiamin_mg", "niacin_mg", "vitamin_a_iu",
    "vitamin_c_mg",
})
RULE_STATUSES = ("proposed", "reviewed")


def filterable_nutrients() -> frozenset[str]:
    """Nutrients the search can Filter on today: Filter columns of `chunk` that are also nutrition columns."""
    return frozenset(filters.RANGE_COLUMNS) & NUTRIENTS


class RuleFileError(ValueError):
    pass


# ---------------------------------------------------------------------------
# The rule book
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Limit:
    nutrient: str
    op: str  # only "max" for now
    daily: float


@dataclass(frozen=True)
class Rule:
    rule_id: str
    label: str
    snomed_codes: frozenset[str]
    limits: tuple[Limit, ...]
    source: str
    status: str
    unsupported_reason: str | None = None


@dataclass(frozen=True)
class RuleBook:
    rules: tuple[Rule, ...]

    def for_code(self, code: str) -> list[Rule]:
        return [r for r in self.rules if code in r.snomed_codes]


RULE_KEYS = {"rule_id", "label", "snomed_codes", "limits", "source", "status", "unsupported_reason"}
LIMIT_KEYS = {"nutrient", "op", "daily"}  # no "when": lab-based limits are not implemented, so refuse them


def parse_rules(data: dict) -> RuleBook:
    """Validate a decoded rule file. Any problem raises RuleFileError naming the rule."""
    if data.get("version") != 1:
        raise RuleFileError(f"unsupported rule file version {data.get('version')!r}")
    rules, seen = [], set()
    for raw in data.get("rules", []):
        rid = raw.get("rule_id")
        where = f"rule {rid!r}"
        if not isinstance(rid, str) or not rid:
            raise RuleFileError("a rule has no rule_id")
        if rid in seen:
            raise RuleFileError(f"{where}: duplicate rule_id")
        seen.add(rid)
        extra = set(raw) - RULE_KEYS
        if extra:
            raise RuleFileError(f"{where}: unknown keys {sorted(extra)}")
        codes = raw.get("snomed_codes")
        if not codes or not all(isinstance(c, str) and c.isdigit() for c in codes):
            raise RuleFileError(f"{where}: snomed_codes must be a non-empty list of digit strings")
        if raw.get("status") not in RULE_STATUSES:
            raise RuleFileError(f"{where}: status must be one of {RULE_STATUSES}")
        if not raw.get("source") or not raw.get("label"):
            raise RuleFileError(f"{where}: label and source are required")
        limits, nutrients = [], set()
        for lim in raw.get("limits", []):
            if set(lim) != LIMIT_KEYS:
                raise RuleFileError(f"{where}: a limit needs exactly {sorted(LIMIT_KEYS)}, got {sorted(lim)}")
            if lim["op"] != "max":
                raise RuleFileError(f"{where}: only op 'max' is supported, got {lim['op']!r}")
            daily = lim["daily"]
            if isinstance(daily, bool) or not isinstance(daily, (int, float)) or daily <= 0:
                raise RuleFileError(f"{where}: daily must be a positive number, got {daily!r}")
            if lim["nutrient"] not in NUTRIENTS:
                raise RuleFileError(f"{where}: unknown nutrient {lim['nutrient']!r}")
            if lim["nutrient"] in nutrients:
                raise RuleFileError(f"{where}: nutrient {lim['nutrient']!r} limited twice")
            nutrients.add(lim["nutrient"])
            limits.append(Limit(lim["nutrient"], lim["op"], float(daily)))
        reason = raw.get("unsupported_reason")
        if not limits and not reason:
            raise RuleFileError(f"{where}: no limits, so it needs an unsupported_reason")
        if limits and reason:
            raise RuleFileError(f"{where}: has limits, so it must not have an unsupported_reason")
        rules.append(Rule(rid, raw["label"], frozenset(codes), tuple(limits), raw["source"], raw["status"], reason))
    if not rules:
        raise RuleFileError("the rule file has no rules")
    return RuleBook(tuple(rules))


def load_rules(path: str | Path) -> RuleBook:
    return parse_rules(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchedCondition:
    code: str
    description: str
    since: date


@dataclass
class AppliedLimit:
    """One rule's limit on one nutrient and the conditions that triggered it."""
    rule_id: str
    label: str
    nutrient: str
    daily: float
    per_serving: float
    source: str
    rule_status: str
    conditions: list[MatchedCondition]
    binding: bool = False  # True when this is the limit that ended up as the Filter


@dataclass
class UnsupportedCondition:
    code: str
    description: str
    since: date
    rule_id: str
    reason: str


@dataclass
class DietPlan:
    patient_id: UUID
    status: Literal["filtered", "no_applicable_rules"]
    filters: dict[str, float] = field(default_factory=dict)  # max_<nutrient>, ready for SearchParams
    evidence: list[AppliedLimit] = field(default_factory=list)
    unapplied_limits: list[AppliedLimit] = field(default_factory=list)  # nutrient not filterable yet
    unsupported_conditions: list[UnsupportedCondition] = field(default_factory=list)
    unmatched_conditions: int = 0  # active conditions no rule mentions (mostly social findings)


def floor_tenth(x: float) -> float:
    """Round down to one decimal; the epsilon keeps 500.0 from becoming 499.9 through float error."""
    return math.floor(x * 10 + 1e-9) / 10


def derive_diet_plan(profile, rules: RuleBook, filterable: frozenset[str], meals_per_day: int) -> DietPlan:
    if meals_per_day < 1:
        raise ValueError("meals_per_day must be at least 1")

    matched: dict[str, list[MatchedCondition]] = {}  # rule_id -> conditions, for rules that have limits
    unsupported: list[UnsupportedCondition] = []
    unmatched = 0
    for cond in profile.active_conditions:
        hits = rules.for_code(cond.code)
        if not hits:
            unmatched += 1
        for rule in hits:
            if rule.limits:
                matched.setdefault(rule.rule_id, []).append(MatchedCondition(cond.code, cond.description, cond.since))
            else:
                unsupported.append(UnsupportedCondition(cond.code, cond.description, cond.since, rule.rule_id,
                                                        rule.unsupported_reason))

    applied: list[AppliedLimit] = []
    unapplied: list[AppliedLimit] = []
    for rule in rules.rules:  # rule-file order keeps the output stable
        if rule.rule_id not in matched:
            continue
        for lim in rule.limits:
            item = AppliedLimit(rule.rule_id, rule.label, lim.nutrient, lim.daily,
                                floor_tenth(lim.daily / meals_per_day), rule.source, rule.status,
                                matched[rule.rule_id])
            (applied if lim.nutrient in filterable else unapplied).append(item)

    plan_filters: dict[str, float] = {}
    for nutrient in sorted({a.nutrient for a in applied}):
        group = [a for a in applied if a.nutrient == nutrient]
        strictest = min(a.per_serving for a in group)
        for a in group:
            a.binding = a.per_serving == strictest
        plan_filters[f"max_{nutrient}"] = strictest

    applied.sort(key=lambda a: a.nutrient)
    return DietPlan(profile.patient_id, "filtered" if plan_filters else "no_applicable_rules", plan_filters,
                    applied, unapplied, unsupported, unmatched)
