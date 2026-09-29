# Evaluation

What's left of the IS603 brief. Retrieval works; this is the work to prove which config is best.

## Destination

One table comparing 4 configs × every loaded Chunking strategy on Recall@5/10/20, MRR, nDCG@5/10 and latency, plus a failure analysis to write the report from.

## Brief coverage

- [x] Phase 1: environment (`docker-compose.yml`, `pyproject.toml`, layout)
- [x] Phase 3: ingest and index (`scripts/ingest.py`, `sql/`, 3 Chunking strategies)
- [x] Phase 4: 4 configs
  - [x] Sparse (`retrieval.sparse`)
  - [x] Dense (`retrieval.dense`)
  - [x] Fusion baseline: Hybrid without Reranking, eval only (`retrieval.fused_candidates`)
  - [x] Hybrid with Reranking (`retrieval.hybrid`)
- [x] Phase 2: ground truth (queries + qrels): `eval/queries.jsonl`
- [x] Phase 5: metrics engine, markdown table, JSON/CSV export (`scripts/evaluate.py`, all 4 configs)
- [ ] Phase 6: failure analyzer (`scripts/failures.py`, done), latency vs accuracy, report sections
- [x] README with run steps
- [x] Ollama (`nomic-embed-text`) documented or added to `docker-compose.yml` (`README.md`)

## Flow

- [ ] `/research`: how to build pseudo-qrels for a corpus with no queries (optional, background)
- [x] `/grill-with-docs`: skipped; open questions settled with defaults in [spec.md](spec.md)
- [x] `/to-spec` → [spec.md](spec.md)
- [x] `/to-tickets` → [issues/](issues/) (01–05)
- [ ] `/implement` each ticket, `/clear` between them

## Open questions

None open. All settled with defaults, see Decisions. Challenge any of them before `/implement` starts.

## Decisions

Full reasoning in [spec.md](spec.md), "Implementation Decisions".

- Test seams: a pure metrics function, plus the eval command end to end on `recipe_test`.
- Queries: 300 Recipes, 1 query each, stratified by category, fixed seed, written by a local Ollama model (`qwen2.5:7b`).
- Ground truth: known-item, one relevant Recipe per query, binary.
- Word overlap is recorded per query, not filtered on.
- Chunk → Recipe: first appearance wins. Sparse/Dense pull 100 Chunks.
- RRF-only is an eval-only baseline. The API and UI are unchanged. `CONTEXT.md` gets a term for it.
- Metrics are hand-written, not `ranx`.
- Results go in one gitignored folder per run: JSON, CSV, markdown.
- Latency is measured in process, per stage, p50/p95.

## Guardrails

- Judge relevance per Recipe, never per Chunk: chunk ids differ across Chunking strategies (from the chunking map).
- No training or fine-tuning.
- RRF stays in the backend, Reranking in the app layer.

## Out of scope

- New embedding or reranker models.
- Image or multimodal retrieval.
