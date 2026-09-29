# Is an eval-only Fusion baseline enough for the brief's Hybrid (RRF)?

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by:
Parent: ../map.md

## Question

The brief (Phase 4) says the core engine supports 4 mandatory configs, the third being "Hybrid (RRF)". Ours is the Fusion baseline: eval-only, never served by the API or UI (see `CONTEXT.md`).

- Is that enough, with the report saying why? Or does it need serving (an API mode and a UI option), which would be its own build ticket outside this map?
- How does the report name the configs: the brief's names once in a mapping table, then glossary names everywhere?

## Answer

- Eval-only is enough. Don't serve it. The brief asks that the engine supports the 4 configs and that they're compared in one metric table (Phase 5). The engine does support it: the Fusion baseline is `fused_candidates()` in `api/retrieval.py`, the same code Hybrid runs before Reranking. It just has no route. As a UI column it would be worse than Hybrid on quality and better only on speed, and the latency table already makes that point.
- Naming: §1 has one mapping table (brief name → glossary name → what it does). Glossary names everywhere after, which matches the config names in `metrics.json`. The table covers the trap: the brief's "Hybrid (RRF)" is our Fusion baseline, and its "Hybrid + Reranking" is our Hybrid.
- The "why eval-only" note sits in that §1 table as a row note: "evaluated, not served: Hybrid with Reranking switched off, kept to measure what Reranking adds". §3 points back to it.
- Side fact for "Which ablations to run": RRF runs in Python in the service layer (`rrf()` in `api/retrieval.py`), not in SQL. The brief allows either.
- No new build ticket. No glossary change: `CONTEXT.md` already defines the Fusion baseline and says to avoid "Hybrid RRF".
