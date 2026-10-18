"""Data passed between the patient-record steps (docs/plan/A3_vectorless_ho_so.md 5.2).

Nothing here holds a name, address, race, ethnicity or file name: a PatientRecord is the record after P2-P7.
"""

from dataclasses import asdict, dataclass, field, replace
from datetime import date
from typing import Literal

Source = Literal["sample", "generated"]
NodeKind = Literal["root", "fixed", "context"]


# ---- C-CDA entries (api/patient/ccda.py reads them) -----------------------------------------------------------

@dataclass(frozen=True)
class Allergy:
    entry_id: str  # act/id/@root
    kind_code: str | None  # observation/value/@code: 414285001 food, 419199007 substance, ...
    kind_display: str | None
    substance_code: str | None  # SNOMED
    substance_display: str | None
    reactions: tuple[str, ...]
    severity: str | None
    active: bool


@dataclass(frozen=True)
class Problem:
    entry_id: str
    code: str | None  # SNOMED
    display: str | None
    suffix: str
    active: bool


@dataclass(frozen=True)
class Medication:
    entry_id: str
    code: str | None  # RxNorm
    code_system: str | None
    display: str | None
    active: bool


@dataclass(frozen=True)
class Observation:
    entry_id: str | None
    loinc: str | None
    display: str | None
    value: str | None
    unit: str | None
    when: date | None


@dataclass(frozen=True)
class Organizer:
    entry_id: str | None
    loinc: str | None
    display: str | None
    when: date | None
    observations: tuple[Observation, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Encounter:
    entry_id: str | None
    code: str | None  # SNOMED
    display: str | None
    when: date | None


# ---- after P2-P7 -----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class PatientRecord:
    patient_id: str
    source: Source
    sex: str | None
    age_years: int | None
    record_date: date
    deceased: bool
    allergies: tuple[Allergy, ...]  # in force (P2), every kind: MV2 keeps the food ones (P3)
    problems: tuple[Problem, ...]  # in force (P2) and (disorder) (P4)
    medications: tuple[Medication, ...]  # in use (P5)
    vitals: tuple[Observation, ...]  # latest per LOINC (P6)
    results: tuple[Organizer, ...]  # allow-listed organizers only (P7, include_loinc.csv)
    encounters: tuple[Encounter, ...]  # minus excluded codes (P7)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    node_id: str  # "allergies", "meds.active", "results.2025"...
    entry_id: str  # C-CDA id/@root of the source entry
    text: str  # short description, e.g. "Shellfish (substance) – angioedema, Moderate"


@dataclass(frozen=True)
class PatientNode:
    node_id: str
    parent_id: str | None
    kind: NodeKind
    title: str
    summary: str | None  # context nodes only (V1c)
    facts: list[dict]  # structured facts, already filtered by P2-P7
    entry_ids: list[str]
    summary_source: str | None = None  # template | llm


@dataclass(frozen=True)
class PatientProfile:
    """V3 output: the constraints a patient's record implies, each with its evidence (spec 5.2)."""
    patient_id: str
    allergens_exclude: frozenset[str]
    ingredients_exclude: frozenset[str]  # canonical names
    nutrient_limits: dict[str, tuple[str, float]]  # chunk column -> (op, per-serving limit), e.g. sodium_mg: (max, 666.67)
    warnings: list[str]  # Vietnamese, shown to the user
    unmapped: list[str]  # substances / conditions with no rule, for a reviewer
    evidence: dict[str, list[Evidence]]  # "allergen:wheat", "ingredient:grapefruit", "nutrient:sodium_mg", "warning:..."
    ruleset_version: str
    mode: str  # direct | vectorless | vectorless_nofixed | vector
    nutrient_soft: dict[str, tuple[str, float]] = field(default_factory=dict)  # preferred, not filtered (ADR-0007)

    def to_dict(self) -> dict:
        return {"patient_id": self.patient_id, "allergens_exclude": sorted(self.allergens_exclude),
                "ingredients_exclude": sorted(self.ingredients_exclude),
                "nutrient_limits": {k: list(v) for k, v in sorted(self.nutrient_limits.items())},
                "nutrient_soft": {k: list(v) for k, v in sorted(self.nutrient_soft.items())},
                "warnings": list(self.warnings), "unmapped": list(self.unmapped),
                "evidence": {k: [asdict(e) for e in v] for k, v in sorted(self.evidence.items())},
                "ruleset_version": self.ruleset_version, "mode": self.mode}

    @classmethod
    def from_dict(cls, d: dict) -> "PatientProfile":
        return cls(d["patient_id"], frozenset(d["allergens_exclude"]), frozenset(d["ingredients_exclude"]),
                   {k: (v[0], float(v[1])) for k, v in d["nutrient_limits"].items()}, list(d["warnings"]),
                   list(d["unmapped"]), {k: [Evidence(**e) for e in v] for k, v in d["evidence"].items()},
                   d["ruleset_version"], d["mode"],
                   {k: (v[0], float(v[1])) for k, v in d.get("nutrient_soft", {}).items()})


def constraint_ids(profile: PatientProfile) -> list[str]:
    """The ids the UI names a record constraint by (stable across turns; the profile's evidence keys):
    allergen:<group>, ingredient:<name>, nutrient:<column>, soft:<column>."""
    return ([f"allergen:{a}" for a in sorted(profile.allergens_exclude)]
            + [f"ingredient:{i}" for i in sorted(profile.ingredients_exclude)]
            + [f"nutrient:{c}" for c in sorted(profile.nutrient_limits)]
            + [f"soft:{c}" for c in sorted(profile.nutrient_soft)])


def without(profile: PatientProfile, lifted: set[str]) -> PatientProfile:
    """The profile in force in a session: the constraints the user lifted with confirmation (MV5) taken out, with
    their evidence. M2, M4, M6 and M7 all read this one, so a lifted constraint is gone everywhere at once."""
    if not lifted:
        return profile

    def keep(prefix: str, key: str) -> bool:
        return f"{prefix}:{key}" not in lifted
    return replace(profile,
                   allergens_exclude=frozenset(a for a in profile.allergens_exclude if keep("allergen", a)),
                   ingredients_exclude=frozenset(i for i in profile.ingredients_exclude if keep("ingredient", i)),
                   nutrient_limits={c: v for c, v in profile.nutrient_limits.items() if keep("nutrient", c)},
                   nutrient_soft={c: v for c, v in profile.nutrient_soft.items() if keep("soft", c)},
                   evidence={k: v for k, v in profile.evidence.items() if k not in lifted})
