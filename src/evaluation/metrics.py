"""
Retrieval metrics. See docs/08_EVALUATION.md for definitions.

Ranking functions take:
    ranked_ids: list[int]       — recipe_idx in ranked order (top-1 first)
    relevant_ids: set[int]      — recipe_idx considered relevant for the query
                                   (graded relevance not modeled here; treat
                                   membership as relevance = 1)

The bootstrap helpers exist because the constructed query set has only a few
hundred queries: a one-point difference in Recall@10 is well inside the noise
floor, so configurations must be compared with an interval, not a bare mean.
"""

import math

import numpy as np


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


def bootstrap_ci(
    values: list[float],
    n_boot: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for the mean of per-query scores."""
    if not values:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    sample = np.asarray(values, dtype="float64")
    draws = rng.integers(0, len(sample), size=(n_boot, len(sample)))
    means = sample[draws].mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    return (
        float(np.quantile(means, alpha)),
        float(np.quantile(means, 1.0 - alpha)),
    )


def paired_bootstrap(
    baseline: list[float],
    candidate: list[float],
    n_boot: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> dict:
    """
    Paired percentile bootstrap over the per-query score differences.

    Both lists must be aligned on the same queries in the same order. The
    reported p-value is the two-sided fraction of resampled mean differences
    that fall on the opposite side of zero from the observed difference.
    """
    if len(baseline) != len(candidate):
        raise ValueError(
            f"paired comparison needs aligned queries: {len(baseline)} vs {len(candidate)}"
        )
    if not baseline:
        return {"mean_diff": 0.0, "ci_low": 0.0, "ci_high": 0.0, "p_value": 1.0}

    rng = np.random.default_rng(seed)
    diff = np.asarray(candidate, dtype="float64") - np.asarray(baseline, dtype="float64")
    draws = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    means = diff[draws].mean(axis=1)

    observed = float(diff.mean())
    alpha = (1.0 - confidence) / 2.0
    crossings = float((means <= 0).mean()) if observed > 0 else float((means >= 0).mean())
    return {
        "mean_diff": observed,
        "ci_low": float(np.quantile(means, alpha)),
        "ci_high": float(np.quantile(means, 1.0 - alpha)),
        "p_value": min(1.0, 2.0 * crossings),
    }
