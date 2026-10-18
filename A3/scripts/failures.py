"""Failure analyzer: where the configs of one Evaluation run disagree. Reads the run folder, never searches.

    uv run scripts/failures.py eval/runs/20260928-002509
    uv run scripts/failures.py eval/runs/20260928-002509 --cases 5

Buckets, per Chunking strategy:
    sparse_win   Sparse rank <= 10 and Dense rank > 10 (or not in the top 20)
    dense_win    the reverse
    rerank_hurt  Hybrid ranks the Recipe worse than the Fusion baseline (a Hybrid miss counts as worst)
    rerank_help  the reverse: Hybrid ranks it better
A bucket is left out when the run lacks one of its two configs.

Also splits each config's metrics into high word overlap (every content word of the query is in the
Recipe's text) and low overlap (the rest), to show how much the synthetic queries favour Sparse.

Prints markdown and writes it to <run>/failures.md, and the same data to <run>/failures.json. Query text and
Recipe titles come from the Query set named in the run's settings.json.
"""

import argparse
import csv
import statistics
from collections import Counter
import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import metrics

ROOT = Path(__file__).resolve().parent.parent

FOUND_AT = 10  # a "win" means found in the top 10 by one method and not the other
HIGH_OVERLAP = 1.0  # the Query set's median: over half the queries share every content word
MISS = metrics.DEPTH + 1  # a Recipe not in the top DEPTH ranks below any found one


@dataclass(frozen=True)
class Bucket:
    first: str  # a config
    second: str  # the config it's compared with
    holds: Callable[[int, int], bool]  # (first's rank, second's rank) -> in the bucket; a miss is MISS
    meaning: str


BUCKETS = {
    "sparse_win": Bucket("sparse", "dense", lambda sparse, dense: sparse <= FOUND_AT < dense,
                         f"Sparse found the Recipe in the top {FOUND_AT}, Dense didn't"),
    "dense_win": Bucket("dense", "sparse", lambda dense, sparse: dense <= FOUND_AT < sparse,
                        f"Dense found the Recipe in the top {FOUND_AT}, Sparse didn't"),
    "rerank_hurt": Bucket("fusion", "hybrid", lambda fusion, hybrid: hybrid > fusion,
                          "Reranking ranked the Recipe lower than the Fusion baseline"),
    "rerank_help": Bucket("fusion", "hybrid", lambda fusion, hybrid: hybrid < fusion,
                          "Reranking ranked the Recipe higher than the Fusion baseline"),
}
TOP = 5  # the net effect counts moves into and out of the top 5, the headline R@5


def read_query_set(run_dir: Path, query_set: Path | None = None) -> dict[str, dict]:
    """Query id -> its Query set line. Defaults to the Query set the run used, checked by hash."""
    settings = json.loads((run_dir / "settings.json").read_text())
    path = query_set or ROOT / settings["query_set"]  # absolute paths survive the join
    expected = settings.get("query_set_sha256")
    if query_set is None and expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"{path} changed since the run; pass the Query set it used with --queries")
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {q["query_id"]: q for q in lines}


def read_ranks(run_dir: Path) -> dict[metrics.Key, int | None]:
    """(config, strategy, query id) -> the relevant Recipe's rank, or None if not in the top DEPTH.

    An Ablation run's arm rows are skipped: the analysis is of the configs as served.
    """
    with open(run_dir / "per_query.csv", newline="") as f:
        return {(r["config"], r["strategy"], r["query_id"]): int(r["rank"]) if r["rank"] else None
                for r in csv.DictReader(f) if r.get("variant", "default") == "default"}


def in_bucket(bucket: Bucket, ranks: dict[str, int | None]) -> bool:
    return bucket.holds(ranks[bucket.first] or MISS, ranks[bucket.second] or MISS)


def read_kinds(run_dir: Path) -> dict[metrics.Key, str]:
    """(config, strategy, query id) -> the Chunk kind that ranked the known Recipe ("" on a miss).

    Empty for runs made before evaluate.py recorded best_kind.
    """
    with open(run_dir / "per_query.csv", newline="") as f:
        return {(r["config"], r["strategy"], r["query_id"]): r["best_kind"] for r in csv.DictReader(f)
                if "best_kind" in r and r.get("variant", "default") == "default"}


def analyze(queries: dict[str, dict], ranks: dict[metrics.Key, int | None],
            kinds: dict[metrics.Key, str] | None = None) -> dict:
    """Bucket members and counts per strategy, metrics split by word overlap, and Reranking's net effect. Pure.

    With `kinds`, the rerank buckets are also split by the Chunk kind Hybrid ranked the Recipe on, to test
    whether Reranking goes wrong when it judges a Recipe by one Chunk.

    Covers the queries the run holds (a `--limit` run holds fewer than its Query set), in query id order.
    """
    configs = list(dict.fromkeys(c for c, _, _ in ranks))
    strategies = list(dict.fromkeys(s for _, s, _ in ranks))
    bucket_names = [name for name, b in BUCKETS.items() if b.first in configs and b.second in configs]
    qids = sorted({q for _, _, q in ranks})

    buckets, counts = {}, {}
    for s in strategies:
        buckets[s] = {name: [] for name in bucket_names}
        for qid in qids:
            by_config = {c: ranks.get((c, s, qid)) for c in configs}
            case = {"query_id": qid, "text": queries[qid]["text"],
                    "recipe_title": queries[qid]["recipe_title"], "ranks": by_config}
            for name in bucket_names:
                if in_bucket(BUCKETS[name], by_config):
                    buckets[s][name].append(case)
        counts[s] = {"queries": len(qids), **{name: len(cases) for name, cases in buckets[s].items()}}

    groups = {g: [q for q in qids if (queries[q]["word_overlap"] >= HIGH_OVERLAP) == (g == "high")]
              for g in ("high", "low")}
    overlap = {(c, s, g): metrics.average([metrics.query_scores(ranks.get((c, s, q))) for q in members])
               for c in configs for s in strategies for g, members in groups.items()}
    net = ({s: rerank_net([(ranks.get(("fusion", s, q)) or MISS, ranks.get(("hybrid", s, q)) or MISS)
                           for q in qids]) for s in strategies}
           if {"fusion", "hybrid"} <= set(configs) else {})
    hybrid_kinds = {}
    if kinds and net:
        kind = lambda s, q: kinds.get(("hybrid", s, q)) or "miss"  # noqa: E731
        hybrid_kinds = {s: {"all": dict(Counter(kind(s, q) for q in qids)),
                            **{b: dict(Counter(kind(s, c["query_id"]) for c in buckets[s][b]))
                               for b in ("rerank_hurt", "rerank_help")}}
                        for s in strategies}
    return {"configs": configs, "bucket_names": bucket_names, "buckets": buckets, "counts": counts,
            "group_sizes": {g: len(members) for g, members in groups.items()}, "overlap": overlap,
            "rerank_net": net, "hybrid_kinds": hybrid_kinds}


def rerank_net(pairs: list[tuple[int, int]]) -> dict:
    """What Reranking did overall, from (Fusion baseline rank, Hybrid rank) per query, a miss as MISS.

    Hurts are many but small; helps are fewer but bigger. This is the table that shows it.
    """
    hurt = [(f, h) for f, h in pairs if h > f]
    helped = [(f, h) for f, h in pairs if h < f]
    drops = sorted(h - f for f, h in hurt)
    left, entered = sum(f <= TOP < h for f, h in hurt), sum(h <= TOP < f for f, h in helped)
    return {"hurt": len(hurt), "help": len(helped), "same": len(pairs) - len(hurt) - len(helped),
            "hurt_left_top5": left, "help_entered_top5": entered, "net_into_top5": entered - left,
            "median_drop_when_hurt": statistics.median(drops) if drops else None,
            "hurt_left_top20": sum(h == MISS for _, h in hurt),
            "help_from_outside_top20": sum(f == MISS for f, _ in helped)}


def analyze_run(run_dir: Path, query_set: Path | None = None) -> dict:
    return analyze(read_query_set(run_dir, query_set), read_ranks(run_dir), read_kinds(run_dir))


def _rank(r: int | None) -> str:
    return str(r) if r else "-"


def markdown(report: dict, cases: int = 10) -> str:
    configs, counts, bucket_names = report["configs"], report["counts"], report["bucket_names"]
    out = [f"# Failure analysis\n\nRanks are over the top {metrics.DEPTH} unique Recipes; `-` means not found.\n",
           "## Counts per Chunking strategy\n",
           "| Strategy | Queries | " + " | ".join(bucket_names) + " |",
           "|---|" + "---:|" * (len(bucket_names) + 1)]
    out += [f"| {s} | {c['queries']} | " + " | ".join(str(c[b]) for b in bucket_names) + " |"
            for s, c in counts.items()]

    n = report["group_sizes"]
    out += ["", "## Metrics by word overlap\n",
            f"High overlap: every content word of the query is in the Recipe's text ({n['high']} queries). "
            f"Low: the rest ({n['low']} queries).\n",
            "| Config | Strategy | Overlap | " + " | ".join(metrics.LABELS[m] for m in metrics.COLUMNS) + " |",
            "|---|---|---|" + "---:|" * len(metrics.COLUMNS)]
    out += [f"| {c} | {s} | {g} | " + " | ".join(f"{r[m]:.3f}" for m in metrics.COLUMNS) + " |"
            for (c, s, g), r in report["overlap"].items()]

    for b in bucket_names:
        out += ["", f"## {b}: {BUCKETS[b].meaning}\n"]
        for s, by_bucket in report["buckets"].items():
            members = by_bucket[b]
            out += [f"### {s} ({len(members)})\n"]
            if not members:
                out += ["None.\n"]
                continue
            out += ["| Query id | Query | Recipe | " + " | ".join(configs) + " |",
                    "|---|---|---|" + "---:|" * len(configs)]
            out += [f"| {m['query_id']} | {m['text']} | {m['recipe_title']} | "
                    + " | ".join(_rank(m["ranks"][c]) for c in configs) + " |" for m in members[:cases]]
            if len(members) > cases:
                out += [f"\n{len(members) - cases} more, not listed."]
            out += [""]
    return "\n".join(out).rstrip() + "\n"


def as_json(report: dict) -> dict:
    """The report with the overlap split as rows, since JSON keys can't be tuples."""
    rows = [{"config": c, "strategy": s, "overlap": g, **r} for (c, s, g), r in report["overlap"].items()]
    return {**report, "overlap": rows}


def run(run_dir: Path, query_set: Path | None = None, cases: int = 10) -> Path:
    """Analyze one Evaluation run and write <run>/failures.md, plus failures.json for the report. Returns the .md."""
    report = analyze_run(run_dir, query_set)
    (run_dir / "failures.json").write_text(json.dumps(as_json(report), indent=2) + "\n")
    path = run_dir / "failures.md"
    path.write_text(markdown(report, cases))
    return path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", type=Path, help="an Evaluation run folder, e.g. eval/runs/<timestamp>")
    p.add_argument("--cases", type=int, default=10, help="cases listed per bucket and strategy (first N by query id)")
    p.add_argument("--queries", type=Path, help="the Query set, if not the one in the run's settings.json")
    return p.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    try:
        out = run(a.run_dir.resolve(), a.queries and a.queries.resolve(), a.cases)
    except (ValueError, FileNotFoundError) as e:
        sys.exit(f"failures: {e}")
    print(out.read_text())
    print(f"Written to {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
