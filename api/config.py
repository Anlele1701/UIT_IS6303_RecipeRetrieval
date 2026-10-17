"""Server settings. Every value can be overridden by an environment variable of the same name."""

import os
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://recipe:recipe@localhost:5434/recipe")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
# Switched from BAAI/bge-reranker-base after its ablation; the Report run was measured with bge-reranker-base.
RERANK_MODEL = os.environ.get("RERANK_MODEL", "mixedbread-ai/mxbai-rerank-base-v1")

# Dietary rules (api/dietary_rules.py). Guidelines are per day, recipes are per serving: a serving is
# assumed to be one meal. A design assumption, not a medical fact.
MEALS_PER_DAY = int(os.environ.get("MEALS_PER_DAY", 3))
RULES_PATH = os.environ.get("RULES_PATH", str(Path(__file__).with_name("dietary_rules.json")))
ALLERGENS_PATH = os.environ.get("ALLERGENS_PATH", str(Path(__file__).with_name("food_allergens.json")))

# Chat model for /recommend's explanation (the same Ollama as the embeddings).
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:7b")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", 180))  # seconds; a 7B model on CPU can be slow
RECOMMEND_CHUNKS = int(os.environ.get("RECOMMEND_CHUNKS", 30))  # Chunks asked of Hybrid, to be grouped into Recipes
RECOMMEND_MAX_K = 10  # most Recipes one /recommend call returns

DEFAULT_K = 5
MAX_K = 50
HYBRID_CANDIDATES = int(os.environ.get("HYBRID_CANDIDATES", 50))  # top N from each retriever
RERANK_TOP = int(os.environ.get("RERANK_TOP", 50))  # fused candidates sent to the reranker
RRF_K = int(os.environ.get("RRF_K", 60))
