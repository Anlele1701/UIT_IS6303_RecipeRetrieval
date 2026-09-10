"""
Dense (embedding-based) retrieval. See docs/04_SEARCH_CONCEPT.md §4.2 and
docs/07_RETRIEVAL_METHODS.md §7.2.

Model choice is a placeholder (CONFIG.embedding_model_name) pending
Experiment 2 (docs/09_EXPERIMENTS.md) — do not treat it as final.
"""

import numpy as np

from src.config import CONFIG
from src.data.loader import Recipe
from src.retrieval.base import SearchResult


class DenseRetriever:
    def __init__(self, recipes: list[Recipe], corpus: list[str], model_name: str = CONFIG.embedding_model_name):
        from sentence_transformers import SentenceTransformer
        import faiss

        self.recipes = recipes
        self.model = SentenceTransformer(model_name)

        embeddings = self.model.encode(
            corpus,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True,  # so inner product == cosine similarity
        )
        embeddings = np.asarray(embeddings, dtype="float32")

        self.dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(embeddings)

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        query_emb = self.model.encode([query], normalize_embeddings=True)
        query_emb = np.asarray(query_emb, dtype="float32")

        scores, indices = self.index.search(query_emb, top_k)
        scores, indices = scores[0], indices[0]

        results = []
        for rank, (i, score) in enumerate(zip(indices, scores), start=1):
            if i < 0:
                continue
            recipe = self.recipes[i]
            results.append(
                SearchResult(
                    recipe_idx=recipe.recipe_idx,
                    rank=rank,
                    score=float(score),
                    name=recipe.name,
                    image=recipe.image,
                )
            )
        return results
