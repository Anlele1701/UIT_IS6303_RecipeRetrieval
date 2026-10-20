"""Load the rule tables in data/rules/ (spec section 4). Code only reads them; a malformed file is an error.

MV1 needs the P7 lists: which Results organizers enter the tree (include_loinc.csv), which are sensitive
(exclude_loinc.csv) and which other codes are sensitive (exclude_codes.csv). MV2 adds the mapping tables.
"""

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

from .. import config
from . import dietary_rules

RULES_DIR = Path(__file__).resolve().parents[2] / "data" / "rules"


class RuleError(ValueError):
    pass


def read(name: str, required: list[str], folder: Path = RULES_DIR) -> list[dict]:
    path = folder / name
    if not path.exists():
        raise RuleError(f"missing rule file {path}")
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    missing = [c for c in required if rows and c not in rows[0]]
    if missing:
        raise RuleError(f"{name}: missing columns {missing}")
    return rows


def sha256(name: str, folder: Path = RULES_DIR) -> str:
    return hashlib.sha256((folder / name).read_bytes()).hexdigest()


@dataclass(frozen=True)
class P7Rules:
    include_loinc: dict[str, str]  # organizer LOINC -> display
    exclude_loinc: dict[str, str]  # organizer LOINC -> category (mental_health, substance_use, violence, death)
    exclude_codes: dict[tuple[str, str], str]  # (applies_to, code) -> category

    def organizer_class(self, loinc: str | None) -> str:
        """include | exclude | not_relevant: only allow-listed organizers enter the tree."""
        if loinc in self.exclude_loinc:
            return "exclude"
        return "include" if loinc in self.include_loinc else "not_relevant"

    def excluded(self, applies_to: str, code: str | None) -> str | None:
        """The P7 category of a problem, encounter or medication code, or None if it may be kept."""
        return self.exclude_codes.get((applies_to, code or ""))


P7_FILES = ["include_loinc.csv", "exclude_loinc.csv", "exclude_codes.csv"]


def load_p7(folder: Path = RULES_DIR) -> P7Rules:
    inc = {r["loinc"]: r["display"] for r in read("include_loinc.csv", ["loinc", "display"], folder)}
    exc = {r["loinc"]: r["category"] for r in read("exclude_loinc.csv", ["loinc", "category"], folder)}
    overlap = sorted(set(inc) & set(exc))
    if overlap:
        raise RuleError(f"LOINC in both include and exclude lists: {overlap}")
    codes = {}
    for r in read("exclude_codes.csv", ["code_system", "code", "applies_to", "category"], folder):
        if r["applies_to"] not in {"problem", "encounter", "medication"}:
            raise RuleError(f"exclude_codes.csv: unknown applies_to {r['applies_to']!r}")
        codes[(r["applies_to"], r["code"])] = r["category"]
    return P7Rules(inc, exc, codes)


# ---- condition -> nutrient limits (spec 4.2) ------------------------------------------------------------------

NUTRIENTS = {"sodium_mg", "sugar_pct_kcal", "sat_fat_pct_kcal", "fiber_per_1000kcal", "protein_g_per_kg",
             "potassium_mg", "phosphorus_mg"}


@dataclass(frozen=True)
class NutrientRule:
    conditions: tuple[str, ...]  # SNOMED codes; ("*",) = every patient
    label: str
    nutrient: str
    op: str | None  # max | min | None (warn only)
    daily_value: float | None
    unit: str
    mode: str  # filter (hard, in the index) | soft (ranking + warning, ADR-0007) | warn | unmapped
    source: str


def load_condition_nutrient(folder: Path = RULES_DIR) -> list[NutrientRule]:
    out = []
    for r in read("condition_nutrient.csv", ["condition_codes", "label", "nutrient", "op", "daily_value", "unit",
                                             "mode", "source"], folder):
        if r["mode"] == "unmapped":  # a diet-relevant condition with no rule yet: listed for review, nothing else
            out.append(NutrientRule(tuple(c.strip() for c in r["condition_codes"].split(";")), r["label"], "", None,
                                    None, "", "unmapped", r["source"]))
            continue
        if r["nutrient"] not in NUTRIENTS:
            raise RuleError(f"condition_nutrient.csv: unknown nutrient {r['nutrient']!r}")
        if r["op"] not in {"max", "min", ""} or r["mode"] not in {"filter", "soft", "warn"}:
            raise RuleError(f"condition_nutrient.csv: bad op/mode in {r}")
        if r["mode"] in {"filter", "soft"} and (not r["op"] or not r["daily_value"]):
            raise RuleError(f"condition_nutrient.csv: a {r['mode']} rule needs op and value: {r}")
        out.append(NutrientRule(tuple(c.strip() for c in r["condition_codes"].split(";")), r["label"], r["nutrient"],
                                r["op"] or None, float(r["daily_value"]) if r["daily_value"] else None, r["unit"],
                                r["mode"], r["source"]))
    return out


# ---- the whole rule set ----------------------------------------------------------------------------------------

ALLERGENS = ["milk", "egg", "fish", "crustacean_shellfish", "tree_nuts", "peanut", "wheat", "soy", "sesame"]
# nutrient -> chunk column it filters on; None = recipe_nutrition has no such column (the rule becomes a warning)
NUTRIENT_COLUMN = {"sodium_mg": "sodium_mg", "sugar_pct_kcal": "sugar_pct_kcal", "sat_fat_pct_kcal": "sat_fat_pct_kcal",
                   "fiber_per_1000kcal": "fiber_per_1000kcal", "protein_g_per_kg": "protein_g",
                   "potassium_mg": "potassium_mg", "phosphorus_mg": None}
RULE_SET_FILES = ["allergy_substance.csv", "condition_nutrient.csv", "drug_food.csv", "encounter_class.csv",
                  "prompt_vitals.csv", *P7_FILES]


@dataclass(frozen=True)
class AllergyRule:
    code: str
    display: str
    allergens: tuple[str, ...]
    extra_ingredients: tuple[str, ...]


@dataclass(frozen=True)
class DrugRule:
    match: str  # lowercase substring of the RxNorm display name
    action: str  # exclude | warn
    targets: tuple[str, ...]  # canonical ingredients
    message_vi: str
    source: str


@dataclass(frozen=True)
class RuleSet:
    allergy: dict[str, AllergyRule]
    nutrient: list[NutrientRule]
    drug: list[DrugRule]
    encounter_class: dict[str, str]
    prompt_vitals: frozenset[str]
    p7: P7Rules
    version: str
    log: tuple[str, ...] = ()  # rules turned into warnings at load time, and why
    diet: dietary_rules.RuleBook | None = None  # Dietary Rule Engine's book (hard limits); None = CSV limits only

    def condition_codes(self) -> set[str]:
        """Every SNOMED code a nutrient rule names: the allow-list of problems a prompt may show."""
        return {c for r in self.nutrient if r.mode != "unmapped" for c in r.conditions if c != "*"}


def _split(s: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in (s or "").split(";") if x.strip())


def ruleset_version(folder: Path = RULES_DIR) -> str:
    h = hashlib.sha256()
    for name in RULE_SET_FILES:
        h.update(name.encode() + b"\0" + (folder / name).read_bytes())
    # the Dietary Rule Engine's book and its meals per day change the hard limits, so they are part of the version
    h.update(b"dietary_rules.json\0" + dietary_rules.RULES_FILE.read_bytes() + b"\0" + str(config.MEALS_PER_DAY).encode())
    return h.hexdigest()[:12]


def load_rules(folder: Path = RULES_DIR) -> RuleSet:
    """Every rule table, checked on its own (no DB). validate_against_db checks names and columns."""
    allergy = {}
    for r in read("allergy_substance.csv", ["snomed_code", "display", "allergens", "extra_ingredients_exclude"], folder):
        bad = [a for a in _split(r["allergens"]) if a not in ALLERGENS]
        if bad:
            raise RuleError(f"allergy_substance.csv: unknown allergen group {bad} for {r['snomed_code']}")
        allergy[r["snomed_code"]] = AllergyRule(r["snomed_code"], r["display"], _split(r["allergens"]),
                                                _split(r["extra_ingredients_exclude"]))
    log = []
    nutrient = []
    for n in load_condition_nutrient(folder):
        if n.mode in {"filter", "soft"} and NUTRIENT_COLUMN.get(n.nutrient) is None:  # spec 4.4.5
            log.append(f"{n.label} {n.nutrient}: no column in recipe_nutrition, filter -> warn")
            n = NutrientRule(n.conditions, n.label, n.nutrient, n.op, n.daily_value, n.unit, "warn", n.source)
        nutrient.append(n)
    drug = []
    for r in read("drug_food.csv", ["match", "action", "target", "message_vi", "source"], folder):
        if r["action"] not in {"exclude", "warn"}:
            raise RuleError(f"drug_food.csv: unknown action {r['action']!r}")
        if not r["source"].strip():
            raise RuleError(f"drug_food.csv: {r['match']} has no source")  # spec 4.3: every row has a source
        drug.append(DrugRule(r["match"].strip().lower(), r["action"], _split(r["target"]), r["message_vi"], r["source"]))
    enc = {r["snomed_code"]: r["class"] for r in read("encounter_class.csv", ["snomed_code", "class"], folder)}
    vitals = frozenset(r["loinc"] for r in read("prompt_vitals.csv", ["loinc"], folder))
    return RuleSet(allergy, nutrient, drug, enc, vitals, load_p7(folder), ruleset_version(folder), tuple(log),
                   dietary_rules.load_rules())


def validate_against_db(rs: RuleSet, conn) -> None:
    """Raise when a rule names an ingredient the ingredient table lacks, or a filter column chunk lacks."""
    names = sorted({n for a in rs.allergy.values() for n in a.extra_ingredients} | {n for d in rs.drug for n in d.targets})
    known = {r[0] for r in conn.execute("SELECT canonical_name FROM ingredient WHERE canonical_name = ANY(%s)", [names])}
    missing = [n for n in names if n not in known]
    if missing:
        raise RuleError(f"ingredients not in the ingredient table: {missing}")
    cols = {r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'chunk' AND table_schema = 'public'")}
    absent = sorted({NUTRIENT_COLUMN[n.nutrient] for n in rs.nutrient if n.mode in {"filter", "soft"}} - cols)
    if absent:
        raise RuleError(f"filter columns missing on chunk (migration 006?): {absent}")
