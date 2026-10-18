"""Rescore: score a saved Evaluation run against pooled qrels. Reads the run folder, never searches.

    uv run python scripts/rescore.py eval/runs/20260928-122309 [eval/runs/<run> ...]

Retrieval is deterministic and every run keeps each query's top 20 Recipes (per_query.csv), so a new answer
key needs no new searches. Each run is rescored into eval/pooled/<run id>/, leaving the original folder as the
single-answer record. Every file is rebuilt: `rank` becomes the first right Recipe's rank (metrics.first_rank),
metrics.json/csv and table.md are recomputed with the latency kept as measured, and significance.json and
failures.json are rerun on the new ranks.

eval/qrels.csv holds every judged (query, Recipe) pair with `relevant` 1 or 0: the Recipe the query was written
from (source `label`, always 1) and every other Recipe in the pooled top 5 of every config, strategy and Ablation
arm, judged against the query (source `judged`). Only the relevant rows count.
"""

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import evaluate
import failures
import metrics
import significance

ROOT = Path(__file__).resolve().parent.parent
QRELS = ROOT / "eval" / "qrels.csv"
OUT = ROOT / "eval" / "pooled"
COPIED = ["recipes.csv", "corpus.json"]


def rescore_rows(rows: list[dict], qrels: dict[str, set[int]]) -> list[dict]:
    """per_query.csv rows with `rank` replaced by the first right Recipe's rank. best_kind names the labelled
    Recipe's Chunk, so it is kept only where that Recipe is still the first right one."""
    out = []
    for r in rows:
        right = qrels.get(r["query_id"])
        if not right or int(r["recipe_id"]) not in right:
            raise ValueError(f"qrels miss the labelled Recipe of {r['query_id']}")
        top = [int(x) for x in r["top_recipe_ids"].split()]
        rank = metrics.first_rank(right, top)
        new = {**r, "rank": rank or ""}
        if "best_kind" in r and rank != metrics.rank_of(int(r["recipe_id"]), top):
            new["best_kind"] = ""
        out.append(new)
    return out


def rescore_metrics(old: list[dict], rows: list[dict]) -> list[dict]:
    """metrics.json rows with the metric columns recomputed from `rows`; latency and short lists as measured."""
    ranks: dict[tuple, list] = {}
    for r in rows:
        side = (r["config"], r.get("variant", "default"), r["strategy"])
        ranks.setdefault(side, []).append(int(r["rank"]) if r["rank"] else None)
    out = []
    for m in old:
        side = (m["config"], m.get("variant", "default"), m["strategy"])
        scores = metrics.average([metrics.query_scores(rank) for rank in ranks[side]])
        if scores["queries"] != m["queries"]:
            raise ValueError(f"{side}: {scores['queries']} queries in per_query.csv, {m['queries']} in metrics.json")
        out.append({**m, **scores})
    return out


def write_metrics_csv(path: Path, rows: list[dict]) -> None:
    """Same columns as evaluate.write_run."""
    stages = ["total", *evaluate.STAGES]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["config", "variant", "strategy", "queries", *metrics.COLUMNS, "short_lists",
                    *(f"{st}_{p}" for st in stages for p in ("p50_ms", "p95_ms"))])
        for r in rows:
            lat = r["latency_ms"]
            w.writerow([r["config"], r.get("variant", "default"), r["strategy"], r["queries"],
                        *(round(r[m], 4) for m in metrics.COLUMNS), r["short_lists"],
                        *(round(lat[st][p], 2) if st in lat else "" for st in stages for p in ("p50_ms", "p95_ms"))])


def rescore(run_dir: Path, qrels_path: Path = QRELS, out: Path = OUT) -> Path:
    """Write the rescored copy of `run_dir` and return its folder."""
    qrels = metrics.read_qrels(qrels_path)
    dest = out / run_dir.name
    dest.mkdir(parents=True, exist_ok=True)
    settings = json.loads((run_dir / "settings.json").read_text())
    settings["rescored_from"] = str(run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir)
    settings["qrels"] = str(qrels_path.relative_to(ROOT) if qrels_path.is_relative_to(ROOT) else qrels_path)
    settings["qrels_sha256"] = hashlib.sha256(qrels_path.read_bytes()).hexdigest()
    (dest / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    for name in COPIED:
        if (run_dir / name).exists():
            shutil.copyfile(run_dir / name, dest / name)

    with open(run_dir / "per_query.csv", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, rescore_rows(list(reader), qrels)
    with open(dest / "per_query.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    new = rescore_metrics(json.loads((run_dir / "metrics.json").read_text()), rows)
    (dest / "metrics.json").write_text(json.dumps(new, indent=2) + "\n")
    write_metrics_csv(dest / "metrics.csv", new)
    (dest / "table.md").write_text(evaluate.markdown([{"variant": "default", **r} for r in new]))
    significance.run(dest)
    failures.run(dest)
    return dest


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dirs", type=Path, nargs="+", help="Evaluation run folders, e.g. eval/runs/<timestamp>")
    p.add_argument("--qrels", type=Path, default=QRELS)
    return p.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    for run in a.run_dirs:
        try:
            dest = rescore(run.resolve(), a.qrels.resolve())
        except (ValueError, FileNotFoundError) as e:
            sys.exit(f"rescore: {run}: {e}")
        print(f"{run} -> {dest.relative_to(ROOT)}")
