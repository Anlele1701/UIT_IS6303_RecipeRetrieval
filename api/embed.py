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


def embed_texts(client: httpx.Client, texts: list[str], prefix: str, batch: int = 32) -> np.ndarray:
    """L2-normalized vectors (one row per text) for `prefix + text`, in input order."""
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        r = client.post(f"{config.OLLAMA_URL}/api/embed",
                        json={"model": config.EMBED_MODEL, "input": [prefix + t for t in texts[i:i + batch]]},
                        timeout=120)
        r.raise_for_status()
        out.extend(r.json()["embeddings"])
    v = np.asarray(out, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def embed_documents(client: httpx.Client, texts: list[str]) -> np.ndarray:
    return embed_texts(client, texts, "search_document: ")


def embed_query_array(client: httpx.Client, text: str) -> np.ndarray:
    return embed_texts(client, [text], "search_query: ")[0]
