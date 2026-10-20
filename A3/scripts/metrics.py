"""Evaluation metrics for known-item search: one relevant Recipe per query, binary relevance.

Pure: ranked Recipe ids in, a metrics table out. Nothing here touches the DB.
With a single relevant Recipe at rank r (1-based, counted over the top DEPTH unique Recipes):
    Recall@k = 1 if r <= k else 0
    RR       = 1 / r, or 0 if the Recipe isn't in the top DEPTH
    nDCG@k   = 1 / log2(r + 1) if r <= k else 0   (the ideal DCG is 1)
Each is averaged over every query in the Query set; a query with no results is a miss.

With pooled qrels (eval/qrels.csv) a query can have several right Recipes. Then r is the rank of the first
right one (`first_rank`), so every formula above stays as it is and the numbers mean the same thing.
"""

import csv
import math
from collections.abc import Iterable, Mapping
from pathlib import Path

import numpy as np

DEPTH = 20
RECALL_AT = (5, 10, 20)
NDCG_AT = (5, 10)
COLUMNS = [*(f"recall@{k}" for k in RECALL_AT), "mrr", *(f"ndcg@{k}" for k in NDCG_AT)]
LABELS = {**{f"recall@{k}": f"R@{k}" for k in RECALL_AT}, "mrr": "MRR", **{f"ndcg@{k}": f"nDCG@{k}" for k in NDCG_AT}}

Key = tuple[str, str, str]  # (config, strategy, query id)


def dedupe(recipe_ids: Iterable[int], depth: int = DEPTH) -> list[int]:
    """Each Recipe once, at its first appearance, cut to `depth`."""
    out: list[int] = []
    for rid in recipe_ids:
        if rid not in out:
            out.append(rid)
            if len(out) == depth:
                break
    return out


def rank_of(relevant: int, ranked: Iterable[int]) -> int | None:
    """1-based rank of the relevant Recipe among the top DEPTH unique Recipes, or None."""
    top = dedupe(ranked)
    return top.index(relevant) + 1 if relevant in top else None


def first_rank(relevant: set[int], ranked: Iterable[int]) -> int | None:
    """1-based rank of the first right Recipe among the top DEPTH unique Recipes, or None."""
    return next((i + 1 for i, rid in enumerate(dedupe(ranked)) if rid in relevant), None)


def read_qrels(path: Path) -> dict[str, set[int]]:
    """query id -> every right Recipe id, from a qrels CSV (query_id, recipe_id, relevant 1/0, ...)."""
    out: dict[str, set[int]] = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if r["relevant"] == "1":
                out.setdefault(r["query_id"], set()).add(int(r["recipe_id"]))
    return out


def query_scores(rank: int | None) -> dict[str, float]:
    scores = {f"recall@{k}": float(rank is not None and rank <= k) for k in RECALL_AT}
    scores["mrr"] = 1 / rank if rank else 0.0
    for k in NDCG_AT:
        scores[f"ndcg@{k}"] = 1 / math.log2(rank + 1) if rank and rank <= k else 0.0
    return scores


def metrics_table(relevant: Mapping[str, int | set[int]], runs: Mapping[Key, list[int]]) -> dict[tuple[str, str], dict]:
    """(config, strategy) -> averaged metrics plus the query count.

    `relevant` is query id -> its Recipe, or the set of its right Recipes. Every (config, strategy) seen in
    `runs` is scored over every query in `relevant`; a query missing from `runs` counts as a miss.
    """
    pairs = dict.fromkeys((c, s) for c, s, _ in runs)  # insertion order, no duplicates
    table = {}
    for config, strategy in pairs:
        table[config, strategy] = average([
            query_scores(first_rank(rid if isinstance(rid, set) else {rid}, runs.get((config, strategy, qid), [])))
            for qid, rid in relevant.items()])
    return table


def average(per_query: list[dict[str, float]]) -> dict:
    """Each metric averaged over the queries' scores, plus the query count."""
    n = len(per_query)
    return {**{col: sum(q[col] for q in per_query) / n if n else 0.0 for col in COLUMNS}, "queries": n}


def latency_summary(ms: Iterable[float]) -> dict[str, float]:
    """p50 and p95 in milliseconds (linear interpolation)."""
    values = list(ms)
    if not values:
        return {"p50_ms": 0.0, "p95_ms": 0.0}
    p50, p95 = np.percentile(values, [50, 95])
    return {"p50_ms": float(p50), "p95_ms": float(p95)}
