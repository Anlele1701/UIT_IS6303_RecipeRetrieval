"""MV4b, rule P8: the evaluation patients, stratified, seeded. Living patients only (Thy, after MV0).

    uv run scripts/patient_sample.py        # -> eval/patient/sample.json

Strata as in scripts/patient_select.py (condition_nutrient.csv codes, multi, food allergy). Every patient with a
constraint stratum is taken (CKD and diabetes in full, Thy); the rest ("none") are sampled with seed 42 up to
TOTAL. Each patient gets a primary stratum for the tables (multi > ckd > diabetes > hypertension > food_allergy
> none) and keeps all its strata. Nothing names a patient beyond the Synthea uuid.
"""

import json
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import psycopg  # noqa: E402

import patient_select  # noqa: E402
from api import config  # noqa: E402
from api.patient import profile_store, rules  # noqa: E402

SEED = 42
TOTAL = 100
PRIORITY = ["multi", "ckd", "diabetes", "hypertension", "food_allergy"]
OUT = ROOT / "eval" / "patient" / "sample.json"


def strata_of(nodes, codes: dict[str, str]) -> set[str]:
    facts = {n.node_id: n.facts for n in nodes}
    found = {codes[f.get("code")] for f in facts.get("problems.active", []) if f.get("code") in codes}
    if len(found) >= 2:
        found.add("multi")
    if any(a.get("kind_code") == "414285001" for a in facts.get("allergies", [])):
        found.add("food_allergy")
    return found


def primary(strata: set[str]) -> str:
    return next((p for p in PRIORITY if p in strata), "none")


def draw(patients: list[dict], total: int = TOTAL, seed: int = SEED) -> list[dict]:
    """All patients with a constraint stratum, then seeded "none" ones up to `total`."""
    keep = [p for p in patients if p["primary"] != "none"]
    rest = sorted((p for p in patients if p["primary"] == "none"), key=lambda p: p["patient_id"])
    random.Random(seed).shuffle(rest)
    return sorted(keep + rest[:max(0, total - len(keep))], key=lambda p: p["patient_id"])


def main():
    rs = rules.load_rules()
    codes = patient_select.condition_codes(rs)
    patients = []
    with psycopg.connect(config.DATABASE_URL) as conn:
        rows = conn.execute("SELECT patient_id, source FROM patient WHERE NOT deceased ORDER BY patient_id").fetchall()
        for pid, source in rows:
            st = strata_of(profile_store.load_nodes(conn, pid), codes)
            patients.append({"patient_id": pid, "source": source, "strata": sorted(st), "primary": primary(st)})
    chosen = draw(patients)
    out = {"ran_at": datetime.now().isoformat(timespec="seconds"), "seed": SEED, "total": TOTAL,
           "rule": __doc__.split("\n\n")[1], "living_patients": len(patients),
           "by_primary": dict(Counter(p["primary"] for p in chosen)),
           "by_source": dict(Counter(p["source"] for p in chosen)),
           "by_stratum": dict(Counter(s for p in chosen for s in p["strata"])), "patients": chosen}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({k: out[k] for k in ("living_patients", "by_primary", "by_source", "by_stratum")})


if __name__ == "__main__":
    main()
