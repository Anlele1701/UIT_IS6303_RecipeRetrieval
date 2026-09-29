# Report outline

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by:
Parent: ../map.md

## Question

Map the old report's 7 sections onto this project and the brief's required content. For each section and subsection: its one claim (or "no claim, just setup"), and which data it needs.

Must fit somewhere:

- scope and modality (text-only), the 4 brief configs and their glossary names;
- dataset and the Query set: how it was built, the 57 hand rewrites, known-item ground truth, word overlap;
- Chunking strategy as a main-results axis, not an ablation;
- latency vs accuracy, logic placement, qualitative case studies, ablations (brief Phase 6);
- limitations: synthetic queries, one relevant Recipe per query, short lists counted as misses.

## Answer

Claims are provisional: each one is checked against the clean run and restated if it flips. Headline metric is R@5 (the API returns 5 results by default, `DEFAULT_K`), MRR second; tables show all metrics.

Header under the title: run folder, `git_commit`, `query_set_sha256`, read from the report run's `settings.json`.

**1. Problem and scope**

- 1.1 Problem: free-text query in, Recipes out. Text-only (brief Phase 1). No claim.
- 1.2 System: diagram of ParadeDB (BM25 + ANN), Ollama embedding, RRF in the FastAPI service, reranker on MPS. Logic placement argued here. Claim: the database does index work, the service does fusion and model inference. Links to §5 if "Which ablations to run" measures placement.
- 1.3 The four configs: brief names mapped to glossary names. Wording owned by "Is an eval-only Fusion baseline enough for the brief's Hybrid (RRF)?".

**2. Dataset**

- 2.1 Source and schema: Shengtao/recipe, fields used. No claim.
- 2.2 Chunks and Chunking strategies: the three Chunk kinds, the three strategies with parameters, Chunk counts. No claim.
- 2.3 Query set: 298 queries, LLM-written from one Recipe each, 57 hand rewrites, known-item ground truth, word overlap. Data: `queries.jsonl`.
- 2.4 Limits of the ground truth: synthetic queries, one relevant Recipe per query, short lists counted as misses. Claim: these numbers flatter Sparse; §6 measures by how much.

Exact stats for 2.1–2.3: "Dataset section stats".

**3. Evaluation setup**

Metrics (R@5 headline and why, MRR, nDCG), depth 20 unique Recipes, p50/p95 latency per stage. Protocol: one warm-up query, one query at a time, one M-series laptop. Full settings table from `settings.json`. Caveats placed here: ANN probe, hardware. Significance method from "Significance tests". No claim.

**4. Main results**

- 4.1 Configs. Claim: Fusion finds more, Reranking puts it on top. Placeholder: R@20 +6–7 pts single-stage → Fusion baseline; R@5 +7–9 pts Fusion baseline → Hybrid. Sparse ≈ Dense overall. Data: `metrics.json`, R@5 vs R@20.
- 4.2 Chunking strategy. Claim: it barely matters. Wording waits on "Significance tests". Data: the 12-row table.
- 4.3 Latency vs accuracy. Claim owned by "Latency vs accuracy framing". Data: per-stage p50/p95.

**5. Ablation**

- 5.1 Cross-encoder models (shortlist from "Which cross-encoder models to compare").
- 5.2+ from "Which ablations to run": `rrf_k`, candidate counts, maybe logic placement, maybe ANN probe (if "What to do about approximate Dense search" makes it an arm).

**6. Error analysis**

- 6.1 Failure Mode Analyzer counts per strategy (sparse_win / dense_win / rerank_hurt). Claim: Sparse and Dense miss different queries (~35 each way), which is why fusion helps. Data: `failures.md` counts.
- 6.2 Synthetic-query bias, word-overlap split. Provisional claim: high → low overlap costs Sparse ~40 pts R@5, Dense ~20–26. Exhibit owned by "Failure cases and the synthetic-query bias".
- 6.3 rerank_hurt, owned by "Explaining rerank_hurt".
- 6.4 Case studies and 6.5 dataset-specific error groups, owned by "Failure cases and the synthetic-query bias".

Order: population counts first, then zoom to cases.

**7. Conclusion**

- 7.1 Verdict and recommendation per use (still fog on the map).
- 7.2 Two or three lessons about method.
- 7.3 Limitations: a short paragraph pointing back to §2.4 and §3.
- 7.4 Future work.

**References**: short list at the end (dataset, RRF paper, nomic-embed-text, BGE reranker, ParadeDB, pgvector).

New ticket: [Dataset section stats](13-dataset-section-stats.md).
