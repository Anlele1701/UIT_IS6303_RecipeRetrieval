"""M0 latency probe: how fast can Reranking get on this CPU-only machine? Writes eval/latency_probe.json.

    uv run scripts/latency_probe.py

Takes N queries (seeded) from the A1 Query set, builds the real fused candidates Hybrid would rerank,
and times several reranker settings on exactly those candidates. Latency only: quality for the
smaller-model and fewer-candidates options comes from A1's Ablation runs (reranker-*, rerank-top-*).
"""

import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import psycopg  # noqa: E402
import torch  # noqa: E402
from sentence_transformers import CrossEncoder  # noqa: E402

from api import config, retrieval  # noqa: E402
from api.embed import embed_query  # noqa: E402
from api.filters import SearchParams  # noqa: E402

OUT = ROOT / "eval" / "latency_probe.json"
SEED = 42
N = 10
# name -> (model, max_length, candidates)
SETTINGS = {
    "mxbai-base len512 top50 (served)": ("mixedbread-ai/mxbai-rerank-base-v1", 512, 50),
    "mxbai-base len512 top20": ("mixedbread-ai/mxbai-rerank-base-v1", 512, 20),
    "mxbai-base len256 top50": ("mixedbread-ai/mxbai-rerank-base-v1", 256, 50),
    "minilm-l6 len512 top50": ("cross-encoder/ms-marco-MiniLM-L-6-v2", 512, 50),
    "minilm-l6 len512 top20": ("cross-encoder/ms-marco-MiniLM-L-6-v2", 512, 20),
}


def main():
    texts = [json.loads(line)["text"] for line in (ROOT / "eval" / "queries.jsonl").read_text(encoding="utf-8").splitlines()]
    queries = random.Random(SEED).sample(texts, N)
    cands = []
    with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=60) as http:
        for q in queries:
            params = SearchParams(q=q, strategy="semantic", k=config.MAX_K)
            fused = retrieval.fused_candidates(conn, params, embed_query(http, q))
            cands.append((q, [c.content for c in fused]))
    chars = [len(t) for _, cs in cands for t in cs]
    res = {"seed": SEED, "queries": N, "torch": torch.__version__, "torch_threads": torch.get_num_threads(),
           "candidate_chars_median": statistics.median(chars), "settings": {}}
    models = {}
    for name, (model, max_len, top) in SETTINGS.items():
        key = (model, max_len)
        if key not in models:
            models[key] = CrossEncoder(model, device="cpu", max_length=max_len)
        ce = models[key]
        ce.predict([(cands[0][0], t) for t in cands[0][1][:top]], batch_size=32)  # warm-up
        ms = []
        for q, cs in cands:
            s = time.perf_counter()
            ce.predict([(q, t) for t in cs[:top]], batch_size=32)
            ms.append((time.perf_counter() - s) * 1000)
        res["settings"][name] = {"model": model, "max_length": max_len, "candidates": top,
                                 "p50_ms": round(statistics.median(ms), 1), "max_ms": round(max(ms), 1)}
        print(f"{name:34} p50 {res['settings'][name]['p50_ms']:>8} ms", flush=True)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
