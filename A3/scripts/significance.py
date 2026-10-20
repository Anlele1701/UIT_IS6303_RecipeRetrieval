"""Significance: paired bootstrap on R@5 and MRR for one Evaluation run. Reads the run folder, never searches.

    uv run scripts/significance.py eval/runs/20260928-122309
    uv run scripts/significance.py eval/runs/<ablation run>

A normal run gets the 15 fixed comparisons (per Chunking strategy: Hybrid vs Fusion baseline, Fusion baseline vs
Sparse and vs Dense, Sparse vs Dense; and the 3 strategy pairs under Hybrid) plus a CI on each config's own
score. An Ablation run gets its arm vs its default, per config and strategy.

Each comparison resamples queries with replacement (10,000 times, seeded) and takes the mean per-query
difference: a 95% percentile CI and a two-sided p, the share of resamples on the far side of 0, doubled.
Writes <run>/significance.json with raw p only. Holm runs across every run the report reads, so the report
bundle applies it, not this script. CIs are not adjusted.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

import metrics

SEED = 603
RESAMPLES = 10_000
METRICS = ["recall@5", "mrr"]
PAIRS = [("hybrid", "fusion"), ("fusion", "sparse"), ("fusion", "dense"), ("sparse", "dense")]
ACROSS_STRATEGIES = "hybrid"  # the config the Chunking strategy pairs are compared under

Side = tuple[str, str, str]  # (config, variant, strategy)


def _resampled_means(values: np.ndarray, resamples: int, seed: int) -> np.ndarray:
    """Mean of `values` over `resamples` draws of the same size, with replacement. Same seed, same draws."""
    idx = np.random.default_rng(seed).integers(0, len(values), (resamples, len(values)))
    return values[idx].mean(axis=1)


def paired_bootstrap(a: list[float], b: list[float], resamples: int = RESAMPLES, seed: int = SEED) -> dict:
    """a - b on per-query scores of the same queries, in the same order."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    means = _resampled_means(d, resamples, seed)
    lo, hi = np.percentile(means, [2.5, 97.5])
    p = min(1.0, 2 * min(float((means <= 0).mean()), float((means >= 0).mean())))
    return {"diff": float(d.mean()), "ci_lo": float(lo), "ci_hi": float(hi), "p_raw": p}


def interval(scores: list[float], resamples: int = RESAMPLES, seed: int = SEED) -> dict:
    values = np.asarray(scores, dtype=float)
    lo, hi = np.percentile(_resampled_means(values, resamples, seed), [2.5, 97.5])
    return {"mean": float(values.mean()), "ci_lo": float(lo), "ci_hi": float(hi)}


def read_scores(run_dir: Path) -> dict[Side, dict[str, dict[str, float]]]:
    """(config, variant, strategy) -> query id -> per-query metric scores."""
    out: dict[Side, dict] = {}
    with open(run_dir / "per_query.csv", newline="") as f:
        for r in csv.DictReader(f):
            side = (r["config"], r.get("variant", "default"), r["strategy"])
            out.setdefault(side, {})[r["query_id"]] = metrics.query_scores(int(r["rank"]) if r["rank"] else None)
    return out


def comparisons(sides: set[Side], arm: dict | None) -> list[tuple[Side, Side]]:
    """The (a, b) pairs to test, a first. Only pairs whose sides the run holds."""
    strategies = sorted({s for _, _, s in sides})
    if arm:
        wanted = [((c, "arm", s), (c, "default", s)) for c in arm["configs"] for s in strategies]
    else:
        wanted = [((a, "default", s), (b, "default", s)) for s in strategies for a, b in PAIRS]
        wanted += [((ACROSS_STRATEGIES, "default", s1), (ACROSS_STRATEGIES, "default", s2))
                   for i, s1 in enumerate(strategies) for s2 in strategies[i + 1:]]
    return [(a, b) for a, b in wanted if a in sides and b in sides]


def analyze(scores: dict[Side, dict], arm: dict | None, resamples: int = RESAMPLES, seed: int = SEED) -> dict:
    side = lambda s: dict(zip(("config", "variant", "strategy"), s))  # noqa: E731
    tests = []
    for a, b in comparisons(set(scores), arm):
        qids = sorted(scores[a])
        if sorted(scores[b]) != qids:
            raise ValueError(f"{a} and {b} hold different queries, so they can't be paired")
        for m in METRICS:
            result = paired_bootstrap([scores[a][q][m] for q in qids], [scores[b][q][m] for q in qids],
                                      resamples, seed)
            tests.append({"a": side(a), "b": side(b), "metric": m, "queries": len(qids), **result})
    intervals = [{**side(s), "metric": m, **interval([v[m] for v in scores[s].values()], resamples, seed)}
                 for s in sorted(scores) for m in METRICS]
    return {"seed": seed, "resamples": resamples, "metrics": METRICS, "intervals": intervals, "comparisons": tests}


def run(run_dir: Path, resamples: int = RESAMPLES, seed: int = SEED) -> Path:
    """Test one run and write <run>/significance.json. Returns its path."""
    arm = json.loads((run_dir / "settings.json").read_text()).get("arm")
    path = run_dir / "significance.json"
    path.write_text(json.dumps(analyze(read_scores(run_dir), arm, resamples, seed), indent=2) + "\n")
    return path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", type=Path, help="an Evaluation run folder, e.g. eval/runs/<timestamp>")
    p.add_argument("--resamples", type=int, default=RESAMPLES)
    return p.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    try:
        out = run(a.run_dir.resolve(), a.resamples)
    except (ValueError, FileNotFoundError) as e:
        sys.exit(f"significance: {e}")
    data = json.loads(out.read_text())
    for t in data["comparisons"]:
        name = lambda s: f"{s['config']}{'' if s['variant'] == 'default' else ' (arm)'}/{s['strategy']}"  # noqa: E731
        print(f"{name(t['a']):>24} vs {name(t['b']):<24} {t['metric']:>8}  {t['diff']:+.3f} "
              f"[{t['ci_lo']:+.3f}, {t['ci_hi']:+.3f}]  p {t['p_raw']:.4f}")
    print(f"Written to {out}")
