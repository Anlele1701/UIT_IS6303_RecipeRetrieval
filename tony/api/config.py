"""Server settings. Every value can be overridden by an environment variable of the same name."""

import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://recipe:recipe@localhost:5434/recipe")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
RERANK_MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-base")

CHUNKER = os.environ.get("CHUNKER", "semantic-v1")  # the only Chunker searched

DEFAULT_K = 5
MAX_K = 50
HYBRID_CANDIDATES = int(os.environ.get("HYBRID_CANDIDATES", 50))  # top N from each retriever
RERANK_TOP = int(os.environ.get("RERANK_TOP", 50))  # fused candidates sent to the reranker
RRF_K = 60
