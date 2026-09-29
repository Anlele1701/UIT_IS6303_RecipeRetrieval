# What to do about approximate Dense search

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by: 02
Parent: ../map.md

## Question

Dense search runs on ParadeDB's ANN cluster index at `vector_cluster_max_probe` 0.02. On synthetic vectors it found ~78% of the exact top 50 (see "What vector index does ParadeDB build for our embeddings?"). That caps Dense, and through it the Fusion baseline and Hybrid, before any model gets a say.

- First, a measurement: exact vs ANN recall on the real Query set's embeddings, at the eval's `chunk_pool` (100), per Chunking strategy. Does the known Recipe drop out of the ANN list but stay in the exact one?
- Then decide: keep the default and report it as a limitation, raise the probe for the report's runs (and the served API?), or make probe an ablation (recall vs latency)?
- Pin the ParadeDB image to a digest or version so the report's numbers stay reproducible?
- Anything that changes the settings must be decided before "Clean Evaluation run on a committed tree", or that run happens twice.

## Answer

Measurement: [research/ann-vs-exact-dense.md](../research/ann-vs-exact-dense.md). At the default probe 0.02, Dense returns ~78% of the exact top 100 Chunks and loses 2.0–3.4 pts R@5 against exact search. The known Recipe drops out of the top 20 in 7–15 queries per Chunking strategy. Exact costs ~+45 ms per Dense call. 0.05 is identical to 0.02.

- Main runs keep the default probe (0.02). The main table measures what the API serves, and changing the served API is out of scope.
- New ablation arm, **exact Dense** (probe 1.0 vs 0.02): measured on Dense, the Fusion baseline and Hybrid, on all 3 Chunking strategies. Paired bootstrap on R@5 and MRR, in the Holm family: 9 more tests, 72 → 81. Record the dense stage p50/p95 too. It shows whether Reranking wins back what the index loses.
- Only 0.02 vs 1.0, no 0.2 midpoint. The claim is "what approximation costs", not index tuning. The table in the research file can back §5 if a curve is wanted.
- Pin the ParadeDB image by digest (`paradedb/paradedb@sha256:8da5d202fe31875af32a49e802ce17cfbc146b0672306f4109809efee1e6f916`, `pg_search 0.25.9`) as a step in "Clean Evaluation run on a committed tree", so that run's commit already has the pin. Vector search is beta in 0.25.x and a floating tag can change Dense numbers on re-pull.
- `settings.json` records the `pg_search` version and the probe value, so the page can show them.
- Report: §3 has one line saying Dense is ANN at probe 0.02 on the pinned version. §5 carries the exact-Dense arm with its CIs. Not an §6 error category.
- Build item for the spec: `scripts/evaluate.py` needs a way to set the probe for an arm (a session `SET paradedb.vector_cluster_max_probe`), without touching the served API.
