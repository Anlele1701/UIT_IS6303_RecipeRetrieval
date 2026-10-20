"""MV4a: pick generated Synthea patients until every P8 stratum has enough living patients (Thy, after MV0).

    uv run scripts/patient_select.py --from ../synthea/output/ccda --command "<the run_synthea line>" --n 1000

Strata follow the rules the evaluation uses: a condition stratum is the label of the condition_nutrient.csv rows
whose codes an active (disorder) matches (hypertension, diabetes = T2D and its complications, ckd = stages 1-4
and kidney disorder due to diabetes); `multi` = two or more of them; `food_allergy` = an active food allergy.
The sample's living patients are counted first; generated ones are then taken in a seeded random order, each only
if it fills a stratum still short of TARGET. They are copied to PATIENT_GENERATED_DIR (refused if it already
holds files) and data/sources.json gets the `generated` entry. Counts go to eval/patient_selection.json.
"""

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api import config  # noqa: E402
from api.patient import ccda, rules  # noqa: E402

SEED = 42
TARGET = 15
CLINICAL = {"Essential hypertension": "hypertension", "Diabetes mellitus type 2": "diabetes",
            "Chronic kidney disease": "ckd", "CKD stage 3/4": "ckd"}
SHORT = ["diabetes", "ckd", "multi"]  # hypertension already has 18 living patients in the sample (MV0)
OUT = ROOT / "eval" / "patient_selection.json"
SOURCES = ROOT / "data" / "sources.json"


def condition_codes(rs) -> dict[str, str]:
    """SNOMED code -> stratum, from the filter/soft/warn rows of condition_nutrient.csv."""
    out = {}
    for r in rs.nutrient:
        if r.mode != "unmapped" and r.label in CLINICAL:
            for c in r.conditions:
                out[c] = CLINICAL[r.label]
    return out


def strata(record, codes: dict[str, str]) -> set[str]:
    found = {codes[p.code] for p in record.problems if p.code in codes}
    if len(found) >= 2:
        found.add("multi")
    if any(a.kind_code == ccda.FOOD_ALLERGY for a in record.allergies):
        found.add("food_allergy")
    return found


def read_folder(folder: Path, source: str, rs) -> list[tuple[Path, object]]:
    out = []
    for path in sorted(folder.glob("*.xml")):
        record, _ = ccda.read_record(path, source, rs.p7)
        out.append((path, record))
    return out


def count(records, codes) -> dict[str, int]:
    c: dict[str, int] = {}
    for _, r in records:
        if r.deceased:
            continue
        for s in strata(r, codes):
            c[s] = c.get(s, 0) + 1
    return c


def select(generated, have: dict[str, int], codes, target: int = TARGET, seed: int = SEED):
    """Seeded order; a patient is kept only if it adds to a stratum still under target."""
    pool = [(p, r) for p, r in generated if not r.deceased]
    random.Random(seed).shuffle(pool)
    have = dict(have)
    chosen = []
    for path, r in pool:
        short = [s for s in SHORT if have.get(s, 0) < target]
        if not short:
            break
        got = strata(r, codes)
        if got & set(short):
            chosen.append((path, r))
            for s in got:
                have[s] = have.get(s, 0) + 1
    return chosen, have


def structure(paths: list[Path]) -> dict:
    """What the parser relies on, per source: share of files with each section, and the code systems of the
    allergy substances, problems and medications (a generated file must read like a sample one)."""
    n = len(paths) or 1
    sections: dict[str, int] = {}
    systems: dict[str, dict[str, int]] = {"allergy_substance": {}, "problem": {}, "medication": {}}
    paths_ = {"allergy_substance": ("48765-2", ".//c:participant/c:participantRole/c:playingEntity/c:code/@codeSystem"),
              "problem": ("11450-4", ".//c:entryRelationship/c:observation/c:value/@codeSystem"),
              "medication": ("10160-0", ".//c:manufacturedMaterial/c:code/@codeSystem")}
    for p in paths:
        doc = ccda.parse(p)
        secs = ccda.sections(doc)
        for code in secs:
            sections[code] = sections.get(code, 0) + 1
        for key, (code, xp) in paths_.items():
            for s in secs.get(code, []):
                for v in s.xpath(xp, namespaces=ccda.NS):
                    systems[key][str(v)] = systems[key].get(str(v), 0) + 1
    return {"files": len(paths), "section_share": {k: round(v / n, 3) for k, v in sorted(sections.items())},
            "code_systems": systems}


def differences(a: dict, b: dict) -> list[str]:
    out = []
    for code in sorted(set(a["section_share"]) | set(b["section_share"])):
        x, y = a["section_share"].get(code, 0), b["section_share"].get(code, 0)
        if (x == 0) != (y == 0) or abs(x - y) > 0.25:
            out.append(f"section {code}: sample {x}, generated {y}")
    for key in a["code_systems"]:
        sa, sb = set(a["code_systems"][key]), set(b["code_systems"][key])
        if sb - sa:
            out.append(f"{key}: code systems only in generated {sorted(sb - sa)}")
    return out


def files_sha(paths: list[Path]) -> str:
    lines = sorted(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in paths)
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def git_head(folder: Path) -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=folder, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="src", required=True, help="Synthea output/ccda folder")
    ap.add_argument("--command", required=True, help="the run_synthea command line, recorded in data/sources.json")
    ap.add_argument("--n", type=int, required=True, help="population size of that run (-p)")
    args = ap.parse_args()
    rs = rules.load_rules()
    codes = condition_codes(rs)
    src = Path(args.src).resolve()
    sample = read_folder(ROOT / config.PATIENT_DATA_DIR, "sample", rs)
    generated = read_folder(src, "generated", rs)
    have = count(sample, codes)
    chosen, after = select(generated, have, codes)
    short = {s: after.get(s, 0) for s in SHORT if after.get(s, 0) < TARGET}

    dest = ROOT / config.PATIENT_GENERATED_DIR
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"{dest} already holds files: move them away first (nothing is overwritten)")
    dest.mkdir(parents=True, exist_ok=True)
    for path, _ in chosen:
        shutil.copy2(path, dest / path.name)
    copied = sorted(dest.glob("*.xml"))

    s_sample = structure([p for p, _ in sample])
    s_gen = structure(copied)
    report = {"ran_at": date.today().isoformat(), "seed": SEED, "target": TARGET, "strata_rule": __doc__.split("\n\n")[1],
              "structure": {"sample": s_sample, "generated_chosen": s_gen,
                            "differences": differences(s_sample, s_gen)},
              "sample_alive": have, "generated_files": len(generated),
              "generated_alive": sum(not r.deceased for _, r in generated),
              "generated_by_stratum": count(generated, codes), "chosen": len(chosen), "after": after,
              "still_short": short}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    sources["generated"] = {
        "dir": config.PATIENT_GENERATED_DIR, "description": f"{len(copied)} Synthea patients chosen from a run of {args.n}",
        "synthea_commit": git_head(src.parents[1]) or "?", "command": args.command, "seed": SEED, "population": args.n,
        "selection": "scripts/patient_select.py, seed 42, eval/patient_selection.json", "files": len(copied),
        "files_sha256_of_sorted_list": files_sha(copied), "generated": date.today().isoformat(),
        "synthea_commit_note": "same commit and default settings as the sample (generate_samples.sh), plus the seed, "
                               "the age range and only_alive_patients"}
    SOURCES.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("sample_alive", "generated_alive", "generated_by_stratum", "chosen",
                                             "after", "still_short")}, indent=1))


if __name__ == "__main__":
    main()
