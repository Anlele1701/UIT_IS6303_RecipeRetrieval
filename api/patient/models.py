"""Data passed between the patient-record steps (docs/plan/A3_vectorless_ho_so.md 5.2).

Nothing here holds a name, address, race, ethnicity or file name: a PatientRecord is the record after P2-P7.
"""

from dataclasses import asdict, dataclass, field
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
