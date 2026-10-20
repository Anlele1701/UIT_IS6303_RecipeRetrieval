"""Independent checker: does a Recipe contain an allergen group, an excluded ingredient, or break a diet?

    uv run scripts/checker.py sample      # the 200-recipe M2 sample -> eval/labels/checker_sample.csv

Used to score constraint violations (CVR, Safe@k in M6), so it must not share anything with the tagger
that drives the hard filter (CLAUDE.md rule 7; tests/test_checker_independence.py): it reads only the
Recipe's title and raw ingredient lines, with its own SQL, and asks a model from another family than the
generator (llama3.1:8b, [S17]). One structured-output call per Recipe covers all its constraints.
Verdicts are cached per (recipe, constraint, model, prompt) in data/cache/checker.jsonl.

A constraint is a string:
  allergen:<code>     one of the FDA nine (milk, egg, fish, crustacean_shellfish, tree_nuts, peanut, wheat, soy, sesame)
  ingredient:<text>   an ingredient the user excluded, in English ("cilantro")
  diet:vegetarian | diet:vegan   "yes" means the Recipe BREAKS the diet
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import psycopg

ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://recipe:recipe@localhost:5435/recipe")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CHECKER_MODEL = os.environ.get("CHECKER_MODEL", "llama3.1:8b")
CACHE = ROOT / "data" / "cache" / "checker.jsonl"
SAMPLE = ROOT / "eval" / "labels" / "allergen_sample.csv"
SAMPLE_OUT = ROOT / "eval" / "labels" / "checker_sample.csv"
SEED = 42

ALLERGEN_TEXT = {  # what each FDA group covers, with common hidden sources (general food-allergen knowledge)
    "milk": "milk or any dairy product made from milk (butter, cheese, cream, sour cream, yogurt, buttermilk, whey, "
            "casein, ghee, milk chocolate)",
    "egg": "eggs or anything made with eggs (mayonnaise, aioli, meringue, egg noodles)",
    "fish": "fish (any finfish) or a product made from fish, including anchovies, anchovy paste, fish sauce, "
            "Worcestershire sauce (made with anchovies), Caesar dressing, bonito flakes and dashi",
    "crustacean_shellfish": "crustacean shellfish (shrimp, prawn, crab, lobster, crayfish) or a product made from them, "
                            "such as shrimp paste; molluscs such as clams, oysters, scallops or squid do not count",
    "tree_nuts": "tree nuts (almond, walnut, pecan, cashew, pistachio, hazelnut, macadamia, Brazil nut, pine nut, "
                 "chestnut) or a product made from them, such as pesto, marzipan, praline or nut butters other than "
                 "peanut butter; coconut does not count",
    "peanut": "peanuts or a product made from peanuts (peanut butter, peanut oil, satay sauce)",
    "wheat": "wheat or a product made with wheat flour: flour, bread, breadcrumbs, pasta, noodles, crackers, "
             "tortillas, cake or biscuit mixes, and regular soy sauce, teriyaki or hoisin sauce",
    "soy": "soybeans or a product made from soy: soy sauce, tofu, miso, edamame, tempeh, soy lecithin",
    "sesame": "sesame seeds or a product made from sesame: sesame oil, tahini, hummus",
}
DIET_TEXT = {
    "vegetarian": "meat, poultry, fish, seafood, gelatin, animal fat or a broth made from meat or fish",
    "vegan": "any animal product: meat, poultry, fish, seafood, dairy, eggs, honey, gelatin or animal fat",
}
PROMPT = """You check a recipe for food restrictions. Judge from what each listed ingredient is actually made of,
not from words in its name (balsamic cream has no dairy; peanut butter has no milk). Count ingredients that
commonly contain the item even when the label does not name it (butter is milk; mayonnaise is egg).
If a line offers alternatives ("butter or margarine"), the item counts if any alternative contains it.
A line marked free of the item ("gluten-free pasta", "dairy-free") does not count for that item.

For each numbered question answer:
- "yes": the recipe contains it (certainly or very likely),
- "unsure": it depends on the brand or the line is too vague to tell,
- "no": nothing in the recipe contains it.
Give evidence_line: the ingredient line, copied exactly, that decides a "yes" or "unsure"; "" for "no".

Recipe: {title}
Ingredients:
{lines}

Questions - does the recipe contain:
{questions}"""
PROMPT_SHA = hashlib.sha256(json.dumps([PROMPT, ALLERGEN_TEXT, DIET_TEXT]).encode()).hexdigest()[:12]  # any wording change re-asks
SCHEMA = {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "object", "properties": {
    "i": {"type": "integer"}, "contains": {"type": "string", "enum": ["yes", "no", "unsure"]},
    "evidence_line": {"type": "string"}}, "required": ["i", "contains", "evidence_line"]}}}, "required": ["answers"]}


@dataclass(frozen=True)
class Verdict:
    contains: str  # yes | no | unsure | error (no valid answer after the retries; scored like unsure)
    evidence_line: str
    evidence_ok: bool  # the evidence is "" for "no", or one of the Recipe's lines


def describe(constraint: str) -> str:
    kind, _, value = constraint.partition(":")
    if kind == "allergen":
        return ALLERGEN_TEXT[value]
    if kind == "diet":
        return DIET_TEXT[value]
    if kind == "ingredient":
        return f"{value}, or a product made from it"
    raise ValueError(f"unknown constraint {constraint!r}")


def recipe_text(conn, recipe_id: int) -> tuple[str, list[str]]:
    title = conn.execute("SELECT title FROM recipe WHERE id = %s", [recipe_id]).fetchone()[0]
    lines = [l for (l,) in conn.execute("SELECT line FROM recipe_ingredient WHERE recipe_id = %s ORDER BY position",
                                        [recipe_id])]
    return title, lines


def cache_key(recipe_id: int, constraint: str) -> str:
    return hashlib.sha256(json.dumps([recipe_id, constraint, CHECKER_MODEL, PROMPT_SHA]).encode()).hexdigest()


def load_cache(path: Path = CACHE) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {row["key"]: row for row in map(json.loads, path.read_text(encoding="utf-8").splitlines())}


def squash(text: str) -> str:
    return " ".join(text.split())


def parse(answers: list[dict], constraints: list[str], lines: list[str]) -> dict[str, Verdict]:
    """Model answers -> a Verdict per constraint; a missing answer is "error" (never a silent "no")."""
    by_i = {a.get("i"): a for a in answers}
    known = {squash(l) for l in lines}
    out = {}
    for k, c in enumerate(constraints, 1):
        a = by_i.get(k, {})
        contains = a.get("contains") if a.get("contains") in {"yes", "no", "unsure"} else "error"
        ev = squash(a.get("evidence_line") or "")
        ok = (ev == "") if contains == "no" else ev in known  # the source often has double spaces
        out[c] = Verdict(contains, ev, ok)
    return out


BATCH = 6  # questions per call: long answer lists were where the 8B model broke the JSON
ATTEMPTS = 3
MAX_TOKENS = 1024  # generated tokens per checker call (a cap, not a target)
RETRIES: list[int] = []  # Recipes with at least one incomplete reply (reported in the run's JSON)


def complete(answers: list[dict], n: int) -> bool:
    return {a.get("i") for a in answers if a.get("contains") in {"yes", "no", "unsure"}} >= set(range(1, n + 1))


def ask(client: httpx.Client, title: str, lines: list[str], constraints: list[str]) -> list[dict]:
    prompt = PROMPT.format(title=title, lines="\n".join(f"- {l}" for l in lines),
                           questions="\n".join(f"{k}. {describe(c)}" for k, c in enumerate(constraints, 1)))
    r = client.post(f"{OLLAMA_URL}/api/chat", json={
        "model": CHECKER_MODEL, "stream": False, "format": SCHEMA,
        # num_predict: without a cap a looping reply ran 15 minutes per call under Ollama's context shift (M6b);
        # six answers with their evidence lines need a few hundred tokens. The cache key (PROMPT_SHA) is unchanged.
        "options": {"temperature": 0, "seed": SEED, "num_ctx": 4096, "num_predict": MAX_TOKENS},
        "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    try:
        return json.loads(r.json()["message"]["content"]).get("answers", [])
    except json.JSONDecodeError:  # a reply cut at MAX_TOKENS: incomplete, so check() asks again, then "error"
        return []


def check(conn, client: httpx.Client, recipe_id: int, constraints: list[str],
          cache: dict[str, dict] | None = None) -> dict[str, Verdict]:
    """Verdicts for one Recipe; only uncached constraints go to the model."""
    cache = load_cache() if cache is None else cache
    todo = [c for c in constraints if cache_key(recipe_id, c) not in cache]
    if todo:
        title, lines = recipe_text(conn, recipe_id)
        fresh = {}
        for b in range(0, len(todo), BATCH):
            part = todo[b:b + BATCH]
            for _ in range(ATTEMPTS):  # an empty or partial reply is asked again; then "error"
                answers = ask(client, title, lines, part)
                if complete(answers, len(part)):
                    break
                if recipe_id not in RETRIES:
                    RETRIES.append(recipe_id)
            fresh.update(parse(answers, part, lines))
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE, "a", encoding="utf-8") as f:
            for c, v in fresh.items():
                row = {"key": cache_key(recipe_id, c), "recipe_id": recipe_id, "constraint": c, "model": CHECKER_MODEL,
                       "prompt_sha": PROMPT_SHA, **v.__dict__}
                cache[row["key"]] = row
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {c: Verdict(cache[cache_key(recipe_id, c)]["contains"], cache[cache_key(recipe_id, c)]["evidence_line"],
                       cache[cache_key(recipe_id, c)]["evidence_ok"]) for c in constraints}


M2_CONSTRAINTS = [f"allergen:{a}" for a in ALLERGEN_TEXT] + [f"diet:{d}" for d in DIET_TEXT]


def run_sample():
    with open(SAMPLE, newline="", encoding="utf-8") as f:
        ids = [int(r["recipe_id"]) for r in sorted(csv.DictReader(f), key=lambda r: int(r["sample_order"]))]
    cache, started = load_cache(), time.time()
    with psycopg.connect(DATABASE_URL) as conn, httpx.Client(timeout=900) as client, \
            open(SAMPLE_OUT, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["recipe_id", "constraint", "contains", "evidence_line", "evidence_ok"])
        for n, rid in enumerate(ids, 1):
            for c, v in check(conn, client, rid, M2_CONSTRAINTS, cache).items():
                w.writerow([rid, c, v.contains, v.evidence_line, v.evidence_ok])
            out.flush()
            print(f"{n}/{len(ids)}  {(time.time() - started) / n:.1f} s/recipe", flush=True)
    meta = {"model": CHECKER_MODEL, "prompt_sha": PROMPT_SHA, "seed": SEED, "constraints": M2_CONSTRAINTS,
            "recipes": len(ids), "seconds": round(time.time() - started), "retried_recipes": RETRIES}
    SAMPLE_OUT.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["sample"])
    p.parse_args()
    run_sample()


if __name__ == "__main__":
    main()
