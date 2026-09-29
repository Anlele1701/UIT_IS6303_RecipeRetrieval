# 04: Build the `sentence` strategy with the new ingest

**What to build:** A developer runs one command to build a Chunking strategy end to end, and `sentence` (3 sentences per Step chunk) becomes a loaded, searchable strategy. Building it doesn't change any other strategy's scores.

The ingest script holds every strategy's definition in one place (name, method, parameters, cut). It builds into a staging table, checks completeness, then indexes and attaches the table as the partition and marks it loaded in one transaction. A crashed build is cleaned up by rerunning it. A loaded strategy is only removed by an explicit drop (which needs confirmation). Reloading the source data is refused while any strategy exists.

`sentence` goes first because it's the simplest cut and needs no tokenizer, so the lifecycle is proven on the easy case.

Spec: [../../chunking-strategies/spec.md](../../chunking-strategies/spec.md), "Slice 2". Decisions: ingest ticket 08, settings ticket 03, registry ticket 05.

**Blocked by:** 02 (Semantic search runs on the partitioned `chunk`)

**Status:** done

- [x] `chunk sentence` finishes with `loaded_at` set, and its Step chunk count is close to 110,314
- [x] Isolation: semantic's top-10 BM25 and dense ids and scores, captured before the build, are identical after it
- [x] `EXPLAIN` for a `sentence` search uses its own partition's index
- [x] Killing the build mid-load, then rerunning it, cleans up and finishes
- [x] `chunk sentence` on a loaded `sentence` refuses and points to `drop`
- [x] `drop <name>` on a loaded strategy refuses without `--yes`
- [x] `load` refuses while strategies exist, and names them
- [x] A second concurrent `chunk sentence` fails fast
- [x] The old `index` command is gone
- [x] The completeness checks (1 Summary, 1 Ingredients, at least 1 Step per Recipe; gap-free positions; no null embeddings; ADR-0001 check) have tests

## Done (2026-09-27)

- `scripts/ingest.py` rewritten around `load` / `chunk <name>` / `drop <name> [--yes]`. `STRATEGIES` holds `semantic` and `sentence` (method, parameters, cut); the cut functions take the parameters with no defaults, so the dict is the only copy.
- Tests in `tests/test_ingest.py` at three seams: the sentence cut, `staging_problems` (each completeness check named), and the commands end to end on `recipe_test` with only the Ollama embed call stubbed (build, isolation, crash + rerun, failed check, refusals, concurrent run, drop, load, `index` gone).
- Live run on the local DB:
  - Started `chunk sentence`, ran a second one while it loaded (failed fast: "already being built"), then `kill -9` after 2 batches. The DB kept `sentence` unloaded with 2,048 staging rows.
  - The rerun discarded that, loaded all 32,719 Recipes in about 85 min (Ollama-bound; a few transient Ollama `tokenize` EOFs were retried), and attached `chunk_sentence`.
  - Counts: 32,719 Summary, 32,719 Ingredients, **110,314 Step** chunks, exactly the simulated number.
  - Isolation: semantic's top-10 sparse and dense ids and scores for 3 queries, captured before the build, are identical after it.
  - `EXPLAIN` of a `sentence` search: ParadeDB Base Scan on `chunk_sentence` using `chunk_sentence_search_idx`.
  - `chunk sentence` → "sentence is loaded; run `drop sentence` first". `drop sentence` → "sentence is loaded with 175752 chunks; rerun with --yes to drop it". `load` → "drop strategies first: semantic, sentence". `chunk foo` lists the known names. `index` is no longer a command.

Notes:

- The live build ran on the pre-review code. The review changed only `load` (check and truncate in one transaction, with `chunking_strategy` locked so a `chunk` can't register in between), `finish` (dropped a redundant `ANALYZE chunk`; `indexes.sql` already analyzes the new partition) and the staging key names (`chunk_<name>_pkey` / `_key`). The live refusal checks above ran on the new code.
- Staging gets its PK and UNIQUE up front (not in the spec) so the attach doesn't build them under its lock. The attach still validates the FKs to `recipe` and `chunking_strategy` with a scan, since `LIKE` doesn't copy FKs.
- A Recipe with empty directions would fail "at least 1 Step chunk" under any strategy. The live data has none.
- `.venv/bin/pytest` has a stale shebang (old project path), so `uv run pytest` fails; `.venv/bin/python -m pytest` works. Recreate the venv to fix.
