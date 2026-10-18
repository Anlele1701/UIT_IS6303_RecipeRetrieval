"""The narrative input mode (spec 6): what a system sees when it reads only the section tables (<text>) of a C-CDA.

Each section becomes one node, named by its title, whose facts are the table rows with Start, Stop, Description (and
Value for vital signs). No code, no statusCode: which allergy is a food allergy and which medication is still taken
must be worked out from the words and the dates. The Code column is read here only to drop P7 rows before the text
can reach a model (questionnaires, substance use, death...: exclude_loinc.csv, exclude_codes.csv); the dropped
sections (Social History, Functional Status) never appear. Used by the evaluation only (eval_patient.py --input
narrative); production reads the coded entries.
"""

import re
from pathlib import Path

from . import ccda
from .models import PatientNode
from .rules import P7Rules

SECTIONS = [  # (LOINC, node id, kind): the fixed four, then the two the context nodes come from
    (ccda.ALLERGIES, "narrative.allergies", "fixed"), (ccda.MEDICATIONS, "narrative.medications", "fixed"),
    (ccda.PROBLEMS, "narrative.problems", "fixed"), (ccda.VITALS, "narrative.vitals", "fixed"),
    (ccda.RESULTS, "narrative.results", "context"), (ccda.ENCOUNTERS, "narrative.encounters", "context")]
FIXED_IDS = [nid for _, nid, kind in SECTIONS if kind == "fixed"]
_APPLIES = {ccda.PROBLEMS: "problem", ccda.ENCOUNTERS: "encounter", ccda.MEDICATIONS: "medication"}


def _cells(tr) -> list[str]:
    return [re.sub(r"\s+", " ", td.xpath("string()")).strip() for td in tr.xpath("c:td", namespaces=ccda.NS)]


def _date(s: str) -> str:
    return s[:10] if s else ""


def table_rows(section) -> list[dict]:
    """The section table as dicts keyed by its header (Start, Stop, Description, Code, Value)."""
    text = section.xpath("c:text", namespaces=ccda.NS)
    if not text:
        return []
    heads = [h.xpath("string()").strip() for h in text[0].xpath(".//c:thead//c:th", namespaces=ccda.NS)]
    return [dict(zip(heads, _cells(tr))) for tr in text[0].xpath(".//c:tbody/c:tr", namespaces=ccda.NS)]


def p7_drops(code_cell: str, loinc: str, p7: P7Rules) -> bool:
    code = code_cell.split()[-1] if code_cell else ""
    if loinc == ccda.RESULTS:
        return code in p7.exclude_loinc
    return bool(_APPLIES.get(loinc) and p7.excluded(_APPLIES[loinc], code))


def narrative_nodes(path: str | Path, p7: P7Rules) -> tuple[list[PatientNode], str]:
    """The narrative nodes of one record, and its record date (the narrative's 'today', as the document says)."""
    doc = ccda.parse(path)
    secs = ccda.sections(doc)
    root = f"patient:{ccda.patient_id(doc)}"
    nodes = [PatientNode(root, None, "root", "Patient", None, [], [])]
    for loinc, nid, kind in SECTIONS:
        facts = []
        for s in secs.get(loinc, []):
            for row in table_rows(s):
                if p7_drops(row.get("Code", ""), loinc, p7):
                    continue
                fact = {"start": _date(row.get("Start", "")), "stop": _date(row.get("Stop", "")),
                        "description": row.get("Description", "")}
                if row.get("Value"):
                    fact["value"] = row["Value"]
                facts.append(fact)
        title = ccda.section_title(secs[loinc][0]) if secs.get(loinc) else nid.split(".")[1].title()
        nodes.append(PatientNode(nid, root, kind, title, f"{len(facts)} rows", facts, []))
    return nodes, ccda.record_date(doc).isoformat()


def as_text(node: PatientNode) -> str:
    """One node as the lines a model reads: 'start -> stop: description (value)'."""
    lines = [f"{f['start'] or '?'} -> {f['stop'] or 'no end date'}: {f['description']}"
             + (f" ({f['value']})" if f.get("value") else "") for f in node.facts]
    return f"## {node.title}\n" + ("\n".join(lines) or "(no rows)")


def latest_weight(nodes: list[PatientNode]) -> dict | None:
    """The newest Body Weight row of the narrative vital signs, parsed from its words ("83.6 kg")."""
    rows = [f for n in nodes if n.node_id == "narrative.vitals" for f in n.facts
            if f["description"].lower().startswith("body weight") and f.get("value")]
    if not rows:
        return None
    f = max(rows, key=lambda r: r["start"])
    m = re.match(r"([\d.]+)\s*(\S+)?", f["value"])
    return {"loinc": "29463-7", "display": "Body Weight", "value": m.group(1) if m else None,
            "unit": (m.group(2) if m else None), "date": f["start"], "entry_id": ""} if m else None
