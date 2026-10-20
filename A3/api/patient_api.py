"""Patient record endpoints for the UI (MV5; contract in docs/plan/A3_ke_hoach_build.md section 6.5).

    GET /patients                      the patients a session may be about (no name: the table holds none)
    GET /patients/{id}/tree            the record tree as a model sees it: prompt views only (ADR-0006)
    GET /patients/{id}/profile         the constraints the rule tables derive, with their evidence

The UI gets exactly what a model may see: allow-listed facts (api/patient/prompt_view.py), never the raw facts,
entry ids, names or P7 data. 404 for an unknown patient, 409 for a deceased one (no session either).
"""

from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from .deps import get_conn
from .patient import profile_store
from .patient import rules as patient_rules
from .patient.mapping import record_groups
from .patient.prompt_view import prompt_view

router = APIRouter(prefix="/patients", tags=["patients"])
_RULES = None


def rules():
    global _RULES
    if _RULES is None:
        _RULES = patient_rules.load_rules()
    return _RULES


def profile_view(profile) -> dict:
    """PatientProfile.to_dict() without the entry ids of its evidence (node id and text are what the UI shows)."""
    d = profile.to_dict()
    d["evidence"] = {k: [{"node_id": e["node_id"], "text": e["text"]} for e in v] for k, v in d["evidence"].items()}
    return d


def _living(conn: psycopg.Connection, pid: str) -> None:
    row = conn.execute("SELECT deceased FROM patient WHERE patient_id = %s", [pid]).fetchone()
    if row is None:
        raise HTTPException(404, f"unknown patient {pid}")
    if row[0]:
        raise HTTPException(409, f"patient {pid} is deceased: no record view and no session")


@router.get("")
def list_patients(alive_only: bool = True, conn=Depends(get_conn)) -> list[dict]:
    rows = conn.execute("""SELECT patient_id, source, sex, age_years, record_date, deceased FROM patient
                           WHERE NOT (%s AND deceased) ORDER BY source, patient_id""", [alive_only]).fetchall()
    out = []
    for pid, source, sex, age, record_date, deceased in rows:
        item = {"patient_id": pid, "source": source, "sex": sex, "age_years": age,
                "record_date": record_date.isoformat(), "deceased": deceased}
        if not deceased:  # a deceased patient has no profile to summarize (P8, no session)
            p = profile_store.load_or_build(conn, pid, rules())
            item["summary"] = {"allergens": sorted(p.allergens_exclude), "nutrient_limits": sorted(p.nutrient_limits),
                               "nutrient_soft": sorted(p.nutrient_soft), "warnings": len(p.warnings)}
        out.append(item)
    return out


@router.get("/{patient_id}/tree")
def patient_tree(patient_id: str, conn=Depends(get_conn)) -> list[dict]:
    _living(conn, patient_id)
    return [{"node_id": n.node_id, "parent_id": n.parent_id, "kind": n.kind, "title": n.title,
             "summary": n.summary, "facts": prompt_view(n, rules(), with_summary=False)["facts"]}
            for n in profile_store.load_nodes(conn, patient_id)]


@router.get("/{patient_id}/profile")
def patient_profile(patient_id: str, mode: Literal["vectorless", "direct"] = "vectorless",
                    conn=Depends(get_conn)) -> dict:
    _living(conn, patient_id)
    profile = profile_store.load_or_build(conn, patient_id, rules(), mode)
    return {**profile_view(profile), "groups": record_groups(profile, profile_store.load_nodes(conn, patient_id))}
