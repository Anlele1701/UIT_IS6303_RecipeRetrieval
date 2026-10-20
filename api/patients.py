"""Patient profiles from the `ehr` schema (Synthea records). Vectorless: a keyed SQL lookup, no embeddings.

The profile is the contract between the record database and the Dietary Rule Engine
(api/dietary_rules.py). Active means `stop_date IS NULL`; conditions are matched by SNOMED code.
"""

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

import psycopg


class PatientNotFound(LookupError):
    pass


@dataclass(frozen=True)
class ActiveCondition:
    code: str  # SNOMED-CT
    description: str
    since: date  # earliest start among this patient's active rows with this code


@dataclass(frozen=True)
class ActiveAllergy:
    code: str  # SNOMED-CT for food and environment, RxNorm for medication
    description: str
    category: str | None  # food | environment | medication
    since: date


@dataclass
class PatientProfile:
    patient_id: UUID
    display_name: str
    age: int
    gender: str
    reference_date: date  # the simulation's "today"; ages and "active" are relative to it
    active_conditions: list[ActiveCondition] = field(default_factory=list)
    active_allergies: list[ActiveAllergy] = field(default_factory=list)


def age_on(birth: date, ref: date) -> int:
    return ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))


def get_profile(conn: psycopg.Connection, patient_id: UUID | str) -> PatientProfile:
    """The patient with their active conditions and allergies. Raises PatientNotFound for an unknown id."""
    row = conn.execute(
        """SELECT p.id, p.display_name, p.birth_date, p.gender, r.reference_date
           FROM ehr.patient p JOIN ehr.cohort_run r USING (run_id) WHERE p.id = %s""",
        [str(patient_id)]).fetchone()
    if row is None:
        raise PatientNotFound(str(patient_id))
    pid, name, birth, gender, ref = row
    conditions = conn.execute(
        """SELECT code, max(description), min(start_date) FROM ehr.condition
           WHERE patient_id = %s AND stop_date IS NULL
           GROUP BY code ORDER BY min(start_date), code""",
        [str(patient_id)]).fetchall()
    allergies = conn.execute(
        """SELECT code, max(description), max(category), min(start_date) FROM ehr.allergy
           WHERE patient_id = %s AND stop_date IS NULL
           GROUP BY code ORDER BY max(category), max(description)""",
        [str(patient_id)]).fetchall()
    return PatientProfile(pid, name, age_on(birth, ref), gender, ref,
                          [ActiveCondition(c, d, s) for c, d, s in conditions],
                          [ActiveAllergy(c, d, cat, s) for c, d, cat, s in allergies])


def list_patients(conn: psycopg.Connection, limit: int = 50, offset: int = 0, q: str | None = None,
                  order: str = "name") -> list[dict]:
    """A page of patients for a picker: id, name, age, gender and how many conditions are active.

    `q` keeps names containing that text (case-insensitive); `order` is "name" or "conditions" (most first).
    """
    if order not in ("name", "conditions"):
        raise ValueError(f"order must be 'name' or 'conditions', not {order!r}")
    like = "%" + (q or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    sort = "6 DESC, p.display_name, p.id" if order == "conditions" else "p.display_name, p.id"
    rows = conn.execute(
        f"""SELECT p.id, p.display_name, p.birth_date, p.gender, r.reference_date,
                   (SELECT count(DISTINCT c.code) FROM ehr.condition c
                    WHERE c.patient_id = p.id AND c.stop_date IS NULL)
            FROM ehr.patient p JOIN ehr.cohort_run r USING (run_id)
            WHERE p.display_name ILIKE %s
            ORDER BY {sort} LIMIT %s OFFSET %s""",
        [like, limit, offset]).fetchall()
    return [{"patient_id": pid, "display_name": name, "age": age_on(birth, ref), "gender": gender,
             "active_conditions": n} for pid, name, birth, gender, ref, n in rows]
