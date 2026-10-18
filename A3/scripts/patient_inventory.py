"""MV0 inventory: every code the Synthea C-CDA files hold, counted, before any rule is written.

    uv run scripts/patient_inventory.py            # scan PATIENT_DATA_DIR -> eval/patient_inventory/, docs/patient_inventory.md
    uv run scripts/patient_inventory.py --render   # rebuild docs/patient_inventory.md from eval/patient_inventory/

Read-only on the XML files. Outputs hold codes, display names and counts only: no name, address, race,
file name or patient id (P7). Social History and Functional Status are counted, never read. A file that
fails to parse is listed by a short hash of its bytes. The P8 strata here are candidates found by keyword
on display names, listed with their codes so the user can check them; sampling is MV4's job.
"""

import argparse
import collections
import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api import config  # noqa: E402
from api.patient import ccda  # noqa: E402

OUT = ROOT / "eval" / "patient_inventory"
DOC = ROOT / "docs" / "patient_inventory.md"
RULES_DIR = ROOT / "data" / "rules"
RULES = RULES_DIR / "allergy_substance.csv"
SEED = 42  # nothing here samples; recorded for the run settings convention


def loinc_list(name: str) -> dict[str, dict]:
    """data/rules/include_loinc.csv or exclude_loinc.csv: LOINC -> row ({} when the file is missing)."""
    path = RULES_DIR / name
    return {r["loinc"]: r for r in csv.DictReader(open(path, encoding="utf-8"))} if path.exists() else {}


def p7_class(loinc: str | None, include: dict, exclude: dict) -> str:
    """A Results organizer goes into the patient tree only if allow-listed; sensitive ones are counted apart."""
    return "exclude" if loinc in exclude else "include" if loinc in include else "not_relevant"


# P8 candidate strata: keyword on an active (disorder) display name
STRATA = {
    "diabetes": re.compile(r"diabetes|prediabetes|hyperglycemia", re.I),
    "hypertension": re.compile(r"hypertension", re.I),
    "ckd": re.compile(r"kidney disease|renal disease|renal failure|nephropathy|end-stage renal", re.I),
}
# Codes and names the spec's draft tables (4.1-4.3) start from, checked against the data
SPEC_SUBSTANCES = {"412071004": "Wheat (substance)", "735029006": "Shellfish (substance)"}
SPEC_CONDITIONS = {"59621000": "Essential hypertension", "44054006": "Diabetes mellitus type 2",
                   "433144002": "CKD stage 3", "431857002": "CKD stage 4"}
SPEC_DRUGS = ["warfarin", "simvastatin", "atorvastatin"]
# Vitals and labs the spec (2.3, 4.2-4.4) expects some rules to use
SPEC_LOINC = {"29463-7": "Body weight", "39156-5": "BMI", "8480-6": "Systolic blood pressure",
              "8462-4": "Diastolic blood pressure", "33914-3": "eGFR (MDRD)", "4548-4": "HbA1c",
              "2951-2": "Sodium (serum)", "2823-3": "Potassium (serum)", "2160-0": "Creatinine (serum)",
              "2339-0": "Glucose (blood)", "2345-7": "Glucose (serum/plasma)"}
DEATH_CERTIFICATE = "69409-1"  # a Results organizer Synthea writes for a deceased patient
SYNONYM_SEARCH = {"prediabetes": r"prediabetes", "diabetes": r"diabetes", "CKD / kidney": r"kidney|renal|nephropathy",
                  "hypertension": r"hypertension", "hyperlipidemia": r"hyperlipidemia|cholesterol",
                  "obesity": r"obesity|body mass index 30", "anemia": r"anemia", "gout": r"gout",
                  "celiac": r"celiac|gluten"}


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def age_band(age: int | None) -> str:
    if age is None:
        return "unknown"
    return "0-17" if age < 18 else "18-39" if age < 40 else "40-64" if age < 65 else "65+"


class Tally:
    """Per code (never per display name: one code can be spelled two ways): the names seen, patients seen,
    patients with it in force, entries."""

    def __init__(self):
        self.rows: dict[tuple, dict] = {}

    def add(self, key: tuple, pid: str, active: bool, names: tuple = (), **extra):
        r = self.rows.setdefault(key, {"patients": set(), "active": set(), "entries": 0, "names": collections.Counter(),
                                       **{k: collections.Counter() for k in extra}})
        r["patients"].add(pid)
        if active:
            r["active"].add(pid)
        r["entries"] += 1
        r["names"][names] += 1
        for k, values in extra.items():
            r[k].update(v for v in values if v)

    @staticmethod
    def names(row: dict) -> tuple:
        """The most common spelling (ties: alphabetical, so the output is stable)."""
        return sorted(row["names"].items(), key=lambda kv: (-kv[1], [str(x) for x in kv[0]]))[0][0]


def scan(folder: Path) -> dict:
    files = sorted(folder.glob("*.xml"))
    t = {k: Tally() for k in ("allergies", "problems", "medications", "observations", "organizers", "encounters")}
    sections = collections.defaultdict(lambda: {"titles": collections.Counter(), "files": 0, "entries": 0})
    errors, software, dates, sexes, ages = [], collections.Counter(), [], collections.Counter(), collections.Counter()
    suffix_dropped = collections.Counter()
    strata_codes = {k: collections.Counter() for k in STRATA}
    patient_strata: list[set] = []
    dropped_entries = collections.Counter()
    ids = set()
    deceased, deceased_dates = 0, []
    include, exclude = loinc_list("include_loinc.csv"), loinc_list("exclude_loinc.csv")
    p7 = {c: {"organizers": 0, "patients": set()} for c in ("include", "exclude", "not_relevant")}
    loinc_patients: dict[str, set] = collections.defaultdict(set)  # any section, any organizer

    for path in files:
        try:
            doc = ccda.parse(path)
            today = ccda.record_date(doc)
            pid = ccda.patient_id(doc)
        except Exception as e:  # noqa: BLE001 - every failure is listed, the scan goes on
            errors.append({"file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:12],
                           "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        ids.add(pid)
        software[ccda.software_name(doc) or ""] += 1
        dates.append(today)
        sexes[ccda.sex(doc) or "unknown"] += 1
        ages[age_band(ccda.age_years(doc, today))] += 1
        found: set[str] = set()
        matched: set[tuple] = set()  # (stratum, code, display), counted once the patient is known to be alive
        secs = ccda.sections(doc)
        for code, group in secs.items():
            for s in group:
                n = len(s.xpath("c:entry", namespaces=ccda.NS))
                sections[code]["titles"][ccda.section_title(s)] += 1
                sections[code]["entries"] += n
                if code in ccda.DROPPED_SECTIONS:
                    dropped_entries[code] += n
            sections[code]["files"] += 1

        for s in secs.get(ccda.ALLERGIES, []):
            for a in ccda.allergies(s):
                t["allergies"].add((a.kind_code, a.substance_code), pid, a.active,
                                   names=(a.kind_display, a.substance_display), reactions=a.reactions,
                                   severity=[a.severity])
                if a.active and a.kind_code == ccda.FOOD_ALLERGY:
                    found.add("food_allergy")
        for s in secs.get(ccda.PROBLEMS, []):
            for p in ccda.problems(s):
                t["problems"].add((p.code,), pid, p.active, names=(p.display, p.suffix))
                if p.active and p.suffix != "disorder":
                    suffix_dropped[p.suffix or "none"] += 1
                if p.active and p.suffix == "disorder":
                    for name, rx in STRATA.items():
                        if rx.search(p.display or ""):
                            found.add(name)
                            matched.add((name, p.code, p.display))
        for s in secs.get(ccda.MEDICATIONS, []):
            for m in ccda.medications(s, today):
                t["medications"].add((m.code,), pid, m.active, names=(m.display,))
        for s in secs.get(ccda.VITALS, []):
            for o in ccda.vitals(s):
                t["observations"].add(("vitals", "", o.loinc), pid, False, names=(o.display,), unit=[o.unit])
                loinc_patients[o.loinc].add(pid)
        is_deceased = False
        for s in secs.get(ccda.RESULTS, []):
            orgs = ccda.organizers(s)
            is_deceased = is_deceased or any(o.loinc == DEATH_CERTIFICATE for o in orgs)
            for org in orgs:
                t["organizers"].add((org.loinc,), pid, False, names=(org.display,))
                cls = p7_class(org.loinc, include, exclude)
                p7[cls]["organizers"] += 1
                p7[cls]["patients"].add(pid)
                for o in org.observations:
                    t["observations"].add(("results", org.loinc, o.loinc), pid, False, names=(o.display,),
                                          unit=[o.unit])
                    loinc_patients[o.loinc].add(pid)
        if is_deceased:
            deceased += 1
            deceased_dates.append(today)
        else:
            for name, code, display in matched:
                strata_codes[name][(code, display)] += 1
        for s in secs.get(ccda.ENCOUNTERS, []):
            for enc in s.xpath("c:entry/c:encounter", namespaces=ccda.NS):
                code = enc.xpath("c:code/@code", namespaces=ccda.NS)
                disp = enc.xpath("c:code/@displayName", namespaces=ccda.NS)
                t["encounters"].add((code[0] if code else None,), pid, False, names=(disp[0] if disp else None,))
        patient_strata.append((found, is_deceased))

    clinical = {"diabetes", "hypertension", "ckd"}
    strata = collections.Counter()
    for found, is_deceased in patient_strata:
        if is_deceased:  # loaded and counted in P1, never in the P8 evaluation set (Thy, after MV0)
            continue
        for k in found:
            strata[k] += 1
        if len(found & clinical) >= 2:
            strata["multi"] += 1
        if not found:
            strata["none"] += 1
    return {"files": len(files), "parsed": len(patient_strata), "distinct_patient_ids": len(ids), "errors": errors,
            "software": software, "dates": dates, "sexes": sexes, "ages": ages, "tallies": t, "sections": sections,
            "suffix_dropped": suffix_dropped, "strata": strata, "strata_codes": strata_codes,
            "dropped_entries": dropped_entries, "deceased": deceased, "deceased_dates": deceased_dates,
            "p7": p7, "include": include, "exclude": exclude, "loinc_patients": loinc_patients}


def _write(name: str, header: list[str], rows: list[list]):
    with open(OUT / name, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _top(counter: collections.Counter, n: int = 6) -> str:
    return ";".join(f"{k} ({v})" for k, v in counter.most_common(n))


def _sorted(tally: Tally):
    return sorted(tally.rows.items(), key=lambda kv: (-len(kv[1]["patients"]), str(kv[0])))


def rule_check() -> dict:
    """Draft allergy_substance.csv against the data and the ingredient table (SELECT only)."""
    if not RULES.exists():
        return {"present": False}
    rows = list(csv.DictReader(open(RULES, encoding="utf-8")))
    names = sorted({n for r in rows for n in (r.get("extra_ingredients_exclude") or "").split(";") if n})
    try:
        import psycopg
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5) as conn:
            known = {r[0] for r in conn.execute("SELECT canonical_name FROM ingredient WHERE canonical_name = ANY(%s)",
                                                [names])}
        missing = [n for n in names if n not in known]
        db = "ok"
    except Exception as e:  # noqa: BLE001
        missing, db = None, f"unavailable: {type(e).__name__}"
    return {"present": True, "rows": len(rows), "extra_ingredients": names, "missing_in_ingredient_table": missing,
            "db": db, "codes": [r["snomed_code"] for r in rows],
            "unmapped": [r["snomed_code"] for r in rows if not r.get("allergens")]}


def write(r: dict, folder: Path) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    t = r["tallies"]
    name = Tally.names
    _write("allergies.csv", ["kind_code", "kind_display", "substance_code", "substance_display", "patients",
                             "patients_active", "entries", "reactions", "severity"],
           [[k[0], name(v)[0], k[1], name(v)[1], len(v["patients"]), len(v["active"]), v["entries"],
             _top(v["reactions"]), _top(v["severity"])] for k, v in _sorted(t["allergies"])])
    _write("problems.csv", ["snomed_code", "display", "suffix", "patients", "patients_active", "entries"],
           [[*k, *name(v), len(v["patients"]), len(v["active"]), v["entries"]] for k, v in _sorted(t["problems"])])
    _write("medications.csv", ["rxnorm_code", "display", "patients", "patients_active", "entries"],
           [[*k, *name(v), len(v["patients"]), len(v["active"]), v["entries"]] for k, v in _sorted(t["medications"])])
    _write("observations.csv", ["section", "organizer_loinc", "loinc", "display", "units", "patients", "observations"],
           [[*k, *name(v), _top(v["unit"], 3), len(v["patients"]), v["entries"]] for k, v in _sorted(t["observations"])])
    _write("organizers.csv", ["loinc", "display", "patients", "organizers", "p7_class"],
           [[*k, *name(v), len(v["patients"]), v["entries"], p7_class(k[0], r["include"], r["exclude"])]
            for k, v in _sorted(t["organizers"])])
    _write("encounters.csv", ["snomed_code", "display", "patients", "entries"],
           [[*k, *name(v), len(v["patients"]), v["entries"]] for k, v in _sorted(t["encounters"])])
    _write("sections.csv", ["loinc", "titles", "files", "entries", "read"],
           [[code, _top(s["titles"], 3), s["files"], s["entries"],
             "no (P7)" if code in ccda.DROPPED_SECTIONS else "yes"]
            for code, s in sorted(r["sections"].items(), key=lambda kv: -kv[1]["files"])])
    summary = {
        "ran_at": datetime.now().isoformat(timespec="seconds"), "git_commit": git_commit(), "seed": SEED,
        "data_dir": config.PATIENT_DATA_DIR, "files": r["files"], "parsed": r["parsed"],
        "distinct_patient_ids": r["distinct_patient_ids"], "parse_errors": r["errors"],
        "software_name": dict(r["software"]),
        "record_date": {"min": min(r["dates"]).isoformat(), "max": max(r["dates"]).isoformat()} if r["dates"] else None,
        "record_year": dict(sorted(collections.Counter(str(d.year) for d in r["dates"]).items())),
        "deceased": {"patients": r["deceased"], "rule": f"Results organizer {DEATH_CERTIFICATE} present",
                     "record_date_min": min(r["deceased_dates"]).isoformat() if r["deceased_dates"] else None,
                     "record_date_max": max(r["deceased_dates"]).isoformat() if r["deceased_dates"] else None},
        "sex": dict(r["sexes"]), "age_band": dict(sorted(r["ages"].items())),
        "food_allergy_kind_code": ccda.FOOD_ALLERGY,
        "active_problems_dropped_by_suffix": dict(r["suffix_dropped"].most_common()),
        "dropped_section_entries": dict(r["dropped_entries"]),
        "p7_results_organizers": {c: {"organizers": v["organizers"], "patients": len(v["patients"])}
                                  for c, v in r["p7"].items()},
        "p7_lists": {"include": sorted(r["include"]), "exclude": sorted(r["exclude"]),
                     "overlap": sorted(set(r["include"]) & set(r["exclude"]))},
        "spec_loinc_patients": {c: len(r["loinc_patients"].get(c, ())) for c in SPEC_LOINC},
        "p8_excludes_deceased": r["deceased"],
        "p8_candidates": {k: r["strata"].get(k, 0) for k in ["food_allergy", "diabetes", "hypertension", "ckd",
                                                              "multi", "none"]},
        "p8_candidate_codes": {k: [{"code": c, "display": d, "patients": n} for (c, d), n in v.most_common()]
                               for k, v in r["strata_codes"].items()},
        "p8_rules": {"food_allergy": f"active allergy with kind {ccda.FOOD_ALLERGY}",
                     **{k: f"active (disorder) matching /{rx.pattern}/i" for k, rx in STRATA.items()},
                     "multi": ">= 2 of diabetes, hypertension, ckd", "none": "none of the above"},
        "rule_check": rule_check(),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


# ---- docs/patient_inventory.md -------------------------------------------------------------------------------

def _read(name: str) -> list[dict]:
    return list(csv.DictReader(open(OUT / name, encoding="utf-8")))


def _n(x) -> str:
    return f"{int(x):,}".replace(",", ".")


def render() -> str:
    s = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    al, pr, md, org = _read("allergies.csv"), _read("problems.csv"), _read("medications.csv"), _read("organizers.csv")
    food = [a for a in al if a["kind_code"] == ccda.FOOD_ALLERGY]
    rc = s["rule_check"]
    drafted = set(rc.get("codes", []))
    L = ["# Inventory hồ sơ bệnh nhân C-CDA (MV0)", "",
         f"Sinh tự động bởi `scripts/patient_inventory.py` lúc {s['ran_at']} (commit `{s['git_commit']}`). "
         "Số liệu gốc ở `eval/patient_inventory/`. Không sửa tay file này.", "",
         "## 1. Tổng quan (P1)", "",
         "| Mục | Giá trị |", "|---|---|",
         f"| Số file `.xml` | {_n(s['files'])} |",
         f"| Parse được | {_n(s['parsed'])} (lỗi: {len(s['parse_errors'])}) |",
         f"| Mã bệnh nhân khác nhau | {_n(s['distinct_patient_ids'])} |",
         f"| `softwareName` | {', '.join(f'`{k}` ({v})' for k, v in s['software_name'].items())} – không có số phiên bản |",
         f"| Ngày hồ sơ (`effectiveTime`) | {s['record_date']['min']} → {s['record_date']['max']} |",
         f"| Năm của ngày hồ sơ | {', '.join(f'{k}: {v}' for k, v in s['record_year'].items())} |",
         f"| Bệnh nhân đã mất ({s['deceased']['rule']}) | {s['deceased']['patients']} (ngày hồ sơ "
         f"{s['deceased']['record_date_min']} → {s['deceased']['record_date_max']}) |",
         f"| Giới tính | {', '.join(f'{k}: {v}' for k, v in s['sex'].items())} |",
         f"| Nhóm tuổi (tại ngày hồ sơ) | {', '.join(f'{k}: {v}' for k, v in s['age_band'].items())} |",
         f"| Entry bị bỏ không đọc (P7) | {', '.join(f'{k}: {_n(v)}' for k, v in s['dropped_section_entries'].items())} |",
         "", "## 2. Ứng viên tầng P8", "",
         "Chỉ để xem có đủ bệnh nhân cho từng tầng hay không. Một bệnh nhân có thể thuộc nhiều tầng. "
         f"Không tính {s['p8_excludes_deceased']} bệnh nhân đã mất (vẫn được nạp và đếm ở P1). "
         "Quy tắc và các mã khớp liệt kê bên dưới.", "",
         "| Tầng | Số bệnh nhân | Quy tắc |", "|---|---:|---|"]
    L += [f"| {k} | {v} | {s['p8_rules'][k]} |" for k, v in s["p8_candidates"].items()]
    for k, codes in s["p8_candidate_codes"].items():
        L += ["", f"Mã khớp tầng `{k}`:", ""] + ([f"- `{c['code']}` {c['display']} – {c['patients']} bệnh nhân"
                                                  for c in codes] or ["- (không có)"])
    L += ["", "## 3. Dị ứng thực phẩm (`414285001`) – đối chiếu `allergy_substance.csv`", "",
          "| SNOMED | Chất | Bệnh nhân | Đang hiệu lực | Có trong luật |", "|---|---|---:|---:|---|"]
    L += [f"| {a['substance_code']} | {a['substance_display']} | {a['patients']} | {a['patients_active']} | "
          f"{'có' if a['substance_code'] in drafted else '**chưa**'} |" for a in food]
    other = collections.Counter()
    for a in al:
        if a["kind_code"] != ccda.FOOD_ALLERGY:
            other[a["kind_display"] or "?"] += int(a["patients"])
    L += ["", "Các loại dị ứng khác (không sinh ràng buộc món ăn): "
          + ", ".join(f"{k} ({v} lượt bệnh nhân)" for k, v in other.most_common()) + "."]
    if rc.get("present"):
        miss = rc["missing_in_ingredient_table"]
        L += ["", f"Kiểm tra luật: {rc['rows']} dòng; chất chưa gán nhóm: "
              f"{', '.join(rc['unmapped']) or 'không có'}; tên trong `extra_ingredients_exclude` không có trong bảng "
              f"`ingredient`: {('không có' if miss == [] else ', '.join(miss)) if miss is not None else 'chưa kiểm (' + rc['db'] + ')'}."]
    L += ["", "## 4. Đối chiếu mã khởi đầu trong đặc tả", "", "| Bảng | Mã / chuỗi | Tên | Bệnh nhân (đang hiệu lực) |",
          "|---|---|---|---:|"]
    by_code = {p["snomed_code"]: p for p in pr}
    al_code = {a["substance_code"]: a for a in al}
    L += [f"| 4.1 | {c} | {d} | {al_code[c]['patients_active'] if c in al_code else '**không thấy**'} |"
          for c, d in SPEC_SUBSTANCES.items()]
    L += [f"| 4.2 | {c} | {d} | {by_code[c]['patients_active'] if c in by_code else '**không thấy**'} |"
          for c, d in SPEC_CONDITIONS.items()]
    for drug in SPEC_DRUGS:
        hits = [m for m in md if drug in (m["display"] or "").lower()]
        L.append(f"| 4.3 | {drug} | {'; '.join(m['display'] for m in hits) or '–'} | "
                 f"{sum(int(m['patients_active']) for m in hits) if hits else '**không thấy**'} |")
    obs = _read("observations.csv")
    L += ["", "## 4b. Sinh hiệu và xét nghiệm đặc tả cần", "",
          "Cột \"Nằm ở\" ghi section và organizer chứa chỉ số. Số bệnh nhân đếm trên mọi section và organizer.", "",
          "| LOINC | Chỉ số | Nằm ở | Bệnh nhân có |", "|---|---|---|---:|"]
    for code, name in SPEC_LOINC.items():
        hits = [o for o in obs if o["loinc"] == code]
        where = ", ".join(sorted({o["section"] + (f" ({o['organizer_loinc']})" if o["organizer_loinc"] else "")
                                  for o in hits}))
        n = s["spec_loinc_patients"].get(code, 0)
        L.append(f"| {code} | {name} | {where or '–'} | {n if n else '**không có trong dữ liệu**'} |")
    L += ["", "## 5. Bệnh `(disorder)` liên quan dinh dưỡng tìm thấy (để bổ sung mã đồng nghĩa)", "",
          "| Nhóm tìm | SNOMED | Tên | Bệnh nhân | Đang hiệu lực |", "|---|---|---|---:|---:|"]
    for label, rx in SYNONYM_SEARCH.items():
        for p in pr:
            if p["suffix"] == "disorder" and re.search(rx, p["display"] or "", re.I):
                L.append(f"| {label} | {p['snomed_code']} | {p['display']} | {p['patients']} | {p['patients_active']} |")
    L += ["", "## 6. Vấn đề đang hiệu lực bị bỏ theo hậu tố (P4)", "",
          ", ".join(f"`({k})`: {_n(v)}" for k, v in s["active_problems_dropped_by_suffix"].items()) + ".",
          "", "## 7. Organizer trong Diagnostic Results (P7)", "",
          "Chỉ organizer có trong `data/rules/include_loinc.csv` (danh sách cho phép) được vào cây hồ sơ. "
          "Organizer trong `data/rules/exclude_loinc.csv` là dữ liệu nhạy cảm, chỉ được đếm. "
          "Các organizer còn lại là `not_relevant`.", "",
          "| Phân loại | Số organizer | Số bệnh nhân |", "|---|---:|---:|"]
    L += [f"| {c} | {_n(v['organizers'])} | {v['patients']} |" for c, v in s["p7_results_organizers"].items()]
    lists = s["p7_lists"]
    L += ["", f"Hai danh sách trùng mã: {', '.join(lists['overlap']) or 'không'}.", "",
          "| LOINC | Tên | Bệnh nhân | Phân loại |", "|---|---|---:|---|"]
    L += [f"| {o['loinc']} | {o['display']} | {o['patients']} | {o['p7_class']} |" for o in org]
    L += ["", "Các bảng đầy đủ: `eval/patient_inventory/{allergies,problems,medications,observations,organizers,"
          "encounters,sections}.csv`.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--render", action="store_true", help="only rebuild docs/patient_inventory.md")
    args = ap.parse_args()
    if not args.render:
        folder = ROOT / config.PATIENT_DATA_DIR
        if not folder.is_dir():
            sys.exit(f"no folder {folder}; set PATIENT_DATA_DIR")
        s = write(scan(folder), folder)
        print(f"{s['parsed']}/{s['files']} files parsed, {len(s['parse_errors'])} errors -> {OUT.relative_to(ROOT)}")
    DOC.write_text(render(), encoding="utf-8")
    print(f"wrote {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
