"""
Central configuration for the RecipeImageRetrieval project.

Keep experiment-affecting constants here so every script/module
(loader, retrievers, evaluator, app) agrees on the same values,
per the reproducibility requirements in docs/09_EXPERIMENTS.md
and docs/17.3 (recorded run parameters).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Config:
    # Dataset (see docs/03_DATASET.md)
    dataset_name: str = "ANDREEEWW/recipe-with-images"
    dataset_revision: str = "ddfbf91a6e33e46b69eb5b0b7faffa3b24f014bc"

    # Subset sampling (docs/03_DATASET.md §6.3) — TODO tune once resource
    # constraints on the dev machine are known.
    corpus_split: str = "train"
    subset_size: int = 5000
    seed: int = 42

    # Searchable text construction (docs/03_DATASET.md §6.4)
    text_fields: tuple = ("name", "ingredients", "description")

    # Retrieval defaults
    default_top_k: int = 10

    # Dense retrieval (docs/04_SEARCH_CONCEPT.md §4.2) — TODO finalize via
    # Experiment 2 in docs/09_EXPERIMENTS.md.
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Reranking (docs/04_SEARCH_CONCEPT.md §4.4)
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidate_pool: int = 50  # TODO tune via Experiment 3

    # Paths
    data_cache_dir: str = "data_cache"  # project-local cache for the built subset
    hf_cache_dir: Optional[str] = None  # None = default HF cache (~/.cache/huggingface/datasets)
    experiments_dir: str = "experiments"


CONFIG = Config()
