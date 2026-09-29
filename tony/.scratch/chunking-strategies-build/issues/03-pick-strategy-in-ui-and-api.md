# 03: Pick a Chunking strategy in the UI and API

**What to build:** A user picks the Chunking strategy next to the search box, and all three result columns re-run under it. Every search endpoint requires a `strategy` (no default). Unknown or not-yet-loaded names get a clear 422. The API lists loaded strategies, reports chunk counts per strategy in health, and echoes the strategy in every response. The `CHUNKER` setting is gone. A strategy that finishes loading while the API is running shows up without a restart.

Spec: [../../chunking-strategies/spec.md](../../chunking-strategies/spec.md), "Slice 3". Decisions: API/UI ticket 07.

**Blocked by:** 02 (Semantic search runs on the partitioned `chunk`)

**Status:** done

- [x] A search with no `strategy`, an unknown one or an unloaded one returns 422 with the messages from the spec; `chunker=` is rejected
- [x] `GET /strategies` returns only loaded strategies, ordered by name
- [x] `/health` shows `chunks` per loaded strategy, and the Settings drawer's Services section shows them
- [x] Responses include `strategy`
- [x] The picker sits next to the search box, pre-selects `semantic` (or the last choice), re-runs the current query on change, and column headers show the strategy
- [x] With no loaded strategy, search is disabled with a message
- [x] Inserting a loaded registry row in a test DB makes it appear in `/strategies` without a restart
- [x] The built UI bundle served by the API is rebuilt

## Progress (2026-09-27)

- `api/strategies.py` reads `chunking_strategy` on every request (no cache). Search endpoints check the strategy in a dependency before embedding, so an unknown name never calls Ollama. The 422 keeps FastAPI's error shape (`loc: [query, strategy]`), so the UI shows it as `strategy: 'foo' is unknown; loaded: semantic`.
- Tests: 21 pass. The registry tests run against a throwaway `recipe_test` database built from `sql/schema.sql` in the same container, and skip if the container is down.
- Sparse now orders by `score DESC, id`. `EXPLAIN` shows ParadeDB still pushes the top-N into the index (`TopK Order By: pdb.score() desc, id asc`).
- Checked by hand against the live DB: `/health`, `/strategies`, all three 422s, a search per method, the UI headers and the Settings counts.
- Not checked by hand: switching strategies, because only `semantic` is loaded. Try it once `sentence` is loaded (ticket 04).
- `api/static` is gitignored, so the rebuilt bundle isn't in the commit. Run `npm run build` in `ui/` after pulling.
