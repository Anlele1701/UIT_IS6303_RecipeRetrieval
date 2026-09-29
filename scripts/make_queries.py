# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]>=3.2", "httpx>=0.27", "snowballstemmer>=3.1"]
# ///
"""Build the Query set: one search query per sampled Recipe, written by a local Ollama model.

    uv run scripts/make_queries.py                   # 300 Recipes, seed 603 -> eval/queries.jsonl
    QUERY_MODEL=llama3.1:8b uv run scripts/make_queries.py --out /tmp/q.jsonl

Recipes are sampled stratified by category with a fixed seed. Re-running skips Recipes that
already have a query in the output file, so a crash resumes where it stopped.
"""

import argparse
import json
import os
import random
import re
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path

import httpx
import psycopg
import snowballstemmer

ROOT = Path(__file__).resolve().parent.parent
QUERY_SET = ROOT / "eval" / "queries.jsonl"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://recipe:recipe@localhost:5434/recipe")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
QUERY_MODEL = os.environ.get("QUERY_MODEL", "qwen2.5:7b")

SIZE, SEED = 300, 603
ATTEMPTS = 3
MAX_WORDS = 12

LLM = Callable[[str], str]  # prompt -> text


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def sample_recipes(recipes: list[tuple[int, str]], n: int, seed: int) -> list[int]:
    """Pick n Recipe ids from (id, category) pairs, stratified by category.

    Each category gets its proportional share (largest remainder), so tiny categories may get none.
    The result is in sample order and depends only on the pairs, n and seed, not on input order.
    """
    by_cat: dict[str, list[int]] = {}
    for rid, cat in sorted(recipes):
        by_cat.setdefault(cat, []).append(rid)
    total = len(recipes)
    quota = {c: n * len(ids) // total for c, ids in by_cat.items()}
    by_remainder = sorted(by_cat, key=lambda c: (-(n * len(by_cat[c]) % total), c))
    for c in by_remainder[:n - sum(quota.values())]:
        quota[c] += 1

    rng = random.Random(seed)
    picked = [rid for c in sorted(by_cat) for rid in rng.sample(by_cat[c], quota[c])]
    rng.shuffle(picked)  # mix categories so a partial run still covers them
    return picked


# ---------------------------------------------------------------------------
# Prompt and validation
# ---------------------------------------------------------------------------

PROMPT = """You write test searches for a recipe search engine. Given a recipe, write the search a
home cook would type when they want a dish like this but don't know its name.

Rules:
- 3 to 8 words, lowercase, no quotes, no explanation.
- Don't use the recipe's title or most of its words. Describe the dish instead: its main
  ingredients, flavour, texture, cooking method, or when you'd eat it.
- Don't write the word "recipe".

Examples:
Title: Alabama Mud Cake -> rich chocolate sheet cake with marshmallows
Title: Very Easy Risotto -> creamy rice with parmesan and broth
Title: Mackerel Dip -> smoked fish spread for crackers

Title: {title}
Description: {description}
Ingredients:
{ingredients}

Search:"""


def build_prompt(recipe: dict) -> str:
    return PROMPT.format(title=recipe["title"], description=recipe["description"],
                         ingredients="\n".join(f"- {line}" for line in recipe["ingredients"]))


def fold(s: str) -> str:
    """Lowercase without accents, so "jalapeño" matches "jalapeno"."""
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def _norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", fold(s)))


def clean(text: str) -> str:
    """First non-empty line once a "Search:" label is removed, without surrounding quotes or a trailing full stop."""
    lines = (re.sub(r"^\s*search:\s*", "", l, flags=re.I).strip() for l in text.splitlines())
    line = next((l for l in lines if l), "")
    return line.strip("\"'`“”").rstrip(".").strip()


def rejection(query: str, title: str) -> str | None:
    """Why a cleaned query is unusable, or None if it's fine."""
    if not query:
        return "empty"
    if len(query.split()) > MAX_WORDS:
        return "too long"
    if _norm(query) == _norm(title):
        return "same as title"
    title_words = set(content_stems(title))
    if len(title_words) > 2 and title_words <= set(content_stems(query)):
        return "repeats the title"  # has every title word; short titles ("Chicken and Olives") may appear
    return None


def generate_query(recipe: dict, llm: LLM, attempts: int = ATTEMPTS) -> str | None:
    """Ask the LLM for a query, retrying bad output. None after `attempts` bad tries."""
    prompt = build_prompt(recipe)
    for i in range(attempts):
        query = clean(llm(prompt))
        why = rejection(query, recipe["title"])
        if why is None:
            return query
        prompt = build_prompt(recipe).removesuffix("Search:") + \
            f'You wrote "{query}", which was rejected ({why}). Write a different one.\n\nSearch:'
        print(f"  recipe {recipe['id']}: try {i + 1}/{attempts} rejected ({why}): {query!r}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Word overlap
# ---------------------------------------------------------------------------

STOPWORDS = frozenset("""
a about above after again all an and any are as at be because been before being below between both
but by can could did do does doing down during each easy few for from further had has have having
how i if in into is it its just like make me more most my no nor not of off on once only or other
our out over own quick recipe recipes same should so some such than that the their them then there
these they this those through to too under until up very was we were what when where which while
who whom why will with would you your
""".split())

_stemmer = snowballstemmer.stemmer("english")


def content_stems(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z]+", fold(text)) if w not in STOPWORDS]
    return _stemmer.stemWords(words)


def word_overlap(query: str, recipe_text: str) -> float:
    """Share of the query's content words (stopwords dropped, stemmed) found in the Recipe's text."""
    q = content_stems(query)
    if not q:
        return 0.0
    doc = set(content_stems(recipe_text))
    return round(sum(s in doc for s in q) / len(q), 3)


def recipe_text(recipe: dict) -> str:
    return "\n".join([recipe["title"], recipe["description"], *recipe["ingredients"], recipe["directions"]])


# ---------------------------------------------------------------------------
# The Query set file
# ---------------------------------------------------------------------------


def read_query_set(path: Path) -> list[dict]:
    """The rows in `path`. A last line cut off by a crash mid-write is removed from the file."""
    if not path.exists():
        return []
    text = path.read_text()
    lines = text.splitlines()
    rows = []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if n < len(lines) or text.endswith("\n"):
                raise
            print(f"dropping a half-written last line: {line[:60]!r}", file=sys.stderr)
            path.write_text("".join(l + "\n" for l in lines[:-1]))
    return rows


def done_recipe_ids(path: Path) -> set[int]:
    return {r["recipe_id"] for r in read_query_set(path)}


def build_query_set(recipes: list[dict], llm: LLM, model: str, out: Path) -> tuple[int, list[int]]:
    """Append one query per Recipe to `out`, skipping Recipes already in it.

    `recipes` is in sample order; a query's id is its position there, so ids are stable across resumes.
    Returns (queries written, ids of Recipes skipped after bad output).
    """
    position = {r["id"]: f"q{i:03d}" for i, r in enumerate(recipes, 1)}
    existing = read_query_set(out)
    stale = [r["query_id"] for r in existing if position.get(r["recipe_id"]) != r["query_id"]]
    if stale:
        raise SystemExit(f"{out} was built from a different sample (e.g. {stale[0]}); "
                         "use the same --size and --seed, or a new --out")
    done = {r["recipe_id"] for r in existing}
    out.parent.mkdir(parents=True, exist_ok=True)
    written, skipped = 0, []
    with out.open("a") as f:
        for i, recipe in enumerate(recipes, 1):
            if recipe["id"] in done:
                continue
            query = generate_query(recipe, llm)
            if query is None:
                print(f"skipped recipe {recipe['id']} ({recipe['title']}): no usable query", file=sys.stderr)
                skipped.append(recipe["id"])
                continue
            f.write(json.dumps({
                "query_id": f"q{i:03d}", "text": query,
                "recipe_id": recipe["id"], "recipe_title": recipe["title"],
                "word_overlap": word_overlap(query, recipe_text(recipe)), "model": model,
            }, ensure_ascii=False) + "\n")
            f.flush()
            written += 1
            print(f"q{i:03d}  {query}  <- {recipe['title']}", flush=True)
    return written, skipped


# ---------------------------------------------------------------------------
# DB and Ollama
# ---------------------------------------------------------------------------


def load_recipes(conn, ids: list[int]) -> list[dict]:
    """Title, description, ingredients and directions for `ids`, in the same order."""
    rows = conn.execute("""
        SELECT r.id, r.title, r.description, r.directions,
               coalesce(array_agg(i.line ORDER BY i.position) FILTER (WHERE i.line IS NOT NULL), '{}')
        FROM recipe r LEFT JOIN recipe_ingredient i ON i.recipe_id = r.id
        WHERE r.id = ANY(%s) GROUP BY r.id""", [ids]).fetchall()
    by_id = {r[0]: dict(id=r[0], title=r[1], description=r[2], directions=r[3], ingredients=r[4])
             for r in rows}
    return [by_id[i] for i in ids]


def ollama_llm(model: str) -> LLM:
    client = httpx.Client(timeout=120)

    def chat(prompt: str) -> str:
        r = client.post(f"{OLLAMA_URL}/api/chat", json={
            "model": model, "stream": False, "options": {"temperature": 0.7},
            "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["message"]["content"]

    return chat


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--size", type=int, default=SIZE, help="Recipes to sample")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--out", type=Path, default=QUERY_SET)
    return p.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    with psycopg.connect(DATABASE_URL) as conn:
        pairs = conn.execute("SELECT r.id, c.name FROM recipe r JOIN category c ON c.id = r.category_id").fetchall()
        recipes = load_recipes(conn, sample_recipes(pairs, a.size, a.seed))
    print(f"{len(recipes)} Recipes sampled (seed {a.seed}), model {QUERY_MODEL} -> {a.out}", flush=True)
    written, skipped = build_query_set(recipes, ollama_llm(QUERY_MODEL), QUERY_MODEL, a.out)
    print(f"done: {written} written, {len(skipped)} skipped {skipped or ''}, "
          f"{len(done_recipe_ids(a.out))} in {a.out}")
