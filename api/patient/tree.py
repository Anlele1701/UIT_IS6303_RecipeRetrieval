"""V1b: a PatientRecord as a table-of-contents tree (spec 5.3). Deterministic, no model, no I/O.

    patient:<uuid>        root     sex, age (no name)
    ├── allergies         fixed    always present, even when empty: "no allergy" is a fact
    ├── problems.active   fixed
    ├── meds.active       fixed
    ├── vitals.latest     fixed
    ├── results.<year>    context  allow-listed organizers of that year
    └── encounters.<year> context  encounters of that year
A year with no fact left after P7 gets no node. Context summaries are filled by summarize.py.
"""

from collections import defaultdict
from datetime import date

from .models import Encounter, Observation, Organizer, PatientNode, PatientRecord

FIXED = [("allergies", "Allergies"), ("problems.active", "Active problems"), ("meds.active", "Current medications"),
         ("vitals.latest", "Latest vital signs")]


def root_id(record: PatientRecord) -> str:
    return f"patient:{record.patient_id}"


def _d(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _obs(o: Observation, with_id: bool = True) -> dict:
    out = {"loinc": o.loinc, "display": o.display, "value": o.value, "unit": o.unit, "date": _d(o.when)}
    return {"entry_id": o.entry_id, **out} if with_id else out


def _organizer(o: Organizer) -> dict:
    return {"entry_id": o.entry_id, "loinc": o.loinc, "display": o.display, "date": _d(o.when),
            "observations": [_obs(x, with_id=False) for x in o.observations]}


def _encounter(e: Encounter) -> dict:
    return {"entry_id": e.entry_id, "code": e.code, "display": e.display, "date": _d(e.when)}


def _by_year(items, when) -> dict[int, list]:
    years: dict[int, list] = defaultdict(list)
    for it in items:
        d = when(it)
        if d is not None:
            years[d.year].append(it)
    return years


def _ids(facts: list[dict]) -> list[str]:
    return [f["entry_id"] for f in facts if f.get("entry_id")]


def build_tree(record: PatientRecord) -> list[PatientNode]:
    root = root_id(record)
    fixed_facts = {
        "allergies": [{"entry_id": a.entry_id, "kind_code": a.kind_code, "kind": a.kind_display,
                       "substance_code": a.substance_code, "substance": a.substance_display,
                       "reactions": list(a.reactions), "severity": a.severity} for a in record.allergies],
        "problems.active": [{"entry_id": p.entry_id, "code": p.code, "display": p.display} for p in record.problems],
        "meds.active": [{"entry_id": m.entry_id, "code": m.code, "display": m.display} for m in record.medications],
        "vitals.latest": [_obs(o) for o in record.vitals],
    }
    nodes = [PatientNode(node_id=root, parent_id=None, kind="root",
                         title=f"Patient ({record.sex or '?'}, {record.age_years if record.age_years is not None else '?'})",
                         summary=None, facts=[{"sex": record.sex, "age_years": record.age_years,
                                               "record_date": record.record_date.isoformat()}], entry_ids=[])]
    for node_id, title in FIXED:
        facts = fixed_facts[node_id]
        nodes.append(PatientNode(node_id=node_id, parent_id=root, kind="fixed", title=title, summary=None,
                                 facts=facts, entry_ids=_ids(facts)))
    for prefix, title, items, when, fact in [
            ("results", "Lab results", record.results, lambda o: o.when, _organizer),
            ("encounters", "Encounters", record.encounters, lambda e: e.when, _encounter)]:
        for year, group in sorted(_by_year(items, when).items()):
            facts = [fact(x) for x in sorted(group, key=lambda x: (when(x), x.entry_id or ""))]
            nodes.append(PatientNode(node_id=f"{prefix}.{year}", parent_id=root, kind="context",
                                     title=f"{title} {year}", summary=None, facts=facts, entry_ids=_ids(facts)))
    return nodes
