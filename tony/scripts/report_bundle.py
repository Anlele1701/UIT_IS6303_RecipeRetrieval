"""Report bundle: every number the Report page shows, in one JSON file. Reads run folders, never searches.

    uv run python scripts/report_bundle.py            # writes ui/public/report.json

Reads only what the manifest eval/report.json names, plus data/recipe.csv for case-study text and the
before-rewrite word overlap. The runs it names are rescored against the pooled qrels (scripts/rescore.py);
`single_answer_run` is the Report run as first scored, one right Recipe per query, kept for comparison.
`check_run` is a fresh run scored with the qrels by evaluate.py itself: it must rank like the rescored Report
run, and it supplies the Chunk kinds (a rescore can't know which Chunk ranked a judged Recipe). Python computes; the page formats. Fails hard if a Timing repeat or an Ablation
run's default rows rank anything differently from the Report run, or a label file names an unknown query.

The bundle records a hash of every input file. tests/test_report_bundle.py recomputes them, so a stale bundle
fails the test suite.
"""

import argparse
import csv
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import failures
import make_queries
import metrics
import runcheck

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "eval" / "report.json"
OUT = ROOT / "ui" / "public" / "report.json"
RECIPE_CSV = ROOT / "data" / "recipe.csv"
RUN_FILES = ["settings.json", "metrics.json", "per_query.csv", "significance.json", "recipes.csv", "corpus.json"]
CONFIGS = ["sparse", "dense", "fusion", "hybrid"]
STAGES = ["embed", "sparse", "dense", "rrf", "rerank"]
TESTED = ["recall@5", "mrr"]  # the metrics significance.py tests
ALPHA = 0.05
EVERY_MISS = "every_miss"  # no config has the Recipe in its top 20; not a failures.py bucket
BUCKET_ORDER = ["sparse_win", "dense_win", "rerank_help", "rerank_hurt", EVERY_MISS]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path):
    return json.loads(path.read_text())


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def input_files(manifest: dict) -> list[Path]:
    """Every file the bundle reads, so the freshness test can hash the same list."""
    runs = [manifest["report_run"], manifest["check_run"], *manifest["timing_repeats"],
            *manifest["ablation_runs"].values()]
    single = ROOT / manifest["single_answer_run"]
    files = [MANIFEST, ROOT / "eval" / "queries.jsonl", ROOT / manifest["qrels"], ROOT / manifest["qrels_check"],
             single / "metrics.json", single / "per_query.csv", *(ROOT / p for p in manifest["labels"].values())]
    files += [ROOT / r / name for r in runs for name in RUN_FILES if (ROOT / r / name).exists()]
    return files


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def holm(p_values: list[float]) -> list[float]:
    """Holm-adjusted p, same order as given: the k-th smallest p times (m - k + 1), kept monotone, capped at 1."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    out, running = [0.0] * m, 0.0
    for k, i in enumerate(order):
        running = max(running, min(1.0, (m - k) * p_values[i]))
        out[i] = running
    return out


def repeat_latency(repeats: list[list[dict]]) -> dict[tuple[str, str], dict]:
    """(config, strategy) -> per stage and total: median p50, median p95, lowest and highest p50, over the repeats.

    Pooling per-query timings would hide the run-to-run drift the range is there to show ("How ablation runs and
    timing repeats are stored").
    """
    out = {}
    keys = {(r["config"], r["strategy"]) for rows in repeats for r in rows}
    for key in keys:
        rows = [next(r for r in rs if (r["config"], r["strategy"]) == key and r["variant"] == "default")
                for rs in repeats]
        out[key] = {}
        for stage in rows[0]["latency_ms"]:
            p50s = [r["latency_ms"][stage]["p50_ms"] for r in rows]
            p95s = [r["latency_ms"][stage]["p95_ms"] for r in rows]
            out[key][stage] = {"p50": statistics.median(p50s), "p95": statistics.median(p95s),
                               "p50_min": min(p50s), "p50_max": max(p50s)}
    return out


def best_rows(rows: list[dict], metric: str = "recall@5") -> set[tuple[str, str]]:
    """(config, strategy) of the highest `metric` per Chunking strategy. Ties all count."""
    out = set()
    for s in {r["strategy"] for r in rows}:
        top = max(r[metric] for r in rows if r["strategy"] == s)
        out |= {(r["config"], s) for r in rows if r["strategy"] == s and r[metric] == top}
    return out


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


def check_ranks(report_run: Path, runs: dict[str, Path]) -> None:
    problems = {name: p for name, run in runs.items() if (p := runcheck.rank_mismatches(report_run, run))}
    if problems:
        lines = [f"{name}: {len(p)} mismatches, e.g. {p[0]}" for name, p in problems.items()]
        raise ValueError("ranks differ from the Report run:\n  " + "\n  ".join(lines))


def significance_block(report_run: Path, ablations: dict[str, Path]) -> list[dict]:
    """Every test in the family, tagged by run, with raw p and Holm p over the whole family."""
    tests = []
    for arm, run in [(None, report_run), *ablations.items()]:
        for t in read_json(run / "significance.json")["comparisons"]:
            tests.append({"arm": arm, **t})
    for t, p in zip(tests, holm([t["p_raw"] for t in tests])):
        t["p_holm"] = p
    return tests


def metrics_block(report_run: Path, latency: dict, intervals: list[dict]) -> list[dict]:
    rows = [r for r in read_json(report_run / "metrics.json") if r.get("variant", "default") == "default"]
    ci = {(i["config"], i["strategy"], i["metric"]): i for i in intervals if i["variant"] == "default"}
    best = best_rows(rows)
    out = []
    for r in sorted(rows, key=lambda r: (CONFIGS.index(r["config"]), r["strategy"])):
        key = (r["config"], r["strategy"])
        out.append({
            "config": r["config"], "strategy": r["strategy"], "queries": r["queries"],
            **{m: r[m] for m in metrics.COLUMNS}, "short_lists": r["short_lists"],
            "ci": {m: {"lo": ci[(*key, m)]["ci_lo"], "hi": ci[(*key, m)]["ci_hi"]} for m in TESTED},
            "latency": latency[key], "best_r5": key in best})
    return out


def ablation_block(ablations: dict[str, Path], tests: list[dict], latency: dict) -> list[dict]:
    """Per arm, config and strategy: default vs arm metrics, the tests, and the same-run latency ratio."""
    out = []
    for arm, run in ablations.items():
        settings = read_json(run / "settings.json")
        rows = read_json(run / "metrics.json")
        by = {(r["config"], r["variant"], r["strategy"]): r for r in rows}
        for c in settings["arm"]["configs"]:
            for s in settings["strategies"]:
                d, a = by[(c, "default", s)], by[(c, "arm", s)]
                ratio = {st: a["latency_ms"][st]["p50_ms"] / d["latency_ms"][st]["p50_ms"]
                         for st in d["latency_ms"] if d["latency_ms"][st]["p50_ms"] > 0}
                found = {t["metric"]: {k: t[k] for k in ("diff", "ci_lo", "ci_hi", "p_raw", "p_holm")}
                         for t in tests if t["arm"] == arm and t["a"]["config"] == c and t["a"]["strategy"] == s}
                out.append({
                    "arm": arm, "set": settings["arm"]["set"], "config": c, "strategy": s,
                    "default": {m: d[m] for m in metrics.COLUMNS}, "arm_metrics": {m: a[m] for m in metrics.COLUMNS},
                    "short_lists": {"default": d["short_lists"], "arm": a["short_lists"]},
                    "tests": found,
                    "latency_same_run": {v: {st: x["p50_ms"] for st, x in r["latency_ms"].items()}
                                         for v, r in (("default", d), ("arm", a))},
                    "latency_ratio": ratio,
                    "p50_on_report_scale": ratio["total"] * latency[(c, s)]["total"]["p50"],
                    "hnsw_indexes": settings["arm"].get("hnsw_indexes")})
    return out


def per_query_block(report_run: Path, fails: dict) -> tuple[list[dict], dict]:
    """Rows per (strategy, query): ranks and top-20 ids per config, and the buckets the query falls in there."""
    rows: dict[tuple[str, str], dict] = {}
    for r in read_csv(report_run / "per_query.csv"):
        if r.get("variant", "default") != "default":
            continue
        row = rows.setdefault((r["strategy"], r["query_id"]),
                              {"strategy": r["strategy"], "query_id": r["query_id"], "ranks": {}, "top": {},
                               "buckets": []})
        row["ranks"][r["config"]] = int(r["rank"]) if r["rank"] else None
        row["top"][r["config"]] = [int(x) for x in r["top_recipe_ids"].split()]
    for s, by_bucket in fails["buckets"].items():
        for bucket, cases in by_bucket.items():
            for case in cases:
                rows[(s, case["query_id"])]["buckets"].append(bucket)
    for row in rows.values():
        if all(row["ranks"][c] is None for c in CONFIGS):
            row["buckets"].append(EVERY_MISS)
        row["buckets"].sort(key=BUCKET_ORDER.index)
    ordered = sorted(rows.values(), key=lambda r: (r["query_id"], r["strategy"]))
    strategies = sorted({r["strategy"] for r in ordered})
    counts = {b: {s: sum(b in r["buckets"] for r in ordered if r["strategy"] == s) for s in strategies}
              for b in BUCKET_ORDER}
    qids = sorted({r["query_id"] for r in ordered})
    in_all = {b: sum(all(b in rows[(s, q)]["buckets"] for s in strategies) for q in qids) for b in BUCKET_ORDER}
    return ordered, {"per_strategy": counts, "all_strategies": in_all}


def read_recipe_rows(urls: set[str]) -> dict[str, dict]:
    """url -> the recipe.csv row, for the given urls only (first row per url, as ingest keeps)."""
    out = {}
    with open(RECIPE_CSV, newline="") as f:
        for r in csv.DictReader(f):
            if r["url"] in urls and r["url"] not in out:
                out[r["url"]] = r
    return out


def recipe_text(row: dict) -> str:
    """The text make_queries scored word overlap against, built from a recipe.csv row as ingest stores it."""
    return make_queries.recipe_text({
        "title": row["title"].strip(), "description": row["description"].strip(),
        "ingredients": [line.strip() for line in row["ingredients"].split(";") if line.strip()],
        "directions": row["directions"].strip()})


def queries_block(queries: list[dict], edits: dict[str, str], groups: dict[str, str], right: dict[str, set[int]],
                  checks: dict[str, dict]) -> dict:
    return {q["query_id"]: {"text": q["text"], "recipe_id": q["recipe_id"], "recipe_title": q["recipe_title"],
                            "right": sorted(right.get(q["query_id"], set()) | {q["recipe_id"]}),
                            "label_check": checks[q["query_id"]]["label"], "vague": checks[q["query_id"]]["vague"] == "yes",
                            "word_overlap": q["word_overlap"], "hand_rewritten": "edited_from" in q,
                            "edited_from": q.get("edited_from"), "edit_reason": edits.get(q["query_id"]),
                            "error_group": groups.get(q["query_id"])}
            for q in queries}


def histogram(values: list[float], width: float = 0.1) -> list[int]:
    """Counts in bins [0, 0.1), …, [0.9, 1.0), plus a last bin for exactly 1.0 (the Query set's median)."""
    bins = [0] * 11
    for v in values:
        bins[10 if v >= 1.0 else int(v / width)] += 1
    return bins


def query_set_block(queries: list[dict], edits: dict[str, str], rows_by_url: dict[str, dict],
                    urls: dict[int, str], corpus: dict) -> dict:
    """§2.3: prompt, rewrites by reason, overlap before and after the rewrites, query length, category spread."""
    before, mismatches = [], []
    for q in queries:
        text = recipe_text(rows_by_url[urls[q["recipe_id"]]])
        if make_queries.word_overlap(q["text"], text) != q["word_overlap"]:
            mismatches.append(q["query_id"])
        before.append(make_queries.word_overlap(q["edited_from"], text) if "edited_from" in q else q["word_overlap"])
    if mismatches:  # the recomputed overlap must equal the stored one, or "before" isn't comparable
        raise ValueError(f"word overlap doesn't reproduce for {len(mismatches)} queries, e.g. {mismatches[:3]}")
    after = [q["word_overlap"] for q in queries]
    lengths = [len(q["text"].split()) for q in queries]
    reasons: dict[str, int] = {}
    for r in edits.values():
        reasons[r] = reasons.get(r, 0) + 1
    by_cat: dict[str, int] = {}
    for q in queries:
        cat = corpus["query_recipe_categories"][str(q["recipe_id"])]
        by_cat[cat] = by_cat.get(cat, 0) + 1
    total = corpus["recipes"]
    return {
        "prompt": make_queries.PROMPT, "model": queries[0]["model"], "seed": make_queries.SEED,
        "sampled": make_queries.SIZE, "queries": len(queries), "skipped": make_queries.SIZE - len(queries),
        "rewritten": sum("edited_from" in q for q in queries), "reasons": reasons,
        "overlap": {"before_mean": statistics.mean(before), "after_mean": statistics.mean(after),
                    "median": statistics.median(after), "high": sum(v >= failures.HIGH_OVERLAP for v in after),
                    "before_bins": histogram(before), "after_bins": histogram(after)},
        "length": {"mean": statistics.mean(lengths), "median": statistics.median(lengths),
                   "min": min(lengths), "max": max(lengths)},
        "categories": [{"category": c, "queries": by_cat.get(c, 0), "query_share": by_cat.get(c, 0) / len(queries),
                        "corpus_share": n / total} for c, n in corpus["category_recipes"].items()],
    }


def every_miss_ids(per_query: list[dict]) -> set[str]:
    """Queries no config ranks in its top DEPTH under any Chunking strategy, from per_query.csv rows."""
    found = {r["query_id"] for r in per_query if r.get("variant", "default") == "default" and r["rank"]}
    return {r["query_id"] for r in per_query} - found


def qrels_block(qrels: list[dict], single_answer: list[dict], check: dict, checks: list[dict],
                single_misses: set[str], misses: set[str], groups: dict[str, str]) -> dict:
    """How the pooled answer key was built, the label check, and what the one-Recipe key scored and missed."""
    judged = [r for r in qrels if r["source"] == "judged"]
    extra: dict[str, int] = {}
    for r in judged:
        if r["relevant"] == "1":
            extra[r["query_id"]] = extra.get(r["query_id"], 0) + 1
    rows = [{"config": r["config"], "strategy": r["strategy"], **{m: r[m] for m in metrics.COLUMNS}}
            for r in single_answer if r.get("variant", "default") == "default"]
    return {"pool_depth": 5, "judged_pairs": len(judged), "relevant_judged": sum(extra.values()),
            "queries_with_extra": len(extra), "max_extra": max(extra.values(), default=0),
            "agreement": {k: check[k] for k in ("pairs", "agree", "kappa")},
            "label_check": {"good": sum(r["label"] == "good" for r in checks),
                            "partial": sum(r["label"] == "partial" for r in checks),
                            "wrong": sum(r["label"] == "wrong" for r in checks),
                            "vague": sum(r["vague"] == "yes" for r in checks)},
            "single_answer_every_miss": len(single_misses),
            "every_miss_found_by_group": {g: sum(groups.get(q) == g for q in single_misses - misses)
                                          for g in sorted(set(groups.values()))},
            "single_answer": sorted(rows, key=lambda r: (CONFIGS.index(r["config"]), r["strategy"]))}


def cases_block(cases: list[dict], queries: dict, rows_by_url: dict[str, dict], urls: dict[int, str]) -> list[dict]:
    out = []
    for c in cases:
        q = queries[c["query_id"]]
        row = rows_by_url[urls[q["recipe_id"]]]
        out.append({"query_id": c["query_id"], "bucket": c["bucket"], "why": c["why"],
                    "description": row["description"].strip(),
                    "ingredients": [line.strip() for line in row["ingredients"].split(";") if line.strip()]})
    return out


def headline_block(rows: list[dict], tests: list[dict], fails: dict, bucket_counts: dict) -> dict:
    """The numbers the prose quotes, so no sentence on the page does arithmetic."""
    get = {(r["config"], r["strategy"]): r for r in rows}
    strategies = sorted({r["strategy"] for r in rows})
    main = [t for t in tests if t["arm"] is None]

    def diffs(a: str, b: str, metric: str = "recall@5") -> list[dict]:
        return [t for t in main if t["a"]["config"] == a and t["b"]["config"] == b and t["metric"] == metric
                and t["a"]["strategy"] == t["b"]["strategy"]]

    rng = lambda xs: {"min": min(xs), "max": max(xs)}  # noqa: E731
    ratio = [get[("hybrid", s)]["latency"]["total"]["p50"] / get[("fusion", s)]["latency"]["total"]["p50"]
             for s in strategies]
    rerank_share = [get[("hybrid", s)]["latency"]["rerank"]["p50"] / get[("hybrid", s)]["latency"]["total"]["p50"]
                    for s in strategies]
    strategy_pairs = [t for t in main if t["a"]["strategy"] != t["b"]["strategy"]]
    # The Chunking strategy whose Hybrid p50 moved most across Timing repeats, same code and same strategy.
    widest = max(strategies, key=lambda s: get[("hybrid", s)]["latency"]["total"]["p50_max"]
                 / get[("hybrid", s)]["latency"]["total"]["p50_min"])
    t = get[("hybrid", widest)]["latency"]["total"]
    spread = {"strategy": widest, "min": t["p50_min"], "max": t["p50_max"]}
    net = fails["rerank_net"]
    return {
        "hybrid_vs_fusion_r5": rng([t["diff"] for t in diffs("hybrid", "fusion")]),
        "hybrid_vs_fusion_mrr": rng([t["diff"] for t in diffs("hybrid", "fusion", "mrr")]),
        "fusion_vs_sparse_r20": rng([get[("fusion", s)]["recall@20"] - get[("sparse", s)]["recall@20"]
                                     for s in strategies]),
        "fusion_vs_dense_r20": rng([get[("fusion", s)]["recall@20"] - get[("dense", s)]["recall@20"]
                                    for s in strategies]),
        "sparse_vs_dense_r5": rng([t["diff"] for t in diffs("sparse", "dense")]),
        "latency_ratio_hybrid_fusion": rng(ratio),
        "hybrid_p50": rng([get[("hybrid", s)]["latency"]["total"]["p50"] for s in strategies]),
        "fusion_p50": rng([get[("fusion", s)]["latency"]["total"]["p50"] for s in strategies]),
        "hybrid_p50_spread": spread,
        "rerank_share": rng(rerank_share),
        "strategy_pairs_min_p": min(t["p_raw"] for t in strategy_pairs) if strategy_pairs else None,
        "net_into_top5": rng([net[s]["net_into_top5"] for s in strategies]),
        "rerank_hurt": rng([net[s]["hurt"] for s in strategies]),
        "rerank_help": rng([net[s]["help"] for s in strategies]),
        "every_miss_all_strategies": bucket_counts["all_strategies"][EVERY_MISS],
        "family_size": len(tests),
    }


def build(manifest_path: Path = MANIFEST) -> dict:
    manifest = read_json(manifest_path)
    report_run = ROOT / manifest["report_run"]
    repeats = [ROOT / p for p in manifest["timing_repeats"]]
    ablations = {arm: ROOT / p for arm, p in manifest["ablation_runs"].items()}
    missing = [rel(p) for p in [report_run, ROOT / manifest["check_run"], *repeats, *ablations.values()]
               if not (p / "per_query.csv").exists()]
    if missing:
        raise ValueError(f"manifest names runs that aren't there: {', '.join(missing)}")
    check_run = ROOT / manifest["check_run"]
    check_ranks(report_run, {rel(check_run): check_run, **{rel(p): p for p in repeats}, **ablations})

    queries = [json.loads(line) for line in (ROOT / "eval" / "queries.jsonl").read_text().splitlines() if line.strip()]
    qids = {q["query_id"] for q in queries}
    labels = {name: read_csv(ROOT / path) for name, path in manifest["labels"].items()}
    unknown = sorted({r["query_id"] for rows in labels.values() for r in rows} - qids)
    if unknown:
        raise ValueError(f"label files name unknown queries: {', '.join(unknown)}")
    edits = {r["query_id"]: r["reason"] for r in labels["query_edits"]}
    groups = {r["query_id"]: r["group"] for r in labels["error_groups"]}

    tests = significance_block(report_run, ablations)
    latency = repeat_latency([read_json(p / "metrics.json") for p in repeats])
    rows = metrics_block(report_run, latency, read_json(report_run / "significance.json")["intervals"])
    # The rescored runs only know the kind of the written-from Recipe's Chunk; the check run knows the first right
    # Recipe's and ranks identically (checked above).
    fails = failures.as_json(failures.analyze(failures.read_query_set(report_run), failures.read_ranks(report_run),
                                              failures.read_kinds(check_run)))
    per_query, bucket_counts = per_query_block(report_run, fails)
    del fails["buckets"]  # the members live in per_query; the page needs only the counts
    recipes = {int(r["recipe_id"]): r for r in read_csv(report_run / "recipes.csv")}
    urls = {rid: r["url"] for rid, r in recipes.items()}
    rows_by_url = read_recipe_rows({urls[q["recipe_id"]] for q in queries})
    corpus = read_json(report_run / "corpus.json")
    right = metrics.read_qrels(ROOT / manifest["qrels"])
    checks = {r["query_id"]: r for r in labels["label_check"]}
    query_map = queries_block(queries, edits, groups, right, checks)
    single = ROOT / manifest["single_answer_run"]

    return {
        "meta": {"manifest": manifest, "runs": {rel(p): read_json(p / "settings.json")
                                                 for p in [report_run, check_run, *repeats, *ablations.values()]},
                 "input_hashes": {rel(p): sha256(p) for p in input_files(manifest)},
                 "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "alpha": ALPHA},
        "metrics": rows,
        "significance": tests,
        "ablations": ablation_block(ablations, tests, latency),
        "failures": {**fails, "bucket_counts": bucket_counts, "found_at": failures.FOUND_AT,
                     "high_overlap": failures.HIGH_OVERLAP},
        "per_query": per_query,
        "queries": query_map,
        "recipes": {str(rid): r["title"] for rid, r in recipes.items()},
        "cases": cases_block(labels["cases"], query_map, rows_by_url, urls),
        "qrels": qrels_block(read_csv(ROOT / manifest["qrels"]), read_json(single / "metrics.json"),
                             read_json(ROOT / manifest["qrels_check"]), labels["label_check"],
                             every_miss_ids(read_csv(single / "per_query.csv")),
                             every_miss_ids(read_csv(report_run / "per_query.csv")), groups),
        "corpus": corpus,
        "query_set": query_set_block(queries, edits, rows_by_url, urls, corpus),
        "headline": headline_block(rows, tests, fails, bucket_counts),
    }


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=OUT)
    return p.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    try:
        bundle = build()
    except (ValueError, FileNotFoundError) as e:
        sys.exit(f"report_bundle: {e}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(bundle, separators=(",", ":")) + "\n")
    print(f"Written {a.out.relative_to(ROOT)} ({a.out.stat().st_size // 1024} KB, "
          f"{len(bundle['significance'])} tests in the Holm family)")  # noqa: E501
