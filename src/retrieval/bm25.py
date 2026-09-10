"""
BM25 sparse retrieval baseline. See docs/04_SEARCH_CONCEPT.md §4.1 and
docs/07_RETRIEVAL_METHODS.md §7.1.
"""

import re

from src.data.loader import Recipe
from src.retrieval.base import SearchResult


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Retriever:
    def __init__(self, recipes: list[Recipe], corpus: list[str]):
        """
        recipes: index-aligned with corpus; recipes[i].recipe_idx should
                 correspond to corpus[i].
        corpus:  searchable text per recipe (src.data.preprocessing.build_corpus).
        """
        from rank_bm25 import BM25Okapi  # local import: optional heavy dep

        self.recipes = recipes
        self.tokenized_corpus = [_tokenize(doc) for doc in corpus]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        query_tokens = _tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for rank, i in enumerate(ranked_indices, start=1):
            recipe = self.recipes[i]
            results.append(
                SearchResult(
                    recipe_idx=recipe.recipe_idx,
                    rank=rank,
                    score=float(scores[i]),
                    name=recipe.name,
                    image=recipe.image,
                )
            )
        return results
