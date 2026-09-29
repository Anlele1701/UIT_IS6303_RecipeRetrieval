# 01: Generate the Query set

**What to build:** One command builds the Query set: 300 Recipes sampled across categories with a fixed seed, one search query per Recipe written by a local Ollama model, each tied to the Recipe it came from. The file is checked into the repo and is the ground truth for every Evaluation run.

Spec: [../spec.md](../spec.md), "Implementation Decisions" (Ground truth, Query set, Query generator).

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Sampling is stratified by category, and the same seed gives the same 300 Recipes
- [x] The model is `qwen2.5:7b` by default and can be overridden by an env var
- [x] The prompt gets the title, description and ingredients, and asks for a short search a home cook would type, without repeating the title
- [x] Output is rejected and retried when it's empty, longer than ~12 words, or equal to the title. After 3 bad tries the Recipe is skipped and logged
- [x] Each JSONL line has query id, text, Recipe id, Recipe title, word overlap and model name
- [x] Word overlap is the share of the query's content words (stopwords dropped, stemmed) found in the Recipe's text
- [x] Re-running skips Recipes that already have a query, so a crash resumes
- [x] Tests use a fake LLM: title rejected and retried, skipped after 3 bad outputs, resume skips finished Recipes, seed is deterministic
- [x] The real set is generated, and about 20 queries are read by hand and look like real searches

## Done (2026-09-27)

- `scripts/make_queries.py` → `eval/queries.jsonl`. Defaults: 300 Recipes, seed 603, `QUERY_MODEL` env var (default `qwen2.5:7b`), `--size/--seed/--out` flags.
- Sampling: proportional per category (largest remainder), sorted input so DB row order doesn't matter, then shuffled so a partial run still covers every category. Categories under ~0.2% of Recipes (holidays, bbq, the junk `251`/`515`) get none.
- The LLM is a `prompt -> text` callable; the Ollama one is `/api/chat`, temperature 0.7.
- Word overlap is against title + description + ingredients + directions, Snowball-stemmed (`snowballstemmer` added to the script deps and the dev group), with a small hand-written stopword list.
- Tests (`tests/test_make_queries.py`, fake LLM): seed determinism and input-order independence, stratified counts, title rejected and retried, skipped after 3 bad outputs, resume skips finished Recipes, JSONL fields, overlap stems and drops stopwords.

Beyond the ticket:

- The first prompt gave "Alabama Mud Cake Recipe" for "Alabama Mud Cake" 8 times out of 10. The prompt now has rules plus 3 examples, and a query holding every content word of a 3+-word title is rejected as "repeats the title" (exact match only for shorter titles, so "chicken in olive herb sauce" is fine for "Chicken and Olives").
- A retry tells the model its last answer and why it was rejected. Without that it repeated the same output 3 times.

Real set:

- 298 queries. Recipes 430 (Banana Oat Muffins) and 7150 (Keto Shrimp Scampi) were skipped after 3 bad tries. A re-run retries them.
- Mean 5.1 words. Word overlap mean 0.80, median 0.80; 125 queries at 1.0, 46 at 0.5 or below. This is the Sparse bias the spec warns about.
- Categories: desserts 36, appetizers 36, side-dish 29, world-cuisine 28, main-dish 26, salad 26, soups 24, bread 23, meat 17, seafood 12, breakfast 12, trusted-brands 11, others under 7.
- 20 read by hand: they read like searches ("creamy clam soup with potatoes" for Quick and Easy Clam Chowder, "egyptian hazelnut sesame dip" for Dukkah). A few are clumsy ("coleslaw meets macaroni creamy chicken tossed") and a few stay close to the title ("no-bake chocolate oatmeal cookies").

Review (2026-09-28):

- Claude read all 298 against their Recipes and flagged 57: 23 wrong facts (qwen often adds "smoked" or "creamy" when it isn't true), 10 broken (2 with Chinese characters), 10 too vague, 6 copying the title, 8 odd wording. Reviewed on a page with the Recipe beside each query; all 57 rewrites were accepted.
- 6 of those rewrites were then swapped again because they broke the "repeats the title" rule. q234 "tomato broccoli soup" breaks it too but was kept on purpose, since it's what a person would type.
- Edited lines keep qwen's text in `edited_from`. The `model` field still says `qwen2.5:7b`, so a script that credits every query to the model needs to check `edited_from` first.
- Word overlap mean went from 0.80 to 0.84. The rewrites fix wrong facts with the Recipe's own words, which helps Sparse a little. Mention this in the report.

Code review fixes (2026-09-28):

- Word overlap folds accents first, so "jalapeño" matches "jalapeno". It used to split into "jalap" + "o". 5 queries changed; mean overlap is now 0.85.
- `clean` removes a "Search:" label on each line before picking the first non-empty one, so "Search:\n<answer>" no longer counts as empty.
- Resume drops a half-written last line left by a crash instead of failing with a JSON error.
- Resume refuses a file built with a different `--size` or `--seed`, because query ids are sample positions and would clash.
