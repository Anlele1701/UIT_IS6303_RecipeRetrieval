# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2>=3.1", "faker>=30"]
# ///
"""Build synthetic patient records (Markdown) with exact nutrition constraint answer keys.

No LLM calls. Constraints are drawn from a seed first; prose is Jinja2 + phrase banks.

    uv run scripts/make_records.py              # 40 patients, seed 603 -> eval/records/
    uv run scripts/make_records.py --limit 5
    uv run scripts/make_records.py --force      # regenerate patients already in answer_key.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "eval" / "records"
ANSWER_KEY = OUT_DIR / "answer_key.json"
TEMPLATE_DIR = Path(__file__).resolve().parent / "records_templates"
PHRASE_DIR = Path(__file__).resolve().parent / "records_phrase_banks"

SIZE, SEED = 40, 603
ATTEMPTS = 3
MIN_CHARS, MAX_CHARS = 3_000, 32_000  # roughly a few thousand tokens of prose

# nutrient -> (unit, current value choices, superseded looser choices)
NUTRIENTS: dict[str, tuple[str, tuple[int, ...], tuple[int, ...]]] = {
    "sodium_mg": ("mg", (400, 500, 600, 700, 800), (1500, 2000, 2300)),
    "sugars_g": ("g", (5, 8, 10, 12, 15), (25, 30, 40)),
    "carbohydrates_g": ("g", (30, 40, 45, 50, 55), (75, 90, 100)),
    "calories": ("kcal", (350, 400, 450, 500, 550), (700, 800, 900)),
    "saturated_fat_g": ("g", (3, 5, 7, 8, 10), (15, 18, 20)),
    "potassium_mg": ("mg", (500, 600, 700, 800), (1200, 1500, 2000)),
}

ROLES = ("PCP", "PCP", "Cardiology", "Dietitian", "Endocrinology", "PCP", "Dietitian", "Nephrology")
ROLE_SLUG = {
    "PCP": "pcp",
    "Cardiology": "cardiology",
    "Dietitian": "dietitian",
    "Endocrinology": "endocrinology",
    "Nephrology": "nephrology",
}


@dataclass(frozen=True)
class Constraint:
    nutrient: str
    op: str
    value: int
    unit: str
    effective_date: str
    evidence_section_id: str


def load_json(name: str):
    return json.loads((PHRASE_DIR / name).read_text())


def section_id_for(visit_date: date, role: str) -> str:
    return f"visit-{visit_date.isoformat()}-{ROLE_SLUG[role]}"


def heading_slugs(markdown: str) -> set[str]:
    """Map ## Visit YYYY-MM-DD — Role headings to section_id style slugs."""
    out: set[str] = set()
    for m in re.finditer(r"^<!-- section_id: (\S+) -->$", markdown, re.M):
        out.add(m.group(1))
    return out


def format_value(value: int, unit: str) -> str:
    return f"{value} {unit}"


def diet_order_text(c: Constraint, *, superseded: bool) -> str:
    label = {
        "sodium_mg": "sodium",
        "sugars_g": "added sugars",
        "carbohydrates_g": "carbohydrates",
        "calories": "calories",
        "saturated_fat_g": "saturated fat",
        "potassium_mg": "potassium",
    }[c.nutrient]
    if superseded:
        return (
            f"On {c.effective_date}, interim nutrition counseling set a provisional "
            f"maximum of {format_value(c.value, c.unit)} {label} per serving. "
            f"This order is superseded by a later visit."
        )
    return (
        f"Effective {c.effective_date}, the active diet order is: "
        f"maximum {format_value(c.value, c.unit)} {label} per serving. "
        f"Use this threshold for meal selection."
    )


def _fmt_mustache(template: str, fmt: dict) -> str:
    """Fill {{name}} placeholders used in phrase-bank JSON strings."""
    out = template
    for k, v in fmt.items():
        out = out.replace("{{" + k + "}}", str(v)).replace("{{ " + k + " }}", str(v))
    return out


def build_demographics(rng: random.Random, patient_id: str) -> dict:
    fake = Faker()
    fake.seed_instance(rng.randint(0, 10**9))
    sex = rng.choice(["female", "male"])
    dob = fake.date_of_birth(minimum_age=35, maximum_age=78)
    return {
        "name": fake.name_female() if sex == "female" else fake.name_male(),
        "dob": dob.isoformat(),
        "sex": sex,
        "mrn": f"SYN-{patient_id.upper()}-{rng.randint(1000, 9999)}",
        "clinic": rng.choice([
            "Riverside Primary Care",
            "Harbor Family Medicine",
            "Northside Internal Medicine",
            "Cedar Outpatient Clinic",
        ]),
    }


def build_constraint_specs(rng: random.Random) -> tuple[list[Constraint], list[Constraint], list[date], dict[str, str]]:
    """Return current constraints, superseded, visit dates, and role per date."""
    n_visits = rng.randint(6, 10)
    # Spread visits over ~18 months ending early 2026
    end = date(2026, 3, 28)
    start = end - timedelta(days=rng.randint(400, 550))
    offsets = sorted(rng.sample(range((end - start).days + 1), n_visits))
    visit_dates = [start + timedelta(days=o) for o in offsets]

    roles = [rng.choice(ROLES) for _ in visit_dates]
    # Guarantee a Dietitian visit near the end for current orders
    roles[-1] = "Dietitian"
    if n_visits >= 3:
        roles[n_visits // 2] = "PCP"

    n_nutrients = rng.randint(1, 3)
    nutrients = rng.sample(list(NUTRIENTS), n_nutrients)

    # Superseded on an earlier visit; current on the last Dietitian visit
    early_idx = rng.randint(1, max(1, n_visits - 2))
    current_date = visit_dates[-1]
    early_date = visit_dates[early_idx]
    if early_date >= current_date:
        early_idx = 0
        early_date = visit_dates[0]

    roles[early_idx] = roles[early_idx] if roles[early_idx] != "Dietitian" else "PCP"

    current: list[Constraint] = []
    superseded: list[Constraint] = []
    for nutrient in nutrients:
        unit, cur_vals, old_vals = NUTRIENTS[nutrient]
        cur_v = rng.choice(cur_vals)
        old_v = rng.choice(old_vals)
        if old_v <= cur_v:
            old_v = cur_v + max(old_vals) // 2
        current.append(Constraint(
            nutrient=nutrient, op="max", value=cur_v, unit=unit,
            effective_date=current_date.isoformat(),
            evidence_section_id=section_id_for(current_date, roles[-1]),
        ))
        superseded.append(Constraint(
            nutrient=nutrient, op="max", value=old_v, unit=unit,
            effective_date=early_date.isoformat(),
            evidence_section_id=section_id_for(early_date, roles[early_idx]),
        ))

    role_by_date = {d.isoformat(): roles[i] for i, d in enumerate(visit_dates)}
    return current, superseded, visit_dates, role_by_date


def render_record(
    patient_id: str,
    rng: random.Random,
    current: list[Constraint],
    superseded: list[Constraint],
    visit_dates: list[date],
    role_by_date: dict[str, str],
) -> str:
    vitals_t = load_json("vitals.json")
    meds_t = load_json("meds.json")
    labs_t = load_json("labs.json")
    social_t = load_json("social.json")
    noise_t = load_json("visit_noise.json")
    med_names = load_json("med_names.json")

    med1, med2 = rng.sample(med_names, 2)
    medications = [
        _fmt_mustache(rng.choice(meds_t), {"med1": med1, "med2": med2})
        for _ in range(rng.randint(3, 5))
    ]
    laboratory = []
    for _ in range(rng.randint(4, 7)):
        laboratory.append(_fmt_mustache(rng.choice(labs_t), {
            "lab_date": (visit_dates[0] + timedelta(days=rng.randint(0, 30))).isoformat(),
            "creat": f"{rng.uniform(0.7, 1.4):.2f}",
            "egfr": str(rng.randint(55, 95)),
            "glucose": str(rng.randint(85, 140)),
            "a1c": f"{rng.uniform(5.4, 7.2):.1f}",
            "na": str(rng.randint(135, 144)),
            "k": f"{rng.uniform(3.6, 4.8):.1f}",
        }))
    social = [
        _fmt_mustache(rng.choice(social_t), {"household": rng.randint(1, 4)})
        for _ in range(rng.randint(3, 5))
    ]

    by_section_current = {c.evidence_section_id: [] for c in current}
    for c in current:
        by_section_current.setdefault(c.evidence_section_id, []).append(c)
    by_section_old = {}
    for c in superseded:
        by_section_old.setdefault(c.evidence_section_id, []).append(c)

    visits = []
    for d in visit_dates:
        role = role_by_date[d.isoformat()]
        sid = section_id_for(d, role)
        vitals = _fmt_mustache(rng.choice(vitals_t), {
            "bp_sys": rng.randint(110, 148),
            "bp_dia": rng.randint(68, 92),
            "hr": rng.randint(58, 95),
            "temp": f"{rng.uniform(36.4, 37.2):.1f}",
            "spo2": rng.randint(95, 99),
        })
        noise = [rng.choice(noise_t) for _ in range(rng.randint(3, 6))]
        # Pad so overall length reaches MIN_CHARS without LLM
        while sum(len(p) for p in noise) < 400:
            noise.append(rng.choice(noise_t))

        orders: list[str] = []
        for c in by_section_old.get(sid, []):
            orders.append(diet_order_text(c, superseded=True))
        for c in by_section_current.get(sid, []):
            orders.append(diet_order_text(c, superseded=False))

        visits.append({
            "date": d.isoformat(),
            "role_label": role,
            "section_id": sid,
            "vitals": vitals,
            "noise": noise,
            "diet_orders": orders,
        })

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    tpl = env.get_template("record.md.j2")
    return tpl.render(
        patient_id=patient_id,
        demographics=build_demographics(rng, patient_id),
        medications=medications,
        laboratory=laboratory,
        social=social,
        visits=visits,
    )


def assert_record(markdown: str, current: list[Constraint], superseded: list[Constraint]) -> list[str]:
    problems: list[str] = []
    slugs = heading_slugs(markdown)
    for c in (*current, *superseded):
        needle = format_value(c.value, c.unit)
        if needle not in markdown:
            problems.append(f"missing value text {needle!r} for {c.nutrient}")
        if c.evidence_section_id not in slugs:
            problems.append(f"missing section_id {c.evidence_section_id}")
    n = len(markdown)
    if n < MIN_CHARS:
        problems.append(f"too short: {n} chars < {MIN_CHARS}")
    if n > MAX_CHARS:
        problems.append(f"too long: {n} chars > {MAX_CHARS}")
    return problems


def patient_ids(n: int) -> list[str]:
    return [f"p{i:03d}" for i in range(1, n + 1)]


def load_answer_key(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return {row["patient_id"]: row for row in data}
    return data


def save_answer_key(path: Path, by_id: dict[str, dict]) -> None:
    rows = [by_id[k] for k in sorted(by_id)]
    path.write_text(json.dumps(rows, indent=2) + "\n")


def generate_one(patient_id: str, base_seed: int) -> tuple[str, dict]:
    last_problems: list[str] = []
    for attempt in range(ATTEMPTS):
        rng = random.Random(base_seed + attempt * 9973 + int(patient_id[1:]) * 13)
        current, superseded, visit_dates, role_by_date = build_constraint_specs(rng)
        md = render_record(patient_id, rng, current, superseded, visit_dates, role_by_date)
        problems = assert_record(md, current, superseded)
        if not problems:
            key = {
                "patient_id": patient_id,
                "constraints": [asdict(c) for c in current],
                "superseded": [asdict(c) for c in superseded],
            }
            return md, key
        last_problems = problems
    raise ValueError(f"{patient_id}: failed after {ATTEMPTS} attempts: {last_problems}")


def build_records(
    out_dir: Path,
    answer_key_path: Path,
    *,
    size: int = SIZE,
    seed: int = SEED,
    limit: int | None = None,
    force: bool = False,
) -> tuple[int, list[str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_id = load_answer_key(answer_key_path)
    ids = patient_ids(size)
    if limit is not None:
        ids = ids[:limit]

    written = 0
    skipped: list[str] = []
    for pid in ids:
        md_path = out_dir / f"{pid}.md"
        if not force and pid in by_id and md_path.exists():
            skipped.append(pid)
            continue
        md, key = generate_one(pid, seed)
        md_path.write_text(md)
        by_id[pid] = key
        written += 1

    save_answer_key(answer_key_path, by_id)
    return written, skipped


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--size", type=int, default=SIZE, help="number of patients (default 40)")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--limit", type=int, help="only the first N patient ids")
    p.add_argument("--force", action="store_true", help="regenerate even if already in answer_key.json")
    p.add_argument("--out", type=Path, default=OUT_DIR, help="output directory for .md and answer_key.json")
    return p.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    out = a.out.resolve()
    key_path = out / "answer_key.json"
    try:
        written, skipped = build_records(
            out, key_path, size=a.size, seed=a.seed, limit=a.limit, force=a.force)
    except ValueError as e:
        sys.exit(f"make_records: {e}")
    print(
        f"done: {written} written, {len(skipped)} skipped, "
        f"{len(load_answer_key(key_path))} in {key_path.relative_to(ROOT)}",
        flush=True,
    )
