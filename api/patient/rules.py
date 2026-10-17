"""Load the rule tables in data/rules/ (spec section 4). Code only reads them; a malformed file is an error.

MV1 needs the P7 lists: which Results organizers enter the tree (include_loinc.csv), which are sensitive
(exclude_loinc.csv) and which other codes are sensitive (exclude_codes.csv). MV2 adds the mapping tables.
"""

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

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
    mode: str  # filter | warn
    source: str


def load_condition_nutrient(folder: Path = RULES_DIR) -> list[NutrientRule]:
    out = []
    for r in read("condition_nutrient.csv", ["condition_codes", "label", "nutrient", "op", "daily_value", "unit",
                                             "mode", "source"], folder):
        if r["nutrient"] not in NUTRIENTS:
            raise RuleError(f"condition_nutrient.csv: unknown nutrient {r['nutrient']!r}")
        if r["op"] not in {"max", "min", ""} or r["mode"] not in {"filter", "warn"}:
            raise RuleError(f"condition_nutrient.csv: bad op/mode in {r}")
        if r["mode"] == "filter" and (not r["op"] or not r["daily_value"]):
            raise RuleError(f"condition_nutrient.csv: a filter rule needs op and value: {r}")
        out.append(NutrientRule(tuple(c.strip() for c in r["condition_codes"].split(";")), r["label"], r["nutrient"],
                                r["op"] or None, float(r["daily_value"]) if r["daily_value"] else None, r["unit"],
                                r["mode"], r["source"]))
    return out
