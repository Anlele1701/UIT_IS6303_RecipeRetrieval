# 05: Build the `fixed` strategy

**What to build:** `fixed` (56-token windows counted with nomic-embed-text's WordPiece tokenizer, cut only between words, ignoring sentence ends, no overlap) is added to the strategy definitions and built with the same command as `sentence`. It becomes a loaded, searchable strategy, and building it doesn't move the other strategies' scores.

Spec: [../../chunking-strategies/spec.md](../../chunking-strategies/spec.md), "Strategies in code". Decisions: settings ticket 03.

**Blocked by:** 04 (Build the `sentence` strategy with the new ingest)

**Status:** done

- [x] The cut has tests: no mid-word cuts, windows of at most 56 tokens, the title prefix not counted, and a Recipe's last window can be shorter
- [x] `chunk fixed` finishes with `loaded_at` set, and its Step chunk count is close to 100,536
- [x] Isolation: semantic's and sentence's top-10 ids and scores are identical before and after the build
- [x] The registry row records `{"tokens": 56, "tokenizer": "bert-base-uncased"}`

## Done (2026-09-27)

- `fixed_cut` in `scripts/ingest.py`: greedy windows of whole words, adding the next word only while the window stays at 56 WordPiece tokens or fewer. Each word's tokens are counted on its own and summed, which is exact for WordPiece because it never merges across a space. `tokenizers` added to the script's inline dependencies and to the dev group (the tests import it).
- Checked the rule before writing it: simulated over all 32,719 Recipes it gives exactly 100,536 windows, mean 46.95 tokens, the settings ticket's numbers.
- Tests: the cut (at most 56, each window full, last one shorter, whole words only, cuts land mid-sentence, short and empty Recipes), the title left out of the count plus the registry parameters (end to end on `recipe_test`), and isolation now checks both semantic and sentence while `fixed` builds.
- Live run on the local DB: `chunk fixed` took about 62 min. 13 transient Ollama errors were retried.
  - `loaded_at` set. The registry row has `{"tokens": 56, "tokenizer": "bert-base-uncased"}`.
  - Counts: 32,719 Summary, 32,719 Ingredients, **100,536 Step** chunks, exactly the simulated number.
  - Every live window is 56 tokens or fewer (max 56, mean 46.95). No single word ran past 56.
  - Isolation: semantic's and sentence's top-10 sparse and dense ids and scores for 3 queries, captured before the build, are byte-identical after it.
  - `EXPLAIN` of a `fixed` search: ParadeDB Base Scan on `chunk_fixed` using `chunk_fixed_search_idx`.

Notes:

- A single word longer than 56 tokens would get a window of its own and go over 56, because the cut never splits a word. It doesn't happen in this data.
- `Tokenizer.from_pretrained` checks the HF Hub, with no pinned revision. It worked from the local cache here, but it prints an unauthenticated-request warning.
