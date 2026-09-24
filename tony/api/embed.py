"""Query embeddings from Ollama, matching how chunks were embedded at ingest."""

import httpx
import numpy as np

from . import config


def embed_query(client: httpx.Client, text: str) -> str:
    """nomic-embed-text of 'search_query: <text>', L2-normalized, as a pgvector literal."""
    r = client.post(f"{config.OLLAMA_URL}/api/embed",
                    json={"model": config.EMBED_MODEL, "input": [f"search_query: {text}"]})
    r.raise_for_status()
    v = np.asarray(r.json()["embeddings"][0], dtype=np.float32)
    v /= np.linalg.norm(v)
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"
