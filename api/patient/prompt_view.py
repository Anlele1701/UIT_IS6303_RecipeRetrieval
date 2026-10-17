"""What of a patient node a model may see: allow-listed content only (Thy, gate MV1; ADR-0006).

An exclusion list can always miss something (MV1 found drug-abuse codes no LOINC list caught), so a prompt gets
only what a rule table lets through. The tree in the DB keeps everything; evidence still points at entry ids.

    allergies        food allergies that have an allergy_substance.csv row
    problems.active  conditions named by condition_nutrient.csv (not its "unmapped" rows)
    meds.active      medications a drug_food.csv row matches
    vitals.latest    LOINC codes in prompt_vitals.csv
    results.<year>   organizers (already allow-listed by include_loinc.csv at read time)
    encounters.<y>   the generic class (encounter_class.csv) and the month; never the visit's name
"""

from .models import PatientNode
from .rules import RuleSet

FOOD_ALLERGY = "414285001"


def encounter_class(rs: RuleSet, code: str | None) -> str:
    return rs.encounter_class.get(code or "", "other")


def visible_facts(node: PatientNode, rs: RuleSet) -> list[dict]:
    nid, facts = node.node_id, node.facts
    if node.kind == "root":
        return [{"sex": f.get("sex"), "age_years": f.get("age_years")} for f in facts]
    if nid == "allergies":
        return [{"substance": f.get("substance"), "reactions": f.get("reactions"), "severity": f.get("severity")}
                for f in facts if f.get("kind_code") == FOOD_ALLERGY and f.get("substance_code") in rs.allergy]
    if nid == "problems.active":
        allowed = rs.condition_codes()
        return [{"display": f.get("display")} for f in facts if f.get("code") in allowed]
    if nid == "meds.active":
        return [{"display": f.get("display")} for f in facts
                if any(d.match in (f.get("display") or "").lower() for d in rs.drug)]
    if nid == "vitals.latest":
        return [{"display": f.get("display"), "value": f.get("value"), "unit": f.get("unit"), "date": f.get("date")}
                for f in facts if f.get("loinc") in rs.prompt_vitals]
    if nid.startswith("results."):
        return [{"display": f.get("display"), "date": f.get("date"), "observations": f.get("observations")}
                for f in facts]
    if nid.startswith("encounters."):
        return [{"class": encounter_class(rs, f.get("code")), "month": (f.get("date") or "")[:7]} for f in facts]
    return []  # an unknown node shows nothing


def prompt_view(node: PatientNode, rs: RuleSet, with_summary: bool = True) -> dict:
    view = {"node_id": node.node_id, "title": node.title, "facts": visible_facts(node, rs)}
    if with_summary and node.summary:
        view["summary"] = node.summary
    return view
