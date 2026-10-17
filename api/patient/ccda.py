"""Read a Synthea C-CDA file: sections by LOINC, entries, and which ones are in force (spec 2.1-2.3).

Pure functions over an lxml tree; nothing here calls a model or the DB. "Today" is the document's own
effectiveTime, never the clock, so a record reads the same on every run. Identity fields (name, address,
race, ethnicity) are never read (P7): the only header fields used are the patient id, sex and birth time.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from lxml import etree

NS = {"c": "urn:hl7-org:v3"}

# Sections, identified by section/code/@code (not title, not templateId: templateIds repeat in Synthea files)
ALLERGIES = "48765-2"
MEDICATIONS = "10160-0"
PROBLEMS = "11450-4"
VITALS = "8716-3"
RESULTS = "30954-2"
ENCOUNTERS = "46240-8"
SURGERIES = "47519-4"
IMMUNIZATIONS = "11369-6"
SOCIAL_HISTORY = "29762-2"
FUNCTIONAL_STATUS = "47420-5"
PLAN_OF_CARE = "18776-5"
DROPPED_SECTIONS = {SOCIAL_HISTORY, FUNCTIONAL_STATUS}  # P7: counted, never read

FOOD_ALLERGY = "414285001"  # observation/value: "Allergy to food"; the only kind that yields a food constraint
SUBSTANCE_ALLERGY = "419199007"  # "Allergy to substance" (environment, latex, drugs...)

_SUFFIX = re.compile(r"\(([^()]+)\)\s*$")


def _x(el, path: str) -> list:
    return el.xpath(path, namespaces=NS)


def _first(el, path: str) -> str | None:
    found = _x(el, path)
    return str(found[0]) if found else None


def parse(path: str | Path) -> etree._ElementTree:
    """The document tree. Opened as bytes so lxml reads the declared encoding (Windows-safe)."""
    with open(path, "rb") as f:
        return etree.parse(f)


def ts(value: str | None) -> date | None:
    """An HL7 timestamp ("20260825154939") as a date; None when missing or unreadable."""
    if not value or len(value) < 8 or not value[:8].isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


# ---- header ---------------------------------------------------------------------------------------------------

def record_date(doc) -> date:
    d = ts(_first(doc, "/c:ClinicalDocument/c:effectiveTime/@value"))
    if d is None:
        raise ValueError("ClinicalDocument/effectiveTime is missing")
    return d


def _patient_role(doc):
    return _x(doc, "/c:ClinicalDocument/c:recordTarget/c:patientRole")[0]


def patient_id(doc) -> str:
    """The Synthea uuid (patientRole/id/@extension); the file name carries the same uuid."""
    return _first(_patient_role(doc), "c:id/@extension")


def sex(doc) -> str | None:
    return _first(_patient_role(doc), "c:patient/c:administrativeGenderCode/@code")


def age_years(doc, today: date) -> int | None:
    born = ts(_first(_patient_role(doc), "c:patient/c:birthTime/@value"))
    if born is None:
        return None
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def software_name(doc) -> str | None:
    return _first(doc, "/c:ClinicalDocument/c:author/c:assignedAuthor/c:assignedAuthoringDevice/c:softwareName/text()")


# ---- sections -------------------------------------------------------------------------------------------------

def sections(doc) -> dict[str, list]:
    """LOINC code -> the sections with that code (a list: nothing guarantees a code appears once)."""
    out: dict[str, list] = {}
    for s in _x(doc, "//c:section"):
        code = _first(s, "c:code/@code")
        if code:
            out.setdefault(code, []).append(s)
    return out


def section_title(section) -> str:
    return (_first(section, "c:title/text()") or "").strip()


def semantic_suffix(display: str | None) -> str:
    """The SNOMED semantic tag at the end of a display name: "... (disorder)" -> "disorder"; "" if none."""
    m = _SUFFIX.search(display or "")
    return m.group(1).strip() if m else ""


# ---- in force (spec 2.2) --------------------------------------------------------------------------------------

def _has_high(el) -> bool:
    """effectiveTime/high with a value. A high that is only a nullFlavor does not end anything."""
    return bool(_x(el, "c:effectiveTime/c:high[@value]"))


def allergy_active(act) -> bool:
    return _first(act, "c:statusCode/@code") == "active" and not _has_high(act)


def problem_active(act) -> bool:
    return _first(act, "c:statusCode/@code") == "active" and not _has_high(act)


def med_active(sa, today: date) -> bool:
    """statusCode is ignored (Synthea marks every medication completed). In use: no high, a nullFlavor high
    ("UNK"), or a high on or after the record date."""
    highs = _x(sa, "c:effectiveTime/c:high")
    if not highs:
        return True
    value = highs[0].get("value")
    if value is None:
        return highs[0].get("nullFlavor") is not None
    end = ts(value)
    return end is not None and end >= today


# ---- entries --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Allergy:
    entry_id: str  # act/id/@root
    kind_code: str | None  # observation/value/@code: FOOD_ALLERGY, SUBSTANCE_ALLERGY, ...
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


def allergies(section) -> list[Allergy]:
    out = []
    for act in _x(section, "c:entry/c:act"):
        obs = _x(act, "c:entryRelationship/c:observation")
        o = obs[0] if obs else act
        entity = "c:participant/c:participantRole/c:playingEntity/c:code"
        sev = [v for r in _x(o, "c:entryRelationship/c:observation[c:code/@code='SEV']")
               for v in _x(r, "c:value/@displayName")]
        out.append(Allergy(
            entry_id=_first(act, "c:id/@root"), kind_code=_first(o, "c:value/@code"),
            kind_display=_first(o, "c:value/@displayName"), substance_code=_first(o, f"{entity}/@code"),
            substance_display=_first(o, f"{entity}/@displayName"),
            reactions=tuple(str(v) for v in _x(o, "c:entryRelationship[@typeCode='MFST']/c:observation/c:value/@displayName")),
            severity=str(sev[0]) if sev else None, active=allergy_active(act)))
    return out


def problems(section) -> list[Problem]:
    out = []
    for act in _x(section, "c:entry/c:act"):
        display = _first(act, "c:entryRelationship/c:observation/c:value/@displayName")
        out.append(Problem(entry_id=_first(act, "c:id/@root"),
                           code=_first(act, "c:entryRelationship/c:observation/c:value/@code"),
                           display=display, suffix=semantic_suffix(display), active=problem_active(act)))
    return out


def medications(section, today: date) -> list[Medication]:
    out = []
    for sa in _x(section, "c:entry/c:substanceAdministration"):
        code = "c:consumable/c:manufacturedProduct/c:manufacturedMaterial/c:code"
        out.append(Medication(entry_id=_first(sa, "c:id/@root"), code=_first(sa, f"{code}/@code"),
                              code_system=_first(sa, f"{code}/@codeSystem"), display=_first(sa, f"{code}/@displayName"),
                              active=med_active(sa, today)))
    return out


def _observation(o) -> Observation:
    return Observation(entry_id=_first(o, "c:id/@root"), loinc=_first(o, "c:code/@code"),
                       display=_first(o, "c:code/@displayName"), value=_first(o, "c:value/@value"),
                       unit=_first(o, "c:value/@unit"),
                       when=ts(_first(o, "c:effectiveTime/@value") or _first(o, "c:effectiveTime/c:low/@value")))


def vitals(section) -> list[Observation]:
    """Every measurement: Synthea puts all dates into one organizer."""
    return [_observation(o) for o in _x(section, "c:entry/c:organizer/c:component/c:observation")]


def latest_by_loinc(observations: list[Observation]) -> dict[str, Observation]:
    """For each LOINC code, the observation with the latest date (ties: the later one in the file)."""
    out: dict[str, Observation] = {}
    for o in observations:
        if not o.loinc:
            continue
        cur = out.get(o.loinc)
        if cur is None or (o.when or date.min) >= (cur.when or date.min):
            out[o.loinc] = o
    return out


def organizers(section) -> list[Organizer]:
    """Diagnostic Results: lab panels and questionnaires, one organizer each."""
    out = []
    for org in _x(section, "c:entry/c:organizer"):
        when = ts(_first(org, "c:effectiveTime/@value") or _first(org, "c:effectiveTime/c:low/@value"))
        out.append(Organizer(entry_id=_first(org, "c:id/@root"), loinc=_first(org, "c:code/@code"),
                             display=_first(org, "c:code/@displayName"), when=when,
                             observations=tuple(_observation(o) for o in _x(org, "c:component/c:observation"))))
    return out
