# Which ablations to run

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by: 03
Parent: ../map.md

## Question

Settled: a cross-encoder model comparison (candidates from "Which cross-encoder models to compare").

Decide the rest, and the arms for each:

- `rrf_k` (default 60);
- candidate counts: `chunk_pool` (100), `hybrid_candidates` (50), `rerank_top` (50);
- logic placement: does it need an ablation (the old report compared RRF in SQL vs in the service layer), or is an argument enough? Ours runs RRF in Python, in the service layer (see "Is an eval-only Fusion baseline enough for the brief's Hybrid (RRF)?").
- anything else the outline needs, e.g. reranking on Sparse or Dense alone.

For each: which Chunking strategy it runs on (all three or one), and what the expected runtime is. Each arm gets a paired bootstrap against its default and counts toward the Holm family (see "Significance tests"), so fewer, sharper arms keep the correction from getting harsh. Remember the full run took ~11 min.

## Answer

Seven arms, each run on all three Chunking strategies, so the report can say whether an effect holds across strategies.

| Arm | Config measured | Against | Strategies |
|---|---|---|---|
| Cross-encoder: `cross-encoder/ms-marco-MiniLM-L6-v2`, `mixedbread-ai/mxbai-rerank-base-v1`, `BAAI/bge-reranker-v2-m3` | Hybrid | `BAAI/bge-reranker-base` | all 3 |
| `rrf_k` 10, 100 | Fusion baseline | k=60 | all 3 |
| `rerank_top` 20, 100 | Hybrid | 50 | all 3 |

- Each arm: paired bootstrap on R@5 and MRR against its default, in the Holm family (see "Significance tests"). 42 arm tests + 30 main = 72; strictest threshold ~0.0007, which 10k resamples still resolve. Small effects will read "no detectable difference", as expected for `rrf_k`.
- Record rerank p50/p95 for every cross-encoder and `rerank_top` arm; they feed §4.3 latency vs accuracy.
- `rrf_k` is measured on the Fusion baseline only: under Hybrid it only changes which 50 Chunks reach the reranker, which re-sorts them anyway.
- `rerank_top` 100 is the most the union of 50 + 50 candidates can give. Prediction to check: 20 barely moves R@5 (Fusion baseline R@20 ≈ Hybrid R@20 on the placeholder run) and cuts rerank latency ~60%.
- gte-reranker-modernbert-base dropped: same question as mxbai ("same cost, better training?"), two more tests.
- Logic placement: argued in §1.2, no arm. The brief allows RRF in "DB/SQL or backend"; ours is backend. The `rrf` stage costs ~0.1 ms, so moving it to SQL saves at most one round trip.
- Not run: Reranking on Sparse or Dense alone (§4.1's R@20 already shows what fusion adds), `hybrid_candidates`, `chunk_pool`.
- Runtime estimate from the placeholder run's per-stage p50: ~65 min for all arms (v2-m3 ~30 min, `rerank_top` 100 ~18 min). Budget is up to 8 h, so time doesn't limit arm choice.
- Build items for the spec: make `RRF_K` settable (it's a constant in `api/config.py`, the others are env vars), and give `scripts/evaluate.py` a way to run arms. How arm results are stored stays fog on the map.

## Addendum

"What to do about approximate Dense search" added an eighth arm: exact Dense (probe 1.0 vs 0.02) on Dense, the Fusion baseline and Hybrid, all 3 strategies. The Holm family grows 72 → 81. Details live on that ticket.
