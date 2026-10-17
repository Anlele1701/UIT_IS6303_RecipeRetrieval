# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]>=3.2"]
# ///
"""Load a Synthea CSV export into the `ehr` schema (patient records for the vectorless side).

    uv run scripts/load_synthea.py load data/patients_record --synthea-args "-p 1000 -a 40-90 -s 603"
    uv run scripts/load_synthea.py stats          # who is in the DB and which conditions are active
    uv run scripts/load_synthea.py reset --yes    # empty every ehr table

`load` applies sql/ehr.sql first (it only creates what is missing), then loads in one transaction.
A run_id that is already loaded is refused unless --replace is given. Synthea is not re-run:
this reads CSVs that already exist. Dead patients are skipped, observations are limited to the
LOINC codes in OBSERVATION_CODES, and the Encounter/Payer columns are dropped.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_SQL = ROOT / "sql" / "ehr.sql"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://recipe:recipe@localhost:5434/recipe")

FILES = ("patients", "conditions", "medications", "allergies", "observations")

# The full observations file is ~1.2M rows, mostly social-history surveys and urinalysis.
# These are the ones a diet rule could use later (see ehr-and-rules-planning.md).
OBSERVATION_CODES = {
    "4548-4": "Hemoglobin A1c",
    "33914-3": "eGFR (MDRD)",
    "39156-5": "Body mass index",
    "29463-7": "Body weight",
    "8480-6": "Systolic blood pressure",
    "8462-4": "Diastolic blood pressure",
    "6298-4": "Potassium, blood",
    "2823-3": "Potassium, serum or plasma",
    "2947-0": "Sodium, blood",
    "2951-2": "Sodium, serum or plasma",
    "38483-4": "Creatinine, blood",
    "2160-0": "Creatinine, serum or plasma",
}


# ---------------------------------------------------------------------------
# Reading the CSVs
# ---------------------------------------------------------------------------


def read_rows(path: Path) -> Iterator[dict]:
    """Rows keyed by lowercase column name (Synthea capitalizes headers inconsistently)."""
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yield {k.lower(): v for k, v in row.items()}


def blank_to_none(s: str | None) -> str | None:
    return s if s not in ("", None) else None


def clean_name(first: str, last: str) -> str:
    """Synthea appends digits to invented names ('Ewa95 Lockman863'); drop them for display."""
    return " ".join(re.sub(r"\d+", "", p).strip() for p in (first, last) if p).strip()


def numeric(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def ensure_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_SQL.read_text())


def copy_rows(conn: psycopg.Connection, table: str, columns: list[str], rows) -> int:
    n = 0
    with conn.cursor().copy(f"COPY ehr.{table} ({', '.join(columns)}) FROM STDIN") as cp:
        for row in rows:
            cp.write_row(row)
            n += 1
    return n


def load(conn: psycopg.Connection, src: Path, run_id: str, synthea_args: str = "",
         replace: bool = False) -> dict:
    """Load one Synthea export. Returns the rows loaded per table. Raises if the run exists and not `replace`."""
    missing = [f for f in FILES if not (src / f"{f}.csv").exists()]
    if missing:
        raise FileNotFoundError(f"{src}: missing {', '.join(m + '.csv' for m in missing)}")

    ensure_schema(conn)
    with conn.transaction():
        if conn.execute("SELECT 1 FROM ehr.cohort_run WHERE run_id = %s", [run_id]).fetchone():
            if not replace:
                raise RuntimeError(f"run {run_id!r} is already loaded; pass --replace to load it again")
            conn.execute("DELETE FROM ehr.patient WHERE run_id = %s", [run_id])  # cascades to the rest
            conn.execute("DELETE FROM ehr.cohort_run WHERE run_id = %s", [run_id])

        # A placeholder reference date until the conditions are read; fixed up at the end.
        conn.execute("INSERT INTO ehr.cohort_run (run_id, reference_date, manifest) VALUES (%s, %s, '{}')",
                     [run_id, date.today()])

        counts: dict[str, int] = {}
        alive: set[str] = set()

        def patients():
            skipped = 0
            for r in read_rows(src / "patients.csv"):
                if r["deathdate"]:
                    skipped += 1
                    continue
                alive.add(r["id"])
                yield [r["id"], run_id, r["birthdate"], r["gender"], clean_name(r["first"], r["last"])]
            counts["patients_skipped_dead"] = skipped

        counts["patient"] = copy_rows(conn, "patient", ["id", "run_id", "birth_date", "gender", "display_name"],
                                      patients())

        latest_start = ""

        def conditions():
            nonlocal latest_start
            for r in read_rows(src / "conditions.csv"):
                if r["patient"] in alive:
                    latest_start = max(latest_start, r["start"])
                    yield [r["patient"], r["start"], blank_to_none(r["stop"]), r["system"], r["code"],
                           r["description"]]

        counts["condition"] = copy_rows(
            conn, "condition", ["patient_id", "start_date", "stop_date", "system", "code", "description"],
            conditions())

        counts["medication"] = copy_rows(
            conn, "medication",
            ["patient_id", "start_at", "stop_at", "code", "description", "reason_code", "reason_description"],
            ([r["patient"], r["start"], blank_to_none(r["stop"]), r["code"], r["description"],
              blank_to_none(r["reasoncode"]), blank_to_none(r["reasondescription"])]
             for r in read_rows(src / "medications.csv") if r["patient"] in alive))

        counts["allergy"] = copy_rows(
            conn, "allergy", ["patient_id", "start_date", "stop_date", "code", "description", "category"],
            ([r["patient"], r["start"], blank_to_none(r["stop"]), r["code"], r["description"],
              blank_to_none(r["category"])]
             for r in read_rows(src / "allergies.csv") if r["patient"] in alive))

        def observations():
            for r in read_rows(src / "observations.csv"):
                if r["patient"] in alive and r["code"] in OBSERVATION_CODES:
                    value = numeric(r["value"]) if r["type"] == "numeric" else None
                    yield [r["patient"], r["date"], r["code"], r["description"], value,
                           None if value is not None else blank_to_none(r["value"]), blank_to_none(r["units"])]

        counts["observation"] = copy_rows(
            conn, "observation",
            ["patient_id", "observed_at", "code", "description", "value_num", "value_text", "units"],
            observations())

        problems = check(conn, run_id, counts)
        if problems:
            raise RuntimeError("load check failed: " + "; ".join(problems))

        manifest = {"source_dir": str(src), "synthea_args": synthea_args, "rows": counts,
                    "files_sha256": {f: sha256(src / f"{f}.csv") for f in FILES},
                    "observation_codes": OBSERVATION_CODES}
        conn.execute("UPDATE ehr.cohort_run SET reference_date = %s, manifest = %s::jsonb WHERE run_id = %s",
                     [latest_start or date.today(), json.dumps(manifest), run_id])
    return counts


def check(conn: psycopg.Connection, run_id: str, counts: dict) -> list[str]:
    """Problems found after loading (empty = fine). Foreign keys already forbid orphan rows."""
    problems = []
    n = conn.execute("SELECT count(*) FROM ehr.patient WHERE run_id = %s", [run_id]).fetchone()[0]
    if n != counts["patient"]:
        problems.append(f"patient rows {n} != loaded {counts['patient']}")
    if counts["patient"] == 0:
        problems.append("no living patients were loaded")
    n = conn.execute("""SELECT count(*) FROM ehr.condition c JOIN ehr.patient p ON p.id = c.patient_id
                        WHERE p.run_id = %s""", [run_id]).fetchone()[0]
    if n != counts["condition"]:
        problems.append(f"condition rows {n} != loaded {counts['condition']}")
    return problems


# ---------------------------------------------------------------------------
# stats / reset
# ---------------------------------------------------------------------------


def stats(conn: psycopg.Connection, top: int = 40) -> str:
    out = []
    for run_id, ref, manifest in conn.execute(
            "SELECT run_id, reference_date, manifest FROM ehr.cohort_run ORDER BY loaded_at").fetchall():
        n = conn.execute("SELECT count(*) FROM ehr.patient WHERE run_id = %s", [run_id]).fetchone()[0]
        out.append(f"run {run_id}: {n} patients, reference date {ref}, synthea args: "
                   f"{manifest.get('synthea_args') or '(not given)'}")
    if not out:
        return "no cohort loaded"
    per_patient = Counter(r[0] for r in conn.execute(
        "SELECT patient_id FROM ehr.condition WHERE stop_date IS NULL").fetchall())
    if per_patient:
        out.append(f"active conditions per patient: min {min(per_patient.values())}, "
                   f"max {max(per_patient.values())}, mean {sum(per_patient.values()) / len(per_patient):.1f}")
    out.append("\nmost common active conditions (patients):")
    for code, description, n in conn.execute(
            """SELECT code, description, count(DISTINCT patient_id) n FROM ehr.condition
               WHERE stop_date IS NULL GROUP BY code, description ORDER BY n DESC, code LIMIT %s""",
            [top]).fetchall():
        out.append(f"  {n:5d}  {code:>18}  {description}")
    return "\n".join(out)


def reset(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("TRUNCATE ehr.allergy, ehr.observation, ehr.medication, ehr.condition, "
                     "ehr.patient, ehr.cohort_run")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="load_synthea.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    cmds = parser.add_subparsers(dest="cmd", required=True)
    p = cmds.add_parser("load", help="load a Synthea CSV folder")
    p.add_argument("source", type=Path, help="folder holding patients.csv, conditions.csv, ...")
    p.add_argument("--run-id", help="name of this load (default: the folder name)")
    p.add_argument("--synthea-args", default="", help="the arguments Synthea was run with, kept in the manifest")
    p.add_argument("--replace", action="store_true", help="load again over an existing run_id")
    cmds.add_parser("stats", help="show what is loaded")
    p = cmds.add_parser("reset", help="empty every ehr table")
    p.add_argument("--yes", action="store_true", help="required: this deletes all patient data")
    args = parser.parse_args(argv)

    with psycopg.connect(DATABASE_URL) as conn:
        if args.cmd == "load":
            run_id = args.run_id or args.source.resolve().name
            try:
                counts = load(conn, args.source, run_id, args.synthea_args, args.replace)
            except (FileNotFoundError, RuntimeError) as e:
                sys.exit(str(e))
            print(f"loaded run {run_id!r}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
        elif args.cmd == "stats":
            ensure_schema(conn)
            conn.commit()
            print(stats(conn))
        elif args.cmd == "reset":
            if not args.yes:
                sys.exit("this deletes every patient record; rerun with --yes")
            ensure_schema(conn)
            reset(conn)
            print("ehr tables emptied")


if __name__ == "__main__":
    main()
