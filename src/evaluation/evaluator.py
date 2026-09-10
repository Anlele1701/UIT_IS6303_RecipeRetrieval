"""
Run a retrieval method over the constructed query set and compute metrics.
See docs/08_EVALUATION.md for the protocol: same corpus, same queries,
same ground truth, same K values across all methods being compared.
"""

import json
import time
from pathlib import Path
from typing import Protocol

from src.evaluation.metrics import mrr, ndcg_at_k, recall_at_k
from src.evaluation.queries import EvalQuery


class SearchFn(Protocol):
    def __call__(self, query: str, top_k: int) -> list:
        ...


def evaluate(
    search_fn: SearchFn,
    queries: list[EvalQuery],
    k_values: tuple[int, ...] = (5, 10),
) -> dict:
    """
    search_fn: a callable like retriever.search(query, top_k) returning a
               list of SearchResult (src.retrieval.base.SearchResult).
    """
    max_k = max(k_values)
    per_query_latency = []
    recall_scores = {k: [] for k in k_values}
    mrr_scores = []
    ndcg_scores = {k: [] for k in k_values}

    for q in queries:
        start = time.perf_counter()
        results = search_fn(q.query_text, max_k)
        elapsed = time.perf_counter() - start
        per_query_latency.append(elapsed)

        ranked_ids = [r.recipe_idx for r in results]
        relevant_ids = set(q.relevant_recipe_ids)

        for k in k_values:
            recall_scores[k].append(recall_at_k(ranked_ids, relevant_ids, k))
            ndcg_scores[k].append(ndcg_at_k(ranked_ids, relevant_ids, k))
        mrr_scores.append(mrr(ranked_ids, relevant_ids))

    n = max(len(queries), 1)
    summary = {
        "num_queries": len(queries),
        "mrr": sum(mrr_scores) / n,
        "avg_latency_sec": sum(per_query_latency) / n,
    }
    for k in k_values:
        summary[f"recall@{k}"] = sum(recall_scores[k]) / n
        summary[f"ndcg@{k}"] = sum(ndcg_scores[k]) / n

    return summary


def save_run(summary: dict, config: dict, out_path: str) -> None:
    """
    Save a single evaluation run with its config, per docs/09_EXPERIMENTS.md
    reproducibility conventions (dataset version, subset size/seed, model,
    parameters, query set, metrics, execution time).
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    payload = {"config": config, "results": summary}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
