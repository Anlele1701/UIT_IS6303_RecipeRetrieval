# Explaining rerank_hurt

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by: 01
Parent: ../map.md

## Question

58–67 of 298 queries are rerank_hurt (Reranking put the right Recipe lower than the Fusion baseline did), yet Hybrid wins overall. Break this down from the clean run and decide how the report explains it.

- How big are the drops: small shuffles inside the top 10, or falls out of the top 20? How many rerank_help queries offset them?
- Is there a pattern: word overlap, Chunk kind of the winning hit, query length, category?
- Candidate cause: the reranker reads one Chunk (up to 512 tokens), not the whole Recipe.
- What goes in the report: a net-effect table, one case study, or both.

## Answer

Breakdown from the report run (`research/rerank_hurt_breakdown.py`, run from the repo root). Hybrid vs Fusion baseline on the right Recipe's rank, a miss counted as 21:

| | fixed | semantic | sentence |
|---|---:|---:|---:|
| rerank_hurt | 58 | 62 | 67 |
| rerank_help | 104 | 91 | 99 |
| same rank | 136 | 145 | 132 |
| hurt, left the top 5 | 10 | 18 | 14 |
| help, entered the top 5 | 37 | 38 | 37 |
| net into the top 5 | +27 | +20 | +23 |
| median drop when hurt | 1 | 2 | 2 |
| hurt, fell out of the top 20 | 1 | 0 | 1 |

- Hurts are mostly small: about two thirds drop 2 ranks or less, over half started at rank 1 in the Fusion baseline, 0–1 fall out of the top 20.
- Helps are bigger: 5–7 per strategy rescued from outside the top 20. Net +27 on fixed is the whole +9.1 pts R@5.
- No pattern in word overlap (hurt is 52–57% high overlap vs 52% overall) or query length (5.0–5.1 words vs 5.2).
- Unstable: 100 queries are rerank_hurt under at least one Chunking strategy, 30 under all three. Reads as near-ties flipping.
- The 512-token cut isn't a cause (Chunks are far shorter). The live hypothesis is that the reranker reads one Chunk, not the whole Recipe. It can't be tested from stored data: `per_query.csv` doesn't record which Chunk won.

Decisions:

- Claim (§6): Reranking moves about 60 queries down, mostly by 1–2 ranks, and about 100 up, often into the top 5; net +20 to +27 queries in the top 5. That's why Hybrid wins despite rerank_hurt.
- Exhibit: the net-effect table above plus one rerank_hurt case study. The case is picked in "Failure cases and the synthetic-query bias".
- Build item: `scripts/failures.py` gains a `rerank_help` bucket and a net-effect block (counts, top-5 crossings each way, drop sizes, out-of-top-20) in its JSON output, so the page reads it rather than computing it.
- Build item: `per_query.csv` records the Chunk kind (Summary, Ingredients, Step) of each config's best hit for the right Recipe. The report splits rerank_hurt by it. If no pattern shows, the report states the one-Chunk cause as an untested hypothesis. The cross-strategy instability (30 of 100) goes in as supporting evidence for near-tie flipping either way.
- Naming: `rerank_hurt` / `rerank_help` stay bucket labels, defined once next to the table. No glossary entry.
