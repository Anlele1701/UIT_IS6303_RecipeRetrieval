# Cross-encoder candidates for the Reranking ablation

Answers `issues/03-cross-encoder-candidates.md`. Checked 2026-09-28 against Hugging Face model cards, the Hub API (`/api/models/<id>` for licence and safetensors parameter count), each repo's `config.json`, and the sentence-transformers docs. Nothing was downloaded or benchmarked.

## Context from the code

- `api/rerank.py` builds `CrossEncoder(model, device=..., max_length=512)` and calls `predict(pairs, batch_size=32)`. The model name comes from `RERANK_MODEL` (`api/config.py`), so any model that loads with a plain `CrossEncoder(name)` can be swapped in by setting the env var. No code change needed.
- `api/retrieval.py` uses the score only to sort. Different score scales (raw logit, sigmoid, softmax) don't matter for ranking.
- Installed: sentence-transformers 6.1.0, transformers 5.17.0, torch 2.14.0 (`.venv`). That covers every "requires" note below (ModernBERT needs transformers >= 4.48; mxbai v2 was saved with sentence-transformers 5.4).
- `max_length=512` caps every candidate at 512 tokens, so the long-context models (8k) get no benefit from their longer window here.

## How the latency estimate works

This is an estimate, not a measurement. Encoder compute per token scales with the non-embedding parameters (the transformer layers). The embedding table is a lookup and costs almost nothing. That matters here: 192M of bge-reranker-base's 278M parameters are its 250k-token multilingual vocabulary, so its real compute is only about 86M parameters.

Estimate = non-embedding params / 86M (bge-reranker-base), same 50 pairs, same 512 cap, same English text. Adjustments noted where the architecture is slower or faster than plain BERT per parameter (DeBERTa's disentangled attention is slower; a decoder LLM adds a prompt template). Non-embedding counts = safetensors total minus `vocab_size x hidden_size` (and position table), from each `config.json`.

Real MPS timings will differ (kernel support, padding, batch size), so the ablation should time each model with the existing `watch("rerank")` stage.

## Comparison

| Model | Params (total / non-embedding) | Max length (model) | Licence | Training data | Plain `CrossEncoder(name)`? | Special handling | Est. latency vs bge-reranker-base (50 pairs, MPS) |
|---|---|---|---|---|---|---|---|
| `BAAI/bge-reranker-base` (current) | 278M / ~86M (XLM-RoBERTa-base, 12 layers, 768) | 512 | MIT | "multilingual pair data" (FlagEmbedding); Chinese + English | Yes | None | 1x (baseline) |
| `cross-encoder/ms-marco-MiniLM-L6-v2` (brief's pick; old name `-L-6-v2` redirects) | 22.7M / ~11M (6 layers, 384) | 512 | Apache-2.0 | MS MARCO passage ranking, English | Yes (ST's own model) | None | ~0.13x (about 7-8x faster) |
| `cross-encoder/ms-marco-MiniLM-L12-v2` | 33.4M / ~21M (12 layers, 384) | 512 | Apache-2.0 | MS MARCO, English | Yes | None | ~0.25x (about 4x faster) |
| `mixedbread-ai/mxbai-rerank-xsmall-v1` | 70.8M / ~22M (DeBERTa-v3, 12 layers, 384) | 512 | Apache-2.0 | Real search queries + top-10 engine results, relevance labelled by an LLM | Yes (card shows it) | None | ~0.3-0.4x |
| `mixedbread-ai/mxbai-rerank-base-v1` | 184M / ~86M (DeBERTa-v3, 12 layers, 768) | 512 | Apache-2.0 | Same as xsmall | Yes (card shows it) | None | ~1.2-1.5x (same size, DeBERTa attention is slower) |
| `Alibaba-NLP/gte-reranker-modernbert-base` | 150M / ~111M (ModernBERT, 22 layers, 768) | 8192 | Apache-2.0 | GTE/mGTE recipe (see mGTE paper); English | Yes | transformers >= 4.48 (have 5.17). flash-attn optional, not on MPS | ~1.3x |
| `jinaai/jina-reranker-v2-base-multilingual` | 278M / ~86M | 1024 | **CC-BY-NC-4.0** | Not stated on card; multilingual query-doc pairs | **No**: needs `trust_remote_code=True` | Custom code, flash-attn by default (fall back needed on MPS), non-commercial licence | ~1x (if it runs on MPS) |
| `jinaai/jina-reranker-v1-turbo-en` | 37.8M / ~14M | 8192 | Apache-2.0 | Not stated | **No**: `trust_remote_code=True` (JinaBert) | Custom code | ~0.2x |
| `BAAI/bge-reranker-large` | 560M / ~303M (XLM-RoBERTa-large, 24 layers, 1024) | 512 | MIT | Same as base | Yes | None | ~3.5x |
| `BAAI/bge-reranker-v2-m3` | 568M / ~303M (bge-m3 backbone, 24 layers, 1024) | 8194 | Apache-2.0 | bge-m3-data + Quora + FEVER, multilingual | Yes | None | ~3.5x |
| `mixedbread-ai/mxbai-rerank-large-v1` | 435M / ~304M (DeBERTa-v3, 24 layers, 1024) | 512 | Apache-2.0 | Same as xsmall v1 | Yes | None | ~4-5x |
| `mixedbread-ai/mxbai-rerank-base-v2` | 494M / ~358M (Qwen2 0.5B decoder) | 32768 | Apache-2.0 | GRPO + contrastive + preference learning (ProRank paper) | Yes, via ST's `LogitScore` module (ST >= 5.4; have 6.1) | **LLM-based reranker**: decoder with a chat template around each pair | ~4-6x (plus prompt overhead) |

Published quality numbers, for orientation only (different benchmarks, not comparable across rows):

- MS MARCO family (V100): MiniLM-L6-v2 NDCG@10 74.30 on TREC DL19, 1800 docs/s; L12-v2 74.31, 960 docs/s. L12 buys almost nothing over L6 on MS MARCO.
- Mixedbread's BEIR (11 datasets) table: bge-reranker-base 41.6, bge-reranker-large 45.2, mxbai-xsmall-v1 43.9, mxbai-base-v1 46.9, mxbai-large-v1 48.8. Vendor-run.
- mxbai v2 card: base-v2 BEIR avg 55.57, large-v1 49.32 (their own eval, A100).
- gte-reranker-modernbert-base card: BEIR 56.19.

## Recommended shortlist

1. **`cross-encoder/ms-marco-MiniLM-L6-v2`**: required by the brief; the small, fast end (~7-8x faster), English, MS MARCO only. Tests whether a tiny model is good enough.
2. **`BAAI/bge-reranker-v2-m3`**: the large, stronger end. Same family and loading path as the current model, drop-in via `RERANK_MODEL`, Apache-2.0. ~3.5x slower, which is the cost the ablation should put a number on.
3. **`mixedbread-ai/mxbai-rerank-base-v1`**: same compute size as bge-reranker-base but different training data (LLM-labelled web search), and a higher published BEIR score. Isolates "better training" from "bigger model".
4. Optional: **`Alibaba-NLP/gte-reranker-modernbert-base`**: newest English-only encoder, similar cost, loads plainly. Add only if time allows.

Left out: jina rerankers (need `trust_remote_code`, which `api/rerank.py` doesn't pass; v2 is non-commercial and defaults to flash-attn), mxbai-rerank-base-v2 (LLM-based, heaviest, and it's a different kind of model than the rest), MiniLM-L12-v2 (no gain over L6 on its own benchmark), bge-reranker-large (same cost as v2-m3, older).

## Sources

- https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2 (card, performance table)
- https://huggingface.co/cross-encoder/ms-marco-MiniLM-L12-v2
- https://sbert.net/docs/cross_encoder/pretrained_models.html
- https://huggingface.co/BAAI/bge-reranker-base (card: "We train the cross-encoder on a multilingual pair data")
- https://huggingface.co/BAAI/bge-reranker-large
- https://huggingface.co/BAAI/bge-reranker-v2-m3 (training data list)
- https://huggingface.co/mixedbread-ai/mxbai-rerank-xsmall-v1
- https://huggingface.co/mixedbread-ai/mxbai-rerank-base-v1 (CrossEncoder usage, BEIR table)
- https://huggingface.co/mixedbread-ai/mxbai-rerank-large-v1
- https://www.mixedbread.com/blog/mxbai-rerank-v1 (training data sentence)
- https://huggingface.co/mixedbread-ai/mxbai-rerank-base-v2 and its `modules.json` / `config_sentence_transformers.json` (LogitScore, ST 5.4.0)
- https://www.arxiv.org/abs/2506.03487 (ProRank, mxbai v2)
- https://huggingface.co/Alibaba-NLP/gte-reranker-modernbert-base
- https://aclanthology.org/2024.emnlp-industry.103/ (mGTE paper)
- https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual (trust_remote_code, flash-attn, CC-BY-NC)
- https://huggingface.co/jinaai/jina-reranker-v1-turbo-en
- Parameter counts, licences, architectures: `https://huggingface.co/api/models/<id>`; layer/hidden/vocab/max positions: `https://huggingface.co/<id>/resolve/main/config.json`
