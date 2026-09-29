# Which cross-encoder models to compare

Type: research
Status: resolved
Blocked by:
Parent: ../map.md

## Question

The ablations will compare cross-encoder models for Reranking. Today it's `BAAI/bge-reranker-base`, loaded by `sentence_transformers.CrossEncoder` in `api/rerank.py` with `max_length=512`, on MPS.

Find 2–4 candidates that:

- load with `CrossEncoder(name)` unchanged (or say what would have to change);
- are off-the-shelf, no fine-tuning (brief constraint);
- include the brief's own suggestion, `cross-encoder/ms-marco-MiniLM-L-6-v2`;
- span size vs quality (e.g. a smaller/faster one and a larger/stronger one than bge-reranker-base).

For each: parameter count, max input length, licence, training data (MS MARCO or other), and expected latency relative to bge-reranker-base for 50 pairs on an M-series Mac. Flag any that need special handling (e.g. `trust_remote_code`, LLM-based rerankers).

## Answer

Full table and sources: [research/cross-encoder-candidates.md](../research/cross-encoder-candidates.md). Latencies are estimates from parameter counts, not measurements.

- Every shortlisted model is a drop-in through `RERANK_MODEL`. No code change. Score scales differ but only the order is used.
- Shortlist:
  - `cross-encoder/ms-marco-MiniLM-L6-v2`: the brief's pick (old name `-L-6-v2` redirects). 22.7M params, ~7-8x faster than today's.
  - `BAAI/bge-reranker-v2-m3`: 568M, ~3.5x slower. Same family as today, bigger.
  - `mixedbread-ai/mxbai-rerank-base-v1`: about today's compute, different training data. Separates "better training" from "bigger model".
  - Optional: `Alibaba-NLP/gte-reranker-modernbert-base` (~1.3x slower).
- Dropped: jina rerankers (need `trust_remote_code`; v2 is non-commercial), mxbai-rerank-base-v2 (LLM-based), MiniLM-L12 (no gain over L6), bge-reranker-large (same cost as v2-m3, older).
- `max_length=512` stays, so long-context models get no benefit from their window here.
- The ablation must time each arm with the existing `rerank` stage.
