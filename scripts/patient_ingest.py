"""V1: Synthea C-CDA files -> patient and patient_node rows, and the P1-P7 counts.

    uv run scripts/patient_ingest.py load [--dir PATH:SOURCE ...]    # parse, build trees (template summaries), store
    uv run scripts/patient_ingest.py tree [--summarize llm] [--source sample|generated]   # rebuild the trees
    uv run scripts/patient_ingest.py profiles                        # PatientProfile of every living patient (V3)
    uv run scripts/patient_ingest.py stats                           # eval/patient_corpus.json, docs/patient_corpus_report.md

Default folders: PATIENT_DATA_DIR as source "sample", plus PATIENT_GENERATED_DIR as "generated" if it exists.
Each patient is written in its own transaction and replaced on a rerun (upsert by patient_id). A patient id
that turns up in two folders is an error: nothing is overwritten. A file that fails to parse is listed by a
short hash of its bytes (file names carry Synthea's fake names) and the run goes on.
`profiles` builds each living patient's PatientProfile (cached in patient_profile_cache, counts only in
eval/patient_profiles.json). `tree --summarize llm` asks qwen2.5:7b for each context node (cached; hours on a CPU), see api/patient/summarize.py.
"""

import argparse
import collections
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import psycopg  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

from api import config  # noqa: E402
from api.patient import ccda, nutrition, profile_store, rules  # noqa: E402
from api.patient.summarize import summarize  # noqa: E402
from api.patient.tree import build_tree  # noqa: E402

OUT_JSON = ROOT / "eval" / "patient_corpus.json"
OUT_MD = ROOT / "docs" / "patient_corpus_report.md"
SOURCES = ROOT / "data" / "sources.json"
SEED = 42  # nothing here samples; recorded for the run settings convention
RULE_FILES = rules.RULE_SET_FILES
OUT_PROFILES = ROOT / "eval" / "patient_profiles.json"


class DuplicatePatient(RuntimeError):
    pass


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def sources_info() -> dict:
    return json.loads(SOURCES.read_text(encoding="utf-8")) if SOURCES.exists() else {}


def default_dirs() -> list[tuple[Path, str]]:
    dirs = [(ROOT / config.PATIENT_DATA_DIR, "sample")]
    generated = ROOT / config.PATIENT_GENERATED_DIR
    if generated.is_dir():
        dirs.append((generated, "generated"))
    return dirs


def parse_dir_arg(value: str) -> tuple[Path, str]:
    path, _, source = value.rpartition(":")
    if source not in {"sample", "generated"} or not path:
        raise argparse.ArgumentTypeError(f"expected PATH:sample or PATH:generated, got {value!r}")
    p = Path(path)
    return (p if p.is_absolute() else ROOT / p), source


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def read_all(dirs: list[tuple[Path, str]], p7: rules.P7Rules):
    """Every record in the folders, with its counts; errors listed. Raises on a patient id seen twice."""
    seen: dict[str, str] = {}
    records, errors = [], []
    for folder, source in dirs:
        for path in sorted(folder.glob("*.xml")):
            try:
                record, counts = ccda.read_record(path, source, p7)
            except Exception as e:  # noqa: BLE001 - listed, the run goes on
                errors.append({"source": source, "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:12],
                               "error": f"{type(e).__name__}: {e}"[:200]})
                continue
            if record.patient_id in seen:
                raise DuplicatePatient(f"patient {record.patient_id} is in {seen[record.patient_id]} and {rel(folder)}")
            seen[record.patient_id] = rel(folder)
            records.append((record, counts, folder, path))
    return records, errors


def write_patient(conn: psycopg.Connection, record, nodes, folder: Path, path: Path, synthea_version: str | None):
    with conn.transaction():
        old = conn.execute("SELECT source_dir FROM patient WHERE patient_id = %s", [record.patient_id]).fetchone()
        if old and old[0] != rel(folder):
            raise DuplicatePatient(f"patient {record.patient_id} was loaded from {old[0]}, now found in {rel(folder)}")
        conn.execute(
            """INSERT INTO patient (patient_id, source, source_dir, source_file, sex, age_years, record_date, deceased,
                                    synthea_version, loaded_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
               ON CONFLICT (patient_id) DO UPDATE SET source = EXCLUDED.source, source_dir = EXCLUDED.source_dir,
                 source_file = EXCLUDED.source_file, sex = EXCLUDED.sex, age_years = EXCLUDED.age_years,
                 record_date = EXCLUDED.record_date, deceased = EXCLUDED.deceased,
                 synthea_version = EXCLUDED.synthea_version, loaded_at = now()""",
            [record.patient_id, record.source, rel(folder), path.name, record.sex, record.age_years,
             record.record_date, record.deceased, synthea_version])
        write_nodes(conn, record.patient_id, nodes)


def write_nodes(conn: psycopg.Connection, patient_id: str, nodes):
    conn.execute("DELETE FROM patient_node WHERE patient_id = %s", [patient_id])
    conn.execute("DELETE FROM patient_profile_cache WHERE patient_id = %s", [patient_id])  # built from the old tree
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO patient_node (patient_id, node_id, parent_id, kind, title, summary, summary_source, facts,
                                         entry_ids, position) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [(patient_id, n.node_id, n.parent_id, n.kind, n.title, n.summary, n.summary_source, Jsonb(n.facts),
              n.entry_ids, i) for i, n in enumerate(nodes)])


def cmd_load(conn, dirs) -> dict:
    rs = rules.load_rules()
    records, errors = read_all(dirs, rs.p7)
    versions = {s: (info or {}).get("synthea_commit") for s, info in sources_info().items()}
    nodes_total = 0
    for record, _, folder, path in records:
        nodes = summarize(build_tree(record), rs, "template")
        write_patient(conn, record, nodes, folder, path, versions.get(record.source))
        nodes_total += len(nodes)
    print(f"loaded {len(records)} patients ({nodes_total} nodes), {len(errors)} files failed to parse")
    for e in errors:
        print(f"  {e['source']} {e['file_sha256']}: {e['error']}")
    return {"patients": len(records), "nodes": nodes_total, "errors": errors}


def cmd_tree(conn, mode: str, source: str | None) -> None:
    rs = rules.load_rules()
    sql = "SELECT patient_id, source, source_dir, source_file FROM patient"
    rows = conn.execute(sql + (" WHERE source = %s" if source else "") + " ORDER BY patient_id",
                        [source] if source else []).fetchall()
    client = httpx.Client(timeout=600) if mode == "llm" else None
    started, n_llm = time.time(), 0
    try:
        for i, (pid, src, folder, name) in enumerate(rows, 1):
            record, _ = ccda.read_record(ROOT / folder / name, src, rs.p7)
            nodes = summarize(build_tree(record), rs, mode, client)
            n_llm += sum(n.summary_source == "llm" for n in nodes)
            with conn.transaction():
                write_nodes(conn, pid, nodes)
            if mode == "llm":
                print(f"{i}/{len(rows)} patients, {n_llm} llm summaries, {time.time() - started:.0f}s", flush=True)
    finally:
        if client:
            client.close()
    print(f"rebuilt trees of {len(rows)} patients ({mode} summaries; llm: {n_llm})")


# ---- profiles (V3) ---------------------------------------------------------------------------------------------

SOFT_BELOW = 0.5  # a nutrient rule leaving under this share of Recipes is soft: ranking + warning (Thy, ADR-0007)
COLUMN_SQL = nutrition.COLUMN_SQL
RECIPES_SQL = "FROM recipe r LEFT JOIN recipe_tag t ON t.recipe_id = r.id LEFT JOIN recipe_nutrition n ON n.recipe_id = r.id"


def _rate(conn, conds: list[str], params: list) -> dict:
    """pass / fail / unknown over every Recipe for conditions joined with AND (null = an input is missing)."""
    cond = " AND ".join(conds) or "true"
    passed, failed, unknown, total = conn.execute(
        f"""SELECT count(*) FILTER (WHERE ({cond}) IS TRUE), count(*) FILTER (WHERE ({cond}) IS FALSE),
                   count(*) FILTER (WHERE ({cond}) IS NULL), count(*) {RECIPES_SQL}""", [*params, *params, *params]
    ).fetchone()  # the conditions appear once per FILTER clause
    known = passed + failed
    return {"pass": passed, "fail": failed, "unknown": unknown,
            "pass_rate_known": round(passed / known, 4) if known else None,
            "pass_rate_unknown_dropped": round(passed / total, 4), "pass_rate_unknown_kept": round((passed + unknown) / total, 4)}


def _hard_conds(p) -> tuple[list[str], list]:
    conds, params = [], []
    if p.allergens_exclude:
        conds.append("NOT (coalesce(t.allergens, '{}') && %s::text[])")
        params.append(sorted(p.allergens_exclude))
    if p.ingredients_exclude:
        conds.append("NOT (coalesce(t.ingredients_norm, '{}') && %s::text[])")
        params.append(sorted(p.ingredients_exclude))
    return conds, params


def _limit_conds(limits: dict) -> list[str]:
    return [f"({COLUMN_SQL[c]}) {'<=' if op == 'max' else '>='} {v!r}" for c, (op, v) in sorted(limits.items())]


def rule_pass_rates(conn, rs) -> dict:
    """Share of all Recipes each patient-derived rule lets through on its own."""
    nutrient = nutrient_pass(conn)["per_rule"]
    for r in nutrient:
        rate = r.get("pass_rate_known")
        r["below_soft_threshold"] = rate is not None and rate < SOFT_BELOW
    allergen = {a: _rate(conn, ["NOT (coalesce(t.allergens, '{}') && %s::text[])"], [[a]])
                for a in rules.ALLERGENS}
    groups = {f"allergy {a.display}: extra ingredients": a.extra_ingredients for a in rs.allergy.values() if a.extra_ingredients}
    groups |= {f"drug {d.match}: {d.action}": d.targets for d in rs.drug if d.action == "exclude"}
    ingredient = {k: _rate(conn, ["NOT (coalesce(t.ingredients_norm, '{}') && %s::text[])"], [sorted(v)])
                  for k, v in groups.items()}
    return {"nutrient": nutrient, "allergen_group": allergen, "excluded_ingredients": ingredient,
            "soft_threshold": SOFT_BELOW,
            "note": "allergen and ingredient exclusions stay hard whatever their pass rate: they are safety rules"}


def patient_pass(conn, p) -> dict:
    """Share of all Recipes one patient's combined rules let through: hard ones, then hard plus soft."""
    conds, params = _hard_conds(p)
    hard = _rate(conn, conds + _limit_conds(p.nutrient_limits), params)
    with_soft = _rate(conn, conds + _limit_conds({**p.nutrient_limits, **p.nutrient_soft}), params)
    return {"patient_id": p.patient_id, "allergens_exclude": sorted(p.allergens_exclude),
            "ingredients_excluded": len(p.ingredients_exclude),
            "nutrient_limits": {k: [op, round(v, 2)] for k, (op, v) in sorted(p.nutrient_limits.items())},
            "nutrient_soft": {k: [op, round(v, 2)] for k, (op, v) in sorted(p.nutrient_soft.items())},
            "hard": hard, "hard_and_soft": with_soft}


def _spread(values: list[float]) -> dict:
    v = sorted(values)
    if not v:
        return {}
    q = lambda f: v[min(len(v) - 1, int(f * len(v)))]  # noqa: E731
    return {"min": v[0], "p10": q(0.1), "median": q(0.5), "max": v[-1],
            "below_50pct": sum(x < 0.5 for x in v), "below_25pct": sum(x < 0.25 for x in v)}


def cmd_profiles(conn, mode: str = "vectorless") -> dict:
    """Build (or reuse) every living patient's PatientProfile; write to eval/patient_profiles.json the counts, each
    rule's pass rate over all Recipes, and each patient's combined pass rate (hard rules, then hard plus soft)."""
    rs = rules.load_rules()
    rules.validate_against_db(rs, conn)
    pids = [r[0] for r in conn.execute("SELECT patient_id FROM patient WHERE NOT deceased ORDER BY patient_id")]
    allergen, ingredient, limit, soft, warning, unmapped = (collections.Counter() for _ in range(6))
    per_patient = []
    n_any = 0
    for pid in pids:
        p = profile_store.load_or_build(conn, pid, rs, mode)
        allergen.update(p.allergens_exclude)
        ingredient.update(p.ingredients_exclude)
        limit.update(f"{k} {op} {v:g}" for k, (op, v) in p.nutrient_limits.items())
        warning.update(p.warnings)
        unmapped.update(p.unmapped)
        n_any += bool(p.allergens_exclude or p.ingredients_exclude or set(p.nutrient_limits) != {"sodium_mg"})
        soft.update(f"{k} {op} {v:g}" for k, (op, v) in p.nutrient_soft.items())
        per_patient.append(patient_pass(conn, p))
    out = {"ran_at": datetime.now().isoformat(timespec="seconds"), "git_commit": git_commit(), "seed": SEED,
           "mode": mode, "ruleset_version": rs.version, "rules_log": list(rs.log),
           "patients_alive": len(pids), "patients_with_more_than_the_default": n_any,
           "patients_by_allergen": dict(allergen.most_common()),
           "patients_by_excluded_ingredient": dict(ingredient.most_common()),
           "patients_by_nutrient_limit": dict(limit.most_common()),
           "patients_by_soft_preference": dict(soft.most_common()),
           "patients_by_warning": dict(warning.most_common()), "unmapped": dict(unmapped.most_common()),
           "rule_pass_rates": rule_pass_rates(conn, rs),
           "patient_pass_spread": {
               "hard": _spread([x["hard"]["pass_rate_known"] for x in per_patient]),
               "hard_and_soft": _spread([x["hard_and_soft"]["pass_rate_known"] for x in per_patient])},
           "per_patient": per_patient,
           "note": "pass rates are shares of all Recipes (known = among Recipes with the needed numbers); "
                   "patient_id is the Synthea uuid, no name or other identity"}
    OUT_PROFILES.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"profiles of {len(pids)} living patients (ruleset {rs.version}) -> {rel(OUT_PROFILES)}")
    return out


# ---- nutrient rule pass rates ----------------------------------------------------------------------------------

REFERENCE_WEIGHTS_KG = [60, 70, 80]  # a per-kg limit needs a weight; the profile uses the record's own (MV2)
COMBINED_WEIGHT_KG = 70


def _count(conn, cond: str) -> dict:
    """pass / fail / unknown over every Recipe for a SQL condition (three-valued: null = an input is missing)."""
    passed, failed, unknown, total = conn.execute(
        f"""SELECT count(*) FILTER (WHERE ({cond}) IS TRUE), count(*) FILTER (WHERE ({cond}) IS FALSE),
                   count(*) FILTER (WHERE ({cond}) IS NULL), count(*)
            FROM recipe r LEFT JOIN recipe_nutrition n ON n.recipe_id = r.id""").fetchone()
    known = passed + failed
    return {"pass": passed, "fail": failed, "unknown": unknown, "recipes": total,
            "pass_rate_known": round(passed / known, 4) if known else None,
            "pass_rate_unknown_dropped": round(passed / total, 4) if total else None,
            "pass_rate_unknown_kept": round((passed + unknown) / total, 4) if total else None}


def _cond(rule, limit: float) -> str:
    return f"({nutrition.SQL[rule.nutrient]}) {'<=' if rule.op == 'max' else '>='} {limit}"


def nutrient_pass(conn) -> dict:
    """Share of all Recipes each rule of condition_nutrient.csv lets through, alone and per condition.

    unknown = an input is null (or calories 0 for a ratio). With unknown_strict on such a Recipe is dropped
    (pass_rate_unknown_dropped), off it is kept with a warning (pass_rate_unknown_kept), spec 4.5.
    """
    rules_ = rules.load_condition_nutrient()
    per_rule = []
    for r in rules_:
        row = {"label": r.label, "conditions": list(r.conditions), "nutrient": r.nutrient, "op": r.op,
               "daily_value": r.daily_value, "unit": r.unit, "mode": r.mode, "source": r.source}
        if r.op is None:
            per_rule.append({**row, "measured": "warn only, no limit"})
        elif r.nutrient not in nutrition.SQL:
            per_rule.append({**row, "measured": "no column in recipe_nutrition"})
        elif r.nutrient == "protein_g_per_kg":
            for w in REFERENCE_WEIGHTS_KG:
                lim = nutrition.per_serving_limit(r, w)
                per_rule.append({**row, "weight_kg": w, "per_serving_limit": round(lim, 2), **_count(conn, _cond(r, lim))})
        else:
            lim = nutrition.per_serving_limit(r)
            per_rule.append({**row, "per_serving_limit": round(lim, 2), **_count(conn, _cond(r, lim))})

    def strictest(group, modes=("filter",)) -> dict[str, tuple]:
        best: dict[str, tuple] = {}
        for r in group:
            if r.mode not in modes or r.nutrient not in nutrition.SQL:
                continue
            lim = nutrition.per_serving_limit(r, COMBINED_WEIGHT_KG)
            old = best.get(r.nutrient)
            if old is None or (lim < old[1] if r.op == "max" else lim > old[1]):
                best[r.nutrient] = (r, lim)
        return best

    default = [r for r in rules_ if r.conditions == ("*",)]
    by_condition = []
    for label in ["default", *dict.fromkeys(r.label for r in rules_ if r.conditions != ("*",))]:
        group = default + [r for r in rules_ if r.label == label and r.conditions != ("*",)]
        best = strictest(group)
        cond = " AND ".join(_cond(r, lim) for r, lim in best.values()) or "true"
        both = strictest(group, ("filter", "soft"))
        cond_soft = " AND ".join(_cond(r, lim) for r, lim in both.values()) or "true"
        by_condition.append({"label": label, "conditions": sorted({c for r in group for c in r.conditions}),
                             "filters": [{"nutrient": n, "op": r.op, "per_serving_limit": round(lim, 2), "from": r.label}
                                         for n, (r, lim) in best.items()],
                             "soft": sorted({r.nutrient for r in group if r.mode == "soft"}),
                             "warn_only": sorted({r.nutrient for r in group if r.mode == "warn"}),
                             **_count(conn, cond), "with_soft": _count(conn, cond_soft)})
    return {"per_meal_fraction": round(config.PER_MEAL_FRACTION, 4), "reference_weights_kg": REFERENCE_WEIGHTS_KG,
            "combined_weight_kg": COMBINED_WEIGHT_KG, "rules_file": "data/rules/condition_nutrient.csv",
            "rules_sha256": rules.sha256("condition_nutrient.csv"),
            "note": "per serving (recipe_nutrition); sugar_pct_kcal uses total sugars; filter rules combined with "
                    "the strictest limit per nutrient (with_soft: soft rules added as if they filtered); warn rules "
                    "are not part of the combined pass rate",
            "per_rule": per_rule, "by_condition": by_condition}


# ---- stats -----------------------------------------------------------------------------------------------------

def _sum(into: dict, counts: dict):
    for rule, c in counts.items():
        for k, v in c.items():
            into[rule][k] += v


def cmd_stats(conn, dirs) -> dict:
    p7 = rules.load_p7()
    records, errors = read_all(dirs, p7)
    per_source: dict = {}
    for folder, source in dirs:
        files = sorted(folder.glob("*.xml"))
        recs = [r for r in records if r[0].source == source]
        agg = {f"P{i}": collections.Counter() for i in range(2, 8)}
        for _, counts, _, _ in recs:
            _sum(agg, counts)
        software = collections.Counter(ccda.software_name(ccda.parse(p)) or "" for _, _, _, p in recs)
        per_source[source] = {
            "dir": rel(folder),
            "P1": {"files": len(files), "parsed": len(recs), "parse_errors": [e for e in errors if e["source"] == source],
                   "deceased": sum(r[0].deceased for r in recs), "alive": sum(not r[0].deceased for r in recs),
                   "software_name": dict(software)},
            **{k: dict(sorted(v.items())) for k, v in agg.items()},
        }
    total = {"P1": {k: sum(s["P1"][k] for s in per_source.values()) for k in ["files", "parsed", "deceased", "alive"]}}
    for rule in [f"P{i}" for i in range(2, 8)]:
        c = collections.Counter()
        for s in per_source.values():
            c.update(s[rule])
        total[rule] = dict(sorted(c.items()))
    db = {
        "patients": [{"source": s, "deceased": d, "n": n} for s, d, n in conn.execute(
            "SELECT source, deceased, count(*) FROM patient GROUP BY 1, 2 ORDER BY 1, 2")],
        "nodes": [{"kind": k, "summary_source": ss, "n": n} for k, ss, n in conn.execute(
            "SELECT kind, summary_source, count(*) FROM patient_node GROUP BY 1, 2 ORDER BY 1, 2")],
    }
    out = {"ran_at": datetime.now().isoformat(timespec="seconds"), "git_commit": git_commit(), "seed": SEED,
           "rules_sha256": {f: rules.sha256(f) for f in RULE_FILES}, "sources": sources_info(),
           "per_source": per_source, "total": total, "db": db, "nutrient_rule_pass": nutrient_pass(conn),
           "P8": "sampling is MV4 (scripts/patient_sample.py); deceased patients are left out"}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render(out), encoding="utf-8")
    print(f"wrote {rel(OUT_JSON)}, {rel(OUT_MD)}")
    return out


def _n(x) -> str:
    return f"{int(x):,}".replace(",", ".")


def render(c: dict) -> str:
    t = c["total"]
    dropped_suffix = {k.removeprefix("dropped_suffix_"): v for k, v in t["P4"].items() if k.startswith("dropped_suffix_")}
    p7_parts = {k: v for k, v in t["P7"].items() if k != "identity_fields_not_read"}
    nodes = collections.Counter()
    for r in c["db"]["nodes"]:
        nodes[r["kind"]] += r["n"]
    summ = collections.Counter()
    for r in c["db"]["nodes"]:
        if r["kind"] == "context":
            summ[r["summary_source"] or "none"] += r["n"]
    L = ["# Báo cáo dữ liệu hồ sơ bệnh nhân (quy tắc P1–P7)", "",
         f"Sinh tự động bởi `scripts/patient_ingest.py stats` lúc {c['ran_at']} (commit `{c['git_commit']}`). "
         "Số liệu gốc ở `eval/patient_corpus.json`. Không sửa tay file này.", "",
         "| Mã | Quy tắc | Số liệu (tổng các nguồn) |", "|---|---|---|",
         f"| P1 | Nạp mọi file `.xml` | {_n(t['P1']['files'])} file → {_n(t['P1']['parsed'])} parse được; "
         f"{_n(t['P1']['alive'])} còn sống, {_n(t['P1']['deceased'])} đã mất |",
         f"| P2 | Chỉ giữ dị ứng và vấn đề đang hiệu lực | dị ứng giữ {_n(t['P2'].get('allergies_in_force', 0))}, "
         f"bỏ {_n(t['P2'].get('allergies_dropped_not_in_force', 0))}; vấn đề bỏ "
         f"{_n(t['P2'].get('problems_dropped_not_in_force', 0))} |",
         f"| P3 | Dị ứng thực phẩm (`414285001`) | {_n(t['P3'].get('food_allergies', 0))} entry; ánh xạ nhóm ở MV2 |",
         f"| P4 | Vấn đề: chỉ giữ `(disorder)` | giữ {_n(t['P4'].get('disorders_kept', 0))}; bỏ "
         + ", ".join(f"`({k})` {_n(v)}" for k, v in dropped_suffix.items()) + " |",
         f"| P5 | Thuốc đang dùng | {_n(t['P5'].get('in_use', 0))} đang dùng; {_n(t['P5'].get('dropped_not_in_use', 0))} đã ngừng |",
         f"| P6 | Sinh hiệu gần nhất, xét nghiệm, lần khám | {_n(t['P6'].get('vitals_latest', 0))} chỉ số sinh hiệu; "
         f"{_n(t['P6'].get('result_organizers', 0))} organizer xét nghiệm (danh sách cho phép); "
         f"{_n(t['P6'].get('encounters', 0))} lần khám |",
         f"| P7 | Loại dữ liệu nhạy cảm | " + "; ".join(f"`{k}` {_n(v)}" for k, v in p7_parts.items())
         + f"; không đọc danh tính ở {_n(t['P7'].get('identity_fields_not_read', 0))} hồ sơ |",
         "", "## Theo nguồn", "", "| Nguồn | Thư mục | File | Parse được | Lỗi | Còn sống | Đã mất |",
         "|---|---|---:|---:|---:|---:|---:|"]
    for s, v in c["per_source"].items():
        p1 = v["P1"]
        L.append(f"| {s} | `{v['dir']}` | {p1['files']} | {p1['parsed']} | {len(p1['parse_errors'])} | {p1['alive']} | "
                 f"{p1['deceased']} |")
    src = c["sources"].get("sample") or {}
    L += ["", "## Cây hồ sơ trong DB", "",
          "| Loại nút | Số nút |", "|---|---:|"] + [f"| {k} | {_n(v)} |" for k, v in sorted(nodes.items())]
    L += ["", "Tóm tắt nút ngữ cảnh: " + ", ".join(f"{k} {_n(v)}" for k, v in sorted(summ.items())) + "."]
    L += render_nutrient(c["nutrient_rule_pass"]) if c.get("nutrient_rule_pass") else []
    L += ["", "## Nguồn dữ liệu", "",
          f"- Bộ mẫu: {src.get('description', '?')}, tải từ {src.get('download_page', '?')} ngày {src.get('downloaded', '?')}.",
          f"- Synthea commit `{src.get('synthea_commit', '?')}` ({src.get('synthea_commit_note', '')}).",
          f"- Kiểm chứng: {src.get('verified', '?')}.",
          f"- Bệnh nhân sinh thêm: {'chưa có' if not c['sources'].get('generated') else 'xem data/sources.json'}.",
          "", "File luật (sha256): " + ", ".join(f"`{k}` `{v[:12]}`" for k, v in c["rules_sha256"].items()) + ".", ""]
    return "\n".join(L)


def _pct(x) -> str:
    return "–" if x is None else f"{x * 100:.1f}%".replace(".", ",")


def render_nutrient(p: dict) -> list[str]:
    L = ["", "## Tỉ lệ công thức qua từng luật dinh dưỡng (bản nháp `condition_nutrient.csv`)", "",
         f"Trên toàn bộ công thức, giá trị theo khẩu phần. Ngưỡng ngày × {str(p['per_meal_fraction']).replace('.', ',')} "
         "cho một bữa; ngưỡng % năng lượng tính trên calo của chính công thức. \"Không rõ\" là công thức thiếu số liệu "
         "(hoặc calo bằng 0). Cột \"qua\" tính trên công thức có số liệu; hai cột sau tính trên toàn bộ, khi bỏ hoặc giữ "
         "công thức không rõ (`unknown_strict` bật / tắt).", "",
         "| Bệnh | Chất | Ngưỡng ngày | Ngưỡng / khẩu phần | Chế độ | Qua | Trượt | Không rõ | Tỉ lệ qua | Bỏ không rõ | Giữ không rõ |",
         "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for r in p["per_rule"]:
        if "measured" in r:
            L.append(f"| {r['label']} | {r['nutrient']} | – | – | {r['mode']} | – | – | – | {r['measured']} | | |")
            continue
        daily = f"{r['op']} {r['daily_value']:g} {r['unit']}" + (f" (nặng {r['weight_kg']} kg)" if "weight_kg" in r else "")
        L.append(f"| {r['label']} | {r['nutrient']} | {daily} | {str(r['per_serving_limit']).replace('.', ',')} | "
                 f"{r['mode']} | {_n(r['pass'])} | {_n(r['fail'])} | {_n(r['unknown'])} | {_pct(r['pass_rate_known'])} | "
                 f"{_pct(r['pass_rate_unknown_dropped'])} | {_pct(r['pass_rate_unknown_kept'])} |")
    L += ["", f"Gộp theo bệnh: mọi luật `filter` (cứng) của bệnh cộng luật mặc định, mỗi chất lấy ngưỡng chặt nhất; "
          "luật `soft` không lọc, chỉ xếp hạng và cảnh báo (cột cuối: tỉ lệ nếu luật mềm cũng lọc); "
          f"luật protein theo kg tính với {p['combined_weight_kg']} kg. Luật `warn` không tính vào tỉ lệ gộp.", "",
          "| Bệnh | Bộ lọc cứng | Luật mềm | Qua | Không rõ | Tỉ lệ qua | Bỏ không rõ | Giữ không rõ | Nếu luật mềm cũng lọc |",
          "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for b in p["by_condition"]:
        filters = "; ".join(f"{f['nutrient']} {f['op']} {str(f['per_serving_limit']).replace('.', ',')} ({f['from']})"
                            for f in b["filters"])
        L.append(f"| {b['label']} | {filters} | {', '.join(b.get('soft', [])) or '–'} | {_n(b['pass'])} | "
                 f"{_n(b['unknown'])} | {_pct(b['pass_rate_known'])} | {_pct(b['pass_rate_unknown_dropped'])} | "
                 f"{_pct(b['pass_rate_unknown_kept'])} | {_pct(b['with_soft']['pass_rate_known'])} |")
    return L


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    load = sub.add_parser("load")
    load.add_argument("--dir", action="append", type=parse_dir_arg, help="PATH:sample or PATH:generated (repeatable)")
    tree = sub.add_parser("tree")
    tree.add_argument("--summarize", choices=["template", "llm"], default="template")
    tree.add_argument("--source", choices=["sample", "generated"])
    prof = sub.add_parser("profiles")
    prof.add_argument("--mode", default="vectorless", choices=["direct", "vectorless"])
    stats = sub.add_parser("stats")
    stats.add_argument("--dir", action="append", type=parse_dir_arg)
    args = ap.parse_args(argv)
    with psycopg.connect(config.DATABASE_URL) as conn:
        if args.cmd == "load":
            cmd_load(conn, args.dir or default_dirs())
        elif args.cmd == "tree":
            cmd_tree(conn, args.summarize, args.source)
        elif args.cmd == "profiles":
            cmd_profiles(conn, args.mode)
        else:
            cmd_stats(conn, args.dir or default_dirs())


if __name__ == "__main__":
    main()
