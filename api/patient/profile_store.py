"""Read a patient's tree from the DB and build (or reuse) its PatientProfile, cached per (patient, ruleset, mode).

Spec 5.5: the profile is computed once per session start; a cached row is valid while the rule files hash the
same (ruleset_version). `patient_ingest.py load` drops a patient's cache rows when it rewrites the tree.
"""

import psycopg
from psycopg.types.json import Jsonb

from .mapping import build_profile
from .models import PatientNode, PatientProfile
from .rules import RuleSet


def load_nodes(conn: psycopg.Connection, patient_id: str) -> list[PatientNode]:
    rows = conn.execute("""SELECT node_id, parent_id, kind, title, summary, facts, entry_ids, summary_source
                           FROM patient_node WHERE patient_id = %s ORDER BY position""", [patient_id]).fetchall()
    return [PatientNode(*r[:7], summary_source=r[7]) for r in rows]


def load_or_build(conn: psycopg.Connection, patient_id: str, rs: RuleSet, mode: str = "vectorless") -> PatientProfile:
    row = conn.execute("SELECT profile FROM patient_profile_cache WHERE patient_id = %s AND ruleset_version = %s "
                       "AND mode = %s", [patient_id, rs.version, mode]).fetchone()
    if row:
        return PatientProfile.from_dict(row[0])
    found = conn.execute("SELECT record_date FROM patient WHERE patient_id = %s", [patient_id]).fetchone()
    if found is None:
        raise KeyError(f"unknown patient {patient_id}")
    profile = build_profile(load_nodes(conn, patient_id), rs, found[0], mode, patient_id)
    with conn.transaction():
        conn.execute("""INSERT INTO patient_profile_cache (patient_id, ruleset_version, mode, profile)
                        VALUES (%s, %s, %s, %s) ON CONFLICT (patient_id, ruleset_version, mode)
                        DO UPDATE SET profile = EXCLUDED.profile, built_at = now()""",
                     [patient_id, rs.version, mode, Jsonb(profile.to_dict())])
    return profile
