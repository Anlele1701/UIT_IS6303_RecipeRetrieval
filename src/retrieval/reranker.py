"""
Cross-encoder reranking over a small candidate pool from HybridRetriever.
See docs/04_SEARCH_CONCEPT.md §4.4 and docs/07_RETRIEVAL_METHODS.md §7.4.

Candidate pool size (CONFIG.rerank_candidate_pool) is the variable studied
in Experiment 3 (docs/09_EXPERIMENTS.md) — 20/50/100.
"""

from src.config import CONFIG
from src.retrieval.base import SearchResult
from src.retrieval.hybrid import HybridRetriever


class Reranker:
    def __init__(self, model_name: str = CONFIG.reranker_model_name):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[SearchResult], top_k: int = 10) -> list[SearchResult]:
        if not candidates:
            return []

        pairs = [(query, c.name) for c in candidates]
        scores = self.model.predict(pairs)

        order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for rank, i in enumerate(order, start=1):
            c = candidates[i]
            results.append(
                SearchResult(
                    recipe_idx=c.recipe_idx,
                    rank=rank,
                    score=float(scores[i]),
                    name=c.name,
                    image=c.image,
                )
            )
        return results


class HybridRerankRetriever:
    """Wraps Hybrid retrieval + Reranker behind the standard search() interface."""

    def __init__(self, hybrid_retriever: HybridRetriever, reranker: Reranker, candidate_pool: int = CONFIG.rerank_candidate_pool):
        self.hybrid = hybrid_retriever
        self.reranker = reranker
        self.candidate_pool = candidate_pool

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        candidates = self.hybrid.search(query, top_k=self.candidate_pool)
        return self.reranker.rerank(query, candidates, top_k=top_k)
