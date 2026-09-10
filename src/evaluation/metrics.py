"""
Retrieval metrics. See docs/08_EVALUATION.md for definitions.

All functions take:
    ranked_ids: list[int]       — recipe_idx in ranked order (top-1 first)
    relevant_ids: set[int]      — recipe_idx considered relevant for the query
                                   (graded relevance not modeled here; treat
                                   membership as relevance = 1)
"""

import math


def recall_at_k(ranked_ids: list[int], relevant_ids: set[int], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = set(ranked_ids[:k])
    hit = len(top_k & relevant_ids)
    return hit / len(relevant_ids)


def mrr(ranked_ids: list[int], relevant_ids: set[int]) -> float:
    for rank, rid in enumerate(ranked_ids, start=1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: list[int], relevant_ids: set[int], k: int) -> float:
    def dcg(ids: list[int]) -> float:
        return sum(
            (1.0 if rid in relevant_ids else 0.0) / math.log2(rank + 1)
            for rank, rid in enumerate(ids[:k], start=1)
        )

    actual_dcg = dcg(ranked_ids)
    ideal_ranked = list(relevant_ids)[:k] + [None] * max(0, k - len(relevant_ids))
    ideal_dcg = dcg([rid for rid in ideal_ranked if rid is not None])

    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg
