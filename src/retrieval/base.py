"""
Shared result type for all retrieval methods.

Per docs/06_TECHNICAL_DESIGN.md, every retrieval method (BM25, Dense,
Hybrid, Hybrid+Reranker) must return this same shape so evaluation code
can treat them interchangeably.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SearchResult:
    recipe_idx: int
    rank: int
    score: float
    name: str
    image: object  # PIL.Image.Image at runtime


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        ...
