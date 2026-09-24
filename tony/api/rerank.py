"""Cross-encoder Reranking, loaded once at startup."""

import threading

import torch
from sentence_transformers import CrossEncoder

from . import config


class Reranker:
    def __init__(self, model: str = config.RERANK_MODEL):
        device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
        self.model = CrossEncoder(model, device=device, max_length=512)
        self.device = device
        self._lock = threading.Lock()  # endpoints run in a threadpool; one forward pass at a time

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        with self._lock:
            return self.model.predict([(query, t) for t in texts], batch_size=32).tolist()
