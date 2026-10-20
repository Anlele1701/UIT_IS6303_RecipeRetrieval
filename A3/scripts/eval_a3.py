"""M6: the A3 experiment on the frozen test set (build plan M6, 6.6; sườn báo cáo 4.3-4.6).

    uv run scripts/eval_a3.py run --sample                 # the M6b run Thy set: ~10% of each set, ~370 turns
    uv run scripts/eval_a3.py run --limit 3                # a smoke run
    uv run scripts/eval_a3.py run --resume eval/runs/<ts>/a3
    uv run scripts/eval_a3.py score eval/runs/<ts>/a3      # metrics.json, per_query.csv, table.md, errors.csv
    uv run scripts/eval_a3.py human-sample eval/runs/<ts>/a3   # the items scripts/human_check.py shows Thy

`run` asks each query in a new session (a T4 dialogue: its turns in one session) once per configuration, with
the full pipeline, and appends one line per turn to turns.jsonl (events, the top-10 ranking M5 traced, latencies).
Configurations: B0 B1 S S-QU S-Filter S-Norm S-Rerank S-Verify on T1-T4, plus S-Conv on T4 only. They are
presets of api/pipeline/flags.py: one code (CLAUDE.md rule 10).

`score` (build plan 6.6):
- retrieval: the top 10 of every configuration pooled per query, judged 0/1/2 by llama3.1:8b (scripts/judge.py);
  rel' = rel x [the Recipe keeps C_q]. nDCG@10', R@10 (relevant: rel' >= 1), MRR. T1: A1's source Recipe is rel 2.
- violations on the 5 Recipes of the context: CVR@5, Safe@5. Allergen groups and diets by the independent checker
  (strict: unsure counts; lenient: it does not; adjudicated: a "yes" whose evidence is not verbatim drops, a
  pending one counts - scripts/adjudicate.py writes the blind queue); named ingredients matched in the raw lines;
  time from total_minutes.
- generation: citation validity and safety; faithfulness, answer relevance, refusals (judge); code-written answers.
- query understanding: intent accuracy and micro slot F1 against the M5 gold (configurations with M1 on).
- latency: p50/p95 per stage and TTFT from the run's own turns (Thy: no separate 3x run, 19/10).
- statistics: per query (a T4 dialogue: the mean of its turns), S against B0, B1 and each ablation: paired
  bootstrap (scripts/significance.py) and Wilcoxon, Holm per family. CIs not adjusted.
- errors: the nine groups of sườn 4.6, tagged by rules on S's turns, with the comma-parser cases apart.
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from api import config  # noqa: E402

TESTSET = ROOT / "eval" / "testset"
SETS = ["t1", "t2", "t3", "t4"]
MAIN = ["B0", "B1", "S", "S-QU", "S-Filter", "S-Norm", "S-Rerank", "S-Verify"]
T4_ONLY = ["S-Conv"]
QU_ON = {"S", "S-Filter", "S-Norm", "S-Rerank", "S-Verify", "S-Conv"}
SAMPLE = {"t1": 10, "t2": 17, "t3": 6, "t4": 4}  # Thy, 19/10: ~10% of each set, ~370 turns in all
SEED = 42
K, DEPTH = 5, 10
R_CITE = re.compile(r"\[R(\d+)\]")
FAMILIES = ["cvr_adj", "safe_adj", "ndcg10", "recall10", "mrr", "citation_safety", "faithful", "answers",
            "intent_ok", "slot_f1"]


# ---- inputs -----------------------------------------------------------------------------------------------------

def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check_frozen() -> dict:
    import freeze_testset as fz
    frozen = json.loads((TESTSET / "frozen.json").read_text(encoding="utf-8"))
    if frozen["sha256"] != fz.digests():
        sys.exit("eval/testset/*.jsonl changed since it was frozen: refusing to run (CLAUDE.md rule 8)")
    return frozen


def balanced_sample(items: list[dict], n: int, seed: int = SEED) -> list[dict]:
    """n items, seeded, half Vietnamese when possible (items in id order first, so the draw is reproducible)."""
    rng = random.Random(seed)
    items = sorted(items, key=lambda it: it["id"])
    by = {lang: [it for it in items if it["lang"] == lang] for lang in sorted({it["lang"] for it in items})}
    for v in by.values():
        rng.shuffle(v)
    out, langs = [], sorted(by, key=lambda lang: (lang != "vi", lang))
    while len(out) < min(n, len(items)):
        for lang in langs:
            if by[lang] and len(out) < n:
                out.append(by[lang].pop())
    return sorted(out, key=lambda it: it["id"])


def pick_items(sample: bool, limit: int | None) -> dict[str, list[dict]]:
    out = {}
    for s in SETS:
        items = read_jsonl(TESTSET / f"{s}.jsonl")
        n = SAMPLE[s] if sample else limit
        out[s] = balanced_sample(items, n) if n else items
    return out


# ---- run --------------------------------------------------------------------------------------------------------

def turn_record(bot, sid, text: str, name: str) -> dict:
    from api.pipeline.flags import preset
    t = time.perf_counter()
    ev: dict = {}
    for e in bot.run_turn(sid, text, preset(name)):
        if e.type != "token":
            ev[e.type] = e.data
    done, c = ev["done"], ev["constraints"]
    trace = {stage: payload for stage, payload in bot.conn.execute(
        "SELECT stage, payload FROM retrieval_trace WHERE message_id = %s", [done["message_id"]])}
    ranked = [rid for rid, _ in (trace.get("m5") or {}).get("ranked", [])]
    return {"intent": c["intent"], "route": c["route"], "constraints": c["constraints"],
            "recipe_ids": [r["id"] for r in ev.get("recipes", [])], "ranked": ranked, "answer": done["answer"],
            "citations": done["citations"], "verified": done["verified"], "removed": done["removed"],
            "regenerated": done["regenerated"], "fallback": done.get("fallback", False),
            "fallback_kind": (trace.get("fallback") or {}).get("kind"), "usage": done["usage"],
            "latency_ms": done["latency_ms"], "seconds": round(time.perf_counter() - t, 2),
            "message_id": done["message_id"]}


def run(args) -> Path:
    import httpx
    import psycopg

    import checker
    import judge
    from api.pipeline import orchestrator as orch
    from api.rerank import Reranker

    frozen = check_frozen()
    out = Path(args.resume) if args.resume else ROOT / "eval" / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S") / "a3"
    out.mkdir(parents=True, exist_ok=True)
    turns_path, settings_path = out / "turns.jsonl", out / "settings.json"
    done = {(r["qid"], r["preset"], r["turn"]) for r in read_jsonl(turns_path)} if turns_path.exists() else set()
    if args.resume and settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        by_id = {it["id"]: it for s in SETS for it in read_jsonl(TESTSET / f"{s}.jsonl")}
        chosen = {s: [by_id[i] for i in settings["qids"][s]] for s in SETS}
        settings.setdefault("resumed", []).append(datetime.now().isoformat(timespec="seconds"))
    else:
        from eval_patient import git_commit, machine
        chosen = pick_items(args.sample, args.limit)
        settings = {"started": datetime.now().isoformat(timespec="seconds"), "machine": machine(), "git": git_commit(),
                    "seed": config.SEED, "sample_seed": SEED, "sample": SAMPLE if args.sample else None,
                    "limit": args.limit, "qids": {s: [it["id"] for it in chosen[s]] for s in SETS},
                    "presets": {"t1-t3": MAIN, "t4": MAIN + T4_ONLY}, "testset_sha256": frozen["sha256"],
                    "models": {"qu": config.QU_MODEL, "gen": config.GEN_MODEL, "embed": config.EMBED_MODEL,
                               "rerank": config.RERANK_MODEL, "checker": checker.CHECKER_MODEL,
                               "judge": judge.JUDGE_MODEL},
                    "k_context": K, "rank_depth": DEPTH, "strategy": config.CHAT_STRATEGY}
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    jobs = [(it, name) for s in ("t1", "t2", "t3") for name in MAIN for it in chosen[s]]
    jobs += [(it, name) for name in MAIN + T4_ONLY for it in chosen["t4"]]
    todo = [(it, name) for it, name in jobs
            if any((it["id"], name, i) not in done for i in range(len(it.get("turns") or [it])))]
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{sum(len(it.get('turns') or [it]) for it, _ in todo)} turns to run ({len(done)} already in {turns_path})")
    with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=1800) as client, \
            open(turns_path, "a", encoding="utf-8") as f:
        bot = orch.Assistant(conn, client, Reranker().score)
        for j, (it, name) in enumerate(todo, 1):
            sid = bot.new_session(name)
            texts = [t["text"] for t in it["turns"]] if it.get("turns") else [it["text"]]
            for i, text in enumerate(texts):  # a T4 dialogue restarts whole if it was cut (its session state)
                rec = turn_record(bot, sid, text, name)
                f.write(json.dumps({"qid": it["id"], "set": it["set"], "preset": name, "turn": i, "text": text,
                                    **rec}, ensure_ascii=False) + "\n")
                f.flush()
            print(f"[{j}/{len(todo)}] {name:9} {it['id']} {len(texts)} turn(s)")
    settings["finished"] = datetime.now().isoformat(timespec="seconds")
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


# ---- pure metrics (tested on hand-built data) --------------------------------------------------------------------

def dcg(gains: list[float]) -> float:
    import math
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg(ranked: list[int], rel: dict[int, int], depth: int = DEPTH) -> float | None:
    """nDCG@depth against every judged Recipe of the query (the pool); None when the pool has nothing relevant."""
    ideal = dcg(sorted(rel.values(), reverse=True)[:depth])
    return dcg([rel.get(r, 0) for r in ranked[:depth]]) / ideal if ideal else None


def recall(ranked: list[int], rel: dict[int, int], depth: int = DEPTH) -> float | None:
    good = {r for r, g in rel.items() if g >= 1}
    return len(good & set(ranked[:depth])) / len(good) if good else None


def mrr(ranked: list[int], rel: dict[int, int], depth: int = DEPTH) -> float | None:
    if not any(g >= 1 for g in rel.values()):
        return None
    return next((1 / (i + 1) for i, r in enumerate(ranked[:depth]) if rel.get(r, 0) >= 1), 0.0)


def gold_constraints(gold: dict) -> dict:
    c = gold.get("constraints") or {}
    return {"allergens_exclude": sorted(c.get("allergens_exclude") or []),
            "ingredients_exclude": sorted(c.get("ingredients_exclude") or []), "diet": c.get("diet"),
            "max_total_minutes": c.get("max_total_minutes")}


def slots(c: dict) -> set[tuple[str, str]]:
    out = {("allergen", a) for a in c.get("allergens_exclude") or []}
    out |= {("ingredient", i) for i in c.get("ingredients_exclude") or []}
    if c.get("diet"):
        out.add(("diet", c["diet"]))
    if c.get("max_total_minutes"):
        out.add(("minutes", str(c["max_total_minutes"])))
    return out


def slot_counts(pred: dict, gold: dict) -> tuple[int, int, int]:
    p, g = slots(pred), slots(gold)
    return len(p & g), len(p - g), len(g - p)


def has_constraint(c: dict) -> bool:
    return bool(slots(c))


def citation_scores(answer: str, context: list[int], ok: set[int]) -> dict:
    """validity: cited ids in the context; safety: cited ids that keep C_q (ok = the context Recipes that do)."""
    cited = [int(x) for x in dict.fromkeys(R_CITE.findall(answer or ""))]
    if not cited:
        return {"cited": 0, "citation_validity": None, "citation_safety": None}
    return {"cited": len(cited), "citation_validity": sum(c in context for c in cited) / len(cited),
            "citation_safety": sum(c in ok for c in cited) / len(cited)}


def percentile(xs: list[float], q: float) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    i = (len(xs) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (i - lo), 1)


# ---- score ------------------------------------------------------------------------------------------------------

def score(run_dir: Path) -> dict:
    import httpx
    import psycopg

    import adjudicate
    import checker
    import judge
    from api.pipeline import m6_generate
    from api.pipeline.m5_postprocess import cards as load_cards
    from eval_patient import compare, holm, names_in
    from significance import interval
    from stats import rate

    # a T4 dialogue cut by a stop is rerun whole on --resume: the last row per (query, configuration, turn) wins
    turns = list({(t["qid"], t["preset"], t["turn"]): t for t in read_jsonl(run_dir / "turns.jsonl")}.values())
    items = {it["id"]: it for s in SETS for it in read_jsonl(TESTSET / f"{s}.jsonl")}

    def gold_of(t):
        it = items[t["qid"]]
        return it["turns"][t["turn"]]["gold"] if it.get("turns") else it["gold"]

    def query_of(t):  # what the judge reads: the dialogue so far for T4
        it = items[t["qid"]]
        return " / ".join(x["text"] for x in it["turns"][:t["turn"] + 1]) if it.get("turns") else it["text"]

    with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=900) as client:
        cache = checker.load_cache()
        lines: dict[int, list[str]] = {}

        def raw(rid):
            if rid not in lines:
                lines[rid] = adjudicate.raw_lines(conn, rid)
            return lines[rid]
        info = {}

        def recipe(rid):
            if rid not in info:
                row = conn.execute("SELECT title, coalesce(description, ''), total_minutes FROM recipe WHERE id = %s",
                                   [rid]).fetchone()
                info[rid] = {"title": row[0], "summary": row[1], "minutes": row[2]}
            return info[rid]

        # 1. the checker on every Recipe whose safety a metric needs (context top 5, the pool for rel')
        verdicts, need = {}, defaultdict(set)
        for t in turns:
            g = gold_constraints(gold_of(t))
            cons = [f"allergen:{a}" for a in g["allergens_exclude"]] + ([f"diet:{g['diet']}"] if g["diet"] else [])
            if cons:
                for rid in set(t["recipe_ids"][:K]) | set(t["ranked"][:DEPTH]):
                    need[rid] |= set(cons)
        for i, (rid, cons) in enumerate(need.items(), 1):
            for c, v in safe_check(checker, conn, client, rid, sorted(cons), cache).items():
                verdicts[(rid, c)] = v
            if i % 50 == 0 or i == len(need):
                print(f"checker {i}/{len(need)} Recipes", flush=True)
        scored = {(s.recipe_id, s.constraint): s for s in adjudicate.score_all(conn, verdicts)}
        settings = json.loads((run_dir / "settings.json").read_text(encoding="utf-8"))
        queue = adjudicate.QUEUE if settings.get("sample") else run_dir / "checker_queue.csv"  # smoke runs stay out
        queue_new = adjudicate.write_queue(conn, list(scored.values()), queue)

        def breaks(rid: int, g: dict, mode: str) -> bool:
            """mode: strict | lenient | adj. Named ingredients and time break in every mode."""
            if names_in(raw(rid), g["ingredients_exclude"]):
                return True
            m = recipe(rid)["minutes"]
            if g["max_total_minutes"] and m is not None and m > g["max_total_minutes"]:
                return True
            cons = [f"allergen:{a}" for a in g["allergens_exclude"]] + ([f"diet:{g['diet']}"] if g["diet"] else [])
            for c in cons:
                v = verdicts.get((rid, c))
                if v is None:
                    continue
                if mode == "strict" and v.contains in {"yes", "unsure", "error"}:
                    return True
                if mode == "lenient" and v.contains == "yes":
                    return True
                if mode == "adj" and scored[(rid, c)].adjudicated:
                    return True
            return False

        # 2. the pool, judged (relevance ignores constraints; rel' applies them)
        pool: dict[tuple[str, int], set[int]] = defaultdict(set)
        for t in turns:
            if t["route"] in {"retrieve"} and t["set"] != "t3":
                pool[(t["qid"], t["turn"])] |= set(t["ranked"][:DEPTH])
        rel: dict[tuple[str, int], dict[int, int]] = {}
        judged_raw: list[dict] = []  # the judge's own scores (before rel'), for the human check
        for n_q, (key, rids) in enumerate(pool.items(), 1):
            print(f"judge pool {n_q}/{len(pool)} queries", flush=True)
            t0 = next(t for t in turns if (t["qid"], t["turn"]) == key)
            g = gold_constraints(gold_of(t0))
            q = query_of(t0)
            src = items[key[0]].get("a1_recipe_id")
            judged = {}
            for rid in sorted(rids):
                r = recipe(rid)
                score_ = 2 if rid == src else judge.relevance(client, q, judge.recipe_text(r["title"], r["summary"], raw(rid)))
                judged[rid] = 0 if score_ is None or breaks(rid, g, "adj") else score_
                if rid != src and score_ is not None:
                    judged_raw.append({"qid": key[0], "turn": key[1], "query": q, "recipe_id": rid, "judge": score_})
            rel[key] = judged

        # 3. per turn
        rows = []
        for n_t, t in enumerate(turns, 1):
            if n_t % 25 == 0 or n_t == len(turns):
                print(f"judge answers {n_t}/{len(turns)} turns", flush=True)
            g = gold_constraints(gold_of(t))
            gold = gold_of(t)
            ctx = t["recipe_ids"][:K]
            r = {"qid": t["qid"], "set": t["set"], "turn": t["turn"], "preset": t["preset"], "route": t["route"],
                 "lang": items[t["qid"]]["lang"], "recipes": len(ctx), "fallback": int(bool(t["fallback"])),
                 "fallback_kind": t["fallback_kind"], **{f"lat_{k}": v for k, v in t["latency_ms"].items()
                                                         if k in {"m1", "m4", "m5", "m6_ttft", "m6", "m7", "total"}}}
            key = (t["qid"], t["turn"])
            if key in rel:
                r.update(ndcg10=ndcg(t["ranked"], rel[key]), recall10=recall(t["ranked"], rel[key]),
                         mrr=mrr(t["ranked"], rel[key]))
            if has_constraint(g) and ctx:
                for mode in ("strict", "lenient", "adj"):
                    v = sum(breaks(rid, g, mode) for rid in ctx)
                    r[f"cvr_{mode}"], r[f"safe_{mode}"] = v / len(ctx), int(v == 0)
            ok = {rid for rid in ctx if not breaks(rid, g, "adj")}
            r.update(citation_scores(t["answer"], ctx, ok))
            if t["preset"] not in {"B0"} and t["answer"]:
                if ctx and t["route"] in {"retrieve", "detail"}:
                    # the cards M6 itself was given (time, allergens, may contain, diet, ingredients): a claim
                    # read off them is supported (smoke run: titles and ingredients alone made every answer unfaithful)
                    context = m6_generate.context_block(load_cards(conn, [(x, 0.0) for x in ctx]))
                    f_ = judge.faithful(client, context, t["answer"])
                    r["faithful"] = None if f_ is None else int(f_)
                a = judge.answers_question(client, query_of(t), t["answer"])
                r["answers"] = None if a is None else a / 2
                ref = judge.refuses(client, query_of(t), t["answer"])
                if ref is not None:
                    if t["set"] == "t3":
                        r["neg_rejection"] = int(ref)
                    elif t["set"] in {"t1", "t2"}:
                        r["false_refusal"] = int(ref)
            if t["preset"] in QU_ON:
                r["intent_ok"] = int(t["intent"] == gold.get("intent"))
                tp, fp, fn = slot_counts(t["constraints"], g)
                r.update(slot_tp=tp, slot_fp=fp, slot_fn=fn,
                         slot_f1=(2 * tp / (2 * tp + fp + fn)) if (tp + fp + fn) else None)
            r["errors"] = ";".join(error_groups(t, r, g, gold, rel.get(key, {}), turns, items, verdicts, raw))
            rows.append(r)

    (run_dir / "pool.json").write_text(json.dumps(judged_raw, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "checker_verdicts.json").write_text(json.dumps(
        [{"recipe_id": rid, "constraint": c, "contains": v.contains, "evidence_line": v.evidence_line}
         for (rid, c), v in sorted(verdicts.items())], ensure_ascii=False) + "\n", encoding="utf-8")
    metrics = {"summary": summarize(rows, rate, interval), "comparisons": comparisons(rows, compare, holm),
               "checker": adjudicate.summary(list(scored.values()), len(need)), "queue_new": queue_new,
               "pool": {"queries": len(rel), "pairs": sum(len(v) for v in rel.values())},
               "errors": error_counts(rows)}
    import human_check  # Thy's labels against the judge and the checker, once she has made them
    metrics["human_check"] = human_check.agreement(
        run_dir, {(r["qid"], r["preset"], r["turn"]): r.get("faithful") for r in rows})
    write_outputs(run_dir, rows, metrics)
    return metrics


def safe_check(checker, conn, client, rid: int, cons: list[str], cache: dict, attempts: int = 2) -> dict:
    """checker.check, retried once when the model's reply is not JSON or the call fails; then every constraint is
    an "error" verdict (scored like unsure: a violation in strict, not in lenient), never a crash of the scoring."""
    for _ in range(attempts):
        try:
            return checker.check(conn, client, rid, cons, cache)
        except Exception as e:  # json.JSONDecodeError (a cut reply), httpx timeouts
            last = e
    print(f"checker failed twice on R{rid}: {type(last).__name__}", file=sys.stderr)
    return {c: checker.Verdict("error", "", False) for c in cons}


def error_groups(t, r, g, gold, rel, turns, items, verdicts, raw) -> list[str]:
    """The nine error groups of sườn 4.6, tagged by rules on S's turns (other configurations: none)."""
    if t["preset"] != "S":
        return []
    out = []
    if r.get("slot_fn") or r.get("slot_fp"):
        out.append("F1_constraint_extraction")
    if r.get("intent_ok") == 0:
        out.append("F2_intent_routing")
    if r.get("cvr_adj"):
        out.append("F3_tagger_miss")
        for rid in t["recipe_ids"][:K]:  # the comma parser (gate M3, note 1): the evidence line has a comma
            for (vr, c), v in verdicts.items():
                if vr == rid and v.contains == "yes" and "," in (v.evidence_line or ""):
                    out.append("F3a_comma_parser_suspect")
                    break
    if t["set"] in {"t2", "t4"} and has_constraint(g) and t["route"] == "retrieve" and not t["recipe_ids"]:
        out.append("F4_overfiltering")
    if rel and any(v >= 1 for v in rel.values()) and not any(rel.get(x, 0) >= 1 for x in t["ranked"][:DEPTH]):
        out.append("F5_retrieval_miss")
    if rel and not any(rel.get(x, 0) >= 1 for x in t["ranked"][:K]) and any(rel.get(x, 0) >= 1 for x in t["ranked"][K:DEPTH]):
        out.append("F6_rerank")
    if r.get("faithful") == 0:
        out.append("F7_unfaithful")
    if r.get("false_refusal") == 1 or r.get("neg_rejection") == 0:
        out.append("F8_refusal")
    if t["set"] == "t4" and t["turn"] > 0 and slots(g) - slots(t["constraints"]):
        out.append("F9_lost_state")
    return list(dict.fromkeys(out))


def error_counts(rows: list[dict]) -> dict:
    s = [r for r in rows if r["preset"] == "S"]
    counts = defaultdict(int)
    for r in s:
        for e in filter(None, r["errors"].split(";")):
            counts[e] += 1
    return {"turns": len(s), "by_group": dict(sorted(counts.items()))}


def summarize(rows: list[dict], rate, interval) -> dict:
    out = {}
    for name in MAIN + T4_ONLY:
        for scope, keep in (("all", lambda r: True), ("t1", lambda r: r["set"] == "t1"), ("t2", lambda r: r["set"] == "t2"),
                            ("t3", lambda r: r["set"] == "t3"), ("t4", lambda r: r["set"] == "t4")):
            rs = [r for r in rows if r["preset"] == name and keep(r)]
            if not rs:
                continue
            s: dict = {"turns": len(rs)}
            for m in ("ndcg10", "recall10", "mrr", "cvr_strict", "cvr_lenient", "cvr_adj", "citation_validity",
                      "citation_safety", "faithful", "answers", "slot_f1"):
                vals = [r[m] for r in rs if r.get(m) is not None]
                if vals:
                    s[m] = {"mean": round(sum(vals) / len(vals), 4), "n": len(vals),
                            **({"ci95": [round(x, 4) for x in (interval(vals, seed=SEED)["ci_lo"], interval(vals, seed=SEED)["ci_hi"])]}
                               if len(vals) >= 2 else {})}
            for m in ("safe_strict", "safe_lenient", "safe_adj", "intent_ok", "neg_rejection", "false_refusal", "fallback"):
                vals = [r[m] for r in rs if r.get(m) is not None]
                if vals:
                    s[m] = rate(sum(vals), len(vals))
            tp, fp, fn = (sum(r.get(k) or 0 for r in rs) for k in ("slot_tp", "slot_fp", "slot_fn"))
            if tp + fp + fn and name in QU_ON:
                s["slot_f1_micro"] = round(2 * tp / (2 * tp + fp + fn), 4)
            lat = {k: [r[f"lat_{k}"] for r in rs if r.get(f"lat_{k}") is not None]
                   for k in ("m1", "m4", "m5", "m6_ttft", "m6", "m7", "total")}
            s["latency_ms"] = {k: {"p50": percentile(v, 0.5), "p95": percentile(v, 0.95)} for k, v in lat.items() if v}
            out[f"{name}|{scope}"] = s
    return out


def per_query(rows: list[dict], name: str, metric: str, scope=None) -> dict[str, float]:
    """One value per query; a T4 dialogue is the mean of its turns."""
    acc = defaultdict(list)
    for r in rows:
        if r["preset"] == name and r.get(metric) is not None and (scope is None or r["set"] in scope):
            acc[r["qid"]].append(float(r[metric]))
    return {q: sum(v) / len(v) for q, v in acc.items()}


def comparisons(rows: list[dict], compare, holm) -> dict:
    """S against B0, B1 and each ablation, per metric family (scope: where the metric means something)."""
    scopes = {"cvr_adj": {"t2", "t4"}, "safe_adj": {"t2", "t4"}, "ndcg10": {"t1", "t2"}, "recall10": {"t1", "t2"},
              "mrr": {"t1", "t2"}, "citation_safety": None, "faithful": None, "answers": None, "intent_ok": None,
              "slot_f1": None}
    out = {}
    for m in FAMILIES:
        items = []
        for other in [p for p in MAIN + T4_ONLY if p != "S"]:
            c = compare(per_query(rows, "S", m, scopes[m]), per_query(rows, other, m, scopes[m]))
            if c:
                items.append((f"S - {other}", c))
        for key, adj in (("p_raw", "p_holm"), ("p_wilcoxon", "p_wilcoxon_holm")):
            for (_, c), a in zip(items, holm([c[key] for _, c in items])):
                c[adj] = a
        out[m] = dict(items)
    if any(r["set"] == "t1" for r in rows):  # G6: no regression on A1-type queries
        out["ndcg10_t1_only"] = {}
        c = compare(per_query(rows, "S", "ndcg10", {"t1"}), per_query(rows, "B0", "ndcg10", {"t1"}))
        if c:
            out["ndcg10_t1_only"]["S - B0"] = c
    return out


# ---- outputs ----------------------------------------------------------------------------------------------------

def _f(x, pct=False) -> str:
    if x is None:
        return "–"
    if isinstance(x, dict):
        if "mean" in x:
            ci = x.get("ci95")
            v = x["mean"] * (100 if pct else 1)
            return f"{v:.1f}{'%' if pct else ''}" + (f" [{ci[0] * (100 if pct else 1):.1f}–{ci[1] * (100 if pct else 1):.1f}]" if ci else "")
        if x.get("value") is None:
            return "–"
        return f"{x['value'] * 100:.0f}% ({x['k']}/{x['n']})"
    return str(x)


def render(m: dict) -> str:
    s = m["summary"]
    out = ["# M6 – Kết quả thực nghiệm A3", "", "Sinh tự động bởi `scripts/eval_a3.py score`. Không sửa tay.", "",
           "## Kết quả chính và ablation", "",
           "| Cấu hình | nDCG@10′ T1 | nDCG@10′ T2 | CVR@5 adj (T2+T4) | Safe@5 adj | Trích dẫn an toàn | Faithfulness | Từ chối đúng T3 | Từ chối sai T1+T2 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for name in MAIN + T4_ONLY:
        a, t1, t2, t3, t4 = (s.get(f"{name}|{x}", {}) for x in ("all", "t1", "t2", "t3", "t4"))
        cvr = [x for x in (t2.get("cvr_adj"), t4.get("cvr_adj")) if x]
        cvr_txt = " / ".join(_f(x, True) for x in cvr) if cvr else "–"
        out.append(f"| {name} | {_f(t1.get('ndcg10'))} | {_f(t2.get('ndcg10'))} | {cvr_txt} | {_f(t2.get('safe_adj'))} | "
                   f"{_f(a.get('citation_safety'), True)} | {_f(a.get('faithful'), True)} | {_f(t3.get('neg_rejection'))} | "
                   f"{_f(a.get('false_refusal'))} |")
    out += ["", "CVR@5 ghi T2 / T4. Strict và lenient (raw) có trong `metrics.json`.", "",
            "## Hiểu truy vấn (so với gold M5)", "", "| Cấu hình | Intent đúng | Slot F1 (micro) |", "|---|---|---|"]
    for name in MAIN + T4_ONLY:
        a = s.get(f"{name}|all", {})
        if name in QU_ON:
            out.append(f"| {name} | {_f(a.get('intent_ok'))} | {a.get('slot_f1_micro', '–')} |")
    out += ["", "## Độ trễ (ms, p50 / p95, từ chính lần chạy)", "",
            "| Cấu hình | M1 | M4 | M5 | M6 TTFT | M6 | Tổng |", "|---|---|---|---|---|---|---|"]
    for name in MAIN + T4_ONLY:
        lat = s.get(f"{name}|all", {}).get("latency_ms", {})
        cell = lambda k: f"{lat[k]['p50']} / {lat[k]['p95']}" if k in lat else "–"  # noqa: E731
        out.append(f"| {name} | {cell('m1')} | {cell('m4')} | {cell('m5')} | {cell('m6_ttft')} | {cell('m6')} | {cell('total')} |")
    out += ["", "## So sánh theo từng câu (bootstrap; Wilcoxon; Holm trong từng họ)", "",
            "| Họ | So sánh | Số câu | Chênh lệch [KTC 95%] | p bootstrap (Holm) | p Wilcoxon (Holm) |", "|---|---|---|---|---|---|"]
    for fam, items in m["comparisons"].items():
        for k, c in items.items():
            out.append(f"| {fam} | {k} | {c['patients']} | {c['diff']:+.3f} [{c['ci_lo']:+.3f}, {c['ci_hi']:+.3f}] | "
                       f"{c['p_raw']:.3f} ({c.get('p_holm', c['p_raw']):.3f}) | {c['p_wilcoxon']:.3f} ({c.get('p_wilcoxon_holm', c['p_wilcoxon']):.3f}) |")
    e = m["errors"]
    out += ["", f"## Nhóm lỗi trên các lượt của S ({e['turns']} lượt)", "", "| Nhóm | Số lượt |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in e["by_group"].items()]
    ch = m["checker"]
    out += ["", f"Bộ kiểm: {ch['recipes']} công thức; phiếu \"yes\": " + ", ".join(f"{k} {v}" for k, v in ch["by_status"].items())
            + f". Mục mới vào hàng duyệt mù: {m['queue_new']}. Pool judge: {m['pool']['queries']} truy vấn, {m['pool']['pairs']} cặp.", ""]
    return "\n".join(out)


def write_outputs(run_dir: Path, rows: list[dict], metrics: dict) -> None:
    (run_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, default=str) + "\n",
                                          encoding="utf-8")
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(run_dir / "per_query.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with open(run_dir / "errors.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["qid", "turn", "groups"])
        w.writerows([[r["qid"], r["turn"], r["errors"]] for r in rows if r["preset"] == "S" and r["errors"]])
    (run_dir / "table.md").write_text(render(metrics), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--sample", action="store_true", help="Thy's M6b sample: ~10%% of each set (SAMPLE)")
    r.add_argument("--limit", type=int)
    r.add_argument("--resume")
    r.add_argument("--no-score", action="store_true")
    s = sub.add_parser("score")
    s.add_argument("run_dir")
    h = sub.add_parser("human-sample")
    h.add_argument("run_dir")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.cmd == "human-sample":
        import human_check
        print(human_check.make_sample(Path(args.run_dir)))
        return
    run_dir = run(args) if args.cmd == "run" else Path(args.run_dir)
    if args.cmd == "score" or not args.no_score:
        score(run_dir)
        print((run_dir / "table.md").read_text(encoding="utf-8"))
    print(f"-> {run_dir}")


if __name__ == "__main__":
    main()
