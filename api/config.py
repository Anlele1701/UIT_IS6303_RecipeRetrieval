"""Server settings. Every value can be overridden by an environment variable of the same name."""

import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://recipe:recipe@localhost:5435/recipe")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
# Switched from BAAI/bge-reranker-base after its ablation; the Report run was measured with bge-reranker-base.
RERANK_MODEL = os.environ.get("RERANK_MODEL", "mixedbread-ai/mxbai-rerank-base-v1")

DEFAULT_K = 5
MAX_K = 50
HYBRID_CANDIDATES = int(os.environ.get("HYBRID_CANDIDATES", 50))  # top N from each retriever
RERANK_TOP = int(os.environ.get("RERANK_TOP", 50))  # fused candidates sent to the reranker
RRF_K = int(os.environ.get("RRF_K", 60))

# Chat pipeline (api/pipeline, A3). Query understanding and generation share the model; the judge and the
# independent checker use another family (scripts/checker.py, CHECKER_MODEL).
QU_MODEL = os.environ.get("QU_MODEL", "qwen2.5:7b")
GEN_MODEL = os.environ.get("GEN_MODEL", "qwen2.5:7b")
QU_TEMPERATURE = 0.0
GEN_TEMPERATURE = 0.2
SEED = 42
CHAT_STRATEGY = os.environ.get("CHAT_STRATEGY", "semantic")
CONTEXT_RECIPES = int(os.environ.get("CONTEXT_RECIPES", 5))  # k Recipes in the generation context
HISTORY_TURNS = 3  # user+assistant turns M1 sees
