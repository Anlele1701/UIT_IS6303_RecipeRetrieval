"""
Hybrid retrieval: BM25 + Dense combined via Reciprocal Rank Fusion (RRF).
See docs/04_SEARCH_CONCEPT.md §4.3 and docs/07_RETRIEVAL_METHODS.md §7.3.
"""

from src.retrieval.base import SearchResult
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever


def reciprocal_rank_fusion(
    rankings: list[list[SearchResult]],
    k: int = 60,
) -> list[tuple[int, float]]:
    """
    Standard RRF: score(d) = sum over rankings containing d of 1 / (k + rank).
    Returns (recipe_idx, fused_score) sorted descending by fused_score.
    """
    fused_scores: dict[int, float] = {}
    ref: dict[int, SearchResult] = {}

    for ranking in rankings:
        for result in ranking:
            fused_scores[result.recipe_idx] = fused_scores.get(result.recipe_idx, 0.0) + 1.0 / (k + result.rank)
            ref.setdefault(result.recipe_idx, result)

    return sorted(fused_scores.items(), key=lambda kv: kv[1], reverse=True)


class HybridRetriever:
    def __init__(self, bm25_retriever: BM25Retriever, dense_retriever: DenseRetriever, candidate_pool: int = 100):
        """
        candidate_pool: how many results to pull from each sub-retriever
        before fusing — should be >= any top_k you plan to request.
        """
        self.bm25 = bm25_retriever
        self.dense = dense_retriever
        self.candidate_pool = candidate_pool

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        bm25_results = self.bm25.search(query, top_k=self.candidate_pool)
        dense_results = self.dense.search(query, top_k=self.candidate_pool)

        # Keep a lookup so we can recover name/image after fusion.
        by_idx = {r.recipe_idx: r for r in bm25_results + dense_results}

        fused = reciprocal_rank_fusion([bm25_results, dense_results])[:top_k]

        results = []
        for rank, (recipe_idx, score) in enumerate(fused, start=1):
            base = by_idx[recipe_idx]
            results.append(
                SearchResult(
                    recipe_idx=recipe_idx,
                    rank=rank,
                    score=score,
                    name=base.name,
                    image=base.image,
                )
            )
        return results
