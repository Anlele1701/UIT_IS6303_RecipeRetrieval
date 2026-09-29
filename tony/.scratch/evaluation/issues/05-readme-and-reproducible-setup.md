# 05: README and reproducible setup

**What to build:** A grader can go from a fresh clone to the same eval table by following a README: start the DB, pull the Ollama models, ingest, build the Chunking strategies, generate or reuse the Query set, run the eval and the failure analyzer.

Spec: [../spec.md](../spec.md), user stories 29–30.

**Blocked by:** None (can start immediately). Update the eval steps once 02–04 land.

**Status:** done

- [x] The README covers prerequisites (Docker, uv, Node, Ollama) and every Ollama model needed (`nomic-embed-text`, `qwen2.5:7b`)
- [x] Steps: DB up, `ingest.py load`, `chunk <name>` per strategy (with rough timings), API + UI, eval, analyzer
- [x] It says the Query set is committed, so regenerating it is optional
- [x] Every command in it is run once from a clean shell and works

## Done (2026-09-28)

- `README.md` at the repo root: prerequisites, both Ollama models in one table, the two Hugging Face models that download on first use, env var overrides, then steps 1–7 (DB, `load`, `chunk` x3 with timings from tickets 02/04/05 of the chunking build, Query set, API + UI, eval, analyzer), tests and layout.
- The Query set section says it's committed and how it was made, including the 57 hand rewrites from ticket 01. A regenerated set can't match it, so the README says to pass it with `--queries`.
- Bug found by the clean-shell run: `ingest.py load` crashed on a fresh clone because `data/` is gitignored and never created. Fixed with a `mkdir`, plus a test (`test_load_downloads_the_csv_into_a_missing_data_folder`).

Verified from a fresh `git clone` in an `env -i` shell:

- `uv sync`, `ingest.py load` (28 s including the download, 32,719 Recipes) into a scratch DB `recipe_readme`.
- `chunk semantic|fixed|sentence`, then `drop sentence --yes` and `chunk sentence`, on that DB cut to 30 Recipes.
- `make_queries.py --size 3 --out eval/my-queries.jsonl`, then `evaluate.py --queries eval/my-queries.jsonl` (all 4 configs x 3 strategies) and `failures.py` on it.
- `evaluate.py --configs sparse dense --strategies fixed --limit 20` and `failures.py` on the live DB with the committed Query set.
- `npm install && npm run build`, `uvicorn`: `/health`, `/` and `/search/hybrid` answer.
- `uv run pytest`: 83 passed.

Not run as written, and why:

- `docker compose up -d --wait` ran from the original folder, not the clone. The compose project name is fixed (`is603`), so a run from the clone would recreate the live container with its mounts pointing at the scratch clone. So the "fresh volume builds the schema" path wasn't exercised here. The test fixture builds `recipe_test` from the same `schema.sql`.
- Full-size `chunk` builds (60–85 min each), the 300-query `make_queries.py` and the full default eval (~11 min, run `20260928-002509` in ticket 03) weren't rerun.
- `ollama pull`: both models were already present.
- uvicorn ran on port 8010, since 8000 was in use.
- The local `.venv` in the working folder has a stale `pytest` shebang from an older folder path, so `uv run pytest` fails there (`uv run python -m pytest` works). A fresh clone is fine. Recreate the venv to fix it.

Code review (2026-09-28), two axes:

- Spec: README said the Query set was "written by qwen2.5:7b", which hid the hand rewrites. Fixed. `QUERY_MODEL` was said to be in `api/config.py`. Fixed, and `HYBRID_CANDIDATES`/`RERANK_TOP` added. Dropped an unsourced "15–30 min" for query generation.
- Standards: "vector search" is on CONTEXT.md's avoid list for Dense retrieval, and "Fusion" should be "Fusion baseline". Fixed. Kept: the test's inline CSV row. There's one `load` test, so a shared row builder in conftest would be premature.
