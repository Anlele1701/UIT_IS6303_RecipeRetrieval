"""MV4: the patient presets on the frozen patient question set (docs/plan/A3_vectorless_ho_so.md 6-7).

    uv run scripts/eval_patient.py run --input coded,narrative --limit 10          # CPU smoke run
    uv run scripts/eval_patient.py run                                             # full run (GPU machine)
    uv run scripts/eval_patient.py run --resume eval/runs/<ts>/patient             # carry on after a stop
    uv run scripts/eval_patient.py score eval/runs/<ts>/patient                    # re-score (after adjudication)

`run` asks every question in a new session, once per preset and input mode (coded entries, or the narrative
section tables; P-Direct reads codes, so it is N/A on the narrative), with the full pipeline (M1-M7), and
appends one line per turn to turns.jsonl. `score` reads turns.jsonl and the DB and writes metrics.json,
per_query.csv and table.md:

- extraction: precision / recall / F1 per type (food allergy substances, conditions, medications) of the
  entities each turn's profile came from, against gold.jsonl; allergy recall is the headline, with the absolute
  number of missed allergies (a miss is a patient eating what they are allergic to);
- node selection: share of needs_context questions whose read nodes hold the answer key's node;
- cost: model calls and characters read in V1-V3, V1-V3 latency, first turn of a patient vs later turns;
- end to end, on the top 5 Recipes: CVR@5 / Safe@5 against the TRUE constraints (the coded profile, rule
  tables, plus the question's own dialogue constraints), whatever the preset read. Allergens and dialogue
  constraints are judged by the independent checker (scripts/checker.py), raw and adjudicated
  (scripts/adjudicate.py; pending "yes" counts; the blind queue is written for every preset); nutrient limits
  are judged by the nutrient columns (a NULL value is counted apart, not as a pass);
- generation: [H:...] citations that name a node of the tree and one the turn read, answers written by code
  (fallback) per route;
- statistics: 95% CIs and paired comparisons by PATIENT (a patient's questions are averaged first):
  bootstrap (scripts/significance.py) and Wilcoxon, Holm within each family. The same tables are written for
  source = sample only (sensitivity).
"""

import argparse
import csv
import json
import platform
import random
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from api import config  # noqa: E402

PATIENT = ROOT / "eval" / "patient"
PRESETS = ["P-Direct", "P-Vectorless", "P-Vectorless-Fixed", "P-Vector", "S-Profile"]
INPUTS = ["coded", "narrative"]
REFERENCE = "P-Vectorless"
TYPES = ["food_allergy_substances", "conditions", "medications"]
K = 5
SEED = 42
H_CITE = re.compile(r"\[H:([^\]\s]+)\]")
FAMILY_METRICS = ["safe_allergen_adj", "safe_nutrition", "safe_dialogue_adj", "allergy_recall", "node_hit"]


# ---- inputs ----------------------------------------------------------------------------------------------------

def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check_frozen() -> dict:
    """The frozen set must be the one Thy approved (sha256 in frozen.json); stop otherwise."""
    import freeze_patient_set as fz
    frozen = json.loads((PATIENT / "frozen.json").read_text(encoding="utf-8"))
    if frozen["sha256"] != fz.digests():
        sys.exit("eval/patient/queries.jsonl or gold.jsonl changed since it was frozen: refusing to run")
    return frozen


def pick(questions: list[dict], limit: int | None, seed: int = SEED) -> list[dict]:
    """All questions, or `limit` of them drawn round-robin over the primary strata in a seeded order (so a smoke
    run still meets each stratum), returned in qid order."""
    if not limit or limit >= len(questions):
        return questions
    by: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        by[q["primary"]].append(q)
    rng = random.Random(seed)
    for k in sorted(by):
        rng.shuffle(by[k])
    order, out = sorted(by), []
    while len(out) < limit:
        for k in order:
            if by[k] and len(out) < limit:
                out.append(by[k].pop())
    return sorted(out, key=lambda q: q["qid"])


def machine() -> dict:
    gpu = None
    try:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    return {"node": platform.node(), "os": platform.platform(), "processor": platform.processor(),
            "python": platform.python_version(), "gpu": gpu}


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT, timeout=10)
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT, timeout=10)
        return out.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return None


# ---- run -------------------------------------------------------------------------------------------------------

def one_turn(bot, q: dict, name: str, inp: str) -> dict:
    from api.pipeline.flags import preset
    bot.patient_input = inp
    sid = bot.new_session(name, q["patient_id"])
    t = time.perf_counter()
    ev: dict = {}
    for e in bot.run_turn(sid, q["message"], preset(name)):
        if e.type != "token":
            ev[e.type] = e.data
    done, c = ev["done"], ev["constraints"]
    fallback = [p.get("kind") for (p,) in bot.conn.execute(
        "SELECT payload FROM retrieval_trace WHERE message_id = %s AND stage = 'fallback'", [done["message_id"]])]
    return {"qid": q["qid"], "patient_id": q["patient_id"], "preset": name, "input": inp,
            "seconds": round(time.perf_counter() - t, 2), "intent": c["intent"], "route": c["route"],
            "constraints": c["constraints"], "patient_profile": ev.get("patient_profile"),
            "recipe_ids": [r["id"] for r in ev.get("recipes", [])], "answer": done["answer"],
            "citations": done["citations"], "verified": done["verified"], "flags": done.get("flags", []),
            "fallback": done.get("fallback", False), "fallback_kind": fallback[0] if fallback else None,
            "usage": done["usage"], "latency_ms": done["latency_ms"]}


def run(args) -> Path:
    import httpx
    import psycopg

    import checker
    from api.pipeline import orchestrator as orch
    from api.pipeline.llm import CACHE as llm_log
    from api.rerank import Reranker

    frozen = check_frozen()
    out = Path(args.resume) if args.resume else ROOT / "eval" / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S") / "patient"
    out.mkdir(parents=True, exist_ok=True)
    turns_path = out / "turns.jsonl"
    done = {(t["qid"], t["preset"], t["input"]) for t in read_jsonl(turns_path)} if turns_path.exists() else set()
    questions = pick(read_jsonl(PATIENT / "queries.jsonl"), args.limit)
    inputs, presets = args.input.split(","), args.presets.split(",")
    settings_path = out / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {
        "started": datetime.now().isoformat(timespec="seconds"), "machine": machine(), "git": git_commit(),
        "seed": config.SEED, "sample_seed": SEED, "per_meal_fraction": config.PER_MEAL_FRACTION,
        "models": {"qu": config.QU_MODEL, "gen": config.GEN_MODEL, "embed": config.EMBED_MODEL,
                   "rerank": config.RERANK_MODEL, "checker": checker.CHECKER_MODEL},
        "inputs": inputs, "presets": presets, "limit": args.limit, "qids": [q["qid"] for q in questions],
        "frozen": frozen["sha256"], "k": K,
        "llm_cache": str(llm_log), "llm_cache_lines_at_start": _lines(llm_log)}
    sys.stdout.reconfigure(encoding="utf-8")
    with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=1800) as client:
        bot = orch.Assistant(conn, client, Reranker().score)
        settings["ruleset_version"] = bot.rules.version
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        todo = [(q, n, i) for i in inputs for n in presets for q in questions
                if not (i == "narrative" and n == "P-Direct") and (q["qid"], n, i) not in done]
        print(f"{len(todo)} turns to run ({len(done)} already in {turns_path})")
        with open(turns_path, "a", encoding="utf-8") as f:
            for j, (q, n, i) in enumerate(todo, 1):
                row = one_turn(bot, q, n, i)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                print(f"[{j}/{len(todo)}] {i:9} {n:19} {q['qid']} {row['route']:12} {row['seconds']:6.1f}s")
    settings["finished"] = datetime.now().isoformat(timespec="seconds")
    settings["llm_cache_lines_at_end"] = _lines(llm_log)
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def _lines(path: Path) -> int:
    return sum(1 for _ in open(path, encoding="utf-8")) if path.exists() else 0


# ---- metrics on one turn (pure: tested on hand-built data) ---------------------------------------------------

def prf(pred: list[str], gold: list[str]) -> dict:
    p, g = set(pred), set(gold)
    return {"tp": len(p & g), "fp": len(p - g), "fn": len(g - p)}


def node_hit(nodes_read: list[str], relevant: list[str], inp: str) -> bool:
    """The read nodes hold the answer key's node. On the narrative a year node is part of its section node."""
    read = set(nodes_read)
    if inp == "narrative":
        return all(f"narrative.{r.split('.')[0]}" in read for r in relevant)
    return all(r in read for r in relevant)


def h_citations(answer: str, tree: set[str], read: set[str]) -> dict:
    ids = H_CITE.findall(answer or "")
    return {"h_cites": len(ids), "h_valid": sum(i in tree for i in ids), "h_read": sum(i in read for i in ids)}


def nutrition_viol(recipe_ids: list[int], limits: dict, values: dict) -> dict:
    """Per Recipe: breaks a hard limit (known value), or has an unknown value on a limit it does not break."""
    from api.patient.nutrition import meets
    viol = unknown = 0
    for rid in recipe_ids:
        verdicts = [meets(values.get(rid, {}).get(col), op, lim) for col, (op, lim) in limits.items()]
        if any(v is False for v in verdicts):
            viol += 1
        elif any(v is None for v in verdicts):
            unknown += 1
    return {"viol": viol, "unknown": unknown}


def holm(ps: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p values, in the input order."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, top = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        top = max(top, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = top
    return adj


def per_patient(rows: list[dict], metric: str) -> dict[str, float]:
    """A patient's questions averaged first (questions of one patient are not independent)."""
    acc: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r.get(metric) is not None:
            acc[r["patient_id"]].append(float(r[metric]))
    return {p: sum(v) / len(v) for p, v in acc.items()}


def compare(a: dict[str, float], b: dict[str, float]) -> dict | None:
    """Paired by patient: bootstrap of the mean difference, and Wilcoxon signed-rank."""
    from scipy.stats import wilcoxon

    from significance import paired_bootstrap
    common = sorted(set(a) & set(b))
    if len(common) < 2:
        return None
    x, y = [a[p] for p in common], [b[p] for p in common]
    out = paired_bootstrap(x, y, seed=SEED)
    diffs = [u - v for u, v in zip(x, y)]
    out["p_wilcoxon"] = 1.0 if not any(diffs) else float(wilcoxon(x, y, zero_method="zsplit").pvalue)
    out["patients"] = len(common)
    return out


# ---- score -----------------------------------------------------------------------------------------------------

def truth(conn, rs, pid: str, cache: dict) -> dict:
    """The true record constraints: the coded profile by the rule tables (what P-Direct applies)."""
    from api.patient import profile_store
    if pid not in cache:
        prof = profile_store.load_or_build(conn, pid, rs, "vectorless")
        cache[pid] = {"allergens": sorted(prof.allergens_exclude), "ingredients": sorted(prof.ingredients_exclude),
                      "limits": {k: tuple(v) for k, v in prof.nutrient_limits.items()},
                      "tree": {n for (n,) in conn.execute("SELECT node_id FROM patient_node WHERE patient_id = %s",
                                                          [pid])}}
    return cache[pid]


def checker_constraints(t: dict, dialogue: dict) -> tuple[list[str], list[str]]:
    """What the independent checker judges: allergen groups (record) and the diet (dialogue), as in M2. Named
    ingredients are matched in the raw lines instead (names_in): asked one by one, the checker read "chicken
    broth" as "clam juice" (MV4c smoke run)."""
    return [f"allergen:{a}" for a in t["allergens"]], [f"diet:{dialogue['diet']}"] if dialogue.get("diet") else []


def names_in(lines: list[str], names: list[str]) -> list[str]:
    """Named ingredients found as whole words (plural s/es allowed) in a Recipe's raw ingredient lines."""
    text = " | ".join(lines).lower()
    return [n for n in names if re.search(rf"\b{re.escape(n.lower())}(e?s)?\b", text)]


def score(run_dir: Path, client=None) -> dict:
    import httpx
    import psycopg

    import adjudicate
    import checker
    from api.patient import narrative, rules
    from api.pipeline.m5_postprocess import nutrient_values
    from significance import interval
    from stats import rate

    turns = read_jsonl(run_dir / "turns.jsonl")
    qs = {q["qid"]: q for q in read_jsonl(PATIENT / "queries.jsonl")}
    gold = {g["patient_id"]: g for g in read_jsonl(PATIENT / "gold.jsonl")}
    rs = rules.load_rules()
    narrative_tree = set(narrative.FIXED_IDS) | {nid for _, nid, k in narrative.SECTIONS if k == "context"}
    settings = json.loads((run_dir / "settings.json").read_text(encoding="utf-8"))
    rows, verdicts, cache, lines = [], {}, {}, {}
    seen: set[tuple] = set()
    with psycopg.connect(config.DATABASE_URL) as conn, (client or httpx.Client(timeout=900)) as http:
        ccache = checker.load_cache()
        for t in turns:
            q = qs[t["qid"]]
            tr = truth(conn, rs, t["patient_id"], cache)
            pp = t["patient_profile"] or {}
            top = t["recipe_ids"][:K]
            key = (t["patient_id"], t["preset"], t["input"])
            r = {"qid": t["qid"], "patient_id": t["patient_id"], "source": q["source"], "primary": q["primary"],
                 "type": q["type"], "lang": q["lang"], "preset": t["preset"], "input": t["input"],
                 "route": t["route"], "recipes": len(top), "first_turn": key not in seen,
                 "v_calls": pp.get("llm_calls"), "extract_chars": pp.get("extract_chars"),
                 **{f"lat_{s}": t["latency_ms"].get(s) for s in ("v1", "v2", "v3", "total")},
                 "gen_tokens": t["usage"]["prompt_tokens"] + t["usage"]["completion_tokens"],
                 "fallback": int(bool(t["fallback"])), "fallback_kind": t["fallback_kind"]}
            seen.add(key)
            ent = pp.get("entities")
            g = gold[t["patient_id"]]
            if ent is not None:
                for ty in TYPES:
                    for k2, v in prf(ent.get(ty, []), g[ty]).items():
                        r[f"{ty}_{k2}"] = v
                r["allergy_recall"] = (r["food_allergy_substances_tp"] / len(g["food_allergy_substances"])
                                       if g["food_allergy_substances"] else None)
                r["allergy_missed"] = r["food_allergy_substances_fn"]
            if q["type"] == "needs_context" and pp:
                r["node_hit"] = int(node_hit(pp.get("nodes_read", []), q.get("relevant_nodes", []), t["input"]))
            tree = narrative_tree | {f"patient:{t['patient_id']}"} if t["input"] == "narrative" else tr["tree"]
            r.update(h_citations(t["answer"], tree, set(pp.get("nodes_read", []))))
            dc = q["dialogue_constraints"]
            record, talk = checker_constraints(tr, dc)
            mt = dc.get("max_total_minutes")
            mins = dict(conn.execute("SELECT id, total_minutes FROM recipe WHERE id = ANY(%s)", [top]).fetchall()) \
                if mt and top else {}
            hits = {}  # per Recipe: broke a named ingredient of the record / of the dialogue (or its time limit)
            for rid in top:
                if record + talk:
                    for c, v in checker.check(conn, http, rid, record + talk, ccache).items():
                        verdicts[(rid, c)] = v
                if rid not in lines:
                    lines[rid] = adjudicate.raw_lines(conn, rid)
                hits[rid] = {"record": bool(names_in(lines[rid], tr["ingredients"])),
                             "talk": bool(names_in(lines[rid], dc.get("ingredients_exclude", [])))
                             or bool(mt and mins.get(rid) is not None and mins[rid] > mt)}
            r["_record"], r["_talk"], r["_top"], r["_hits"] = record, talk, top, hits
            r["has_record_constraint"] = bool(tr["allergens"] or tr["ingredients"])
            r["has_dialogue_constraint"] = bool(dc)
            if tr["limits"] and top:
                vals = nutrient_values(conn, top, list(tr["limits"]))
                nv = nutrition_viol(top, tr["limits"], vals)
                r.update(nutr_viol=nv["viol"], nutr_unknown=nv["unknown"], safe_nutrition=int(nv["viol"] == 0),
                         cvr_nutrition=nv["viol"] / len(top))
            rows.append(r)
        scored = adjudicate.score_all(conn, verdicts)
        queue = run_dir / "checker_queue.csv" if settings.get("limit") else adjudicate.QUEUE  # smoke runs stay out
        queued = adjudicate.write_queue(conn, scored, queue)
    by = {(s.recipe_id, s.constraint): s for s in scored}
    for r in rows:
        top, hits = r.pop("_top"), r.pop("_hits")
        for part, name, has in (("record", "allergen", "has_record_constraint"),
                                ("talk", "dialogue", "has_dialogue_constraint")):
            cs = r.pop(f"_{part}")
            if not r[has] or not top:
                continue
            raw = sum(hits[rid][part] or any(by[(rid, c)].raw for c in cs) for rid in top)
            adj = sum(hits[rid][part] or any(by[(rid, c)].adjudicated for c in cs) for rid in top)
            r.update({f"viol_{name}_raw": raw, f"viol_{name}_adj": adj, f"safe_{name}_raw": int(raw == 0),
                      f"safe_{name}_adj": int(adj == 0), f"cvr_{name}_raw": raw / len(top),
                      f"cvr_{name}_adj": adj / len(top)})
    metrics = {"all": summarize(rows, rate, interval), "sample_only": summarize(
        [r for r in rows if r["source"] == "sample"], rate, interval),
        "checker": adjudicate.summary(scored, len({rid for rid, _ in verdicts})), "queue_new": queued,
        "queue": str(queue.relative_to(ROOT)) if queue.is_relative_to(ROOT) else str(queue)}
    write_outputs(run_dir, rows, metrics)
    return metrics


def summarize(rows: list[dict], rate, interval) -> dict:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["input"], r["preset"])].append(r)
    table = {}
    for (inp, name), rs_ in sorted(groups.items()):
        s: dict = {"questions": len(rs_), "patients": len({r["patient_id"] for r in rs_})}
        for ty in TYPES:
            tp, fp, fn = (sum(r.get(f"{ty}_{k}", 0) or 0 for r in rs_) for k in ("tp", "fp", "fn"))
            if any(f"{ty}_tp" in r for r in rs_):
                p = tp / (tp + fp) if tp + fp else None
                rc = tp / (tp + fn) if tp + fn else None
                f1 = 2 * p * rc / (p + rc) if p and rc else (0.0 if p is not None and rc is not None else None)
                s[ty] = {"precision": p, "recall": rc, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
        s["allergy_missed"] = sum(r.get("allergy_missed") or 0 for r in rs_)
        s["patients_with_missed_allergy"] = len({r["patient_id"] for r in rs_ if r.get("allergy_missed")})
        for m in ("node_hit", "safe_allergen_raw", "safe_allergen_adj", "safe_nutrition", "safe_dialogue_raw",
                  "safe_dialogue_adj", "fallback"):
            vals = [r[m] for r in rs_ if r.get(m) is not None]
            s[m] = rate(sum(vals), len(vals)) if vals else None
            pp = per_patient(rs_, m)
            if len(pp) >= 2:
                s[m + "_by_patient"] = interval(list(pp.values()), seed=SEED)
        for m in ("cvr_allergen_raw", "cvr_allergen_adj", "cvr_nutrition", "cvr_dialogue_raw", "cvr_dialogue_adj"):
            vals = [r[m] for r in rs_ if r.get(m) is not None]
            s[m] = sum(vals) / len(vals) if vals else None
        s["nutr_unknown_recipes"] = sum(r.get("nutr_unknown") or 0 for r in rs_)
        s["h"] = {k: sum(r[k] for r in rs_) for k in ("h_cites", "h_valid", "h_read")}
        s["fallback_by_route"] = {rt: rate(sum(r["fallback"] for r in rs_ if r["route"] == rt),
                                           sum(r["route"] == rt for r in rs_))
                                  for rt in sorted({r["route"] for r in rs_})}
        for when, sel in (("first", True), ("later", False)):
            sub = [r for r in rs_ if r["first_turn"] is sel]
            s[f"cost_{when}"] = {k: _mean([r.get(k) for r in sub]) for k in
                                 ("v_calls", "extract_chars", "lat_v1", "lat_v2", "lat_v3", "lat_total", "gen_tokens")}
            s[f"cost_{when}"]["turns"] = len(sub)
        table[f"{inp}|{name}"] = s
    return {"table": table, "comparisons": comparisons(rows)}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else "–"


def comparisons(rows: list[dict]) -> dict:
    """Per input: the reference preset vs each other one; per preset: coded vs narrative. Holm per family
    (input or 'inputs' x metric) on the Wilcoxon p and, separately, on the bootstrap p."""
    out: dict = {}
    by = defaultdict(list)
    for r in rows:
        by[(r["input"], r["preset"])].append(r)
    families: dict[tuple, list[tuple[str, dict]]] = defaultdict(list)
    for m in FAMILY_METRICS:
        for inp in INPUTS:
            if (inp, REFERENCE) not in by:
                continue
            ref = per_patient(by[(inp, REFERENCE)], m)
            for name in PRESETS:
                if name != REFERENCE and (inp, name) in by:
                    c = compare(ref, per_patient(by[(inp, name)], m))
                    if c:
                        families[(inp, m)].append((f"{REFERENCE} - {name}", c))
        for name in PRESETS:
            if ("coded", name) in by and ("narrative", name) in by:
                c = compare(per_patient(by[("coded", name)], m), per_patient(by[("narrative", name)], m))
                if c:
                    families[("coded-narrative", m)].append((name, c))
    for (fam, m), items in families.items():
        for key, adj in (("p_raw", "p_holm"), ("p_wilcoxon", "p_wilcoxon_holm")):
            for (_, c), a in zip(items, holm([c[key] for _, c in items])):
                c[adj] = a
        out[f"{fam}|{m}"] = dict(items)
    return out


# ---- outputs ---------------------------------------------------------------------------------------------------

def write_outputs(run_dir: Path, rows: list[dict], metrics: dict) -> None:
    (run_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, default=str) + "\n",
                                          encoding="utf-8")
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(run_dir / "per_query.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    (run_dir / "table.md").write_text(render(metrics), encoding="utf-8")


def _pct(x) -> str:
    if x is None:
        return "–"
    if isinstance(x, dict):
        if x.get("value") is None:
            return "–"
        ci = x.get("ci95")
        return f"{x['value'] * 100:.0f}% ({x['k']}/{x['n']})" + (f" [{ci[0] * 100:.0f}–{ci[1] * 100:.0f}]" if ci else "")
    return f"{x * 100:.1f}%"


def render(metrics: dict) -> str:
    out = ["# MV4 – Kết quả nhánh hồ sơ bệnh nhân", "",
           "Sinh tự động bởi `scripts/eval_patient.py score`. Không sửa tay.", ""]
    for part, title in (("all", "Toàn bộ"), ("sample_only", "Độ nhạy: chỉ nguồn sample")):
        t = metrics[part]["table"]
        out += [f"## {title}", "", "### Trích ràng buộc (so với đáp án gold.jsonl)", "",
                "| Đầu vào | Preset | Dị ứng P/R | Dị ứng bỏ sót (ca / BN) | Bệnh F1 | Thuốc F1 |", "|---|---|---|---|---|---|"]
        for key, s in t.items():
            inp, name = key.split("|")
            a = s.get("food_allergy_substances")
            fa = f"{_pct(a['precision'])} / {_pct(a['recall'])}" if a else "–"
            out.append(f"| {inp} | {name} | {fa} | {s['allergy_missed']} / {s['patients_with_missed_allergy']} | "
                       f"{_pct((s.get('conditions') or {}).get('f1'))} | {_pct((s.get('medications') or {}).get('f1'))} |")
        out += ["", "### Đầu cuối (top 5) và chọn nút", "",
                "| Đầu vào | Preset | Câu | Safe@5 dị ứng (adj) | CVR@5 dị ứng raw / adj | Safe@5 dinh dưỡng | "
                "CVR@5 dinh dưỡng | Safe@5 hội thoại (adj) | Chọn nút đúng | Trả lời do code |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for key, s in t.items():
            inp, name = key.split("|")
            out.append(f"| {inp} | {name} | {s['questions']} | {_pct(s['safe_allergen_adj'])} | "
                       f"{_pct(s['cvr_allergen_raw'])} / {_pct(s['cvr_allergen_adj'])} | {_pct(s['safe_nutrition'])} | "
                       f"{_pct(s['cvr_nutrition'])} | {_pct(s['safe_dialogue_adj'])} | {_pct(s['node_hit'])} | "
                       f"{_pct(s['fallback'])} |")
        out += ["", "### Chi phí V1–V3 (trung bình mỗi lượt; lượt đầu của bệnh nhân / các lượt sau)", "",
                "| Đầu vào | Preset | Lời gọi LLM | Ký tự đọc | V1 ms | V2 ms | V3 ms | Tổng ms | [H:] hợp lệ / đã đọc / tổng |",
                "|---|---|---|---|---|---|---|---|---|"]
        for key, s in t.items():
            inp, name = key.split("|")
            f_, l_ = s["cost_first"], s["cost_later"]
            out.append(f"| {inp} | {name} | {f_['v_calls']} / {l_['v_calls']} | {f_['extract_chars']} / {l_['extract_chars']} | "
                       f"{f_['lat_v1']} / {l_['lat_v1']} | {f_['lat_v2']} / {l_['lat_v2']} | {f_['lat_v3']} / {l_['lat_v3']} | "
                       f"{f_['lat_total']} / {l_['lat_total']} | {s['h']['h_valid']} / {s['h']['h_read']} / {s['h']['h_cites']} |")
        out += ["", "### So sánh ghép cặp theo bệnh nhân (bootstrap 10.000 lần, Wilcoxon; Holm trong từng họ)", "",
                "| Họ | So sánh | Số BN | Chênh lệch [KTC 95%] | p bootstrap (Holm) | p Wilcoxon (Holm) |", "|---|---|---|---|---|---|"]
        for fam, items in metrics[part]["comparisons"].items():
            for cmp_, c in items.items():
                out.append(f"| {fam} | {cmp_} | {c['patients']} | {c['diff']:+.3f} [{c['ci_lo']:+.3f}, {c['ci_hi']:+.3f}] | "
                           f"{c['p_raw']:.3f} ({c['p_holm']:.3f}) | {c['p_wilcoxon']:.3f} ({c['p_wilcoxon_holm']:.3f}) |")
        out.append("")
    ch = metrics["checker"]
    out += ["## Bộ kiểm độc lập", "", f"Công thức được kiểm: {ch['recipes']}. Trạng thái các phán quyết \"yes\": "
            + ", ".join(f"{k} {v}" for k, v in ch["by_status"].items())
            + f". Mục mới vào hàng duyệt mù `{metrics['queue']}`: {metrics['queue_new']} (pending tính là vi phạm).",
            "Dị ứng và chế độ ăn do bộ kiểm độc lập chấm; nguyên liệu có tên (từ hồ sơ hoặc hội thoại) so khớp nguyên "
            "từ trên dòng nguyên liệu thô; giới hạn thời gian đọc cột total_minutes; dinh dưỡng đọc cột dinh dưỡng.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--input", default=",".join(INPUTS))
    r.add_argument("--presets", default=",".join(PRESETS))
    r.add_argument("--limit", type=int)
    r.add_argument("--resume")
    r.add_argument("--no-score", action="store_true")
    s = sub.add_parser("score")
    s.add_argument("run_dir")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    run_dir = run(args) if args.cmd == "run" else Path(args.run_dir)
    if args.cmd == "score" or not args.no_score:
        score(run_dir)
        print((run_dir / "table.md").read_text(encoding="utf-8"))
    print(f"-> {run_dir}")


if __name__ == "__main__":
    main()
