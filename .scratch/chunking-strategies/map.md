# Chunking strategies side by side

Label: wayfinder:map

## Destination

A spec, ready to implement, for storing fixed-size, sentence-based and semantic Chunking strategies side by side, picking one per search (API parameter + UI picker), with each strategy's scores isolated from the others.

Reached 2026-09-27: [spec.md](spec.md).

## Notes

- Domain: recipe retrieval, ParadeDB (pg_search + pgvector), FastAPI `api/`, Vite UI `ui/`, ingest in `scripts/ingest.py`. Terms in `CONTEXT.md`; decisions in `docs/adr/`.
- Every session: call the Skill tool for "grilling" and "domain-modeling" on grilling tickets.
- Settled while charting:
  - Term is **Chunking strategy** (not Chunker). Code will be renamed to match: `chunker` → `strategy`.
  - Strategies vary only how directions are cut into Step chunks. Summary and Ingredients chunks are identical under every strategy.
  - The existing `semantic-v1` data (~32.7k recipes, ~70 min to embed) is kept as-is as the semantic strategy (value renamed to `semantic` during migration).
  - Strategy is chosen per request in the API and with a picker in the UI.
- Planning only: no code changes on this map.

## Decisions so far

- [Does ParadeDB mix corpus stats across strategies?](issues/01-paradedb-stats-across-strategies.md): yes, BM25 stats are index-wide; isolation needs one ParadeDB index per strategy (separate tables or list partitions).
- [How the schema keeps strategies isolated](issues/04-isolation-design.md): `chunk` partitioned by list on `strategy`, one ParadeDB index per partition (ADR-0002).
- [Measure semantic-v1's chunk sizes](issues/02-measure-semantic-chunk-sizes.md): Step chunks median 185 chars / 3 sentences, max 400; 15% under 80 chars from split-after-merge, so match the distribution, not just the mean.
- [Settings for fixed-size and sentence-based](issues/03-fixed-and-sentence-settings.md): `fixed` = 56 nomic tokens on word boundaries, `sentence` = 3 sentences, no overlap anywhere; both tuned to semantic's chunk count and mean. Names `semantic`/`fixed`/`sentence`.
- [Where a strategy's name and settings live](issues/05-where-strategy-settings-live.md): a `chunking_strategy` table (name, method, parameters jsonb, loaded_at) with a foreign key from `chunk.strategy`; ingest registers the row (with a staging table, attached as the partition only once loaded; see the ingest ticket), a crashed run is dropped and rebuilt, only loaded strategies are listed.
- [How the live DB moves to partitions without re-embedding](issues/06-migrate-live-db-to-partitions.md): copy (not attach) into a new partitioned `chunk` in one `psql` transaction, ids kept, old table kept as `chunk_legacy` until exact-score checks pass; the value rename forces one index rebuild either way.
- [API and UI contract for picking a strategy](issues/07-api-ui-contract.md): required `strategy` param on every search endpoint (no default, `CHUNKER` removed), checked per request with 422s, `GET /strategies` lists loaded ones, `/health` counts per strategy, response echoes it; UI picker sits next to the search box and re-runs the query.
- [Ingest command shape for one strategy](issues/08-ingest-command-shape.md): `chunk <name>` loads into a standalone staging table, checks completeness, then builds the index and attaches it as the partition with `loaded_at` in one transaction; `drop <name>` (`--yes` if loaded), `index` removed, `load` refuses while strategies exist; strategies defined in a `STRATEGIES` dict, each re-embeds its own Summary/Ingredients.

## Not yet specified


## Out of scope

- Evaluation (test queries, relevance judgments, runs, metrics): its own session later. Guardrail for this map: nothing here may block judging relevance per Recipe, since chunk ids differ across strategies.
